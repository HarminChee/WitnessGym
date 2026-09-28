---
name: witnessgym
description: Construct buggy program variants and evaluate coding agents by executable witnesses using WitnessGym. Use for configuring language adapters, bug and transformation specifications, bounded construction runs, and clean-versus-buggy validation.
---

# WitnessGym

An executable witness is an input plus a test harness that exposes the intended bug. The portable framework accepts evaluation witnesses only when the same changed tests pass on the clean program and expose the configured failure on the buggy program.

## Locate and select the workflow

For an installed skill, the code root is `runtime/` beside this file. In a source checkout, it is two directories above this file. Read that root's `README.md` and, before configuring a run, `docs/ADAPTERS.md`. The command is `witnessgym`; without installation use `PYTHONPATH=<root>/src python3 -m witnessgym`.

Prefer the portable CLI for new projects. Its `examples/adapters/` demonstrate Python, JavaScript, and Java. Additional languages require explicit build/test commands and a target-specific oracle, not a claim of automatic compatibility. Bug and transformation specifications accept an `id` and `instruction`; they are not limited to the bundled Java catalogue.

For existing Java/Maven trace collection or compatibility manifests, read `docs/COMPATIBILITY.md`, then the relevant sibling `witnessgym-trace-prep`, `witnessgym-inject`, or `witnessgym-trigger` skill. Keep these tools beside `witnessgym-runtime`; do not confuse their schemas with the portable adapter.

## Run only the requested scope

Resolve the clean repository, permitted production/test roots, construction witness, intended failure, agent command, and output location. For evaluation also resolve the buggy repository, report, and optional execution context. Ask only for material missing choices. Preserve the user's chosen language, model, bug type, and transformation.

Use `check-adapter` before execution. For an offline check, run `scripts/smoke.py` with a fresh output outside the checkout; it uses a deterministic fixture, not an LLM. For paid agents, first confirm model/provider, maximum calls or attempts, and cost authorization. Do not infer permission to start evaluation after a construction-only request or to upload results after a local run.

Untrusted repositories and agents need an external, disposable sandbox. `--allow-local-execution` acknowledges execution in the current environment and does not sandbox it. Do not run untrusted code on a credential-bearing host. Supply approved credential names through `env_allowlist`, never token values in files. Do not change unrelated machine settings.

## Verification and handoff

- Construction requires a passing clean baseline, production-only changes, and the target failure. Retain transformations only when the oracle still holds; report rejected stages.
- Evaluation removes declared hidden witnesses, permits test-only changes, and replays identical generated tests on clean and buggy copies. Compilation errors, timeouts, agent errors, and failures on clean code are not successful witnesses.
- Do not bypass a failed audit or overwrite a run directory. Stop after the authorized attempt budget and report the recorded failure.
- Keep run outputs outside the code release. For packaging use `scripts/check_release.py` and `scripts/package_code.py`; never bundle credentials, benchmark cases, model judgments, or experiment manifests.
- Report observed checks and their limits. Fixture tests validate mechanics, not model performance, all bug semantics, or benchmark realism. Do not label duplicate cases as independent samples or fabricate missing cases to hit a requested count.
