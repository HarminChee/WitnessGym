#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import traceback
from pathlib import Path
from types import SimpleNamespace


def build_agent_env(backend_mode: str, aws_region: str, model_id: str) -> dict[str, str]:
    if backend_mode == "bedrock":
        if not model_id:
            raise SystemExit("Missing --model-id for bedrock mode")
        return {
            "CLAUDE_CODE_USE_BEDROCK": "1",
            "AWS_REGION": aws_region,
            "AWS_DEFAULT_REGION": aws_region,
            "ANTHROPIC_MODEL": model_id,
            "BEDROCK_MODEL_ID": model_id,
            "OPENHANDS_MODEL": model_id,
            "OPENCODE_MODEL": model_id,
            "CODEX_MODEL": model_id,
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
        }
    if backend_mode == "env":
        env = {}
        for key in [
            "AWS_REGION",
            "AWS_DEFAULT_REGION",
            "AWS_PROFILE",
            "ANTHROPIC_MODEL",
            "BEDROCK_MODEL_ID",
            "OPENHANDS_MODEL",
            "OPENCODE_MODEL",
            "CODEX_MODEL",
            "ANTHROPIC_API_KEY",
            "OPENAI_API_KEY",
            "DEEPSEEK_API_KEY",
            "MOONSHOT_API_KEY",
            "MINIMAX_API_KEY",
        ]:
            value = os.environ.get(key)
            if value:
                env[key] = value
        if aws_region:
            env.setdefault("AWS_REGION", aws_region)
            env.setdefault("AWS_DEFAULT_REGION", aws_region)
        if model_id:
            env.setdefault("ANTHROPIC_MODEL", model_id)
        return env
    raise SystemExit(f"Unsupported backend mode: {backend_mode}")


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Review-facing trigger-v2 entrypoint with bedrock/env backend support.")
    ap.add_argument("--bench-root", required=True)
    ap.add_argument("--repo-template", required=True)
    ap.add_argument("--out-root", required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--group", required=True)
    ap.add_argument("--trace-id", default="")
    ap.add_argument("--pattern-id", required=True)
    ap.add_argument("--transform-ids", default="")
    ap.add_argument("--official-test-path", required=True)
    ap.add_argument("--official-test-class", required=True)
    ap.add_argument("--bug-related-files", required=True)
    ap.add_argument("--inject-verify-rc", type=int, required=True)
    ap.add_argument("--verify-cmd", required=True)
    ap.add_argument("--buggy-repo", required=True)
    ap.add_argument("--pattern-summary", default="")
    ap.add_argument("--system-prompt", required=True)
    ap.add_argument("--task-template", required=True)
    ap.add_argument("--agent-runner-script", required=True)
    ap.add_argument("--backend-mode", choices=["bedrock", "env"], default="bedrock")
    ap.add_argument("--aws-region", default="us-west-2")
    ap.add_argument("--model-id", default="")
    ap.add_argument("--agent-timeout-s", type=int, default=1800)
    ap.add_argument("--verify-timeout-s", type=int, default=1200)
    ap.add_argument("--spotless-timeout-s", type=int, default=600)
    ap.add_argument("--spotless-modules", default="")
    ap.add_argument("--repo-name", default="unknown")
    return ap.parse_args()


def ensure_git_template(repo_template: Path, out_root: Path) -> Path:
    """Return a template path with a clean git baseline for trigger auditing."""
    head = subprocess.run(
        ["git", "-C", str(repo_template), "rev-parse", "--verify", "HEAD"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if (repo_template / ".git").exists() and head.returncode == 0:
        return repo_template

    prepared = out_root / "_prepared_repo_template"
    if prepared.exists():
        raise FileExistsError("Prepared template already exists; use a new output root")
    if prepared.resolve().is_relative_to(repo_template.resolve()):
        raise ValueError("Prepared template must be outside the original repository")
    shutil.copytree(repo_template, prepared)
    subprocess.run(["git", "-C", str(prepared), "init"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
    subprocess.run(["git", "-C", str(prepared), "config", "user.name", "WITNESSGYM Reviewer"], check=True)
    subprocess.run(["git", "-C", str(prepared), "config", "user.email", "witnessgym@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(prepared), "add", "-A"], check=True)
    commit_env = os.environ.copy()
    commit_env.update(
        {
            "GIT_AUTHOR_NAME": "WITNESSGYM Reviewer",
            "GIT_AUTHOR_EMAIL": "witnessgym@example.invalid",
            "GIT_COMMITTER_NAME": "WITNESSGYM Reviewer",
            "GIT_COMMITTER_EMAIL": "witnessgym@example.invalid",
        }
    )
    subprocess.run(
        ["git", "-C", str(prepared), "commit", "-m", "WITNESSGYM clean template baseline"],
        env=commit_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )
    return prepared


def main() -> None:
    args = parse_args()
    bench_root = Path(args.bench_root).resolve()
    sys.path.insert(0, str(bench_root))

    from src.trigger_v2.config import TriggerConfig
    from src.trigger_v2.report.artifact_writer import write_json
    from src.trigger_v2.runner import run_single_case
    from src.trigger_v2.runtime.permissions import build_allowed_tools_for_trigger_v2

    out_root = Path(args.out_root)
    out_root.mkdir(parents=True, exist_ok=True)
    try:
        repo_template = ensure_git_template(Path(args.repo_template).resolve(), out_root.resolve())
        config = TriggerConfig(
            repo_template=repo_template,
            out_root=out_root.resolve(),
            system_prompt_path=Path(args.system_prompt).resolve(),
            task_template_path=Path(args.task_template).resolve(),
            agent_runner_script=Path(args.agent_runner_script).resolve(),
            allowed_tools=build_allowed_tools_for_trigger_v2(),
            agent_timeout_s=args.agent_timeout_s,
            verify_timeout_s=args.verify_timeout_s,
            spotless_timeout_s=args.spotless_timeout_s,
            spotless_modules=[x for x in args.spotless_modules.split(",") if x],
            allowed_test_roots=["src/test/java", "src/testFixtures/java"],
            protected_prod_roots=["src/main/java"],
            agent_env=build_agent_env(args.backend_mode, args.aws_region, args.model_id),
        )
        case_input = SimpleNamespace(
            repo_name=args.repo_name,
            run_id=args.run_id,
            group=args.group,
            trace_id=args.trace_id,
            pattern_id=args.pattern_id,
            transform_ids=[x for x in args.transform_ids.split(",") if x],
            official_test_path=args.official_test_path,
            official_test_class=args.official_test_class,
            bug_related_files=[x for x in args.bug_related_files.split(",") if x],
            inject_verify_rc=args.inject_verify_rc,
            verify_cmd=json.loads(args.verify_cmd),
            buggy_repo=args.buggy_repo,
            pattern_summary=args.pattern_summary,
        )
        result = run_single_case(config=config, case_input=case_input)
        write_json(out_root / "last_case_result.json", result)
        print(json.dumps(result, indent=2))
    except Exception as exc:
        payload = {
            "ok": False,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }
        write_json(out_root / "fatal_error.json", payload)
        print(json.dumps(payload, indent=2))
        raise


if __name__ == "__main__":
    main()
