#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
from pathlib import Path


METHOD_LINE_RE = re.compile(
    r"^(\s*)((public|protected|private)\s+)?"
    r"((static|final|synchronized|strictfp)\s+)*"
    r"[A-Za-z0-9_<>\[\], ?.@]+\s+"
    r"([A-Za-z_$][A-Za-z0-9_$]*)\s*\([^;{}]*\)\s*"
    r"(throws\s+[A-Za-z0-9_.,\s]+)?\{\s*$"
)
PACKAGE_RE = re.compile(r"(?m)^\s*package\s+([A-Za-z0-9_.]+)\s*;")


def bucket_of(n: int) -> str:
    if 1 <= n <= 40:
        return "short"
    if 41 <= n <= 70:
        return "mid-short"
    if 71 <= n <= 120:
        return "mid-long"
    if 121 <= n <= 150:
        return "long"
    raise ValueError(f"distinct production function count {n} is outside [1, 150]")


def parse_json_cmd(raw: str) -> list[str]:
    value = json.loads(raw)
    if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
        raise SystemExit("--replay-cmd must be a JSON array of strings")
    return value


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def package_name(java_file: Path) -> str:
    match = PACKAGE_RE.search(read_text(java_file))
    return match.group(1).strip() if match else ""


def find_test_file(repo: Path, official_test_path: str, official_test_class: str) -> Path:
    if official_test_path:
        candidate = repo / official_test_path
        if candidate.is_file():
            return candidate
        raise SystemExit(f"official test path not found: {official_test_path}")

    simple = official_test_class.rsplit(".", 1)[-1]
    matches = []
    for path in repo.rglob(f"{simple}.java"):
        rel = str(path.relative_to(repo)).replace("\\", "/")
        if "/src/test/java/" not in f"/{rel}":
            continue
        pkg = package_name(path)
        fqcn = f"{pkg}.{path.stem}" if pkg else path.stem
        if fqcn == official_test_class:
            matches.append(path)
    if len(matches) != 1:
        raise SystemExit(f"expected one test file for {official_test_class}, found {len(matches)}")
    return matches[0]


def nearest_pom(start: Path, stop: Path) -> Path | None:
    cur = start
    while True:
        candidate = cur / "pom.xml"
        if candidate.exists():
            return candidate
        if cur == stop or cur.parent == cur:
            return None
        cur = cur.parent


def module_rel_for_test(repo: Path, test_file: Path) -> str:
    pom = nearest_pom(test_file.parent, repo)
    if pom is None:
        return "."
    rel = pom.parent.relative_to(repo)
    return str(rel).replace("\\", "/") if str(rel) else "."


def default_replay_cmd(repo: Path, test_file: Path, official_test_class: str) -> list[str]:
    runner = "./mvnw" if (repo / "mvnw").exists() else "mvn"
    module_rel = module_rel_for_test(repo, test_file)
    if module_rel == ".":
        return [runner, "-q", f"-Dtest={official_test_class}", "test"]
    return [runner, "-q", "-pl", module_rel, f"-Dtest={official_test_class}", "test"]


def trace_logger_source() -> str:
    return """package witnessgym;

public final class TraceLogger {
  private static final Object LOCK = new Object();
  private static final java.nio.file.Path OUT = resolveOut();

  private TraceLogger() {}

  private static java.nio.file.Path resolveOut() {
    String value = System.getenv("WITNESSGYM_TRACE_OUT");
    if (value == null || value.isEmpty()) {
      value = System.getProperty("witnessgym.trace.out");
    }
    if (value == null || value.isEmpty()) {
      return null;
    }
    return java.nio.file.Paths.get(value);
  }

  public static void hit(String path, String name, int line) {
    if (OUT == null) {
      return;
    }
    synchronized (LOCK) {
      try {
        java.nio.file.Path parent = OUT.getParent();
        if (parent != null) {
          java.nio.file.Files.createDirectories(parent);
        }
        String row = path + "\\t" + name + "\\t" + line + "\\n";
        java.nio.file.Files.write(
            OUT,
            row.getBytes(java.nio.charset.StandardCharsets.UTF_8),
            java.nio.file.StandardOpenOption.CREATE,
            java.nio.file.StandardOpenOption.APPEND);
      } catch (Throwable ignored) {
      }
    }
  }
}
"""


