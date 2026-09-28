#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-root", required=True)
    ap.add_argument("--run-name", default="")
    args = ap.parse_args()

    out_root = Path(args.out_root).resolve()
    run_name = args.run_name or f"managed_run_{utc_stamp()}"
    run_root = out_root / run_name
    for rel in [
        "intake",
        "execution_contexts",
        "manifests",
        "inject/results",
        "trigger/results",
        "release",
        "logs",
    ]:
        (run_root / rel).mkdir(parents=True, exist_ok=True)

    intake = {
        "repo_names": [],
        "reuse_existing_execution_contexts": None,
        "requested_trace_ids": [],
        "requested_trace_buckets": [],
        "bug_pattern_ids": [],
        "transform_ids": [],
        "construction_agent_family": "claude-code",
        "construction_backend_mode": "bedrock",
        "construction_model_id": "",
        "evaluation_agent_family": "claude-code",
        "evaluation_backend_mode": "bedrock",
        "evaluation_model_id": "",
        "run_groups": ["A", "B"],
        "notes": "",
    }
    (run_root / "intake" / "intake.json").write_text(json.dumps(intake, indent=2) + "\n", encoding="utf-8")

    placeholders = {
        "execution_context_manifest_jsonl": "manifests/execution_contexts.jsonl",
        "inject_manifest_jsonl": "manifests/inject_manifest.jsonl",
        "trigger_manifest_jsonl": "manifests/trigger_manifest.jsonl",
        "review_release_dir": "release/review_release",
    }
    (run_root / "manifests" / "layout.json").write_text(json.dumps(placeholders, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({"run_root": str(run_root), "ok": True}, indent=2))


if __name__ == "__main__":
    main()
