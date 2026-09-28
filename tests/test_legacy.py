import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "witnessgym-runtime"))
from src.trigger_v2.outcome_classifier import classify_outcome
from src.trigger_v2.repo_audit import audit_repo_changes, capture_repo_diff_baseline
from src.trigger_v2.test_discovery import discover_generated_tests
from src.trigger_v2.workspace import prepare_case_workspace, restore_official_test


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    (root / "module/src/main/java").mkdir(parents=True)
    (root / "module/src/test/java").mkdir(parents=True)
    (root / "module/src/main/java/Logic.java").write_text("clean\n")
    (root / "module/src/test/java/LogicTest.java").write_text("test\n")

    def git(*args):
        subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)

    git("init")
    git("config", "user.name", "Fixture")
    git("config", "user.email", "fixture@example.invalid")
    git("add", ".")
    git("commit", "-m", "fixture")
    return root


def audit(repo, before):
    return audit_repo_changes(
        workspace_repo=repo,
        allowed_test_roots=["src/test/java"],
        protected_prod_roots=["src/main/java"],
        baseline_modified_files=before,
    )


def test_legacy_audit_already_modified_file(repo):
    file = repo / "module/src/main/java/Logic.java"
    file.write_text("injected\n")
    before = capture_repo_diff_baseline(workspace_repo=repo)
    file.write_text("tampered\n")
    assert audit(repo, before).modified_production_files == ["module/src/main/java/Logic.java"]


def test_legacy_audit_staged_and_untracked(repo):
    before = capture_repo_diff_baseline(workspace_repo=repo)
    (repo / "module/src/main/java/Logic.java").write_text("tampered\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    (repo / "credentials.env").write_text("not-a-secret fixture\n")
    result = audit(repo, before)
    assert result.modified_production_files
    assert "credentials.env" in result.forbidden_non_test_changes


def test_legacy_new_test_discovery(repo, tmp_path):
    path = repo / "module/src/test/java/NewTest.java"
    path.write_text("new witness\n")
    result = discover_generated_tests(
        workspace_repo=repo, official_test_path="", out_dir=tmp_path / "tests"
    )
    assert result.generated_test_files == ["module/src/test/java/NewTest.java"]


@pytest.mark.parametrize(
    ("rc", "text", "expected"),
    [
        (124, "Tests run: 1, Failures: 1", "TIMEOUT"),
        (1, "Tests run: 0, Failures: 0\nNo tests were executed", "NO_TESTS"),
        (1, "Tests run: 3, Failures: 0\nBUILD FAILURE\nnetwork unavailable", "HARNESS_FAIL"),
        (1, "Tests run: 3, Failures: 1, Errors: 0\nThere are test failures.", "TEST_FAILURE"),
    ],
)
def test_legacy_outcomes(tmp_path, rc, text, expected):
    out = tmp_path / "stdout"
    err = tmp_path / "stderr"
    out.write_text(text)
    err.write_text("")
    assert (
        classify_outcome(verify_rc=rc, verify_stdout_path=out, verify_stderr_path=err).failure_type
        == expected
    )


def test_legacy_run_collision_is_not_deleted(repo, tmp_path):
    root = tmp_path / "runs"
    workspace = prepare_case_workspace(
        repo_template=repo, out_root=root, run_id="case", group="NoEC"
    )
    marker = workspace.case_dir / "keep"
    marker.write_text("user work")
    with pytest.raises((ValueError, FileExistsError)):
        prepare_case_workspace(repo_template=repo, out_root=root, run_id="case", group="NoEC")
    assert marker.read_text() == "user work"


def test_legacy_path_traversal(repo, tmp_path):
    with pytest.raises(ValueError):
        prepare_case_workspace(
            repo_template=repo, out_root=tmp_path / "runs", run_id="../../escape", group="A"
        )


def test_legacy_test_path_traversal(repo, tmp_path):
    with pytest.raises(ValueError):
        restore_official_test(
            repo_template=repo, workspace_repo=repo, official_test_path="../outside"
        )


def test_legacy_spec_catalogues_load_with_index_files():
    from src.patterns.registry import PatternRegistry
    from src.transform.registry import TransformRegistry

    patterns = PatternRegistry.load(ROOT / "witnessgym-inject/specs/patterns")
    transforms = TransformRegistry.load(ROOT / "witnessgym-inject/specs/transforms")
    assert len(patterns.list_ids()) == 10
    assert len(transforms.list_ids()) == 10


def test_legacy_checked_command_raises(tmp_path):
    from src.common.errors import WitnessGymError
    from src.common.proc import run_checked

    with pytest.raises(WitnessGymError):
        run_checked([sys.executable, "-c", "raise SystemExit(3)"], cwd=tmp_path)


def test_legacy_injection_does_not_erase_dirty_input(repo):
    from types import SimpleNamespace

    from src.common.errors import OrchestratorError
    from src.pipeline.orchestrator import run_injection

    modified = repo / "module/src/main/java/Logic.java"
    modified.write_text("user work")
    with pytest.raises(OrchestratorError, match="uncommitted"):
        run_injection(SimpleNamespace(repo_root=repo))
    assert modified.read_text() == "user work"


def test_legacy_maven_missing_executable_is_harness_failure(tmp_path):
    from src.trigger_v2.verify.maven_runner import run_maven_verify

    result = run_maven_verify(
        workspace_repo=tmp_path,
        verify_cmd=["/nonexistent/witnessgym-test-executable"],
        timeout_s=1,
        out_dir=tmp_path / "logs",
    )
    assert result.verify_rc == 127


def test_legacy_packaging_preserves_existing_directory(tmp_path):
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "package_case", ROOT / "witnessgym-full-workflow/scripts/package_review_case.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = tmp_path / "source"
    source.mkdir()
    dest = tmp_path / "destination"
    dest.mkdir()
    marker = dest / "keep"
    marker.write_text("user content")
    with pytest.raises(FileExistsError):
        module.copy_buggy_repo(source, dest)
    assert marker.read_text() == "user content"
