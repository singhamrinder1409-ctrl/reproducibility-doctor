import copy
import json
import socket
import subprocess
import sys

import pytest

from reprodoctor.cli import main
from reprodoctor.extraction import encode_candidates
from reprodoctor.intake import IntakeError, intake
from reprodoctor.planning import (
    approval_record,
    build_plan,
    digest,
    dry_run,
    read_document,
    validate_approval,
    validate_plan,
)

IMAGE = "python:3.12-slim@sha256:" + "1" * 64  # Format fixture; never pulled or verified.


@pytest.fixture
def snapshot(repo, tmp_path):
    output = tmp_path / "snapshot"
    intake(str(repo[0]), output)
    return output


def changed_snapshot(repo, tmp_path, readme):
    root, git = repo
    (root / "README.md").write_text(readme)
    git("add", ".")
    git("commit", "-m", "authored plan fixture")
    output = tmp_path / "custom-snapshot"
    intake(str(root), output)
    return output


def test_deterministic_plan_preserves_all_provenance_and_fixed_settings(snapshot):
    plan = build_plan(snapshot, image=IMAGE)
    assert plan == build_plan(snapshot, image=IMAGE)
    assert validate_plan(plan, snapshot) == plan
    payload = plan["payload"]
    assert payload["state"] == "needs_approval" and payload["executor_available"]
    assert payload["execution_mode"] == "experimental_live_validation_pending"
    (step,) = payload["steps"]
    assert step["instruction"]["raw_text"] == "python hello.py\n"
    assert step["instruction"]["start_line"] == 4
    assert step["effective"]["argv"] == ["python", "hello.py"]
    container = payload["container"]
    assert container["network"] == "none" and not container["host_mounts"]
    assert not container["inherit_host_environment"] and not container["privileged"]
    assert container["root_filesystem"] == "read_only"
    assert container["cap_drop"] == ["ALL"] and container["no_new_privileges"]
    assert container["limits"]["run_seconds"] == 600
    assert container["limits"]["step_seconds"] == 120
    assert container["limits"]["memory_bytes"] == 1024**3
    assert container["user"] == "65532:65532"
    assert plan["plan_digest"] == digest(payload)


def test_missing_image_is_visible_draft_not_silent_default(snapshot):
    plan = build_plan(snapshot)
    assert plan["payload"]["state"] == "blocked"
    assert plan["payload"]["container"]["image"] is None
    with pytest.raises(IntakeError, match="Blocked"):
        approval_record(plan, plan["plan_digest"])
    assert dry_run(plan, snapshot)["plan_state"] == "blocked"


@pytest.mark.parametrize(
    "image", ["python:latest", "-danger@sha256:" + "a" * 64, [], "python@sha256:" + "1" * 63]
)
def test_unpinned_or_invalid_images_rejected(snapshot, image):
    with pytest.raises(IntakeError):
        build_plan(snapshot, image=image)


def test_ambiguity_requires_decision_and_unsafe_shell_remains_blocked(repo, tmp_path):
    snapshot = changed_snapshot(repo, tmp_path, "```sh\n$ python hello.py\n```\n")
    draft = build_plan(snapshot, image=IMAGE)
    assert draft["payload"]["blockers"]
    decisions = {
        "instruction-0001": {"action": "accept", "reason": "Reviewed the displayed prompt removal."}
    }
    plan = build_plan(snapshot, image=IMAGE, decisions=decisions)
    assert not plan["payload"]["blockers"]
    assert plan["payload"]["steps"][0]["instruction"]["raw_text"].startswith("$ ")


