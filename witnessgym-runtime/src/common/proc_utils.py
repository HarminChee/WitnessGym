from __future__ import annotations

import os
import sys

def python_bin() -> str:
    v = os.environ.get("BENCHINJECT_PYTHON")
    if v and v.strip():
        return v.strip()
    return sys.executable
