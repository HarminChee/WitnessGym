from __future__ import annotations

from pathlib import Path

from .types import TriggerCaseContext


def _stringify_verify_cmd(cmd: list[str]) -> str:
    return " ".join(cmd)


def build_task_text(template_path: Path, case_input: TriggerCaseContext) -> str:
    template = template_path.read_text()

    replacements = {
        "{repo_name}": case_input.repo_name,
        "{group}": case_input.group,
        "{run_id}": case_input.run_id,
        "{trace_id}": case_input.trace_id or "(not provided in this group)",
        "{pattern_id}": case_input.pattern_id,
        "{transform_ids}": ", ".join(case_input.transform_ids) if case_input.transform_ids else "(none)",
        "{official_test_path}": case_input.official_test_path,
        "{official_test_class}": case_input.official_test_class,
        "{bug_related_files}": "\n".join(f"- {x}" for x in case_input.bug_related_files) if case_input.bug_related_files else "(none)",
        "{inject_verify_rc}": str(case_input.inject_verify_rc),
        "{verify_cmd}": _stringify_verify_cmd(case_input.verify_cmd),
        "{pattern_summary}": case_input.pattern_summary or "(none)",
    }

    text = template
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text
