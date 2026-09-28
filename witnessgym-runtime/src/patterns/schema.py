from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.common.errors import PatternError

def _must(d: dict[str, Any], k: str) -> Any:
    if k not in d:
        raise PatternError(f"Missing required field: {k}")
    return d[k]

def _must_str(d: dict[str, Any], k: str) -> str:
    v = _must(d, k)
    if not isinstance(v, str) or not v.strip():
        raise PatternError(f"Field must be non-empty string: {k}")
    return v

def _must_list_str(d: dict[str, Any], k: str) -> list[str]:
    v = _must(d, k)
    if not isinstance(v, list) or not all(isinstance(x, str) and x.strip() for x in v):
        raise PatternError(f"Field must be list[str]: {k}")
    return list(v)

@dataclass(frozen=True)
class Pattern:
    id: str
    name: str
    category: str
    scope: str
    language: str
    description: str
    required_elements: list[str]
    forbidden_elements: list[str]
    exception_type: str
    typical_stacktrace_signals: list[str]
    trigger_test_shape: str
    trigger_input_properties: str
    codeql_query_id: str | None
    raw: dict[str, Any]

def _default_exception_type(category: str, language: str) -> str:
    c = (category or "").strip().upper()
    l = (language or "").strip().lower()
    if l == "java" and c == "NPE":
        return "java.lang.NullPointerException"
    return "none"

def parse_pattern(obj: dict[str, Any]) -> Pattern:
    pid = _must_str(obj, "id")
    name = _must_str(obj, "name")
    category = _must_str(obj, "category")
    scope = _must_str(obj, "scope")
    language = _must_str(obj, "language")
    description = _must_str(obj, "description")

    sc = _must(obj, "structure_constraints")
    if not isinstance(sc, dict):
        raise PatternError("structure_constraints must be object")
    required = _must_list_str(sc, "required_elements")
    forbidden = _must_list_str(sc, "forbidden_elements")

    reff = obj.get("runtime_effect", {})
    if reff is None:
        reff = {}
    if not isinstance(reff, dict):
        raise PatternError("runtime_effect must be object")

    ex = reff.get("exception_type")
    if isinstance(ex, str) and ex.strip():
        exception_type = ex.strip()
    else:
        exception_type = _default_exception_type(category, language)

    typical = reff.get("typical_stacktrace_signals", [])
    if typical is None:
        typical = []
    if not isinstance(typical, list) or not all(isinstance(x, str) for x in typical):
        raise PatternError("runtime_effect.typical_stacktrace_signals must be list[str]")
    typical2 = [x for x in typical if x.strip()]

    trig = _must(obj, "trigger_conditions")
    if not isinstance(trig, dict):
        raise PatternError("trigger_conditions must be object")
    test_shape = _must_str(trig, "test_shape")
    input_props = _must_str(trig, "input_properties")

    codeql = obj.get("codeql")
    codeql_query_id = None
    if isinstance(codeql, dict):
        qid = codeql.get("query_id")
        if isinstance(qid, str) and qid.strip():
            codeql_query_id = qid.strip()

    return Pattern(
        id=pid,
        name=name,
        category=category,
        scope=scope,
        language=language,
        description=description,
        required_elements=required,
        forbidden_elements=forbidden,
        exception_type=exception_type,
        typical_stacktrace_signals=typical2,
        trigger_test_shape=test_shape,
        trigger_input_properties=input_props,
        codeql_query_id=codeql_query_id,
        raw=obj,
    )
