import argparse
import json
import os
import signal
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any


DEFAULT_MODEL = "amazon-bedrock/moonshotai.kimi-k2.5"


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


def _collect_strings_with_keys(obj: Any, keys: set[str], out: list[str]) -> None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in keys and isinstance(value, str) and value.strip():
                out.append(value)
            else:
                _collect_strings_with_keys(value, keys, out)
    elif isinstance(obj, list):
        for item in obj:
            _collect_strings_with_keys(item, keys, out)


def _extract_text_from_jsonl(stdout: str) -> str:
    parts: list[str] = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            parts.append(line)
            continue
        _collect_strings_with_keys(
            obj,
            {"text", "content", "message", "output"},
            parts,
        )
    return "\n".join(part for part in parts if part.strip())


def _build_opencode_env(*, model: str, aws_region: str, aws_profile: str | None) -> dict[str, str]:
    env = os.environ.copy()

    # Force the experiment away from personal direct-provider APIs.
    for key in [
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "DEEPSEEK_API_KEY",
        "MOONSHOT_API_KEY",
        "MINIMAX_API_KEY",
        "OPENROUTER_API_KEY",
        "CODEX_API_KEY",
        "ANTHROPIC_MODEL",
        "CLAUDE_CODE_USE_BEDROCK",
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC",
    ]:
        env.pop(key, None)

    if env.get("AWS_BEARER_TOKEN_BEDROCK") and env.get("OPENCODE_ALLOW_BEDROCK_BEARER") != "1":
        env.pop("AWS_BEARER_TOKEN_BEDROCK", None)

    env["AWS_REGION"] = aws_region
    env["AWS_DEFAULT_REGION"] = aws_region
    if aws_profile:
        env["AWS_PROFILE"] = aws_profile

    env["OPENCODE_DISABLE_AUTOUPDATE"] = "1"
    env["OPENCODE_DISABLE_CLAUDE_CODE"] = "1"
    env["OPENCODE_DISABLE_CLAUDE_CODE_PROMPT"] = "1"
    env["OPENCODE_DISABLE_CLAUDE_CODE_SKILLS"] = "1"

    config = {
        "$schema": "https://opencode.ai/config.json",
        "model": model,
        "provider": {
            "amazon-bedrock": {
                "options": {
                    "region": aws_region,
                    **({"profile": aws_profile} if aws_profile else {}),
                }
            }
        },
    }
    env["OPENCODE_CONFIG_CONTENT"] = json.dumps(config, ensure_ascii=False)
    return env


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--system", required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--timeout-s", type=int, default=None)
    parser.add_argument("--tools", default="Read,Glob,Grep,LS,View,Bash,Edit,MultiEdit,Write")
    parser.add_argument("--model", default=os.environ.get("OPENCODE_MODEL", DEFAULT_MODEL))
    parser.add_argument("--aws-region", default=os.environ.get("AWS_REGION", "us-west-2"))
    parser.add_argument("--aws-profile", default=os.environ.get("AWS_PROFILE", "default"))
    args = parser.parse_args()

    if not args.model.startswith("amazon-bedrock/"):
        raise SystemExit(f"Refusing non-Bedrock OpenCode model: {args.model}")

    repo = Path(args.repo).resolve()
    system_path = Path(args.system).resolve()
    task_path = Path(args.task).resolve()
    out_path = Path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    timeout_s = args.timeout_s or int(os.environ.get("OPENCODE_TIMEOUT_S", "1800"))

    stdout_path = out_path.parent / "llm.stdout.txt"
    stderr_path = out_path.parent / "llm.stderr.txt"
    result_path = out_path.parent / "llm.result.txt"
    prompt_path = out_path.parent / "opencode_prompt.txt"

    system_text = system_path.read_text(encoding="utf-8", errors="ignore")
    task_text = task_path.read_text(encoding="utf-8", errors="ignore")

    prompt = "\n\n".join(
        [
            "SYSTEM INSTRUCTIONS:",
            system_text,
            "TASK INSTRUCTIONS:",
            task_text,
        ]
    )
    prompt_path.write_text(prompt, encoding="utf-8")

    opencode_bin = os.environ.get("OPENCODE_BIN") or shutil.which("opencode")
    if not opencode_bin:
        raise SystemExit(
            "opencode binary not found. Install it first, e.g. `curl -fsSL https://opencode.ai/install | bash` "
            "or `npm install -g opencode-ai`."
        )

    cmd = [
        opencode_bin,
        "run",
        "--pure",
        "--dir",
        str(repo),
        "--model",
        args.model,
        "--format",
        "json",
        "--dangerously-skip-permissions",
        "--title",
        "witnessgym-trigger",
        "Follow the attached WITNESSGYM trigger instructions exactly.",
        f"--file={prompt_path}",
    ]

    env = _build_opencode_env(
        model=args.model,
        aws_region=args.aws_region,
        aws_profile=args.aws_profile or None,
    )

    pre_status = _run_git(repo, ["status", "--porcelain=v1", "-uno"])
    pre_diff = _run_git(repo, ["diff"])

    start = time.time()
    process = subprocess.Popen(
        cmd,
        cwd=str(repo),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
        env=env,
    )

    try:
        stdout, stderr = process.communicate(timeout=timeout_s)
        returncode = int(process.returncode) if process.returncode is not None else 0
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
        stdout, stderr = "", f"[opencode_timeout] timeout_s={timeout_s}\n"
        returncode = 124

    result_text = _extract_text_from_jsonl(stdout or "")
    stdout_path.write_text(stdout or "", encoding="utf-8", errors="ignore")
    stderr_path.write_text(stderr or "", encoding="utf-8", errors="ignore")
    result_path.write_text(result_text, encoding="utf-8", errors="ignore")

    post_status = _run_git(repo, ["status", "--porcelain=v1", "-uno"])
    post_diff = _run_git(repo, ["diff"])

    payload = {
        "cmd": cmd,
        "cwd": str(repo),
        "returncode": returncode,
        "stdout": stdout or "",
        "stderr": stderr or "",
        "result": result_text,
        "timeout_s": timeout_s,
        "elapsed_s": round(time.time() - start, 3),
        "pre_git_status": pre_status,
        "pre_git_diff": pre_diff,
        "post_git_status": post_status,
        "post_git_diff": post_diff,
        "env": {
            "OPENCODE_MODEL": args.model,
            "OPENCODE_BIN": opencode_bin,
            "AWS_REGION": env.get("AWS_REGION"),
            "AWS_PROFILE": env.get("AWS_PROFILE"),
            "OPENAI_API_KEY_PRESENT": bool(env.get("OPENAI_API_KEY")),
            "ANTHROPIC_API_KEY_PRESENT": bool(env.get("ANTHROPIC_API_KEY")),
            "AWS_BEARER_TOKEN_BEDROCK_PRESENT": bool(env.get("AWS_BEARER_TOKEN_BEDROCK")),
        },
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"Return code: {returncode}")


if __name__ == "__main__":
    main()
