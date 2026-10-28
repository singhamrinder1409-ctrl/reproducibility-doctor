"""Host-signaling/live mutation harnesses require explicit opt-in and enabled assertions."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.mark.parametrize(
    ("script", "flag"),
    [
        ("validate_live_signals.py", "execute_approved"),
        ("validate_live_mutations.py", "execute_approved_tests"),
    ],
)
def test_live_harness_refuses_before_reading_inputs_without_optin(script, flag, monkeypatch):
    path = Path(__file__).parents[1] / "scripts" / script
    spec = importlib.util.spec_from_file_location("guarded_experiment", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    def forbidden(*args, **kwargs):
        raise AssertionError("Inputs or backend touched before opt-in guard")

    monkeypatch.setattr(module, "read_document", forbidden)
    with pytest.raises(ValueError, match="Explicit"):
        module.validate(SimpleNamespace(**{flag: False}))
    monkeypatch.setattr(module, "sys", SimpleNamespace(flags=SimpleNamespace(optimize=1)))
    with pytest.raises(ValueError, match="without Python -O"):
        module.validate(SimpleNamespace(**{flag: True}))
