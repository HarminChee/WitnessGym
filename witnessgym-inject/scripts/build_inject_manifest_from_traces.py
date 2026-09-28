#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_rows(path: Path, collection_key: str) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    payload = json.loads(text)
    if isinstance(payload, list):
        return payload
    rows = payload.get(collection_key)
    if isinstance(rows, list):
        return rows
    rows = payload.get("rows")
    if isinstance(rows, list):
        return rows
    raise SystemExit(f"Could not find rows in {path}")


def trace_id(row: dict) -> str:
    return str(row.get("trace_id") or row.get("id") or row.get("test_name") or "").strip()


def trace_bucket(row: dict) -> str:
    value = str(row.get("trace_bucket") or row.get("bucket") or "").strip()
    aliases = {"midshort": "mid-short", "midlong": "mid-long"}
    return aliases.get(value, value)


def repo_name(row: dict, default_repo: str) -> str:
    return str(row.get("repo_name") or row.get("repo") or default_repo).strip()


def command_ids(commands: list[dict]) -> set[str]:
    ids = set()
    for row in commands:
        cid = str(row.get("id") or row.get("trace_id") or row.get("test_name") or "").strip()
        if cid:
            ids.add(cid)
    return ids


def main() -> None:
    ap = argparse.ArgumentParser(description="Build a paper-aligned inject manifest from trace and command assets.")
    ap.add_argument("--traces", required=True)
    ap.add_argument("--commands", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--repo-template-root", default="")
    ap.add_argument("--default-repo-name", default="")
    ap.add_argument("--pattern-ids", nargs="+", required=True)
    ap.add_argument("--transform-ids", nargs="*", default=[])
    ap.add_argument("--trace-buckets", nargs="*", default=[])
    ap.add_argument("--max-rows", type=int, default=0)
    args = ap.parse_args()

    traces_path = Path(args.traces).resolve()
    commands_path = Path(args.commands).resolve()
    traces = load_rows(traces_path, "traces")
    commands = load_rows(commands_path, "commands")
    valid_command_ids = command_ids(commands)
    requested_buckets = {b.strip() for b in args.trace_buckets if b.strip()}

    out_rows: list[dict] = []
    for tr in traces:
        tid = trace_id(tr)
        if not tid:
            continue
        if valid_command_ids and tid not in valid_command_ids:
            continue
        bucket = trace_bucket(tr)
        if requested_buckets and bucket not in requested_buckets:
            continue
        repo = repo_name(tr, args.default_repo_name)
        if not repo:
            raise SystemExit(f"Trace {tid} does not include repo_name/repo and --default-repo-name was not provided")
        repo_template = ""
        if args.repo_template_root:
            repo_template = str((Path(args.repo_template_root) / repo).resolve())
        for pattern_id in args.pattern_ids:
            out_rows.append(
                {
                    "repo_name": repo,
                    "repo_template": repo_template,
                    "trace_id": tid,
                    "pattern_id": pattern_id,
                    "transform_ids": list(args.transform_ids),
                    "traces_path": str(traces_path),
                    "commands_path": str(commands_path),
                    "trace_bucket": bucket,
                    "notes": "",
                }
            )
            if args.max_rows and len(out_rows) >= args.max_rows:
                break
        if args.max_rows and len(out_rows) >= args.max_rows:
            break

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in out_rows), encoding="utf-8")
    print(json.dumps({"ok": True, "rows": len(out_rows), "output": str(output)}, indent=2))


if __name__ == "__main__":
    main()
