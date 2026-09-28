from __future__ import annotations

from pathlib import Path
from typing import Optional

from .proc import run_cmd, run_cmd_checked
from .errors import ConfigError

def assert_git_repo(repo: str | Path) -> None:
    r = run_cmd(["git", "rev-parse", "--is-inside-work-tree"], cwd=repo)
    if r.returncode != 0 or "true" not in r.stdout.strip():
        raise ConfigError(f"Not a git repo: {repo}")

def git_is_clean(repo: str | Path) -> bool:
    r = run_cmd_checked(["git", "status", "--porcelain"], cwd=repo)
    return r.stdout.strip() == ""

def git_restore_all(repo: str | Path) -> None:
    run_cmd_checked(["git", "restore", "."], cwd=repo)

def git_diff_patch(repo: str | Path) -> str:
    r = run_cmd_checked(["git", "diff"], cwd=repo)
    return r.stdout

def git_rev(repo: str | Path) -> str:
    r = run_cmd_checked(["git", "rev-parse", "HEAD"], cwd=repo)
    return r.stdout.strip()
