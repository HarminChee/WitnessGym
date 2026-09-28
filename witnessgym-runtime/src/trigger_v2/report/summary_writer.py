from __future__ import annotations

from pathlib import Path

from src.trigger_v2.report.artifact_writer import write_json


def write_case_result(out_dir: Path, payload: dict) -> None:
    write_json(out_dir / "case_result.json", payload)


def write_decision(out_dir: Path, payload: dict) -> None:
    write_json(out_dir / "decision.json", payload)


def write_batch_summary(out_path: Path, payload: dict) -> None:
    write_json(out_path, payload)