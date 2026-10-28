"""Regression for saved-receipt overwrite and copying the wrong plan's digest."""

import builtins
import importlib.util
import io
import json
from pathlib import Path

import pytest

from reprodoctor.intake import IntakeError, intake
from reprodoctor.planning import approval_record, build_plan, read_document, validate_approval


def load_helper():
    path = Path(__file__).parents[1] / "scripts/resume_approvals.py"
    spec = importlib.util.spec_from_file_location("resume_approval_helper", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Terminal(io.StringIO):
    def isatty(self):
        return True


def test_resume_skips_verified_receipts_and_shows_current_digest(repo, tmp_path, monkeypatch):
    module = load_helper()
    source, _ = repo
    review = tmp_path / "review"
    review.mkdir()
    plans = {}
    for name in ["first", "second"]:
        root = review / name
        root.mkdir()
        intake(str(source), root / "snapshot")
        image_hash = ("1" if name == "first" else "2") * 64
        plan = build_plan(root / "snapshot", image="python@sha256:" + image_hash)
        (root / "plan.json").write_text(json.dumps(plan))
        plans[name] = plan
    # Synthetic unit-test receipt only; no real container approval is created here.
    receipt = review / "first/approval.json"
    receipt.write_text(json.dumps(approval_record(plans["first"], plans["first"]["plan_digest"])))
    before = receipt.read_bytes()
    assert plans["first"]["plan_digest"] != plans["second"]["plan_digest"]
    (review / "preparation.json").write_text(
        json.dumps(
            {"kind": "control_probe_preparation", "cases": [{"id": "first"}, {"id": "second"}]}
        )
    )
    stdout = Terminal()
    calls = []

    def human_input(prompt):
        calls.append(prompt)
        assert "CURRENT PLAN: second" in stdout.getvalue()
        assert plans["second"]["plan_digest"] in stdout.getvalue()
        return plans["second"]["plan_digest"]

    with monkeypatch.context() as patch:
        patch.setattr(module.sys, "stdin", Terminal())
        patch.setattr(module.sys, "stdout", stdout)
        patch.setattr(builtins, "input", human_input)
        assert module.resume(review) == 0
        assert module.resume(review) == 0
    assert len(calls) == 1
    assert receipt.read_bytes() == before
    validate_approval(read_document(review / "second/approval.json"), plans["second"])
    assert "saved approval verified; skipping" in stdout.getvalue()


def test_resume_refuses_piped_confirmation_and_escapes_controls(tmp_path, monkeypatch):
    module = load_helper()
    monkeypatch.setattr(module.sys, "stdin", io.StringIO("a" * 64))
    with pytest.raises(IntakeError, match="interactive terminal"):
        module.resume(tmp_path)
    assert module.terminal_text("\x1b\u202etest") == "\\u001b\\u202etest"
