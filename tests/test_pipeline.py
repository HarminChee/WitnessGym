import json
import shutil
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from witnessgym.config import Adapter, load_spec
from witnessgym.errors import WitnessGymError
from witnessgym.files import snapshot
from witnessgym.pipeline import construct, evaluate
from witnessgym.process import execute

ROOT = Path(__file__).resolve().parents[1]


def fixture_agent():
    return ((sys.executable, str(ROOT / "examples/agents/fixture_agent.py"), "{request}"), ())


@pytest.mark.parametrize("language", ["python", "javascript", "java"])
def test_construction_transformation_and_differential_evaluation(language, tmp_path):
    if language == "javascript" and not shutil.which("node"):
        pytest.skip("Node.js is not installed")
    if language == "java" and not (shutil.which("java") and shutil.which("javac")):
        pytest.skip("JDK is not installed")
    clean = ROOT / "examples" / language
    adapter = Adapter.load(ROOT / f"examples/adapters/{language}.json")
    before = snapshot(clean, adapter.ignore_dirs)
    constructed = tmp_path / "construction"
    result = construct(
        clean_repo=clean,
        output=constructed,
        adapter=adapter,
        bug=load_spec(ROOT / "examples/specs/clamp-bug.json", kind="bug"),
        transformations=[
            load_spec(ROOT / "examples/specs/helper-transform.json", kind="transform")
        ],
        agent=fixture_agent(),
        allow_local_execution=True,
    )
    assert result["accepted"]
    assert result["applied_transformations"] == ["fixture-helper-extraction"]
    for context in (None, {"functions": ["clamp"]}):
        name = "with" if context else "without"
        run = evaluate(
            clean_repo=constructed / "clean",
            buggy_repo=constructed / "buggy",
            output=tmp_path / name,
            adapter=adapter,
            report="clamp incorrectly handles a positive number.",
            agent=fixture_agent(),
            execution_context=context,
            allow_local_execution=True,
        )
        assert run["accepted"]
        assert run["checks"]["clean"]["returncode"] == 0
        assert run["checks"]["buggy"]["returncode"] == 1
        request = json.loads((tmp_path / name / "request.json").read_text())
        assert "failure_regex" not in request
        assert ("execution_context" in request) == (context is not None)
    assert before == snapshot(clean, adapter.ignore_dirs)


def test_execution_is_opt_in(tmp_path):
    with pytest.raises(WitnessGymError, match="Execution requires"):
        construct(
            clean_repo=ROOT / "examples/python",
            output=tmp_path / "out",
            adapter=Adapter.load(ROOT / "examples/adapters/python.json"),
            bug={},
            transformations=[],
            agent=fixture_agent(),
        )
    assert not (tmp_path / "out").exists()


def test_existing_run_preserved(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "keep").write_text("important")
    with pytest.raises(WitnessGymError, match="already exists"):
        construct(
            clean_repo=ROOT / "examples/python",
            output=out,
            adapter=Adapter.load(ROOT / "examples/adapters/python.json"),
            bug={},
            transformations=[],
            agent=fixture_agent(),
            allow_local_execution=True,
        )
    assert (out / "keep").read_text() == "important"


def test_construction_no_changes_rejected(tmp_path):
    with pytest.raises(WitnessGymError, match="No injection passed"):
        construct(
            clean_repo=ROOT / "examples/python",
            output=tmp_path / "out",
            adapter=Adapter.load(ROOT / "examples/adapters/python.json"),
            bug={"id": "noop", "instruction": "noop"},
            transformations=[],
            agent=((sys.executable, "-c", "pass"), ()),
            attempts=1,
            allow_local_execution=True,
        )


