#!/usr/bin/env python3
"""Fail closed on non-code content in a release tree; never print secret values."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIRECTORIES = {
    "src",
    "scripts",
    "tests",
    "examples",
    "docs",
    "skills",
    ".github",
    "witnessgym-runtime",
    "witnessgym-full-workflow",
    "witnessgym-trace-prep",
    "witnessgym-inject",
    "witnessgym-trigger",
}
FILES = {
    "MANIFEST.in",
    "PKG-INFO",
    "setup.cfg",
    "README.md",
    "INSTALL_SKILLS.md",
    "SECURITY.md",
    "pyproject.toml",
    ".gitignore",
    "bundle_manifest.json",
}
SKIP = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".ruff_cache", "build", "dist"}
SUFFIXES = {".py", ".md", ".txt", ".json", ".toml", ".yaml", ".yml", ".js", ".java"}
FORBIDDEN = re.compile(
    r"(?:^|[_-])(?:token|secret|credential|results?|metrics|judgments?|case_summary)(?:[_.-]|$)",
    re.I,
)
CREDENTIAL = re.compile(
    r"(?:hf_[A-Za-z0-9]{25,}|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|sk-(?:proj-)?[A-Za-z0-9_-]{30,})"
)


def release_files(root: Path) -> list[Path]:
    root = root.resolve()
    files = []
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if any(part in SKIP or part.endswith(".egg-info") for part in rel.parts):
            continue
        if path.is_symlink():
            raise ValueError(f"Release symlink rejected: {rel}")
        if path.is_dir():
            continue
        if rel.parts[0] not in DIRECTORIES and rel.as_posix() not in FILES:
            raise ValueError(f"Unexpected release file: {rel}")
        if path.suffix not in SUFFIXES and rel.as_posix() not in FILES:
            raise ValueError(f"Non-source release file: {rel}")
        if path.stat().st_size > 1_000_000:
            raise ValueError(f"Oversized release file: {rel}")
        if FORBIDDEN.search(path.name) and path.suffix not in {".py", ".js", ".java"}:
            raise ValueError(f"Sensitive/output filename rejected: {rel}")
        text = path.read_text(encoding="utf-8")
        if CREDENTIAL.search(text):
            raise ValueError(f"Credential-like content rejected (value redacted): {rel}")
        if re.search(r"/Users/[A-Za-z0-9_-]+/|/home/[A-Za-z0-9_-]+/", text):
            raise ValueError(f"Private absolute path rejected: {rel}")
        # JSON catalogues/configurations are allowed; measured case records are not.
        if path.suffix == ".json" and re.search(
            r'"(?:case_id|probability_injected|judge_model|success_rate|overall_accuracy)"\s*:',
            text,
        ):
            raise ValueError(f"Experiment/case JSON rejected: {rel}")
        files.append(path)
    if not files or not (root / "src/witnessgym/cli.py").is_file():
        raise ValueError("Missing WitnessGym source")
    return files


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    try:
        files = release_files(args.root)
    except (ValueError, OSError, UnicodeError) as exc:
        print(f"FAIL: {exc}")
        return 1
    print(
        f"PASS: {len(files)} allowlisted code/documentation files; no dataset or experiment outputs"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
