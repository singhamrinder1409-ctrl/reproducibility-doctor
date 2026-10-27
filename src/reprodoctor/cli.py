"""Inspection commands export evidence and candidates, never setup verdicts."""

import argparse
import json
from pathlib import Path

from .checks import check_snapshot
from .extraction import encode_candidates, extract_snapshot
from .intake import IntakeError, intake
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
    args = parser.parse_args(argv)
    try:
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
