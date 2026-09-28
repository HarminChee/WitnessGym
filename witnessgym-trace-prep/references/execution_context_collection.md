# Execution-context collection

The paper defines execution context as the ordered production-side execution path exercised by a selected test case.

## What to collect

For each selected test:

- repository identifier
- trace identifier
- target test name or test method
- official test path
- official test class
- replay command
- ordered production-side method list
- distinct production-side function count
- trace summary
- candidate anchors
- bug-related production files

## Bucket definition

Assign buckets by the number of distinct production-side functions reached:

- `short`: 1 to 40
- `mid-short`: 41 to 70
- `mid-long`: 71 to 120
- `long`: 121 to 150

## Candidate anchors

Candidate anchors should identify trace-relevant edit regions and should include, when available:

- file path
- method or symbol name
- role in the trace
- optional snippet or short rationale

## Replay command discipline

Every execution context must be paired with a replay command that:

- passes on the clean repository
- targets the same test context
- is stable enough to be reused during inject and trigger

## Maven collection script

For Maven repositories, use the bundled collector:

```bash
python3 witnessgym-trace-prep/scripts/collect_maven_execution_context.py \
  --repo-template "$BENCHMARK_ROOT/dubbo" \
  --repo-name dubbo \
  --official-test-class org.apache.dubbo.common.url.URLParamTest \
  --official-test-path dubbo-common/src/test/java/org/apache/dubbo/common/url/URLParamTest.java \
  --workspace-root out/review_workspaces/trace \
  --output-dir out/review_trace_assets/dubbo_URLParamTest
```

The script copies the clean repository template, adds a small production-side
`witnessgym.TraceLogger` helper into the target Maven module, instruments production Java
methods, runs the replay command with `WITNESSGYM_TRACE_OUT`, and normalizes the recorded
method hits. It writes:

- `execution_context.json`
- `selected_traces.json`
- `selected_commands.json`
- `collection_summary.json`
- replay stdout and stderr logs

Pass `--replay-cmd '["./mvnw","-q","-pl","module","-Dtest=ClassName","test"]'` when the
default Maven command is not the correct replay command.

The collector is intentionally conservative and reviewer-facing. For repositories with
non-standard builds or multi-line Java method declarations that are not picked up by the
simple instrumentation pass, produce the same normalized schema using an equivalent runtime
instrumentation method and validate it with `validate_trace_asset_bundle.py`.

## What not to store

Do not archive:

- full local filesystem paths
- machine-specific build locations
- user identifiers
- transient runtime logs unless needed to derive the normalized context
