from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .types import GeneratedTestsResult
from .repo_audit import _git_diff_name_only

_ALLOWED_TEST_SUFFIXES = (
    "Test.java",
    "Tests.java",
    "IT.java",
)


def _is_test_java_file(path: str) -> bool:
    normalized = path.lstrip("./")
    if "src/test/java/" not in normalized and "src/testFixtures/java/" not in normalized:
        return False
    return normalized.endswith(_ALLOWED_TEST_SUFFIXES)


def discover_generated_tests(
    *,
    workspace_repo: Path,
    official_test_path: str,
    out_dir: Path,
) -> GeneratedTestsResult:
    out_dir.mkdir(parents=True, exist_ok=True)

    modified_files = _git_diff_name_only(workspace_repo)

    candidates = []
    for rel_path in modified_files:
        normalized = rel_path.lstrip("./")
        abs_path = workspace_repo / normalized
        if abs_path.is_symlink() or not abs_path.resolve().is_relative_to(workspace_repo.resolve()):
            raise ValueError('Test path escapes the evaluation workspace')
        if _is_test_java_file(normalized) and abs_path.exists() and abs_path.is_file():
            candidates.append(normalized)

    generated_test_files = sorted(set(candidates))

    applied_dir = out_dir / "applied_files"
    applied_dir.mkdir(parents=True, exist_ok=True)

    for rel_path in generated_test_files:
        src = workspace_repo / rel_path
        dst = applied_dir / rel_path
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    return GeneratedTestsResult(
        generated_test_files=generated_test_files,
    )
