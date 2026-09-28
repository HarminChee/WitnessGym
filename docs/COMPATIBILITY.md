# Compatibility and migration

The code-only source was assembled from the supplied construction/evaluation bundle, checked against the earlier artifact and research implementations, and renamed to WitnessGym. It retains the original Java/Maven runtime, ten bug-pattern definitions, ten transformation definitions, execution-context tooling, and provider wrappers. Experiment manifests and result tables from the source bundle are excluded.

Use the portable `witnessgym` entrypoint for new adapters. Use the compatibility scripts only when replaying the existing Java/Maven workflow or integrating its trace tooling. The portable runner does not claim to reproduce the paper's agent scores, sampling, or full benchmark from the tiny fixtures.

Compatibility hardening includes collision-safe workspaces, traversal checks, content-based file audits including staged and untracked files, discovery of newly created test files, timeout handling, and clean-baseline verification of generated witnesses. The legacy Maven outcome classifier still interprets Java/Maven output; it is not interchangeable with a project-specific structured oracle. Provider CLIs, trace collection on large repositories, and live model calls require their own environment validation.

Implementation paths containing `trigger` remain stable compatibility identifiers. The public task term is **witness construction / bug validation**. No test result is silently substituted when a provider, build, or test fails.
