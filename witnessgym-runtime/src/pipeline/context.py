from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

@dataclass(frozen=True)
class TraceTarget:
    trace_id: str
    test_name: str | None
    methods: list[dict[str, Any]]
    raw: dict[str, Any]

@dataclass(frozen=True)
class InjectionRequest:
    repo_root: Path
    pattern_id: str
    transform_ids: list[str]
    traces_path: Path
    commands_path: Path
    trace_id: str
    run_root: Path
    runner_script: Path
    system_prompt_path: Path
    max_attempts: int = 1
    verify_timeout_s: int | None = None

    dataset_root: Path | None = None
    archive_dataset: bool = True
    auto_clean_after: bool = True

@dataclass(frozen=True)
class VerifyCommand:
    test_id: str
    cmd: list[str]
