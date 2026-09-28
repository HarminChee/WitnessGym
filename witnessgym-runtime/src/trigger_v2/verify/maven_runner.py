from __future__ import annotations

import json
from pathlib import Path

from ...common.proc import run_cmd

from ..types import VerifyResult


def run_maven_verify(
    *,
    workspace_repo: Path,
    verify_cmd: list[str],
    timeout_s: int,
    out_dir: Path,
) -> VerifyResult:
    out_dir.mkdir(parents=True, exist_ok=True)

    stdout_path = out_dir / "verify.stdout.txt"
    stderr_path = out_dir / "verify.stderr.txt"
    summary_path = out_dir / "verify.summary.json"

    completed = run_cmd(verify_cmd, cwd=workspace_repo, timeout_s=timeout_s)
    verify_rc = completed.returncode
    stdout_text = completed.stdout
    stderr_text = completed.stderr

    stdout_path.write_text(stdout_text)
    stderr_path.write_text(stderr_text)
    summary_path.write_text(
        json.dumps(
            {
                "verify_rc": verify_rc,
                "verify_cmd": verify_cmd,
                "verify_cmd_display": " ".join(verify_cmd),
                "timeout_s": timeout_s,
            },
            indent=2,
        )
    )

    return VerifyResult(
        verify_rc=verify_rc,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        summary_path=summary_path,
    )
