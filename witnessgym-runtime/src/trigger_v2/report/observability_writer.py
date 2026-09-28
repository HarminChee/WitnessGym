from __future__ import annotations

import json
from pathlib import Path


def _json_safe(obj):
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, tuple):
        return [_json_safe(v) for v in obj]
    return obj


def write_observability_bundle(
    *,
    out_path: Path,
    case_input,
    agent_result: dict,
    audit_result: dict,
    generated_tests_result: dict,
    spotless_result: dict,
    verify_result: dict,
    outcome_result: dict,
    decision: dict,
) -> None:
    payload = {
        "run_id": case_input.run_id,
        "group": case_input.group,
        "trace_id": case_input.trace_id,
        "pattern_id": case_input.pattern_id,
        "transform_ids": case_input.transform_ids,
        "official_test_path": case_input.official_test_path,
        "official_test_class": case_input.official_test_class,
        "agent": {
            "returncode": agent_result.get("returncode"),
            "trigger_report": agent_result.get("trigger_report", {}),
            "parse_source_path": agent_result.get("parse_source_path"),
            "stdout_path": agent_result.get("stdout_path"),
            "stderr_path": agent_result.get("stderr_path"),
            "result_path": agent_result.get("result_path"),
            "json_path": agent_result.get("json_path"),
            "runner_stdout_path": agent_result.get("runner_stdout_path"),
            "runner_stderr_path": agent_result.get("runner_stderr_path"),
            "trigger_report_path": agent_result.get("trigger_report_path"),
        },
        "materialization": {
            "generated_test_files": generated_tests_result.get("generated_test_files", []),
            "generated_test_files_count": len(generated_tests_result.get("generated_test_files", [])),
            "agent_reported_materialized_files": agent_result.get("trigger_report", {}).get("materialized_test_files", []),
        },
        "repo_audit": {
            "modified_files": audit_result.get("modified_files", []),
            "modified_production_files": audit_result.get("modified_production_files", []),
            "forbidden_non_test_changes": audit_result.get("forbidden_non_test_changes", []),
        },
        "verify": {
            "spotless_rc": spotless_result.get("spotless_rc"),
            "spotless_stdout_path": spotless_result.get("stdout_path"),
            "spotless_stderr_path": spotless_result.get("stderr_path"),
            "spotless_summary_path": spotless_result.get("summary_path"),
            "verify_rc": verify_result.get("verify_rc"),
            "failure_type": outcome_result.get("failure_type"),
            "verify_stdout_path": verify_result.get("stdout_path"),
            "verify_stderr_path": verify_result.get("stderr_path"),
            "verify_summary_path": verify_result.get("summary_path"),
        },
        "decision": decision,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(_json_safe(payload), indent=2))
