#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case-result", required=True)
    args = ap.parse_args()

    payload = json.loads(Path(args.case_result).read_text(encoding="utf-8"))
    ok = bool(
        payload.get("generated_test_files")
        and payload.get("failure_type") == "TEST_FAILURE"
        and not payload.get("modified_production_files")
        and not payload.get("forbidden_non_test_changes")
    )
    summary = {
        "ok": ok,
        "detect_success": payload.get("detect_success"),
        "failure_type": payload.get("failure_type"),
        "verify_rc": payload.get("verify_rc"),
        "generated_test_files": payload.get("generated_test_files", []),
    }
    print(json.dumps(summary, indent=2))
    if not ok:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
