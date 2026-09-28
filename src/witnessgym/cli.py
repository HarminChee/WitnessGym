from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .config import Adapter, load_spec
from .errors import WitnessGymError
from .pipeline import agent_settings, construct, evaluate


def main() -> int:
    parser = argparse.ArgumentParser(description="Construct and evaluate executable bug witnesses")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="action", required=True)
    check = sub.add_parser(
        "check-adapter", help="Validate a language adapter without executing commands"
    )
    check.add_argument("adapter", type=Path)
    for name in ("construct", "evaluate"):
        p = sub.add_parser(name)
        p.add_argument("--clean-repo", type=Path, required=True)
        p.add_argument("--adapter", type=Path, required=True)
        p.add_argument("--agent", type=Path, required=True)
        p.add_argument("--output", type=Path, required=True)
        p.add_argument(
            "--allow-local-execution",
            action="store_true",
            help="Explicitly acknowledge host execution; use only trusted inputs or run inside a disposable container",
        )
        if name == "construct":
            p.add_argument("--bug", type=Path, required=True)
            p.add_argument("--transform", type=Path, action="append", default=[])
            p.add_argument("--attempts", type=int, default=3)
        else:
            p.add_argument("--buggy-repo", type=Path, required=True)
            p.add_argument("--report", type=Path, required=True)
            p.add_argument("--context", type=Path)
    args = parser.parse_args()
    try:
        adapter = Adapter.load(args.adapter)
        if args.action == "check-adapter":
            print(json.dumps({"valid": True, "language": adapter.language}))
            return 0
        common = dict(
            clean_repo=args.clean_repo.resolve(),
            output=args.output,
            adapter=adapter,
            agent=agent_settings(args.agent),
            allow_local_execution=args.allow_local_execution,
        )
        if args.action == "construct":
            result = construct(
                **common,
                bug=load_spec(args.bug, kind="bug"),
                transformations=[load_spec(p, kind="transform") for p in args.transform],
                attempts=args.attempts,
            )
        else:
            context = json.loads(args.context.read_text()) if args.context else None
            result = evaluate(
                **common,
                buggy_repo=args.buggy_repo.resolve(),
                report=args.report.read_text(),
                execution_context=context,
            )
        print(json.dumps({"accepted": result["accepted"], "output": str(args.output.resolve())}))
        return 0 if result["accepted"] else 1
    except (WitnessGymError, OSError, ValueError) as exc:
        print(f"WitnessGym: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
