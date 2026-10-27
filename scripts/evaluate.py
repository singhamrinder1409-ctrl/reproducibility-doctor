"""Frozen authored static evaluation. Never executes fixture Python/README commands."""

import argparse
import hashlib
import json
import os
import platform
import statistics
import subprocess
import tempfile
import time
from pathlib import Path

from reprodoctor.checks import check_snapshot
from reprodoctor.extraction import extract_snapshot
from reprodoctor.intake import intake

ROOT = Path(__file__).resolve().parents[1]


def fixture_repository(files: dict, destination: Path) -> None:
    """Writes only the tracked, authored fixture definitions shipped with Doctor."""
    destination.mkdir()
    for name, text in files.items():
        path = destination / name
        if path.is_absolute() and not path.is_relative_to(destination):
            raise ValueError("Fixture escaped destination")
        if ".." in Path(name).parts or Path(name).is_absolute():
            raise ValueError("Invalid authored fixture path")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    env = {
        "PATH": os.defpath,
        "HOME": str(destination.parent),
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "Doctor Fixture",
        "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
        "GIT_COMMITTER_NAME": "Doctor Fixture",
        "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
        "GIT_AUTHOR_DATE": "2000-01-01T00:00:00+00:00",
        "GIT_COMMITTER_DATE": "2000-01-01T00:00:00+00:00",
    }
    for args in (
        ["init", "--template=", "--object-format=sha1", "--initial-branch=main"],
        ["add", "."],
        ["commit", "-m", "Authored evaluation fixture"],
    ):
        subprocess.run(
            ["git", "-C", str(destination), "-c", "core.hooksPath=/dev/null", *args],
            env=env,
            check=True,
            capture_output=True,
            timeout=30,
        )


def freeze_digest() -> str:
    hasher = hashlib.sha256()
    paths = sorted((ROOT / "evaluation/fixtures").glob("*.json"))
    paths += sorted((ROOT / "src/reprodoctor").glob("*.py"))
    paths += [Path(__file__).resolve()]
    for path in paths:
        hasher.update(path.relative_to(ROOT).as_posix().encode() + b"\0" + path.read_bytes())
    return hasher.hexdigest()


def measure(results: list) -> dict:
    metrics = {}
    for row in results:
        for label in row["labels"]:
            rule = label["rule"]
            counts = metrics.setdefault(rule, {"tp": 0, "fp": 0, "tn": 0, "fn": 0})
            expected, observed = label["expected"], label["observed"]
            counts[
                "tp" if expected and observed else "fp" if observed else "fn" if expected else "tn"
            ] += 1
    for counts in metrics.values():
        tp, fp, tn, fn = (counts[k] for k in ("tp", "fp", "tn", "fn"))
        counts.update(
            precision=tp / (tp + fp) if tp + fp else None,
            recall=tp / (tp + fn) if tp + fn else None,
            false_positive_rate=fp / (fp + tn) if fp + tn else None,
            labeled_assertions=tp + fp + tn + fn,
        )
    return metrics


def evaluate() -> dict:
    frozen = (ROOT / "evaluation/frozen.sha256").read_text().strip()
    if freeze_digest() != frozen:
        raise ValueError(
            "Frozen implementation/fixtures changed; do not silently retune held-out results"
        )
    results = []
    with tempfile.TemporaryDirectory(prefix="doctor-evaluation-") as temporary:
        for path in sorted((ROOT / "evaluation/fixtures").glob("*.json")):
            fixture = json.loads(path.read_text())
            base = Path(temporary) / fixture["id"]
            base.mkdir()
            started = time.monotonic()
            fixture_repository(fixture["files"], base / "repo")
            intake(str(base / "repo"), base / "snapshot")
            static = check_snapshot(base / "snapshot")
            extraction = extract_snapshot(base / "snapshot")
            labels = []
            for rule, status, expected in fixture["labels"]:
                observed = (
                    any(item["ambiguity_reasons"] for item in extraction["instructions"])
                    if rule == "extraction"
                    else any(
                        item["rule_id"] == rule and item["status"] == status
                        for item in static["findings"]
                    )
                )
                labels.append(
                    {"rule": rule + "/" + status, "expected": expected, "observed": observed}
                )
            results.append(
                {
                    "id": fixture["id"],
                    "split": "held_out" if fixture["id"].startswith("hold-") else "development",
                    "repository": static["repository"],
                    "labels": labels,
                    "static_unknown_or_unsupported": sum(
                        f["status"] in {"unknown", "unsupported"} for f in static["findings"]
                    ),
                    "runtime_status": "not_run",
                    "runtime_expected": fixture["runtime_expected"],
                    "seconds": round(time.monotonic() - started, 6),
                }
            )
    durations = sorted(row["seconds"] for row in results)
    return {
        "schema_version": 1,
        "kind": "static_evaluation",
        "frozen_sha256": frozen,
        "environment": {"python": platform.python_version(), "platform": platform.platform()},
        "scope": "Authored static rule/status assertions only; not end-to-end setup accuracy.",
        "results": results,
        "metrics": {
            split: measure([r for r in results if r["split"] == split])
            for split in ("development", "held_out")
        },
        "timings": {
            "sample_count": len(durations),
            "p50_seconds": statistics.median(durations),
            "p95_seconds_nearest_rank": durations[-1],
        },
        "execution_reliability": {
            "attempted": 0,
            "successful": None,
            "cleanup_rate": None,
            "reason": "Live Docker validation deferred",
        },
        "limitations": [
            "Tiny authored fixtures are not representative of GitHub projects.",
            "Held-out definitions were visible to the author; "
            "this is a pre-reserved split, not a blinded study.",
            "Precision/recall denominators are explicit rule/status assertions, "
            "not all possible defects.",
            "No execution, containment or end-to-end reproducibility accuracy is measured.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--freeze", action="store_true", help="Write a NEW freeze before first evaluation"
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.freeze:
        with (ROOT / "evaluation/frozen.sha256").open("x") as stream:
            stream.write(freeze_digest() + "\n")
    else:
        if not args.output:
            parser.error("--output is required")
        result = evaluate()
        with args.output.open("x") as stream:
            json.dump(result, stream, indent=2)
            stream.write("\n")
        print("Static evaluation written; no fixture commands executed.")


if __name__ == "__main__":
    main()
