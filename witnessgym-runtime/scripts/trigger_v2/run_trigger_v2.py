from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.trigger_v2.config import TriggerConfig, build_bedrock_env
from src.trigger_v2.report.artifact_writer import write_json
from src.trigger_v2.runner import run_single_case
from src.trigger_v2.runtime.permissions import build_allowed_tools_for_trigger_v2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-template", required=True)
    parser.add_argument("--out-root", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--group", required=True)
    parser.add_argument("--trace-id", default="")
    parser.add_argument("--pattern-id", required=True)
    parser.add_argument("--transform-ids", default="")
    parser.add_argument("--official-test-path", required=True)
    parser.add_argument("--official-test-class", required=True)
    parser.add_argument("--bug-related-files", required=True)
    parser.add_argument("--inject-verify-rc", type=int, required=True)
    parser.add_argument("--verify-cmd", required=True)
    parser.add_argument("--buggy-repo", required=True)
    parser.add_argument("--pattern-summary", default="")
    parser.add_argument("--system-prompt", required=True)
    parser.add_argument("--task-template", required=True)
    parser.add_argument("--agent-runner-script", required=True)
    parser.add_argument("--aws-region", required=True)
    parser.add_argument("--bedrock-model-id", required=True)
    parser.add_argument("--agent-timeout-s", type=int, default=1800)
    parser.add_argument("--verify-timeout-s", type=int, default=1200)
    parser.add_argument("--spotless-timeout-s", type=int, default=600)
    parser.add_argument("--spotless-modules", default="")
    parser.add_argument("--repo-name", default="unknown")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    out_root = Path(args.out_root)
    out_root.mkdir(parents=True, exist_ok=True)

    try:
        transform_ids = [x for x in args.transform_ids.split(",") if x]
        bug_related_files = [x for x in args.bug_related_files.split(",") if x]
        verify_cmd = json.loads(args.verify_cmd)
        spotless_modules = [x for x in args.spotless_modules.split(",") if x]

        config = TriggerConfig(
            repo_template=Path(args.repo_template).resolve(),
            out_root=out_root.resolve(),
            system_prompt_path=Path(args.system_prompt).resolve(),
            task_template_path=Path(args.task_template).resolve(),
            agent_runner_script=Path(args.agent_runner_script).resolve(),
            allowed_tools=build_allowed_tools_for_trigger_v2(),
            agent_timeout_s=args.agent_timeout_s,
            verify_timeout_s=args.verify_timeout_s,
            spotless_timeout_s=args.spotless_timeout_s,
            spotless_modules=spotless_modules,
            allowed_test_roots=["src/test/java", "src/testFixtures/java"],
            protected_prod_roots=["src/main/java"],
            agent_env=build_bedrock_env(
                aws_region=args.aws_region,
                bedrock_model_id=args.bedrock_model_id,
            ),
        )

        case_input = SimpleNamespace(
            repo_name=args.repo_name,
            run_id=args.run_id,
            group=args.group,
            trace_id=args.trace_id,
            pattern_id=args.pattern_id,
            transform_ids=transform_ids,
            official_test_path=args.official_test_path,
            official_test_class=args.official_test_class,
            bug_related_files=bug_related_files,
            inject_verify_rc=args.inject_verify_rc,
            verify_cmd=verify_cmd,
            buggy_repo=args.buggy_repo,
            pattern_summary=args.pattern_summary,
        )

        result = run_single_case(config=config, case_input=case_input)
        write_json(out_root / "last_case_result.json", result)
        print(json.dumps(result, indent=2))

    except Exception as e:
        payload = {
            "ok": False,
            "error_type": type(e).__name__,
            "error": str(e),
            "traceback": traceback.format_exc(),
        }
        write_json(out_root / "fatal_error.json", payload)
        print(json.dumps(payload, indent=2))
        raise


if __name__ == "__main__":
    main()
