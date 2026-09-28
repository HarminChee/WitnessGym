#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

REQUIRED_FIELDS = {
    "repo_name",
    "trace_id",
    "official_test_path",
    "official_test_class",
    "replay_cmd",
    "methods",
    "distinct_prod_function_count",
    "trace_bucket",
}
ALLOWED_BUCKETS = {"short", "mid-short", "mid-long", "long", "midshort", "midlong"}


def load_rows(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    payload = json.loads(text)
    if isinstance(payload, list):
        return payload
    for key in ("traces", "rows"):
        rows = payload.get(key)
        if isinstance(rows, list):
            return rows
    return []


def contains_absolute_path(value) -> bool:
    if isinstance(value, str):
        return value.startswith("/") or (len(value) > 2 and value[1:3] == ":\\")
    if isinstance(value, list):
        return any(contains_absolute_path(v) for v in value)
    if isinstance(value, dict):
        return any(contains_absolute_path(v) for v in value.values())
    return False


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="JSON or JSONL trace asset bundle")
    args = ap.parse_args()

    path = Path(args.input)
    rows = load_rows(path)

    errors = []
    if not rows:
        errors.append({"row": 0, "issue": "no_trace_rows"})
    for idx, row in enumerate(rows, start=1):
        missing = sorted(REQUIRED_FIELDS - set(row))
        if missing:
            errors.append({"row": idx, "trace_id": row.get("trace_id"), "missing": missing})
        bucket = str(row.get("trace_bucket") or row.get("bucket") or "")
        if bucket not in ALLOWED_BUCKETS:
            errors.append({"row": idx, "trace_id": row.get("trace_id"), "issue": "invalid_trace_bucket", "value": bucket})
        if contains_absolute_path(row):
            errors.append({"row": idx, "trace_id": row.get("trace_id"), "issue": "absolute_local_path_detected"})

    payload = {"rows": len(rows), "errors": errors, "ok": not errors}
    print(json.dumps(payload, indent=2))
    if errors:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
