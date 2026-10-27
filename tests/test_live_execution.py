"""Never auto-generates approval. Disabled unless explicitly invoked with reviewed inputs."""

from pathlib import Path

import pytest

from reprodoctor.execution import execute_plan
from reprodoctor.planning import read_document


def test_explicitly_approved_live_smoke(request, tmp_path):
    if not request.config.getoption("--live-container"):
        pytest.skip(
            "Live container validation pending; requires --live-container and reviewed inputs"
        )
    paths = {
        name: request.config.getoption("--live-" + name)
        for name in ("plan", "snapshot", "approval", "wheelhouse")
    }
    if not all(paths[name] for name in ("plan", "snapshot", "approval")):
        pytest.fail(
            "Supply --live-plan, --live-snapshot and --live-approval; no approval is generated"
        )
    report = execute_plan(
        read_document(Path(paths["plan"])),
        read_document(Path(paths["approval"])),
        Path(paths["snapshot"]),
        tmp_path / "live-report.json",
        wheelhouse=Path(paths["wheelhouse"]) if paths["wheelhouse"] else None,
        socket=request.config.getoption("--live-docker-socket"),
        experimental=True,
    )
    assert report["preflight"].get("status") == "verified_for_this_run", report.get("error")
    assert report["execution_status"] == "completed", report
    assert report["cleanup"]["status"] == "removed", report["cleanup"]
