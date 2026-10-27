"""Deterministic interpretation of local execution records, never project execution."""

import hashlib
import json
import re
from pathlib import Path

from . import __version__
from .intake import IntakeError
from .planning import _nonfinite, _pairs

MAX_REPORT = 64 * 1024 * 1024
RULES = (
    (
        "missing_file",
        r"FileNotFoundError|can't open file|No such file or directory",
        "Check the referenced path against the pinned source and earlier generated files.",
    ),
    (
        "dependency_artifact_unavailable",
        r"No matching distribution found|Could not find a version that satisfies",
        (
            "Check approved offline wheels, Python/platform tags and version "
            "constraints. This does not establish remote package availability."
        ),
    ),
    (
        "missing_import",
        r"ModuleNotFoundError|ImportError",
        "Check declared dependencies, approved installation steps and import paths.",
    ),
    (
        "version_incompatibility",
        (
            "requires a different "
            "Python|Requires-Python|UnsupportedPythonVersion|ResolutionIm"
            "possible|conflicting dependencies"
        ),
        "Compare the recorded interpreter, dependency constraints and approved artifacts.",
    ),
    (
        "missing_configuration",
        (
            "KeyError:|environment variable.{0,80}(?:missing|not "
            "set|required)|(?:missing|required).{0,80}(?:configuration|en"
            "vironment variable)"
        ),
        (
            "Review the named configuration and documented examples. Supply "
            "only disposable test values; KeyError alone does not prove an "
            "environment variable is required."
        ),
    ),
)


def read_execution(path: Path) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_REPORT:
        raise IntakeError("Execution report must be a bounded regular JSON file")
    try:
        with path.open("rb") as stream:
            raw = stream.read(MAX_REPORT + 1)
        if len(raw) > MAX_REPORT:
            raise ValueError()
        value = json.loads(raw, object_pairs_hook=_pairs, parse_constant=_nonfinite)
        validate_execution(value)
        return value
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError) as exc:
        raise IntakeError("Invalid execution report") from exc


def validate_execution(value: dict) -> None:
    if (
        not isinstance(value, dict)
        or value.get("kind") != "execution_report"
        or type(value.get("schema_version")) is not int
        or value["schema_version"] != 1
    ):
        raise ValueError("Expected execution_report schema 1")
    if value.get("execution_status") not in {
        "not_run",
        "completed",
        "failed",
        "timed_out",
        "cancelled",
        "infrastructure_error",
    }:
        raise ValueError("Invalid execution status")
    repository = value["repository"]
    if not isinstance(repository, dict) or not all(
        isinstance(repository.get(k), str) for k in ("commit", "content_digest")
    ):
        raise ValueError("Missing source binding")
    if not isinstance(value.get("cleanup"), dict) or not isinstance(
        value["cleanup"].get("status"), str
    ):
        raise ValueError("Missing cleanup status")
    if not isinstance(value.get("steps"), list) or len(value["steps"]) > 200:
        raise ValueError("Invalid steps")
    ids = set()
    for step in value["steps"]:
        if not isinstance(step, dict) or not isinstance(step.get("id"), str) or step["id"] in ids:
            raise ValueError("Invalid or duplicate step")
        ids.add(step["id"])
        if step.get("status") not in {
            "excluded",
            "state_updated",
            "starting",
            "passed",
            "failed",
            "timed_out",
            "cancelled",
            "infrastructure_error",
        }:
            raise ValueError("Invalid step status")
        if (
            "exit_code" in step
            and step["exit_code"] is not None
            and type(step["exit_code"]) is not int
        ):
            raise ValueError("Invalid exit code")
        if not isinstance(step.get("source", {}), dict) or not isinstance(
            step.get("effective", {}), dict
        ):
            raise ValueError("Invalid step provenance")
        for name in ("stdout", "stderr"):
            if name in step and (
                not isinstance(step[name], dict)
                or not isinstance(step[name].get("text"), str)
                or len(step[name]["text"].encode()) > 8 * 1024 * 1024
            ):
                raise ValueError("Invalid bounded log")


