# Anonymous release contract

This release contract is for reviewer-facing benchmark artifacts.

## Per-case files to keep

- `case.json`
- `bug.patch`
- `buggy_repo/`
- `execution_context.json`

## Per-case files to exclude

- raw agent logs
- local progress logs
- scratch workspaces
- full pipeline run directories
- absolute local paths
- account identifiers
- API credentials
- machine-specific cache files

## `case.json` requirements

Each `case.json` should contain only the fields needed to run or inspect the case:

- `case_id`
- `repo_id`
- `trace_id`
- `trace_bucket`
- `pattern_id`
- `pattern_category`
- `transform_ids`
- `official_test_path`
- `official_test_class`
- `verify_cmd`
- `bug_related_files`
- `transform_depth`
- `module_root`
- `oracle_type`
- `expected_verify_rc`
- `execution_context_file`

Do not include:

- usernames
- absolute workstation paths
- source machine directory names
- cloud account IDs
- any prompt logs or agent internals

## `buggy_repo/` requirements

Keep the smallest executable repository snapshot that still supports verification:

- the buggy production file set
- the correct official test file
- the minimal build files and wrapper files needed to run the replay command

Exclude:

- `.git/`
- build caches
- IDE state
- temporary files
- historical pipeline artifacts

## `execution_context.json` requirements

Keep the normalized execution context needed for WithEC reproduction:

- `trace_id`
- `trace_bucket`
- `trace_summary`
- `methods`
- `anchors`
- `bug_related_files`

The file must not contain absolute workstation paths, raw agent logs, cloud account IDs, or
credentials. It may contain project-relative Java file paths and method names.

## Bucket spelling

Use paper-facing bucket spelling in execution-context assets:

- `short`
- `mid-short`
- `mid-long`
- `long`

If an older release index uses `midshort` or `midlong`, treat those as aliases for
`mid-short` and `mid-long`. Do not change benchmark semantics when normalizing spelling.

## Trigger conversion

Use:

```bash
python3 witnessgym-trigger/scripts/release_to_trigger_manifest.py \
  --release-root out/review_release \
  --repo-template-root "$BENCHMARK_ROOT" \
  --output-jsonl out/review_manifests/trigger.jsonl
```

The converter reads `case.json`, `buggy_repo/`, and `execution_context.json`, then emits
the NoEC/WithEC trigger manifest fields expected by `witnessgym-trigger`.
