"""Contract tests use a SIMULATED daemon; they are not containment evidence."""

import ast
import copy
import io
import json
import os
import sys
import tarfile

import pytest

from reprodoctor import container_scripts
from reprodoctor.execution import (
    LABEL,
    PLAN_LABEL,
    Docker,
    RuntimeFailure,
    create_arguments,
    execute_plan,
    recover,
    verify_container,
    verify_image,
    verify_probe,
    verify_server,
)
from reprodoctor.intake import IntakeError, intake
from reprodoctor.planning import approval_record, build_plan, digest
from reprodoctor.processes import Capture, bounded_process

IMAGE = "python:3.12-slim@sha256:" + "1" * 64
IMAGE_ID = "sha256:" + "2" * 64


def image_metadata():
    return {
        "Id": IMAGE_ID,
        "RepoDigests": [IMAGE],
        "Os": "linux",
        "Architecture": "amd64",
        "Config": {"Env": ["PATH=/image/bin", "IMAGE_SECRET=not-in-project-env"], "Volumes": None},
    }


def kernel_metadata(settings):
    paths = {path: {"read_only": True} for path in ("/", "/sys", "/sys/fs/cgroup", "/proc/sys")}
    for path, size in {
        **settings["writable_tmpfs"],
        "/dev/shm": settings["shared_memory_bytes"],
    }.items():
        paths[path] = {"read_only": False, "bytes": size, "mount": {"type": "tmpfs"}}
    return {
        "implementation": "cpython",
        "python": [3, 12, 9],
        "version": "fixture CPython",
        "executable": "/usr/local/bin/python",
        "machine": "x86_64",
        "uid": 65532,
        "gid": 65532,
        "status": {"NoNewPrivs": "1", "Seccomp": "2", "CapEff": "0", "CapPrm": "0", "CapBnd": "0"},
        "rlimits": {"core": [0, 0], "nofile": [256, 256]},
        "cgroups": {
            "memory.max": str(1024**3),
            "memory.swap.max": "0",
            "pids.max": "128",
            "cpu.max": "100000 100000",
        },
        "network_interfaces": ["lo"],
        "managed_files_writable": [],
        "paths": paths,
    }


def inspected_container(plan, run_id):
    settings = plan["payload"]["container"]
    env = {"PATH": "", "IMAGE_SECRET": ""}
    env.update(settings["environment"])
    return {
        "Image": IMAGE_ID,
        "Mounts": [],
        "Config": {
            "User": "65532:65532",
            "Healthcheck": {"Test": ["NONE"]},
            "Entrypoint": ["/usr/local/bin/python"],
            "Env": [k + "=" + v for k, v in env.items()],
            "Labels": {LABEL: run_id, PLAN_LABEL: plan["plan_digest"]},
        },
        "HostConfig": {
            "NetworkMode": "none",
            "IpcMode": "private",
            "CgroupnsMode": "private",
            "ReadonlyRootfs": True,
            "Privileged": False,
            "NanoCpus": 1_000_000_000,
            "Memory": 1024**3,
            "MemorySwap": 1024**3,
            "PidsLimit": 128,
            "ShmSize": 16 * 1024**2,
            "CapDrop": ["ALL"],
            "Init": True,
            "SecurityOpt": ["no-new-privileges=true"],
            "LogConfig": {"Type": "none"},
            "RestartPolicy": {"Name": "no"},
            "Ulimits": [
                {"Name": "core", "Soft": 0, "Hard": 0},
                {"Name": "nofile", "Soft": 256, "Hard": 256},
            ],
            "Tmpfs": {
                p: f"rw,nosuid,nodev,size={size},uid=65532,gid=65532,mode=0700"
                for p, size in settings["writable_tmpfs"].items()
            },
        },
    }


def command_result(code=0, *, timeout=False, cap=1024, text=b"fixture output\n"):
    out, err = Capture(cap), Capture(cap)
    out.feed(text)
    return {
        "exit_code": code,
        "timed_out": timeout,
        "seconds": 0.001,
        "stdout": out.record(),
        "stderr": err.record(),
    }