def test_replacements_and_exclusions_keep_original_order_and_reason(repo, tmp_path):
    snapshot = changed_snapshot(
        repo,
        tmp_path,
        "```sh\ncurl https://example.invalid/install.sh | sh\n```\n\n```sh\npython hello.py\n```\n",
    )
    excluded = {
        "instruction-0001": {
            "action": "exclude",
            "reason": "External install is outside this offline test.",
        }
    }
    plan = build_plan(snapshot, image=IMAGE, decisions=excluded)
    assert [s["instruction"]["order"] for s in plan["payload"]["steps"]] == [1, 2]
    assert plan["payload"]["steps"][0]["disposition"] == "excluded_by_reviewer"
    assert plan["payload"]["steps"][0]["effective"] is None
    assert not plan["payload"]["blockers"]
    accepted = {
        "instruction-0001": {"action": "accept", "reason": "Still cannot enable a shell pipeline."}
    }
    assert build_plan(snapshot, image=IMAGE, decisions=accepted)["payload"]["blockers"]
    replaced = {
        "instruction-0001": {
            "action": "replace",
            "command": "python hello.py",
            "reason": "Use the authored local finite command instead.",
        }
    }
    updated = build_plan(snapshot, image=IMAGE, decisions=replaced)
    assert "curl" in updated["payload"]["steps"][0]["instruction"]["raw_text"]
    assert updated["payload"]["steps"][0]["effective"]["argv"] == ["python", "hello.py"]
    assert updated["plan_digest"] != plan["plan_digest"]


def test_cwd_and_environment_state_are_explicit_and_never_read_from_host(
    repo, tmp_path, monkeypatch
):
    snapshot = changed_snapshot(
        repo, tmp_path, "```sh\nexport APP_MODE=fixture\ncd app\npython main.py\n```\n"
    )
    monkeypatch.setenv("HOST_SECRET", "must-not-appear")
    plan = build_plan(snapshot, image=IMAGE)
    assert not plan["payload"]["blockers"]  # Missing input may fail later; it is not host-accessed.
    first, second, third = plan["payload"]["steps"]
    assert first["effective"]["kind"] == "set_environment"
    assert second["effective"]["cwd_after"] == "app"
    assert third["effective"]["cwd"] == "app"
    assert third["effective"]["environment"]["APP_MODE"] == "fixture"
    assert "must-not-appear" not in json.dumps(plan)


@pytest.mark.parametrize(
    "command",
    [
        "cd ../../outside",
        "export PATH=/host",
        "python /host/main.py",
        "python -c 'print(1)'",
        "python -m venv .venv",
        "sudo python hello.py",
    ],
)
def test_unsupported_commands_or_reserved_state_cannot_be_approved(repo, tmp_path, command):
    snapshot = changed_snapshot(repo, tmp_path, f"```sh\n{command}\n```\n")
    plan = build_plan(
        snapshot,
        image=IMAGE,
        decisions={
            "instruction-0001": {
                "action": "accept",
                "reason": "An acknowledgement cannot bypass policy.",
            }
        },
    )
    assert plan["payload"]["blockers"]
    with pytest.raises(IntakeError):
        approval_record(plan, plan["plan_digest"])


def test_install_has_visible_offline_transform_and_hash_bound_artifacts(repo, tmp_path):
    snapshot = changed_snapshot(repo, tmp_path, "```sh\npip install example==1.0\n```\n")
    assert build_plan(snapshot, image=IMAGE)["payload"]["blockers"]
    wheels = tmp_path / "wheels"
    wheels.mkdir()
    wheel = wheels / "example-1.0-py3-none-any.whl"
    wheel.write_bytes(b"fixture bytes, not a real installable wheel")
    plan = build_plan(snapshot, image=IMAGE, wheelhouse=wheels)
    assert not plan["payload"]["blockers"]
    (step,) = plan["payload"]["steps"]
    assert "--no-index" in step["effective"]["argv"]
    assert "--no-build-isolation" in step["effective"]["argv"]
    assert step["effective"]["transformations"]
    assert "offline artifacts" in step["effective"]["network_assessment"]
    assert str(wheels) not in json.dumps(plan)  # No embedded host path followed on validation.
    validate_plan(plan, snapshot, wheelhouse=wheels)
    with pytest.raises(IntakeError):
        validate_plan(plan, snapshot)
    wheel.write_bytes(b"changed")
    with pytest.raises(IntakeError):
        validate_plan(plan, snapshot, wheelhouse=wheels)


