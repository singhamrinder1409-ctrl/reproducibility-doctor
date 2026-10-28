"""Explicit live experiment: signal only owned Doctor children, recover exact journals.

Requires an existing human-approved wait-fixture plan. Never creates an approval,
uses a host shell, prunes Docker resources or runs target source on the host.
"""

import argparse
import json
import signal
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

from reprodoctor.execution import (
    LABEL,
    PLAN_LABEL,
    Docker,
    RuntimeFailure,
    _record,
    create_arguments,
    recover,
    remove_owned,
    verify_container,
    verify_image,
)
from reprodoctor.planning import read_document, validate_approval, validate_plan


def process_identity(pid):
    result = subprocess.run(
        ["/bin/ps", "-p", str(pid), "-o", "lstart=", "-o", "comm="],
        capture_output=True,
        text=True,
        timeout=5,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def wait_started(process, report, docker, plan):
    journal = report.with_name(report.name + ".run.json")
    deadline = time.monotonic() + 30
    while process.poll() is None and time.monotonic() < deadline:
        if journal.exists():
            record = read_document(journal)
            if record.get("state") == "running":
                assert record["plan_digest"] == plan["plan_digest"]
                state = docker.document(
                    ["container", "inspect", record["container_name"], "--format", "{{json .}}"],
                    seconds=5,
                )
                assert state["Config"]["Labels"][LABEL] == record["run_id"]
                assert state["Config"]["Labels"][PLAN_LABEL] == plan["plan_digest"]
                probe = docker.document(
                    [
                        "container",
                        "exec",
                        record["container_name"],
                        "/usr/local/bin/python",
                        "-I",
                        "-S",
                        "-c",
                        "import json;from pathlib import Path;"
                        "print(json.dumps({'ready':Path('/workspace/wait-started').is_file()}))",
                    ],
                    seconds=5,
                )
                if probe["ready"]:
                    return record
        time.sleep(0.05)
    raise RuntimeFailure("Owned wait fixture did not reach its start marker")


def validate(args):
    if not args.execute_approved:
        raise ValueError("Explicit --execute-approved is required")
    if sys.flags.optimize:
        raise ValueError("Run validation harnesses without Python -O")
    plan = validate_plan(read_document(args.plan), args.snapshot)
    validate_approval(read_document(args.approval), plan)
    assert plan["payload"]["steps"][0]["effective"]["argv"] == ["python", "wait.py"]
    for source in (args.snapshot,):
        if args.output.resolve().is_relative_to(source.resolve()):
            raise ValueError("Output must be outside inputs")
    args.output.mkdir(mode=0o700)
    rows = []
    run_id = uuid.uuid4().hex
    sentinel = {
        "schema_version": 1,
        "kind": "execution_journal",
        "run_id": run_id,
        "container_name": "reprodoctor-" + run_id,
        "plan_digest": plan["plan_digest"],
        "state": "owned_infrastructure_sentinel",
    }
    sentinel_path = args.output / "sentinel.run.json"
    _record(sentinel_path, sentinel, new=True)
    with tempfile.TemporaryDirectory(prefix="doctor-signal-validation-") as temporary:
        docker = Docker(Path(temporary), args.docker_socket)
        image = verify_image(
            docker.document(
                [
                    "image",
                    "inspect",
                    plan["payload"]["container"]["image"],
                    "--format",
                    "{{json .}}",
                ]
            ),
            plan["payload"]["container"],
        )
        touched = False
        try:
            touched = True
            docker.command(create_arguments(sentinel["container_name"], run_id, plan, image))
            verify_container(
                docker.document(
                    ["container", "inspect", sentinel["container_name"], "--format", "{{json .}}"]
                ),
                plan,
                run_id,
                image,
            )
            docker.command(["container", "start", sentinel["container_name"]])
            for label, signum in (
                ("sigint", signal.SIGINT),
                ("sigterm", signal.SIGTERM),
                ("sigkill-recovery", signal.SIGKILL),
            ):
                report = args.output / (label + ".json")
                command = [
                    sys.executable,
                    "-I",
                    "-m",
                    "reprodoctor",
                    "run",
                    str(args.plan),
                    "--snapshot",
                    str(args.snapshot),
                    "--approval",
                    str(args.approval),
                    "--docker-socket",
                    args.docker_socket,
                    "--experimental-execution",
                    "--output",
                    str(report),
                ]
                process = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    start_new_session=True,
                )
                owner = None
                row = {"case": label}
                try:
                    owner = wait_started(process, report, docker, plan)
                    children = subprocess.run(
                        ["/usr/bin/pgrep", "-P", str(process.pid)],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    helpers = {
                        int(pid): process_identity(int(pid)) for pid in children.stdout.split()
                    }
                    process.send_signal(signum)
                    stdout, stderr = process.communicate(timeout=50)
                    row.update(host_return_code=process.returncode, target_started=True)
                    if signum == signal.SIGKILL:
                        assert process.returncode == -signal.SIGKILL and not report.exists()
                        state = docker.document(
                            [
                                "container",
                                "inspect",
                                owner["container_name"],
                                "--format",
                                "{{json .}}",
                            ]
                        )
                        assert state["State"]["Running"] is True
                        row["container_retained_after_host_kill"] = True
                        row["recovery"] = recover(
                            report.with_name(report.name + ".run.json"), socket=args.docker_socket
                        )
                        assert row["recovery"]["status"] == "removed"
                    else:
                        assert process.returncode == 2, (stdout, stderr)
                        result = read_document(report)
                        assert result["execution_status"] == "cancelled"
                        assert result["cleanup"]["status"] == "removed"
                        assert result["steps"][0]["status"] == "cancelled"
                        assert result["steps_not_reached"] == ["instruction-0002"]
                        row["cleanup"] = result["cleanup"]
                        row["partial_output_capture"] = result["steps"][0].get(
                            "output_capture_status"
                        )
                    # Inspect only known direct children of our own process, never global args.
                    deadline = time.monotonic() + 5
                    while time.monotonic() < deadline and any(
                        identity and process_identity(pid) == identity
                        for pid, identity in helpers.items()
                    ):
                        time.sleep(0.1)
                    remaining = [
                        pid
                        for pid, identity in helpers.items()
                        if identity and process_identity(pid) == identity
                    ]
                    row["host_helpers_remaining"] = len(remaining)
                    # A surviving owned helper is an explicit failure, not a claimed cleanup pass.
                    assert not remaining, "An owned Docker helper remained after recovery"
                    state = docker.document(
                        [
                            "container",
                            "inspect",
                            sentinel["container_name"],
                            "--format",
                            "{{json .}}",
                        ]
                    )
                    assert state["State"]["Running"] is True
                    assert (
                        docker.document(
                            ["image", "inspect", image["id"], "--format", "{{json .}}"]
                        )["Id"]
                        == image["id"]
                    )
                    row.update(other_owned_container_preserved=True, image_preserved=True)
                    rows.append(row)
                    _record(args.output / "progress.json", {"cases": rows})
                    print(label + " verified", flush=True)
                finally:
                    if process.poll() is None:
                        process.terminate()
                        try:
                            process.communicate(timeout=50)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.communicate(timeout=10)
                    if owner:
                        row["final_target_absence"] = remove_owned(docker, owner)
        finally:
            if touched:
                sentinel["cleanup"] = remove_owned(docker, sentinel)
                sentinel["state"] = "finished"
                _record(sentinel_path, sentinel)
    result = {
        "schema_version": 1,
        "kind": "approved_live_signal_validation",
        "plan_digest": plan["plan_digest"],
        "cases": rows,
        "sentinel_cleanup": sentinel["cleanup"],
        "limitations": [
            "Only harness-owned processes and exact labeled containers were targeted.",
            "SIGKILL itself cannot run cleanup; explicit journal recovery was necessary.",
            "This does not guarantee cleanup during daemon failure or host loss.",
        ],
    }
    _record(args.output / "summary.json", result, new=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("plan", "snapshot", "approval", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--docker-socket", required=True)
    parser.add_argument("--execute-approved", action="store_true")
    print(json.dumps(validate(parser.parse_args()), indent=2))


if __name__ == "__main__":
    main()
