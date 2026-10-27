import json
from dataclasses import replace

import pytest

from reprodoctor.cli import main
from reprodoctor.intake import (
    Git,
    IntakeError,
    Limits,
    github_url,
    intake,
    validate_path,
)


def test_clean_snapshot_is_deterministic_and_does_not_execute(repo, tmp_path):
    root, git = repo
    marker = tmp_path / "executed"
    (root / "hello.py").write_text(f"open({str(marker)!r}, 'w').write('bad')\n")
    git("add", ".")
    git("commit", "-m", "executable content")
    a = intake(str(root), tmp_path / "a")
    b = intake(str(root), tmp_path / "b")
    assert a == b
    assert a["commit"] == git("rev-parse", "HEAD")
    assert len(a["content_digest"]) == 64
    assert not marker.exists()
    assert not (tmp_path / "a/files/.git").exists()
    assert json.loads((tmp_path / "a/snapshot.json").read_text()) == a
    assert (tmp_path / "a/files/hello.py").read_bytes() == (root / "hello.py").read_bytes()


@pytest.mark.parametrize("change", ["modified", "untracked", "ignored", "deleted", "staged"])
def test_dirty_requires_explicit_committed_only(repo, tmp_path, change):
    root, git = repo
    if change == "modified":
        (root / "README.md").write_text("changed")
    elif change == "deleted":
        (root / "README.md").unlink()
    elif change in {"untracked", "ignored"}:
        (root / "credentials.txt").write_text("HOST_SECRET")
        if change == "ignored":
            (root / ".git/info").mkdir(exist_ok=True)
            (root / ".git/info/exclude").write_text("credentials.txt\n")
    else:
        (root / "README.md").write_text("staged")
        git("add", ".")
        (root / "README.md").write_text(git("show", "HEAD:README.md") + "\n")
    with pytest.raises(IntakeError, match="commit"):
        intake(str(root), tmp_path / "rejected")
    assert not (tmp_path / "rejected").exists()
    result = intake(str(root), tmp_path / "accepted", committed_only=True)
    assert result["working_tree_policy"] == "committed-only"
    assert "HOST_SECRET" not in "".join(
        p.read_text() for p in (tmp_path / "accepted").rglob("*") if p.is_file()
    )


def test_local_config_hooks_filters_and_inherited_environment_are_unused(
    repo, tmp_path, monkeypatch
):
    root, git = repo
    marker = tmp_path / "hook-ran"
    hook = root / ".git/hooks/post-checkout"
    hook.parent.mkdir(exist_ok=True)
    hook.write_text(f"#!/bin/sh\ntouch '{marker}'\n")
    hook.chmod(0o755)
    git("config", "filter.evil.smudge", f"touch '{marker}'")
    (root / ".gitattributes").write_text("*.py filter=evil\n")
    git("add", ".gitattributes")
    git("commit", "-m", "filter declaration")
    git("config", "core.fsmonitor", str(hook))
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "core.fsmonitor")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", str(hook))
    monkeypatch.setenv("GIT_DIR", "/does/not/exist")
    monkeypatch.setenv("GIT_TRACE", str(marker))
    intake(str(root), tmp_path / "snapshot")
    assert not marker.exists()


def test_packed_refs_and_tags_resolve_to_commit(repo, tmp_path):
    root, git = repo
    git("tag", "-a", "v1", "-m", "version")
    git("pack-refs", "--all")
    result = intake(str(root), tmp_path / "snapshot", ref="v1")
    assert result["commit"] == git("rev-parse", "HEAD")


def test_snapshot_stays_pinned_after_source_changes(repo, tmp_path):
    root, git = repo
    first = git("rev-parse", "HEAD")
    original = intake(str(root), tmp_path / "original")
    (root / "hello.py").write_text("print('new')\n")
    git("add", ".")
    git("commit", "-m", "new commit")
    pinned = intake(str(root), tmp_path / "pinned", ref=first, committed_only=True)
    assert pinned["content_digest"] == original["content_digest"]
    assert pinned["commit"] == first


@pytest.mark.parametrize("kind", ["symlink", "submodule", "case-collision"])
def test_unsupported_tree_entries_fail_without_publishing(repo, tmp_path, kind):
    root, git = repo
    if kind == "symlink":
        (root / "escape").symlink_to(tmp_path / "outside")
        git("add", "escape")
    elif kind == "submodule":
        git("update-index", "--add", "--cacheinfo", "160000", git("rev-parse", "HEAD"), "vendor")
    else:
        blob = git("hash-object", "-w", "--stdin", input=b"collision")
        git("update-index", "--add", "--cacheinfo", "100644", blob, "readme.md")
    git("commit", "-m", kind)
    with pytest.raises(IntakeError):
        intake(str(root), tmp_path / "snapshot", committed_only=True)
    assert not (tmp_path / "snapshot").exists()


