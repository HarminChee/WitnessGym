from pathlib import Path
import subprocess

Path("build").mkdir(exist_ok=True)
sources = sorted(str(p) for p in Path("src").glob("*.java"))
sources += sorted(str(p) for p in Path("tests").glob("*.java"))
raise SystemExit(subprocess.run(["javac", "-d", "build", *sources]).returncode)
