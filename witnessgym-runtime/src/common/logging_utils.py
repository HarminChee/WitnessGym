from __future__ import annotations

import json
import logging
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

@dataclass(frozen=True)
class LogContext:
    run_id: str
    component: str

class JsonFormatter(logging.Formatter):
    def __init__(self, ctx: LogContext):
        super().__init__()
        self.ctx = ctx

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "run_id": self.ctx.run_id,
            "component": self.ctx.component,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        extra = getattr(record, "extra", None)
        if isinstance(extra, dict):
            for k, v in extra.items():
                if k not in payload:
                    payload[k] = v
        return json.dumps(payload, ensure_ascii=False)

def build_logger(name: str, run_id: str, component: str, level: str | None = None) -> logging.Logger:
    lvl = (level or os.getenv("BENCHINJECT_LOG_LEVEL") or "INFO").upper()
    logger = logging.getLogger(f"{name}.{run_id}.{component}")
    logger.setLevel(getattr(logging, lvl, logging.INFO))
    logger.handlers.clear()
    logger.propagate = False

    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(JsonFormatter(LogContext(run_id=run_id, component=component)))
    logger.addHandler(h)
    return logger
