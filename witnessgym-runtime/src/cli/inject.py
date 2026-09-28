from __future__ import annotations

import argparse
from pathlib import Path

from src.pipeline.context import InjectionRequest
from src.pipeline.orchestrator import run_injection

def _parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--pattern-id", required=True)
    ap.add_argument("--transform-ids", default="", nargs="*")
    ap.add_argument("--traces", required=True)
    ap.add_argument("--commands", required=True)
    ap.add_argument("--trace-id", required=True)
    ap.add_argument("--run-root", default="out/runs")
    ap.add_argument("--dataset-root", default="out/dataset")
    ap.add_argument("--auto-clean-after", type=int, default=1)
    ap.add_argument("--runner-script", default="scripts/run_claude_headless.py")
    ap.add_argument("--system-prompt", default="prompts/system/inject.system.txt")
    ap.add_argument("--max-attempts", type=int, default=1)
    ap.add_argument("--verify-timeout-s", type=int, default=900)
    return ap.parse_args()

def main() -> None:
    args = _parse_args()
    import ast
    raw = getattr(args, 'transform_ids', None)
    if isinstance(raw, str):
        s = raw.strip()
        if s.startswith('[') and s.endswith(']'):
            try:
                v = ast.literal_eval(s)
                args.transform_ids = [str(x).strip() for x in v if str(x).strip()]
            except Exception:
                args.transform_ids = s.split()
        else:
            args.transform_ids = s.split() if s else []
    elif isinstance(raw, (list, tuple)):
        args.transform_ids = [str(x).strip() for x in raw if str(x).strip()]
    else:
        args.transform_ids = []
    raw_tids = args.transform_ids
    if isinstance(raw_tids, str):
        transform_ids = raw_tids.split() if raw_tids.strip() else []
    elif isinstance(raw_tids, (list, tuple)):
        transform_ids = [str(x).strip() for x in raw_tids if str(x).strip()]
    else:
        transform_ids = []
    req = InjectionRequest(
        repo_root=Path(args.repo),
        pattern_id=args.pattern_id,
        transform_ids=transform_ids,
        traces_path=Path(args.traces),
        commands_path=Path(args.commands),
        trace_id=args.trace_id,
        run_root=Path(args.run_root),
        dataset_root=Path(args.dataset_root),
        auto_clean_after=bool(int(args.auto_clean_after)),
        runner_script=Path(args.runner_script),
        system_prompt_path=Path(args.system_prompt),
        max_attempts=int(args.max_attempts),
        verify_timeout_s=int(args.verify_timeout_s) if args.verify_timeout_s is not None else None,
    )
    res = run_injection(req)
    print(res.run_dir)
    if not res.ok:
        raise SystemExit(2)

if __name__ == "__main__":
    main()
