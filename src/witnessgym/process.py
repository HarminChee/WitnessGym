from __future__ import annotations

import os
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from .errors import WitnessGymError


@dataclass(frozen=True)
class Execution:
    returncode: int
    stdout: str
    stderr: str
    status: str
    cleanup_confirmed: bool = True


def _stop(process: subprocess.Popen) -> bool:
    if os.name == "posix":
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except PermissionError as exc:
            # A short-lived group can disappear between poll() and killpg().
            # Reap our child before deciding whether termination actually failed.
            if process.poll() is None:
                raise WitnessGymError("Cannot terminate the running subprocess group") from exc
            process.wait()
            return False  # Parent exited; descendant cleanup cannot be certified.
    elif process.poll() is None:
        process.kill()
    process.wait()
    return True


def execute(
    argv: list[str],
    *,
    cwd: Path,
    log_dir: Path,
    timeout: float,
    pass_env: tuple[str, ...] = (),
    max_output_bytes: int = 10 * 1024 * 1024,
) -> Execution:
    if not argv or any(not isinstance(x, str) or "\x00" in x for x in argv):
        raise WitnessGymError("Command must be a nonempty argument array")
    if timeout <= 0 or max_output_bytes <= 0:
        raise WitnessGymError("Timeout and output limit must be positive")
    env = {
        k: os.environ[k]
        for k in ("PATH", "SYSTEMROOT", "LANG", "LC_ALL", "TMPDIR")
        if k in os.environ
    }
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    for name in pass_env:
        if name not in os.environ:
            raise WitnessGymError(f"Requested environment variable is not set: {name}")
        env[name] = os.environ[name]
    log_dir.mkdir(parents=True, exist_ok=False)
    out_path, err_path = log_dir / "stdout.txt", log_dir / "stderr.txt"
    status = "completed"
    cleanup_confirmed = True
    with out_path.open("wb") as stdout, err_path.open("wb") as stderr:
        try:
            child = subprocess.Popen(
                argv,
                cwd=cwd,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
                start_new_session=os.name == "posix",
            )
        except OSError as exc:
            raise WitnessGymError(
                f"Cannot start executable {Path(argv[0]).name}: {type(exc).__name__}"
            ) from exc
        deadline = time.monotonic() + timeout
        try:
            while child.poll() is None:
                if out_path.stat().st_size + err_path.stat().st_size > max_output_bytes:
                    status = "output_limit"
                    cleanup_confirmed = _stop(child) and cleanup_confirmed
                    break
                if time.monotonic() >= deadline:
                    status = "timeout"
                    cleanup_confirmed = _stop(child) and cleanup_confirmed
                    break
                time.sleep(0.02)
            if out_path.stat().st_size + err_path.stat().st_size > max_output_bytes:
                status = "output_limit"
        finally:
            # Kill children left behind after their parent exited, too.
            cleanup_confirmed = _stop(child) and cleanup_confirmed
            if not cleanup_confirmed and status == "completed":
                status = "cleanup_unconfirmed"

    def bounded_text(path: Path) -> str:
        with path.open("rb") as handle:
            return handle.read(max_output_bytes).decode("utf-8", errors="replace")

    return Execution(
        child.returncode, bounded_text(out_path), bounded_text(err_path), status, cleanup_confirmed
    )
