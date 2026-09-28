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


def load_rows_and_key(path: Path) -> tuple[list[dict], str, bool]:
    raw = path.read_text(encoding="utf-8")
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in raw.splitlines() if line.strip()], "", True
    payload = json.loads(raw)
    if isinstance(payload, list):
        return payload, "", False
    if isinstance(payload.get("traces"), list):
        return payload["traces"], "traces", False
    if isinstance(payload.get("rows"), list):
        return payload["rows"], "rows", False
    return [], "rows", False


def count_prod_functions(methods: list[dict]) -> int:
    seen: set[tuple[str, str]] = set()
    for m in methods:
        if str(m.get("kind", "")).lower() != "prod":
            continue
        seen.add((str(m.get("path", "")), str(m.get("name", ""))))
    return len(seen)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="JSON or JSONL execution-context file")
    ap.add_argument("--output", default="", help="Write updated records here; default prints to stdout")
    args = ap.parse_args()

    input_path = Path(args.input)
    rows, collection_key, is_jsonl = load_rows_and_key(input_path)

    out_rows = []
    for row in rows:
        count = row.get("distinct_prod_function_count")
        if count is None:
            count = count_prod_functions(list(row.get("methods", [])))
        row["distinct_prod_function_count"] = int(count)
        row["trace_bucket"] = bucket_of(int(count))
        out_rows.append(row)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if is_jsonl:
            output_path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in out_rows), encoding="utf-8")
        elif collection_key:
            output_path.write_text(json.dumps({collection_key: out_rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        else:
            output_path.write_text(json.dumps(out_rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    else:
        if is_jsonl:
            print("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in out_rows), end="")
        elif collection_key:
            print(json.dumps({collection_key: out_rows}, ensure_ascii=False, indent=2))
        else:
            print(json.dumps(out_rows, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