class FakeDocker:
    """Only models control flow and metadata. Never starts any process."""

    def __init__(self, plan, *, failure=None, process_code=0, timeout=False, interrupt=False):
        self.plan, self.failure = plan, failure
        self.process_code, self.timeout, self.interrupt = process_code, timeout, interrupt
        self.created = False
        self.calls = []
        self.process_calls = []

    def factory(self, home, socket):
        return self

    def document(self, args, **kwargs):
        self.calls.append(args)
        if args[0] == "info":
            return {
                "OSType": "linux",
                "CgroupVersion": "2",
                "SecurityOptions": ["name=seccomp,profile=builtin"],
                "ServerVersion": "fixture",
            }
        if args[:2] == ["image", "inspect"]:
            return image_metadata()
        if args[:2] == ["container", "inspect"]:
            if args[-1] == "{{json .State}}":
                return {"Running": True, "OOMKilled": False, "ExitCode": 0, "Error": ""}
            return copy.deepcopy(self.inspection)
        if args[-1] == container_scripts.PROBE:
            probe = kernel_metadata(self.plan["payload"]["container"])
            if self.failure == "probe":
                probe["cgroups"]["memory.max"] = "max"
            return probe
        raise AssertionError(args)

    def command(self, args, *, stdin=None, cap=1024, **kwargs):
        self.calls.append(args)
        if args[:2] == ["container", "create"]:
            self.created = True
            self.name = args[args.index("--name") + 1]
            self.inspection = inspected_container(self.plan, self.name.removeprefix("reprodoctor-"))
            if self.failure == "inspect":
                self.inspection["HostConfig"]["NetworkMode"] = "host"
            if self.failure == "create":
                raise RuntimeFailure("simulated partial create error")
        elif args[:2] == ["container", "start"]:
            if self.failure == "start":
                raise RuntimeFailure("simulated start error")
        elif args[-1] == container_scripts.RECEIVE:
            entries = []
            import hashlib

            with tarfile.open(fileobj=stdin, mode="r:") as archive:
                for member in archive:
                    data = archive.extractfile(member).read()
                    entries.append(
                        {
                            "path": member.name,
                            "size": len(data),
                            "mode": member.mode,
                            "sha256": hashlib.sha256(data).hexdigest(),
                        }
                    )
            expected = {
                "digest": digest(sorted(entries, key=lambda e: e["path"])),
                "files": len(entries),
                "bytes": sum(e["size"] for e in entries),
            }
            if self.failure == "transfer":
                expected["digest"] = "changed"
            return command_result(text=json.dumps(expected).encode())
        elif args[-1] == container_scripts.EXECUTE:
            job = json.loads(stdin.read())
            self.process_calls.append(job)
            if self.interrupt:
                raise KeyboardInterrupt()
            return command_result(self.process_code, timeout=self.timeout, cap=cap)
        elif args[:2] == ["container", "ls"]:
            return command_result(text=(self.name + "\n").encode() if self.created else b"")
        elif args[:2] == ["container", "rm"]:
            if self.failure == "cleanup":
                raise RuntimeFailure("simulated daemon unavailable")
            self.created = False
        return command_result(text=b"")


@pytest.fixture
def execution_inputs(repo, tmp_path):
    snapshot = tmp_path / "snapshot"
    intake(str(repo[0]), snapshot)
    plan = build_plan(snapshot, image=IMAGE)
    # This is an authored-fixture test token, NEVER authority for real execution.
    approval = approval_record(plan, plan["plan_digest"])
    return snapshot, plan, approval


def simulated_run(execution_inputs, tmp_path, **options):
    snapshot, plan, approval = execution_inputs
    fake = FakeDocker(plan, **options)
    report = execute_plan(
        plan,
        approval,
        snapshot,
        tmp_path / "report.json",
        experimental=True,
        docker_factory=fake.factory,
    )
    return report, fake


def test_simulated_success_records_evidence_and_removes_owned_container(execution_inputs, tmp_path):
    report, fake = simulated_run(execution_inputs, tmp_path)
    assert report["execution_status"] == "completed" and report["cleanup"]["status"] == "removed"
    assert report["live_validation"] == "pending" and report["experimental"]
    assert report["preflight"]["transfer"]["files"] == 2
    assert report["steps"][0]["effective"]["argv"] == ["python", "hello.py"]
    assert report["steps"][0]["exit_code"] == 0 and report["steps"][0]["signal"] is None
    assert len(fake.process_calls) == 1 and not fake.created
    assert json.loads((tmp_path / "report.json").read_text()) == report
    journal = json.loads((tmp_path / "report.json.run.json").read_text())
    assert journal["state"] == "finished"
    assert (tmp_path / "report.json").stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("failure", ["create", "start", "inspect", "probe", "transfer"])
