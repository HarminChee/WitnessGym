<div align="center">

# WitnessGym

### Benchmarking Coding Agents on the Construction of Bug Witnesses

<p>
  <a href="https://arxiv.org/abs/2609.36635"><img src="https://img.shields.io/badge/arXiv-2609.36635-b31b1b.svg" alt="arXiv"></a>
  <a href="https://huggingface.co/datasets/HarminChee/WitnessGym"><img src="https://img.shields.io/badge/🤗%20Dataset-WitnessGym-FFD21E.svg" alt="Hugging Face dataset"></a>
  <a href="https://github.com/HarminChee/WitnessGym/actions/workflows/ci.yml"><img src="https://github.com/HarminChee/WitnessGym/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <img src="https://img.shields.io/badge/Python-3.11%2B-3776AB.svg" alt="Python 3.11+">
</p>

**WitnessGym** is a framework for constructing bug-validation benchmarks and evaluating whether coding agents can produce **executable bug witnesses**.

[Paper](https://arxiv.org/abs/2609.36635) · [Dataset](https://huggingface.co/datasets/HarminChee/WitnessGym) · [Adapter contract](docs/ADAPTERS.md) · [Compatibility notes](docs/COMPATIBILITY.md) · [Security guidance](SECURITY.md)

</div>

---

## What is an executable witness?

An executable witness combines a **concrete input** with a **testing harness** that invokes the relevant code under the required environment and exposes an observable failure, such as an assertion violation, exception, or crash.

WitnessGym supports the complete lifecycle around that artifact:

```text
clean repository + bug specification
                 │
                 ▼
      construct a candidate bug
                 │
                 ▼
 replay a construction-time witness
                 │
                 ▼
 apply bug-preserving transformations
                 │
                 ▼
      hide the reference witness
                 │
                 ▼
 ask an agent to construct a new witness
                 │
                 ▼
 verify the same test on clean and buggy code
```

A generated witness is accepted only when the changed test **passes on the clean program** and **exposes the configured target failure on the buggy program**. Compilation errors, timeouts, infrastructure failures, and unrelated crashes are not counted as successful validation.

## Highlights

- **Construction and evaluation in one framework.** Build buggy program variants, preserve a known failure through transformations, then evaluate an agent without revealing the construction witness.
- **Differential verification.** The same generated test is checked against clean and buggy program states using a target-specific failure oracle.
- **Configurable bug semantics.** Bug and transformation behavior is supplied through specifications rather than a fixed portable catalogue.
- **Adapter-based execution.** Build commands, verification commands, source roots, hidden tests, timeouts, and failure signatures are explicit configuration.
- **Multiple execution contexts.** Evaluate agents with or without dynamic execution context while keeping the verification rule fixed.
- **Portable core with compatibility tooling.** The generic interface is exercised by Python, JavaScript, and Java fixtures; the repository also retains the Java/Maven workflow used by the research artifact.
- **Installable agent skill.** Package the framework as a self-contained `witnessgym` skill for compatible agent hosts.

## Repository boundary

This is the **code release** for WitnessGym. It contains framework code, adapters, compatibility tooling, local fixtures, tests, and CI configuration. It intentionally does not include model judgments, benchmark scores, aggregate experimental results, or other evaluation outputs.

The 1,300 released benchmark cases are hosted separately on the [WitnessGym Hugging Face dataset](https://huggingface.co/datasets/HarminChee/WitnessGym).

## Quick start

### Requirements

- Python 3.11 or newer
- Git
- Toolchains required by the target repository, such as Node.js or JDK/Maven

### Install from source

```bash
git clone https://github.com/HarminChee/WitnessGym.git
cd WitnessGym

python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .

witnessgym --help
```

### Run an offline smoke test

The smoke tests use deterministic fixture agents and do not call a model provider.

```bash
python scripts/smoke.py --language python --output /tmp/witnessgym-python
python scripts/smoke.py --language javascript --output /tmp/witnessgym-javascript
python scripts/smoke.py --language java --output /tmp/witnessgym-java
```

Use a fresh output directory for every run. JavaScript requires Node.js; Java requires a JDK.

### Validate an adapter

Adapter validation checks the configuration without executing project commands:

```bash
witnessgym check-adapter examples/adapters/python.json
```

## Core commands

### Construct a buggy variant

```bash
witnessgym construct \
  --clean-repo /path/to/clean-repository \
  --adapter /path/to/adapter.json \
  --agent /path/to/agent.json \
  --bug /path/to/bug-spec.json \
  --transform /path/to/transform-spec.json \
  --attempts 3 \
  --output /path/to/fresh-construction-output \
  --allow-local-execution
```

Construction first verifies the unchanged baseline. It then asks the configured agent to inject the requested bug and applies each transformation only when the construction witness still exposes the configured failure.

### Evaluate witness construction

```bash
witnessgym evaluate \
  --clean-repo /path/to/clean-repository \
  --buggy-repo /path/to/buggy-repository \
  --adapter /path/to/adapter.json \
  --agent /path/to/agent.json \
  --report /path/to/bug-report.txt \
  --context /path/to/execution-context.json \
  --output /path/to/fresh-evaluation-output \
  --allow-local-execution
```

Omit `--context` for a context-agnostic run. During evaluation, the hidden construction witness is removed and the agent may edit only the configured test roots.

## Adapting WitnessGym

New projects do not require changes to the portable runner. They require explicit project-specific inputs:

1. **Adapter** — language, production/test roots, build and verification commands, timeouts, hidden tests, and the target failure oracle.
2. **Bug specification** — an instruction describing the intended faulty behavior and any task-specific constraints.
3. **Transformation specification** — an optional structure-changing instruction whose output must preserve the configured failure.
4. **Agent wrapper** — a command that accepts the JSON request, edits the supplied workspace, and reports failure with a nonzero exit code.
5. **Regression fixture** — a small project that verifies the adapter and oracle before any measured run.

The portable adapter and agent contracts are documented in [`docs/ADAPTERS.md`](docs/ADAPTERS.md). The retained Java/Maven pipeline and migration boundary are documented in [`docs/COMPATIBILITY.md`](docs/COMPATIBILITY.md).

## Agent skill

Install the unified skill from this checkout:

```bash
python scripts/install_skill.py --destination /absolute/path/to/skills
```

The installer creates a self-contained `witnessgym` directory and refuses to overwrite an existing installation. Reload skill discovery in the host, then invoke `$witnessgym`. See [`INSTALL_SKILLS.md`](INSTALL_SKILLS.md) for the full installation and compatibility notes.

## Project layout

```text
WitnessGym/
├── src/witnessgym/          # portable construction and evaluation core
├── examples/                # Python, JavaScript, and Java fixtures
├── tests/                   # regression and contract tests
├── docs/                    # adapter and compatibility documentation
├── skills/witnessgym/       # unified installable skill
├── witnessgym-runtime/      # retained Java/Maven runtime
├── witnessgym-*/            # compatibility skills and workflows
├── scripts/                 # smoke, packaging, and release checks
└── .github/workflows/       # CI and code-only release workflow
```

## Development and verification

```bash
python -m pip install -e '.[dev]'
ruff check .
pytest
python scripts/check_release.py
python -m build
```

Continuous integration runs on Python 3.11–3.13 with Node.js and JDK 17. The release checker also guards the public code boundary so experiment outputs and sensitive local artifacts are not included in packaged releases.

## Safety

WitnessGym executes repository code and may run an agent that edits files. A copied workspace and post-run file audit are **not a security sandbox**. Use a disposable, unprivileged environment without unrelated credentials, host mounts, or unnecessary network access.

Local execution requires the explicit `--allow-local-execution` acknowledgement. Review the adapter, agent wrapper, failure oracle, and hidden-test policy before running a measured evaluation. See [`SECURITY.md`](SECURITY.md) for the complete guidance.

## Paper and citation

**WitnessGym: Benchmarking Coding Agents on the Construction of Bug Witnesses**<br>
Haomin Qi, Xiangzhe Xu, Yiming Huang, Jingbo Shang, and Chengpeng Wang.<br>
[arXiv:2609.36635](https://arxiv.org/abs/2609.36635), 2026.

```bibtex
@article{qi2026witnessgym,
  title         = {WitnessGym: Benchmarking Coding Agents on the Construction of Bug Witnesses},
  author        = {Qi, Haomin and Xu, Xiangzhe and Huang, Yiming and Shang, Jingbo and Wang, Chengpeng},
  journal       = {arXiv preprint arXiv:2609.36635},
  year          = {2026},
  eprint        = {2609.36635},
  archivePrefix = {arXiv},
  primaryClass  = {cs.SE}
}
```

## License

A project-wide software license has not yet been selected. Please contact the maintainers before reusing or redistributing the framework. Dataset files may additionally contain derived material governed by their respective upstream project licenses.