def diagnose(report: dict) -> dict:
    """Facts describe the record; patterns in attacker-controlled logs are only hints."""
    try:
        validate_execution(report)
    except (ValueError, TypeError, KeyError) as exc:
        raise IntakeError("Invalid execution report") from exc
    findings = []

    def add(category, fact, action, evidence, *, kind="observation"):
        findings.append(
            {
                "id": f"diagnosis-{len(findings) + 1:04d}",
                "category": category,
                "kind": kind,
                "observed_fact": fact,
                "suggested_action": action,
                "evidence": evidence,
            }
        )

    status = report["execution_status"]
    if status in {"infrastructure_error", "not_run", "cancelled", "timed_out"}:
        add(
            status,
            f"The execution record reports {status}.",
            (
                "Inspect runner errors, timings and runtime settings before "
                "attributing this outcome to the project."
            ),
            {"json_pointer": "/execution_status", "value": status},
        )
    if report["cleanup"]["status"] not in {"removed", "absent", "not_needed"}:
        add(
            "cleanup_incomplete",
            "Container removal was not confirmed by this record.",
            (
                "Inspect the recovery journal and use reprodoctor cleanup with "
                "the original local socket."
            ),
            {"json_pointer": "/cleanup", "value": report["cleanup"]},
        )
    for index, step in enumerate(report["steps"]):
        prefix = f"/steps/{index}"
        state = step["status"]
        if state not in {"failed", "timed_out", "cancelled", "infrastructure_error"}:
            continue
        evidence = {
            "step_id": step["id"],
            "json_pointer": prefix,
            "source": step.get("source", {}),
            "exit_code": step.get("exit_code"),
            "exit_code_source": step.get("exit_code_source"),
            "signal": step.get("signal"),
        }
        phase = step.get("source", {}).get("phase")
        category = (
            "unsuccessful_tests" if phase == "test" and state == "failed" else "command_" + state
        )
        add(
            category,
            f"Step {step['id']} has recorded status {state} and exit code {step.get('exit_code')}.",
            (
                "Review the effective argv, bounded logs and source instruction. "
                "A CLI exit status alone does not identify a root cause."
            ),
            evidence,
        )
        # Transport errors and interruption logs cannot establish project failure causes.
        if (
            state != "failed"
            or status == "infrastructure_error"
            or step.get("exit_code") in {125, 126, 127}
        ):
            continue
        for stream in ("stderr", "stdout"):
            log = step.get(stream, {})
            text = log.get("text", "")
            for category, pattern, action in RULES:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    add(
                        category,
                        f"The recorded {stream} contains text matching {category}; "
                        "this is a possible cause, not verified truth.",
                        action,
                        {
                            "step_id": step["id"],
                            "json_pointer": prefix + "/" + stream + "/text",
                            "character_span": list(match.span()),
                            "excerpt": text[max(0, match.start() - 100) : match.end() + 180],
                            "retained_text_sha256": hashlib.sha256(text.encode()).hexdigest(),
                            "truncated": log.get("truncated", False),
                        },
                        kind="suggestion",
                    )
    return {
        "schema_version": 1,
        "kind": "diagnosis_report",
        "tool_version": __version__,
        "repository": report["repository"],
        "plan_digest": report.get("plan_digest"),
        "execution_status": status,
        "experimental": report.get("experimental", True),
        "live_validation": report.get("live_validation", "unknown"),
        "findings": findings,
        "limitations": [
            (
                "This interprets an editable local execution record; it does not "
                "authenticate the record or rerun commands."
            ),
            (
                "Logs are untrusted and may be forged, incomplete or truncated. "
                "Pattern matches are suggestions only."
            ),
            (
                "No match means unknown cause. Successful commands are not proof "
                "of reproducibility or application correctness."
            ),
            (
                "Docker CLI and program exit codes can be ambiguous; no signal or "
                "exact root cause is inferred."
            ),
        ],
    }
