from __future__ import annotations

from src.patterns.constraints import extract_required_forbidden
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import traceback

from src.llmtool.claude_code import ClaudeCodeHeadless
from src.patterns.schema import Pattern
from src.common.io_utils import write_json

@dataclass(frozen=True)
class InjectResult:
    ok: bool
    detail: str
    llm_output_path: str | None
    context_updates: dict[str, Any]
    report: dict[str, Any]

class AgentPatternInjector:
    def __init__(self, repo_root: str | Path, runner_script: str | Path, system_prompt_path: str | Path, run_dir: str | Path):
        self.repo_root = Path(repo_root)
        self.runner_script = Path(runner_script)
        self.system_prompt_path = Path(system_prompt_path)
        self.run_dir = Path(run_dir)
        self.client = ClaudeCodeHeadless(repo_root=self.repo_root, runner_script=self.runner_script)

    def apply(self, pattern: Pattern, trace_context: dict[str, Any]) -> InjectResult:
        try:
            system_prompt = self.system_prompt_path.read_text(encoding="utf-8")

            anchors = trace_context.get("anchors", [])
            trace_summary = trace_context.get("trace_summary", "")
            allowed_files = trace_context.get("allowed_files", [])

            task = []
            task.append("You are performing controlled BUG INJECTION into production code for research benchmarking.")
            task.append("Goal: introduce a subtle, realistic bug consistent with the specified pattern, while keeping changes hard to spot in review.")
            task.append("")
            task.append("=== PATTERN ===")
            task.append(f"- id: {pattern.id}")
            task.append(f"- name: {pattern.name}")
            task.append(f"- category: {pattern.category}")
            task.append(f"- scope: {pattern.scope}")
            task.append(f"- language: {pattern.language}")
            task.append("")
            task.append("Description:")
            task.append(pattern.description)
            task.append("")

            req_elems, forb_elems = extract_required_forbidden(pattern)
            task.append("Required elements (must satisfy):")
            for x in req_elems:
                task.append(f"- {x}")
            task.append("")
            task.append("Forbidden elements (must avoid):")
            for x in forb_elems:
                task.append(f"- {x}")
            task.append("")

            task.append("=== CONSTRAINTS ===")
            task.append("- Do NOT modify tests unless explicitly allowed by the task.")
            task.append("- Do NOT change public/protected API signatures.")
            task.append("- Avoid broad refactors/renames/reformatting; keep edits localized and natural.")
            task.append("")

            task.append("=== STEALTH + DEPTH GUIDANCE ===")
            task.append("- Prefer deeper injection points along trace-relevant call chains (not top-level obvious sites).")
            task.append("- Prefer delayed-effect or boundary-condition failures over blatant crashes, unless the pattern requires an exception.")
            task.append("- Prefer multi-hop helper flow and nested structures when compatible with the pattern contract.")
            task.append("")

            task.append("=== RUNTIME EFFECT (hints) ===")
            task.append(f"- exception_type_hint: {pattern.exception_type}")
            if pattern.typical_stacktrace_signals:
                task.append("- typical_stacktrace_signals_hint:")
                for x in pattern.typical_stacktrace_signals:
                    task.append(f"  - {x}")
            task.append("")

            task.append("=== TRIGGER CONDITIONS (hints) ===")
            task.append(f"- test_shape_hint: {pattern.trigger_test_shape}")
            task.append(f"- input_properties_hint: {pattern.trigger_input_properties}")
            task.append("")

            if trace_summary:
                task.append("=== TRACE CONTEXT SUMMARY ===")
                task.append(trace_summary)
                task.append("")

            if anchors:
                task.append("=== CANDIDATE ANCHORS (choose a consistent chain) ===")
                for a in anchors:
                    task.append(f"- {a}")
                task.append("")

            if allowed_files:
                task.append("=== ALLOWED FILE SCOPE (stay within if provided) ===")
                for f in allowed_files:
                    task.append(f"- {f}")
                task.append("")

            task.append("=== DELIVERABLE ===")
            task.append("1) Implement the bug strictly according to the pattern contract.")
            task.append("2) Keep the patch minimal and consistent with repository style.")
            task.append("3) Provide evidence in the final JSON: observed failure signature, high-level call_chain, and notes explaining stealth/depth.")
            task.append("")
            task.append("=== REQUIRED REPORTING ===")
            task.append("Append exactly one final line with this prefix:")
            task.append("INJECT_REPORT_JSON: { ... }")
            task.append("The JSON object must contain these keys:")
            task.append("- ok")
            task.append("- pattern_id")
            task.append("- target_files")
            task.append("- target_symbols")
            task.append("- selected_anchor")
            task.append("- why_this_site")
            task.append("- expected_trigger_path")
            task.append("- stealth_rationale")
            task.append("- bug_mechanism")
            task.append("- preserved_prior_structure")
            task.append("- possible_risks")
            task_prompt = "\n".join(task)

            rr = self.client.run_checked(
                system_prompt=system_prompt,
                task_prompt=task_prompt,
                out_dir=self.run_dir,
                name=f"inject__{pattern.id}",
            )

            updates = {
                "callstack_depth": int(trace_context.get("callstack_depth", 0)),
            }

            report = {}
            if isinstance(rr.parsed_reports, dict):
                report = dict(rr.parsed_reports.get("inject_report") or {})

            return InjectResult(
                ok=True,
                detail="injected",
                llm_output_path=str(rr.output_json),
                context_updates=updates,
                report=report,
            )

        except Exception as e:
            write_json(self.run_dir / "attempt_1.error.json", {"error": str(e), "traceback": traceback.format_exc()})
            return InjectResult(ok=False, detail=str(e), llm_output_path=None, context_updates={}, report={})
