#!/usr/bin/env python3
"""Create a code-only archive outside the source tree after release validation."""

from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

from check_release import ROOT, release_files


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.is_relative_to(ROOT) or output.exists():
        parser.error("Use a new archive path outside the source checkout")
    files = release_files(ROOT)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for file in files:
            archive.write(file, "WitnessGym/" + file.relative_to(ROOT).as_posix())
    print(f"Created code-only archive: {output} ({len(files)} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
