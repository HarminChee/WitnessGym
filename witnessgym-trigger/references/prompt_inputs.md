# Prompt inputs used in trigger evaluation

The paper-facing trigger task payload includes:

- repository name
- evaluation group or context condition
- injected case run ID
- bug-pattern ID and category
- applied transformation IDs
- bug-related production files
- injection-stage verification exit code
- replay command
- natural-language bug summary
- target test path and target test class
- execution-context summary only in `WithEC`

The implementation may use the term `trigger generation`; in the paper this corresponds to bug witness validation.
