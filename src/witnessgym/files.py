from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path, PurePosixPath

from .errors import WitnessGymError


def relative_path(value: str) -> str:
    path = PurePosixPath(value)
    if (
        not value
        or "\\" in value
        or path.is_absolute()
        or any(p in {".", ".."} for p in value.split("/"))
        or ":" in value
    ):
        raise WitnessGymError(f"Expected a safe relative path: {value!r}")
    return str(path)


def inside(root: Path, name: str) -> Path:
    name = relative_path(name)
    result = root / name
    if not result.resolve().is_relative_to(root.resolve()):
        raise WitnessGymError("Path escapes its workspace")
    return result


def under(path: str, roots: tuple[str, ...]) -> bool:
    return any(path == root or path.startswith(root + "/") for root in roots)


def ignored(path: Path, root: Path, ignore_dirs: tuple[str, ...]) -> bool:
    return bool(set(path.relative_to(root).parts) & set(ignore_dirs))


def snapshot(root: Path, ignore_dirs: tuple[str, ...] = ()) -> dict[str, str]:
    if not root.is_dir() or root.is_symlink():
        raise WitnessGymError("Repository must be a regular directory")
    result = {}
    for path in sorted(root.rglob("*")):
        # Reject symlinks even in ignored directories: never follow an external tree.
        if path.is_symlink():
            raise WitnessGymError(
                f"Symlink is not permitted in an execution workspace: {path.name}"
            )
        if ignored(path, root, ignore_dirs + (".git", "__pycache__")):
            continue
        if path.is_file():
            digest = hashlib.sha256()
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
            result[path.relative_to(root).as_posix()] = digest.hexdigest()
    return result


def changes(before: dict[str, str], after: dict[str, str]) -> list[str]:
    return sorted(k for k in before.keys() | after.keys() if before.get(k) != after.get(k))


def copy_repo(source: Path, destination: Path, ignore_dirs: tuple[str, ...]) -> None:
    snapshot(source, ignore_dirs)
    if destination.resolve().is_relative_to(source.resolve()):
        raise WitnessGymError("Output must not be inside the input repository")
    shutil.copytree(
        source, destination, ignore=shutil.ignore_patterns(".git", "__pycache__", *ignore_dirs)
    )


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix="." + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(payload, out, indent=2, ensure_ascii=False, allow_nan=False)
            out.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
