from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--python-bin", default="python3")
    parser.add_argument("--entry-script", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest_path = Path(args.manifest)
    items = [json.loads(line) for line in manifest_path.read_text().splitlines() if line.strip()]

    results = []
    for item in items:
        cmd = [args.python_bin, args.entry_script]
        for key, value in item.items():
            cmd.extend([f"--{key}", str(value)])
        completed = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        results.append(
            {
                "cmd": cmd,
                "returncode": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
            }
        )

    print(json.dumps({"total": len(results), "results": results}, indent=2))


if __name__ == "__main__":
    main()
