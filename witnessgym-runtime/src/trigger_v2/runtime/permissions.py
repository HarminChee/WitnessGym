from __future__ import annotations

import json
import os
import stat
from pathlib import Path


def ensure_prompt_files_exist(system_prompt_path: Path, task_template_path: Path) -> None:
    if not system_prompt_path.is_file():
        raise FileNotFoundError(f"Missing system prompt: {system_prompt_path}")
    if not task_template_path.is_file():
        raise FileNotFoundError(f"Missing task template: {task_template_path}")


def build_allowed_tools_for_trigger_v2() -> str:
    return "Read,Glob,Grep,LS,View,Bash,Edit,MultiEdit,Write"


def _normalize_rel_path(path: str) -> str:
    return path.lstrip("./").strip("/")


def _normalize_root(root: str) -> str:
    return root.strip("/")


def _matches_root(rel_path: str, root: str) -> bool:
    normalized = _normalize_rel_path(rel_path)
    root_norm = _normalize_root(root)
    if not root_norm:
        return False
    if normalized == root_norm:
        return True
    if normalized.startswith(root_norm + "/"):
        return True
    if f"/{root_norm}/" in f"/{normalized}/":
        return True
    if normalized.endswith("/" + root_norm):
        return True
    return False


def is_under_any_root(rel_path: str, roots: list[str]) -> bool:
    return any(_matches_root(rel_path, root) for root in roots)


def validate_test_only_write_targets(
    paths: list[str],
    allowed_test_roots: list[str],
) -> tuple[bool, list[str]]:
    violations = []
    for path in paths:
        if not is_under_any_root(path, allowed_test_roots):
            violations.append(path)
    return len(violations) == 0, violations


def _collect_permission_targets(repo_root: Path) -> list[Path]:
    items = []
    for path in repo_root.rglob("*"):
        rel = path.relative_to(repo_root).as_posix()
        if rel == ".git" or rel.startswith(".git/"):
            continue
        items.append(path)
    items.sort(key=lambda p: len(p.relative_to(repo_root).as_posix().split("/")))
    return items


def lock_repo_to_test_writes(
    *,
    workspace_repo: Path,
    allowed_test_roots: list[str],
    state_path: Path,
) -> dict:
    extra_writable_roots = [".artifacts"]
    writable_roots = allowed_test_roots + extra_writable_roots
    state = {"locked": [], "writable_roots": writable_roots}

    for path in _collect_permission_targets(workspace_repo):
        rel = path.relative_to(workspace_repo).as_posix()
        if is_under_any_root(rel, writable_roots):
            continue
        try:
            current_mode = stat.S_IMODE(path.stat().st_mode)
            new_mode = current_mode & ~stat.S_IWUSR
            if new_mode != current_mode:
                os.chmod(path, new_mode)
                state["locked"].append(
                    {
                        "path": rel,
                        "mode_before": current_mode,
                        "mode_after": new_mode,
                    }
                )
        except FileNotFoundError:
            continue

    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2))
    return state


def restore_repo_permissions(
    *,
    workspace_repo: Path,
    state_path: Path,
) -> dict:
    if not state_path.is_file():
        return {"restored": 0, "missing_state": True}

    state = json.loads(state_path.read_text())
    restored = 0
    for item in reversed(state.get("locked", [])):
        path = workspace_repo / item["path"]
        if not path.exists():
            continue
        os.chmod(path, item["mode_before"])
        restored += 1
    return {"restored": restored, "missing_state": False}