# Terminology map

This map exists to prevent confusion between paper wording and repository-internal wording.

| Paper term | Implementation term | Notes |
| --- | --- | --- |
| WITNESSGYM | WITNESSGYM | Reviewer-facing benchmark and workflow name. |
| core implementation directory | `witnessgym-runtime` | Bundled core implementation used by the wrapper scripts. |
| bug type | pattern / pattern ID | The paper’s ten bug types map to pattern IDs. |
| bug-type name | pattern name | Human-facing label for the pattern. |
| transformation | transform / transform ID | The paper’s ten transformations map to internal transform IDs. |
| bug witness validation | trigger generation | Trigger is the implementation term for bug witness validation. |
| execution context | trace / trace summary / anchors | The paper-facing term is execution context; the code often says trace. |
| replay command | verify command | The same fixed test command is reused across construction and evaluation. |
| NoEC | group A | Context omitted. |
| WithEC | group B | Execution-context block included. |
| buggy repository snapshot | buggy_repo | The overlaid repository state used for trigger evaluation. |
| official target test | official_test_path / official_test_class | The clean baseline test target for the case. |
| `mid-short`, `mid-long` | `midshort`, `midlong` | Older release metadata may omit hyphens; treat them as spelling aliases only. |

Agents using these skills should freely translate between these terms in both directions.
