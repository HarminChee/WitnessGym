from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from .errors import WitnessGymError
from .files import relative_path, under


def command(value: object, name: str) -> tuple[str, ...]:
    if (
        not isinstance(value, list)
        or not value
        or any(not isinstance(x, str) or not x or "\x00" in x for x in value)
    ):
        raise WitnessGymError(f"{name} must be a nonempty argument array, not a shell string")
    return tuple(value)


@dataclass(frozen=True)
class Adapter:
    language: str
    production_roots: tuple[str, ...]
    test_roots: tuple[str, ...]
    build: tuple[str, ...]
    verify: tuple[str, ...]
    failure_regex: str
    hidden_tests: tuple[str, ...] = ()
    ignore_dirs: tuple[str, ...] = ()
    timeout: int = 120
    failure_exit_codes: tuple[int, ...] = (1,)

    @classmethod
    def load(cls, path: Path) -> "Adapter":
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError) as exc:
            raise WitnessGymError("Cannot read adapter configuration") from exc
        if not isinstance(data, dict) or data.get("schema_version") != 1:
            raise WitnessGymError("Adapter requires schema_version 1")
        permitted = {
            "schema_version",
            "language",
            "production_roots",
            "test_roots",
            "build",
            "verify",
            "failure_regex",
            "hidden_tests",
            "ignore_dirs",
            "timeout",
            "failure_exit_codes",
        }
        if set(data) - permitted:
            raise WitnessGymError(
                "Unknown adapter fields: " + ", ".join(sorted(set(data) - permitted))
            )
        if not isinstance(data.get("language"), str) or not data["language"].strip():
            raise WitnessGymError("A language label is required")
        paths = {}
        for field in ("production_roots", "test_roots", "hidden_tests", "ignore_dirs"):
            values = data.get(field, [])
            if not isinstance(values, list) or any(not isinstance(x, str) for x in values):
                raise WitnessGymError(f"{field} must contain relative path strings")
            paths[field] = tuple(relative_path(x) for x in values)
        if not paths["production_roots"] or not paths["test_roots"]:
            raise WitnessGymError("Both production and test roots are required")
        for a in paths["production_roots"]:
            for b in paths["test_roots"]:
                if under(a, (b,)) or under(b, (a,)):
                    raise WitnessGymError("Production and test roots must not overlap")
        for name in paths["ignore_dirs"]:
            if (
                "/" in name
                or name.startswith(".")
                or any(
                    name in p.split("/") for p in paths["production_roots"] + paths["test_roots"]
                )
            ):
                raise WitnessGymError("Ignore entries must be separate build-directory names")
        if any(not under(x, paths["test_roots"]) for x in paths["hidden_tests"]):
            raise WitnessGymError("Hidden witnesses must be inside test roots")
        timeout = data.get("timeout", 120)
        if type(timeout) is not int or not 1 <= timeout <= 86400:
            raise WitnessGymError("Timeout must be an integer between 1 and 86400 seconds")
        regex = data.get("failure_regex")
        if not isinstance(regex, str) or not regex.strip():
            raise WitnessGymError("A target-specific failure_regex is required")
        try:
            if re.search(regex, "") is not None:
                raise WitnessGymError("Failure expression must not match empty output")
        except re.error as exc:
            raise WitnessGymError("Invalid failure expression") from exc
        codes = data.get("failure_exit_codes", [1])
        if (
            not isinstance(codes, list)
            or not codes
            or any(type(c) is not int or not 1 <= c < 124 for c in codes)
        ):
            raise WitnessGymError("Expected failure exit codes must be between 1 and 123")
        return cls(
            data["language"],
            paths["production_roots"],
            paths["test_roots"],
            command(data.get("build"), "build"),
            command(data.get("verify"), "verify"),
            regex,
            paths["hidden_tests"],
            paths["ignore_dirs"],
            timeout,
            tuple(codes),
        )


def load_spec(path: Path, *, kind: str) -> dict:
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        raise WitnessGymError(f"Cannot read {kind} specification") from exc
    if not isinstance(data, dict) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", str(data.get("id", ""))
    ):
        raise WitnessGymError(f"{kind} specification requires a safe, nonempty id")
    if not isinstance(data.get("instruction"), str) or not data["instruction"].strip():
        raise WitnessGymError(f"{kind} specification requires an instruction")
    return data
