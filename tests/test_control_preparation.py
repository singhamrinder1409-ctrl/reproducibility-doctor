"""Preparation/syntax tests only: never run the actual network/resource/log fixtures here."""

import ast
import importlib.util
import json
from pathlib import Path

import pytest


def load_preparer(monkeypatch):
    scripts = Path(__file__).parents[1] / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location(
        "control_preparation", scripts / "prepare_live_controls.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_controls_only_prepare_unapproved_plans(tmp_path, monkeypatch):
    module = load_preparer(monkeypatch)
    original = module.fixture_repository.__globals__["subprocess"].run

    def git_only(argv, **kwargs):
        assert argv[0] == "git", "Target probe must not run during preparation"
        return original(argv, **kwargs)

    monkeypatch.setattr(module.fixture_repository.__globals__["subprocess"], "run", git_only)
    result = module.prepare(
        tmp_path / "review", image="python@sha256:" + "1" * 64, platform="linux/arm64"
    )
    sentinel = Path(result["host_sentinel"])
    try:
        assert result["execution_status"] == "not_run" and not result["approval_created"]
        assert sentinel.stat().st_mode & 0o777 == 0o600
        assert {case["id"] for case in result["cases"]} == {"network", "resources", "logs"}
        for case in result["cases"]:
            base = tmp_path / "review" / case["id"]
            plan = json.loads((base / "plan.json").read_text())
            assert not plan["payload"]["blockers"]
            assert plan["payload"]["state"] == "needs_approval"
            assert not (base / "approval.json").exists()
            for path in (base / "source").glob("*.py"):
                ast.parse(path.read_text())
        config = json.loads((tmp_path / "review/network/source/sentinel.json").read_text())
        assert config["host_only_path"] == str(sentinel)
        assert not (tmp_path / "review/network/source" / sentinel.name).exists()
    finally:
        sentinel.unlink()
    with pytest.raises(FileExistsError):
        module.prepare(
            tmp_path / "review", image="python@sha256:" + "1" * 64, platform="linux/arm64"
        )


def test_controls_reject_output_inside_checkout(monkeypatch):
    module = load_preparer(monkeypatch)
    with pytest.raises(ValueError, match="outside"):
        module.prepare(module.ROOT / "never-create", image="unused", platform="linux/arm64")
