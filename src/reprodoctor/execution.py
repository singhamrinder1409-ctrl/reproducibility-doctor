"""Experimental local Docker executor. Live acceptance gates are still pending.

Only fixed infrastructure commands run on the host. Target argv travels as JSON
to a Python bootstrap IN the container, after inspection and kernel preflight.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import shutil
import signal
import tarfile
import tempfile
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from threading import current_thread, main_thread

from . import __version__
from .container_scripts import EXECUTE, PROBE, RECEIVE
from .intake import IntakeError, canonical
from .planning import digest, validate_approval, validate_plan, wheel_inventory
from .processes import ProcessInterrupted, bounded_process
from .snapshot import load_snapshot

LABEL = "org.reprodoctor.run"
PLAN_LABEL = "org.reprodoctor.plan"


class RuntimeFailure(IntakeError):
    def __init__(self, message: str, evidence: dict | None = None):
        super().__init__(message)
        self.evidence = evidence


class RuntimeBudgetExpired(RuntimeFailure):
    pass


@contextmanager
def cancellation_signals():
    def cancel(signum, frame):
        raise KeyboardInterrupt()

    previous = None
    if current_thread() is main_thread():
        previous = signal.signal(signal.SIGTERM, cancel)
    try:
        yield
    finally:
        if previous is not None:
            signal.signal(signal.SIGTERM, previous)


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


class Docker:
    """Local Unix socket only; no host Docker config, contexts, credentials or proxy."""

    def __init__(self, home: Path, socket: str):
        if not socket.startswith("/") or any(ord(c) < 32 for c in socket):
            raise RuntimeFailure("Docker socket must be an explicit absolute local Unix path")
        binary = shutil.which("docker", path=os.defpath + ":/usr/local/bin:/opt/homebrew/bin")
        if binary is None:
            raise RuntimeFailure("Docker CLI is not installed; live execution unavailable")
        self.prefix = [binary, "--host", "unix://" + socket, "--config", str(home)]
        self.environment = {"PATH": os.defpath, "HOME": str(home), "LC_ALL": "C"}
        self.home = home

    def command(
        self,
        args: list[str],
        *,
        seconds: float = 30,
        cap: int = 1024 * 1024,
        stdin=None,
        checked: bool = True,
    ) -> dict:
        result = bounded_process(
            self.prefix + args,
            environment=self.environment,
            cwd=str(self.home),
            seconds=seconds,
            cap=cap,
            stdin=stdin,
        )
        if checked and (
            result["timed_out"]
            or result["exit_code"]
            or result["stdout"]["truncated"]
            or result["stderr"]["truncated"]
        ):
            evidence = {
                **result,
                "operation": args[:2],
                "stdout": {k: v for k, v in result["stdout"].items() if k != "text"},
            }
            raise RuntimeFailure(
                "Docker infrastructure command failed, timed out or exceeded output budget",
                evidence,
            )
        return result

    def document(self, args: list[str], *, seconds: float = 30) -> dict:
        result = self.command(args, seconds=seconds)
        try:
            value = json.loads(result["stdout"]["text"])
            if not isinstance(value, dict):
                raise ValueError()
        except (ValueError, RecursionError) as exc:
            raise RuntimeFailure("Docker returned unexpected metadata") from exc
        return value


def verify_server(info: dict) -> dict:
    security = info.get("SecurityOptions", [])
    if (
        info.get("OSType") != "linux"
        or info.get("CgroupVersion") != "2"
        or (not isinstance(security, list) or "name=seccomp,profile=builtin" not in security)
    ):
        raise RuntimeFailure(
            "Requires Linux cgroup v2 and Docker builtin seccomp; missing controls fail closed"
        )
    return {
        key: info.get(key)
        for key in ("ServerVersion", "OSType", "CgroupVersion", "SecurityOptions")
    }


def verify_image(image: dict, settings: dict) -> dict:
    identity = image.get("Id")
    desired = settings["image"].split("@", 1)[1]
    if not isinstance(identity, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", identity):
        raise RuntimeFailure("Image ID could not be established")
    if not any(
        isinstance(ref, str) and ref.endswith("@" + desired)
        for ref in image.get("RepoDigests", []) or []
    ):
        raise RuntimeFailure("Selected image digest is not verified in the local image store")
    if (
        image.get("Os") != "linux"
        or image.get("Architecture") != settings["platform"].split("/")[1]
    ):
        raise RuntimeFailure("Local image does not match the approved platform")
    config = image.get("Config")
    if not isinstance(config, dict) or config.get("Volumes"):
        raise RuntimeFailure("Images declaring volumes or missing configuration are unsupported")
    keys = []
    for entry in config.get("Env", []) or []:
        if not isinstance(entry, str) or not re.fullmatch(
            r"[A-Za-z_][A-Za-z0-9_]*=.*", entry, re.S
        ):
            raise RuntimeFailure("Image environment cannot be cleared deterministically")
        keys.append(entry.split("=", 1)[0])
    return {
        "id": identity,
        "repo_digest": desired,
        "platform": settings["platform"],
        "image_environment_keys_cleared": sorted(set(keys)),
    }


def create_arguments(name: str, run_id: str, plan: dict, image: dict) -> list[str]:
    settings = plan["payload"]["container"]
    limits = settings["limits"]
    args = [
        "container",
        "create",
        "--name",
        name,
        "--pull=never",
        "--platform",
        settings["platform"],
        "--label",
        LABEL + "=" + run_id,
        "--label",
        PLAN_LABEL + "=" + plan["plan_digest"],
        "--network=none",
        "--ipc=private",
        "--cgroupns=private",
        "--read-only",
        "--init",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges=true",
        "--user=65532:65532",
        "--cpus=1",
        "--memory=" + str(limits["memory_bytes"]),
        "--memory-swap=" + str(limits["memory_bytes"]),
        "--pids-limit=128",
        "--ulimit=core=0:0",
        "--ulimit=nofile=256:256",
        "--shm-size=" + str(settings["shared_memory_bytes"]),
        "--log-driver=none",
        "--no-healthcheck",
        "--restart=no",
        "--stop-timeout=1",
        "--workdir=/",
        "--entrypoint=/usr/local/bin/python",
    ]
    for path, size in settings["writable_tmpfs"].items():
        args += ["--tmpfs", f"{path}:rw,nosuid,nodev,size={size},uid=65532,gid=65532,mode=0700"]
    for key in image["image_environment_keys_cleared"]:
        args += ["--env", key + "="]
    for key, value in settings["environment"].items():
        args += ["--env", key + "=" + value]
    return args + [image["id"], "-I", "-S", "-u", "-c", "import time; time.sleep(600)"]


def verify_container(document: dict, plan: dict, run_id: str, image: dict) -> dict:
    config, host = document.get("Config", {}), document.get("HostConfig", {})
    settings = plan["payload"]["container"]
    limits = settings["limits"]
    expected = {
        "NetworkMode": "none",
        "IpcMode": "private",
        "CgroupnsMode": "private",
        "ReadonlyRootfs": True,
        "Privileged": False,
        "NanoCpus": 1_000_000_000,
        "Memory": limits["memory_bytes"],
        "MemorySwap": limits["memory_bytes"],
        "PidsLimit": limits["pids"],
        "ShmSize": settings["shared_memory_bytes"],
        "CapDrop": ["ALL"],
        "Init": True,
    }
    if any(host.get(key) != value for key, value in expected.items()):
        raise RuntimeFailure("Runtime did not apply the approved container settings")
    security = host.get("SecurityOpt", [])
    if security not in (["no-new-privileges=true"], ["no-new-privileges"]):
        raise RuntimeFailure("Unexpected container security options")
    if (
        host.get("Binds")
        or host.get("Mounts")
        or host.get("VolumesFrom")
        or (
            host.get("PortBindings")
            or host.get("CapAdd")
            or host.get("Devices")
            or host.get("DeviceRequests")
            or host.get("PidMode")
            or host.get("UTSMode")
        )
    ):
        raise RuntimeFailure("Unexpected mount, namespace, device, capability or port access")
    if (
        host.get("LogConfig", {}).get("Type") != "none"
        or host.get("RestartPolicy", {}).get("Name") != "no"
    ):
        raise RuntimeFailure("Unbounded runtime logging or restart policy is not allowed")
    ulimits = {entry["Name"]: (entry["Soft"], entry["Hard"]) for entry in host.get("Ulimits", [])}
    if ulimits != {"core": (0, 0), "nofile": (256, 256)}:
        raise RuntimeFailure("Core/file descriptor limits do not match approval")
    if config.get("User") != "65532:65532" or config.get("Healthcheck", {}).get("Test") != ["NONE"]:
        raise RuntimeFailure("Unexpected identity or image healthcheck")
    if (
        config.get("Labels", {}).get(LABEL) != run_id
        or config.get("Labels", {}).get(PLAN_LABEL) != plan["plan_digest"]
    ):
        raise RuntimeFailure("Container ownership labels do not match the approved run")
    if document.get("Image") != image["id"] or config.get("Entrypoint") != [
        "/usr/local/bin/python"
    ]:
        raise RuntimeFailure("Image or entrypoint changed")
    expected_env = {key: "" for key in image["image_environment_keys_cleared"]}
    expected_env.update(settings["environment"])
    entries = config.get("Env", [])
    try:
        actual_env = dict(entry.split("=", 1) for entry in entries)
    except (ValueError, TypeError) as exc:
        raise RuntimeFailure("Container environment is malformed") from exc
    if actual_env != expected_env:
        raise RuntimeFailure("Container inherited unexpected environment values")
    tmpfs = host.get("Tmpfs", {})
    if set(tmpfs) != set(settings["writable_tmpfs"]):
        raise RuntimeFailure("Writable tmpfs paths do not match approval")
    for path, size in settings["writable_tmpfs"].items():
        required = {"rw", "nosuid", "nodev", f"size={size}", "uid=65532", "gid=65532", "mode=0700"}
        if set(tmpfs[path].split(",")) != required:
            raise RuntimeFailure("Writable tmpfs options do not match approval")
    for mount in document.get("Mounts", []):
        if mount.get("Type") != "tmpfs" or mount.get("Destination") not in tmpfs:
            raise RuntimeFailure("Runtime exposed an unexpected mount")
    return {
        "image_id": image["id"],
        "host_config_verified": expected,
        "environment_keys": sorted(actual_env),
        "healthcheck_disabled": True,
    }


def verify_probe(probe: dict, settings: dict) -> dict:
    def require(condition):
        if not condition:
            raise RuntimeFailure("Kernel preflight could not establish every required control")

    try:
        require(probe["implementation"] == "cpython" and probe["python"][:2] == [3, 12])
        require(probe["uid"] == probe["gid"] == 65532)
        require(probe["rlimits"] == {"core": [0, 0], "nofile": [256, 256]})
        require(probe["network_interfaces"] == ["lo"])
        status = probe["status"]
        require(status["NoNewPrivs"] == "1" and status["Seccomp"] == "2")
        require(all(int(status[key], 16) == 0 for key in ("CapEff", "CapPrm", "CapBnd")))
        groups = probe["cgroups"]
        require(int(groups["memory.max"]) == settings["limits"]["memory_bytes"])
        require(int(groups["memory.swap.max"]) == 0 and int(groups["pids.max"]) == 128)
        quota, period = map(int, groups["cpu.max"].split())
        require(quota > 0 and period > 0 and quota == period)
        for path in ("/", "/sys", "/sys/fs/cgroup", "/proc/sys"):
            require(probe["paths"][path]["read_only"] is True)
        for path, size in {
            **settings["writable_tmpfs"],
            "/dev/shm": settings["shared_memory_bytes"],
        }.items():
            actual = probe["paths"][path]
            require(actual["read_only"] is False and 0 < actual["bytes"] <= size)
            require(actual["mount"]["type"] == "tmpfs")
        require(not probe["managed_files_writable"])
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeFailure("Kernel preflight could not establish every required control") from exc
    return probe


def stage_transfer(fileobj, snapshot: Path, wheelhouse: Path | None, plan: dict) -> dict:
    """Build tar from verified bytes, never extract a target archive on the host."""
    manifest, contents = load_snapshot(snapshot)
    if {key: manifest[key] for key in ("commit", "content_digest")} != plan["payload"][
        "repository"
    ]:
        raise RuntimeFailure("Snapshot changed before staging")
    if wheel_inventory(wheelhouse) != plan["payload"]["artifacts"]:
        raise RuntimeFailure("Wheel artifacts changed before staging")
    entries = []
    with tarfile.open(fileobj=fileobj, mode="w") as archive:
        for entry in manifest["files"]:
            _tar_entry(
                archive,
                entries,
                "workspace/" + entry["path"],
                contents[entry["path"]],
                0o755 if entry["mode"] == "100755" else 0o644,
            )
        for wheel in plan["payload"]["artifacts"]["files"]:
            path = wheelhouse / wheel["name"]
            if path.is_symlink():
                raise RuntimeFailure("Wheel became a symlink before staging")
            with path.open("rb") as stream:
                data = stream.read(32 * 1024 * 1024 + 1)
            if len(data) != wheel["size"] or hashlib.sha256(data).hexdigest() != wheel["sha256"]:
                raise RuntimeFailure("Actual wheel bytes changed before staging")
            _tar_entry(archive, entries, "wheels/" + wheel["name"], data, 0o444)
    fileobj.seek(0)
    return {
        "digest": digest(sorted(entries, key=lambda e: e["path"])),
        "files": len(entries),
        "bytes": sum(entry["size"] for entry in entries),
    }


def _tar_entry(archive, entries: list, name: str, data: bytes, mode: int) -> None:
    info = tarfile.TarInfo(name)
    info.size, info.mode, info.uid, info.gid = len(data), mode, 65532, 65532
    archive.addfile(info, io.BytesIO(data))
    entries.append(
        {"path": name, "size": len(data), "mode": mode, "sha256": hashlib.sha256(data).hexdigest()}
    )


def _record(path: Path, document: dict, *, new: bool = False) -> None:
    # Private host-created audit data. A same-directory stage makes updates atomic.
    descriptor, temporary = tempfile.mkstemp(prefix=".doctor-record-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            count = 0
            for chunk in json.JSONEncoder(ensure_ascii=True, indent=2).iterencode(document):
                count += len(chunk)
                if count > 64 * 1024 * 1024:
                    raise RuntimeFailure("Execution record exceeds its byte budget")
                stream.write(chunk)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        if new:
            os.link(temporary, path)  # Atomic no-overwrite publication.
        else:
            os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def remove_owned(docker: Docker, journal: dict) -> dict:
    """Remove one exactly named/labeled container. Never prune or select broad labels."""
    run_id, name = journal.get("run_id"), journal.get("container_name")
    plan_hash = journal.get("plan_digest")
    if (
        not isinstance(run_id, str)
        or not re.fullmatch(r"[0-9a-f]{32}", run_id)
        or name != "reprodoctor-" + run_id
        or not isinstance(plan_hash, str)
        or not re.fullmatch(r"[0-9a-f]{64}", plan_hash)
    ):
        raise RuntimeFailure("Invalid run journal identity")
    listing = docker.command(
        ["container", "ls", "--all", "--filter", "name=^/" + name + "$", "--format", "{{.Names}}"],
        seconds=10,
    )
    if not listing["stdout"]["text"].strip():
        return {"status": "absent", "container_name": name}
    metadata = docker.document(["container", "inspect", name, "--format", "{{json .}}"], seconds=10)
    labels = metadata.get("Config", {}).get("Labels", {})
    if labels.get(LABEL) != run_id or labels.get(PLAN_LABEL) != journal.get("plan_digest"):
        raise RuntimeFailure("Container labels do not match journal; refusing removal")
    docker.command(["container", "rm", "--force", "--volumes", name], seconds=10)
    remaining = docker.command(
        ["container", "ls", "--all", "--filter", "name=^/" + name + "$", "--format", "{{.Names}}"],
        seconds=10,
    )
    if remaining["stdout"]["text"].strip():
        raise RuntimeFailure("Container remains after removal")
    return {"status": "removed", "container_name": name}


def execute_plan(
    plan: dict,
    approval: dict,
    snapshot: Path,
    output: Path,
    *,
    wheelhouse: Path | None = None,
    socket: str = "/var/run/docker.sock",
    docker_factory=Docker,
    experimental: bool = False,
) -> dict:
    """Prototype: approval/preflight gates are mandatory; live acceptance is pending."""
    if not experimental:
        raise IntakeError(
            "Execution is experimental and needs explicit opt-in; live validation pending"
        )
    validate_plan(plan, snapshot, wheelhouse=wheelhouse)
    validate_approval(approval, plan)
    if output.exists() or output.is_symlink() or not output.parent.is_dir():
        raise IntakeError("Execution output must be a new file in an existing directory")
    for root in (snapshot, wheelhouse):
        if root is not None and output.resolve().is_relative_to(root.resolve()):
            raise IntakeError("Execution records must be outside snapshot/wheelhouse")
    run_id = uuid.uuid4().hex
    journal_path = output.with_name(output.name + ".run.json")
    journal = {
        "schema_version": 1,
        "kind": "execution_journal",
        "run_id": run_id,
        "container_name": "reprodoctor-" + run_id,
        "plan_digest": plan["plan_digest"],
        "state": "preparing",
        "started_at": _utc(),
    }
    _record(journal_path, journal, new=True)
    started = time.monotonic()
    settings = plan["payload"]["container"]
    deadline = started + settings["limits"]["run_seconds"]
    report = {
        "schema_version": 1,
        "kind": "execution_report",
        "tool_version": __version__,
        "experimental": True,
        "live_validation": "pending",
        "run_id": run_id,
        "plan_digest": plan["plan_digest"],
        "repository": plan["payload"]["repository"],
        "started_at": journal["started_at"],
        "execution_status": "not_run",
        "steps": [],
        "preflight": {},
        "approved_container_settings": settings,
        "artifacts": plan["payload"]["artifacts"],
        "engine": plan["payload"]["planner"],
        "cleanup": {"status": "not_needed"},
    }
    docker = None
    touched = False
    active_step = None
    step_started = None

    def remaining(maximum=30):
        value = min(maximum, deadline - time.monotonic())
        if value <= 0:
            raise RuntimeBudgetExpired("Whole-run wall-clock budget exhausted")
        return value

    with cancellation_signals(), tempfile.TemporaryDirectory(prefix="doctor-runtime-") as temporary:
        home = Path(temporary)
        try:
            docker = docker_factory(home, socket)
            info = docker.document(["info", "--format", "{{json .}}"], seconds=remaining())
            report["preflight"]["server_observed"] = {
                key: info.get(key)
                for key in ("ServerVersion", "OSType", "CgroupVersion", "SecurityOptions")
            }
            report["preflight"]["server"] = verify_server(info)
            image = verify_image(
                docker.document(
                    ["image", "inspect", settings["image"], "--format", "{{json .}}"],
                    seconds=remaining(),
                ),
                settings,
            )
            report["preflight"]["image"] = image
            # Stage actual verified bytes before creating a container; no target code runs.
            with tempfile.TemporaryFile() as archive:
                transfer = stage_transfer(archive, snapshot, wheelhouse, plan)
                touched = True  # Creation may succeed even if the client is interrupted.
                journal["state"] = "creating"
                _record(journal_path, journal)
                docker.command(
                    create_arguments(journal["container_name"], run_id, plan, image),
                    seconds=remaining(),
                )
                name = journal["container_name"]
                metadata = docker.document(
                    ["container", "inspect", name, "--format", "{{json .}}"], seconds=remaining()
                )
                report["preflight"]["container_observed"] = {
                    "image_id": metadata.get("Image"),
                    "host_config": {
                        key: metadata.get("HostConfig", {}).get(key)
                        for key in (
                            "NetworkMode",
                            "ReadonlyRootfs",
                            "Memory",
                            "MemorySwap",
                            "PidsLimit",
                            "NanoCpus",
                            "SecurityOpt",
                            "Privileged",
                            "Binds",
                            "Devices",
                            "Tmpfs",
                        )
                    },
                }
                report["preflight"]["container"] = verify_container(metadata, plan, run_id, image)
                docker.command(["container", "start", name], seconds=remaining())
                prefix = [
                    "container",
                    "exec",
                    "--interactive",
                    name,
                    "/usr/local/bin/python",
                    "-I",
                    "-S",
                    "-u",
                    "-c",
                ]
                probe = docker.document(prefix + [PROBE], seconds=remaining())
                report["preflight"]["kernel"] = probe
                verify_probe(probe, settings)
                result = docker.command(prefix + [RECEIVE], seconds=remaining(), stdin=archive)
                if json.loads(result["stdout"]["text"]) != transfer:
                    raise RuntimeFailure(
                        "Transferred file bytes differ from the approved snapshot/artifacts"
                    )
                report["preflight"]["transfer"] = transfer
            report["preflight"]["status"] = "verified_for_this_run"
            journal["state"] = "running"
            _record(journal_path, journal)
            log_left = settings["limits"]["run_log_bytes"]
            report["execution_status"] = "completed"
            for step in plan["payload"]["steps"]:
                budget = remaining(settings["limits"]["step_seconds"])
                if step["disposition"] == "excluded_by_reviewer":
                    report["steps"].append(
                        {
                            "id": step["instruction"]["id"],
                            "status": "excluded",
                            "decision": step["decision"],
                        }
                    )
                    continue
                effective = step["effective"]
                record = {
                    "id": step["instruction"]["id"],
                    "effective": effective,
                    "source": step["instruction"],
                    "decision": step["decision"],
                    "started_at": _utc(),
                    "status": "starting",
                }
                # Preserve an attempted step even if transport/cancellation prevents a return.
                step_started = time.monotonic()
                report["steps"].append(record)
                active_step = record
                if effective["kind"] == "set_environment":
                    record.update(status="state_updated", exit_code=None, seconds=0)
                else:
                    result = docker.command(
                        prefix + [EXECUTE],
                        stdin=io.BytesIO(canonical(effective)),
                        seconds=budget,
                        cap=min(settings["limits"]["log_bytes_per_stream_per_step"], log_left // 2),
                        checked=False,
                    )
                    record.update(result)
                    record["exit_code_source"] = "docker_exec_cli"
                    record["signal"] = None  # 128+N is ambiguous; do not invent a signal.
                    log_left -= (
                        result["stdout"]["captured_bytes"] + result["stderr"]["captured_bytes"]
                    )
                    record["status"] = (
                        "timed_out"
                        if result["timed_out"]
                        else "passed"
                        if result["exit_code"] == 0
                        else "failed"
                    )
                record["finished_at"] = _utc()
                active_step = None
                if record["status"] in {"failed", "timed_out"}:
                    report["execution_status"] = record["status"]
                    break
        except RuntimeBudgetExpired as exc:
            report["execution_status"] = "timed_out"
            report["error"] = str(exc)
            if active_step is not None:
                active_step.update(
                    status="timed_out",
                    error=str(exc),
                    output_capture_status="unavailable_on_budget_expiry",
                    finished_at=_utc(),
                    seconds=round(time.monotonic() - step_started, 6),
                )
        except Exception as exc:
            report["execution_status"] = "infrastructure_error"
            report["error"] = str(exc)
            if active_step is not None:
                active_step.update(
                    status="infrastructure_error",
                    error=str(exc),
                    output_capture_status="unavailable",
                    finished_at=_utc(),
                    seconds=round(time.monotonic() - step_started, 6),
                )
            if isinstance(exc, RuntimeFailure) and exc.evidence is not None:
                report["infrastructure_evidence"] = exc.evidence
        except (KeyboardInterrupt, EOFError) as exc:
            report["execution_status"] = "cancelled"
            if active_step is not None:
                if isinstance(exc, ProcessInterrupted):
                    active_step.update(exc.result)
                    active_step["output_capture_status"] = "partial_on_interrupt"
                    active_step["exit_code_source"] = "interrupted_host_docker_cli"
                    active_step["signal"] = None
                else:
                    active_step["output_capture_status"] = "unavailable_on_interrupt"
                active_step["status"] = "cancelled"
                active_step["finished_at"] = _utc()
                active_step.setdefault("seconds", round(time.monotonic() - step_started, 6))
        finally:
            if docker is not None and touched:
                try:
                    state = docker.document(
                        [
                            "container",
                            "inspect",
                            journal["container_name"],
                            "--format",
                            "{{json .State}}",
                        ],
                        seconds=5,
                    )
                    report["container_state_before_cleanup"] = {
                        key: state.get(key) for key in ("Running", "ExitCode", "OOMKilled", "Error")
                    }
                except (Exception, KeyboardInterrupt) as exc:
                    # Diagnostic collection must never prevent the removal attempt.
                    report["container_state_before_cleanup"] = {
                        "status": "unavailable",
                        "error": str(exc),
                    }
                try:
                    report["cleanup"] = remove_owned(docker, journal)
                except (Exception, KeyboardInterrupt) as exc:
                    report["cleanup"] = {
                        "status": "failed",
                        "error": str(exc),
                        "journal": str(journal_path),
                    }
            report["finished_at"] = _utc()
            report["seconds"] = round(time.monotonic() - started, 6)
            seen = {step["id"] for step in report["steps"]}
            report["steps_not_reached"] = [
                step["instruction"]["id"]
                for step in plan["payload"]["steps"]
                if step["instruction"]["id"] not in seen
            ]
            report["limitations"] = [
                "Live containment acceptance tests are pending.",
                "Zero status does not prove application correctness or arbitrary-code safety.",
                "Codes 125/126/127 may be Docker errors or the program's own exit status.",
                "Background descendants can persist inside the container until removal.",
                "Host crashes/SIGKILL or daemon failure can prevent cleanup; use the journal.",
            ]
            journal["state"] = (
                "cleanup_failed" if report["cleanup"]["status"] == "failed" else "finished"
            )
            journal["cleanup"] = report["cleanup"]
            _record(journal_path, journal)
            _record(output, report, new=True)
    return report


def recover(
    journal_path: Path, *, socket: str = "/var/run/docker.sock", docker_factory=Docker
) -> dict:
    from .planning import read_document

    journal = read_document(journal_path)
    if (
        type(journal.get("schema_version")) is not int
        or journal.get("schema_version") != 1
        or journal.get("kind") != "execution_journal"
    ):
        raise IntakeError("Expected an execution recovery journal")
    with tempfile.TemporaryDirectory(prefix="doctor-recovery-") as temporary:
        result = remove_owned(docker_factory(Path(temporary), socket), journal)
    journal.update(state="recovered", cleanup=result)
    _record(journal_path, journal)
    return result
