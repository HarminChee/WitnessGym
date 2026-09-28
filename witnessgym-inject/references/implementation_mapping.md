# Inject implementation mapping

These are the primary implementation files included in this standalone bundle.
Use the wrapper scripts in this skill as the reviewer-facing entrypoints.

## Core inject path

- `witnessgym-runtime/src/cli/inject.py`
- `witnessgym-runtime/src/pipeline/orchestrator.py`
- `witnessgym-runtime/src/pipeline/pattern_injector.py`
- `witnessgym-runtime/src/patterns/registry.py`
- `witnessgym-runtime/src/patterns/contract_checker.py`
- `witnessgym-runtime/src/pipeline/verify_runner.py`
- `witnessgym-inject/scripts/run_paper_aligned_inject_case.py`
- `witnessgym-inject/scripts/run_paper_aligned_inject_batch.py`
- `witnessgym-inject/scripts/build_inject_manifest_from_traces.py`

## Core transform path

- `witnessgym-runtime/src/transform/registry.py`
- `witnessgym-runtime/src/transform/specs/*.json`
- `witnessgym-runtime/src/transform/operators/agent_operator.py`
- `witnessgym-inject/specs/transforms/*.json`

## Bundled paper specs

- `witnessgym-inject/specs/patterns/*.json`
- `witnessgym-inject/specs/transforms/*.json`

The bundled specs mirror the paper-aligned ten bug types and ten transformation operators so
reviewers can inspect IDs and natural-language constraints without hunting through the core
source tree.

## Agent runner and prompts

- `witnessgym-runtime/scripts/run_claude_headless.py`
- `witnessgym-runtime/prompts/system/inject.system.txt`

## Agent helper

- `witnessgym-runtime/scripts/run_claude_inject_bedrock.py`

The wrapper scripts in this skill enforce the paper-aligned retry policy and anonymized
parameterization.
