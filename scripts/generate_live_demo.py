"""Create a read-only replay of genuine approved records. Never executes target commands."""

import argparse
import html
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path, help="New directory only")
    args = parser.parse_args()
    args.output.mkdir()
    summary = json.loads((ROOT / "evaluation/results-runtime-v1.json").read_text())
    scenes = []
    for case in ("dev-01", "dev-02", "dev-05", "dev-08", "hold-04"):
        source = ROOT / "examples" / ("runtime-" + case + ".json")
        if source.is_symlink() or source.stat().st_size > 128 * 1024:
            raise ValueError("Replay expects bounded authored records")
        command = ["diagnose", str(source), "--format", "json"]
        result = subprocess.run(
            [sys.executable, "-I", "-m", "reprodoctor", *command],
            capture_output=True,
            text=True,
            timeout=20,
            env={"PATH": os.defpath, "LC_ALL": "C"},
        )
        if result.returncode or len(result.stdout.encode()) > 1024 * 1024:
            raise RuntimeError("Read-only diagnosis replay failed")
        diagnosis = json.loads(result.stdout)
        display = "reprodoctor " + " ".join(command).replace(str(ROOT) + "/", "")
        scenes.append(
            {
                "case": case,
                "command": display,
                "output": result.stdout,
                "status": diagnosis["execution_status"],
                "findings": diagnosis["findings"],
            }
        )
    preface = (
        "Read-only replay of actual CLI diagnosis output from genuine manually approved runs.\n"
        "No target command, approval, image pull or Docker call is made by this generator.\n"
        "Entry point shown as reprodoctor; captured via python -I -m reprodoctor.\n"
        "Project paths are normalized. Replay timing is paced, not a screen recording.\n"
        f"Frozen corpus: {summary['executed_cases']} executions, "
        f"{summary['planning_abstentions']} abstentions. "
        "Tiny public sample; no general accuracy claim.\n"
    )
    transcript = (
        preface + "\n" + "\n\n".join("$ " + s["command"] + "\n" + s["output"] for s in scenes)
    )
    (args.output / "transcript.txt").write_text(transcript)
    events = [
        {
            "version": 2,
            "width": 110,
            "height": 35,
            "timestamp": 0,
            "title": "Reproducibility Doctor — genuine evidence, read-only replay",
        },
        [0.0, "o", preface.replace("\n", "\r\n")],
    ]
    for index, scene in enumerate(scenes, 1):
        events.append(
            [
                index * 10.0,
                "o",
                "$ " + scene["command"] + "\r\n" + scene["output"].replace("\n", "\r\n"),
            ]
        )
    (args.output / "demo.cast").write_text("\n".join(json.dumps(e) for e in events) + "\n")
    rows = "".join(
        "<tr>"
        + "".join(
            "<td>" + html.escape(str(value)) + "</td>"
            for value in (
                row["id"],
                row["split"],
                row["observed_status"],
                row.get("cleanup", "not executed"),
                row.get("seconds", "—"),
            )
        )
        + "</tr>"
        for row in summary["results"]
    )
    panels = []
    for scene in scenes:
        cards = []
        for finding in scene["findings"]:
            cards.append(
                '<div class="finding"><strong>'
                + html.escape(finding["kind"])
                + ": "
                + html.escape(finding["category"])
                + "</strong><p>"
                + html.escape(finding["observed_fact"])
                + "</p><p>Next action: "
                + html.escape(finding["suggested_action"])
                + "</p></div>"
            )
        if not cards:
            cards = [
                "<p>No failure findings in this record. This does not certify reproducibility.</p>"
            ]
        panels.append(
            "<section><h2>"
            + html.escape(scene["case"] + " · " + scene["status"])
            + "</h2>"
            + "".join(cards)
            + "<details><summary>Captured CLI JSON</summary><pre>$ "
            + html.escape(scene["command"] + "\n\n" + scene["output"])
            + "</pre></details></section>"
        )
    page = """<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Reproducibility Doctor — evidence demo</title><style>
body{background:#101722;color:#e2eaf5;font:16px/1.6 system-ui;
max-width:1050px;margin:40px auto;padding:20px}
h1{font-size:42px;line-height:1.1}small,a{color:#91d9c3}section,table{margin:24px 0;width:100%}
section,.finding{border:1px solid #39475b;border-radius:12px;padding:18px}.finding{margin:12px 0}
td,th{text-align:left;border-bottom:1px solid #39475b;padding:8px;font-size:14px}
pre{white-space:pre-wrap;overflow-wrap:anywhere;font:12px/1.5 ui-monospace,monospace}
summary{cursor:pointer}
</style><small>LOCAL CLI · PINNED EVIDENCE · REVIEW BEFORE EXECUTION</small>
<h1>Reproducibility Doctor</h1>
<p>What worked, what failed, and what the evidence actually supports.</p>
<p><strong>7 controlled executions · 5 explicit abstentions · 7 confirmed cleanups.</strong>
Expected failed/timed-out states are validation outcomes, not successful project setups.</p>
<p>This replay reads genuine approved records. It runs no target code. The small authored corpus is
public and not blinded; it is not a general GitHub accuracy benchmark. Containers do not make
arbitrary code completely safe. Execution was validated on one Docker Desktop Linux ARM64 setup.</p>
<table><thead><tr><th>Case</th><th>Split</th><th>Observed</th>
<th>Cleanup</th><th>Seconds</th></tr></thead><tbody>"""
    page += rows + "</tbody></table>" + "".join(panels)
    page += (
        '<p><a href="transcript.txt">Captured transcript</a> · '
        '<a href="demo.cast">Paced replay</a></p></html>'
    )
    (args.output / "index.html").write_text(page)
    print("Generated read-only evidence replay; no target or Docker execution.")


if __name__ == "__main__":
    main()
