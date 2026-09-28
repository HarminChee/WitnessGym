# Trigger manifest schema

Use JSONL rows with the following fields:

```json
{
  "repo_name": "dubbo",
  "run_id": "inject__20260315T064448Z",
  "trace_id": "org.apache.dubbo.common.url.URLParamTest",
  "pattern_id": "logic_predicate_inversion_in_guard",
  "pattern_category": "Logic",
  "transform_ids": [
    "t_rare_profile_gate_v1",
    "t_call_stack_deepen_v1",
    "t_private_adapter_layer_v1"
  ],
  "official_test_path": "dubbo-common/src/test/java/org/apache/dubbo/common/url/URLParamTest.java",
  "official_test_class": "org.apache.dubbo.common.url.URLParamTest",
  "bug_related_files": [
    "dubbo-common/src/main/java/org/apache/dubbo/common/url/component/URLParam.java"
  ],
  "inject_verify_rc": 1,
  "verify_cmd": ["./mvnw", "-q", "-pl", "dubbo-common", "-Dtest=org.apache.dubbo.common.url.URLParamTest", "test"],
  "buggy_repo": "path/to/buggy_repo_snapshot",
  "pattern_summary": "A predicate inversion in a method-membership guard causes a method-specific parameter lookup to return an invalid result.",
  "execution_context_summary": "{... archived WithEC context summary ...}",
  "spotless_modules": ["dubbo-common"]
}
```

The batch wrapper expands each row into `NoEC` and `WithEC` unless you explicitly restrict the groups.

Build the manifest from an anonymous review release with:

```bash
python3 witnessgym-trigger/scripts/release_to_trigger_manifest.py \
  --release-root out/review_release \
  --repo-template-root "$BENCHMARK_ROOT" \
  --output-jsonl out/review_manifests/trigger.jsonl
```

`execution_context_summary` is used only for group `B` / WithEC. Group `A` / NoEC passes an
empty trace ID and does not receive the context block. The summary should come from the
archived `execution_context.json` sidecar or an equivalent normalized trace bundle.

`spotless_modules` is optional. Include module roots when the Maven project needs targeted
formatting after an agent writes tests.

To run a non-default agent family, pass the runner at batch time, for example:

```bash
python3 witnessgym-trigger/scripts/run_paper_aligned_trigger_batch.py \
  --manifest out/review_manifests/trigger.jsonl \
  --out-root out/review_runs/trigger_codex \
  --groups A,B \
  --backend-mode env \
  --agent-runner-script witnessgym-runtime/scripts/run_codex_headless.py \
  --model-id gpt-5.4
```
