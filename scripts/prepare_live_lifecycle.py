"""Prepare unapproved timeout/recovery/path/offline-wheel plans; never run targets."""

import argparse
import base64
import csv
import hashlib
import io
import json
import os
import shlex
import zipfile
from pathlib import Path

from evaluate import fixture_repository

from reprodoctor.extraction import encode_candidates
from reprodoctor.intake import intake
from reprodoctor.planning import build_plan

ROOT = Path(__file__).resolve().parents[1]
CASES = ("step-wait", "run-budget", "path-boundary", "offline-wheel")


def authored_wheel(base: Path) -> Path:
    """Write static authored bytes and metadata; never import/build project code."""
    files = {
        "doctor_validation_fixture.py": b'VALUE = "authored offline fixture"\n',
        "doctor_validation_fixture-0.0.0.dist-info/METADATA": (
            b"Metadata-Version: 2.1\nName: doctor-validation-fixture\nVersion: 0.0.0\n"
            b"Summary: Authored offline validation fixture\nLicense: MIT\n\n"
        ),
        "doctor_validation_fixture-0.0.0.dist-info/WHEEL": (
            b"Wheel-Version: 1.0\nGenerator: Reproducibility-Doctor-Fixture\n"
            b"Root-Is-Purelib: true\nTag: py3-none-any\n"
        ),
    }
    rows = []
    for name, data in sorted(files.items()):
        encoded = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
        rows.append((name, "sha256=" + encoded, str(len(data))))
    record_name = "doctor_validation_fixture-0.0.0.dist-info/RECORD"
    rows.append((record_name, "", ""))
    buffer = io.StringIO(newline="")
    csv.writer(buffer, lineterminator="\n").writerows(rows)
    files[record_name] = buffer.getvalue().encode()
    wheelhouse = base / "wheelhouse"
    wheelhouse.mkdir()
    wheel = wheelhouse / "doctor_validation_fixture-0.0.0-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "x") as archive:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(2000, 1, 1, 0, 0, 0))
            info.external_attr = 0o644 << 16
            archive.writestr(info, data)
            source = base / "wheel-source" / name
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_bytes(data)
    return wheelhouse


def prepare(output: Path, *, image: str, platform: str) -> dict:
    if output.resolve().is_relative_to(ROOT):
        raise ValueError("Review artifacts must be outside the source checkout")
    output.mkdir(mode=0o700)
    cases = []
    helper = [
        "#!/bin/zsh",
        "set -eu",
        "unset PYTHONPATH PYTHONHOME",
        'echo "Review FOUR NEW lifecycle plans. This helper only creates approval receipts."',
    ]
    for name in CASES:
        directory = ROOT / "tests/fixtures/live-lifecycle" / name
        files = {}
        for path in sorted(directory.rglob("*")):
            if path.is_symlink():
                raise ValueError("Symlink in authored fixture")
            if path.is_file():
                files[path.relative_to(directory).as_posix()] = path.read_text()
        base = output / name
        base.mkdir()
        fixture_repository(files, base / "source")
        intake(str(base / "source"), base / "snapshot")
        wheelhouse = authored_wheel(base) if name == "offline-wheel" else None
        plan = build_plan(base / "snapshot", image=image, platform=platform, wheelhouse=wheelhouse)
        if plan["payload"]["blockers"]:
            raise ValueError(f"{name} plan blocked: {plan['payload']['blockers']}")
        descriptor = os.open(base / "plan.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as stream:
            stream.write(encode_candidates(plan))
        cases.append(
            {"id": name, "plan_digest": plan["plan_digest"], "wheelhouse": bool(wheelhouse)}
        )
        source_paths = list((base / "source").rglob("*"))
        if wheelhouse:
            source_paths += list((base / "wheel-source").rglob("*"))
        for path in sorted(source_paths):
            if path.is_file() and ".git" not in path.parts:
                helper += [
                    "echo " + shlex.quote("Review source: " + str(path)),
                    "cat -- " + shlex.quote(str(path)),
                ]
        command = [
            str(ROOT / ".venv/bin/python"),
            "-I",
            "-m",
            "reprodoctor",
            "approve",
            str(base / "plan.json"),
            "--snapshot",
            str(base / "snapshot"),
            "--output",
            str(base / "approval.json"),
        ]
        if wheelhouse:
            command += ["--wheelhouse", str(wheelhouse)]
        helper.append(" ".join(shlex.quote(item) for item in command))
    helper += [
        'echo "Tell Codex: lifecycle plans approved. No target commands have run."',
        'read "?Press Enter to close."',
    ]
    path = output / "Review-and-approve-lifecycle.command"
    path.write_text("\n".join(helper) + "\n")
    path.chmod(0o700)
    result = {
        "schema_version": 1,
        "kind": "lifecycle_probe_preparation",
        "execution_status": "not_run",
        "approval_created": False,
        "cases": cases,
    }
    (output / "preparation.json").write_text(json.dumps(result, indent=2) + "\n")
    (output / "REVIEW.md").write_text(
        "# Lifecycle and artifact validation — FOUR NEW plans\n\n"
        "No fixture command has run. The helper displays source/plans and records approval.\n\n"
        "- **step-wait**: wait for the 120-second step deadline; reuse this exact plan for "
        "Ctrl-C, SIGTERM and SIGKILL of its own Doctor process, then targeted journal "
        "recovery, plus preservation of another owned container/image. Never signal other apps.\n"
        "- **run-budget**: six 110-second sleeps; expect the whole-run 600-second deadline to stop "
        "the last step. This takes about TEN MINUTES, mostly idle.\n"
        "- **path-boundary**: run a quoted filename, create a symlink to container /tmp, then "
        "Doctor must reject the workspace escape and skip the later step.\n"
        "- **offline-wheel**: install one tiny authored pure-Python wheel from the reviewed local "
        "wheelhouse, then import its harmless marker module inside the container. No host package "
        "installation/build backend/index. Separate copied-input mutation checks must reject stale "
        "approvals before Docker access.\n\n"
        "Settings remain network=none, no host mounts/credentials, non-root, read-only root, "
        "bounded tmpfs, CPU/RAM/PID/log/time limits and dropped capabilities. Shared-kernel risk "
        "remains; containers do not make arbitrary code completely safe.\n\n"
        + "\n".join(f"- {case['id']}: `{case['plan_digest']}`" for case in cases)
        + "\n"
    )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--image", required=True)
    parser.add_argument("--platform", required=True, choices=["linux/amd64", "linux/arm64"])
    args = parser.parse_args()
    print(encode_candidates(prepare(args.output, image=args.image, platform=args.platform)), end="")


if __name__ == "__main__":
    main()
