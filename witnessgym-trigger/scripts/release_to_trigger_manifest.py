#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


PATTERN_CATEGORIES = {
    "codeql_java_comparison-of-identical-expressions": "API Contract",
    "codeql_java_equals-typo": "API Contract",
    "codeql_java_hashcode-typo": "API Contract",
    "codeql_java_hashing-without-hashcode": "API Contract",
    "codeql_java_inconsistent-equals-and-hashcode": "API Contract",
    "npe_intra_method_guard_removed": "Value Flow",
    "npe_collection_element_lazily_nullified": "Value Flow",
    "logic_predicate_inversion_in_guard": "Logic",
    "logic_aggregation_counter_skipped_on_branch": "Logic",
    "logic_deep_branch_collection_misroute": "Logic",
}


PATTERN_SUMMARIES = {
    "codeql_java_comparison-of-identical-expressions": "A condition compares a value with itself, producing a constant result that disables intended validation or equality logic.",
    "codeql_java_equals-typo": "An equals-like method has the wrong name or signature, so Java keeps using reference equality.",
    "codeql_java_hashcode-typo": "A hashCode-like method has the wrong name or signature, so hashed collections use identity hashing.",
    "codeql_java_hashing-without-hashcode": "A class overrides equals without a compatible hashCode, breaking hash-based lookup.",
    "codeql_java_inconsistent-equals-and-hashcode": "equals and hashCode use inconsistent state, breaking lookup in hash-based collections.",
    "npe_intra_method_guard_removed": "A value that was checked for null is later overwritten, moved outside the guard, or dereferenced on an unguarded path.",
    "npe_collection_element_lazily_nullified": "A collection maintenance path leaves a null element that a later lookup or iteration assumes is non-null.",
    "logic_predicate_inversion_in_guard": "A guard predicate is inverted or weakened, sending inputs through the wrong semantic path.",
    "logic_aggregation_counter_skipped_on_branch": "A branch processes an item but skips the corresponding counter or aggregate update.",
    "logic_deep_branch_collection_misroute": "A loop writes to a legal but wrong index or key, leaving a collection complete but logically misordered.",
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_context_index(path: Path) -> dict[str, dict]:
    if not path:
        return {}
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".jsonl":
        rows = [json.loads(line) for line in text.splitlines() if line.strip()]
    else:
        payload = json.loads(text)
        rows = payload if isinstance(payload, list) else payload.get("traces") or payload.get("rows") or []
    out = {}
    for row in rows:
        trace_id = str(row.get("trace_id") or row.get("id") or row.get("test_name") or "")
        if trace_id:
            out[trace_id] = row
    return out


def context_summary(case_dir: Path, case: dict, context_index: dict[str, dict]) -> str:
    embedded = case.get("execution_context_summary")
    if isinstance(embedded, str) and embedded.strip():
        return embedded.strip()

    sidecar_name = str(case.get("execution_context_file") or "execution_context.json")
    sidecar = case_dir / sidecar_name
    if sidecar.exists():
        payload = load_json(sidecar)
        summary = payload.get("trace_summary")
        if isinstance(summary, str) and summary.strip():
            return summary.strip()
        methods = payload.get("methods") or []
        anchors = payload.get("anchors") or []
        return json.dumps(
            {
                "trace_id": payload.get("trace_id") or case.get("trace_id"),
                "trace_bucket": payload.get("trace_bucket") or case.get("trace_bucket"),
                "methods": methods[:80],
                "anchors": anchors[:20],
            },
            indent=2,
            ensure_ascii=False,
        )

    row = context_index.get(str(case.get("trace_id") or ""))
    if row:
        summary = row.get("trace_summary")
        if isinstance(summary, str) and summary.strip():
            return summary.strip()
        return json.dumps(
            {
                "trace_id": row.get("trace_id") or row.get("id"),
                "trace_bucket": row.get("trace_bucket") or row.get("bucket"),
                "methods": (row.get("methods") or [])[:80],
                "anchors": (row.get("anchors") or [])[:20],
            },
            indent=2,
            ensure_ascii=False,
        )
    return ""


def iter_case_dirs(release_root: Path):
    cases_root = release_root / "cases"
    root = cases_root if cases_root.is_dir() else release_root
    for case_json in sorted(root.glob("*/case.json")):
        yield case_json.parent


def normalize_command(value) -> list[str]:
    if isinstance(value, list):
        return [str(x) for x in value]
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, list):
                return [str(x) for x in parsed]
        except json.JSONDecodeError:
            pass
        return stripped.split()
    return []


def main() -> None:
    ap = argparse.ArgumentParser(description="Convert an anonymous review release into trigger-evaluation JSONL.")
    ap.add_argument("--release-root", required=True)
    ap.add_argument("--output-jsonl", required=True)
    ap.add_argument("--repo-template-root", required=True)
    ap.add_argument("--execution-contexts", default="", help="Optional JSON/JSONL trace bundle for WithEC summaries")
    ap.add_argument("--default-inject-verify-rc", type=int, default=1)
    args = ap.parse_args()

    release_root = Path(args.release_root).resolve()
    repo_template_root = Path(args.repo_template_root).resolve()
    context_index = load_context_index(Path(args.execution_contexts).resolve()) if args.execution_contexts else {}
    rows = []
    missing_context = []

    for case_dir in iter_case_dirs(release_root):
        case = load_json(case_dir / "case.json")
        pattern_id = str(case["pattern_id"])
        repo_id = str(case.get("repo_id") or case.get("repo_name") or case.get("repo") or "")
        if not repo_id:
            raise SystemExit(f"Missing repo_id/repo_name in {case_dir / 'case.json'}")
        summary = context_summary(case_dir, case, context_index)
        if not summary:
            missing_context.append(str(case.get("case_id") or case_dir.name))
        verify_cmd = normalize_command(case.get("verify_cmd") or case.get("replay_cmd") or case.get("cmd"))
        rows.append(
            {
                "repo_name": repo_id,
                "repo_template": str(repo_template_root / repo_id),
                "run_id": str(case.get("case_id") or case_dir.name),
                "trace_id": str(case.get("trace_id") or ""),
                "pattern_id": pattern_id,
                "pattern_category": str(case.get("pattern_category") or PATTERN_CATEGORIES.get(pattern_id, "")),
                "transform_ids": list(case.get("transform_ids") or []),
                "official_test_path": str(case.get("official_test_path") or ""),
                "official_test_class": str(case.get("official_test_class") or ""),
                "bug_related_files": list(case.get("bug_related_files") or []),
                "inject_verify_rc": int(case.get("expected_verify_rc") or case.get("inject_verify_rc") or args.default_inject_verify_rc),
                "verify_cmd": verify_cmd,
                "buggy_repo": str(case_dir / "buggy_repo"),
                "pattern_summary": str(case.get("pattern_summary") or PATTERN_SUMMARIES.get(pattern_id, "")),
                "execution_context_summary": summary,
                "spotless_modules": [case["module_root"]] if case.get("module_root") else [],
            }
        )

    output = Path(args.output_jsonl)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    report = {
        "ok": True,
        "rows": len(rows),
        "output_jsonl": str(output),
        "missing_execution_context_summary_count": len(missing_context),
        "missing_execution_context_summary_cases": missing_context[:50],
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
