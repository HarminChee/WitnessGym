---
name: witnessgym-trace-prep
description: Use when collecting, normalizing, bucketing, or validating WITNESSGYM execution contexts and replay commands from Java repository tests. This skill defines what an execution context contains, how buckets are assigned, and what downstream inject and trigger stages need.
---

# WITNESSGYM Trace Prep

This is the Java/Maven compatibility workflow. Run repository code only in an approved environment, do not overwrite existing run outputs, and keep collected traces and case data outside the code-release tree. Collect new traces only when requested; do not expand a read-only audit into execution.

Use this skill when preparing execution contexts for benchmark construction or bug witness validation.

If the paper or reviewer prompt says WITNESSGYM, use the WITNESSGYM scripts in this bundle;
the names refer to the same benchmark workflow.

Execution context is the paper-facing term for the structured test-to-production trace record.

## Default rules

- Count distinct production-side functions reached by the target test.
- Assign one of four buckets:
  - `short`
  - `mid-short`
  - `mid-long`
  - `long`
- Keep only the context fields needed downstream by inject and trigger.
- Store replay-command metadata keyed by the same trace identifier.

## Read next

- `references/execution_context_collection.md`
- `references/trace_asset_schema.md`

## Scripts

- `scripts/collect_maven_execution_context.py`
- `scripts/bucket_execution_contexts.py`
- `scripts/build_execution_context_record.py`
- `scripts/validate_trace_asset_bundle.py`
