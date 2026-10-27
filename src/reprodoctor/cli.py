"""The milestone-2 interface exports snapshots, not setup verdicts."""

import argparse
import json
from pathlib import Path

from .intake import IntakeError, intake


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
    args = parser.parse_args(argv)
    try:
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
