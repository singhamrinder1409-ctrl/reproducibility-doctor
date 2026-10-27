"""Regenerate authored static reports; never execute the fixture's project code."""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from reprodoctor.checks import check_snapshot
from reprodoctor.extraction import encode_candidates
from reprodoctor.intake import intake
from reprodoctor.static_report import markdown_report


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    source = root / "examples/static-fixture"
    with tempfile.TemporaryDirectory(prefix="doctor-static-demo-") as temporary:
        home = Path(temporary)
        repo = home / "fixture"
        shutil.copytree(source, repo)
        env = {
            "PATH": os.defpath,
            "HOME": str(home),
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": "Doctor Fixture",
            "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
            "GIT_COMMITTER_NAME": "Doctor Fixture",
            "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
            "GIT_AUTHOR_DATE": "2000-01-01T00:00:00+00:00",
            "GIT_COMMITTER_DATE": "2000-01-01T00:00:00+00:00",
        }
        for args in [
            ["init", "--template=", "--object-format=sha1", "--initial-branch=main"],
            ["add", "."],
            ["commit", "-m", "Authored static report fixture"],
        ]:
            subprocess.run(
                ["git", "-C", str(repo), "-c", "core.hooksPath=/dev/null", *args],
                env=env,
                check=True,
                capture_output=True,
            )
        snapshot = home / "snapshot"
        intake(str(repo), snapshot)
        report = check_snapshot(snapshot)
        (root / "examples/static-report.json").write_text(
            encode_candidates(report), encoding="utf-8"
        )
        (root / "examples/static-report.md").write_text(markdown_report(report), encoding="utf-8")
        print(
            "Wrote examples/static-report.json and examples/static-report.md; fixture code not run."
        )


if __name__ == "__main__":
    main()
