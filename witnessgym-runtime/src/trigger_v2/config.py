from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

RESULT_FAILURE_TYPES = {
    "PASS",
    "TEST_FAILURE",
    "NO_TESTS",
    "COMPILE_ERROR",
    "TIMEOUT",
    "OTHER_FAIL",
    "NPE",
}

STRICT_SUCCESS_SIGNALS = {
    "required_failure_type": "TEST_FAILURE",
    "require_generated_test": True,
    "require_no_production_changes": True,
    "require_no_forbidden_non_test_changes": True,
}


@dataclass
class TriggerConfig:
    repo_template: Path
    out_root: Path
    system_prompt_path: Path
    task_template_path: Path
    agent_runner_script: Path
    allowed_tools: str
    agent_timeout_s: int
    verify_timeout_s: int
    spotless_timeout_s: int
    spotless_modules: list[str]
    allowed_test_roots: list[str]
    protected_prod_roots: list[str]
    fail_on_empty_trigger_report: bool = False
    fail_on_missing_generated_test: bool = True
    agent_env: dict[str, str] = field(default_factory=dict)


def build_bedrock_env(
    *,
    aws_region: str,
    bedrock_model_id: str,
    bedrock_enabled: bool = True,
) -> dict[str, str]:
    env = {}
    if bedrock_enabled:
        env["CLAUDE_CODE_USE_BEDROCK"] = "1"
    env["AWS_REGION"] = aws_region
    env["AWS_DEFAULT_REGION"] = aws_region
    env["ANTHROPIC_MODEL"] = bedrock_model_id
    env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] = "1"
    return env
