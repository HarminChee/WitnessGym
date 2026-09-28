from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.transform.spec import TransformSpec
from src.transform.operators.base import OperatorResult
from src.llmtool.claude_code import ClaudeCodeHeadless

@dataclass(frozen=True)
class AgentOperatorConfig:
    runner_script: Path
    system_prompt_path: Path

class AgentTransformOperator:
    def __init__(self, repo_root: str | Path, cfg: AgentOperatorConfig, run_dir: str | Path):
        self.repo_root = Path(repo_root)
        self.cfg = cfg
        self.run_dir = Path(run_dir)
        self.client = ClaudeCodeHeadless(repo_root=self.repo_root, runner_script=self.cfg.runner_script)

    def check_applicable(self, spec: TransformSpec, context: dict[str, Any]) -> tuple[bool, str]:
        if spec.implementation.mode != "agent":
            return False, "spec.mode is not agent"
        lang = context.get("language")
        if isinstance(lang, str) and lang.strip() and spec.language != lang:
            return False, f"language mismatch spec={spec.language} ctx={lang}"
        return True, "ok"

    def apply(self, spec: TransformSpec, context: dict[str, Any]) -> OperatorResult:
        ok, reason = self.check_applicable(spec, context)
        if not ok:
            return OperatorResult(ok=False, operator_id="agent", transform_id=spec.id, detail=reason, llm_output_path=None, metrics={})

        system_prompt = self.cfg.system_prompt_path.read_text(encoding="utf-8")
        trace_summary = context.get("trace_summary", "")
        anchors = context.get("anchors", [])
        file_scope = spec.implementation.file_scope

        task = []
        task.append("You are applying ONE transformation step in a controlled bug-injection pipeline.")
        task.append("Your job is to make a small, natural-looking, review-resistant edit that satisfies this transform spec.")
        task.append("")
        task.append("=== TRANSFORM SPEC ===")
        task.append(f"- id: {spec.id}")
        task.append(f"- name: {spec.name}")
        task.append(f"- intent: {spec.intent}")
        task.append("")
        task.append("Description:")
        task.append(spec.description)
        task.append("")
        if spec.requires:
            task.append("Applicability requirements (must be true):")
            for x in spec.requires:
                task.append(f"- {x}")
            task.append("")
        if spec.forbids:
            task.append("Forbidden elements (must avoid):")
            for x in spec.forbids:
                task.append(f"- {x}")
            task.append("")
        if spec.must_preserve:
            task.append("Must preserve (do not violate):")
            for x in spec.must_preserve:
                task.append(f"- {x}")
            task.append("")
        if spec.post_conditions:
            task.append("Post-conditions (must achieve):")
            for x in spec.post_conditions:
                task.append(f"- {x}")
            task.append("")

        task.append("=== EDIT BOUNDARIES ===")
        task.append("- Do NOT modify tests unless explicitly allowed by the spec.")
        task.append("- Do NOT change public/protected API signatures.")
        task.append("- Avoid refactors/renames/formatting sweeps; keep diffs tight.")
        task.append("- Keep semantics unchanged for non-trigger inputs unless the spec explicitly changes semantics.")
        task.append("")

        if file_scope:
            task.append("Allowed file scope (prefer staying within):")
            for x in file_scope:
                task.append(f"- {x}")
            task.append("")
        if trace_summary:
            task.append("Trace context summary (use it to pick realistic edit sites):")
            task.append(trace_summary)
            task.append("")
        if anchors:
            task.append("Candidate anchors (optional hints; choose consistent sites):")
            for a in anchors:
                task.append(f"- {a}")
            task.append("")

        task.append("=== DELIVERABLE ===")
        task.append("1) Apply the transformation now.")
        task.append("2) Ensure the repository still compiles and remains consistent with constraints.")
        task.append("3) The final patch must look like a legitimate engineering change.")
        task.append("")
        task.append("=== REQUIRED REPORTING ===")
        task.append("Append exactly one final line with this prefix:")
        task.append("TRANSFORM_REPORT_JSON: { ... }")
        task.append("The JSON object must contain these keys:")
        task.append("- ok")
        task.append("- transform_id")
        task.append("- changed_files")
        task.append("- edit_sites")
        task.append("- what_was_added_or_wrapped")
        task.append("- what_was_preserved")
        task.append("- what_was_replaced_or_overwritten")
        task.append("- compatibility_with_previous_steps")
        task.append("- expected_effect_on_stealth")
        task.append("- expected_effect_on_trigger_depth")
        task_prompt = "\n".join(task)

        name = f"transform__{spec.id}"
        rr = self.client.run_checked(system_prompt=system_prompt, task_prompt=task_prompt, out_dir=self.run_dir, name=name)

        metrics = {"returncode": rr.returncode}
        if isinstance(rr.parsed_reports, dict):
            tr = rr.parsed_reports.get("transform_report")
            if isinstance(tr, dict):
                metrics["transform_report"] = tr

        return OperatorResult(
            ok=True,
            operator_id="agent",
            transform_id=spec.id,
            detail="applied",
            llm_output_path=str(rr.output_json),
            metrics=metrics,
        )
