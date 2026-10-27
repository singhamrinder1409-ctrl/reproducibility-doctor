"""Prepare three review-only live control probes. Never starts Docker or approves plans."""

import argparse
import hashlib
import json
import os
import shlex
import tempfile
from pathlib import Path

from evaluate import fixture_repository

from reprodoctor.extraction import encode_candidates
from reprodoctor.intake import intake
from reprodoctor.planning import build_plan

ROOT = Path(__file__).resolve().parents[1]


def prepare(output: Path, *, image: str, platform: str) -> dict:
    if output.resolve().is_relative_to(ROOT):
        raise ValueError("Review artifacts must be outside the source checkout")
    output.mkdir(mode=0o700)
    descriptor, sentinel = tempfile.mkstemp(prefix="reprodoctor-host-sentinel-", dir="/tmp")
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(b"Authored host-only sentinel, not a credential.\n")
    sentinel_path = Path(sentinel)
    try:
        cases = []
        helper = [
            "#!/bin/zsh",
            "set -eu",
            "unset PYTHONPATH PYTHONHOME",
            'echo "Review the NEW control probes and full plans. This helper only approves."',
        ]
        for name in ("network", "resources", "logs"):
            directory = ROOT / "tests/fixtures/live-controls" / name
            files = {}
            for path in sorted(directory.rglob("*")):
                if path.is_symlink():
                    raise ValueError("Symlink in authored fixture")
                if path.is_file():
                    files[path.relative_to(directory).as_posix()] = path.read_text()
            if name == "network":
                files["sentinel.json"] = json.dumps({"host_only_path": sentinel}) + "\n"
            base = output / name
            base.mkdir()
            fixture_repository(files, base / "source")
            intake(str(base / "source"), base / "snapshot")
            plan = build_plan(base / "snapshot", image=image, platform=platform)
            if plan["payload"]["blockers"]:
                raise ValueError("Probe plan is blocked; inspect before review")
            descriptor = os.open(base / "plan.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "w") as stream:
                stream.write(encode_candidates(plan))
            cases.append({"id": name, "plan_digest": plan["plan_digest"]})
            for path in sorted((base / "source").rglob("*")):
                if path.is_file() and ".git" not in path.relative_to(base / "source").parts:
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
            helper.append(" ".join(shlex.quote(item) for item in command))
        helper += [
            'echo "Tell Codex: control plans approved. No probe has run."',
            'read "?Press Enter to close."',
        ]
        path = output / "Review-and-approve-controls.command"
        path.write_text("\n".join(helper) + "\n")
        path.chmod(0o700)
        manifest = {
            "schema_version": 1,
            "kind": "control_probe_preparation",
            "execution_status": "not_run",
            "approval_created": False,
            "host_sentinel": str(sentinel_path),
            "host_sentinel_sha256": hashlib.sha256(sentinel_path.read_bytes()).hexdigest(),
            "required_host_environment": {"DOCTOR_HOST_SENTINEL": "synthetic-host-only"},
            "cases": cases,
        }
        (output / "preparation.json").write_text(json.dumps(manifest, indent=2) + "\n")
        (output / "REVIEW.md").write_text(
            "# New live control probes — review before approval\n\n"
            "No target probe has run. The approval helper creates receipts only.\n\n"
            "- **network**: attempt unreachable IPv4/IPv6 destinations; check the dummy host file, "
            "host environment, home paths, Docker socket and host-sharing mounts are absent.\n"
            "- **resources**: deliberate CPU, memory/OOM, PID, descriptor/core and tmpfs stress in "
            "the constrained container. This can briefly use up to its 1 GiB RAM / 1 CPU limits.\n"
            "- **logs**: three commands each emit 3 MiB to both streams, "
            "including control/invalid bytes, "
            "to exercise per-stream and aggregate retained-log caps.\n\n"
            "Plans keep network=none, no host mounts/credentials, non-root, read-only image root, "
            "dropped capabilities and the existing time/resource/log limits. "
            "Containers do not make "
            "arbitrary code completely safe. Review the complete fixture source and JSON plans.\n\n"
            + "\n".join(f"- {case['id']}: `{case['plan_digest']}`" for case in cases)
            + "\n"
        )
        return manifest
    except BaseException:
        sentinel_path.unlink(missing_ok=True)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--image", required=True, help="Explicit digest-pinned image")
    parser.add_argument("--platform", required=True, choices=["linux/amd64", "linux/arm64"])
    args = parser.parse_args()
    print(encode_candidates(prepare(args.output, image=args.image, platform=args.platform)), end="")


if __name__ == "__main__":
    main()
