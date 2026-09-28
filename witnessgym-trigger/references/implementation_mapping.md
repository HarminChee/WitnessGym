# Trigger implementation mapping

These are the primary implementation files included in this standalone bundle.
Use the wrapper scripts in this skill as the reviewer-facing entrypoints.

## Core trigger path

- `witnessgym-runtime/src/trigger_v2/run_trigger_v2.py`
- `witnessgym-runtime/src/trigger_v2/runner.py`
- `witnessgym-runtime/src/trigger_v2/context_builder.py`
- `witnessgym-runtime/src/trigger_v2/workspace.py`
- `witnessgym-runtime/src/trigger_v2/repo_audit.py`
- `witnessgym-runtime/src/trigger_v2/test_discovery.py`
- `witnessgym-runtime/src/trigger_v2/outcome_classifier.py`
- `witnessgym-runtime/src/trigger_v2/config.py`
- `witnessgym-trigger/scripts/run_trigger_core_review.py`
- `witnessgym-trigger/scripts/run_paper_aligned_trigger_case.py`
- `witnessgym-trigger/scripts/run_paper_aligned_trigger_batch.py`
- `witnessgym-trigger/scripts/release_to_trigger_manifest.py`

## Prompt files

- `witnessgym-runtime/src/trigger_v2/prompts/system.trigger_v2.txt`
- `witnessgym-runtime/src/trigger_v2/prompts/task_template.trigger_v2.txt`

## Agent runners

- `witnessgym-runtime/scripts/run_claude_headless.py`
- `witnessgym-runtime/scripts/run_codex_headless.py`
- `witnessgym-runtime/scripts/run_opencode_headless.py`
- `witnessgym-runtime/scripts/run_openhands_headless.py`

The wrapper scripts in this skill provide the reviewer-facing paper-aligned 3-attempt
policy and neutral path handling.

For WithEC, the wrapper appends the archived execution-context summary to a temporary task
template for group `B`. This keeps the core runner unchanged while making the NoEC/WithEC
prompt difference explicit and reproducible.
