#!/usr/bin/env python3
"""Offline smoke test, deliberately not a measured LLM experiment."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from witnessgym.config import Adapter, load_spec
from witnessgym.errors import WitnessGymError
from witnessgym.pipeline import construct, evaluate


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--language", choices=["python", "javascript", "java"], required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.output.resolve()
    if root.exists() or root.is_relative_to(ROOT) or ROOT.is_relative_to(root):
        parser.error("Use a fresh output directory outside the code checkout")
    adapter = Adapter.load(ROOT / f"examples/adapters/{args.language}.json")
    agent = ((sys.executable, str(ROOT / "examples/agents/fixture_agent.py"), "{request}"), ())
    try:
        result = construct(
            clean_repo=ROOT / "examples" / args.language,
            output=root / "construction",
            adapter=adapter,
            bug=load_spec(ROOT / "examples/specs/clamp-bug.json", kind="bug"),
            transformations=[
                load_spec(ROOT / "examples/specs/helper-transform.json", kind="transform")
            ],
            agent=agent,
            allow_local_execution=True,
        )
        if not result["accepted"]:
            return 1
        for label, context in [("NoEC", None), ("WithEC", {"functions": ["clamp"]})]:
            result = evaluate(
                clean_repo=root / "construction/clean",
                buggy_repo=root / "construction/buggy",
                output=root / label,
                adapter=adapter,
                report="clamp incorrectly handles positive values.",
                agent=agent,
                execution_context=context,
                allow_local_execution=True,
            )
            if not result["accepted"]:
                print(f"{label} failed; inspect {root / label}", file=sys.stderr)
                return 1
    except WitnessGymError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(f"PASS: {args.language} offline construction, transformation, NoEC and WithEC")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
