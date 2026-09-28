# Managed intake protocol

Use this intake protocol when a user asks for end-to-end managed reproduction.

## Questions the agent should ask

Only ask for choices that are still unset.

### Required user choices

1. Which real repository or repositories should be used?
2. Should the agent reuse existing execution contexts or collect new ones?
3. Which target traces or trace buckets should be used?
4. Which bug types or bug-pattern IDs should be injected?
5. Which transformation operators or transform IDs should be applied?
6. Which agent should be used for construction and evaluation?
7. Which model and provider should be used?
8. Should bug witness validation be run in both `NoEC` and `WithEC`?

### Choices the agent should not ask about unless the user overrides them

Use these defaults silently:

- injection attempts per case: 3
- transformation attempts per operator: 1
- trigger attempts per case: 3
- agent timeout: 1800 seconds
- verification timeout: 1200 seconds
- optional formatting timeout: 600 seconds
- case timeout: 4200 seconds

## What the agent should do itself

The agent should directly perform:

- repository layout validation
- execution-context bucketing
- manifest construction
- workspace preparation
- wrapper-script invocation
- result validation
- anonymous release packaging
