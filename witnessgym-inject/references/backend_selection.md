# Inject backend selection

## Paper-faithful default

Use:

- agent family: Claude Code
- model: Claude Sonnet 4.5
- backend mode: AWS Bedrock

## Supported wrapper modes

The wrapper scripts support:

- `--backend-mode bedrock`
- `--backend-mode env`

### `bedrock`

The wrapper sets:

- `CLAUDE_CODE_USE_BEDROCK=1`
- `AWS_REGION`
- `AWS_DEFAULT_REGION`
- `ANTHROPIC_MODEL`

### `env`

The wrapper passes through the caller environment.
Use this mode when the user wants to provide API-key-backed access or another externally configured environment.

## Runner override

The default runner is the Claude headless runner from the repository.
If the user explicitly asks for a different compatible runner script, pass it through `--runner-script`.
