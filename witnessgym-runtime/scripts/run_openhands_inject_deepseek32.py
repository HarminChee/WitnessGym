#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--system", required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--timeout-s", type=int, default=None)
    parser.add_argument("--tools", default="")
    args = parser.parse_args()

    base = Path(__file__).resolve().with_name("run_openhands_headless.py")
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
        "--model",
        "bedrock/deepseek.v3.2",
        "--runtime",
        "cli",
        "--aws-region",
        "us-west-2",
        "--aws-profile",
        "default",
    ]
    if args.timeout_s is not None:
        cmd.extend(["--timeout-s", str(args.timeout_s)])
    if args.tools:
        cmd.extend(["--tools", args.tools])

    completed = subprocess.run(cmd, check=False)
    raise SystemExit(completed.returncode)


if __name__ == "__main__":
    main()
