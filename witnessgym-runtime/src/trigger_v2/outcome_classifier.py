from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


@dataclass
class OutcomeResult:
    failure_type: str


def _read_text(path: Path | str) -> str:
    p = Path(path)
    if not p.exists():
        return ""
    try:
        return p.read_text()
    except Exception:
        return ""


def classify_outcome(
    *,
    verify_rc: int,
    verify_stdout_path: Path | str,
    verify_stderr_path: Path | str,
) -> OutcomeResult:
    stdout = _read_text(verify_stdout_path)
    stderr = _read_text(verify_stderr_path)
    text = stdout + "\n" + stderr

    if verify_rc == 124:
        return OutcomeResult(failure_type="TIMEOUT")
    if verify_rc < 0 or verify_rc in (126, 127):
        return OutcomeResult(failure_type="HARNESS_FAIL")
    if "No tests were executed" in text or "No tests to run" in text:
        return OutcomeResult(failure_type="NO_TESTS")
    if verify_rc == 0:
        return OutcomeResult(failure_type="PASS")

    compile_markers = [
        "COMPILATION ERROR",
        "Compilation failure",
        "Failed to execute goal org.apache.maven.plugins:maven-compiler-plugin",
        "cannot find symbol",
        "package org.",
        "class, interface, enum, or record expected",
    ]
    if any(x in text for x in compile_markers):
        return OutcomeResult(failure_type="COMPILE_ERROR")

    test_failure_markers = [
        "AssertionFailedError",
        "org.opentest4j.AssertionFailedError",
        "There are test failures.",
        "Failed tests:",
        "<<< FAILURE!",
    ]
    if any(x in text for x in test_failure_markers) or re.search(r'Failures:\s*[1-9][0-9]*\b', text):
        return OutcomeResult(failure_type="TEST_FAILURE")

    if "No tests were executed" in text or "No tests to run" in text:
        return OutcomeResult(failure_type="NO_TESTS")

    if "BUILD FAILURE" in text or "Failed to execute goal" in text:
        return OutcomeResult(failure_type="HARNESS_FAIL")

    return OutcomeResult(failure_type="OTHER_FAIL")
