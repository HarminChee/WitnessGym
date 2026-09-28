from __future__ import annotations

import shutil
import subprocess
import re
from pathlib import Path

from .types import WorkspaceLayout


def _safe_group_name(group: str) -> str:
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', group):
        raise ValueError('Run and group identifiers must be safe path components')
    return group


def _relative_file(root: Path, name: str) -> Path:
    p = Path(name)
    if not name or p.is_absolute() or '..' in p.parts or '\\' in name:
        raise ValueError('Expected a repository-relative test path')
    result = root / p
    if not result.resolve().is_relative_to(root.resolve()) or result.is_symlink():
        raise ValueError('Test path escapes the repository')
    return result


def prepare_case_workspace(
    *,
    repo_template: Path,
    out_root: Path,
    run_id: str,
    group: str,
) -> WorkspaceLayout:
    case_dir = out_root / f"{_safe_group_name(run_id)}__{_safe_group_name(group)}"
    if case_dir.resolve().is_relative_to(repo_template.resolve()):
        raise ValueError('Output must not be inside the repository template')
    workspace_repo = case_dir / "workspace_repo"
    context_dir = case_dir / "context"
    agent_dir = case_dir / "agent"
    generated_tests_dir = case_dir / "generated_tests"
    verify_dir = case_dir / "verify"

    if case_dir.exists():
        raise FileExistsError('Run directory already exists; use a fresh run identifier')

    case_dir.mkdir(parents=True, exist_ok=True)
    context_dir.mkdir(parents=True, exist_ok=True)
    agent_dir.mkdir(parents=True, exist_ok=True)
    generated_tests_dir.mkdir(parents=True, exist_ok=True)
    verify_dir.mkdir(parents=True, exist_ok=True)

    shutil.copytree(repo_template, workspace_repo)

    return WorkspaceLayout(
        case_dir=case_dir,
        workspace_repo=workspace_repo,
        context_dir=context_dir,
        agent_dir=agent_dir,
        generated_tests_dir=generated_tests_dir,
        verify_dir=verify_dir,
    )


def overlay_buggy_repo(
    *,
    workspace_repo: Path,
    buggy_repo: Path,
) -> dict:
    if not buggy_repo.is_dir():
        raise FileNotFoundError(f"Missing buggy repo dir: {buggy_repo}")
    if any(p.is_symlink() for p in buggy_repo.rglob('*')):
        raise ValueError('Symlinks are not permitted in a buggy repository overlay')

    completed = subprocess.run(
        ["rsync", "-a", str(buggy_repo) + "/", str(workspace_repo) + "/"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    diff = subprocess.run(
        ["git", "diff", "--name-only"],
        cwd=str(workspace_repo),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    return {
        "buggy_repo": str(buggy_repo),
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "diff_name_only": diff.stdout.splitlines(),
    }


def restore_official_test(
    *,
    repo_template: Path,
    workspace_repo: Path,
    official_test_path: str,
) -> dict:
    src = _relative_file(repo_template, official_test_path)
    dst = _relative_file(workspace_repo, official_test_path)

    if not src.is_file():
        return {
            "ok": False,
            "src": str(src),
            "dst": str(dst),
            "reason": "missing_official_test_in_repo_template",
        }

    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)

    return {
        "ok": True,
        "src": str(src),
        "dst": str(dst),
    }
