# Paper-aligned inject contract

## Required inputs

- clean repository template
- execution-context record
- replay command record
- selected bug pattern
- selected transformation chain, if any

## Paper-aligned budgets

- bug-injection attempts per case: up to 3
- workspace reset: required before every injection attempt
- transformation attempts: 1 per operator
- final verification timeout: 1200 seconds

## Success conditions

A constructed case is retained only if:

1. the final repository contains a non-empty semantic production-code diff
2. the patch matches the selected bug type
3. the fixed replay command fails because of the injected bug
4. every transformation in the chain preserves replay-command triggerability

## Notes on implementation alignment

Current repository helper scripts may expose different retry defaults or local conveniences.
For reviewer reproduction, use the wrapper scripts in this skill and keep the paper-aligned limits above.

`run_paper_aligned_inject_case.py` passes selected transform IDs through the core ordered
planner path. That path records contract and replay-command verification after each
operator, which is the required evidence for condition 4.

The wrapper also performs a final patch-scope check before accepting a successful core run:
the retained diff must include production Java code and must not modify tests or build
configuration.
