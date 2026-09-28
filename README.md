# WitnessGym

WitnessGym provides tools for constructing buggy program variants and evaluating the executable witnesses produced by coding agents. A witness combines an input with a test harness that exposes a bug.

The construction workflow applies a bug specification and optional transformations to a clean project. The evaluation workflow checks the same generated witness against clean and buggy versions: it must pass on the clean version and expose the configured failure on the buggy version. Build errors, timeouts, and agent failures are not successful validations.

## Contents

- A configurable construction and evaluation runner.
- Bug and transformation specifications, build/test adapters, and agent interfaces.
- An installable agent skill and Java/Maven compatibility tools.
- Small Python, JavaScript, and Java examples, regression tests, and CI checks.

This is a **code-only repository**. It does not include the benchmark dataset, model judgments, evaluation results, or experimental summaries. The examples are deterministic test fixtures, not benchmark measurements.

## Getting started

Python 3.11+ and Git are required. Install the toolchain for your target language separately.

```sh
git clone https://github.com/HarminChee/WitnessGym.git
cd WitnessGym
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/witnessgym --help
```

Run a local example without calling a model:

```sh
.venv/bin/python scripts/smoke.py --language python --output /tmp/witnessgym-example
```

Use a fresh output directory for each run. The same command supports `--language javascript` with Node.js and `--language java` with a JDK.

## Agent skill

From the source checkout:

```sh
.venv/bin/python scripts/install_skill.py --destination "$HOME/.codex/skills"
```

The installer adds a self-contained `witnessgym` skill without overwriting existing installations. Reload your host's skill discovery and invoke `$witnessgym`. See [installation details](INSTALL_SKILLS.md).

## Adapting a project

Supply the project's build and verification commands, production/test directories, a target-specific failure oracle, and an agent command. Bug and transformation instructions can be supplied as specification files without changing a fixed catalogue.

See [adapter and agent contracts](docs/ADAPTERS.md) for the portable interface and [compatibility notes](docs/COMPATIBILITY.md) for the Java/Maven workflow. New projects and bug types need their own validation; the included examples do not establish general coverage.

Repository code and agents execute programs. The runner is not a sandbox: use a disposable, unprivileged environment without unrelated credentials. Local execution requires `--allow-local-execution`; paid model calls require an explicitly configured agent. See [security notes](SECURITY.md).

## Development

```sh
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m pytest
.venv/bin/ruff check .
.venv/bin/python scripts/check_release.py
```

CI checks Python 3.11–3.13 with Node.js and JDK 17. A separate manual workflow prepares a code-only archive; it does not publish datasets or experimental outputs.

## License

A project-wide license has not yet been selected. Please contact the maintainers about reuse terms.
