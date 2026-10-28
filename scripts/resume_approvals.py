"""Resume prepared review plans without overwriting receipts or supplying approval input."""

import argparse
import builtins
import re
import sys
from pathlib import Path

from reprodoctor.cli import main as doctor_main
from reprodoctor.intake import IntakeError
from reprodoctor.planning import read_document, validate_approval, validate_plan
from reprodoctor.snapshot import load_snapshot

KINDS = {"reserved_runtime_preparation", "lifecycle_probe_preparation", "control_probe_preparation"}


def terminal_text(value):
    return "".join(
        c if c in "\n\t" or 32 <= ord(c) < 127 else f"\\u{ord(c):04x}" for c in str(value)
    )


def resume(review):
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise IntakeError("Approval needs an interactive terminal; no piped confirmation")
    review = review.resolve()
    manifest = read_document(review / "preparation.json")
    if manifest.get("kind") not in KINDS:
        raise IntakeError("Unsupported preparation manifest")
    original_input = builtins.input
    for case in manifest["cases"]:
        if case.get("eligible") is False:
            continue
        name = case["id"]
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", name):
            raise IntakeError("Unsafe prepared case ID")
        root = review / name
        wheels = None
        if case.get("wheelhouse"):
            wheels = (
                review if manifest["kind"] == "reserved_runtime_preparation" else root
            ) / "wheelhouse"
        for path in (root, root / "snapshot", wheels):
            if path is not None and not path.resolve().is_relative_to(review):
                raise IntakeError("Prepared input escapes review directory")
        plan = validate_plan(
            read_document(root / "plan.json"), root / "snapshot", wheelhouse=wheels
        )
        receipt = root / "approval.json"
        if receipt.exists() or receipt.is_symlink():
            validate_approval(read_document(receipt), plan)
            print(name + ": saved approval verified; skipping.")
            continue
        if plan["payload"]["blockers"]:
            raise IntakeError("Blocked plan cannot be approved; inspect its full blockers")
        _, contents = load_snapshot(root / "snapshot")
        print("Review pinned source for " + name)
        if sum(map(len, contents.values())) <= 256 * 1024:
            for path, data in sorted(contents.items()):
                print("Source: " + terminal_text(path))
                print(terminal_text(data.decode("utf-8", errors="replace")))
        else:
            print("Source exceeds the display budget; inspect the pinned snapshot separately.")

        # Display the digest beside the prompt; return only the HUMAN's unmodified input.
        def human_input(prompt):
            print("\nCURRENT PLAN: " + name)
            print("Copy only this hash, without labels, quotes or backticks:")
            print(plan["plan_digest"])
            return original_input(prompt)

        command = [
            "approve",
            str(root / "plan.json"),
            "--snapshot",
            str(root / "snapshot"),
            "--output",
            str(receipt),
        ]
        if wheels:
            command += ["--wheelhouse", str(wheels)]
        builtins.input = human_input
        try:
            status = doctor_main(command)
        finally:
            builtins.input = original_input
        if status:
            print(
                "No approval saved for this plan. Rerun to resume here; saved receipts stay intact."
            )
            return status
        validate_approval(read_document(receipt), plan)
    print("All eligible approval receipts verified. No target commands or Docker calls were made.")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", required=True, type=Path)
    args = parser.parse_args()
    try:
        return resume(args.review)
    except (IntakeError, OSError) as error:
        print(terminal_text(error))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
