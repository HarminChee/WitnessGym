---
name: witnessgym-full-workflow
description: Use when an agent needs to reproduce the full WITNESSGYM workflow from execution-context collection through bug injection, bug-preserving transformation, bug witness validation, and anonymous benchmark archiving. This skill coordinates the trace-prep, inject, and trigger skills and enforces paper-aligned defaults for reviewer reproduction.
---

# WITNESSGYM Full Workflow

Use this skill when the task spans more than one phase of the WITNESSGYM workflow.

WITNESSGYM is the benchmark name used throughout this reviewer-facing bundle. The core
implementation lives in `${PROJECT_ROOT}/witnessgym-runtime`, where `${PROJECT_ROOT}` is the
root of this standalone bundle.

Assume the project is laid out as:

- `${PROJECT_ROOT}/witnessgym-runtime` for the bundled core implementation
- a clean repository template root supplied as `${BENCHMARK_ROOT}` or `--benchmark-root`
- this skill bundle for reviewer-facing scripts and instructions

Default to the paper-aligned protocol, not to legacy helper defaults, when they differ.

## Managed mode

When this skill is invoked for an end-to-end reproduction run, the agent should operate in managed mode.

Managed mode means:

1. Ask only for user choices that cannot be inferred safely.
2. Execute all mechanical preparation and script invocation steps directly.
3. Keep paper terminology and implementation terminology aligned in all user-facing messages.
4. Continue from construction into validation only when both phases were requested. Confirm the model/provider and call budget before any paid agent run; never publish or upload without explicit authorization.

These are Java/Maven compatibility instructions. New language adapters use the unified `witnessgym` skill and portable runtime. Repository copies and file audits are not an OS sandbox; run untrusted code in an isolated environment. Use a new run directory and never delete an existing run to retry it. Keep case data, judgments, and experimental results outside the code-release tree.

## Intake order

If the user has not already fixed these choices, ask for them in this order:

1. repository or repository set
2. trace source:
   - reuse existing execution contexts
   - or collect new execution contexts
3. target trace selection or bucket targets
4. bug types or bug-pattern IDs
5. transformation operators or transform IDs
6. agent backend:
   - Claude Code
   - OpenCode
   - OpenHands
   - another supported agent
7. model and provider:
   - API key backed
   - AWS Bedrock
   - other supported backend
8. whether to run both `NoEC` and `WithEC`

If the user gives paper-facing terms such as “bug type” or “bug witness validation,” translate them to implementation fields without asking the user to restate them.

## Workflow order

1. Validate the bundle layout with `scripts/check_project_layout.py`.
2. Optionally initialize a managed run workspace with `scripts/scaffold_managed_run.py`.
3. Use `witnessgym-trace-prep` to collect or normalize execution contexts and replay commands.
4. Use `witnessgym-inject` to construct buggy cases with paper-aligned attempt budgets.
5. Use `witnessgym-trigger` to run NoEC and WithEC bug witness validation.
6. Archive only the minimal anonymous artifacts needed for review release: `case.json`, `bug.patch`, `buggy_repo/`, and `execution_context.json`.

## Read next

- `references/workflow.md` for the end-to-end protocol
- `references/release_contract.md` for the anonymous release rules
- `references/intake_protocol.md` for what to ask the user
- `references/terminology_map.md` for paper-to-implementation term mapping
