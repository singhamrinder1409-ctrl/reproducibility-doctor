import hashlib
import html
import json
from pathlib import Path

import pytest

from reprodoctor.checks import Checks, check_snapshot
from reprodoctor.cli import main
from reprodoctor.intake import IntakeError, intake
from reprodoctor.static_report import markdown_report


def analyze(files: dict[str, str | bytes], target="3.12.0") -> list[dict]:
    checks = Checks({p: v.encode() if isinstance(v, str) else v for p, v in files.items()}, target)
    checks.manifest_checks()
    checks.python_checks()
    checks.reference_checks()
    checks.environment_checks()
    return checks.findings


def select(findings, rule, status):
    return [f for f in findings if f["rule_id"] == rule and f["status"] == status]


def test_manifest_absence_is_review_not_missing_dependency():
    findings = analyze({"README.md": "# Example\n"})
    assert select(findings, "dependencies", "review")
    assert not select(findings, "dependencies", "finding")


def test_valid_empty_and_dynamic_dependency_declarations():
    for declaration in ["dependencies=[]", 'dependencies=["requests>=2"]']:
        findings = analyze({"pyproject.toml": "[project]\n" + declaration})
        assert len(select(findings, "dependencies", "pass")) == 2
        assert not select(findings, "dependencies", "finding")
    for declaration in ['dynamic=["dependencies"]', 'name="example"']:
        assert select(
            analyze({"pyproject.toml": "[project]\n" + declaration}), "dependencies", "unknown"
        )


@pytest.mark.parametrize(
    "metadata",
    [
        "[project",
        "project=[]",
        '[project]\ndependencies="requests"',
        '[project]\ndependencies=["not a valid requirement ==="]',
        '[project]\ndynamic="dependencies"',
        '[project]\ndependencies=[]\ndynamic=["dependencies"]',
    ],
)
def test_invalid_manifest_is_direct_observation(metadata):
    findings = analyze({"pyproject.toml": metadata})
    bad = select(findings, "dependencies", "finding")
    assert bad and bad[0]["evidence"][0]["path"] == "pyproject.toml"
    assert all(f["limitation"] and f["suggested_action"] for f in findings)


def test_legacy_manifest_is_not_executed_or_declared_missing():
    findings = analyze({"setup.py": "raise Exception('must never execute')"})
    assert select(findings, "dependencies", "pass")
    assert select(findings, "dependencies", "unknown")
    assert not select(findings, "dependencies", "finding")


def test_requirements_includes_syntax_and_unsupported_options():
    findings = analyze(
        {
            "requirements.txt": "-r requirements/base.txt\n-cconstraints.txt\n",
            "requirements/base.txt": "requests>=2; python_version >= '3.10'\n",
            "constraints.txt": "requests==2.32.0\n",
        }
    )
    assert len(select(findings, "references", "pass")) == 2
    assert not select(findings, "references", "finding")
    unknown = analyze({"requirements.txt": "--index-url https://index.invalid\n-e .\n"})
    assert select(unknown, "dependencies", "unknown")
    assert not select(unknown, "dependencies", "finding")
    bad_include = analyze({"requirements.txt": "-r missing.txt\n"})
    assert select(bad_include, "references", "finding")[0]["evidence"][0]["start_line"] == 1


def test_python_allowed_excluded_and_unknown_are_distinct():
    good = analyze({"pyproject.toml": '[project]\nrequires-python=">=3.12,<3.13"'})
    assert select(good, "python", "pass")
    excluded = analyze({"pyproject.toml": '[project]\nrequires-python="<3.12"'})
    assert select(excluded, "python", "unsupported")
    assert not select(excluded, "python", "finding")
    assert select(analyze({".python-version": "pypy3.10\n"}), "python", "unknown")
    assert select(analyze({}), "python", "unknown")


def test_minor_python_pin_preserves_patch_range():
    findings = analyze(
        {
            "pyproject.toml": '[project]\nrequires-python=">=3.12.1,<3.13"',
            ".python-version": "3.12\n",
        },
        target="3.12.2",
    )
    assert select(findings, "consistency", "pass")
    assert not select(findings, "consistency", "finding")


