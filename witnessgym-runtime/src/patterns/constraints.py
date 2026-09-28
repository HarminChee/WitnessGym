from __future__ import annotations
from typing import Any, Iterable, Tuple

def _as_list(x: Any) -> list[str]:
    if x is None:
        return []
    if isinstance(x, list):
        return [str(i) for i in x if i is not None]
    if isinstance(x, tuple):
        return [str(i) for i in x if i is not None]
    return [str(x)]

def _get_attr(x: Any, k: str) -> Any:
    return getattr(x, k, None)

def _get_key(d: Any, k: str) -> Any:
    if isinstance(d, dict):
        return d.get(k)
    return None

def _pick(d: Any, keys: Iterable[str]) -> Any:
    for k in keys:
        v = _get_key(d, k)
        if v is not None:
            return v
    return None

def _extract_from_structure_constraints(p: Any) -> Tuple[list[str], list[str]]:
    sc = _get_attr(p, "structure_constraints")
    if sc is None:
        sc = _get_key(p, "structure_constraints")
    if sc is None:
        return [], []
    req = _pick(sc, ["required_elements", "required", "requires"])
    forb = _pick(sc, ["forbidden_elements", "forbidden", "forbids"])
    return _as_list(req), _as_list(forb)

def _extract_from_applicability(p: Any) -> Tuple[list[str], list[str]]:
    app = _get_attr(p, "applicability")
    if app is None:
        app = _get_key(p, "applicability")
    if app is None:
        return [], []
    req = _pick(app, ["requires", "required_elements", "required"])
    forb = _pick(app, ["forbids", "forbidden_elements", "forbidden"])
    return _as_list(req), _as_list(forb)

def _extract_from_top_level(p: Any) -> Tuple[list[str], list[str]]:
    req = _get_attr(p, "required_elements")
    forb = _get_attr(p, "forbidden_elements")
    if req is None:
        req = _get_key(p, "required_elements")
    if forb is None:
        forb = _get_key(p, "forbidden_elements")
    if req is None and isinstance(p, dict):
        req = _pick(p, ["required", "requires"])
    if forb is None and isinstance(p, dict):
        forb = _pick(p, ["forbidden", "forbids"])
    return _as_list(req), _as_list(forb)

def extract_required_forbidden(p: Any) -> Tuple[list[str], list[str]]:
    req, forb = _extract_from_top_level(p)
    if req or forb:
        return req, forb
    req, forb = _extract_from_structure_constraints(p)
    if req or forb:
        return req, forb
    req, forb = _extract_from_applicability(p)
    if req or forb:
        return req, forb
    return [], []