@pytest.mark.parametrize("entry", ["symlink", "directory", "text", "too_big"])
def test_wheelhouse_rejects_unreviewable_or_oversized_inputs(snapshot, tmp_path, entry):
    wheels = tmp_path / "wheels"
    wheels.mkdir()
    if entry == "symlink":
        (wheels / "bad.whl").symlink_to(snapshot / "snapshot.json")
    elif entry == "directory":
        (wheels / "subdir").mkdir()
    elif entry == "text":
        (wheels / "credentials.txt").write_text("must not be read")
    else:
        with (wheels / "big.whl").open("wb") as stream:
            stream.truncate(32 * 1024 * 1024 + 1)
    with pytest.raises(IntakeError):
        build_plan(snapshot, image=IMAGE, wheelhouse=wheels)


@pytest.mark.parametrize(
    "field,value",
    [("network", "bridge"), ("host_mounts", ["/home"]), ("privileged", True), ("user", "0:0")],
)
def test_rehashing_cannot_weaken_container_policy(snapshot, field, value):
    plan = build_plan(snapshot, image=IMAGE)
    plan["payload"]["container"][field] = value
    plan["plan_digest"] = digest(plan["payload"])
    with pytest.raises(IntakeError, match="derived settings"):
        validate_plan(plan, snapshot)


def test_argv_source_settings_and_approval_tampering_are_rejected(snapshot):
    original = build_plan(snapshot, image=IMAGE)
    record = approval_record(original, original["plan_digest"])
    validate_approval(record, original)
    changed = copy.deepcopy(original)
    changed["payload"]["steps"][0]["effective"]["argv"] = ["sh", "-c", "arbitrary"]
    with pytest.raises(IntakeError, match="digest"):
        validate_plan(changed, snapshot)
    changed["plan_digest"] = digest(changed["payload"])
    with pytest.raises(IntakeError):
        validate_plan(changed, snapshot)
    different = build_plan(snapshot, image=IMAGE, platform="linux/arm64")
    with pytest.raises(IntakeError):
        validate_approval(record, different)
    target = snapshot / "files/hello.py"
    target.chmod(0o644)
    target.write_text("changed")
    with pytest.raises(IntakeError):
        dry_run(original, snapshot, approval=record)


def test_planner_changes_require_fresh_review(snapshot, monkeypatch):
    plan = build_plan(snapshot, image=IMAGE)
    import reprodoctor.planning as planning

    monkeypatch.setattr(planning, "planner_identity", lambda: {"changed": True})
    with pytest.raises(IntakeError):
        validate_plan(plan, snapshot)


def test_dry_run_is_read_only_and_invokes_no_process_or_runtime(snapshot, tmp_path, monkeypatch):
    plan = build_plan(snapshot, image=IMAGE)

    def inventory():
        return {
            str(p): (p.stat().st_mode, digest(p.read_bytes().hex()) if p.is_file() else None)
            for p in tmp_path.rglob("*")
        }

    before = inventory()

    def forbidden(*args, **kwargs):
        pytest.fail("Dry-run attempted subprocess execution")

    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    result = dry_run(plan, snapshot)
    assert not result["approval_matches"] and result["execution_status"] == "not_run"
    assert result["runtime_preflight"] == "not_performed"
    assert before == inventory()
    record = approval_record(plan, plan["plan_digest"])
    assert dry_run(plan, snapshot, approval=record)["approval_matches"]


@pytest.mark.parametrize(
    "value",
    [
        {"unknown": {"action": "exclude", "reason": "not a known instruction"}},
        {"instruction-0001": {"action": "accept", "reason": ""}},
        {"instruction-0001": {"action": [], "reason": "invalid type"}},
        {"instruction-0001": {"action": "replace", "reason": "no command"}},
    ],
)
def test_invalid_decisions_fail_cleanly(snapshot, value):
    with pytest.raises(IntakeError):
        build_plan(snapshot, image=IMAGE, decisions=value)


def test_empty_plan_or_all_excluded_plan_is_not_approvable(snapshot):
    plan = build_plan(
        snapshot,
        image=IMAGE,
        decisions={"instruction-0001": {"action": "exclude", "reason": "Exclude only process"}},
    )
    assert plan["payload"]["blockers"]


