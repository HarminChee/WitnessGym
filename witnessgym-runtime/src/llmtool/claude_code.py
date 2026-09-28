from __future__ import annotations
from src.common.proc_utils import python_bin

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.common.proc import run_cmd
from src.common.errors import LLMError
from src.common.io_utils import ensure_dir, write_text, read_json

def project_root() -> Path:
    return Path(__file__).resolve().parents[2]

def resolve_runner(runner_script: str | Path) -> Path:
    p = Path(runner_script)
    if p.is_absolute() and p.exists():
        return p
    root = project_root()
    cand1 = (root / p).resolve()
    if cand1.exists():
        return cand1
    cand2 = (root / "scripts" / "run_claude_headless.py").resolve()
    if cand2.exists():
        return cand2
    raise LLMError(f"Claude headless runner not found: {runner_script}")

def extract_json_report(text: str, prefix: str) -> dict[str, Any] | None:
    for line in (text or "").splitlines():
        t = line.strip()
        if not t.startswith(prefix):
            continue
        payload = t[len(prefix):].strip()
        if not payload:
            continue
        try:
            obj = json.loads(payload)
            if isinstance(obj, dict):
                return obj
        except Exception:
            continue
    return None

@dataclass(frozen=True)
class ClaudeRun:
    output_json: Path
    returncode: int
    stdout: str
    stderr: str
    payload: dict[str, Any] | None
    parsed_reports: dict[str, Any]

class ClaudeCodeHeadless:
    def __init__(self, repo_root: str | Path, runner_script: str | Path):
        self.repo_root = Path(repo_root).resolve()
        self.runner_script = resolve_runner(runner_script)

    def run(self, system_prompt: str, task_prompt: str, out_dir: str | Path, name: str) -> ClaudeRun:
        od = ensure_dir(out_dir)
        sys_path = (od / f"{name}.system.txt").resolve()
        task_path = (od / f"{name}.task.txt").resolve()
        out_json = (od / f"{name}.claude.json").resolve()
        write_text(sys_path, system_prompt + "\n")
        write_text(task_path, task_prompt + "\n")

        cmd = [
            python_bin(),
            str(self.runner_script),
            "--repo", str(self.repo_root),
            "--system", str(sys_path),
            "--task", str(task_path),
            "--out", str(out_json),
        ]

        r = run_cmd(cmd, cwd=self.repo_root)

        payload = None
        parsed_reports: dict[str, Any] = {}
        if out_json.exists():
            try:
                obj = read_json(out_json)
                if isinstance(obj, dict):
                    payload = obj
            except Exception:
                payload = None

        stdout_text = ""
        stderr_text = ""
        if isinstance(payload, dict):
            stdout_text = str(payload.get("stdout", "") or "")
            stderr_text = str(payload.get("stderr", "") or "")
            result_text = str(payload.get("result", "") or "")

            inner_obj = None
            if stdout_text.strip():
                try:
                    maybe = json.loads(stdout_text)
                    if isinstance(maybe, dict):
                        inner_obj = maybe
                except Exception:
                    inner_obj = None

            search_texts = []
            if stdout_text.strip():
                search_texts.append(stdout_text)
            if result_text.strip():
                search_texts.append(result_text)

            if isinstance(inner_obj, dict):
                inner_result = str(inner_obj.get("result", "") or "")
                inner_stdout = str(inner_obj.get("stdout", "") or "")
                inner_stderr = str(inner_obj.get("stderr", "") or "")
                if inner_result.strip():
                    search_texts.append(inner_result)
                if inner_stdout.strip():
                    search_texts.append(inner_stdout)
                if inner_stderr.strip():
                    search_texts.append(inner_stderr)

            merged = "\n".join([x for x in search_texts if x.strip()])

            inject_report = extract_json_report(merged, "INJECT_REPORT_JSON:")
            transform_report = extract_json_report(merged, "TRANSFORM_REPORT_JSON:")
            detect_report = extract_json_report(merged, "DETECT_REPORT_JSON:")

            if inject_report is not None:
                parsed_reports["inject_report"] = inject_report
            if transform_report is not None:
                parsed_reports["transform_report"] = transform_report
            if detect_report is not None:
                parsed_reports["detect_report"] = detect_report

        return ClaudeRun(
            output_json=out_json,
            returncode=r.returncode,
            stdout=r.stdout,
            stderr=r.stderr,
            payload=payload,
            parsed_reports=parsed_reports,
        )

    def run_checked(self, system_prompt: str, task_prompt: str, out_dir: str | Path, name: str) -> ClaudeRun:
        rr = self.run(system_prompt, task_prompt, out_dir, name)
        if rr.returncode != 0:
            raise LLMError(f"Claude headless failed rc={rr.returncode}\n{rr.stdout}\n{rr.stderr}")
        return rr