def should_skip_line(stripped: str) -> bool:
    prefixes = ("if ", "for ", "while ", "switch ", "catch ", "try ", "else ", "do ")
    if stripped.startswith(prefixes):
        return True
    return any(token in stripped for token in (" class ", " interface ", " enum ", " record "))


def instrument_java_file(path: Path, repo: Path) -> int:
    rel = str(path.relative_to(repo)).replace("\\", "/")
    original = read_text(path).splitlines(keepends=True)
    out: list[str] = []
    inserted = 0
    for line_no, line in enumerate(original, start=1):
        out.append(line)
        stripped = line.strip()
        if not stripped.endswith("{") or should_skip_line(stripped):
            continue
        match = METHOD_LINE_RE.match(line.rstrip("\n\r"))
        if not match:
            continue
        method_name = match.group(6)
        indent = match.group(1) + "  "
        out.append(f'{indent}witnessgym.TraceLogger.hit("{rel}", "{method_name}", {line_no});\n')
        inserted += 1
    if inserted:
        path.write_text("".join(out), encoding="utf-8")
    return inserted


def add_trace_logger(module_root: Path) -> Path:
    helper = module_root / "src" / "main" / "java" / "witnessgym" / "TraceLogger.java"
    helper.parent.mkdir(parents=True, exist_ok=True)
    helper.write_text(trace_logger_source(), encoding="utf-8")
    return helper


def instrument_module(repo: Path, module_root: Path) -> dict:
    main_java = module_root / "src" / "main" / "java"
    if not main_java.is_dir():
        raise SystemExit(f"module has no src/main/java: {module_root}")
    helper = add_trace_logger(module_root)
    instrumented_files = 0
    instrumented_methods = 0
    for path in sorted(main_java.rglob("*.java")):
        if path == helper:
            continue
        count = instrument_java_file(path, repo)
        if count:
            instrumented_files += 1
            instrumented_methods += count
    return {
        "helper": str(helper.relative_to(repo)).replace("\\", "/"),
        "instrumented_files": instrumented_files,
        "instrumented_methods": instrumented_methods,
    }


def read_trace_rows(trace_log: Path, repo: Path, official_test_path: str, official_test_class: str) -> list[dict]:
    methods: list[dict] = [
        {
            "kind": "test",
            "name": official_test_class.rsplit(".", 1)[-1],
            "path": official_test_path,
            "signature": official_test_class,
        }
    ]
    if not trace_log.exists():
        return methods
    for raw in trace_log.read_text(encoding="utf-8", errors="ignore").splitlines():
        parts = raw.split("\t")
        if len(parts) != 3:
            continue
        path, name, line_s = parts
        try:
            line_no = int(line_s)
        except ValueError:
            line_no = 0
        methods.append(
            {
                "kind": "prod",
                "name": name,
                "path": path,
                "line": line_no,
                "signature": f"{name}(...)",
            }
        )
    return methods


def distinct_prod_count(methods: list[dict]) -> int:
    return len(
        {
            (str(m.get("path", "")), str(m.get("name", "")), int(m.get("line", 0) or 0))
            for m in methods
            if str(m.get("kind", "")).lower() == "prod"
        }
    )


def anchors_from_methods(methods: list[dict], limit: int) -> list[dict]:
    anchors = []
    seen: set[tuple[str, str]] = set()
    for method in methods:
        if method.get("kind") != "prod":
            continue
        key = (str(method.get("path", "")), str(method.get("name", "")))
        if key in seen:
            continue
        seen.add(key)
        anchors.append(
            {
                "file": key[0],
                "symbol": key[1],
                "role": "trace-observed production method",
            }
        )
        if len(anchors) >= limit:
            break
    return anchors


