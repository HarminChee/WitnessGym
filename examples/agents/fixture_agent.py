"""Deterministic smoke-test driver. NOT an LLM and NOT benchmark-quality evidence."""

import json
from pathlib import Path
import sys

request = json.loads(Path(sys.argv[1]).read_text())
repo = Path(request["workspace"])
language = request["language"]
stage = request["stage"]
files = {"python": "src/logic.py", "javascript": "src/logic.js", "java": "src/Logic.java"}
if stage == "inject":
    source = repo / files[language]
    source.write_text(source.read_text().replace("max(", "min("))
elif stage == "transform":
    source = repo / files[language]
    if language == "python":
        source.write_text(
            "def identity(value):\n    return value\n\ndef clamp(value):\n    return identity(min(value, 0))\n"
        )
    elif language == "javascript":
        source.write_text(
            "const identity = value => value;\nmodule.exports.clamp = value => identity(Math.min(value, 0));\n"
        )
    else:
        source.write_text(
            "public final class Logic {\n    private static int identity(int value) { return value; }\n    public static int clamp(int value) { return identity(Math.min(value, 0)); }\n}\n"
        )
elif stage == "evaluate":
    if language == "python":
        name = "tests/witness.py"
        text = "import sys\nfrom pathlib import Path\nsys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))\nfrom logic import clamp\nassert clamp(2) == 2, 'WITNESS_TARGET: positive value must be preserved'\n"
    elif language == "javascript":
        name = "tests/witness.js"
        text = "const assert = require('node:assert/strict');\nconst {clamp} = require('../src/logic.js');\nassert.equal(clamp(2), 2, 'WITNESS_TARGET: positive value must be preserved');\n"
    else:
        name = "tests/Witness.java"
        text = 'public final class Witness { public static void main(String[] args) { if (Logic.clamp(2) != 2) throw new AssertionError("WITNESS_TARGET: positive value must be preserved"); } }\n'
    (repo / name).parent.mkdir(parents=True, exist_ok=True)
    (repo / name).write_text(text)
else:
    raise ValueError("Unknown fixture stage")
