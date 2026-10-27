"""Bounded Git-object intake without checkout, local Git config, filters or hooks.

Git itself remains trusted infrastructure, not a sandbox. Local input currently
requires an ordinary .git directory: linked worktrees and bare repos are rejected.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import signal
import stat
import subprocess
import tempfile
import time
import unicodedata
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Iterator
from urllib.parse import urlsplit

from . import __version__


class IntakeError(Exception):
    """An input or required control could not be accepted."""


@dataclass(frozen=True)
class Limits:
    snapshot_bytes: int = 50 * 1024 * 1024
    file_bytes: int = 1024 * 1024
    files: int = 5000
    git_output_bytes: int = 4 * 1024 * 1024
    fetch_bytes: int = 100 * 1024 * 1024
    command_seconds: float = 30
    fetch_seconds: float = 120

    def __post_init__(self) -> None:
        if any(value <= 0 for value in asdict(self).values()):
            raise ValueError("All intake limits must be positive")


@dataclass(frozen=True)
class Entry:
    path: str
    mode: str
    object_id: str
    size: int


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def github_url(value: str) -> str:
    """Accept only public GitHub repository HTTPS URLs, never embedded credentials."""
    parsed = urlsplit(value)
    if parsed.scheme != "https" or parsed.netloc != "github.com" or parsed.query or parsed.fragment:
        raise IntakeError(
            "Expected https://github.com/OWNER/REPOSITORY without credentials or query"
        )
    parts = parsed.path.strip("/").split("/")
    if len(parts) != 2 or any(not re.fullmatch(r"[A-Za-z0-9_.-]+", p) for p in parts):
        raise IntakeError("GitHub URL must identify exactly one owner and repository")
    owner, repo = parts
    repo = repo.removesuffix(".git")
    if owner in {".", ".."} or repo in {"", ".", ".."}:
        raise IntakeError("Invalid GitHub owner or repository")
    return f"https://github.com/{owner}/{repo}.git"


def validate_ref(ref: str) -> None:
    if (
        not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_./-]{0,199}", ref)
        or any(part in {"", ".", ".."} or part.endswith(".lock") for part in ref.split("/"))
        or ".." in ref
    ):
        raise IntakeError("Ref must be HEAD, a branch/tag name, or a full commit ID")


def validate_path(path: str) -> None:
    parts = path.split("/")
    if (
        not path
        or PurePosixPath(path).is_absolute()
        or "\\" in path
        or len(path.encode()) > 1024
        or any(ord(c) < 32 or ord(c) == 127 for c in path)
        or any(
            p in {"", ".", ".."} or p.casefold() == ".git" or ":" in p or p.endswith((" ", "."))
            for p in parts
        )
    ):
        raise IntakeError("Repository contains an unsafe or unsupported path")


def _disk_bytes(root: Path, stop: int) -> int:
    total = 0
    for directory, _, files in os.walk(root, followlinks=False):
        for name in files:
            total += (Path(directory) / name).lstat().st_size
            if total > stop:
                return total
    return total


class Git:
    def __init__(self, root: Path, limits: Limits):
        executable = shutil.which("git")
        if executable is None:
            raise IntakeError("Git is required")
        self.executable = executable
        self.root = root
        self.limits = limits
        self.env = {
            "PATH": os.defpath,
            "HOME": str(root),
            "LC_ALL": "C",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_ASKPASS": "/usr/bin/false",
            "GIT_NO_REPLACE_OBJECTS": "1",
            "GIT_NO_LAZY_FETCH": "1",
            "GIT_OPTIONAL_LOCKS": "0",
        }

    def run(self, *args: str, fetch: bool = False, cap: int | None = None) -> bytes:
        maximum = self.limits.git_output_bytes if cap is None else cap
        deadline = time.monotonic() + (
            self.limits.fetch_seconds if fetch else self.limits.command_seconds
        )
        command = [
            self.executable,
            "--no-replace-objects",
            "-c",
            "core.hooksPath=/dev/null",
            "-c",
            "credential.helper=",
            "-c",
            "protocol.allow=never",
            "-c",
            "protocol.https.allow=always",
            "-c",
            "http.followRedirects=false",
            "-c",
            "http.extraHeader=",
            "-c",
            "maintenance.auto=false",
            "-c",
            "gc.auto=0",
            *args,
        ]
        with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
            process = subprocess.Popen(
                command,
                cwd=self.root,
                env=self.env,
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
                start_new_session=True,
            )
            try:
                while True:
                    status = process.poll()
                    if time.monotonic() > deadline:
                        raise IntakeError("Git operation exceeded its time limit")
                    if os.fstat(stdout.fileno()).st_size > maximum or (
                        os.fstat(stderr.fileno()).st_size > self.limits.git_output_bytes
                    ):
                        raise IntakeError("Git output exceeded its byte limit")
                    if fetch and _disk_bytes(self.root, self.limits.fetch_bytes) > (
                        self.limits.fetch_bytes
                    ):
                        raise IntakeError("Git download exceeded its disk budget")
                    if status is not None:
                        break
                    time.sleep(0.01)
                if status:
                    # Never echo untrusted Git errors (which may contain secrets/control codes).
                    raise IntakeError(
                        "Git operation failed; check the repository/ref and Git version"
                    )
                stdout.seek(0)
                return stdout.read(maximum + 1)
            finally:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGKILL)
                process.wait()


def _read_metadata(path: Path, limit: int = 1024 * 1024) -> str:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
        raise IntakeError("Unsupported Git metadata file")
    try:
        return path.read_text(encoding="ascii").strip()
    except UnicodeError as exc:
        raise IntakeError("Unsupported Git metadata encoding") from exc


def _local_oid(git_dir: Path, ref: str, depth: int = 0) -> str:
    if depth > 5:
        raise IntakeError("Too many symbolic Git refs")
    if re.fullmatch(r"[0-9a-fA-F]{40}", ref):
        return ref.lower()
    candidates = (
        [ref]
        if ref == "HEAD" or ref.startswith("refs/")
        else [
            f"refs/heads/{ref}",
            f"refs/tags/{ref}",
        ]
    )
    found = set()
    for name in candidates:
        validate_ref(name)
        target = git_dir / name
        if any(p.is_symlink() for p in [target, *target.parents] if p != git_dir.parent):
            raise IntakeError("Symlinked Git metadata is unsupported")
        if target.is_file():
            value = _read_metadata(target)
            if value.startswith("ref: "):
                value = _local_oid(git_dir, value[5:], depth + 1)
            if not re.fullmatch(r"[0-9a-fA-F]{40}", value):
                raise IntakeError("Unsupported Git ref contents")
            found.add(value.lower())
        elif name != "HEAD" and (git_dir / "packed-refs").exists():
            for line in _read_metadata(git_dir / "packed-refs").splitlines():
                fields = line.split(" ")
                if len(fields) == 2 and fields[1] == name:
                    if not re.fullmatch(r"[0-9a-f]{40}", fields[0]):
                        raise IntakeError("Unsupported packed Git ref")
                    found.add(fields[0])
    if len(found) != 1:
        raise IntakeError("Local ref is missing or ambiguous; use a full commit ID")
    return found.pop()


def _tree(git: Git, oid: str, limits: Limits) -> list[Entry]:
    raw = git.run("ls-tree", "-r", "-l", "-z", oid)
    entries = []
    seen: dict[str, str] = {}
    total = 0
    for record in raw.split(b"\0"):
        if not record:
            continue
        try:
            metadata, name = record.split(b"\t", 1)
            mode, kind, object_id, size = metadata.decode("ascii").split()
            path = name.decode("utf-8")
        except (ValueError, UnicodeError) as exc:
            raise IntakeError("Unsupported Git tree entry") from exc
        validate_path(path)
        if mode not in {"100644", "100755"} or kind != "blob":
            raise IntakeError("Symlinks, submodules and special files are unsupported")
        for n in range(1, len(path.split("/")) + 1):
            original = "/".join(path.split("/")[:n])
            normalized = unicodedata.normalize("NFC", original).casefold()
            if normalized in seen and seen[normalized] != original:
                raise IntakeError("Repository paths collide on a supported filesystem")
            seen[normalized] = original
        length = int(size)
        total += length
        if length > limits.file_bytes or total > limits.snapshot_bytes:
            raise IntakeError("Repository exceeds the file or snapshot byte limit")
        entries.append(Entry(path, mode, object_id, length))
        if len(entries) > limits.files:
            raise IntakeError("Repository exceeds the file-count limit")
    return sorted(entries, key=lambda e: e.path)


def _check_clean(source: Path, entries: list[Entry], blobs: dict[str, bytes]) -> None:
    expected = {e.path: e for e in entries}
    expected_dirs = {
        str(parent)
        for entry in entries
        for parent in PurePosixPath(entry.path).parents
        if parent != PurePosixPath(".")
    }
    count = 0
    for directory, dirs, files in os.walk(source, followlinks=False):
        relative = Path(directory).relative_to(source)
        if relative == Path("."):
            dirs[:] = [d for d in dirs if d != ".git"]
        for name in dirs:
            child = Path(directory) / name
            if child.is_symlink() or child.relative_to(source).as_posix() not in expected_dirs:
                raise IntakeError("Working tree contains extra directories; use --committed-only")
        for name in files:
            path = Path(directory) / name
            key = path.relative_to(source).as_posix()
            entry = expected.get(key)
            mode = path.lstat().st_mode
            if (
                entry is None
                or not stat.S_ISREG(mode)
                or path.stat().st_size != entry.size
                or bool(mode & stat.S_IXUSR) != (entry.mode == "100755")
                or path.read_bytes() != blobs[entry.object_id]
            ):
                raise IntakeError("Working tree differs from commit; use --committed-only")
            count += 1
    if count != len(entries):
        raise IntakeError("Working tree has missing files; use --committed-only")


@contextmanager
def _object_source(
    source: str, ref: str, limits: Limits
) -> Iterator[tuple[Git, str, str, Path | None]]:
    with tempfile.TemporaryDirectory(prefix="reprodoctor-intake-") as temporary:
        root = Path(temporary)
        git = Git(root, limits)
        git.run("init", "--bare", "--template=", "--object-format=sha1", ".")
        if "://" in source or source.startswith("git@"):
            origin = github_url(source)
            git.run(
                "fetch",
                "--depth=1",
                "--no-tags",
                "--no-recurse-submodules",
                origin,
                ref,
                fetch=True,
            )
            resolved = "FETCH_HEAD"
            local = None
        else:
            local = Path(source).resolve(strict=True)
            git_dir = local / ".git"
            if not git_dir.is_dir() or git_dir.is_symlink():
                raise IntakeError("Local input requires an ordinary repository .git directory")
            objects = git_dir / "objects"
            if not objects.is_dir() or objects.is_symlink():
                raise IntakeError("Symlinked Git objects are unsupported")
            for index, path in enumerate(objects.rglob("*")):
                if index > 100_000 or path.is_symlink():
                    raise IntakeError("Git object store is too large or contains symlinks")
            if (objects / "info" / "alternates").exists() or (git_dir / "commondir").exists():
                raise IntakeError("Shared object stores and linked worktrees are unsupported")
            git.env["GIT_OBJECT_DIRECTORY"] = str(objects)
            resolved = _local_oid(git_dir, ref)
            origin = str(local)
        oid = git.run("rev-parse", "--verify", f"{resolved}^{{commit}}").decode().strip()
        if not re.fullmatch(r"[0-9a-f]{40}", oid):
            raise IntakeError("Expected a full SHA-1 commit ID")
        yield git, oid, origin, local


def intake(
    source: str,
    output: Path,
    *,
    ref: str = "HEAD",
    committed_only: bool = False,
    limits: Limits | None = None,
) -> dict:
    """Export a new snapshot directory, publishing atomically after all checks."""
    limits = limits or Limits()
    validate_ref(ref)
    output = output.absolute()
    if output.exists() or output.is_symlink():
        raise IntakeError("Output must be a new directory")
    if not output.parent.is_dir():
        raise IntakeError("Output parent directory must already exist")
    with _object_source(source, ref, limits) as (git, oid, origin, local):
        if local is not None and output.resolve().is_relative_to(local):
            raise IntakeError("Output must be outside the input repository")
        entries = _tree(git, oid, limits)
        blobs = {}
        for entry in entries:
            if entry.object_id not in blobs:
                data = git.run("cat-file", "blob", entry.object_id, cap=limits.file_bytes)
                if len(data) != entry.size:
                    raise IntakeError("Git blob size changed during intake")
                blobs[entry.object_id] = data
        if local is not None and not committed_only:
            _check_clean(local, entries, blobs)
            # Also reject staged changes even if worktree bytes match HEAD. Read index
            # through the isolated Git config; this never invokes status or filters.
            index_path = local / ".git" / "index"
            if index_path.is_symlink():
                raise IntakeError("Symlinked Git index is unsupported")
            git.env["GIT_INDEX_FILE"] = str(index_path)
            indexed = git.run("ls-files", "--stage", "-z").split(b"\0")
            expected = [f"{e.mode} {e.object_id} 0\t{e.path}".encode() for e in entries]
            if sorted(r for r in indexed if r) != sorted(expected):
                raise IntakeError("Index differs from commit; use --committed-only")
        inventory = [
            {**asdict(e), "sha256": hashlib.sha256(blobs[e.object_id]).hexdigest()} for e in entries
        ]
        digest = hashlib.sha256(canonical(inventory)).hexdigest()
        manifest = {
            "schema_version": 1,
            "tool_version": __version__,
            "origin": origin,
            "requested_ref": ref,
            "commit": oid,
            "content_digest": digest,
            "files": inventory,
            "total_bytes": sum(e.size for e in entries),
            "omissions": ["Git metadata", "Untracked and ignored working-tree files"],
            "working_tree_policy": "committed-only" if committed_only else "require-clean",
            "limits": asdict(limits),
            "git_version": git.run("--version").decode().strip(),
            "warnings": [
                "Tracked contents may include secrets; no secret scan has been performed."
            ],
        }
        # Stage beside the destination so rename stays on one filesystem.
        with tempfile.TemporaryDirectory(prefix=".reprodoctor-stage-", dir=output.parent) as stage:
            staged = Path(stage) / "snapshot"
            files = staged / "files"
            files.mkdir(parents=True)
            for entry in entries:
                target = files / entry.path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(blobs[entry.object_id])
                target.chmod(0o555 if entry.mode == "100755" else 0o444)
            (staged / "snapshot.json").write_bytes(canonical(manifest) + b"\n")
            if output.exists() or output.is_symlink():
                raise IntakeError("Output appeared during intake; refusing to overwrite")
            staged.rename(output)
        return manifest
