from __future__ import annotations

import json
from pathlib import Path

from ...common.proc import run_cmd

from ..types import SpotlessResult


def run_spotless(
    *,
    workspace_repo: Path,
    modules: list[str],
    timeout_s: int,
    out_dir: Path,
) -> SpotlessResult:
    out_dir.mkdir(parents=True, exist_ok=True)

    stdout_path = out_dir / "spotless.stdout.txt"
    stderr_path = out_dir / "spotless.stderr.txt"
    summary_path = out_dir / "spotless.summary.json"

    if modules:
        cmd = ["./mvnw", "-q"]
        for module in modules:
            cmd.extend(["-pl", module])
        cmd.append("spotless:apply")
    else:
        cmd = ["./mvnw", "-q", "spotless:apply"]

    completed = run_cmd(cmd, cwd=workspace_repo, timeout_s=timeout_s)
    spotless_rc = completed.returncode
    stdout_text = completed.stdout
    stderr_text = completed.stderr

    stdout_path.write_text(stdout_text)
    stderr_path.write_text(stderr_text)
    summary_path.write_text(
        json.dumps(
            {
                "spotless_rc": spotless_rc,
                "spotless_modules": modules,
                "spotless_cmd": cmd,
                "spotless_cmd_display": " ".join(cmd),
                "timeout_s": timeout_s,
            },
            indent=2,
        )
    )

    return SpotlessResult(
        spotless_rc=spotless_rc,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        summary_path=summary_path,
    )