def test_failure_before_project_code_always_cleans_up(execution_inputs, tmp_path, failure):
    report, fake = simulated_run(execution_inputs, tmp_path, failure=failure)
    assert report["execution_status"] == "infrastructure_error"
    assert report["cleanup"]["status"] == "removed" and not fake.created
    assert fake.process_calls == []


@pytest.mark.parametrize(
    "code,timeout,status", [(9, False, "failed"), (0, True, "timed_out"), (137, False, "failed")]
)
def test_observed_statuses_are_not_invented_signals(
    execution_inputs, tmp_path, code, timeout, status
):
    report, fake = simulated_run(execution_inputs, tmp_path, process_code=code, timeout=timeout)
    assert report["execution_status"] == status and report["cleanup"]["status"] == "removed"
    assert report["steps"][0]["signal"] is None
    assert report["steps"][0]["exit_code_source"] == "docker_exec_cli"


def test_cancelled_target_path_still_removes_container(execution_inputs, tmp_path):
    report, fake = simulated_run(execution_inputs, tmp_path, interrupt=True)
    assert report["execution_status"] == "cancelled"
    assert report["cleanup"]["status"] == "removed" and not fake.created


def test_cleanup_failure_is_visible_and_journal_supports_recovery(execution_inputs, tmp_path):
    report, fake = simulated_run(execution_inputs, tmp_path, failure="cleanup")
    assert report["cleanup"]["status"] == "failed" and fake.created
    path = tmp_path / "report.json.run.json"
    assert json.loads(path.read_text())["state"] == "cleanup_failed"
    fake.failure = None
    assert recover(path, docker_factory=fake.factory)["status"] == "removed"
    assert json.loads(path.read_text())["state"] == "recovered"


def test_recovery_refuses_another_containers_labels(execution_inputs, tmp_path):
    report, fake = simulated_run(execution_inputs, tmp_path, failure="cleanup")
    fake.failure = None
    fake.inspection["Config"]["Labels"][LABEL] = "another-run"
    with pytest.raises(RuntimeFailure, match="labels"):
        recover(tmp_path / "report.json.run.json", docker_factory=fake.factory)
    assert fake.created


def test_opt_in_and_approval_gate_before_any_backend_calls(execution_inputs, tmp_path):
    snapshot, plan, approval = execution_inputs

    def forbidden(*args):
        pytest.fail("Backend reached without matching approval")

    with pytest.raises(IntakeError, match="opt-in"):
        execute_plan(plan, approval, snapshot, tmp_path / "report.json", docker_factory=forbidden)
    approval["plan_digest"] = "changed"
    with pytest.raises(IntakeError):
        execute_plan(
            plan,
            approval,
            snapshot,
            tmp_path / "report.json",
            experimental=True,
            docker_factory=forbidden,
        )
    assert not (tmp_path / "report.json.run.json").exists()


def test_missing_docker_is_honest_infrastructure_result(execution_inputs, tmp_path, monkeypatch):
    monkeypatch.setattr("reprodoctor.execution.shutil.which", lambda *a, **kw: None)
    snapshot, plan, approval = execution_inputs
    report = execute_plan(plan, approval, snapshot, tmp_path / "report.json", experimental=True)
    assert report["execution_status"] == "infrastructure_error"
    assert report["steps"] == [] and report["cleanup"]["status"] == "not_needed"
    assert "not installed" in report["error"]


@pytest.mark.parametrize(
    "changes", [{"OSType": "windows"}, {"CgroupVersion": "1"}, {"SecurityOptions": ["unconfined"]}]
)
def test_server_controls_must_be_available(changes):
    info = {
        "OSType": "linux",
        "CgroupVersion": "2",
        "SecurityOptions": ["name=seccomp,profile=builtin"],
    }
    info.update(changes)
    with pytest.raises(RuntimeFailure):
        verify_server(info)


@pytest.mark.parametrize(
    "field,value",
    [
        ("NetworkMode", "host"),
        ("ReadonlyRootfs", False),
        ("MemorySwap", -1),
        ("PidsLimit", 0),
        ("Binds", ["/home:/host"]),
        ("Devices", ["/dev/sda"]),
        ("SecurityOpt", ["seccomp=unconfined"]),
    ],
)
def test_inspect_rejects_weaker_configuration(execution_inputs, field, value):
    _, plan, _ = execution_inputs
    image = verify_image(image_metadata(), plan["payload"]["container"])
    metadata = inspected_container(plan, "a" * 32)
    metadata["HostConfig"][field] = value
    with pytest.raises(RuntimeFailure):
        verify_container(metadata, plan, "a" * 32, image)


