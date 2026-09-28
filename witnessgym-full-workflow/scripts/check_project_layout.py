#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def default_project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", default=str(default_project_root()))
    ap.add_argument("--benchmark-root", default="")
    ap.add_argument("--skills-root", default="", help="Defaults to the parent bundle containing this script")
    args = ap.parse_args()

    root = Path(args.project_root).resolve()
    benchmark_root = Path(args.benchmark_root).resolve() if args.benchmark_root else None
    skills_root = Path(args.skills_root).resolve() if args.skills_root else root
    pattern_specs = skills_root / "witnessgym-inject" / "specs" / "patterns"
    transform_specs = skills_root / "witnessgym-inject" / "specs" / "transforms"
    runtime_root = root / "witnessgym-runtime"
    required = {
        "project_root": root.exists(),
        "runtime_root": runtime_root.is_dir(),
        "runtime_src": (runtime_root / "src" / "cli" / "inject.py").is_file()
        and (runtime_root / "src" / "trigger_v2" / "runner.py").is_file(),
        "runtime_agent_scripts": (runtime_root / "scripts" / "run_claude_headless.py").is_file(),
        "runtime_prompts": (runtime_root / "prompts" / "system" / "inject.system.txt").is_file()
        and (runtime_root / "src" / "trigger_v2" / "prompts" / "system.trigger_v2.txt").is_file(),
        "benchmark_root": True if benchmark_root is None else benchmark_root.is_dir(),
        "skills_root": skills_root.is_dir(),
        "trace_prep_skill": (skills_root / "witnessgym-trace-prep" / "SKILL.md").is_file(),
        "inject_skill": (skills_root / "witnessgym-inject" / "SKILL.md").is_file(),
        "trigger_skill": (skills_root / "witnessgym-trigger" / "SKILL.md").is_file(),
        "full_workflow_skill": (skills_root / "witnessgym-full-workflow" / "SKILL.md").is_file(),
        "paper_pattern_specs": pattern_specs.is_dir() and len([p for p in pattern_specs.glob("*.json") if not p.name.startswith("_")]) >= 10,
        "paper_transform_specs": transform_specs.is_dir() and len([p for p in transform_specs.glob("*.json") if not p.name.startswith("_")]) >= 10,
    }
    payload = {
        "project_root": str(root),
        "benchmark_root": str(benchmark_root) if benchmark_root else "",
        "skills_root": str(skills_root),
        "runtime_root": str(runtime_root),
        "checks": required,
        "ok": all(required.values()),
    }
    print(json.dumps(payload, indent=2))
    if not payload["ok"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