def test_explicit_readme_config_contradiction_has_two_evidence_locations():
    findings = analyze(
        {
            "README.md": "# Example\n\nPython: 3.11\n",
            "pyproject.toml": '[project]\nrequires-python=">=3.12"',
        }
    )
    (mismatch,) = select(findings, "consistency", "finding")
    assert {e["path"] for e in mismatch["evidence"]} == {"README.md", "pyproject.toml"}
    assert mismatch["evidence"][1]["start_line"] == 3
    assert "no overlap" in mismatch["observed_fact"]


def test_python_prose_code_html_and_dynamic_are_not_guessed():
    readme = (
        "Requires Python 3.10 or later.\n\n```text\nPython: 3.9\n```\n\n<!--\nPython: 3.8\n-->\n"
    )
    findings = analyze(
        {"README.md": readme, "pyproject.toml": '[project]\ndynamic=["requires-python"]'}
    )
    assert not select(findings, "python", "pass")
    assert select(findings, "consistency", "unknown")


@pytest.mark.parametrize(
    "declaration,status",
    [('"nonsense"', "finding"), ("123", "finding"), ('"===custom"', "unknown")],
)
def test_python_invalid_and_unsupported_constraints(declaration, status):
    findings = analyze({"pyproject.toml": "[project]\nrequires-python=" + declaration})
    assert select(findings, "python", status)


def test_no_dependency_presence_guarantees_runtime_success():
    findings = analyze({"requirements.txt": "package-that-is-not-queried==9.9\n"})
    assert select(findings, "dependencies", "pass")
    assert not select(findings, "dependencies", "finding")
    assert "availability" in select(findings, "dependencies", "pass")[0]["limitation"]


def test_literal_paths_ordered_cwd_and_missing_file():
    findings = analyze(
        {
            "README.md": "```sh\ncd app\npip install -r requirements.txt\npython missing.py\n```\n",
            "app/requirements.txt": "",
        }
    )
    assert len(select(findings, "references", "pass")) == 2
    (missing,) = select(findings, "references", "finding")
    assert "app/missing.py" in missing["observed_fact"]
    assert missing["evidence"][0]["start_line"] == 4
    assert missing["evidence"][1]["sha256"] is None


def test_generated_copy_target_is_review_not_confirmed_missing_input():
    findings = analyze(
        {
            "README.md": "```sh\ncp template.py generated.py\npython generated.py\n```\n",
            "template.py": "print('example')",
        }
    )
    assert select(findings, "references", "review")
    assert not select(findings, "references", "finding")


@pytest.mark.parametrize(
    "command",
    [
        "cd $PROJECT",
        "cd ../outside",
        "git clone https://example.invalid/project",
        "pip install . && cd anywhere",
    ],
)
def test_unknown_or_escaping_cwd_cannot_create_confident_missing_file(command):
    findings = analyze({"README.md": f"```sh\n{command}\npython main.py\n```\n"})
    assert not select(findings, "references", "finding")
    assert select(findings, "references", "unknown")


def test_requirements_reference_cannot_read_host_file(tmp_path):
    secret = tmp_path / "secret"
    secret.write_text("HOST_SECRET_DO_NOT_COPY")
    findings = analyze({"requirements.txt": f"-r {secret}\n-r ../../outside.txt\n"})
    assert select(findings, "references", "unknown")
    assert select(findings, "references", "review")
    assert "HOST_SECRET_DO_NOT_COPY" not in json.dumps(findings)


def test_environment_names_matched_defaults_unknown_and_values_omitted():
    findings = analyze(
        {
            "README.md": "```sh\nexport API_KEY=README_SECRET\n```\n",
            ".env.example": "API_KEY=EXAMPLE_SECRET\n",
            "app.py": "import os\nx=os.environ['API_KEY']\n"
            "y=os.getenv('OPTIONAL', 'SOURCE_SECRET')\nz=os.environ.get('THIRD')\n",
        }
    )
    assert len(select(findings, "environment", "pass")) == 2
    assert len(select(findings, "environment", "review")) == 2
    assert select(findings, "environment", "unknown")
    encoded = json.dumps(findings)
    for secret in ("README_SECRET", "EXAMPLE_SECRET", "SOURCE_SECRET"):
        assert secret not in encoded
    assert not select(findings, "environment", "finding")


