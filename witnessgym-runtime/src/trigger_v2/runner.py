from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import shutil

from src.trigger_v2.agent_invoker import run_agent
from src.trigger_v2.config import TriggerConfig
from src.trigger_v2.context_builder import build_task_text
from src.trigger_v2.outcome_classifier import classify_outcome
from src.trigger_v2.repo_audit import audit_repo_changes
from src.trigger_v2.repo_audit import capture_repo_diff_baseline
from src.trigger_v2.report.artifact_writer import write_json, write_text
from src.trigger_v2.report.observability_writer import write_observability_bundle
from src.trigger_v2.report.summary_writer import write_case_result, write_decision
from src.trigger_v2.runtime.permissions import ensure_prompt_files_exist
from src.trigger_v2.runtime.permissions import lock_repo_to_test_writes
from src.trigger_v2.runtime.permissions import restore_repo_permissions
from src.trigger_v2.test_discovery import discover_generated_tests
from src.trigger_v2.verify.maven_runner import run_maven_verify
from src.trigger_v2.verify.spotless_runner import run_spotless
from src.trigger_v2.workspace import overlay_buggy_repo
from src.trigger_v2.workspace import prepare_case_workspace
from src.trigger_v2.workspace import restore_official_test


def run_single_case(
    *,
    config: TriggerConfig,
    case_input,
) -> dict:
    workspace = prepare_case_workspace(
        repo_template=config.repo_template,
        out_root=config.out_root,
        run_id=case_input.run_id,
        group=case_input.group,
    )

    overlay_result = overlay_buggy_repo(
        workspace_repo=workspace.workspace_repo,
        buggy_repo=Path(case_input.buggy_repo),
    )
    write_json(workspace.case_dir / "overlay_buggy_repo_result.json", overlay_result)

    if overlay_result["returncode"] != 0:
        raise RuntimeError(
            f"Failed to overlay buggy repo: {overlay_result['stderr']}"
        )

    restore_test_result = restore_official_test(
        repo_template=config.repo_template,
        workspace_repo=workspace.workspace_repo,
        official_test_path=case_input.official_test_path,
    )
    write_json(workspace.case_dir / "restore_official_test_result.json", restore_test_result)

    if not restore_test_result["ok"]:
        raise RuntimeError(
            f"Failed to restore official test: {restore_test_result['reason']}"
        )

    ensure_prompt_files_exist(config.system_prompt_path, config.task_template_path)

    system_prompt_copy = workspace.context_dir / "system.txt"
    task_prompt_path = workspace.context_dir / "task.txt"
    permission_state_path = workspace.case_dir / "permission_lock_state.json"

    write_text(system_prompt_copy, config.system_prompt_path.read_text())
    write_text(task_prompt_path, build_task_text(config.task_template_path, case_input))

    official_test_file = workspace.workspace_repo / case_input.official_test_path
    deleted_official_test = False
    if official_test_file.exists():
        official_test_file.unlink()
        deleted_official_test = True

    baseline_modified_files = capture_repo_diff_baseline(
        workspace_repo=workspace.workspace_repo,
    )
    write_json(
        workspace.case_dir / "baseline_modified_files.json",
        {"modified_files": baseline_modified_files},
    )

    lock_state = lock_repo_to_test_writes(
        workspace_repo=workspace.workspace_repo,
        allowed_test_roots=config.allowed_test_roots,
        state_path=permission_state_path,
    )

    try:
        agent_result = run_agent(
            runner_script=config.agent_runner_script,
            workspace_repo=workspace.workspace_repo,
            system_prompt_path=system_prompt_copy,
            task_prompt_path=task_prompt_path,
            allowed_tools=config.allowed_tools,
            env_overrides=config.agent_env,
            timeout_s=config.agent_timeout_s,
            out_dir=workspace.agent_dir,
        )
    finally:
        restore_result = restore_repo_permissions(
            workspace_repo=workspace.workspace_repo,
            state_path=permission_state_path,
        )
        write_json(workspace.case_dir / "permission_restore_result.json", restore_result)

    generated_tests = discover_generated_tests(
        workspace_repo=workspace.workspace_repo,
        official_test_path=case_input.official_test_path,
        out_dir=workspace.generated_tests_dir,
    )

    spotless = run_spotless(
        workspace_repo=workspace.workspace_repo,
        modules=config.spotless_modules,
        timeout_s=config.spotless_timeout_s,
        out_dir=workspace.verify_dir,
    )

    # Formatting is part of the mutation surface and must also be audited.
    audit = audit_repo_changes(
        workspace_repo=workspace.workspace_repo,
        allowed_test_roots=config.allowed_test_roots,
        protected_prod_roots=config.protected_prod_roots,
        baseline_modified_files=baseline_modified_files,
    )

    clean_workspace = workspace.case_dir / 'clean_verification_repo'
    shutil.copytree(config.repo_template, clean_workspace,
        ignore=shutil.ignore_patterns('.git', 'target', 'build', '__pycache__'))
    clean_official_test = clean_workspace / case_input.official_test_path
    if clean_official_test.exists():
        clean_official_test.unlink()
    for name in generated_tests.generated_test_files:
        destination = clean_workspace / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(workspace.workspace_repo / name, destination)
    clean_verify = run_maven_verify(
        workspace_repo=clean_workspace,
        verify_cmd=case_input.verify_cmd,
        timeout_s=config.verify_timeout_s,
        out_dir=workspace.case_dir / 'clean_verify',
    )

    verify = run_maven_verify(
        workspace_repo=workspace.workspace_repo,
        verify_cmd=case_input.verify_cmd,
        timeout_s=config.verify_timeout_s,
        out_dir=workspace.verify_dir,
    )

    outcome = classify_outcome(
        verify_rc=verify.verify_rc,
        verify_stdout_path=verify.stdout_path,
        verify_stderr_path=verify.stderr_path,
    )

    materialized_test_files = agent_result.trigger_report.get("materialized_test_files", [])
    has_trigger_report = bool(agent_result.trigger_report)

    case_result = {
        "run_id": case_input.run_id,
        "group": case_input.group,
        "official_test_path": case_input.official_test_path,
        "official_test_class": case_input.official_test_class,
        "generated_test_files": generated_tests.generated_test_files,
        "materialized_test_files_reported_by_agent": materialized_test_files,
        "modified_files": audit.modified_files,
        "modified_production_files": audit.modified_production_files,
        "forbidden_non_test_changes": audit.forbidden_non_test_changes,
        "verify_rc": verify.verify_rc,
        "clean_verify_rc": clean_verify.verify_rc,
        "failure_type": outcome.failure_type,
        "spotless_rc": spotless.spotless_rc,
        "agent_returncode": agent_result.returncode,
        "trigger_report": agent_result.trigger_report,
        "deleted_official_test": deleted_official_test,
        "policy_violation": len(audit.forbidden_non_test_changes) > 0,
        "permission_lock_entries": len(lock_state.get("locked", [])),
        "overlay_buggy_repo_rc": overlay_result["returncode"],
    }

    trigger_success = (
        len(generated_tests.generated_test_files) > 0
        and verify.verify_rc != 0
        and clean_verify.verify_rc == 0
        and agent_result.returncode == 0
        and outcome.failure_type == "TEST_FAILURE"
        and len(audit.modified_production_files) == 0
        and len(audit.forbidden_non_test_changes) == 0
        and (has_trigger_report or not config.fail_on_empty_trigger_report)
    )

    if config.fail_on_missing_generated_test and len(generated_tests.generated_test_files) == 0:
        trigger_success = False

    decision = {
        "strict_policy": {
            "trigger_success_requires": [
                "generated_test_files>0",
                "verify_rc!=0",
                "failure_type==TEST_FAILURE",
                "same_witness_passes_clean_baseline",
                "no_production_changes",
                "no_forbidden_non_test_changes",
            ],
            "trigger_success": trigger_success,
        },
        "signals": {
            "verify_rc": verify.verify_rc,
            "failure_type": outcome.failure_type,
            "generated_test_files_count": len(generated_tests.generated_test_files),
            "production_changes_count": len(audit.modified_production_files),
            "forbidden_non_test_changes_count": len(audit.forbidden_non_test_changes),
            "has_trigger_report": has_trigger_report,
            "permission_lock_entries": len(lock_state.get("locked", [])),
            "deleted_official_test": deleted_official_test,
            "overlay_buggy_repo_rc": overlay_result["returncode"],
        },
    }

    case_result["detect_success"] = trigger_success

    write_case_result(workspace.case_dir, case_result)
    write_decision(workspace.case_dir, decision)
    write_json(workspace.case_dir / "agent_result.json", asdict(agent_result))
    write_json(workspace.case_dir / "audit_result.json", asdict(audit))
    write_json(workspace.case_dir / "generated_tests_result.json", asdict(generated_tests))
    write_json(workspace.case_dir / "spotless_result.json", asdict(spotless))
    write_json(workspace.case_dir / "verify_result.json", asdict(verify))
    write_json(workspace.case_dir / "clean_verify_result.json", asdict(clean_verify))
    write_json(workspace.case_dir / "outcome_result.json", asdict(outcome))
    write_json(workspace.case_dir / "permission_lock_result.json", lock_state)

    write_observability_bundle(
        out_path=workspace.case_dir / "observability.json",
        case_input=case_input,
        agent_result=asdict(agent_result),
        audit_result=asdict(audit),
        generated_tests_result=asdict(generated_tests),
        spotless_result=asdict(spotless),
        verify_result=asdict(verify),
        outcome_result=asdict(outcome),
        decision=decision,
    )

    return case_result
