# WITNESSGYM workflow

This reference describes the reviewer-facing, paper-aligned workflow.

WITNESSGYM is the benchmark name used throughout this reviewer-facing bundle. The
`witnessgym-runtime/` directory is part of the bundle and contains the core implementation
invoked by the reviewer-facing wrapper scripts.

## Phase 1: Execution-context collection

Input:

- a clean Java repository with a stable test suite
- one or more target tests
- the replay command for each target test

Output:

- one normalized execution-context record per selected test
- a replay-command record keyed by the same trace identifier
- a length bucket for each execution context:
  - `short`: 1 to 40 distinct production-side functions
  - `mid-short`: 41 to 70
  - `mid-long`: 71 to 120
  - `long`: 121 to 150

Use the `witnessgym-trace-prep` skill for this phase.

Single-test Maven collection command:

```bash
python3 witnessgym-trace-prep/scripts/collect_maven_execution_context.py \
  --repo-template "$BENCHMARK_ROOT/dubbo" \
  --repo-name dubbo \
  --official-test-class org.apache.dubbo.common.url.URLParamTest \
  --official-test-path dubbo-common/src/test/java/org/apache/dubbo/common/url/URLParamTest.java \
  --workspace-root out/review_workspaces/trace \
  --output-dir out/review_trace_assets/dubbo_URLParamTest
```

This writes `execution_context.json`, `selected_traces.json`, and
`selected_commands.json`. Reuse existing trace assets when they already contain the same
schema.

## Phase 2: Bug injection and transformation

Input:

- a clean repository template
- one execution context
- one bug pattern
- zero or more transformation operators
- the fixed replay command

Paper-aligned defaults:

- injection agent: Claude Code backed by Claude Sonnet 4.5
- bug-injection attempts per case: up to 3
- clean workspace restore before every injection attempt
- transformation attempts: 1 per operator
- verification timeout: 1200 seconds
- paper analysis transformation depths: 1, 3, 5, and 10 operators

Retain a case only if:

1. the repository ends with a non-empty semantic production-code diff
2. the patch is structurally consistent with the selected bug type
3. the same replay command passes on the clean baseline and fails on the modified repository because of the injected bug
4. every applied transformation preserves replay-command triggerability

Use the `witnessgym-inject` skill for this phase.

Build an injection manifest from collected traces:

```bash
python3 witnessgym-inject/scripts/build_inject_manifest_from_traces.py \
  --traces out/review_trace_assets/dubbo_URLParamTest/selected_traces.json \
  --commands out/review_trace_assets/dubbo_URLParamTest/selected_commands.json \
  --output out/review_manifests/inject.jsonl \
  --repo-template-root "$BENCHMARK_ROOT" \
  --pattern-ids logic_predicate_inversion_in_guard \
  --transform-ids t_rare_profile_gate_v1 t_call_stack_deepen_v1
```

Run construction:

```bash
python3 witnessgym-inject/scripts/run_paper_aligned_inject_batch.py \
  --manifest out/review_manifests/inject.jsonl \
  --workspace-root out/review_workspaces/inject \
  --out-root out/review_runs/inject \
  --dataset-root out/review_dataset \
  --backend-mode bedrock \
  --model-id "$BEDROCK_MODEL_ID"
```

The wrapper restores a clean copied workspace before each injection attempt. When transform
IDs are present, it invokes the core transform planner in ordered full-chain mode so each
operator is followed by contract and replay-command verification.

Package a successful construction attempt into the reviewer release shape:

```bash
python3 witnessgym-full-workflow/scripts/package_review_case.py \
  --case-summary out/review_runs/inject/cases/dubbo__org.apache.dubbo.common.url.URLParamTest__logic_predicate_inversion_in_guard/case_summary.json \
  --case-id dubbo_URLParamTest_logic_guard_001 \
  --output-root out/review_release/cases \
  --repo-id dubbo \
  --pattern-category Logic
```

## Phase 3: bug witness validation

Input:

- a buggy repository snapshot
- a bug summary and pattern metadata
- the target test path and class
- the fixed replay command
- the applied transformation IDs
- the bug-related production files
- optionally the archived execution-context summary

Paper-aligned defaults:

- settings:
  - `NoEC`: no execution-context block
  - `WithEC`: include the archived execution-context block
- attempts per evaluation case: up to 3
- agent timeout: 1800 seconds
- verification timeout: 1200 seconds
- optional formatting timeout: 600 seconds
- case timeout: 4200 seconds

Use the `witnessgym-trigger` skill for this phase.

Convert reviewer cases to the trigger manifest:

```bash
python3 witnessgym-trigger/scripts/release_to_trigger_manifest.py \
  --release-root out/review_release \
  --repo-template-root "$BENCHMARK_ROOT" \
  --output-jsonl out/review_manifests/trigger.jsonl
```

Run NoEC and WithEC:

```bash
python3 witnessgym-trigger/scripts/run_paper_aligned_trigger_batch.py \
  --manifest out/review_manifests/trigger.jsonl \
  --out-root out/review_runs/trigger \
  --groups A,B \
  --backend-mode bedrock \
  --model-id "$BEDROCK_MODEL_ID"
```

Group `A` is NoEC. Group `B` is WithEC and receives only the archived execution-context
summary from `execution_context.json` or an equivalent trace bundle.

For the full paper-style agent comparison, rerun the same trigger manifest for each agent/model
configuration listed in `witnessgym-trigger/references/backend_selection.md`, overriding
`--agent-runner-script` and `--model-id` as needed.

## Phase 4: Anonymous review release

Archive only the minimum clean artifacts:

- `case.json`
- `bug.patch`
- `buggy_repo/`
- `execution_context.json`

Update the global index and schema documents after every export batch.

## Layout validation

Before a reviewer run, validate the local layout:

```bash
python3 witnessgym-full-workflow/scripts/check_project_layout.py
```