def test_environment_dynamic_alias_syntax_and_budget_abstentions():
    findings = analyze(
        {
            "app.py": "import os as other\nx=other.getenv('ALIAS')\n"
            "y=os.getenv(prefix+'DYNAMIC')\n",
            "bad.py": "syntax error ???",
            "large.py": "#" * (128 * 1024 + 1),
        }
    )
    assert not select(findings, "environment", "review")
    assert len(select(findings, "environment", "unknown")) == 3


def test_evidence_line_numbers_use_physical_lines():
    findings = analyze({"README.md": "Title\u2028same line\r\nPython: 3.11\r\n"})
    assert select(findings, "python", "unsupported")[0]["evidence"][0]["start_line"] == 2


def test_full_reports_deterministic_cli_formats_and_no_project_execution(repo, tmp_path, capsys):
    root, git = repo
    marker = tmp_path / "must-not-exist"
    (root / "README.md").write_text("Python: 3.11\n\n```sh\npython missing.py\n```\n")
    (root / "pyproject.toml").write_text('[project]\nrequires-python=">=3.12"\ndependencies=[]\n')
    (root / "setup.py").write_text(f"open({str(marker)!r}, 'w').write('bad')")
    git("add", ".")
    git("commit", "-m", "authored static fixture")
    snapshot = tmp_path / "snapshot"
    intake(str(root), snapshot)
    first = check_snapshot(snapshot)
    assert first == check_snapshot(snapshot)
    assert first["execution_status"] == "not_run" and not first["execution_permitted"]
    assert first["summary"]["finding"] >= 2
    assert not marker.exists()
    for format_ in ("json", "markdown"):
        output = tmp_path / ("report." + format_)
        assert main(["check", str(snapshot), "--format", format_, "--output", str(output)]) == 0
        content = output.read_text()
        if format_ == "json":
            assert json.loads(content) == first
        else:
            assert content == markdown_report(first)
            assert "Execution: **not run**" in content
            assert all(
                f["id"] in content and f["observed_fact"] in html.unescape(content)
                for f in first["findings"]
            )
        assert main(["check", str(snapshot), "--output", str(output)]) == 2
    assert main(["check", str(snapshot), "--output", str(snapshot / "report.json")]) == 2
    assert main(["check", str(snapshot), "--python-version", "3.12"]) == 2
    capsys.readouterr()
    assert main(["check", str(snapshot)]) == 0
    assert json.loads(capsys.readouterr().out) == first
    target = snapshot / "files/README.md"
    target.chmod(0o644)
    target.write_text("tampered")
    with pytest.raises(IntakeError):
        check_snapshot(snapshot)


def test_markdown_escapes_html_links_and_terminal_controls():
    report = {
        "repository": {"commit": "abc", "content_digest": "def"},
        "target_python": "3.12.0",
        "tool_version": "test",
        "summary": {},
        "limitations": [],
        "findings": [
            {
                "id": "f",
                "rule_id": "references",
                "status": "review",
                "observed_fact": "<script>alert(1)</script> [click](https://evil.invalid)\x1b[31m",
                "suggested_action": "review",
                "limitation": "unknown",
                "evidence": [],
            }
        ],
    }
    content = markdown_report(report)
    assert "<script>" not in content and "[click]" not in content and "\x1b" not in content


def test_reserved_evaluation_is_still_unchanged():
    root = Path(__file__).parents[1]
    spec = (root / "evaluation/scenarios.json").read_bytes()
    assert (
        hashlib.sha256(spec).hexdigest()
        == (root / "evaluation/reservation.sha256").read_text().split()[0]
    )
