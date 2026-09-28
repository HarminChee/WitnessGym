# Inject manifest schema

Use JSONL rows with the following normalized fields:

```json
{
  "repo_name": "dubbo",
  "repo_template": "<BENCHMARK_ROOT>/dubbo",
  "trace_id": "org.apache.dubbo.common.url.URLParamTest",
  "pattern_id": "logic_predicate_inversion_in_guard",
  "transform_ids": [
    "t_rare_profile_gate_v1",
    "t_call_stack_deepen_v1",
    "t_private_adapter_layer_v1"
  ],
  "traces_path": "out/trace_assets/selected_traces.json",
  "commands_path": "out/trace_assets/selected_commands.json",
  "trace_bucket": "short",
  "notes": ""
}
```

All paths should be project-relative or passed explicitly by the wrapper caller.

Build this manifest from trace assets with:

```bash
python3 witnessgym-inject/scripts/build_inject_manifest_from_traces.py \
  --traces out/review_trace_assets/selected_traces.json \
  --commands out/review_trace_assets/selected_commands.json \
  --output out/review_manifests/inject.jsonl \
  --repo-template-root "$BENCHMARK_ROOT" \
  --pattern-ids logic_predicate_inversion_in_guard \
  --transform-ids t_rare_profile_gate_v1 t_call_stack_deepen_v1
```

`repo_template` may be omitted when the batch wrapper receives `--repo-template-root`.
The wrapper copies the clean template into a temporary workspace and creates a local git
baseline there if the template itself is not already a git repository.

When `transform_ids` is non-empty, `run_paper_aligned_inject_case.py` invokes the core
transform path in ordered planner mode. This keeps the paper requirement that each applied
operator is followed by contract and replay-command validation.
