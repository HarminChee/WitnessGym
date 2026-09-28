# Paper-aligned trigger contract

## Two evaluation settings

- `NoEC`: omit the execution-context block
- `WithEC`: include the archived execution-context block

In the repository-level batch tooling these are commonly materialized as two groups:

- `A` = `NoEC`
- `B` = `WithEC`

Neither setting may reveal:

- the reference bug witness
- hidden validation logic
- construction-time solution code
- permission to modify production code

## Required inputs

- buggy repository snapshot
- natural-language bug description
- bug pattern ID and category
- applied transformation IDs
- target test path and target test class
- replay command
- bug-related production files
- execution-context summary only in `WithEC`

## Paper-aligned budgets

- up to 3 bug witness validation attempts per benchmark case
- agent timeout: 1800 seconds
- verification timeout: 1200 seconds
- optional formatting timeout: 600 seconds
- case timeout: 4200 seconds

## Success conditions

A trigger attempt succeeds only if:

1. a real Java testcase is materialized under `src/test/java`
2. the testcase compiles
3. the replay command fails because the injected bug is triggered
4. the failure is a semantic test failure rather than a compile or harness failure
5. no production file or forbidden non-test file is modified
