"""Inspection commands export evidence and candidates, never setup verdicts."""

import argparse
import json
import os
import sys
from pathlib import Path

from .checks import check_snapshot
from .extraction import encode_candidates, extract_snapshot
from .intake import IntakeError, intake
from .planning import (
    approval_record,
    build_plan,
    dry_run,
    read_document,
    validate_plan,
)
from .static_report import markdown_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="reprodoctor")
    commands = parser.add_subparsers(dest="command", required=True)
    snapshot = commands.add_parser(
        "intake", help="Pin and export tracked Git files without checkout"
    )
    snapshot.add_argument("source", help="Local repository or public HTTPS GitHub repository URL")
    snapshot.add_argument("--ref", default="HEAD", help="Commit, branch or tag (default: HEAD)")
    snapshot.add_argument("--output", required=True, type=Path, help="New directory outside input")
    snapshot.add_argument(
        "--committed-only",
        action="store_true",
        help="Explicitly ignore local working-tree/index changes and inspect the selected commit",
    )
    extraction = commands.add_parser(
        "extract", help="Extract review-only README command candidates"
    )
    extraction.add_argument("snapshot", type=Path, help="Snapshot directory produced by intake")
    extraction.add_argument(
        "--output", type=Path, help="New JSON file outside the snapshot; else stdout"
    )
    checking = commands.add_parser("check", help="Check a snapshot statically; no execution")
    checking.add_argument("snapshot", type=Path)
    checking.add_argument("--output", type=Path, help="New file outside snapshot; otherwise stdout")
    checking.add_argument("--format", choices=["json", "markdown"], default="json")
    checking.add_argument(
        "--python-version", default="3.12.0", help="Static target, not an executed runtime"
    )
    planning = commands.add_parser(
        "plan", help="Build a reviewable plan; does not approve or execute"
    )
    planning.add_argument("snapshot", type=Path)
    planning.add_argument("--image", help="Digest-pinned image; omit to produce a blocked draft")
    planning.add_argument(
        "--platform", choices=["linux/amd64", "linux/arm64"], default="linux/amd64"
    )
    planning.add_argument(
        "--decisions", type=Path, help="Explicit accept/replace/exclude decisions JSON"
    )
    planning.add_argument("--wheelhouse", type=Path, help="Explicit local .whl files; no downloads")
    planning.add_argument("--output", required=True, type=Path, help="New plan file outside inputs")
    approving = commands.add_parser(
        "approve", help="Display a plan and require full-digest confirmation"
    )
    running = commands.add_parser("run", help="Dry-run only at this milestone; no executor exists")
    for command in (approving, running):
        command.add_argument("plan", type=Path)
        command.add_argument("--snapshot", required=True, type=Path)
        command.add_argument(
            "--wheelhouse", type=Path, help="Supply again if the plan includes wheels"
        )
    approving.add_argument("--output", required=True, type=Path, help="New local approval record")
    running.add_argument("--dry-run", action="store_true")
    running.add_argument(
        "--approval", type=Path, help="Optionally verify a matching approval record"
    )
    args = parser.parse_args(argv)
    try:
        if args.command in {"plan", "approve", "run"}:
            if args.command == "run" and not args.dry_run:
                raise IntakeError("Execution is not implemented. Use --dry-run; no commands ran.")
            if args.command != "run":
                _new_output(args.output, args.snapshot, args.wheelhouse)
            if args.command == "plan":
                result = build_plan(
                    args.snapshot,
                    image=args.image,
                    platform=args.platform,
                    wheelhouse=args.wheelhouse,
                    decisions=read_document(args.decisions) if args.decisions else None,
                )
                _write_new(args.output, result)
                print(
                    json.dumps(
                        {
                            "output": str(args.output.absolute()),
                            "plan_digest": result["plan_digest"],
                            "state": result["payload"]["state"],
                        }
                    )
                )
            elif args.command == "approve":
                plan = validate_plan(
                    read_document(args.plan), args.snapshot, wheelhouse=args.wheelhouse
                )
                # Always display the complete escaped plan, including blockers, before refusal.
                print(encode_candidates(plan), end="")
                if plan["payload"]["blockers"]:
                    raise IntakeError(
                        "Blocked plans cannot be approved; resolve the listed blockers"
                    )
                if not sys.stdin.isatty() or not sys.stdout.isatty():
                    raise IntakeError(
                        "Approval requires an interactive terminal; no --yes or piped approval"
                    )
                confirmation = input(
                    "Review every step/settings, then type the full plan digest to approve: "
                )
                # Revalidate again after human review before binding the approval record.
                current = validate_plan(plan, args.snapshot, wheelhouse=args.wheelhouse)
                _write_new(args.output, approval_record(current, confirmation))
                print(
                    json.dumps(
                        {"approval": str(args.output.absolute()), "execution_status": "not_run"}
                    )
                )
            else:
                result = dry_run(
                    read_document(args.plan),
                    args.snapshot,
                    wheelhouse=args.wheelhouse,
                    approval=read_document(args.approval) if args.approval else None,
                )
                print(encode_candidates(result), end="")
            return 0
        if args.command in {"extract", "check"}:
            if args.output is not None and args.output.resolve().is_relative_to(
                args.snapshot.resolve()
            ):
                raise IntakeError("Report output must be outside the snapshot")
            result = (
                extract_snapshot(args.snapshot)
                if args.command == "extract"
                else check_snapshot(args.snapshot, python_version=args.python_version)
            )
            encoded = (
                markdown_report(result)
                if args.command == "check" and args.format == "markdown"
                else encode_candidates(result)
            )
            if len(encoded.encode()) > 8 * 1024 * 1024:
                raise IntakeError("Report output byte limit exceeded; no partial result")
            if args.output is None:
                print(encoded, end="")
            else:
                with args.output.open("x", encoding="utf-8") as stream:
                    stream.write(encoded)
                print(
                    json.dumps(
                        {
                            "output": str(args.output.absolute()),
                            "records": len(result.get("instructions", result.get("findings", []))),
                        }
                    )
                )
            return 0
        manifest = intake(
            args.source,
            args.output,
            ref=args.ref,
            committed_only=args.committed_only,
        )
    except (EOFError, KeyboardInterrupt):
        print(json.dumps({"error": "Operation cancelled; no project commands executed."}))
        return 2
    except (IntakeError, OSError) as exc:
        # JSON escaping prevents control characters in paths/errors affecting terminals.
        print(json.dumps({"error": str(exc)}, ensure_ascii=True))
        return 2
    print(
        json.dumps(
            {
                "commit": manifest["commit"],
                "content_digest": manifest["content_digest"],
                "files": len(manifest["files"]),
                "output": str(args.output.absolute()),
            },
            ensure_ascii=True,
        )
    )
    return 0


def _new_output(output: Path, snapshot: Path, wheelhouse: Path | None) -> None:
    if output.exists() or output.is_symlink():
        raise IntakeError("Output must be a new file")
    for source in (snapshot, wheelhouse):
        if source is not None and output.resolve().is_relative_to(source.resolve()):
            raise IntakeError("Output must be outside snapshot and wheelhouse inputs")
    if not output.parent.is_dir():
        raise IntakeError("Output parent directory must already exist")


def _write_new(output: Path, document: dict) -> None:
    encoded = encode_candidates(document)
    descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write(encoded)
