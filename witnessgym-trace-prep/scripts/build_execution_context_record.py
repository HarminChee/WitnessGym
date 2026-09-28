#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def bucket_of(n: int) -> str:
    if 1 <= n <= 40:
        return "short"
    if 41 <= n <= 70:
        return "mid-short"
    if 71 <= n <= 120:
        return "mid-long"
    if 121 <= n <= 150:
        return "long"
    raise ValueError(f"distinct_prod_function_count {n} is outside the paper-aligned range [1,150]")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-name", required=True)
    ap.add_argument("--trace-id", required=True)
    ap.add_argument("--test-name", required=True)
    ap.add_argument("--official-test-path", required=True)
    ap.add_argument("--official-test-class", required=True)
    ap.add_argument("--replay-cmd", required=True, help="JSON array string")
    ap.add_argument("--methods-json", required=True, help="Path to JSON array of method entries")
    ap.add_argument("--trace-summary", default="")
    ap.add_argument("--anchors-json", default="", help="Path to JSON array of anchor records")
    ap.add_argument("--bug-related-files-json", default="", help="Path to JSON array of repo-relative paths")
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    methods = json.loads(Path(args.methods_json).read_text(encoding="utf-8"))
    anchors = json.loads(Path(args.anchors_json).read_text(encoding="utf-8")) if args.anchors_json else []
    bug_related_files = json.loads(Path(args.bug_related_files_json).read_text(encoding="utf-8")) if args.bug_related_files_json else []
    replay_cmd = json.loads(args.replay_cmd)

    seen = {
        (str(m.get("path", "")), str(m.get("name", "")))
        for m in methods
        if str(m.get("kind", "")).lower() == "prod"
    }
    distinct_prod_function_count = len(seen)
    record = {
        "id": args.trace_id,
        "repo_name": args.repo_name,
        "repo": args.repo_name,
        "trace_id": args.trace_id,
        "test_name": args.test_name,
        "official_test_path": args.official_test_path,
        "official_test_class": args.official_test_class,
        "replay_cmd": replay_cmd,
        "cmd": replay_cmd,
        "methods": methods,
        "distinct_prod_function_count": distinct_prod_function_count,
        "trace_bucket": bucket_of(distinct_prod_function_count),
        "trace_summary": args.trace_summary,
        "anchors": anchors,
        "bug_related_files": bug_related_files,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
