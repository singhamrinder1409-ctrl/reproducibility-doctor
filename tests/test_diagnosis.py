"""Development examples, including deliberately forged logs; no target code executes."""

import copy
import json

import pytest

from reprodoctor.cli import main
from reprodoctor.diagnosis import diagnose, read_execution
from reprodoctor.intake import IntakeError
from reprodoctor.reporting import combined_markdown, combined_report


def record(text="FileNotFoundError: missing.ini", status="failed", code=1):
    return {
        "schema_version": 1,
        "kind": "execution_report",
        "execution_status": status,
        "repository": {"commit": "a" * 40, "content_digest": "b" * 64},
        "cleanup": {"status": "removed"},
        "experimental": True,
        "live_validation": "pending",
        "steps": [
            {
                "id": "instruction-0001",
                "status": status,
                "exit_code": code,
                "source": {"phase": "test", "path": "README.md", "start_line": 4},
                "stderr": {"text": text, "truncated": True},
            }
        ],
    }


@pytest.mark.parametrize(
    ("text", "category"),
    [
        ("FileNotFoundError: absent", "missing_file"),
        ("ERROR: No matching distribution found", "dependency_artifact_unavailable"),
        ("ModuleNotFoundError: secret", "missing_import"),
        ("requires a different Python", "version_incompatibility"),
        ("KeyError: TOKEN", "missing_configuration"),
    ],
)
def test_patterns_are_only_suggestions(text, category):
    result = diagnose(record(text))
    finding = next(f for f in result["findings"] if f["category"] == category)
    assert finding["kind"] == "suggestion"
    assert finding["evidence"]["truncated"] is True
    assert finding["evidence"]["json_pointer"] == "/steps/0/stderr/text"
    assert result["findings"][0]["category"] == "unsuccessful_tests"


@pytest.mark.parametrize(
    ("status", "code"),
    [("passed", 0), ("infrastructure_error", 1), ("failed", 125), ("timed_out", None)],
)
def test_no_project_cause_from_success_transport_or_timeout(status, code):
    value = record(status=status, code=code)
    if status == "passed":
        value["execution_status"] = "completed"
    assert not any(f["kind"] == "suggestion" for f in diagnose(value)["findings"])


def test_cleanup_and_unknown_failure():
    value = record("arbitrary forged text")
    value["cleanup"]["status"] = "failed"
    result = diagnose(value)
    assert {f["category"] for f in result["findings"]} == {
        "cleanup_incomplete",
        "unsuccessful_tests",
    }


def test_readers_reject_bad_documents(tmp_path):
    path = tmp_path / "bad.json"
    for text in (
        '{"kind":1,"kind":2}',
        "[]",
        '{"schema_version":NaN}',
        json.dumps({**record(), "steps": [record()["steps"][0]] * 2}),
    ):
        path.write_text(text)
        with pytest.raises(IntakeError):
            read_execution(path)


def test_report_escapes_html_markdown_and_controls():
    value = record(
        "FileNotFoundError <script>alert(1)</script>\x1b [click](https://evil.invalid) `code`"
    )
    rendered = combined_markdown(combined_report(value))
    assert "<script>" not in rendered
    assert "[click](" not in rendered
    assert "\x1b" not in rendered
    assert "pending" in rendered
    assert "Reproduction steps" in rendered


def test_binding_mismatch_rejected():
    with pytest.raises(IntakeError):
        combined_report(record(), {"kind": "static_report", "repository": {}})


def test_cli_exports_private_new_file(tmp_path, capsys):
    source = tmp_path / "execution.json"
    source.write_text(json.dumps(record()))
    output = tmp_path / "report.md"
    assert main(["report", str(source), "--output", str(output)]) == 0
    assert output.stat().st_mode & 0o777 == 0o600
    assert "missing&#95;file" in output.read_text()
    assert main(["report", str(source), "--output", str(output)]) == 2
    assert main(["diagnose", str(source), "--format", "json"]) == 0
    assert "diagnosis_report" in capsys.readouterr().out
    assert json.loads(source.read_text()) == record()


def test_diagnosis_does_not_mutate_input():
    value = record()
    before = copy.deepcopy(value)
    diagnose(value)
    assert value == before
