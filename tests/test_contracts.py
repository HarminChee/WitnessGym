import json
import subprocess
import sys
from pathlib import Path

import pytest

from witnessgym.config import Adapter, load_spec
from witnessgym.errors import WitnessGymError
from witnessgym.pipeline import agent_settings

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from check_release import release_files
from install_skill import install


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("schema_version", 2),
        ("production_roots", ["../src"]),
        ("production_roots", ["/tmp/src"]),
        ("production_roots", ["."]),
        ("test_roots", ["src/tests"]),
        ("hidden_tests", ["src/logic.py"]),
        ("ignore_dirs", ["src"]),
        ("ignore_dirs", [".git"]),
        ("timeout", True),
        ("timeout", 0),
        ("timeout", 100000),
        ("build", "python build.py"),
        ("verify", []),
        ("failure_regex", ".*"),
        ("failure_regex", "[invalid"),
        ("failure_exit_codes", [0]),
        ("failure_exit_codes", [124]),
        ("unrecognized", "field"),
    ],
)
def test_invalid_adapters_fail_closed(tmp_path, key, value):
    data = json.loads((ROOT / "examples/adapters/python.json").read_text())
    data[key] = value
    path = tmp_path / "adapter.json"
    path.write_text(json.dumps(data))
    with pytest.raises(WitnessGymError):
        Adapter.load(path)


def test_new_spec_does_not_require_registry_membership(tmp_path):
    path = tmp_path / "spec.json"
    path.write_text(
        json.dumps({"id": "new-project-new-bug", "instruction": "Use the supplied oracle"})
    )
    assert load_spec(path, kind="bug")["id"] == "new-project-new-bug"


def test_agent_credentials_are_names_not_values(tmp_path):
    path = tmp_path / "agent.json"
    path.write_text(json.dumps({"command": ["agent"], "env_allowlist": ["some-token-value"]}))
    with pytest.raises(WitnessGymError):
        agent_settings(path)


def test_release_guard_accepts_source_tree():
    files = release_files(ROOT)
    assert files and not any(p.suffix in {".csv", ".jsonl"} for p in files)


@pytest.mark.parametrize("name", ["dataset.jsonl", "results.csv", "hf_token.md"])
def test_release_guard_rejects_data(tmp_path, name):
    (tmp_path / name).write_text("fixture, not a real credential")
    with pytest.raises(ValueError):
        release_files(tmp_path)


def test_skill_installs_and_runs_without_repository(tmp_path):
    target = install(tmp_path / "skills")
    assert (target / "SKILL.md").is_file()
    result = subprocess.run(
        [
            sys.executable,
            str(target / "runtime/scripts/smoke.py"),
            "--language",
            "python",
            "--output",
            str(tmp_path / "smoke"),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    with pytest.raises(FileExistsError):
        install(tmp_path / "skills")


def test_cli_invalid_adapter_is_nonzero(tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "witnessgym", "check-adapter", str(tmp_path / "missing.json")],
        capture_output=True,
        text=True,
        env={**__import__("os").environ, "PYTHONPATH": str(ROOT / "src")},
    )
    assert result.returncode == 2