@pytest.mark.parametrize(
    "where,key,value",
    [
        ("status", "Seccomp", "0"),
        ("status", "CapEff", "1"),
        ("cgroups", "cpu.max", "max 100000"),
        ("cgroups", "memory.max", "max"),
        ("cgroups", "memory.swap.max", "1024"),
        ("cgroups", "pids.max", "max"),
    ],
)
def test_kernel_probe_rejects_missing_enforcement(execution_inputs, where, key, value):
    _, plan, _ = execution_inputs
    settings = plan["payload"]["container"]
    probe = kernel_metadata(settings)
    probe[where][key] = value
    with pytest.raises(RuntimeFailure):
        verify_probe(probe, settings)


def test_mount_network_and_image_volume_escape_checks(execution_inputs):
    _, plan, _ = execution_inputs
    settings = plan["payload"]["container"]
    for path in ("/", "/sys/fs/cgroup"):
        probe = kernel_metadata(settings)
        probe["paths"][path]["read_only"] = False
        with pytest.raises(RuntimeFailure):
            verify_probe(probe, settings)
    probe = kernel_metadata(settings)
    probe["network_interfaces"] = ["eth0", "lo"]
    with pytest.raises(RuntimeFailure):
        verify_probe(probe, settings)
    image = image_metadata()
    image["Config"]["Volumes"] = {"/unbounded": {}}
    with pytest.raises(RuntimeFailure):
        verify_image(image, settings)


def test_create_never_pulls_mounts_or_inherits_host_credentials(
    execution_inputs, tmp_path, monkeypatch
):
    _, plan, _ = execution_inputs
    image = verify_image(image_metadata(), plan["payload"]["container"])
    args = create_arguments("reprodoctor-" + "a" * 32, "a" * 32, plan, image)
    assert "--pull=never" in args and "--log-driver=none" in args and "--no-healthcheck" in args
    assert "--memory-swap=1073741824" in args
    assert not set(args) & {"--mount", "--volume", "--privileged", "--network=host"}
    monkeypatch.setenv("DOCKER_HOST", "tcp://remote.invalid")
    monkeypatch.setenv("HOST_SECRET", "host-only")
    monkeypatch.setattr("reprodoctor.execution.shutil.which", lambda *a, **kw: "/trusted/docker")
    adapter = Docker(tmp_path, "/local/docker.sock")
    assert "HOST_SECRET" not in adapter.environment and "DOCKER_HOST" not in adapter.environment
    assert "unix:///local/docker.sock" in adapter.prefix
    with pytest.raises(RuntimeFailure):
        Docker(tmp_path, "tcp://remote.invalid")


def test_bootstrap_scripts_only_parsed_on_host_not_executed():
    for script in (container_scripts.PROBE, container_scripts.RECEIVE, container_scripts.EXECUTE):
        ast.parse(script)


def test_trusted_host_capture_drains_both_streams_with_bounded_memory(tmp_path):
    # Fixed Doctor infrastructure test code, NEVER extracted repository commands.
    source = (
        "import sys; sys.stdout.buffer.write(b'x'*200000); sys.stderr.buffer.write(b'y'*200000)"
    )
    result = bounded_process(
        [sys.executable, "-I", "-S", "-c", source],
        environment={"PATH": os.defpath},
        cwd=str(tmp_path),
        seconds=5,
        cap=1024,
    )
    assert result["exit_code"] == 0
    assert result["stdout"]["total_bytes"] == result["stderr"]["total_bytes"] == 200000
    assert result["stdout"]["captured_bytes"] == 1024 and result["stderr"]["truncated"]


def test_trusted_host_capture_stdin_and_timeout(tmp_path):
    args = dict(environment={"PATH": os.defpath}, cwd=str(tmp_path), cap=32)
    result = bounded_process(
        [sys.executable, "-I", "-S", "-c", "import sys; print(sys.stdin.read())"],
        stdin=io.BytesIO(b"fixture"),
        seconds=5,
        **args,
    )
    assert result["stdout"]["text"] == "fixture\n"
    result = bounded_process(
        [sys.executable, "-I", "-S", "-c", "import time; time.sleep(10)"], seconds=0.1, **args
    )
    assert result["timed_out"] and result["seconds"] < 3


