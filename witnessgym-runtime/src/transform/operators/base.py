from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from src.transform.spec import TransformSpec

@dataclass(frozen=True)
class OperatorResult:
    ok: bool
    operator_id: str
    transform_id: str
    detail: str
    llm_output_path: str | None
    metrics: dict[str, Any]

class TransformOperator(Protocol):
    def check_applicable(self, spec: TransformSpec, context: dict[str, Any]) -> tuple[bool, str]:
        ...

    def apply(self, spec: TransformSpec, context: dict[str, Any]) -> OperatorResult:
        ...
