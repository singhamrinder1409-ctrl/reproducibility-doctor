"""Frozen reserved-corpus runtime evaluation. Prepare first; execute only real approved plans."""

import argparse
import hashlib
import json
import math
import os
import platform
import shlex
import shutil
import statistics
from importlib.metadata import version
from pathlib import Path

from evaluate import fixture_repository, measure

from reprodoctor.checks import check_snapshot
from reprodoctor.diagnosis import diagnose
from reprodoctor.execution import execute_plan
from reprodoctor.extraction import encode_candidates
from reprodoctor.intake import intake
from reprodoctor.planning import (
    build_plan,
    digest,
    planner_identity,
    read_document,
    validate_approval,
    validate_plan,
    wheel_inventory,
)
from reprodoctor.reporting import combined_markdown, combined_report
from reprodoctor.snapshot import load_snapshot

ROOT = Path(__file__).resolve().parents[1]
FREEZE = ROOT / "evaluation/runtime-freeze-v1.json"


def fingerprint():
    paths = sorted((ROOT / "src/reprodoctor").glob("*.py"))
    paths += sorted((ROOT / "evaluation/fixtures").glob("*.json"))
    paths += [
        ROOT / "evaluation/runtime-protocol-v1.json",
        ROOT / "scripts/evaluate.py",
        Path(__file__).resolve(),
    ]
    return {
        "engine": planner_identity(),
        "packaging_version": version("packaging"),
        "files": {
            p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in paths
        },
    }


def verify_freeze():
    frozen = read_document(FREEZE)
    if frozen != fingerprint():
        raise ValueError(
            "Runtime evaluation freeze drifted; retain results and document amendments"
        )
    return frozen


def write_new(path, value):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        stream.write(encode_candidates(value, maximum_bytes=64 * 1024 * 1024))


