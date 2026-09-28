from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

DECL_RE = re.compile(
    r'(?m)^[ \t]*(public|protected|private)[ \t]+(?:static[ \t]+)?(?:final[ \t]+)?[A-Za-z0-9_<>\[\], ?]+[ \t]+([A-Za-z_][A-Za-z0-9_]*)[ \t]*\('
)

def class_to_path(klass: str) -> Path:
    parts = klass.split(".")
    return Path(*parts[:-1], parts[-1] + ".java")

def read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="ignore")

def find_java_file(repo: Path, module: str, klass: str, kind: str) -> Path | None:
    rel = class_to_path(klass)
    base = repo / module / "src" / ("test" if kind == "test" else "main") / "java"
    cand = base / rel
    if cand.exists():
        return cand
    if base.exists():
        hits = list(base.rglob(rel.name))
        for h in hits:
            if str(h).endswith(str(rel)):
                return h
        if hits:
            return hits[0]
    return None

def infer_prod_class(test_class: str) -> str | None:
    if test_class.endswith("TestCase"):
        return test_class[: -len("TestCase")]
    if test_class.endswith("Test"):
        return test_class[: -len("Test")]
    if test_class.endswith("Tests"):
        return test_class[: -len("Tests")]
    return None

def extract_declared_methods(java_src: str) -> list[str]:
    out: list[str] = []
    for m in DECL_RE.finditer(java_src):
        out.append(m.group(2))
    return out

def build_methods(repo: Path, module: str, test_class: str) -> list[dict[str, Any]]:
    methods: list[dict[str, Any]] = []

    tf = find_java_file(repo, module, test_class, "test")
    if tf is not None and tf.exists():
        src = read_text(tf)
        for n in extract_declared_methods(src):
            methods.append(
                {
                    "name": n,
                    "method": n,
                    "method_name": n,
                    "file": str(tf.relative_to(repo)),
                    "path": str(tf.relative_to(repo)),
                    "signature": n,
                    "sig": n,
                    "kind": "test",
                }
            )

    prod_class = infer_prod_class(test_class)
    if prod_class:
        pf = find_java_file(repo, module, prod_class, "main")
        if pf is not None and pf.exists():
            src = read_text(pf)
            for n in extract_declared_methods(src):
                methods.append(
                    {
                        "name": n,
                        "method": n,
                        "method_name": n,
                        "file": str(pf.relative_to(repo)),
                        "path": str(pf.relative_to(repo)),
                        "signature": n,
                        "sig": n,
                        "kind": "prod",
                    }
                )

    seen: set[tuple[str, str]] = set()
    uniq: list[dict[str, Any]] = []
    for m in methods:
        k = (m.get("file", ""), m.get("name", ""))
        if not k[0] or not k[1]:
            continue
        if k in seen:
            continue
        seen.add(k)
        uniq.append(m)
    return uniq

def write_json(p: Path, obj: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--trace-id", required=True)
    ap.add_argument("--test-class", required=True)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--module", required=True)
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[1]
    out_dir = root / args.out
    repo = root / args.repo
    module = args.module
    test_class = args.test_class

    methods = build_methods(repo=repo, module=module, test_class=test_class)

    traces = {
        "traces": [
            {
                "id": args.trace_id,
                "test_name": test_class,
                "methods": methods,
            }
        ]
    }

    cmd = f"mvn -pl {module} -Dtest={test_class} test"
    commands = {
        "commands": [
            {
                "id": args.trace_id,
                "test_name": test_class,
                "cmd": cmd,
                "cwd": str(repo),
            }
        ]
    }

    write_json(out_dir / "traces.json", traces)
    write_json(out_dir / "commands.json", commands)

    print(str(out_dir / "traces.json"))
    print(str(out_dir / "commands.json"))

if __name__ == "__main__":
    main()
