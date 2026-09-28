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
    ap.add_argument("--out-root", required=True)
    ap.add_argument("--groups", default="A,B")
    ap.add_argument("--backend-mode", choices=["bedrock", "env"], default="bedrock")
    ap.add_argument("--aws-region", default="us-west-2")
    ap.add_argument("--model-id", default="")
    ap.add_argument("--system-prompt", default="")
    ap.add_argument("--task-template", default="")
    ap.add_argument("--agent-runner-script", default="")
    ap.add_argument("--max-attempts", type=int, default=3)
    ap.add_argument("--agent-timeout-s", type=int, default=1800)
    ap.add_argument("--verify-timeout-s", type=int, default=1200)
    ap.add_argument("--spotless-timeout-s", type=int, default=600)
    ap.add_argument("--case-timeout-s", type=int, default=4200)
    ap.add_argument("--python", default=sys.executable)
    args = ap.parse_args()

    if args.backend_mode == "bedrock" and not args.model_id:
        raise SystemExit("Missing --model-id")

    project_root = Path(args.project_root).resolve()
    script = Path(__file__).resolve().parent / "run_paper_aligned_trigger_case.py"
    manifest_path = Path(args.manifest).resolve()
    repo_template_root = Path(args.repo_template_root).resolve() if args.repo_template_root else None
    out_root = Path(args.out_root).resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    rows = [json.loads(line) for line in manifest_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    groups = [g.strip() for g in args.groups.split(",") if g.strip()]

    expanded = []
    for row in rows:
        for group in groups:
            expanded.append((row, group))

    summary_path = out_root / "batch_summary.jsonl"
    progress_path = out_root / "batch_progress.json"
    done = 0
    success = 0

    with summary_path.open("a", encoding="utf-8") as summary_f:
        for idx, (row, group) in enumerate(expanded, start=1):
            repo_template = row.get("repo_template")
            if not repo_template:
                if not repo_template_root:
                    raise SystemExit("Missing repo_template and no --repo-template-root was provided")
                repo_template = str(repo_template_root / row["repo_name"])

            cmd = [
                args.python,
                str(script),
                "--project-root",
                str(project_root),
                "--repo-template",
                repo_template,
                "--out-root",
                str(out_root / "cases" / f"{row['run_id']}__{group}"),
                "--repo-name",
                row["repo_name"],
                "--run-id",
                row["run_id"],
                "--group",
                group,
                "--trace-id",
                row.get("trace_id", ""),
                "--pattern-id",
                row["pattern_id"],
                "--official-test-path",
                row["official_test_path"],
                "--official-test-class",
                row["official_test_class"],
                "--inject-verify-rc",
                str(int(row["inject_verify_rc"])),
                "--verify-cmd",
                json.dumps(row["verify_cmd"], ensure_ascii=False),
                "--buggy-repo",
                row["buggy_repo"],
                "--pattern-summary",
                row.get("pattern_summary", ""),
                "--aws-region",
                args.aws_region,
                "--backend-mode",
                args.backend_mode,
                "--model-id",
                args.model_id,
                "--max-attempts",
                str(args.max_attempts),
                "--agent-timeout-s",
                str(args.agent_timeout_s),
                "--verify-timeout-s",
                str(args.verify_timeout_s),
                "--spotless-timeout-s",
                str(args.spotless_timeout_s),
                "--case-timeout-s",
                str(args.case_timeout_s),
            ]
            if args.system_prompt:
                cmd.extend(["--system-prompt", args.system_prompt])
            if args.task_template:
                cmd.extend(["--task-template", args.task_template])
            if args.agent_runner_script:
                cmd.extend(["--agent-runner-script", args.agent_runner_script])
            transform_ids = row.get("transform_ids") or []
            bug_related_files = row.get("bug_related_files") or []
            spotless_modules = row.get("spotless_modules") or []
            if transform_ids:
                cmd.extend(["--transform-ids", *transform_ids])
            if bug_related_files:
                cmd.extend(["--bug-related-files", *bug_related_files])
            if spotless_modules:
                cmd.extend(["--spotless-modules", *[str(x) for x in spotless_modules if str(x)]])
            if row.get("execution_context_summary"):
                context_file = out_root / "_execution_contexts" / f"{row['run_id']}__{group}.txt"
                context_file.parent.mkdir(parents=True, exist_ok=True)
                context_file.write_text(str(row.get("execution_context_summary")), encoding="utf-8")
                cmd.extend(["--execution-context-summary-file", str(context_file)])

            completed = subprocess.run(cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            record = {
                "index": idx,
                "total": len(expanded),
                "run_id": row["run_id"],
                "group": group,
                "returncode": completed.returncode,
            }
            summary_f.write(json.dumps(record, ensure_ascii=False) + "\n")
            done += 1
            if completed.returncode == 0:
                success += 1
            progress_path.write_text(
                json.dumps({"completed": done, "total": len(expanded), "success": success, "failed": done - success}, indent=2) + "\n",
                encoding="utf-8",
            )


if __name__ == "__main__":
    main()
