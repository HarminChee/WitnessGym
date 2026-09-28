from __future__ import annotations

import subprocess
import hashlib
from dataclasses import dataclass
from pathlib import Path


@dataclass
class RepoAuditResult:
    modified_files: list[str]
    modified_production_files: list[str]
    forbidden_non_test_changes: list[str]


def _git_diff_name_only(workspace_repo: Path) -> list[str]:
    completed = subprocess.run(
        ["git", "diff", "HEAD", "--name-only", "-z"],
        cwd=str(workspace_repo),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr)
    untracked = subprocess.run(["git", "ls-files", "--others", "--exclude-standard", "-z"],
        cwd=workspace_repo, text=True, capture_output=True, check=True)
    return sorted(set(x for x in (completed.stdout + untracked.stdout).split('\0') if x))


def _snapshot(workspace_repo: Path) -> dict[str, str]:
    result = {}
    for path in workspace_repo.rglob('*'):
        rel = path.relative_to(workspace_repo)
        if any(p in {'.git', 'target', 'build', '__pycache__'} for p in rel.parts):
            continue
        if path.is_symlink():
            raise ValueError('Symlinks are not permitted in an evaluation workspace')
        if path.is_file():
            result[rel.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def _within(path: str, roots: list[str]) -> bool:
    return any('/' + root.strip('/') + '/' in '/' + path for root in roots if root.strip('/'))


def capture_repo_diff_baseline(
    *,
    workspace_repo: Path,
) -> dict[str, str]:
    return _snapshot(workspace_repo)


def audit_repo_changes(
    *,
    workspace_repo: Path,
    allowed_test_roots: list[str],
    protected_prod_roots: list[str],
    baseline_modified_files: dict[str, str] | None = None,
) -> RepoAuditResult:
    if baseline_modified_files is None:
        incremental = _git_diff_name_only(workspace_repo)
    elif not isinstance(baseline_modified_files, dict):
        raise ValueError('A content-hash baseline is required; filename-only baselines are unsafe')
    else:
        current = _snapshot(workspace_repo)
        incremental = sorted(p for p in current.keys() | baseline_modified_files.keys()
            if current.get(p) != baseline_modified_files.get(p))

    modified_production_files = []
    forbidden_non_test_changes = []

    normalized_allowed = [x.rstrip("/") + "/" for x in allowed_test_roots]
    normalized_protected = [x.rstrip("/") + "/" for x in protected_prod_roots]

    for path in incremental:
        if _within(path, protected_prod_roots):
            modified_production_files.append(path)
        if not _within(path, allowed_test_roots):
            forbidden_non_test_changes.append(path)

    return RepoAuditResult(
        modified_files=incremental,
        modified_production_files=modified_production_files,
        forbidden_non_test_changes=forbidden_non_test_changes,
    )
