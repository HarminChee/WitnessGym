from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class TriggerCaseContext:
    repo_name: str
    run_id: str
    group: str
    trace_id: str
    pattern_id: str
    transform_ids: list[str]
    official_test_path: str
    official_test_class: str
    bug_related_files: list[str]
    inject_verify_rc: int
    verify_cmd: list[str]
    buggy_repo: str
    pattern_summary: str


@dataclass
class AgentRunResult:
    returncode: int
    stdout_path: Path
    stderr_path: Path
    result_path: Path
    json_path: Path
    parse_source_path: Path
    trigger_report_path: Path
    runner_stdout_path: Path
    runner_stderr_path: Path
    trigger_report: dict


@dataclass
class AuditResult:
    modified_files: list[str]
    modified_production_files: list[str]
    forbidden_non_test_changes: list[str]


@dataclass
class GeneratedTestsResult:
    generated_test_files: list[str]


@dataclass
class SpotlessResult:
    spotless_rc: int
    stdout_path: Path
    stderr_path: Path
    summary_path: Path


@dataclass
class VerifyResult:
    verify_rc: int
    stdout_path: Path
    stderr_path: Path
    summary_path: Path


@dataclass
class OutcomeClassification:
    failure_type: str


@dataclass
class WorkspaceLayout:
    case_dir: Path
    workspace_repo: Path
    context_dir: Path
    agent_dir: Path
    generated_tests_dir: Path
    verify_dir: Path
