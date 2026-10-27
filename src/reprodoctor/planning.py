"""Review-only execution contracts. This module never invokes a runtime or a shell."""

from __future__ import annotations

import hashlib
import json
import re
import shlex
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path, PurePosixPath

from . import __version__
from .extraction import encode_candidates, extract_readme
from .intake import IntakeError, canonical
from .snapshot import load_snapshot

MAX_JSON = 8 * 1024 * 1024
ENVIRONMENT = {
    "PATH": "/usr/local/bin:/usr/bin:/bin",
    "HOME": "/tmp",
    "PYTHONDONTWRITEBYTECODE": "1",
    "PYTHONNOUSERSITE": "1",
    "PYTHONPATH": "/workspace/.doctor-packages",
    "PIP_CONFIG_FILE": "/dev/null",
    "PIP_NO_INDEX": "1",
    "PIP_DISABLE_PIP_VERSION_CHECK": "1",
    "PIP_NO_INPUT": "1",
}


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def _pairs(pairs: list[tuple]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _nonfinite(_: str) -> None:
    raise ValueError("Nonfinite JSON number")


def read_document(path: Path) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_JSON:
        raise IntakeError("Review document must be a bounded regular JSON file")
    try:
        with path.open("rb") as stream:
            data = stream.read(MAX_JSON + 1)
        if len(data) > MAX_JSON:
            raise ValueError()
        document = json.loads(
            data,
            object_pairs_hook=_pairs,
            parse_constant=_nonfinite,
        )
        if not isinstance(document, dict):
            raise ValueError()
        canonical(document)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise IntakeError(
            "Invalid review JSON (including duplicate keys or excessive nesting)"
        ) from exc
    return document


def planner_identity() -> dict:
    root = Path(__file__).parent
    return {
        "tool_version": __version__,
        "contract_version": 1,
        "code_digest": digest(
            {
                name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                for name in (
                    "planning.py",
                    "extraction.py",
                    "snapshot.py",
                    "intake.py",
                    "cli.py",
                    "__init__.py",
                    "execution.py",
                    "processes.py",
                    "container_scripts.py",
                )
            }
        ),
        "markdown_it_version": version("markdown-it-py"),
        "mdurl_version": version("mdurl"),
    }


def wheel_inventory(root: Path | None) -> dict:
    files = []
    total = 0
    if root is not None:
        if root.is_symlink() or not root.is_dir():
            raise IntakeError("Wheelhouse must be a directory without symlinks")
        entries = []
        for count, path in enumerate(root.iterdir()):
            if count >= 100:
                raise IntakeError("Wheelhouse supports at most 100 entries")
            entries.append(path)
        for path in sorted(entries):
            if (
                path.is_symlink()
                or not path.is_file()
                or not re.fullmatch(r"[A-Za-z0-9_+.-]+\.whl", path.name)
            ):
                raise IntakeError(
                    "Wheelhouse supports at most 100 regular .whl files, no other entries"
                )
            size = path.stat().st_size
            total += size
            if size > 32 * 1024 * 1024 or total > 128 * 1024 * 1024:
                raise IntakeError("Wheelhouse exceeds its file or total byte budget")
            hasher = hashlib.sha256()
            read = 0
            with path.open("rb") as stream:
                while chunk := stream.read(1024 * 1024):
                    read += len(chunk)
                    if read > size:
                        raise IntakeError("Wheelhouse changed while being read")
                    hasher.update(chunk)
            if read != size:
                raise IntakeError("Wheelhouse changed while being read")
            files.append({"name": path.name, "size": size, "sha256": hasher.hexdigest()})
    return {
        "files": files,
        "content_digest": digest(files),
        "total_bytes": total,
        "container_directory": "/wheels",
        "validation": "hashes_only_not_wheel_validity",
    }


def container_settings(image: str | None, platform: str) -> dict:
    if image is not None and (
        not isinstance(image, str)
        or not re.fullmatch(r"[a-z0-9][a-z0-9._:/-]{0,180}@sha256:[0-9a-f]{64}", image)
    ):
        raise IntakeError(
            "Image must be a digest-pinned reference; omit it to create a blocked draft"
        )
    if platform not in ("linux/amd64", "linux/arm64"):
        raise IntakeError("Only linux/amd64 and linux/arm64 are supported")
    return {
        "image": image,
        "platform": platform,
        "expected_python_series": "3.12",
        "network": "none",
        "ports": [],
        "host_mounts": [],
        "privileged": False,
        "user": "65532:65532",
        "cap_drop": ["ALL"],
        "no_new_privileges": True,
        "seccomp": "runtime_default_required",
        "root_filesystem": "read_only",
        "entrypoint": "overridden_no_image_startup_command",
        "healthcheck": "disabled",
        "runtime_log_driver": "none",
        "runtime_namespaces": {"ipc": "private", "cgroup": "private", "pid": "private"},
        "runtime_support": "experimental_local_Docker_Linux_cgroup_v2_builtin_seccomp",
        "environment": ENVIRONMENT.copy(),
        "inherit_host_environment": False,
        "image_environment": "must_clear_before_project_steps",
        "source_transfer": "copy_only_verified_snapshot_no_git_metadata",
        "source_copy_permissions": "user_writable_0644_or_0755_matching_tracked_executable_bit",
        "project_umask": "0022",
        "artifact_transfer": "copy_only_verified_wheels_no_host_mounts",
        "writable_tmpfs": {
            "/workspace": 256 * 1024 * 1024,
            "/tmp": 64 * 1024 * 1024,
            "/wheels": 128 * 1024 * 1024,
        },
        "shared_memory_bytes": 16 * 1024 * 1024,
        "limits": {
            "cpus": 1,
            "memory_bytes": 1024 * 1024 * 1024,
            "extra_swap_bytes": 0,
            "pids": 128,
            "step_seconds": 120,
            "run_seconds": 600,
            "log_bytes_per_stream_per_step": 1024 * 1024,
            "run_log_bytes": 4 * 1024 * 1024,
            "core_bytes": 0,
            "open_files": 256,
        },
        "cleanup": "remove_container_and_temporary_data_on_exit_or_reconcile_after_interruption",
        "preflight_required": [
            "verify_local_image_digest_and_platform",
            "verify_CPython_3.12",
            "reject_image_declared_volumes",
            "verify_all_resource_controls",
            "clear_image_entrypoint_and_environment",
            "verify_no_sensitive_mounts",
        ],
    }


def _relative(name: str, cwd: str) -> str:
    if not name or name.startswith(("/", "~")) or "\\" in name:
        raise IntakeError("Expected a repository-relative path")
    parts: list[str] = []
    for part in (PurePosixPath(cwd) / name).parts:
        if part == "..":
            if not parts:
                raise IntakeError("Path escapes the container workspace")
            parts.pop()
        elif part != ".":
            parts.append(part)
    result = "/".join(parts) or "."
    if any(p.startswith(".doctor-") for p in parts):
        raise IntakeError("Path uses a reserved Doctor directory")
    return result


def _compile(command: str, cwd: str, environment: dict, artifacts: dict) -> dict:
    if len(command) > 16 * 1024 or re.search(r"[\x00-\x1f\x7f$`;&|<>\\]", command):
        raise IntakeError("Command needs unsupported shell syntax, expansion or control characters")
    try:
        words = shlex.split(command, comments=True)
    except ValueError as exc:
        raise IntakeError("Command has unbalanced quotes") from exc
    if not words:
        raise IntakeError("Command is empty")
    first = words[0]
    result = {
        "kind": "process",
        "argv": [],
        "cwd": cwd,
        "environment": environment.copy(),
        "transformations": [],
        "network_assessment": "Program network requirements are unknown; network is denied.",
        "cwd_after": cwd,
        "environment_after": environment.copy(),
    }
    if words != shlex.split(command, comments=False):
        result["transformations"].append(
            "Remove unquoted shell comments during literal argv parsing."
        )
    if first == "cd" and len(words) == 2:
        result.update(kind="change_directory", cwd_after=_relative(words[1], cwd))
        result["network_assessment"] = "No network operation is modeled for this state change."
    elif first == "export" or (len(words) == 1 and "=" in first):
        assignment = words[1] if first == "export" and len(words) == 2 else first
        if first == "export" and len(words) != 2:
            raise IntakeError("Only one literal export assignment is supported")
        match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)=(.*)", assignment)
        if (
            not match
            or match[1] in ENVIRONMENT
            or match[1].startswith(("LD_", "DYLD_", "PYTHON", "PIP_"))
        ):
            raise IntakeError(
                "Assignment is invalid or changes a reserved runtime environment name"
            )
        if len(match[2]) > 4096:
            raise IntakeError("Environment value exceeds its review budget")
        result.update(kind="set_environment")
        result["environment_after"][match[1]] = match[2]
        result["network_assessment"] = "No network operation is modeled for this state change."
    else:
        python = first in {"python", "python3", "python3.12"}
        pip_args = (
            words[2:]
            if first in {"pip", "pip3"} and words[1:2] == ["install"]
            else (words[4:] if python and words[1:4] == ["-m", "pip", "install"] else None)
        )
        if pip_args is not None:
            _validate_pip(pip_args, cwd)
            if not artifacts["files"]:
                raise IntakeError(
                    "Install steps require a reviewed nonempty offline wheelhouse in this MVP"
                )
            result["argv"] = [
                "python",
                "-m",
                "pip",
                "--isolated",
                "--disable-pip-version-check",
                "--no-input",
                "install",
                "--no-index",
                "--find-links=/wheels",
                "--no-cache-dir",
                "--no-build-isolation",
                "--target=/workspace/.doctor-packages",
                *pip_args,
            ]
            result["transformations"] += [
                "Use the container Python pip, disable index/cache/input and build isolation, "
                "use only offline wheels and install into /workspace/.doctor-packages. "
                "Build dependencies must already exist via the image or earlier explicit steps."
            ]
            result["network_assessment"] = (
                "Documented installation may need dependency/build downloads. This plan instead "
                "requires reviewed offline artifacts; no network access is approved."
            )
        elif first == "pytest":
            result["argv"] = ["python", "-m", "pytest", *words[1:]]
            result["transformations"].append("Use pytest through the container Python interpreter.")
        elif (
            python
            and len(words) >= 3
            and words[1] == "-m"
            and re.fullmatch(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*", words[2])
            and words[2] not in {"pip", "venv", "ensurepip"}
        ):
            result["argv"] = ["python", *words[1:]]
        elif python and len(words) >= 2 and words[1].endswith(".py"):
            _relative(words[1], cwd)
            result["argv"] = ["python", *words[1:]]
        else:
            raise IntakeError(
                "Command is outside the supported direct Python/pytest/install/state subset"
            )
        if python and first != "python":
            result["transformations"].append(
                "Normalize the executable to the pinned container Python."
            )
    return result


def _validate_pip(args: list[str], cwd: str) -> None:
    if not args:
        raise IntakeError("Install command has no targets")
    index = 0
    while index < len(args):
        value = args[index]
        if value in {"-r", "--requirement", "-c", "--constraint", "-e", "--editable"}:
            index += 1
            if index == len(args):
                raise IntakeError("Install option has no operand")
            _relative(args[index], cwd)
        elif value.startswith("-"):
            raise IntakeError("Install options outside -r/-c/-e need a replacement command")
        elif ":" in value or "@" in value:
            raise IntakeError(
                "Direct dependency URLs are not supported in reviewed install targets"
            )
        elif value.startswith((".", "/")):
            _relative(value, cwd)
        elif not re.fullmatch(r"[A-Za-z0-9_.+\[\],=!-]+", value):
            raise IntakeError("Dependency target is outside the literal offline subset")
        index += 1


def _decisions(value: dict | None, ids: set[str]) -> dict:
    if value is None:
        return {}
    if not isinstance(value, dict) or set(value) - ids:
        raise IntakeError("Review decisions contain unknown instruction IDs")
    for decision in value.values():
        if not isinstance(decision, dict) or set(decision) not in (
            {"action", "reason"},
            {"action", "reason", "command"},
        ):
            raise IntakeError(
                "A review decision needs action/reason, plus command only for replace"
            )
        action = decision["action"]
        if not isinstance(action, str) or action not in {"accept", "exclude", "replace"}:
            raise IntakeError("Review action must be accept, exclude or replace")
        reason = decision["reason"]
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 1024:
            raise IntakeError("A nonempty review reason of at most 1024 characters is required")
        if (action == "replace") != ("command" in decision):
            raise IntakeError("Only a replace decision supplies a command")
        if "command" in decision and not isinstance(decision["command"], str):
            raise IntakeError("Replacement command must be text")
    return value


def build_plan(
    snapshot: Path,
    *,
    image: str | None = None,
    platform: str = "linux/amd64",
    wheelhouse: Path | None = None,
    decisions: dict | None = None,
) -> dict:
    manifest, contents = load_snapshot(snapshot)
    if any(part.startswith(".doctor-") for path in contents for part in PurePosixPath(path).parts):
        raise IntakeError("Snapshot uses a reserved Doctor directory")
    extraction = extract_readme(contents.get("README.md", b""))
    instructions = extraction["instructions"]
    if len(instructions) > 200:
        raise IntakeError("Execution plans support at most 200 instruction records")
    reviewed = _decisions(decisions, {i["id"] for i in instructions})
    container = container_settings(image, platform)
    artifacts = wheel_inventory(wheelhouse)
    blockers = [] if image else ["A digest-pinned container image is required before approval."]
    cwd, environment = ".", ENVIRONMENT.copy()
    known = True
    processes = 0
    steps = []
    for instruction in instructions:
        choice = reviewed.get(instruction["id"])
        command = (
            choice.get("command", instruction["candidate_text"])
            if choice
            else instruction["candidate_text"]
        )
        step = {
            "instruction": instruction,
            "decision": choice or {"action": "include", "reason": "Pending overall human approval"},
            "reviewed_command": command,
            "effective": None,
            "blocker": None,
        }
        if choice and choice["action"] == "exclude":
            step["disposition"] = "excluded_by_reviewer"
        else:
            step["disposition"] = "included"
            try:
                if instruction["ambiguity_reasons"] and choice is None:
                    raise IntakeError(
                        "Extraction ambiguity needs an explicit accept/replace/exclude decision"
                    )
                if not known:
                    raise IntakeError(
                        "A preceding unresolved step makes working directory/environment unknown"
                    )
                effective = _compile(command, cwd, environment, artifacts)
                step["effective"] = effective
                cwd, environment = effective["cwd_after"], effective["environment_after"].copy()
                processes += effective["kind"] == "process"
            except IntakeError as exc:
                step["blocker"] = str(exc)
                blockers.append(f"{instruction['id']}: {exc}")
                known = False
        steps.append(step)
    if not processes:
        blockers.append("No executable process step is included.")
    payload = {
        "planner": planner_identity(),
        "repository": {"commit": manifest["commit"], "content_digest": manifest["content_digest"]},
        "extraction_digest": digest(extraction),
        "container": container,
        "artifacts": artifacts,
        "decisions": reviewed,
        "steps": steps,
        "blockers": blockers,
        "state": "blocked" if blockers else "needs_approval",
        "executor_available": True,
        "execution_mode": "experimental_live_validation_pending",
        "limitations": [
            "Network needs of arbitrary program/build code cannot be inferred statically.",
            "Image existence, digest/platform, Python and runtime controls are not verified here.",
            "Approval records are local audit data, not identity proof or blanket permission.",
            "Containers reduce exposure but do not make arbitrary code completely safe.",
            "Experimental execution needs opt-in and runtime preflight; live tests are pending.",
        ],
    }
    plan = {
        "schema_version": 1,
        "kind": "execution_plan",
        "plan_digest": digest(payload),
        "payload": payload,
    }
    encode_candidates(plan)
    return plan


def validate_plan(plan: dict, snapshot: Path, *, wheelhouse: Path | None = None) -> dict:
    if set(plan) != {"schema_version", "kind", "plan_digest", "payload"} or (
        type(plan.get("schema_version")) is not int
        or plan["schema_version"] != 1
        or plan.get("kind") != "execution_plan"
        or not isinstance(plan.get("payload"), dict)
    ):
        raise IntakeError("Unsupported execution-plan schema")
    payload = plan["payload"]
    if digest(payload) != plan.get("plan_digest"):
        raise IntakeError("Plan digest does not match; rebuild and review the plan")
    container = payload.get("container")
    if not isinstance(container, dict) or not isinstance(payload.get("decisions"), dict):
        raise IntakeError("Invalid plan inputs")
    rebuilt = build_plan(
        snapshot,
        image=container.get("image"),
        platform=container.get("platform"),
        wheelhouse=wheelhouse,
        decisions=payload["decisions"],
    )
    if canonical(rebuilt) != canonical(plan):
        raise IntakeError(
            "Source, artifacts, planner or derived settings changed; rebuild and review"
        )
    return plan


def approval_record(plan: dict, confirmation: str) -> dict:
    """The CLI supplies confirmation only after displaying a freshly validated plan."""
    if plan["payload"]["blockers"]:
        raise IntakeError("Blocked plans cannot be approved")
    if confirmation != plan["plan_digest"]:
        raise IntakeError("Approval digest was not confirmed exactly; no approval was written")
    return {
        "schema_version": 1,
        "kind": "execution_approval",
        "method": "interactive_full_digest",
        "plan_digest": plan["plan_digest"],
        "repository": plan["payload"]["repository"],
        "approved_at": datetime.now(timezone.utc).isoformat(),
        "tool_version": __version__,
    }


def validate_approval(record: dict, plan: dict) -> None:
    expected_keys = {
        "schema_version",
        "kind",
        "method",
        "plan_digest",
        "repository",
        "approved_at",
        "tool_version",
    }
    if (
        set(record) != expected_keys
        or type(record.get("schema_version")) is not int
        or (
            record["schema_version"] != 1
            or record.get("kind") != "execution_approval"
            or record.get("method") != "interactive_full_digest"
            or record.get("plan_digest") != plan["plan_digest"]
            or record.get("repository") != plan["payload"]["repository"]
            or record.get("tool_version") != __version__
            or plan["payload"]["blockers"]
        )
    ):
        raise IntakeError("Approval does not match this unblocked plan and snapshot")
    try:
        stamp = datetime.fromisoformat(record["approved_at"])
        if stamp.tzinfo is None:
            raise ValueError()
    except (TypeError, ValueError) as exc:
        raise IntakeError("Approval timestamp is invalid") from exc


def dry_run(
    plan: dict, snapshot: Path, *, wheelhouse: Path | None = None, approval: dict | None = None
) -> dict:
    validate_plan(plan, snapshot, wheelhouse=wheelhouse)
    if approval is not None:
        validate_approval(approval, plan)
    return {
        "kind": "execution_dry_run",
        "plan_digest": plan["plan_digest"],
        "plan_state": plan["payload"]["state"],
        "approval_matches": approval is not None,
        "execution_status": "not_run",
        "executor_available": True,
        "execution_mode": "experimental_live_validation_pending",
        "runtime_preflight": "not_performed",
        "plan": plan,
        "side_effects": "no container, image pull, install, project command or approval write",
    }
