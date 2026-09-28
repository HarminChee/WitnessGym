---
name: witnessgym-inject
description: Use when constructing WITNESSGYM benchmark cases by injecting one of the paper’s ten bug types into trace-reachable production code, validating the replay command, and optionally applying one of the paper’s ten bug-preserving transformation operators. This skill follows the paper-aligned attempt budgets and archive rules.
---

# WITNESSGYM Inject

This is the Java/Maven compatibility workflow. Before any model invocation, resolve the authorized provider/model, attempt budget, and execution environment. Construction does not authorize a subsequent evaluation or upload. Keep cases and results outside the code-release tree, preserve existing runs, and stop at the authorized budget. For new languages use the unified `witnessgym` adapter workflow.

Use this skill for benchmark construction after execution contexts and replay commands already exist.

If the paper or reviewer prompt says WITNESSGYM, use the WITNESSGYM scripts in this bundle;
the names refer to the same benchmark workflow.

Default to the paper-aligned construction protocol:

- inject with Claude Code backed by Claude Sonnet 4.5
- up to 3 injection attempts per candidate case
- clean workspace before every injection attempt
- 1 attempt per transformation operator
- keep only cases whose replay command exposes the injected bug

For paper-faithful reproduction, keep the construction agent fixed to Claude Code.
Only override the runner script or backend mode if the user explicitly asks for a non-paper reproduction path.

## Read next

- `references/inject_contract.md`
- `references/patterns_and_transforms.md`
- `references/inject_manifest_schema.md`
- `references/prompt_inputs.md`
- `references/backend_selection.md`
- `references/implementation_mapping.md`

## Scripts

- `scripts/build_inject_manifest_from_traces.py`
- `scripts/run_paper_aligned_inject_case.py`
- `scripts/run_paper_aligned_inject_batch.py`

## Bundled specs

- `specs/patterns/*.json` contains the ten paper-aligned bug-pattern specs.
- `specs/transforms/*.json` contains the ten paper-aligned transformation specs.
