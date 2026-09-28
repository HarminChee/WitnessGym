import argparse
import asyncio
import json
import os
import subprocess
import sys
import time
import traceback
import uuid
from pathlib import Path
from typing import Any


DEFAULT_OPENHANDS_ROOT = Path(os.environ.get("OPENHANDS_ROOT", "OpenHands")).expanduser()
DEFAULT_VENV_PYTHON = Path(os.environ.get("OPENHANDS_VENV_PYTHON", "")).expanduser()
DEFAULT_MODEL = "bedrock/google.gemma-3-27b-it"


def _ensure_openhands_python() -> None:
    """agent_invoker launches runner scripts with python3; re-exec into the OpenHands venv."""
    if str(DEFAULT_VENV_PYTHON) and DEFAULT_VENV_PYTHON.exists() and Path(sys.executable) != DEFAULT_VENV_PYTHON:
        os.execv(str(DEFAULT_VENV_PYTHON), [str(DEFAULT_VENV_PYTHON), *sys.argv])


_ensure_openhands_python()


def _normalize_bedrock_model(model: str | None) -> str:
    raw = (model or "").strip()
    if not raw:
        return DEFAULT_MODEL
    if raw.startswith("amazon-bedrock/"):
        return "bedrock/" + raw.split("/", 1)[1]
    return raw


def _run_git(repo: Path, args: list[str]) -> str:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=str(repo),
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        return completed.stdout or ""
    except Exception:
        return ""


def _json_safe(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, tuple):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, Path):
        return str(obj)
    try:
        json.dumps(obj)
        return obj
    except TypeError:
        return repr(obj)


def _event_text(event: Any) -> str:
    if isinstance(event, dict):
        parts = []
        for key in ("content", "thought", "command", "message", "error"):
            value = event.get(key)
            if isinstance(value, str) and value.strip():
                parts.append(value)
        for key in ("args", "observation", "extras"):
            value = event.get(key)
            if isinstance(value, dict):
                parts.append(_event_text(value))
        return "\n".join(part for part in parts if part)
    if isinstance(event, list):
        return "\n".join(_event_text(x) for x in event)
    return ""


def _history_to_dicts(history: Any, event_to_dict: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in history or []:
        if isinstance(item, dict):
            rows.append(_json_safe(item))
            continue
        try:
            rows.append(_json_safe(event_to_dict(item)))
        except Exception:
            rows.append({"repr": repr(item)})
    return rows


def _extract_last_json_object(text: str) -> dict[str, Any]:
    starts = [idx for idx, ch in enumerate(text) if ch == "{"]
    for start in reversed(starts):
        depth = 0
        in_str = False
        escape = False
        for idx in range(start, len(text)):
            ch = text[idx]
            if in_str:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start : idx + 1]
                    try:
                        payload = json.loads(candidate)
                    except Exception:
                        break
                    if isinstance(payload, dict):
                        return payload
                    break
    return {}


def _normalize_trigger_report_text(text: str) -> str:
    if "TRIGGER_REPORT_JSON:" in text:
        return text
    payload = _extract_last_json_object(text)
    if not payload:
        return text
    report_like_keys = {
        "ok",
        "summary",
        "materialized_test_files",
        "selected_test_path",
        "trigger_strategy",
    }
    if not (report_like_keys & set(payload)):
        return text
    return text.rstrip() + "\n\nTRIGGER_REPORT_JSON: " + json.dumps(payload, ensure_ascii=False) + "\n"


