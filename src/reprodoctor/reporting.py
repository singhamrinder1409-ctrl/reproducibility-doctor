"""Readable and structured reports; repository/log text is escaped as plain data."""

import hashlib
import json

from .diagnosis import diagnose
from .intake import IntakeError
from .static_report import _text, markdown_report


def combined_report(execution: dict, static: dict | None = None) -> dict:
    diagnosis = diagnose(execution)
    if static is not None:
        if (
            static.get("kind") != "static_report"
            or static.get("repository") != execution["repository"]
        ):
            raise IntakeError("Static report must match the execution repository binding")
        try:
            markdown_report(static)
        except (KeyError, TypeError, AttributeError) as exc:
            raise IntakeError("Invalid static report structure") from exc
    encoded = json.dumps(execution, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return {
        "schema_version": 1,
        "kind": "combined_report",
        "repository": execution["repository"],
        "input_execution_sha256": hashlib.sha256(encoded.encode()).hexdigest(),
        "execution": execution,
        "diagnosis": diagnosis,
        "static": static,
        "reproduction_steps": [
            "Obtain the recorded commit and verify its snapshot content digest.",
            (
                "Use the recorded Doctor engine, platform, digest-pinned image "
                "and offline artifact hashes."
            ),
            (
                "Rebuild the plan with the same explicit review decisions and "
                "inspect every command/settings."
            ),
            (
                "Approve the new plan interactively before any execution; supply "
                "the explicit local Docker socket."
            ),
            (
                "Run only if the runtime passes the recorded policy. Compare "
                "statuses, logs and cleanup evidence."
            ),
        ],
    }


def diagnosis_markdown(report: dict) -> str:
    lines = [
        "# Reproducibility Doctor — failure diagnosis",
        "",
        "Execution status: " + _text(report["execution_status"]),
        "",
        "Live validation: " + _text(report["live_validation"]),
        "",
        "Commit: " + _text(report["repository"]["commit"]),
        "",
    ]
    if not report["findings"]:
        lines += [
            "No failure findings from the recorded fields. This is not a reproducibility verdict.",
            "",
        ]
    for finding in report["findings"]:
        lines += [
            "## " + _text(finding["id"]) + ": " + _text(finding["category"]),
            "",
            "Type: " + _text(finding["kind"]),
            "",
            "Observed: " + _text(finding["observed_fact"]),
            "",
            "Suggested next action: " + _text(finding["suggested_action"]),
            "",
            "Evidence: "
            + _text(json.dumps(finding["evidence"], ensure_ascii=True, sort_keys=True)),
            "",
        ]
    lines += ["## Limits", ""] + ["- " + _text(item) for item in report["limitations"]] + [""]
    return "\n".join(lines)


def combined_markdown(report: dict) -> str:
    execution = report["execution"]
    lines = [
        "# Reproducibility Doctor — run report",
        "",
        "Experimental execution; live validation: " + _text(report["diagnosis"]["live_validation"]),
        "",
        (
            "This report interprets a local record; it does not authenticate "
            "evidence or certify safety."
        ),
        "",
        "Snapshot digest: " + _text(report["repository"]["content_digest"]),
        "",
        "Plan digest: " + _text(execution.get("plan_digest")),
        "",
        "Input execution record SHA-256 (canonical JSON): " + report["input_execution_sha256"],
        "",
        "Cleanup: " + _text(execution["cleanup"]),
        "",
        "## Recorded steps",
        "",
    ]
    for step in execution["steps"]:
        lines += [
            "### " + _text(step["id"]) + " — " + _text(step["status"]),
            "",
            "Source: " + _text(step.get("source", {})),
            "",
            "Effective command/state: " + _text(step.get("effective", {})),
            "",
            "Exit code/source: " + _text([step.get("exit_code"), step.get("exit_code_source")]),
            "",
            "Elapsed seconds: " + _text(step.get("seconds")),
            "",
        ]
        for stream in ("stdout", "stderr"):
            if stream in step:
                lines += [stream + " (bounded): " + _text(step[stream]), ""]
    lines += [
        "Not reached: " + _text(execution.get("steps_not_reached", [])),
        "",
        "## Environment and evidence",
        "",
        "Approved settings: " + _text(execution.get("approved_container_settings", {})),
        "",
        "Observed preflight: " + _text(execution.get("preflight", {})),
        "",
        "Artifacts: " + _text(execution.get("artifacts", {})),
        "",
        "Engine: " + _text(execution.get("engine", {})),
        "",
        diagnosis_markdown(report["diagnosis"]),
        "## Reproduction steps",
        "",
    ]
    lines += [f"{i}. {_text(item)}" for i, item in enumerate(report["reproduction_steps"], 1)]
    if report["static"] is not None:
        lines += ["", markdown_report(report["static"])]
    return "\n".join(lines) + "\n"
