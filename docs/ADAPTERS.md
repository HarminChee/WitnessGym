# Adapter and agent contract

## Inputs and oracle

An adapter is JSON with `schema_version: 1`, a descriptive `language`, disjoint `production_roots` and `test_roots`, and nonempty `build` and `verify` argument arrays. Commands run from the copied repository root; shell strings and implicit shell expansion are not supported.

`hidden_tests` lists construction witnesses to remove before the evaluation agent sees the repository. `failure_regex` identifies the expected target failure in verifier output; `failure_exit_codes` defaults to `[1]`. The failure must correspond to the intended bug, not merely any assertion, crash, or generic build error. `timeout` is a per-command limit in seconds (default 120). `ignore_dirs` may contain build/cache directory names, never production/test roots. Existing symlinks are rejected.

Construction first requires the unchanged program and construction witness to build and pass. The agent edits production code only. Injection receives a configurable bounded attempt budget; each requested transformation receives one attempt and is retained only if the target failure still occurs. Rejected transformations are recorded and not claimed as applied. This establishes preservation of the configured witness, not a proof of full semantic equivalence.

Evaluation removes the hidden construction witness, gives the agent a bug report and optional execution context, and permits edits only under test roots. The same changed tests must pass on clean code and fail on buggy code with the configured target signature. Verification runs on fresh copies, so agent-created build caches are discarded. Configure a harness that actually executes the generated tests; an exit code alone cannot establish meaningful test coverage.

The language-independent interface is exercised by the three fixtures in `examples/`. For another language or project, supply its build/test commands, target-specific oracle, allowed roots, and a regression fixture. Dependencies must already be installed in the runner or provisioned by an explicitly reviewed command. A mutable dependency resolver or flaky test can invalidate the comparison.

## Agent protocol

Agent configuration:

```json
{
  "command": ["/absolute/path/to/agent-wrapper", "--request", "{request}"],
  "env_allowlist": ["PROVIDER_API_KEY"]
}
```

Only `{request}` and `{workspace}` placeholders are expanded. List environment **names**, not credentials. The agent process receives a minimal environment plus the explicitly allowed names; the build/test processes do not receive that allowlist. Logs may nevertheless contain anything printed by a wrapper, so inspect them before sharing.

The JSON request contains `schema_version`, `stage` (`inject`, `transform`, or `evaluate`), `workspace`, `instruction`, `language`, and `allowed_roots`. Construction requests include `spec`; evaluation requests include `bug_report` and, only for WithEC, `execution_context`. Evaluation requests do not include the hidden witness or the oracle regex.

The wrapper edits files in `workspace` and exits zero only after successful task execution. A nonzero exit, timeout, or output limit fails the attempt. Model choice, reasoning settings, retry policy, and budget belong to the explicitly supplied wrapper configuration, not to hidden framework defaults.

## Generic bug and transformation specifications

Both accept a safe `id`, a nonempty `instruction`, and optional additional task-specific fields. See `examples/specs/`. No closed bug-type or transformation list is built into the portable core. The retained Java catalogue has its own richer schema and is not silently converted to portable specifications.

## Execution boundary

Run untrusted agents and repositories in an external sandbox. A copied workspace and file audit are not a security boundary against a process that can access the host. Review the oracle and hidden-test removal before a measured evaluation. Do not compare or aggregate runs with different oracle policies as though they were identical experiments.
