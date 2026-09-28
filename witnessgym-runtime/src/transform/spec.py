from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.common.errors import TransformError

def _must(d: dict[str, Any], k: str) -> Any:
    if k not in d:
        raise TransformError(f"Missing required field: {k}")
    return d[k]

def _must_str(d: dict[str, Any], k: str) -> str:
    v = _must(d, k)
    if not isinstance(v, str) or not v.strip():
        raise TransformError(f"Field must be non-empty string: {k}")
    return v

def _opt_list_str(d: dict[str, Any], k: str) -> list[str]:
    v = d.get(k, [])
    if v is None:
        return []
    if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
        raise TransformError(f"Field must be list[str]: {k}")
    return [x for x in v if x.strip()]

@dataclass(frozen=True)
class TransformImplementation:
    mode: str
    module: str | None
    entry: str | None
    prompt_template: str | None
    max_steps: int
    file_scope: list[str]

@dataclass(frozen=True)
class TransformSpec:
    id: str
    name: str
    language: str
    intent: str
    description: str
    requires: list[str]
    forbids: list[str]
    must_preserve: list[str]
    post_conditions: list[str]
    implementation: TransformImplementation
    raw: dict[str, Any]

def parse_transform(obj: dict[str, Any]) -> TransformSpec:
    tid = _must_str(obj, "id")
    name = _must_str(obj, "name")
    language = _must_str(obj, "language")
    intent = _must_str(obj, "intent")
    description = _must_str(obj, "description")

    appl = obj.get("applicability", {})
    if appl is None:
        appl = {}
    if not isinstance(appl, dict):
        raise TransformError("applicability must be object")
    requires = _opt_list_str(appl, "requires")
    forbids = _opt_list_str(appl, "forbids")

    contract = obj.get("edit_contract", {})
    if contract is None:
        contract = {}
    if not isinstance(contract, dict):
        raise TransformError("edit_contract must be object")
    must_preserve = _opt_list_str(contract, "must_preserve")
    post_conditions = _opt_list_str(contract, "post_conditions")

    impl = _must(obj, "implementation")
    if not isinstance(impl, dict):
        raise TransformError("implementation must be object")
    mode = _must_str(impl, "mode")
    module = impl.get("module")
    if module is not None and not isinstance(module, str):
        raise TransformError("implementation.module must be string")
    entry = impl.get("entry")
    if entry is not None and not isinstance(entry, str):
        raise TransformError("implementation.entry must be string")
    prompt_template = impl.get("prompt_template")
    if prompt_template is not None and not isinstance(prompt_template, str):
        raise TransformError("implementation.prompt_template must be string")
    max_steps = impl.get("max_steps", 8)
    if not isinstance(max_steps, int) or max_steps <= 0:
        raise TransformError("implementation.max_steps must be positive int")
    file_scope = _opt_list_str(impl, "file_scope")

    implementation = TransformImplementation(
        mode=mode,
        module=module,
        entry=entry,
        prompt_template=prompt_template,
        max_steps=max_steps,
        file_scope=file_scope,
    )

    return TransformSpec(
        id=tid,
        name=name,
        language=language,
        intent=intent,
        description=description,
        requires=requires,
        forbids=forbids,
        must_preserve=must_preserve,
        post_conditions=post_conditions,
        implementation=implementation,
        raw=obj,
    )