def test_terminal_controls_are_not_live_terminal_sequences():
    capture = Capture(100)
    capture.feed(b"\x1b[31mred\x00\n")
    assert "\x1b" not in capture.record()["text"] and "\x00" not in capture.record()["text"]


def multi_inputs(repo, tmp_path, body):
    root, git = repo
    (root / "README.md").write_text("```sh\n" + body + "```\n")
    (root / "app").mkdir()
    (root / "app/main.py").write_text("print('fixture; never executed by FakeDocker')\n")
    git("add", ".")
    git("commit", "-m", "authored multi-step controller fixture")
    snapshot = tmp_path / "multi-snapshot"
    intake(str(root), snapshot)
    plan = build_plan(snapshot, image=IMAGE)
    assert not plan["payload"]["blockers"]
    return snapshot, plan, approval_record(plan, plan["plan_digest"])


def test_state_forwarding_and_stop_after_first_failure(repo, tmp_path):
    inputs = multi_inputs(
        repo, tmp_path, "export MODE=fixture\ncd app\npython main.py\npython main.py\n"
    )
    report, fake = simulated_run(inputs, tmp_path, process_code=5)
    assert report["steps"][0]["status"] == "state_updated"
    # The fake's first command is the directory check; failure stops before Python launch.
    assert fake.process_calls[0]["kind"] == "change_directory"
    assert fake.process_calls[0]["environment"]["MODE"] == "fixture"
    assert report["steps_not_reached"] == ["instruction-0003", "instruction-0004"]
    assert report["cleanup"]["status"] == "removed"


def test_aggregate_log_budget_remains_bounded_across_steps(repo, tmp_path):
    snapshot, plan, approval = multi_inputs(repo, tmp_path, "python hello.py\n" * 3)

    class Flood(FakeDocker):
        def command(self, args, **kwargs):
            if args[-1] == container_scripts.EXECUTE:
                cap = kwargs["cap"]
                result = command_result(cap=cap, text=b"x" * (1024 * 1024 + 1))
                capture = Capture(cap)
                capture.feed(b"y" * (1024 * 1024 + 1))
                result["stderr"] = capture.record()
                return result
            return super().command(args, **kwargs)

    fake = Flood(plan)
    report = execute_plan(
        plan,
        approval,
        snapshot,
        tmp_path / "flood.json",
        experimental=True,
        docker_factory=fake.factory,
    )
    captured = sum(
        step[stream]["captured_bytes"]
        for step in report["steps"]
        for stream in ("stdout", "stderr")
    )
    assert captured == plan["payload"]["container"]["limits"]["run_log_bytes"]
    assert report["steps"][-1]["stdout"]["captured_bytes"] == 0
    assert report["steps"][-1]["stderr"]["truncated"]


def test_required_preflight_checks_survive_python_optimization(execution_inputs, tmp_path):
    # Trustworthy host test of Doctor's verifier; no target code is executed here.
    from reprodoctor.processes import bounded_process

    source = (
        "from reprodoctor.execution import verify_probe, RuntimeFailure\n"
        "try: verify_probe({}, {})\n"
        "except RuntimeFailure: print('denied')\n"
        "else: raise SystemExit('unsafe optimization bypass')\n"
    )
    result = bounded_process(
        [sys.executable, "-O", "-c", source],
        environment={"PATH": os.defpath},
        cwd=str(tmp_path),
        seconds=5,
        cap=1024,
    )
    assert result["exit_code"] == 0 and result["stdout"]["text"] == "denied\n"


def test_infrastructure_failures_keep_bounded_exit_and_stderr_evidence(tmp_path, monkeypatch):
    monkeypatch.setattr("reprodoctor.execution.shutil.which", lambda *a, **kw: "/trusted/docker")
    monkeypatch.setattr(
        "reprodoctor.execution.bounded_process",
        lambda *a, **kw: command_result(125, text=b"metadata prefix omitted from record"),
    )
    with pytest.raises(RuntimeFailure) as error:
        Docker(tmp_path, "/local.sock").command(["image", "inspect", IMAGE])
    assert error.value.evidence["exit_code"] == 125
    assert "text" not in error.value.evidence["stdout"]
    assert "stderr" in error.value.evidence
