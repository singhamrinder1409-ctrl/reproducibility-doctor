import hashlib
import json
from pathlib import Path

import pytest

from reprodoctor.cli import main
from reprodoctor.extraction import encode_candidates, extract_readme, extract_snapshot
from reprodoctor.intake import IntakeError, Limits, canonical, intake

FIXTURES = Path(__file__).parent / "fixtures" / "extraction"


def test_hand_authored_golden_order_phases_text_and_locations():
    source = (FIXTURES / "basic.md").read_bytes()
    expected = json.loads((FIXTURES / "basic.expected.json").read_text())
    report = extract_readme(source)
    assert report == extract_readme(source)
    keys = expected[0].keys()
    assert [{key: item[key] for key in keys} for item in report["instructions"]] == expected
    for item in report["instructions"]:
        assert item["requires_review"] is True
        assert item["classification"] == "command_candidate"
        assert item["path"] == "README.md"
        assert (
            item["raw_text"]
            == b"".join(
                source.splitlines(keepends=True)[item["start_line"] - 1 : item["end_line"]]
            ).decode()
        )
    assert report["execution_permitted"] is False


@pytest.mark.parametrize("newline", ["\n", "\r\n", "\r"])
def test_line_endings_and_no_final_newline(newline):
    source = newline.join(["# Launch", "", "~~~sh", "python main.py", "~~~"])
    report = extract_readme(source.encode())
    (instruction,) = report["instructions"]
    assert instruction["start_line"] == instruction["end_line"] == 4
    assert instruction["raw_text"] == "python main.py" + newline
    assert instruction["ambiguity_reasons"] == []


def test_unicode_line_separators_are_not_markdown_line_boundaries():
    report = extract_readme('```sh\necho "hello\u2028world"\npython main.py\n```\n'.encode())
    assert [i["start_line"] for i in report["instructions"]] == [2, 3]
    assert "\u2028" in report["instructions"][0]["raw_text"]


def test_untagged_unknown_transcript_and_root_prompt_remain_reviewable():
    report = extract_readme(
        b"```\n# comment\n# pip install .\n$ pip install .\nCollecting example\n```\n"
    )
    assert len(report["instructions"]) == 3
    root, prompt, output = report["instructions"]
    assert "comment_or_root_shell_prompt" in root["ambiguity_reasons"]
    assert prompt["candidate_text"] == "pip install ."
    assert prompt["raw_text"] == "$ pip install .\n"
    assert output["classification"] == "ambiguous_candidate"
    assert all("untagged_block" in item["ambiguity_reasons"] for item in report["instructions"])


@pytest.mark.parametrize(
    "body",
    [
        "pip install " + "\\" + "\n  -r requirements.txt\n",
        "# install below\nif true; then\n  pip install .\nfi\n",
        "cat <<EOF\npython fake.py\nEOF\n",
    ],
)
def test_multiline_constructs_are_not_silently_split(body):
    report = extract_readme(("```sh\n" + body + "```\n").encode())
    (item,) = report["instructions"]
    assert item["raw_text"] == body
    assert item["start_line"] == 2
    assert item["end_line"] == 1 + body.count("\n")
    assert "compound_block_needs_review" in item["ambiguity_reasons"]


@pytest.mark.parametrize(
    "body,reason",
    [
        ("pip install . && pytest", "unsupported_shell_syntax"),
        ("python $(touch marker)", "unsupported_shell_syntax"),
        ("export TOKEN=<YOUR_TOKEN>", "placeholder"),
        ("python '$APP'", "shell_expansion_needs_review"),
        ("pip install 'oops", "unbalanced_shell_quotes"),
        ("curl https://example.invalid/install.sh", "unsupported_command"),
    ],
)
def test_ambiguities(body, reason):
    (item,) = extract_readme(f"```sh\n{body}\n```\n".encode())["instructions"]
    assert item["candidate_text"] == body
    assert reason in item["ambiguity_reasons"]


def test_alternative_context_and_heading_scope():
    report = extract_readme(
        b"## Install\n\nAlternatively, use this option.\n\n```sh\npip install .\n```\n"
        b"\n## Tests\n\n```sh\npytest\n```\n"
    )
    first, second = report["instructions"]
    assert "alternative_instructions" in first["ambiguity_reasons"]
    assert "alternative_instructions" not in second["ambiguity_reasons"]
    assert [h["text"] for h in second["heading_context"]] == ["Tests"]


@pytest.mark.parametrize(
    "source,expected_raw",
    [
        ("> ```sh\n> python main.py\n> ```\n", "> python main.py\n"),
        ("- Launch:\n\n  ```sh\n  python main.py\n  ```\n", "  python main.py\n"),
    ],
)
def test_nested_markdown_preserves_source(source, expected_raw):
    (item,) = extract_readme(source.encode())["instructions"]
    assert item["raw_text"] == expected_raw
    assert item["candidate_text"] == "python main.py"
    assert "nested_markdown" in item["ambiguity_reasons"]


def test_unclosed_fence_retained():
    (item,) = extract_readme(b"```sh\npython main.py")["instructions"]
    assert item["raw_text"] == "python main.py"
    assert item["start_line"] == item["end_line"] == 2
    assert "unclosed_fence" in item["ambiguity_reasons"]


