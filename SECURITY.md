# Security and disclosure

This framework executes code and may ask agents to modify it. Use a disposable, unprivileged runner with no unrelated credentials, host mounts, or network permissions. Neither file permissions nor post-execution file audits sandbox an agent. Generated witnesses and source repositories must be treated as untrusted.

Never put provider tokens into an adapter, agent configuration, dataset, or code archive. Supply credential names through the environment allowlist only after approving the wrapper and run budget. Inspect logs before sharing them. CI uses only deterministic local fixtures and requires no model-provider secrets.

Timeouts, infrastructure errors, compilation failures, missing tests, and clean-baseline failures must not be reported as successful bug validation. A target-specific oracle and an independently passing baseline remain the user's responsibility when adding a project.

For a sensitive issue, contact the repository owner privately rather than publishing credentials or exploit-bearing production data in an issue.
