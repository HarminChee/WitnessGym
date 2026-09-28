from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.common.proc import run_cmd

@dataclass(frozen=True)
class VerifyReport:
    cmd: list[str]
    returncode: int
    stdout: str
    stderr: str
    timeout_s: int | None

def run_verify(repo_root: str | Path, cmd: list[str], timeout_s: int | None) -> VerifyReport:
    r = run_cmd(cmd, cwd=repo_root, timeout_s=timeout_s)
    return VerifyReport(cmd=list(cmd), returncode=int(r.returncode), stdout=r.stdout, stderr=r.stderr, timeout_s=timeout_s)
