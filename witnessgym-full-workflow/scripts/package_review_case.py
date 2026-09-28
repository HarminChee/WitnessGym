#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import re
import shlex
from pathlib import Path


BUILD_CACHE_NAMES = {
    ".git",
    ".gradle",
    ".idea",
    ".settings",
    "target",
    "build",
    "out",
    ".mvn/timing.properties",
}


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_rows(path: Path, key: str) -> list[dict]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    payload = json.loads(text)
    if isinstance(payload, list):
        return payload
    return payload.get(key) or payload.get("rows") or []


def find_row(rows: list[dict], trace_id: str) -> dict:
    for row in rows:
        rid = str(row.get("trace_id") or row.get("id") or row.get("test_name") or "")
        if rid == trace_id:
            return row
    return {}


def find_success(summary: dict) -> dict:
    idx = summary.get("successful_attempt_index")
    for attempt in summary.get("attempts", []):
        if attempt.get("ok") and (idx is None or int(attempt.get("attempt_index", -1)) == int(idx)):
            return attempt
    raise SystemExit("No successful attempt found in case summary")


def ignore_release_files(dir_path: str, names: list[str]) -> set[str]:
    ignored = set()
    for name in names:
        if name in {".git", ".gradle", ".idea", ".settings", "target", "build"}:
            ignored.add(name)
        if name.endswith(".class") or name == ".DS_Store":
            ignored.add(name)
    return ignored


def copy_buggy_repo(src: Path, dst: Path) -> None:
    if dst.exists():
        raise FileExistsError(f"Refusing to replace existing case: {dst}")
    if dst.resolve().is_relative_to(src.resolve()):
        raise ValueError("Output must not be inside the input repository")
    if any(p.is_symlink() for p in src.rglob("*")):
        raise ValueError("Case repositories containing symlinks require explicit review")
    shutil.copytree(src, dst, ignore=ignore_release_files)


def list_changed_prod_files(patch_text: str) -> list[str]:
    files = []
    for line in patch_text.splitlines():
        if not line.startswith("diff --git "):
            continue
        parts = line.split()
        if len(parts) >= 4:
            path = parts[2][2:] if parts[2].startswith("a/") else parts[2]
            if "/src/main/java/" in f"/{path}" and path not in files:
                files.append(path)
    return files


def main() -> None:
    ap = argparse.ArgumentParser(description="Package a successful inject wrapper result as an anonymous review case.")
    ap.add_argument("--case-summary", required=True, help="case_summary.json from run_paper_aligned_inject_case.py")
    ap.add_argument("--case-id", required=True)
    ap.add_argument("--output-root", required=True)
    ap.add_argument("--repo-id", default="")
    ap.add_argument("--module-root", default="")
    ap.add_argument("--pattern-category", default="")
    ap.add_argument("--expected-verify-rc", type=int, default=1)
    ap.add_argument("--oracle-type", default="failing_test")
    args = ap.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", args.case_id):
        raise SystemExit("case-id must be a single safe path component")

    case_summary_path = Path(args.case_summary).resolve()
    case_summary = load_json(case_summary_path)
    success = find_success(case_summary)
    run_dir = Path(str(success["run_dir"])).resolve()
    workspace = Path(str(success["workspace"])).resolve()
    inputs = load_json(run_dir / "inputs.json")
    trace_id = str(inputs.get("trace_id", case_summary.get("trace_id", "")))
    pattern_id = str(inputs.get("pattern_id", case_summary.get("pattern_id", "")))
    transform_ids = list(inputs.get("transform_ids") or case_summary.get("transform_ids") or [])
    traces_path = Path(str(inputs.get("traces_path", ""))).resolve()
    commands_path = Path(str(inputs.get("commands_path", ""))).resolve()
    trace_row = find_row(load_rows(traces_path, "traces"), trace_id)
    command_row = find_row(load_rows(commands_path, "commands"), trace_id)
    result = load_json(run_dir / "result.json") if (run_dir / "result.json").exists() else {}
    attempt_idx = int(success.get("attempt_index", result.get("attempt", 1)))
    patch_path = run_dir / f"attempt_{attempt_idx}.diff.patch"
    patch_text = patch_path.read_text(encoding="utf-8", errors="ignore") if patch_path.exists() else ""

    repo_id = args.repo_id or str(trace_row.get("repo_name") or trace_row.get("repo") or Path(str(case_summary.get("repo_template", ""))).name)
    verify_cmd = result.get("repro_cmd") or trace_row.get("replay_cmd") or command_row.get("cmd") or command_row.get("command")
    if isinstance(verify_cmd, str):
        verify_cmd = shlex.split(verify_cmd)
    if not isinstance(verify_cmd, list) or not verify_cmd or not all(isinstance(x, str) and x for x in verify_cmd):
        raise SystemExit("Could not determine verify command")
    if not patch_text.strip():
        raise SystemExit("Cannot release a case without its production patch")

    official_test_path = str(trace_row.get("official_test_path") or "")
    official_test_class = str(trace_row.get("official_test_class") or trace_row.get("test_name") or trace_id)
    bug_related_files = list(trace_row.get("bug_related_files") or [])
    if not bug_related_files:
        bug_related_files = list_changed_prod_files(patch_text)

    trace_bucket = str(trace_row.get("trace_bucket") or trace_row.get("bucket") or "")
    aliases = {"midshort": "mid-short", "midlong": "mid-long"}
    release_bucket = aliases.get(trace_bucket, trace_bucket)

    out_case = Path(args.output_root).resolve() / args.case_id
    if out_case.is_relative_to(workspace) or workspace.is_relative_to(out_case):
        raise SystemExit("Case output and input repository must not be nested")
    out_case.mkdir(parents=True, exist_ok=False)
    (out_case / "bug.patch").write_text(patch_text, encoding="utf-8")
    copy_buggy_repo(workspace, out_case / "buggy_repo")

    execution_context = {
        "trace_id": trace_id,
        "trace_bucket": trace_bucket,
        "trace_summary": trace_row.get("trace_summary", ""),
        "methods": trace_row.get("methods", []),
        "anchors": trace_row.get("anchors", []),
        "bug_related_files": bug_related_files,
    }
    (out_case / "execution_context.json").write_text(json.dumps(execution_context, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    case_json = {
        "case_id": args.case_id,
        "repo_id": repo_id,
        "dimension": "",
        "trace_bucket": release_bucket,
        "trace_id": trace_id,
        "official_test_path": official_test_path,
        "official_test_class": official_test_class,
        "verify_cmd": verify_cmd,
        "pattern_id": pattern_id,
        "pattern_category": args.pattern_category,
        "transform_depth": len(transform_ids),
        "transform_ids": transform_ids,
        "module_root": args.module_root,
        "bug_related_files": bug_related_files,
        "oracle_type": args.oracle_type,
        "expected_verify_rc": args.expected_verify_rc,
        "execution_context_file": "execution_context.json",
    }
    (out_case / "case.json").write_text(json.dumps(case_json, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "case_dir": str(out_case)}, indent=2))


if __name__ == "__main__":
    main()
