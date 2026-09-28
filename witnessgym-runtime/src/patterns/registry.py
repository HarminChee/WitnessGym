from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.common.io_utils import read_json
from src.common.errors import PatternError, ConfigError
from .schema import Pattern, parse_pattern

def _extract_patterns_root(data: Any) -> Any:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for k in ["patterns", "buggy_patterns", "items", "data"]:
            v = data.get(k)
            if isinstance(v, list):
                return v
        return data
    return data

def _flatten_patterns(x: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []

    def walk(v: Any) -> None:
        if v is None:
            return
        if isinstance(v, list):
            for e in v:
                walk(e)
            return
        if isinstance(v, dict):
            if "id" in v and isinstance(v.get("id"), str):
                out.append(v)
                return
            for k in ["patterns", "buggy_patterns", "items", "data"]:
                vv = v.get(k)
                if isinstance(vv, list):
                    walk(vv)
                    return
            raise PatternError("Pattern entry is an object but missing 'id' and no nested patterns list found")
        raise PatternError(f"Pattern entry has invalid type: {type(v).__name__}")

    walk(x)
    return out

@dataclass(frozen=True)
class PatternRegistry:
    source_path: Path
    patterns: dict[str, Pattern]

    @staticmethod
    def load(path: str | Path) -> "PatternRegistry":
        p = Path(path)
        if not p.exists():
            raise ConfigError(f"Pattern path not found: {p}")

        patterns: dict[str, Pattern] = {}

        def load_one(fp: Path) -> None:
            data = read_json(fp)
            root = _extract_patterns_root(data)
            if isinstance(root, dict) and "id" in root:
                root_list = [root]
            else:
                root_list = root
            if not isinstance(root_list, (list, dict)):
                raise PatternError(f"Pattern file must be a JSON list or an object containing a patterns list: {fp}")
            objs = _flatten_patterns(root_list)
            for obj in objs:
                pat = parse_pattern(obj)
                if pat.id in patterns:
                    raise PatternError(f"Duplicate pattern id: {pat.id}")
                patterns[pat.id] = pat

        if p.is_dir():
            files = sorted([x for x in p.glob("*.json") if x.is_file() and not x.name.startswith("_")])
            if not files:
                raise ConfigError(f"No pattern spec files found in dir: {p}")
            for fp in files:
                load_one(fp)
            return PatternRegistry(source_path=p, patterns=patterns)

        load_one(p)
        return PatternRegistry(source_path=p, patterns=patterns)

    def get(self, pattern_id: str) -> Pattern:
        if pattern_id not in self.patterns:
            raise PatternError(f"Pattern not found: {pattern_id}")
        return self.patterns[pattern_id]

    def list_ids(self) -> list[str]:
        return sorted(self.patterns.keys())
