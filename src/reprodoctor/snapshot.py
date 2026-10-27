"""Validate bounded intake artifacts before consuming their untrusted contents."""

import hashlib
import json
import os
import re
import stat
from pathlib import Path

from .intake import IntakeError, Limits, canonical, validate_path


def _read(path: Path, maximum: int) -> bytes:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > maximum:
        raise IntakeError("Snapshot file is missing, unsafe or exceeds its byte limit")
    with path.open("rb") as stream:
        data = stream.read(maximum + 1)
    if len(data) > maximum:
        raise IntakeError("Snapshot file exceeded its byte limit while reading")
    return data


def load_snapshot(root: Path) -> tuple[dict, dict[str, bytes]]:
    """Revalidate hashes; this establishes integrity, not provenance or approval."""
    root = root.resolve(strict=True)
    limits = Limits()
    try:
        manifest = json.loads(_read(root / "snapshot.json", limits.git_output_bytes))
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise IntakeError("Invalid snapshot JSON") from exc
    if (
        not isinstance(manifest, dict)
        or type(manifest.get("schema_version")) is not int
        or manifest["schema_version"] != 1
    ):
        raise IntakeError("Unsupported snapshot schema")
    inventory = manifest.get("files")
    if not isinstance(inventory, list) or len(inventory) > limits.files:
        raise IntakeError("Invalid or oversized snapshot inventory")
    if not isinstance(manifest.get("commit"), str) or not re.fullmatch(
        r"[0-9a-f]{40}", manifest["commit"]
    ):
        raise IntakeError("Invalid snapshot commit ID")
    try:
        digest = hashlib.sha256(canonical(inventory)).hexdigest()
    except RecursionError as exc:
        raise IntakeError("Snapshot inventory is too deeply nested") from exc
    if digest != manifest.get("content_digest"):
        raise IntakeError("Snapshot inventory digest does not match")
    files_root = root / "files"
    if files_root.is_symlink() or not files_root.is_dir():
        raise IntakeError("Snapshot files directory is missing or unsafe")
    contents = {}
    total = 0
    for entry in inventory:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            raise IntakeError("Invalid snapshot inventory entry")
        name = entry["path"]
        validate_path(name)
        if (
            name in contents
            or not isinstance(entry.get("mode"), str)
            or entry["mode"] not in {"100644", "100755"}
        ):
            raise IntakeError("Duplicate or unsupported snapshot entry")
        size = entry.get("size")
        if type(size) is not int or not 0 <= size <= limits.file_bytes:
            raise IntakeError("Invalid snapshot file size")
        total += size
        if total > limits.snapshot_bytes:
            raise IntakeError("Snapshot exceeds its total byte limit")
        target = files_root / name
        if any(parent.is_symlink() for parent in target.parents if parent != root.parent):
            raise IntakeError("Snapshot contains symlinked directories")
        data = _read(target, limits.file_bytes)
        if len(data) != size or hashlib.sha256(data).hexdigest() != entry.get("sha256"):
            raise IntakeError("Snapshot file hash or size does not match")
        oid = hashlib.sha1(b"blob " + str(size).encode() + b"\0" + data).hexdigest()
        if oid != entry.get("object_id"):
            raise IntakeError("Snapshot Git object ID does not match")
        if bool(target.stat().st_mode & stat.S_IXUSR) != (entry["mode"] == "100755"):
            raise IntakeError("Snapshot executable mode changed")
        contents[name] = data
    expected_dirs = {
        str(parent) for name in contents for parent in Path(name).parents if parent != Path(".")
    }
    observed = set()
    for directory, dirs, files in os.walk(files_root, followlinks=False):
        for name in dirs:
            path = Path(directory) / name
            if path.is_symlink() or path.relative_to(files_root).as_posix() not in expected_dirs:
                raise IntakeError("Snapshot contains unexpected directories")
        for name in files:
            observed.add((Path(directory) / name).relative_to(files_root).as_posix())
            if len(observed) > len(contents):
                raise IntakeError("Snapshot contains unexpected files")
    if observed != set(contents) or manifest.get("total_bytes") != total:
        raise IntakeError("Snapshot file inventory or total does not match")
    return manifest, contents
