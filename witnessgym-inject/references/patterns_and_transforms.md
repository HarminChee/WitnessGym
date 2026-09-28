# Bug types and transformation operators

## Ten bug types used in the paper

| Internal pattern ID | Paper-facing bug type | Category |
| --- | --- | --- |
| `codeql_java_comparison-of-identical-expressions` | Comparison of Identical Values | API Contract |
| `codeql_java_equals-typo` | Typo in `equals` | API Contract |
| `codeql_java_hashcode-typo` | Typo in `hashCode` | API Contract |
| `codeql_java_hashing-without-hashcode` | Hashed Value Without `hashCode` | API Contract |
| `codeql_java_inconsistent-equals-and-hashcode` | Inconsistent `equals` and `hashCode` | API Contract |
| `npe_intra_method_guard_removed` | Intra-Function Null Dereference | Value Flow |
| `npe_collection_element_lazily_nullified` | Collection Element Null Dereference | Value Flow |
| `logic_predicate_inversion_in_guard` | Guard Predicate Inversion | Logic |
| `logic_aggregation_counter_skipped_on_branch` | Skipped Aggregation Counter | Logic |
| `logic_deep_branch_collection_misroute` | In-Bounds Collection Misrouting | Logic |

## Ten transformation operators used in the paper

| Internal transform ID | Paper-facing operator | Family |
| --- | --- | --- |
| `t_call_stack_deepen_v1` | Helper Call Insertion | Call Stack |
| `t_private_adapter_layer_v1` | Call-Site Rerouting | Call Stack |
| `t_extractor_helper_split_v1` | Extract-and-Apply Split | Call Stack |
| `t_argument_object_introduce_v1` | Parameter Bundling | Data Flow |
| `t_context_object_wrap_v1` | Local State Bundling | Data Flow |
| `t_private_state_holder_v1` | Intermediate State Passing | Data Flow |
| `t_cached_accessor_layer_v1` | Cached Value Access | Data Flow |
| `t_nested_container_introduce_v1` | Nested Data Access | Data Flow |
| `t_pipeline_stage_extract_v1` | Pipeline Stage Split | Data Flow |
| `t_rare_profile_gate_v1` | Rare Input Path Conditioning | Control Flow |

When a wrapper or prompt uses internal IDs, map them back to these paper-facing names in logs and release metadata.

The concrete JSON specifications are bundled inside this skill:

- `specs/patterns/`
- `specs/transforms/`

Use the IDs exactly as shown in the tables and JSON filenames. Do not substitute legacy or
experiment-only specs when reproducing the paper-aligned benchmark workflow.