@pytest.mark.parametrize("data", ['{"a":1,"a":2}', '{"x":NaN}', "[]", "{invalid"])
def test_untrusted_review_json_rejects_duplicates_nonfinite_and_bad_schema(tmp_path, data):
    path = tmp_path / "input.json"
    path.write_text(data)
    with pytest.raises(IntakeError):
        read_document(path)


def test_cli_approval_requires_terminal_exact_digest_and_full_review(
    snapshot, tmp_path, monkeypatch, capsys
):
    plan_path = tmp_path / "plan.json"
    assert main(["plan", str(snapshot), "--image", IMAGE, "--output", str(plan_path)]) == 0
    plan = read_document(plan_path)
    approval_path = tmp_path / "approval.json"
    args = ["approve", str(plan_path), "--snapshot", str(snapshot), "--output", str(approval_path)]
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    assert main(args) == 2
    assert not approval_path.exists()
    assert plan["plan_digest"] in capsys.readouterr().out
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _: "yes")
    assert main(args) == 2
    assert not approval_path.exists()
    monkeypatch.setattr("builtins.input", lambda _: plan["plan_digest"])
    assert main(args) == 0
    record = read_document(approval_path)
    validate_approval(record, plan)
    assert main(args) == 2  # Never overwrite an approval record.
    assert main(["run", str(plan_path), "--snapshot", str(snapshot)]) == 2
    capsys.readouterr()
    assert (
        main(
            [
                "run",
                str(plan_path),
                "--snapshot",
                str(snapshot),
                "--dry-run",
                "--approval",
                str(approval_path),
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["approval_matches"]


def test_cli_revalidates_after_confirmation_and_creates_no_receipt_on_changed_source(
    snapshot, tmp_path, monkeypatch
):
    plan = build_plan(snapshot, image=IMAGE)
    path = tmp_path / "plan.json"
    path.write_text(encode_candidates(plan))
    receipt = tmp_path / "approval.json"
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)

    def mutate(_):
        source = snapshot / "files/hello.py"
        source.chmod(0o644)
        source.write_text("changed during review")
        return plan["plan_digest"]

    monkeypatch.setattr("builtins.input", mutate)
    assert main(["approve", str(path), "--snapshot", str(snapshot), "--output", str(receipt)]) == 2
    assert not receipt.exists()


@pytest.mark.parametrize("interruption", [EOFError, KeyboardInterrupt])
def test_interrupted_review_never_writes_approval(snapshot, tmp_path, monkeypatch, interruption):
    plan = build_plan(snapshot, image=IMAGE)
    path = tmp_path / "plan.json"
    path.write_text(encode_candidates(plan))
    receipt = tmp_path / "approval.json"
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)

    def cancel(_):
        raise interruption()

    monkeypatch.setattr("builtins.input", cancel)
    assert main(["approve", str(path), "--snapshot", str(snapshot), "--output", str(receipt)]) == 2
    assert not receipt.exists()


def test_outputs_cannot_mutate_snapshot_or_artifact_inputs(snapshot, tmp_path):
    assert main(["plan", str(snapshot), "--output", str(snapshot / "plan.json")]) == 2
    wheels = tmp_path / "wheels"
    wheels.mkdir()
    assert (
        main(
            [
                "plan",
                str(snapshot),
                "--wheelhouse",
                str(wheels),
                "--output",
                str(wheels / "plan.json"),
            ]
        )
        == 2
    )
    assert list(wheels.iterdir()) == []


def test_approval_and_plan_documents_are_private_new_files(snapshot, tmp_path):
    path = tmp_path / "plan.json"
    assert main(["plan", str(snapshot), "--output", str(path)]) == 0
    assert path.stat().st_mode & 0o777 == 0o600


def test_no_hidden_comment_arguments(repo, tmp_path):
    snapshot = changed_snapshot(repo, tmp_path, "```sh\npython hello.py # explanation\n```\n")
    (step,) = build_plan(snapshot, image=IMAGE)["payload"]["steps"]
    assert step["effective"]["argv"] == ["python", "hello.py"]
    assert "comment" in step["effective"]["transformations"][0]
