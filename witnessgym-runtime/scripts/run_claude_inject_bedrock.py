#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


DEFAULT_MODEL = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--system", required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--timeout-s", type=int, default=None)
    parser.add_argument("--tools", default="")
    parser.add_argument("--aws-region", default="us-west-2")
    parser.add_argument("--aws-profile", default="default")
    parser.add_argument("--bedrock-model-id", default=DEFAULT_MODEL)
    args = parser.parse_args()

    base = Path(__file__).resolve().with_name("run_claude_headless.py")
    cmd = [
        sys.executable,
        str(base),
        "--repo",
        args.repo,
        "--system",
        args.system,
        "--task",
        args.task,
        "--out",
        args.out,
    ]
    if args.timeout_s is not None:
        cmd.extend(["--timeout-s", str(args.timeout_s)])
    if args.tools:
        cmd.extend(["--tools", args.tools])

    env = os.environ.copy()
    env["CLAUDE_CODE_USE_BEDROCK"] = "1"
    env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] = "1"
    env["AWS_REGION"] = args.aws_region
    env["AWS_DEFAULT_REGION"] = args.aws_region
    env["ANTHROPIC_MODEL"] = args.bedrock_model_id
    if args.aws_profile:
        env["AWS_PROFILE"] = args.aws_profile
    for key in [
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "DEEPSEEK_API_KEY",
        "MOONSHOT_API_KEY",
        "MINIMAX_API_KEY",
        "OPENROUTER_API_KEY",
        "CODEX_API_KEY",
        "GOOGLE_API_KEY",
    ]:
        env.pop(key, None)

    completed = subprocess.run(cmd, check=False, env=env)
    raise SystemExit(completed.returncode)


if __name__ == "__main__":
    main()
