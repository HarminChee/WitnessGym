from __future__ import annotations

from pathlib import Path
from typing import Any

from src.common.io_utils import read_json
from src.common.errors import ConfigError

def load_commands(commands_path: str | Path) -> Any:
    p = Path(commands_path)
    return read_json(p)

def find_command(commands: Any, trace_obj: dict[str, Any], trace_id: str) -> list[str]:
    if isinstance(trace_obj, dict):
        for k in ["cmd", "command", "mvn_cmd", "exec"]:
            v = trace_obj.get(k)
            if isinstance(v, list) and all(isinstance(x, str) for x in v):
                return list(v)
            if isinstance(v, str) and v.strip():
                return v.strip().split()

    if isinstance(commands, dict):
        if trace_id in commands:
            v = commands[trace_id]
            if isinstance(v, list) and all(isinstance(x, str) for x in v):
                return list(v)
            if isinstance(v, dict):
                for k in ["cmd", "command"]:
                    vv = v.get(k)
                    if isinstance(vv, list) and all(isinstance(x, str) for x in vv):
                        return list(vv)
                    if isinstance(vv, str) and vv.strip():
                        return vv.strip().split()
        if "commands" in commands and isinstance(commands["commands"], list):
            for item in commands["commands"]:
                if isinstance(item, dict) and str(item.get("id", "")) == trace_id:
                    v = item.get("cmd") or item.get("command")
                    if isinstance(v, list) and all(isinstance(x, str) for x in v):
                        return list(v)
                    if isinstance(v, str) and v.strip():
                        return v.strip().split()

    raise ConfigError(f"Command not found for trace: {trace_id}")
