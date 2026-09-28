#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def default_project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", default=str(default_project_root()))
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--repo-template-root", default="")
    ap.add_argument("--workspace-root", required=True)
    ap.add_argument("--out-root", required=True)
    ap.add_argument("--dataset-root", required=True)
    ap.add_argument("--backend-mode", choices=["bedrock", "env"], default="bedrock")
    ap.add_argument("--aws-region", default="us-west-2")
    ap.add_argument("--model-id", default="")
    ap.add_argument("--max-attempts", type=int, default=3)
    ap.add_argument("--verify-timeout-s", type=int, default=1200)
    ap.add_argument("--python", default=sys.executable)
    args = ap.parse_args()

    if args.backend_mode == "bedrock" and not args.model_id:
        raise SystemExit("Missing --model-id")

    project_root = Path(args.project_root).resolve()
    script = Path(__file__).resolve().parent / "run_paper_aligned_inject_case.py"
    manifest_path = Path(args.manifest).resolve()
    repo_template_root = Path(args.repo_template_root).resolve() if args.repo_template_root else None
    out_root = Path(args.out_root).resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    workspace_root = Path(args.workspace_root).resolve()
    dataset_root = Path(args.dataset_root).resolve()

    rows = [json.loads(line) for line in manifest_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    summary_path = out_root / "batch_summary.jsonl"
    progress_path = out_root / "batch_progress.json"

    done = 0
    success = 0
    with summary_path.open("a", encoding="utf-8") as summary_f:
        for idx, row in enumerate(rows, start=1):
            repo_template = row.get("repo_template")
            if not repo_template:
                if not repo_template_root:
                    raise SystemExit(f"Row {idx} is missing repo_template and no --repo-template-root was provided")
                repo_template = str(repo_template_root / row["repo_name"])
            cmd = [
                args.python,
                str(script),
                "--project-root",
                str(project_root),
                "--repo-template",
                repo_template,
                "--trace-id",
                row["trace_id"],
                "--pattern-id",
                row["pattern_id"],
                "--traces",
                row["traces_path"],
                "--commands",
                row["commands_path"],
                "--workspace-root",
                str(workspace_root),
                "--out-root",
                str(out_root / "cases"),
                "--dataset-root",
                str(dataset_root),
                "--aws-region",
                args.aws_region,
                "--backend-mode",
                args.backend_mode,
                "--model-id",
                args.model_id,
                "--max-attempts",
                str(args.max_attempts),
                "--verify-timeout-s",
                str(args.verify_timeout_s),
            ]
            transform_ids = row.get("transform_ids") or []
            if transform_ids:
                cmd.extend(["--transform-ids", *transform_ids])

            completed = subprocess.run(cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            record = {
                "index": idx,
                "total": len(rows),
                "trace_id": row["trace_id"],
                "pattern_id": row["pattern_id"],
                "returncode": completed.returncode,
            }
            summary_f.write(json.dumps(record, ensure_ascii=False) + "\n")
            done += 1
            if completed.returncode == 0:
                success += 1
            progress_path.write_text(
                json.dumps({"completed": done, "total": len(rows), "success": success, "failed": done - success}, indent=2) + "\n",
                encoding="utf-8",
            )


if __name__ == "__main__":
    main()
