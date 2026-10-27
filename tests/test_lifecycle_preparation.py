"""Preparation only: never run wait, wheel-install or path-escape target commands here."""

import ast
import base64
import csv
import hashlib
import importlib.util
import io
import json
import zipfile
from pathlib import Path


def load_preparer(monkeypatch):
    scripts = Path(__file__).parents[1] / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location(
        "lifecycle_preparation", scripts / "prepare_live_lifecycle.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_lifecycle_preparation_keeps_approval_manual(tmp_path, monkeypatch):
    module = load_preparer(monkeypatch)
    original = module.fixture_repository.__globals__["subprocess"].run

    def git_only(argv, **kwargs):
        assert argv[0] == "git", "Lifecycle fixture commands must never run on the host"
        return original(argv, **kwargs)

    monkeypatch.setattr(module.fixture_repository.__globals__["subprocess"], "run", git_only)
    result = module.prepare(
        tmp_path / "review", image="python@sha256:" + "1" * 64, platform="linux/arm64"
    )
    assert not result["approval_created"] and result["execution_status"] == "not_run"
    assert len(result["cases"]) == 4
    for case in result["cases"]:
        root = tmp_path / "review" / case["id"]
        plan = json.loads((root / "plan.json").read_text())
        assert plan["payload"]["state"] == "needs_approval"
        assert not (root / "approval.json").exists()
        assert not list(root.glob("*report*"))
        for path in (root / "source").glob("*.py"):
            ast.parse(path.read_text())
    root = tmp_path / "review/offline-wheel"
    plan = json.loads((root / "plan.json").read_text())
    assert len(plan["payload"]["artifacts"]["files"]) == 1
    assert "--no-index" in plan["payload"]["steps"][0]["effective"]["argv"]


def test_authored_wheel_records_match_bytes_and_repeat(tmp_path, monkeypatch):
    module = load_preparer(monkeypatch)
    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir()
    second.mkdir()
    wheel = next(module.authored_wheel(first).glob("*.whl"))
    repeat = next(module.authored_wheel(second).glob("*.whl"))
    assert wheel.read_bytes() == repeat.read_bytes()
    with zipfile.ZipFile(wheel) as archive:
        rows = csv.reader(
            io.StringIO(archive.read("doctor_validation_fixture-0.0.0.dist-info/RECORD").decode())
        )
        for name, digest, size in rows:
            if not digest:
                assert name.endswith("/RECORD") and size == ""
                continue
            data = archive.read(name)
            encoded = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
            assert digest == "sha256=" + encoded and int(size) == len(data)
        ast.parse(archive.read("doctor_validation_fixture.py"))
