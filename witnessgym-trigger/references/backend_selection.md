# Trigger backend selection

## Paper-facing agent set

The paper reports six bug witness validation agent configurations:

- Codex with GPT-5.4
- Claude Code with Claude Sonnet 4.5
- OpenHands with DeepSeek-V3.2
- OpenCode with ZAI GLM-4.7
- OpenHands with Devstral-2-123B
- OpenCode with Qwen3-Coder-480B-A35B-Instruct

For a single smoke reproduction, Claude Code with Claude Sonnet 4.5 on AWS Bedrock is the
default runner. For a paper-style comparison, run the same trigger manifest once per agent
configuration.

## Supported review-facing wrapper modes

The trigger wrappers support:

- `--backend-mode bedrock`
- `--backend-mode env`

`bedrock` is the paper-faithful default for Claude Code runs. `env` is a reviewer-facing
escape hatch for explicit non-paper comparisons or local agent runners; it passes through
the caller's provider environment variables instead of constructing AWS Bedrock settings.

The trigger wrappers also allow the caller to override:

- `--agent-runner-script`
- `--system-prompt`
- `--task-template`

This makes it possible to switch from the default Claude runner to another compatible runner when the user explicitly requests a different agent family.

When `--model-id` is provided, the review core passes it through common runner environment
variables: `ANTHROPIC_MODEL`, `BEDROCK_MODEL_ID`, `OPENHANDS_MODEL`, `OPENCODE_MODEL`,
and `CODEX_MODEL`. Agent-specific runner scripts may still require the provider-specific model
spelling expected by that framework.

Implementation note: the repository's historical `src.trigger_v2.run_trigger_v2` entrypoint
is Bedrock-oriented. The reviewer-facing wrapper calls `run_trigger_core_review.py`, which
imports the same core runner but supports both `bedrock` and `env` modes without changing
the evaluation policy.

## Recommended agent-family mapping

Use this mapping when the user names a family:

- Claude Code:
  - default runner: `witnessgym-runtime/scripts/run_claude_headless.py`
- Codex:
  - typical runner: `witnessgym-runtime/scripts/run_codex_headless.py`
- OpenCode:
  - typical runner: `witnessgym-runtime/scripts/run_opencode_headless.py`
- OpenHands:
  - typical runner: `witnessgym-runtime/scripts/run_openhands_headless.py`

OpenHands runner configuration sets temperature `0` and maximum output length `4096`, matching
the paper's exposed decoding controls. Claude Code and OpenCode retain their default decoding
settings in this setup.

These skills keep the paper-facing evaluation policy fixed even when the underlying runner changes:

- `NoEC` and `WithEC`
- up to 3 attempts
- test-only edits
- replay-command-based validation