def main() -> None:
    ap = argparse.ArgumentParser(description="Collect a paper-aligned Maven execution context for one test.")
    ap.add_argument("--repo-template", required=True, help="Clean repository template")
    ap.add_argument("--repo-name", required=True)
    ap.add_argument("--official-test-class", required=True)
    ap.add_argument("--official-test-path", default="")
    ap.add_argument("--trace-id", default="", help="Defaults to official test class")
    ap.add_argument("--replay-cmd", default="", help="JSON array; defaults to Maven test command")
    ap.add_argument("--workspace-root", required=True)
    ap.add_argument("--output-dir", required=True)
    ap.add_argument("--timeout-s", type=int, default=1200)
    ap.add_argument("--anchor-limit", type=int, default=12)
    args = ap.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", args.repo_name) or not re.fullmatch(r"[A-Za-z0-9_.$]+", args.official_test_class):
        raise SystemExit("Repository and test identifiers must not contain path separators")

    repo_template = Path(args.repo_template).resolve()
    workspace_root = Path(args.workspace_root).resolve()
    output_dir = Path(args.output_dir).resolve()
    repo_work = workspace_root / f"{args.repo_name}__{args.official_test_class.replace('.', '_')}"
    if repo_work.exists() or output_dir.exists():
        raise SystemExit("Use fresh workspace and output directories; existing files are preserved")
    if repo_work.is_relative_to(repo_template) or output_dir.is_relative_to(repo_template):
        raise SystemExit("Trace outputs must be outside the repository template")
    shutil.copytree(repo_template, repo_work)
    output_dir.mkdir(parents=True, exist_ok=False)

    test_file = find_test_file(repo_work, args.official_test_path, args.official_test_class)
    official_test_path = str(test_file.relative_to(repo_work)).replace("\\", "/")
    module_rel = module_rel_for_test(repo_work, test_file)
    module_root = repo_work if module_rel == "." else repo_work / module_rel
    replay_cmd = parse_json_cmd(args.replay_cmd) if args.replay_cmd else default_replay_cmd(repo_work, test_file, args.official_test_class)

    instrumentation = instrument_module(repo_work, module_root)
    trace_log = output_dir / "trace.log.tsv"
    env = os.environ.copy()
    env["WITNESSGYM_TRACE_OUT"] = str(trace_log)
    completed = subprocess.run(
        replay_cmd,
        cwd=str(repo_work),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=args.timeout_s,
        check=False,
    )
    (output_dir / "replay.stdout.txt").write_text(completed.stdout or "", encoding="utf-8", errors="ignore")
    (output_dir / "replay.stderr.txt").write_text(completed.stderr or "", encoding="utf-8", errors="ignore")

    if completed.returncode != 0:
        payload = {
            "ok": False,
            "returncode": completed.returncode,
            "reason": "instrumented replay command failed",
            "instrumentation": instrumentation,
        }
        (output_dir / "collection_error.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        raise SystemExit(2)

    methods = read_trace_rows(trace_log, repo_work, official_test_path, args.official_test_class)
    count = distinct_prod_count(methods)
    trace_id = args.trace_id or args.official_test_class
    bucket = bucket_of(count)
    bug_related_files = []
    for method in methods:
        if method.get("kind") == "prod" and method.get("path") not in bug_related_files:
            bug_related_files.append(str(method.get("path")))
    record = {
        "id": trace_id,
        "trace_id": trace_id,
        "repo_name": args.repo_name,
        "repo": args.repo_name,
        "test_name": args.official_test_class,
        "official_test_path": official_test_path,
        "official_test_class": args.official_test_class,
        "replay_cmd": replay_cmd,
        "cmd": replay_cmd,
        "methods": methods,
        "distinct_prod_function_count": count,
        "trace_bucket": bucket,
        "trace_summary": json.dumps(
            {
                "trace_id": trace_id,
                "test_name": args.official_test_class,
                "distinct_prod_function_count": count,
                "trace_bucket": bucket,
            },
            indent=2,
        ),
        "anchors": anchors_from_methods(methods, args.anchor_limit),
        "bug_related_files": bug_related_files[:12],
    }
    command = {
        "id": trace_id,
        "test_name": args.official_test_class,
        "cmd": replay_cmd,
        "repo": args.repo_name,
        "build": "maven",
    }
    (output_dir / "execution_context.json").write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (output_dir / "selected_traces.json").write_text(json.dumps({"traces": [record]}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (output_dir / "selected_commands.json").write_text(json.dumps({"commands": [command]}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    summary = {
        "ok": True,
        "trace_id": trace_id,
        "trace_bucket": bucket,
        "distinct_prod_function_count": count,
        "replay_cmd": replay_cmd,
        "workspace": str(repo_work),
        "instrumentation": instrumentation,
    }
    (output_dir / "collection_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
