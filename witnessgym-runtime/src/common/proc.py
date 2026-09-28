from __future__ import annotations

import os
import subprocess
import signal
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from .errors import WitnessGymError

@dataclass(frozen=True)
class ProcResult:
    cmd: list[str]
    returncode: int
    stdout: str
    stderr: str
    cwd: str | None

def _to_text(x: object) -> str:
    if x is None:
        return ""
    if isinstance(x, bytes):
        return x.decode("utf-8", errors="replace")
    return str(x)

def run_cmd(cmd: Sequence[str], cwd: str | Path | None = None, timeout_s: int | None = None, env: dict[str, str] | None = None) -> ProcResult:
    c = [str(x) for x in cmd]
    e = os.environ.copy()
    if env:
        e.update(env)

    cwd_str = str(cwd) if cwd is not None else None

    try:
        child = subprocess.Popen(
            c,
            cwd=cwd_str,
            env=e,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=os.name == 'posix',
        )
        try:
            stdout, stderr = child.communicate(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            if os.name == 'posix':
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            else:
                child.kill()
            stdout, stderr = child.communicate()
            return ProcResult(list(c), 124, stdout or '', stderr or '', cwd_str)
        return ProcResult(
            cmd=list(c),
            returncode=int(child.returncode),
            stdout=stdout or "",
            stderr=stderr or "",
            cwd=cwd_str,
        )
    except subprocess.TimeoutExpired as te:
        return ProcResult(
            cmd=list(c),
            returncode=124,
            stdout=_to_text(getattr(te, "stdout", "")),
            stderr=_to_text(getattr(te, "stderr", "")),
            cwd=cwd_str,
        )
    except Exception as ex:
        return ProcResult(
            cmd=list(c),
            returncode=127,
            stdout="",
            stderr=_to_text(ex),
            cwd=cwd_str,
        )

def run_cmd_checked(cmd: Sequence[str], cwd: str | Path | None = None, timeout_s: int | None = None, env: dict[str, str] | None = None) -> ProcResult:
    r = run_cmd(cmd, cwd=cwd, timeout_s=timeout_s, env=env)
    if r.returncode != 0:
        raise WitnessGymError(f"Command failed: {r.cmd} rc={r.returncode}\n{r.stdout}\n{r.stderr}")
    return r

def run_checked(cmd: Sequence[str], cwd: str | Path | None = None, timeout_s: int | None = None, env: dict[str, str] | None = None) -> ProcResult:
    return run_cmd_checked(cmd, cwd=cwd, timeout_s=timeout_s, env=env)
