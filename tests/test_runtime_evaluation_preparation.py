"""Materialize frozen cases without Docker, target imports, execution or fake approvals."""

import importlib.util
import json
from pathlib import Path

import pytest


def test_reserved_runtime_preparation_and_label_tamper_guard(tmp_path, monkeypatch):
    scripts = Path(__file__).parents[1] / "scripts"
    monkeypatch.syspath_prepend(str(scripts))

    def load(name, path):
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    builder = load("authored_wheel_builder", scripts / "prepare_live_lifecycle.py")
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    wheelhouse = builder.authored_wheel(artifacts)
    module = load("reserved_runtime_harness", scripts / "evaluate_runtime.py")
    original = module.fixture_repository.__globals__["subprocess"].run

    def git_only(argv, **kwargs):
        assert argv[0] == "git", "Fixture commands must not run during preparation"
        return original(argv, **kwargs)

    def forbidden(*args, **kwargs):
        raise AssertionError("Backend or target touched before approval")

    monkeypatch.setattr(module.fixture_repository.__globals__["subprocess"], "run", git_only)
    monkeypatch.setattr(module, "execute_plan", forbidden)
    frozen = module.fingerprint()
    review = tmp_path / "review"
    result = module.prepare(
        review,
        image="python@sha256:" + "1" * 64,
        platform_name="linux/arm64",
        wheelhouse=wheelhouse,
        frozen=frozen,
    )
    assert len(result["cases"]) == 12
    assert sum(case["eligible"] for case in result["cases"]) == 7
    assert result["execution_status"] == "not_run" and not result["approval_created"]
    assert not list(review.rglob("approval.json")) and not (review / "results").exists()
    result["cases"][0]["expected"]["expected_status"] = "failed"
    (review / "preparation.json").write_text(json.dumps(result))
    with pytest.raises(ValueError, match="labels changed"):
        module.run(review, socket="/never.sock", frozen=frozen)
    assert not (review / "results").exists()
