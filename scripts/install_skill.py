#!/usr/bin/env python3
"""Install a self-contained skill without overwriting an existing installation."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from check_release import ROOT, release_files


def install(destination: Path) -> Path:
    destination = destination.expanduser().resolve()
    target = destination / "witnessgym"
    if target.exists() or target.is_symlink():
        raise FileExistsError("WitnessGym skill already exists; review it before replacing it")
    if destination.is_relative_to(ROOT) or ROOT.is_relative_to(target):
        raise ValueError("Skill destination must be outside the source checkout")
    files = release_files(ROOT)
    target.mkdir(parents=True, exist_ok=False)
    for file in files:
        rel = file.relative_to(ROOT)
        if rel.parts[0] in {"tests", ".github"}:
            continue
        if rel.parts[:2] == ("skills", "witnessgym"):
            output = target.joinpath(*rel.parts[2:])
        elif rel.parts[0] == "skills" or file.name == "install_skill.py":
            continue
        else:
            output = target / "runtime" / rel
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file, output)
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    try:
        target = install(args.destination)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Install failed: {exc}\n")
    print(f"Installed skill: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