@pytest.mark.parametrize(
    "path",
    [
        "../x",
        "/etc/passwd",
        "a/../../b",
        "a/.git/config",
        "a\\b",
        "a\nfile",
        "a:b",
        "a/./b",
        "a//b",
        "a.",
    ],
)
def test_path_validation(path):
    with pytest.raises(IntakeError):
        validate_path(path)


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/a/b",
        "https://github.com.evil/a/b",
        "https://user:secret@github.com/a/b",
        "git@github.com:a/b",
        "https://github.com/a/b/tree/main",
        "https://github.com/a/b?q=x",
        "https://github.com/a/%2e%2e",
        "file:///tmp/a",
    ],
)
def test_disallowed_urls(url):
    with pytest.raises(IntakeError):
        github_url(url)


def test_github_canonical_url():
    assert github_url("https://github.com/example/project/") == (
        "https://github.com/example/project.git"
    )


@pytest.mark.parametrize(
    "limits", [Limits(file_bytes=3), Limits(snapshot_bytes=3), Limits(files=1)]
)
def test_size_limits_and_cleanup(repo, tmp_path, limits):
    with pytest.raises(IntakeError, match="limit"):
        intake(str(repo[0]), tmp_path / "snapshot", limits=limits)
    assert not (tmp_path / "snapshot").exists()
    assert not list(tmp_path.glob(".reprodoctor-stage-*"))


def test_existing_output_and_inside_source_rejected(repo, tmp_path):
    root, _ = repo
    output = tmp_path / "existing"
    output.mkdir()
    with pytest.raises(IntakeError, match="new directory"):
        intake(str(root), output)
    with pytest.raises(IntakeError, match="outside"):
        intake(str(root), root / "snapshot")


def test_shared_objects_rejected(repo, tmp_path):
    root, _ = repo
    (root / ".git/objects/info/alternates").write_text("/sensitive\n")
    with pytest.raises(IntakeError, match="Shared"):
        intake(str(root), tmp_path / "snapshot")


def test_git_timeout_and_output_bound(tmp_path):
    git = Git(tmp_path, replace(Limits(), command_seconds=5, git_output_bytes=32))
    fake = tmp_path / "fake-git"
    fake.write_text("#!/bin/sh\nwhile :; do printf 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'; done\n")
    fake.chmod(0o755)
    git.executable = str(fake)
    with pytest.raises(IntakeError, match="byte limit"):
        git.run()
    git.limits = replace(git.limits, command_seconds=0.1)
    fake.write_text("#!/bin/sh\nsleep 5\n")
    with pytest.raises(IntakeError, match="time limit"):
        git.run()


def test_cli_success_and_safe_error(repo, tmp_path, capsys):
    assert main(["intake", str(repo[0]), "--output", str(tmp_path / "snapshot")]) == 0
    assert len(json.loads(capsys.readouterr().out)["commit"]) == 40
    assert main(["intake", "missing\npath", "--output", str(tmp_path / "other")]) == 2
    output = capsys.readouterr().out
    assert len(output.splitlines()) == 1
    assert "error" in json.loads(output)


def test_github_fetch_uses_fresh_store_and_restricted_arguments(repo, tmp_path, monkeypatch):
    root, real_git = repo
    original = Git.run
    observed = []

    def fetch_stub(self, *args, **kwargs):
        if args[0] == "fetch":
            observed.append((args, kwargs, self.env.copy()))
            # A transport stub supplies real controlled objects. Everything after fetch
            # still exercises the actual Git-object intake path.
            self.env["GIT_OBJECT_DIRECTORY"] = str(root / ".git/objects")
            (self.root / "FETCH_HEAD").write_text(real_git("rev-parse", "HEAD") + "\n")
            return b""
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Git, "run", fetch_stub)
    monkeypatch.setenv("GITHUB_TOKEN", "HOST_SECRET")
    result = intake("https://github.com/example/project", tmp_path / "snapshot", ref="main")
    args, kwargs, env = observed[0]
    assert "--no-recurse-submodules" in args and "--no-tags" in args
    assert args[-2:] == ("https://github.com/example/project.git", "main")
    assert kwargs["fetch"] is True
    assert "GITHUB_TOKEN" not in env and "SSH_AUTH_SOCK" not in env
    assert result["commit"] == real_git("rev-parse", "HEAD")


def test_remote_failure_does_not_publish(tmp_path, monkeypatch):
    original = Git.run

    def failed(self, *args, **kwargs):
        if args[0] == "fetch":
            raise IntakeError("Git operation failed")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Git, "run", failed)
    with pytest.raises(IntakeError):
        intake("https://github.com/example/project", tmp_path / "snapshot")
    assert not (tmp_path / "snapshot").exists()
