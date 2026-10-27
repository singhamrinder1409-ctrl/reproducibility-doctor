"""Readable static-only report; never renders repository HTML or executable links."""

import html
import re


def _text(value: object) -> str:
    text = str(value)
    text = re.sub(r"[\x00-\x1f\x7f]", lambda m: f"\\u{ord(m[0]):04x}", text)
    text = html.escape(text, quote=True)
    for character in "\\`*_[]|":
        text = text.replace(character, f"&#{ord(character)};")
    return text


def markdown_report(report: dict) -> str:
    lines = [
        "# Reproducibility Doctor — static inspection",
        "",
        "Execution: **not run**. This report contains static observations, not a setup verdict.",
        "",
        f"Commit: {_text(report['repository']['commit'])}",
        f"Snapshot digest: {_text(report['repository']['content_digest'])}",
        f"Static target Python: {_text(report['target_python'])}",
        "Checker environment: " + _text(report.get("checker_environment", {})),
        "",
        "Status counts: " + ", ".join(f"{_text(k)}={v}" for k, v in report["summary"].items()),
        "",
    ]
    for finding in report["findings"]:
        lines.extend(
            [
                f"## {_text(finding['id'])}: {_text(finding['rule_id'])} "
                f"— {_text(finding['status'])}",
                "",
                "Observed: " + _text(finding["observed_fact"]),
                "",
                "Suggested next action: " + _text(finding["suggested_action"]),
                "",
                "Limit: " + _text(finding["limitation"]),
                "",
            ]
        )
        if not finding["evidence"]:
            lines.extend(["Evidence: snapshot inventory / limited check coverage.", ""])
        for evidence in finding["evidence"]:
            location = evidence["path"]
            if evidence["start_line"] is not None:
                location += f":{evidence['start_line']}"
                if evidence["end_line"] != evidence["start_line"]:
                    location += f"–{evidence['end_line']}"
            lines.extend(
                [
                    "Evidence: "
                    + _text(location)
                    + "; SHA-256: "
                    + _text(evidence["sha256"] or "absent"),
                    "",
                ]
            )
    lines.extend(
        [
            "## Reproduce this inspection",
            "",
            "1. Obtain the same committed source and verify the recorded snapshot digest.",
            "2. Use the recorded Doctor version and dependency versions.",
            "3. Run reprodoctor check SNAPSHOT --python-version "
            + _text(report["target_python"])
            + " --format markdown.",
            "4. Review findings alongside the source. No project commands have run.",
            "",
            "Doctor version: " + _text(report["tool_version"]),
            "",
            "## Coverage and limitations",
            "",
        ]
    )
    lines.extend("- " + _text(limit) for limit in report["limitations"])
    lines.append("")
    return "\n".join(lines)
