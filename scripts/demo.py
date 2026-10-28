"""Record a small static-only CLI demo using authored source; no target code runs."""

import argparse
import html
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from evaluate import fixture_repository

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True, help="New demo directory")
    args = parser.parse_args()
    args.output.mkdir()
    fixture = json.loads((ROOT / "evaluation/fixtures/dev-02.json").read_text())
    steps = []
    with tempfile.TemporaryDirectory(prefix="doctor-demo-") as temporary:
        base = Path(temporary)
        fixture_repository(fixture["files"], base / "fixture")
        commands = [
            (
                "Pin source without checkout",
                ["intake", str(base / "fixture"), "--output", str(base / "snapshot")],
            ),
            ("Extract README commands for review", ["extract", str(base / "snapshot")]),
            (
                "Find the absent requirements file",
                ["check", str(base / "snapshot"), "--format", "markdown"],
            ),
            (
                "Build a blocked draft; no image selected",
                ["plan", str(base / "snapshot"), "--output", str(base / "plan.json")],
            ),
            (
                "Preview only; never execute",
                ["run", str(base / "plan.json"), "--snapshot", str(base / "snapshot"), "--dry-run"],
            ),
        ]
        for title, command in commands:
            result = subprocess.run(
                [sys.executable, "-m", "reprodoctor", *command],
                capture_output=True,
                text=True,
                timeout=30,
                env={**os.environ, "NO_COLOR": "1"},
            )
            if result.returncode:
                raise RuntimeError(result.stdout + result.stderr)
            display = "reprodoctor " + " ".join(command)
            output = result.stdout
            display = display.replace(str(base), "$DEMO")
            output = output.replace(str(base), "$DEMO")
            steps.append({"title": title, "command": display, "output": output})
    transcript = [
        "Static-only CLI demo. Actual CLI output; temporary paths normalized to $DEMO.",
        "No fixture commands or containers executed. Plans remain unapproved.",
        "",
    ]
    for step in steps:
        transcript += ["$ " + step["command"], step["output"], ""]
    (args.output / "transcript.txt").write_text("\n".join(transcript))
    # An asciinema v2 recording of the captured output, paced for replay.
    events = [
        {
            "version": 2,
            "width": 110,
            "height": 35,
            "timestamp": 0,
            "title": "Reproducibility Doctor — static CLI demo (normalized paths)",
        }
    ]
    for i, step in enumerate(steps):
        events.append(
            [i * 8.0, "o", "$ " + step["command"] + "\r\n" + step["output"].replace("\n", "\r\n")]
        )
    (args.output / "demo.cast").write_text("\n".join(json.dumps(e) for e in events) + "\n")
    panels = "\n".join(
        "<details"
        + (" open" if i == 2 else "")
        + "><summary>"
        + html.escape(step["title"])
        + "</summary><pre>$ "
        + html.escape(step["command"] + "\n\n" + step["output"])
        + "</pre></details>"
        for i, step in enumerate(steps)
    )
    (args.output / "index.html").write_text(
        """<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Reproducibility Doctor
demo</title>
<style>body{font:17px/1.6
system-ui;background:#101722;color:#e2eaf5;max-width:1000px;margin:50px auto;padding:24px}
h1{font-size:40px;line-height:1.15}small{color:#91d9c3}details{border:1px solid
#39475b;border-radius:12px;margin:18px 0;padding:16px}
summary{cursor:pointer;font-weight:650}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:13px/1.6
ui-monospace,monospace;color:#c6dcf4}
a{color:#91d9c3}</style><small>LOCAL • DETERMINISTIC • REVIEW BEFORE EXECUTION</small>
<h1>Reproducibility Doctor</h1><p>A README references a file that does not exist. Doctor pins
the source,
finds the instruction and reports the evidence.</p><p>This walkthrough contains captured static
CLI output.
Temporary paths are normalized to $DEMO. This walkthrough ran no project commands or containers.
Separate live reference validation is documented in the repository.</p>"""
        + panels
        + '<p><a href="transcript.txt">Full transcript</a> · '
        '<a href="demo.cast">Asciinema recording</a></p></html>'
    )
    print("Recorded static-only demo in " + str(args.output.absolute()))


if __name__ == "__main__":
    main()
