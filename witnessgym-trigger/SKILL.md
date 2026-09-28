---
name: witnessgym-trigger
description: Use when evaluating bug witness validation on already-injected WITNESSGYM cases under the paper’s NoEC and WithEC settings. This skill enforces test-only edits, the paper-aligned per-case attempt budget, and the trigger verification protocol.
---

# WITNESSGYM Trigger

This is the Java/Maven compatibility workflow. Resolve the authorized model, run budget, and isolated execution environment before invoking an agent. A witness must pass on the clean baseline and expose the intended bug on the buggy program; an infrastructure failure is not success. Preserve existing runs and keep judgments/results outside the code-release tree. Do not upload or publish without explicit authorization.

Use this skill after buggy cases already exist.

If the paper or reviewer prompt says WITNESSGYM, use the WITNESSGYM scripts in this bundle;
the names refer to the same benchmark workflow.

Default to the paper-aligned trigger protocol:

- evaluate both `NoEC` and `WithEC`
- up to 3 bug witness validation attempts per evaluation case
- test-only edits under `src/test/java`
- no production or build-file modifications
- success requires a materialized Java testcase and replay-command failure caused by the injected bug

Unlike construction, evaluation may legitimately vary the agent family and model when the user requests a comparison run.
If the user asks for a paper-faithful default, start with Claude Code.

## Read next

- `references/trigger_contract.md`
- `references/trigger_manifest_schema.md`
- `references/prompt_inputs.md`
- `references/backend_selection.md`
- `references/implementation_mapping.md`

## Scripts

- `scripts/release_to_trigger_manifest.py`
- `scripts/run_trigger_core_review.py`
- `scripts/run_paper_aligned_trigger_case.py`
- `scripts/run_paper_aligned_trigger_batch.py`
- `scripts/validate_trigger_result.py`
