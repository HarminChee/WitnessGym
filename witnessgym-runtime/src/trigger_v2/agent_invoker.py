from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import time
from pathlib import Path

from src.trigger_v2.types import AgentRunResult


def _read_if_exists(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(errors="ignore")


def _pick_first_existing(base_dir: Path, candidates: list[str]) -> Path | None:
    for name in candidates:
        path = base_dir / name
        if path.exists():
            return path
    return None


def _extract_trigger_report_from_text(text: str) -> dict:
    if not text:
        return {}

    marker = "TRIGGER_REPORT_JSON:"
    idx = text.rfind(marker)
    if idx < 0:
        return {}

    tail = text[idx + len(marker):].strip()
    start = tail.find("{")
    if start < 0:
        return {}

    brace = 0
    end = None
    for i, ch in enumerate(tail[start:]):
        if ch == "{":
            brace += 1
        elif ch == "}":
            brace -= 1
            if brace == 0:
                end = start + i + 1
                break

    if end is None:
        return {}

    candidate = tail[start:end].strip()

    for attempt in [
        candidate,
        bytes(candidate, "utf-8").decode("unicode_escape"),
        candidate.replace('\\\"', '"').replace("\\n", "\n").replace("\\t", "\t"),
    ]:
        try:
            return json.loads(attempt)
        except Exception:
            pass

    return {}


def _extract_text_from_llm_json(path: Path) -> str:
    if not path.exists():
        return ""

    try:
        payload = json.loads(path.read_text(errors="ignore"))
    except Exception:
        return ""

    parts = []
    for key in ["stdout", "result", "stderr"]:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            parts.append(value)

    return "\n\n".join(parts)


def run_agent(
    *,
    runner_script: Path,
    workspace_repo: Path,
    system_prompt_path: Path,
    task_prompt_path: Path,
    allowed_tools: str,
    env_overrides: dict[str, str],
    timeout_s: int,
    out_dir: Path,
) -> AgentRunResult:
    out_dir.mkdir(parents=True, exist_ok=True)

    llm_stdout_fallback = out_dir / "llm.stdout.txt"
    llm_stderr_fallback = out_dir / "llm.stderr.txt"
    llm_result_fallback = out_dir / "llm.result.txt"
    llm_json_fallback = out_dir / "llm.claude.json"

    parse_source = out_dir / "trigger.parse_source.txt"
    trigger_report_path = out_dir / "trigger.report.json"
    agent_runner_stdout = out_dir / "agent_runner.stdout.txt"
    agent_runner_stderr = out_dir / "agent_runner.stderr.txt"

    cmd = [
        "python3",
        str(runner_script),
        "--repo",
        str(workspace_repo),
        "--system",
        str(system_prompt_path),
        "--task",
        str(task_prompt_path),
        "--out",
        str(llm_json_fallback),
        "--timeout-s",
        str(timeout_s),
        "--tools",
        allowed_tools,
    ]

    env = os.environ.copy()
    env.update(env_overrides)

    process = subprocess.Popen(
        cmd,
        cwd=str(workspace_repo),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )

    try:
        stdout, stderr = process.communicate(timeout=timeout_s)
        completed = subprocess.CompletedProcess(
            args=cmd,
            returncode=int(process.returncode) if process.returncode is not None else 0,
            stdout=stdout or "",
            stderr=stderr or "",
        )
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except Exception:
            pass
        time.sleep(2)
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except Exception:
            pass
        stdout, stderr = process.communicate()
        completed = subprocess.CompletedProcess(
            args=cmd,
            returncode=124,
            stdout=stdout or "",
            stderr=(stderr or "") + f"\n[agent_invoker_timeout] timeout_s={timeout_s}\n",
        )

    agent_runner_stdout.write_text(completed.stdout)
    agent_runner_stderr.write_text(completed.stderr)

    llm_stdout = _pick_first_existing(out_dir, ["llm.stdout.txt", "stdout.txt"])
    llm_stderr = _pick_first_existing(out_dir, ["llm.stderr.txt", "stderr.txt"])
    llm_result = _pick_first_existing(out_dir, ["llm.result.txt", "result.txt"])
    llm_json = _pick_first_existing(out_dir, ["llm.claude.json", "claude.json", "response.json"])

    json_text = _extract_text_from_llm_json(llm_json or llm_json_fallback)

    combined_text = "\n\n".join(
        [
            _read_if_exists(agent_runner_stdout),
            _read_if_exists(agent_runner_stderr),
            _read_if_exists(llm_result) if llm_result else "",
            _read_if_exists(llm_stdout) if llm_stdout else "",
            _read_if_exists(llm_stderr) if llm_stderr else "",
            json_text,
        ]
    )

    parse_source.write_text(combined_text)
    trigger_report = _extract_trigger_report_from_text(combined_text)
    trigger_report_path.write_text(json.dumps(trigger_report, indent=2))

    return AgentRunResult(
        returncode=completed.returncode,
        stdout_path=llm_stdout or llm_stdout_fallback,
        stderr_path=llm_stderr or llm_stderr_fallback,
        result_path=llm_result or llm_result_fallback,
        json_path=llm_json or llm_json_fallback,
        parse_source_path=parse_source,
        trigger_report_path=trigger_report_path,
        runner_stdout_path=agent_runner_stdout,
        runner_stderr_path=agent_runner_stderr,
        trigger_report=trigger_report,
    )
