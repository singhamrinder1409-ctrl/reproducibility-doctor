"""Fixture preparation must never execute target code or manufacture approval."""

import importlib.util
import json
from pathlib import Path

import pytest


def test_preparation_is_review_only(tmp_path, monkeypatch):
    scripts = Path(__file__).parents[1] / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location(
        "live_preparation", scripts / "prepare_live_validation.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    original = module.fixture_repository.__globals__["subprocess"].run
    calls = []

    def git_only(argv, **kwargs):
        assert argv[0] == "git", "Target commands must not run during preparation"
        calls.append(argv)
        return original(argv, **kwargs)

    monkeypatch.setattr(module.fixture_repository.__globals__["subprocess"], "run", git_only)
    output = tmp_path / "kit"
    result = module.prepare(output)
    assert result["execution_status"] == "not_run"
    assert result["approval_created"] is False
    assert calls
    for case in result["cases"]:
        root = output / case["id"]
        plan = json.loads((root / "plan.json").read_text())
        assert plan["payload"]["blockers"]
        assert not list(root.glob("*approval*"))
        assert not list(root.glob("*report*"))
        assert (root / "snapshot/snapshot.json").exists()
    with pytest.raises(FileExistsError):
        module.prepare(output)