async def _run_openhands(
    *,
    repo: Path,
    prompt: str,
    model: str,
    aws_region: str,
    runtime: str,
    max_iterations: int,
    timeout_s: int,
    out_dir: Path,
) -> tuple[int, dict[str, Any], str]:
    openhands_root = Path(os.environ.get("OPENHANDS_ROOT", str(DEFAULT_OPENHANDS_ROOT))).resolve()
    if str(openhands_root) not in sys.path:
        sys.path.insert(0, str(openhands_root))

    import openhands.agenthub  # noqa: F401
    from openhands.core.config import AgentConfig, LLMConfig, OpenHandsConfig, SandboxConfig
    from openhands.core.main import run_controller
    from openhands.events.action import MessageAction
    from openhands.events.serialization.event import event_to_dict
    from openhands.resolver.utils import codeact_user_response

    sid = f"witnessgym-openhands-{uuid.uuid4().hex[:12]}"
    file_store_path = out_dir / "openhands_file_store"
    file_store_path.mkdir(parents=True, exist_ok=True)
    cache_dir = out_dir / "openhands_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    config = OpenHandsConfig(
        default_agent="CodeActAgent",
        runtime=runtime,
        file_store="local",
        file_store_path=str(file_store_path),
        enable_browser=False,
        workspace_base=str(repo),
        workspace_mount_path_in_sandbox=str(repo),
        cache_dir=str(cache_dir),
        run_as_openhands=False,
        max_iterations=max_iterations,
        debug=False,
    )
    config.set_llm_config(
        LLMConfig(
            model=model,
            aws_region_name=aws_region,
            num_retries=2,
            retry_min_wait=3,
            retry_max_wait=20,
            timeout=timeout_s,
            temperature=0,
            max_output_tokens=4096,
            disable_vision=True,
            disable_stop_word=True,
            native_tool_calling=False,
            drop_params=True,
            modify_params=True,
        )
    )
    config.set_agent_config(
        AgentConfig(
            enable_browsing=False,
            enable_jupyter=False,
            enable_mcp=False,
            enable_llm_editor=False,
            enable_editor=True,
            enable_cmd=True,
            enable_finish=True,
            enable_plan_mode=False,
            runtime=runtime,
        )
    )
    config.sandbox = SandboxConfig(
        timeout=max(120, timeout_s),
        runtime_startup_env_vars={
            "AWS_REGION": aws_region,
            "AWS_DEFAULT_REGION": aws_region,
            "AWS_PROFILE": os.environ.get("AWS_PROFILE", "default"),
        },
        trusted_dirs=[str(repo)],
    )

    state = await asyncio.wait_for(
        run_controller(
            config=config,
            initial_user_action=MessageAction(content=prompt),
            sid=sid,
            headless_mode=True,
            fake_user_response_fn=codeact_user_response,
        ),
        timeout=timeout_s,
    )

    history = _history_to_dicts(getattr(state, "history", []) if state else [], event_to_dict)
    agent_rows = [
        row
        for row in history
        if row.get("source") == "agent" and row.get("action") != "system"
    ]
    result_text = "\n\n".join(_event_text(row) for row in agent_rows if _event_text(row).strip())
    result_text = _normalize_trigger_report_text(result_text)
    payload = {
        "sid": sid,
        "agent_state": repr(getattr(state, "agent_state", None)) if state else None,
        "last_error": str(getattr(state, "last_error", "") or "") if state else "",
        "metrics": _json_safe(getattr(state, "metrics", None)) if state else None,
        "history": history,
    }
    agent_state_text = repr(getattr(state, "agent_state", None)) if state else ""
    last_error = str(getattr(state, "last_error", "") or "") if state else ""
    returncode = 1 if "ERROR" in agent_state_text or last_error else 0
    return returncode, payload, result_text


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--system", required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--timeout-s", type=int, default=None)
    parser.add_argument("--tools", default="Read,Glob,Grep,LS,View,Bash,Edit,MultiEdit,Write")
    parser.add_argument("--model", default=None)
    parser.add_argument("--aws-region", default=os.environ.get("AWS_REGION", "us-west-2"))
    parser.add_argument("--aws-profile", default=os.environ.get("AWS_PROFILE", "default"))
    parser.add_argument("--runtime", default=os.environ.get("OPENHANDS_RUNTIME", "cli"))
    parser.add_argument("--max-iterations", type=int, default=int(os.environ.get("OPENHANDS_MAX_ITERATIONS", "50")))
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    system_path = Path(args.system).resolve()
    task_path = Path(args.task).resolve()
    out_path = Path(args.out).resolve()
    out_dir = out_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    timeout_s = args.timeout_s or int(os.environ.get("OPENHANDS_TIMEOUT_S", "1800"))
    model = _normalize_bedrock_model(
        args.model
        or os.environ.get("OPENHANDS_MODEL")
        or os.environ.get("ANTHROPIC_MODEL")
        or os.environ.get("BEDROCK_MODEL_ID")
    )
    if not model.startswith("bedrock/"):
        raise SystemExit(f"Refusing non-Bedrock OpenHands model: {model}")

    for key in [
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "DEEPSEEK_API_KEY",
        "MOONSHOT_API_KEY",
        "MINIMAX_API_KEY",
        "OPENROUTER_API_KEY",
        "CODEX_API_KEY",
        "GOOGLE_API_KEY",
    ]:
        os.environ.pop(key, None)
    os.environ["AWS_REGION"] = args.aws_region
    os.environ["AWS_DEFAULT_REGION"] = args.aws_region
    os.environ["AWS_REGION_NAME"] = args.aws_region
    if args.aws_profile:
        os.environ["AWS_PROFILE"] = args.aws_profile
    os.environ["DESIRED_NUM_WARM_SERVERS"] = "0"
    os.environ["LOCAL_WORKSPACE_BASE"] = str(repo)
    os.environ["LITELLM_LOG"] = "ERROR"

    stdout_path = out_dir / "llm.stdout.txt"
    stderr_path = out_dir / "llm.stderr.txt"
    result_path = out_dir / "llm.result.txt"
    history_path = out_dir / "openhands.history.json"
    prompt_path = out_dir / "openhands_prompt.txt"

    system_text = system_path.read_text(encoding="utf-8", errors="ignore")
    task_text = task_path.read_text(encoding="utf-8", errors="ignore")
    prompt = "\n\n".join(
        [
            "SYSTEM INSTRUCTIONS:",
            system_text,
            "TASK INSTRUCTIONS:",
            task_text,
            "Runner note: you are running through OpenHands CodeActAgent. Directly edit files in this repository. Do not wait for human approval. At the end, print the required TRIGGER_REPORT_JSON line.",
            f"Runner path note: your current working directory is exactly {repo}. Use relative paths from this directory, such as module/src/test/java/..., and do not prefix paths with /workspace_repo or /workspace.",
        ]
    )
    prompt_path.write_text(prompt, encoding="utf-8")

    pre_status = _run_git(repo, ["status", "--porcelain=v1", "-uno"])
    pre_diff = _run_git(repo, ["diff"])

    start = time.time()
    returncode = 0
    stderr = ""
    result_text = ""
    state_payload: dict[str, Any] = {}
    try:
        returncode, state_payload, result_text = asyncio.run(
            _run_openhands(
                repo=repo,
                prompt=prompt,
                model=model,
                aws_region=args.aws_region,
                runtime=args.runtime,
                max_iterations=args.max_iterations,
                timeout_s=timeout_s,
                out_dir=out_dir,
            )
        )
    except asyncio.TimeoutError:
        returncode = 124
        stderr = f"[openhands_timeout] timeout_s={timeout_s}\n"
    except Exception as exc:
        returncode = 1
        stderr = f"{type(exc).__name__}: {exc}\n\n{traceback.format_exc()}"

    stdout_path.write_text("", encoding="utf-8")
    stderr_path.write_text(stderr, encoding="utf-8", errors="ignore")
    result_path.write_text(result_text or "", encoding="utf-8", errors="ignore")
    history_path.write_text(json.dumps(_json_safe(state_payload), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    post_status = _run_git(repo, ["status", "--porcelain=v1", "-uno"])
    post_diff = _run_git(repo, ["diff"])

    payload = {
        "cmd": [str(DEFAULT_VENV_PYTHON), *sys.argv],
        "cwd": str(repo),
        "returncode": returncode,
        "stdout": "",
        "stderr": stderr,
        "result": result_text or "",
        "timeout_s": timeout_s,
        "elapsed_s": round(time.time() - start, 3),
        "pre_git_status": pre_status,
        "pre_git_diff": pre_diff,
        "post_git_status": post_status,
        "post_git_diff": post_diff,
        "env": {
            "OPENHANDS_MODEL": model,
            "OPENHANDS_RUNTIME": args.runtime,
            "OPENHANDS_ROOT": str(os.environ.get("OPENHANDS_ROOT", DEFAULT_OPENHANDS_ROOT)),
            "AWS_REGION": os.environ.get("AWS_REGION"),
            "AWS_PROFILE": os.environ.get("AWS_PROFILE"),
            "OPENAI_API_KEY_PRESENT": bool(os.environ.get("OPENAI_API_KEY")),
            "ANTHROPIC_API_KEY_PRESENT": bool(os.environ.get("ANTHROPIC_API_KEY")),
            "GOOGLE_API_KEY_PRESENT": bool(os.environ.get("GOOGLE_API_KEY")),
        },
        "openhands_history_path": str(history_path),
    }
    out_path.write_text(json.dumps(_json_safe(payload), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"Return code: {returncode}")
    raise SystemExit(returncode)


if __name__ == "__main__":
    main()
