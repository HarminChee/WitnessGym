#!/usr/bin/env python3
import argparse
import json
import os
import shutil
import signal
import subprocess
import time
from pathlib import Path


DEFAULT_MODEL = "gpt-5.1-codex-mini"
CODEX_BIN = "/Applications/Codex.app/Contents/Resources/codex"


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


def _load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _build_prompt(system_text: str, task_text: str) -> str:
    return "\n\n".join(
        [
            "SYSTEM INSTRUCTIONS:",
            system_text,
            "TASK INSTRUCTIONS:",
            task_text,
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--system", required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--timeout-s", type=int, default=None)
    parser.add_argument("--tools", default="")
    parser.add_argument("--model", default=os.environ.get("CODEX_MODEL", DEFAULT_MODEL))
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    system_path = Path(args.system).resolve()
    task_path = Path(args.task).resolve()
    out_path = Path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    timeout_s = args.timeout_s or int(os.environ.get("CODEX_TIMEOUT_S", "1800"))

    stdout_path = out_path.parent / "llm.stdout.txt"
    stderr_path = out_path.parent / "llm.stderr.txt"
    result_path = out_path.parent / "llm.result.txt"
    prompt_path = out_path.parent / "codex_prompt.txt"

    prompt = _build_prompt(_load_text(system_path), _load_text(task_path))
    prompt_path.write_text(prompt, encoding="utf-8")

    codex_bin = os.environ.get("CODEX_BIN") or shutil.which("codex") or CODEX_BIN
    if not codex_bin or not Path(codex_bin).exists():
        raise SystemExit("codex binary not found")

    cmd = [
        codex_bin,
        "exec",
        "--full-auto",
        "--ephemeral",
        "--json",
        "--skip-git-repo-check",
        "-C",
        str(repo),
        "-m",
        args.model,
        "-o",
        str(result_path),
        "-",
    ]

    env = os.environ.copy()
    # Force this path onto OpenAI/Codex rather than any other provider.
    for key in [
        "ANTHROPIC_API_KEY",
        "DEEPSEEK_API_KEY",
        "MOONSHOT_API_KEY",
        "MINIMAX_API_KEY",
        "OPENROUTER_API_KEY",
        "AWS_BEARER_TOKEN_BEDROCK",
        "CLAUDE_CODE_USE_BEDROCK",
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC",
        "ANTHROPIC_MODEL",
        "OPENHANDS_MODEL",
        "OPENHANDS_RUNTIME",
        "OPENCODE_MODEL",
        "OPENCODE_CONFIG_CONTENT",
    ]:
        env.pop(key, None)
    env["CODEX_DISABLE_AUTO_UPDATE"] = "1"
    if os.environ.get("CODEX_FORCE_LOCAL_HOME") == "1":
        codex_home = out_path.parent / "codex_home"
        codex_home.mkdir(parents=True, exist_ok=True)
        home_root = out_path.parent / "home"
        home_root.mkdir(parents=True, exist_ok=True)
        env["CODEX_HOME"] = str(codex_home)
        env["HOME"] = str(home_root)

    pre_status = _run_git(repo, ["status", "--porcelain=v1", "-uno"])
    pre_diff = _run_git(repo, ["diff"])

    start = time.time()
    process = subprocess.Popen(
        cmd,
        cwd=str(repo),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
        env=env,
    )

    try:
        stdout, stderr = process.communicate(prompt, timeout=timeout_s)
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
        stdout, stderr = "", f"[codex_timeout] timeout_s={timeout_s}\n"
        returncode = 124

    stdout_path.write_text(stdout or "", encoding="utf-8", errors="ignore")
    stderr_path.write_text(stderr or "", encoding="utf-8", errors="ignore")

    post_status = _run_git(repo, ["status", "--porcelain=v1", "-uno"])
    post_diff = _run_git(repo, ["diff"])

    payload = {
        "cmd": cmd,
        "cwd": str(repo),
        "returncode": returncode,
        "stdout": stdout or "",
        "stderr": stderr or "",
        "result": result_path.read_text(encoding="utf-8", errors="ignore") if result_path.exists() else "",
        "timeout_s": timeout_s,
        "elapsed_s": round(time.time() - start, 3),
        "pre_git_status": pre_status,
        "pre_git_diff": pre_diff,
        "post_git_status": post_status,
        "post_git_diff": post_diff,
        "env": {
            "CODEX_MODEL": args.model,
            "CODEX_BIN": codex_bin,
            "OPENAI_API_KEY_PRESENT": bool(env.get("OPENAI_API_KEY")),
        },
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"Return code: {returncode}")


if __name__ == "__main__":
    main()
