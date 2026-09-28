import shutil
import subprocess
import sys
from dataclasses import fields
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "witnessgym-runtime"))
from src.trigger_v2 import runner
from src.trigger_v2.config import TriggerConfig
from src.trigger_v2.types import AgentRunResult, SpotlessResult, TriggerCaseContext


@pytest.mark.parametrize(
    ("fail_clean", "format_tamper", "expected"),
    [(False, False, True), (True, False, False), (False, True, False)],
)
def test_legacy_differential_verification(
    tmp_path, monkeypatch, fail_clean, format_tamper, expected
):
    clean = tmp_path / "clean"
    prod = "module/src/main/java/Logic.java"
    official = "module/src/test/java/OfficialTest.java"
    (clean / prod).parent.mkdir(parents=True)
    (clean / prod).write_text("clean")
    (clean / official).parent.mkdir(parents=True)
    (clean / official).write_text("hidden construction witness")
    for args in [
        ["init"],
        ["config", "user.name", "Fixture"],
        ["config", "user.email", "fixture@example.invalid"],
        ["add", "."],
        ["commit", "-m", "fixture"],
    ]:
        subprocess.run(["git", *args], cwd=clean, check=True, capture_output=True)
    buggy = tmp_path / "overlay"
    (buggy / prod).parent.mkdir(parents=True)
    (buggy / prod).write_text("buggy")
    system = tmp_path / "system.txt"
    system.write_text("Fixture")
    task = tmp_path / "task.txt"
    task.write_text("{pattern_summary}")
    config = TriggerConfig(
        clean,
        tmp_path / "runs",
        system,
        task,
        tmp_path / "unused-agent",
        "",
        3,
        3,
        3,
        [],
        ["src/test/java"],
        ["src/main/java"],
    )
    verify = [
        sys.executable,
        "-c",
        f"from pathlib import Path; bad={fail_clean!r} or Path({prod!r}).read_text() != 'clean'; "
        "print('Tests run: 1, Failures: 1' if bad else 'Tests run: 1, Failures: 0'); raise SystemExit(1 if bad else 0)",
    ]
    case = TriggerCaseContext(
        "fixture",
        "case",
        "NoEC",
        "",
        "fixture-bug",
        [],
        official,
        "OfficialTest",
        [prod],
        1,
        verify,
        str(buggy),
        "Fixture bug",
    )

    def agent(**kwargs):
        repo = kwargs["workspace_repo"]
        assert not (repo / official).exists()
        (repo / "module/src/test/java/GeneratedTest.java").write_text("new witness")
        out = kwargs["out_dir"]
        out.mkdir(exist_ok=True)
        values = {f.name: out / f.name for f in fields(AgentRunResult)}
        for p in values.values():
            p.write_text("")
        values.update(
            returncode=0, trigger_report={"materialized_test_files": ["GeneratedTest.java"]}
        )
        return AgentRunResult(**values)

    def format_code(**kwargs):
        if format_tamper:
            (kwargs["workspace_repo"] / prod).write_text("formatter tampered")
        log = kwargs["out_dir"] / "format.log"
        log.write_text("")
        return SpotlessResult(0, log, log, log)

    def overlay(**kwargs):
        shutil.copytree(kwargs["buggy_repo"], kwargs["workspace_repo"], dirs_exist_ok=True)
        return {"returncode": 0, "stderr": ""}

    monkeypatch.setattr(runner, "run_agent", agent)
    monkeypatch.setattr(runner, "run_spotless", format_code)
    monkeypatch.setattr(runner, "overlay_buggy_repo", overlay)
    result = runner.run_single_case(config=config, case_input=case)
    assert result["detect_success"] is expected
    assert result["clean_verify_rc"] == (1 if fail_clean else 0)
    if format_tamper:
        assert result["modified_production_files"] == [prod]
