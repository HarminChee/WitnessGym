from __future__ import annotations

from pathlib import Path
from typing import Any

from src.common.io_utils import read_json
from src.common.errors import ConfigError

def load_traces(traces_path: str | Path) -> Any:
    p = Path(traces_path)
    data = read_json(p)
    return data

def find_trace(data: Any, trace_id: str) -> dict[str, Any]:
    if isinstance(data, dict):
        if trace_id in data:
            v = data[trace_id]
            if isinstance(v, dict):
                return v
            return {"value": v}
        if "traces" in data and isinstance(data["traces"], list):
            for item in data["traces"]:
                if isinstance(item, dict) and str(item.get("id", "")) == trace_id:
                    return item
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and str(item.get("id", "")) == trace_id:
                return item
    raise ConfigError(f"Trace not found: {trace_id}")

def normalize_methods(trace_obj: dict[str, Any]) -> list[dict[str, Any]]:
    for k in ["methods", "executed_methods", "calls"]:
        v = trace_obj.get(k)
        if isinstance(v, list) and all(isinstance(x, dict) for x in v):
            return list(v)
    return []

def normalize_test_name(trace_obj: dict[str, Any]) -> str | None:
    for k in ["test", "test_name", "case", "name"]:
        v = trace_obj.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None
