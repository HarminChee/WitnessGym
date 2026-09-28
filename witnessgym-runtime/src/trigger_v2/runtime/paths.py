from __future__ import annotations

from pathlib import Path


def normalize_repo_relpath(path: str | Path) -> str:
    return str(path).replace("\\", "/").lstrip("./")


def is_test_side_path(path: str | Path) -> bool:
    p = normalize_repo_relpath(path)
    return "/src/test/" in f"/{p}" or p.startswith("src/test/")


def is_production_path(path: str | Path) -> bool:
    p = normalize_repo_relpath(path)
    return "/src/main/" in f"/{p}" or p.startswith("src/main/")


def is_build_or_meta_path(path: str | Path) -> bool:
    p = normalize_repo_relpath(path)
    prefixes = (
        ".git/",
        ".github/",
        ".mvn/",
        "target/",
        "build/",
    )
    filenames = {
        "pom.xml",
        "build.gradle",
        "settings.gradle",
        "gradle.properties",
        "mvnw",
        "mvnw.cmd",
    }
    return p.startswith(prefixes) or p in filenames
