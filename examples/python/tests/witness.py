import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from logic import clamp

assert clamp(2) == 2, "WITNESS_TARGET: positive value must be preserved"
