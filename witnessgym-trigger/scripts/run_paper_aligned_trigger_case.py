#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def default_project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def trigger_success(payload: dict) -> bool:
    return bool(
        payload.get("detect_success")
        or (
            payload.get("failure_type") == "TEST_FAILURE"
            and payload.get("generated_test_files")
            and not payload.get("modified_production_files")
            and not payload.get("forbidden_non_test_changes")
        )
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", default=str(default_project_root()))
    ap.add_argument("--repo-template", required=True)
    ap.add_argument("--out-root", required=True)
    ap.add_argument("--repo-name", required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--group", choices=["A", "B"], required=True)
    ap.add_argument("--trace-id", default="")
    ap.add_argument("--pattern-id", required=True)
    ap.add_argument("--transform-ids", nargs="*", default=[])
    ap.add_argument("--official-test-path", required=True)
    ap.add_argument("--official-test-class", required=True)
    ap.add_argument("--bug-related-files", nargs="*", default=[])
    ap.add_argument("--inject-verify-rc", type=int, required=True)
    ap.add_argument("--verify-cmd", required=True, help="JSON array string")
    ap.add_argument("--buggy-repo", required=True)
    ap.add_argument("--pattern-summary", default="")
    ap.add_argument("--execution-context-summary", default="")
    ap.add_argument("--execution-context-summary-file", default="")
    ap.add_argument("--system-prompt", default="")
    ap.add_argument("--task-template", default="")
    ap.add_argument("--agent-runner-script", default="")
    ap.add_argument("--backend-mode", choices=["bedrock", "env"], default="bedrock")
    ap.add_argument("--aws-region", default=os.environ.get("AWS_REGION", "us-west-2"))
    ap.add_argument("--model-id", default=os.environ.get("BEDROCK_MODEL_ID", ""))
    ap.add_argument("--max-attempts", type=int, default=3)
    ap.add_argument("--agent-timeout-s", type=int, default=1800)
    ap.add_argument("--verify-timeout-s", type=int, default=1200)
    ap.add_argument("--spotless-timeout-s", type=int, default=600)
    ap.add_argument("--spotless-modules", nargs="*", default=[])
    ap.add_argument("--case-timeout-s", type=int, default=4200)
    ap.add_argument("--python", default=sys.executable)
    args = ap.parse_args()

    if args.backend_mode == "bedrock" and not args.model_id:
        raise SystemExit("Missing --model-id or BEDROCK_MODEL_ID for bedrock mode")

    project_root = Path(args.project_root).resolve()
    bench_root = project_root / "witnessgym-runtime"
    system_prompt = Path(args.system_prompt).resolve() if args.system_prompt else bench_root / "src" / "trigger_v2" / "prompts" / "system.trigger_v2.txt"
    task_template = Path(args.task_template).resolve() if args.task_template else bench_root / "src" / "trigger_v2" / "prompts" / "task_template.trigger_v2.txt"
    agent_runner_script = Path(args.agent_runner_script).resolve() if args.agent_runner_script else bench_root / "scripts" / "run_claude_headless.py"
    review_core = Path(__file__).resolve().parent / "run_trigger_core_review.py"
    out_root = Path(args.out_root).resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    verify_cmd = json.loads(args.verify_cmd)
    execution_context_summary = args.execution_context_summary
    if args.execution_context_summary_file:
        execution_context_summary = Path(args.execution_context_summary_file).read_text(encoding="utf-8", errors="ignore")

    summary: dict[str, object] = {
        "repo_name": args.repo_name,
        "run_id": args.run_id,
        "group": args.group,
        "trace_id": args.trace_id if args.group == "B" else "",
        "pattern_id": args.pattern_id,
        "transform_ids": list(args.transform_ids),
        "paper_aligned_max_attempts": args.max_attempts,
        "attempts": [],
        "ok": False,
    }

    for attempt_idx in range(1, args.max_attempts + 1):
        attempt_out = out_root / f"attempt_{attempt_idx:02d}"
        attempt_out.mkdir(parents=True, exist_ok=True)
        attempt_task_template = task_template
        if args.group == "B" and execution_context_summary.strip():
            attempt_task_template = attempt_out / "task_template.with_execution_context.txt"
            base_template = task_template.read_text(encoding="utf-8", errors="ignore")
            addition = (
                "\n\nExecution-context block for WithEC:\n"
                "The following execution context was collected during benchmark construction. "
                "It is not a reference bug witness, hidden oracle, or construction-time solution.\n\n"
                f"{execution_context_summary.strip()}\n"
            )
            attempt_task_template.write_text(base_template.rstrip() + addition, encoding="utf-8")
        cmd = [
            args.python,
            str(review_core),
            "--bench-root",
            str(bench_root),
            "--repo-template",
            str(Path(args.repo_template).resolve()),
            "--out-root",
            str(attempt_out),
            "--run-id",
            args.run_id,
            "--group",
            args.group,
            "--trace-id",
            args.trace_id if args.group == "B" else "",
            "--pattern-id",
            args.pattern_id,
            "--transform-ids",
            ",".join(args.transform_ids),
            "--official-test-path",
            args.official_test_path,
            "--official-test-class",
            args.official_test_class,
            "--bug-related-files",
            ",".join(args.bug_related_files),
            "--inject-verify-rc",
            str(args.inject_verify_rc),
            "--verify-cmd",
            json.dumps(verify_cmd, ensure_ascii=False),
            "--buggy-repo",
            str(Path(args.buggy_repo).resolve()),
            "--pattern-summary",
            args.pattern_summary,
            "--system-prompt",
            str(system_prompt),
            "--task-template",
            str(attempt_task_template),
            "--agent-runner-script",
            str(agent_runner_script),
            "--backend-mode",
            args.backend_mode,
            "--aws-region",
            args.aws_region,
            "--model-id",
            args.model_id,
            "--agent-timeout-s",
            str(args.agent_timeout_s),
            "--verify-timeout-s",
            str(args.verify_timeout_s),
            "--spotless-timeout-s",
            str(args.spotless_timeout_s),
            "--spotless-modules",
            ",".join(args.spotless_modules),
            "--repo-name",
            args.repo_name,
        ]
        completed = subprocess.run(
            cmd,
            cwd=str(bench_root),
            env=os.environ.copy(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=args.case_timeout_s,
            check=False,
        )
        (attempt_out / "cmd.txt").write_text(" ".join(cmd) + "\n", encoding="utf-8")
        (attempt_out / "stdout.txt").write_text(completed.stdout or "", encoding="utf-8", errors="ignore")
        (attempt_out / "stderr.txt").write_text(completed.stderr or "", encoding="utf-8", errors="ignore")

        last_case_result = attempt_out / "last_case_result.json"
        payload = json.loads(last_case_result.read_text(encoding="utf-8")) if last_case_result.exists() else {}
        attempt_result = {
            "attempt_index": attempt_idx,
            "returncode": completed.returncode,
            "detect_success": payload.get("detect_success"),
            "failure_type": payload.get("failure_type"),
            "verify_rc": payload.get("verify_rc"),
            "generated_test_files": payload.get("generated_test_files", []),
            "ok": trigger_success(payload),
        }
        summary["attempts"].append(attempt_result)
        (attempt_out / "attempt_result.json").write_text(json.dumps(attempt_result, indent=2) + "\n", encoding="utf-8")
        if attempt_result["ok"]:
            summary["ok"] = True
            summary["successful_attempt_index"] = attempt_idx
            break

    (out_root / "case_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    if not summary["ok"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