def prepare(output, *, image, platform_name, wheelhouse, frozen):
    if frozen != fingerprint():
        raise ValueError("Preparation freeze mismatch")
    if output.resolve().is_relative_to(ROOT):
        raise ValueError("Review output must be outside the checkout")
    output.mkdir(mode=0o700)
    protocol = read_document(ROOT / "evaluation/runtime-protocol-v1.json")
    original_wheels = wheel_inventory(wheelhouse)
    if original_wheels["content_digest"] != protocol["required_wheelhouse_content_digest"]:
        raise ValueError("Evaluation requires the frozen authored wheelhouse bytes")
    shared = output / "wheelhouse"
    shared.mkdir()
    for entry in original_wheels["files"]:
        shutil.copyfile(wheelhouse / entry["name"], shared / entry["name"], follow_symlinks=False)
    if wheel_inventory(shared) != original_wheels:
        raise ValueError("Wheel bytes changed during preparation")
    protocol = read_document(ROOT / "evaluation/runtime-protocol-v1.json")
    helper = [
        "#!/bin/zsh",
        "set -eu",
        "unset PYTHONPATH PYTHONHOME",
        'echo "Review the reserved corpus source and each full plan. No execution here."',
        "cat -- " + shlex.quote(str(output / "wheel-inventory.json")),
    ]
    write_new(output / "wheel-inventory.json", original_wheels)
    cases = []
    for name, expected in protocol["cases"].items():
        fixture = read_document(ROOT / "evaluation/fixtures" / (name + ".json"))
        base = output / name
        base.mkdir()
        fixture_repository(fixture["files"], base / "source")
        intake(str(base / "source"), base / "snapshot")
        wheels = shared if expected["wheelhouse"] else None
        plan = build_plan(base / "snapshot", image=image, platform=platform_name, wheelhouse=wheels)
        static = check_snapshot(base / "snapshot", python_version=protocol["target_python"])
        write_new(base / "plan.json", plan)
        write_new(base / "static.json", static)
        eligible = not plan["payload"]["blockers"]
        if eligible == (expected["expected_status"] == "abstain"):
            raise ValueError(f"{name}: protocol/plan eligibility mismatch before execution")
        cases.append(
            {
                "id": name,
                "eligible": eligible,
                "wheelhouse": bool(wheels),
                "plan_digest": plan["plan_digest"],
                "repository": plan["payload"]["repository"],
                "blockers": plan["payload"]["blockers"],
                "expected": expected,
            }
        )
        if not eligible:
            continue
        for path in sorted((base / "source").rglob("*")):
            if path.is_file() and ".git" not in path.parts:
                helper += [
                    "echo " + shlex.quote("Source: " + str(path)),
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
        if wheels:
            command += ["--wheelhouse", str(shared)]
        helper.append(" ".join(shlex.quote(value) for value in command))
    helper += [
        'echo "Tell Codex: evaluation plans approved. No corpus commands have run."',
        'read "?Press Enter to close."',
    ]
    path = output / "Review-and-approve-evaluation.command"
    path.write_text("\n".join(helper) + "\n")
    path.chmod(0o700)
    manifest = {
        "schema_version": 1,
        "kind": "reserved_runtime_preparation",
        "freeze_digest": digest(frozen),
        "execution_status": "not_run",
        "approval_created": False,
        "cases": cases,
    }
    write_new(output / "preparation.json", manifest)
    lines = [
        "# Reserved runtime evaluation — review seven plans",
        "",
        "The existing 12 authored fixture definitions are unchanged. Seven are executable; "
        "five remain unsupported/ambiguous and will be reported as explicit abstentions.",
        "",
        "NEW commands include a deliberately failing unittest, missing requirements, an "
        "unavailable OFFLINE distribution, a two-minute infinite-output timeout, successful "
        "launches/state, and a held-out memory-abuse/control-output fixture. No silent fixes.",
        "",
        "All runs retain the approved network/resource/filesystem/log restrictions. Shared-kernel "
        "risk remains; containers do not make arbitrary code completely safe. The wheelhouse "
        "is the same tiny authored wheel reviewed in lifecycle validation; its hash is shown. "
        "No remote package index, paid API or host target execution.",
        "",
        "The public split is not blinded. Frozen category-presence assertions have tiny "
        "denominators; this is not broad setup or causal-diagnosis accuracy.",
        "",
    ]
    for case in cases:
        lines += [
            "- "
            + case["id"]
            + ": "
            + (
                "APPROVAL REQUIRED — `" + case["plan_digest"] + "`"
                if case["eligible"]
                else "ABSTAIN — " + case["expected"]["reason"]
            )
        ]
    (output / "REVIEW.md").write_text("\n".join(lines) + "\n")
    return manifest


def run(review, *, socket, frozen):
    if frozen != fingerprint():
        raise ValueError("Execution freeze mismatch")
    manifest = read_document(review / "preparation.json")
    if manifest["freeze_digest"] != digest(frozen):
        raise ValueError("Review bindings changed")
    protocol = read_document(ROOT / "evaluation/runtime-protocol-v1.json")
    if [case["id"] for case in manifest["cases"]] != list(protocol["cases"]):
        raise ValueError("Reserved corpus membership/order changed")
    # Bind labels and source to the frozen corpus before reading any receipt/backend.
    for case in manifest["cases"]:
        name = case["id"]
        if case["expected"] != protocol["cases"][name]:
            raise ValueError("Frozen runtime labels changed")
        fixture = read_document(ROOT / "evaluation/fixtures" / (name + ".json"))
        _, contents = load_snapshot(review / name / "snapshot")
        if contents != {path: value.encode() for path, value in fixture["files"].items()}:
            raise ValueError("Prepared source differs from frozen fixture")
        wheels = review / "wheelhouse" if case["wheelhouse"] else None
        plan = validate_plan(
            read_document(review / name / "plan.json"),
            review / name / "snapshot",
            wheelhouse=wheels,
        )
        if (
            plan["plan_digest"] != case["plan_digest"]
            or plan["payload"]["repository"] != case["repository"]
            or case["wheelhouse"] != case["expected"]["wheelhouse"]
            or bool(plan["payload"]["blockers"]) == case["eligible"]
            or plan["payload"]["blockers"] != case["blockers"]
        ):
            raise ValueError("Prepared plan eligibility/bindings changed")
    output = review / "results"
    if output.exists():
        raise ValueError("Results already exist; retain prior evaluation rather than overwriting")
    # Verify EVERY receipt before touching Docker. No approval is manufactured.
    approved = {}
    for case in manifest["cases"]:
        if case["eligible"]:
            base = review / case["id"]
            wheels = review / "wheelhouse" if case["wheelhouse"] else None
            plan = validate_plan(
                read_document(base / "plan.json"), base / "snapshot", wheelhouse=wheels
            )
            receipt = read_document(base / "approval.json")
            validate_approval(receipt, plan)
            approved[case["id"]] = plan, receipt, wheels
    output.mkdir(mode=0o700)
    rows = []
    for case in manifest["cases"]:
        name, expected = case["id"], case["expected"]
        base = review / name
        row = {
            "id": name,
            "split": "held_out" if name.startswith("hold-") else "development",
            "repository": case["repository"],
            "expected_status": expected["expected_status"],
        }
        if not case["eligible"]:
            row.update(
                observed_status="abstain",
                reason=expected["reason"],
                blockers=case["blockers"],
                outcome_match=True,
                labels=[],
            )
        else:
            plan, receipt, wheels = approved[name]
            record = execute_plan(
                plan,
                receipt,
                base / "snapshot",
                output / (name + ".json"),
                wheelhouse=wheels,
                socket=socket,
                experimental=True,
            )
            diagnosis = diagnose(record)
            categories = {f["category"] for f in diagnosis["findings"]}
            static = read_document(base / "static.json")
            combined = combined_report(record, static)
            (output / (name + ".md")).write_text(combined_markdown(combined))
            row.update(
                observed_status=record["execution_status"],
                cleanup=record["cleanup"]["status"],
                seconds=record["seconds"],
                plan_digest=record["plan_digest"],
                outcome_match=record["execution_status"] == expected["expected_status"],
                diagnosis_categories=sorted(categories),
                labels=[],
            )
            checks = {
                "status": row["outcome_match"],
                "cleanup": record["cleanup"]["status"] == "removed",
            }
            category = expected.get("diagnosis_category")
            if category:
                matches = [f for f in diagnosis["findings"] if f["category"] == category]
                kind = (
                    "suggestion"
                    if category in {"missing_file", "dependency_artifact_unavailable"}
                    else "observation"
                )
                checks["diagnosis_category_and_kind"] = bool(matches) and all(
                    f["kind"] == kind for f in matches
                )
            for rule in read_document(ROOT / "evaluation/runtime-protocol-v1.json")[
                "diagnosis_rules"
            ]:
                row["labels"].append(
                    {
                        "rule": rule,
                        "expected": expected.get("diagnosis_category") == rule,
                        "observed": rule in categories,
                    }
                )
            if expected.get("clean_static"):
                row["definitive_static_findings"] = static["summary"].get("finding", 0)
                checks["no_definitive_static_false_positive"] = (
                    row["definitive_static_findings"] == 0
                )
            first_step = next(iter(record["steps"]), {})
            if expected.get("require_truncation"):
                row["truncation_observed"] = first_step.get("stdout", {}).get("truncated", False)
                checks["truncation"] = row["truncation_observed"]
            if expected.get("require_escaped_controls"):
                text = first_step.get("stdout", {}).get("text", "")
                row["terminal_controls_escaped"] = "\x1b" not in text and "\\u001b" in text
                checks["controls_escaped"] = row["terminal_controls_escaped"]
            if expected.get("cause_unknown"):
                row["causal_suggestions"] = sum(
                    f["kind"] == "suggestion" for f in diagnosis["findings"]
                )
                row["coverage_limit"] = expected["coverage_limit"]
                checks["unknown_cause_not_invented"] = row["causal_suggestions"] == 0
            row["checks"] = checks
            row["outcome_match"] = all(checks.values())
            if record["execution_status"] in {"infrastructure_error", "cancelled"}:
                row["halt_reason"] = (
                    "Infrastructure/cancellation interrupted evaluation; later cases not run"
                )
            if record["cleanup"]["status"] not in {"removed", "absent", "not_needed"}:
                row["halt_reason"] = "Cleanup unconfirmed; later corpus cases were not run"
        rows.append(row)
        write_new(output / (name + "-evaluation.json"), row)
        print(name + ": " + row["observed_status"], flush=True)
        if "halt_reason" in row:
            break
    durations = sorted(row["seconds"] for row in rows if "seconds" in row)
    result = {
        "schema_version": 1,
        "kind": "reserved_runtime_evaluation",
        "freeze_digest": digest(frozen),
        "host_python": platform.python_version(),
        "planned_cases": len(manifest["cases"]),
        "results": rows,
        "executed_cases": len(durations),
        "planning_abstentions": sum(r["observed_status"] == "abstain" for r in rows),
        "outcome_matches": sum(r["outcome_match"] for r in rows),
        "unreached_cases": [
            c["id"] for c in manifest["cases"] if c["id"] not in {r["id"] for r in rows}
        ],
        "metrics": {
            split: measure([r for r in rows if r["split"] == split])
            for split in ("development", "held_out")
        },
        "timings": {
            "executed_sample_count": len(durations),
            "p50_seconds": statistics.median(durations) if durations else None,
            "p95_seconds_nearest_rank": durations[math.ceil(0.95 * len(durations)) - 1]
            if durations
            else None,
        },
        "limitations": read_document(ROOT / "evaluation/runtime-protocol-v1.json")["limitations"],
    }
    write_new(output / "summary.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--run-approved", action="store_true")
    parser.add_argument("--review", type=Path)
    parser.add_argument("--image")
    parser.add_argument("--platform", choices=["linux/arm64", "linux/amd64"])
    parser.add_argument("--wheelhouse", type=Path)
    parser.add_argument("--docker-socket")
    args = parser.parse_args()
    if args.freeze:
        write_new(FREEZE, fingerprint())
    elif args.prepare:
        if not all((args.review, args.image, args.platform, args.wheelhouse)):
            parser.error("Preparation requires --review, --image, --platform and --wheelhouse")
        result = prepare(
            args.review,
            image=args.image,
            platform_name=args.platform,
            wheelhouse=args.wheelhouse,
            frozen=verify_freeze(),
        )
        print(encode_candidates(result), end="")
    else:
        if not args.review or not args.docker_socket:
            parser.error("Execution requires --review and explicit --docker-socket")
        result = run(args.review, socket=args.docker_socket, frozen=verify_freeze())
        print(json.dumps({"cases": len(result["results"]), "executed": result["executed_cases"]}))


if __name__ == "__main__":
    main()
