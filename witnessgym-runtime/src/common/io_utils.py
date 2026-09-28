from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .errors import ConfigError

def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p

def read_text(path: str | Path, encoding: str = "utf-8") -> str:
    p = Path(path)
    if not p.exists():
        raise ConfigError(f"Missing file: {p}")
    return p.read_text(encoding=encoding)

def write_text(path: str | Path, content: str, encoding: str = "utf-8") -> None:
    p = Path(path)
    ensure_dir(p.parent)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(content, encoding=encoding)
    os.replace(tmp, p)

def read_json(path: str | Path) -> Any:
    raw = read_text(path)
    return json.loads(raw)

def _to_jsonable(obj: Any) -> Any:
    if is_dataclass(obj):
        return asdict(obj)
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, Mapping):
        return {str(k): _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(v) for v in obj]
    return obj

def write_json(path: str | Path, data: Any, indent: int = 2) -> None:
    p = Path(path)
    ensure_dir(p.parent)
    payload = _to_jsonable(data)
    s = json.dumps(payload, ensure_ascii=False, indent=indent, sort_keys=False)
    write_text(p, s + "\n")

def mktemp_dir(prefix: str = "witnessgym_") -> Path:
    d = Path(tempfile.mkdtemp(prefix=prefix))
    return d
