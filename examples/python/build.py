import ast
from pathlib import Path

for path in Path("src").rglob("*.py"):
    ast.parse(path.read_text(), filename=str(path))