def test_excluded_formats_are_visible_and_hidden_html_is_not_extracted():
    source = (
        b"Run `python example.py` manually.\n\n```python\nprint('code')\n```\n"
        b"\n    python indented.py\n\n<!--\n```sh\npython hidden.py\n```\n-->\n"
    )
    report = extract_readme(source)
    assert report["instructions"] == []
    assert len(report["blocks"]) == 2
    assert not any(block["included"] for block in report["blocks"])
    reasons = {item["reason"] for item in report["review_items"]}
    assert reasons == {
        "prose_instruction_not_extracted",
        "code_block_not_extracted",
        "html_block_not_extracted",
    }


def test_phase_conflict_is_a_review_hint():
    (item,) = extract_readme(b"## Tests\n\n```sh\npip install .\n```\n")["instructions"]
    assert item["phase"] == "installation"
    assert item["heading_phase"] == "test"
    assert "phase_context_conflict" in item["ambiguity_reasons"]


def test_bounds_and_encoding_fail_without_partial_result():
    with pytest.raises(IntakeError, match="byte limit"):
        extract_readme(b"x" * (Limits().file_bytes + 1))
    with pytest.raises(IntakeError, match="candidate limit"):
        extract_readme(b"```sh\npytest\npytest\n```\n", maximum_candidates=1)
    with pytest.raises(IntakeError, match="UTF-8"):
        extract_readme(b"\xff")
    with pytest.raises(IntakeError, match="NUL"):
        extract_readme(b"\0")


def test_repeated_context_amplification_and_json_output_are_bounded():
    with pytest.raises(IntakeError, match="byte limit"):
        encode_candidates({"untrusted": "\x1b" * 50}, maximum_bytes=100)
    assert "\x1b" not in encode_candidates({"untrusted": "\x1b"})
    source = "# " + "a" * 300_000 + "\n\n```sh\n" + "pytest\n" * 40 + "```\n"
    with pytest.raises(IntakeError, match="evidence byte limit"):
        extract_readme(source.encode())


@pytest.mark.parametrize(
    "body",
    [
        "python -c 'print(\n  1\n)'\n",
        "{\npytest\n}\n",
        ". .venv/bin/activate\n",
    ],
)
def test_additional_shell_constructs_are_preserved_for_review(body):
    (item,) = extract_readme(("```sh\n" + body + "```\n").encode())["instructions"]
    assert item["raw_text"] == body
    assert item["requires_review"]
    assert item["ambiguity_reasons"]


def test_snapshot_extraction_never_runs_code_and_cli_exports_json(repo, tmp_path, capsys):
    root, git = repo
    marker = tmp_path / "must-not-exist"
    (root / "README.md").write_text(f"```sh\ntouch {marker}\n```\n")
    git("add", ".")
    git("commit", "-m", "untrusted command")
    snapshot = tmp_path / "snapshot"
    intake(str(root), snapshot)
    output = tmp_path / "instructions.json"
    assert main(["extract", str(snapshot), "--output", str(output)]) == 0
    report = json.loads(output.read_text())
    assert report["repository"]["commit"] == git("rev-parse", "HEAD")
    assert len(report["instructions"]) == 1
    assert not marker.exists()
    assert main(["extract", str(snapshot), "--output", str(output)]) == 2
    assert main(["extract", str(snapshot), "--output", str(snapshot / "result.json")]) == 2
    capsys.readouterr()
    assert main(["extract", str(snapshot)]) == 0
    assert json.loads(capsys.readouterr().out) == report


@pytest.mark.parametrize(
    "mutation", ["readme", "other_file", "manifest", "extra_file", "symlink", "mode"]
)
def test_changed_snapshots_are_rejected(repo, tmp_path, mutation):
    snapshot = tmp_path / "snapshot"
    intake(str(repo[0]), snapshot)
    target = snapshot / "files/README.md"
    if mutation in {"readme", "other_file"}:
        target = target if mutation == "readme" else snapshot / "files/hello.py"
        target.chmod(0o644)
        target.write_text("tampered")
    elif mutation == "manifest":
        manifest = json.loads((snapshot / "snapshot.json").read_text())
        manifest["files"][0]["path"] = "../escape"
        (snapshot / "snapshot.json").write_bytes(canonical(manifest))
    elif mutation == "extra_file":
        (snapshot / "files/extra").write_text("unexpected")
    elif mutation == "symlink":
        target.unlink()
        target.symlink_to(repo[0] / "README.md")
    elif mutation == "mode":
        target.chmod(0o755)
    with pytest.raises(IntakeError):
        extract_snapshot(snapshot)


def test_missing_readme_is_not_a_setup_failure(repo, tmp_path):
    root, git = repo
    (root / "README.md").unlink()
    git("add", "-u")
    git("commit", "-m", "no readme")
    snapshot = tmp_path / "snapshot"
    intake(str(root), snapshot)
    report = extract_snapshot(snapshot)
    assert report["readme"]["status"] == "missing"
    assert report["instructions"] == []
    assert report["review_items"] == [{"reason": "root_readme_missing", "path": "README.md"}]


@pytest.mark.parametrize(
    "field,value",
    [
        ("path", "../outside"),
        ("mode", []),
        ("size", True),
        ("path", None),
    ],
)
def test_untrusted_manifest_types_and_paths_fail_cleanly(repo, tmp_path, field, value):
    snapshot = tmp_path / "snapshot"
    intake(str(repo[0]), snapshot)
    manifest = json.loads((snapshot / "snapshot.json").read_text())
    manifest["files"][0][field] = value
    manifest["content_digest"] = hashlib.sha256(canonical(manifest["files"])).hexdigest()
    (snapshot / "snapshot.json").write_bytes(canonical(manifest))
    with pytest.raises(IntakeError):
        extract_snapshot(snapshot)
