import argparse
import json
import os
import signal
import subprocess
import time
from pathlib import Path

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--system", required=True)
    ap.add_argument("--task", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--timeout-s", type=int, default=None)
    ap.add_argument("--tools", default="Bash,Edit,Read,Grep,Glob")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    sys_path = Path(args.system).resolve()
    task_path = Path(args.task).resolve()
    out_path = Path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    claude_timeout_s = args.timeout_s
    if claude_timeout_s is None:
        claude_timeout_s = int(os.environ.get("CLAUDE_TIMEOUT_S", "1800"))

    sys_text = sys_path.read_text(encoding="utf-8", errors="ignore")
    task_text = task_path.read_text(encoding="utf-8", errors="ignore")

    cmd = [
        "claude",
        "-p",
        "--append-system-prompt",
        sys_text,
        task_text,
        "--output-format",
        "json",
        "--allowedTools",
        args.tools,
        "bash",
        "--permission-mode",
        "acceptEdits",
    ]

    pre_status = subprocess.run(["git", "status", "--porcelain=v1", "-uno"], cwd=str(repo), capture_output=True, text=True)
    pre_diff = subprocess.run(["git", "diff"], cwd=str(repo), capture_output=True, text=True)

    p = subprocess.Popen(
        cmd,
        cwd=str(repo),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    t0 = time.time()
    try:
        out, err = p.communicate(timeout=claude_timeout_s)
        p_stdout = out or ""
        p_stderr = err or ""
        p_rc = int(p.returncode) if p.returncode is not None else 0
    except subprocess.TimeoutExpired:
        try:
            os.killpg(p.pid, signal.SIGTERM)
        except Exception:
            pass
        time.sleep(2)
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except Exception:
            pass
        p_stdout = ""
        p_stderr = f"[claude_timeout] timeout_s={claude_timeout_s} cmd={' '.join(cmd)}\n"
        p_rc = 124

    post_status = subprocess.run(["git", "status", "--porcelain=v1", "-uno"], cwd=str(repo), capture_output=True, text=True)
    post_diff = subprocess.run(["git", "diff"], cwd=str(repo), capture_output=True, text=True)

    payload = {
        "cmd": cmd,
        "cwd": str(repo),
        "returncode": p_rc,
        "stdout": p_stdout,
        "stderr": p_stderr,
        "timeout_s": claude_timeout_s,
        "elapsed_s": round(time.time() - t0, 3),
        "pre_git_status": pre_status.stdout,
        "pre_git_diff": pre_diff.stdout,
        "post_git_status": post_status.stdout,
        "post_git_diff": post_diff.stdout,
        "env": {
            "CLAUDE_CODE_USE_BEDROCK": os.environ.get("CLAUDE_CODE_USE_BEDROCK"),
            "AWS_REGION": os.environ.get("AWS_REGION"),
            "AWS_PROFILE": os.environ.get("AWS_PROFILE"),
            "ANTHROPIC_MODEL": os.environ.get("ANTHROPIC_MODEL"),
        },
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"Return code: {p_rc}")

if __name__ == "__main__":
    main()
