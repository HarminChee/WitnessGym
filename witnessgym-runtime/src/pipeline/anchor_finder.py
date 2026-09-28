from __future__ import annotations

from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class Anchor:
    kind: str
    method: str | None
    file: str | None
    detail: str

def _pick_str(d: dict[str, Any], keys: list[str]) -> str | None:
    for k in keys:
        v = d.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None

def propose_anchors(methods: list[dict[str, Any]], limit: int = 12) -> list[Anchor]:
    anchors: list[Anchor] = []
    for m in methods:
        if not isinstance(m, dict):
            continue
        name = _pick_str(m, ["method", "name", "callee", "fn"])
        file = _pick_str(m, ["file", "path", "source"])
        sig = _pick_str(m, ["signature", "sig"])
        if name is None and sig is None:
            continue
        text = sig or name or ""
        kind = "unknown"
        lower = text.lower()
        if any(x in lower for x in ["toString".lower(), "get", "metadata", "decode", "parse", "inspect", "process"]):
            kind = "deref_candidate"
        if any(x in lower for x in ["normalize", "prepare", "merge", "cache", "build", "analyze"]):
            kind = "mid_helper_candidate"
        anchors.append(Anchor(kind=kind, method=name, file=file, detail=text))
        if len(anchors) >= limit:
            break
    return anchors