def test_compile_error_cannot_be_success(tmp_path):
    adapter = replace(
        Adapter.load(ROOT / "examples/adapters/python.json"),
        build=(sys.executable, "-c", "raise SystemExit(1)"),
    )
    with pytest.raises(WitnessGymError, match="Clean baseline"):
        construct(
            clean_repo=ROOT / "examples/python",
            output=tmp_path / "out",
            adapter=adapter,
            bug={"id": "bad", "instruction": "bad"},
            transformations=[],
            agent=fixture_agent(),
            allow_local_execution=True,
        )


def prepare_pair(tmp_path):
    clean = tmp_path / "clean"
    buggy = tmp_path / "buggy"
    shutil.copytree(ROOT / "examples/python", clean)
    shutil.copytree(clean, buggy)
    source = buggy / "src/logic.py"
    source.write_text(source.read_text().replace("max(", "min("))
    return clean, buggy


def test_always_failing_test_rejected_on_clean(tmp_path):
    clean, buggy = prepare_pair(tmp_path)
    program = "from pathlib import Path; Path('tests/witness.py').write_text(\"raise AssertionError('WITNESS_TARGET: fake')\\n\")"
    run = evaluate(
        clean_repo=clean,
        buggy_repo=buggy,
        output=tmp_path / "out",
        adapter=Adapter.load(ROOT / "examples/adapters/python.json"),
        report="clamp",
        agent=((sys.executable, "-c", program), ()),
        allow_local_execution=True,
    )
    assert not run["accepted"]
    assert not run["checks"]["clean"]["accepted"]


def test_production_tampering_rejected(tmp_path):
    clean, buggy = prepare_pair(tmp_path)
    program = "from pathlib import Path; Path('src/logic.py').write_text('tampered')"
    run = evaluate(
        clean_repo=clean,
        buggy_repo=buggy,
        output=tmp_path / "out",
        adapter=Adapter.load(ROOT / "examples/adapters/python.json"),
        report="clamp",
        agent=((sys.executable, "-c", program), ()),
        allow_local_execution=True,
    )
    assert not run["accepted"]
    assert "Forbidden file changes" in run["reason"]


def test_secret_not_inherited(tmp_path, monkeypatch):
    monkeypatch.setenv("WITNESSGYM_TEST_CREDENTIAL", "example-not-secret")
    result = execute(
        [sys.executable, "-c", "import os; print('WITNESSGYM_TEST_CREDENTIAL' in os.environ)"],
        cwd=tmp_path,
        log_dir=tmp_path / "logs",
        timeout=3,
    )
    assert result.stdout.strip() == "False"


def test_timeout_not_accepted(tmp_path):
    result = execute(
        [sys.executable, "-c", "import time; time.sleep(5)"],
        cwd=tmp_path,
        log_dir=tmp_path / "logs",
        timeout=0.1,
    )
    assert result.status == "timeout"
    assert result.returncode != 0


def test_output_limit(tmp_path):
    result = execute(
        [sys.executable, "-c", "print('x'*20000)"],
        cwd=tmp_path,
        log_dir=tmp_path / "logs",
        timeout=3,
        max_output_bytes=1024,
    )
    assert result.status == "output_limit"
    assert len(result.stdout) == 1024


def test_symlinks_rejected(tmp_path):
    (tmp_path / "link").symlink_to(ROOT / "README.md")
    with pytest.raises(WitnessGymError, match="Symlink"):
        snapshot(tmp_path)


@pytest.mark.skipif(__import__("os").name != "posix", reason="POSIX process groups")
@pytest.mark.parametrize("returncode", [0, None])
def test_group_cleanup_exit_race(monkeypatch, returncode):
    from types import SimpleNamespace

    from witnessgym import process

    child = SimpleNamespace(pid=12345, poll=lambda: returncode, wait=lambda: returncode)

    def denied(*args):
        raise PermissionError("fixture signal race")

    monkeypatch.setattr(process.os, "killpg", denied)
    if returncode is None:
        with pytest.raises(WitnessGymError, match="terminate"):
            process._stop(child)
    else:
        assert process._stop(child) is False
