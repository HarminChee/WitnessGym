from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from .config import Adapter, command
from .errors import WitnessGymError
from .files import changes, copy_repo, inside, snapshot, under, write_json
from .process import execute


def agent_settings(path: Path) -> tuple[tuple[str, ...], tuple[str, ...]]:
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        raise WitnessGymError("Cannot read agent configuration") from exc
    if not isinstance(data, dict) or set(data) - {"command", "env_allowlist"}:
        raise WitnessGymError("Agent configuration accepts command and env_allowlist only")
    names = data.get("env_allowlist", [])
    if not isinstance(names, list) or any(
        not isinstance(x, str) or not re.fullmatch(r"[A-Z_][A-Z0-9_]*", x) for x in names
    ):
        raise WitnessGymError("env_allowlist must contain environment-variable names, not values")
    return command(data.get("command"), "agent command"), tuple(names)


def _new_output(output: Path, repositories: tuple[Path, ...]) -> Path:
    output = output.resolve()
    if any(
        output.is_relative_to(r.resolve()) or r.resolve().is_relative_to(output)
        for r in repositories
    ):
        raise WitnessGymError(
            "Output and input repositories must be separate, non-nested directories"
        )
    if output.exists():
        raise WitnessGymError("Output already exists; use a fresh run directory")
    output.mkdir(parents=True)
    return output


def _agent(
    *,
    argv: tuple[str, ...],
    env: tuple[str, ...],
    repo: Path,
    stage: str,
    instruction: str,
    details: dict,
    directory: Path,
    timeout: int,
) -> None:
    request = directory / "request.json"
    write_json(
        request,
        {
            "schema_version": 1,
            "stage": stage,
            "workspace": str(repo),
            "instruction": instruction,
            **details,
        },
    )
    values = {"request": str(request), "workspace": str(repo)}
    try:
        expanded = [x.format_map(values) for x in argv]
    except (KeyError, ValueError) as exc:
        raise WitnessGymError("Agent placeholders may only be {request} and {workspace}") from exc
    execution = execute(
        expanded, cwd=repo, log_dir=directory / "agent", timeout=timeout, pass_env=env
    )
    if execution.status != "completed" or execution.returncode != 0:
        raise WitnessGymError(f"Agent failed: {execution.status}; exit {execution.returncode}")


def _verify(repo: Path, adapter: Adapter, logs: Path, *, buggy: bool) -> dict:
    """Build first; a nonzero build or infrastructure outcome is never a witness."""
    build = execute(list(adapter.build), cwd=repo, log_dir=logs / "build", timeout=adapter.timeout)
    if build.status != "completed" or build.returncode != 0:
        return {
            "accepted": False,
            "reason": "build_failed",
            "status": build.status,
            "returncode": build.returncode,
        }
    run = execute(list(adapter.verify), cwd=repo, log_dir=logs / "verify", timeout=adapter.timeout)
    if run.status != "completed":
        return {"accepted": False, "reason": run.status, "returncode": run.returncode}
    accepted = (
        (
            run.returncode in adapter.failure_exit_codes
            and re.search(adapter.failure_regex, run.stdout + "\n" + run.stderr) is not None
        )
        if buggy
        else run.returncode == 0
    )
    return {
        "accepted": accepted,
        "reason": "expected_outcome" if accepted else "unexpected_outcome",
        "returncode": run.returncode,
        "status": run.status,
    }


def _audit(
    before: dict[str, str], repo: Path, adapter: Adapter, roots: tuple[str, ...]
) -> list[str]:
    delta = changes(before, snapshot(repo, adapter.ignore_dirs))
    if not delta:
        raise WitnessGymError("Agent produced no file changes")
    forbidden = [p for p in delta if not under(p, roots)]
    if forbidden:
        raise WitnessGymError("Forbidden file changes: " + ", ".join(forbidden))
    return delta


def construct(
    *,
    clean_repo: Path,
    output: Path,
    adapter: Adapter,
    bug: dict,
    transformations: list[dict],
    agent: tuple[tuple[str, ...], tuple[str, ...]],
    attempts: int = 3,
    allow_local_execution: bool = False,
) -> dict:
    if not allow_local_execution:
        raise WitnessGymError(
            "Execution requires an isolated runner or explicit --allow-local-execution"
        )
    if type(attempts) is not int or not 1 <= attempts <= 20:
        raise WitnessGymError("Attempts must be between 1 and 20")
    original = snapshot(clean_repo, adapter.ignore_dirs)
    root = _new_output(output, (clean_repo,))
    baseline = root / "clean"
    copy_repo(clean_repo, baseline, adapter.ignore_dirs)
    baseline_result = _verify(baseline, adapter, root / "baseline-check", buggy=False)
    if not baseline_result["accepted"]:
        write_json(root / "result.json", {"accepted": False, "reason": "invalid_clean_baseline"})
        raise WitnessGymError("Clean baseline does not build and pass its witness")
    current = baseline
    reports = []
    stages = [("inject", bug), *[("transform", s) for s in transformations]]
    for index, (stage, spec) in enumerate(stages):
        accepted_repo = None
        for attempt in range(attempts if stage == "inject" else 1):
            directory = root / f"{index:03d}-{stage}-{attempt + 1}"
            candidate = directory / "workspace"
            directory.mkdir()
            copy_repo(current, candidate, adapter.ignore_dirs)
            before = snapshot(candidate, adapter.ignore_dirs)
            try:
                _agent(
                    argv=agent[0],
                    env=agent[1],
                    repo=candidate,
                    stage=stage,
                    instruction=spec["instruction"],
                    details={
                        "spec": spec,
                        "language": adapter.language,
                        "allowed_roots": list(adapter.production_roots),
                    },
                    directory=directory,
                    timeout=adapter.timeout,
                )
                delta = _audit(before, candidate, adapter, adapter.production_roots)
                # Reconstruct the verification tree without agent-created build artifacts.
                checked = directory / "verification"
                copy_repo(candidate, checked, adapter.ignore_dirs)
                result = _verify(checked, adapter, directory / "checks", buggy=True)
                result.update(
                    {
                        "stage": stage,
                        "spec_id": spec["id"],
                        "attempt": attempt + 1,
                        "changed_files": delta,
                    }
                )
                if result["accepted"]:
                    accepted_repo = candidate
            except WitnessGymError as exc:
                result = {
                    "accepted": False,
                    "stage": stage,
                    "spec_id": spec["id"],
                    "attempt": attempt + 1,
                    "reason": str(exc),
                }
            reports.append(result)
            write_json(root / "result.json", {"accepted": False, "stages": reports})
            if accepted_repo is not None:
                break
        if accepted_repo is None:
            if stage == "inject":
                raise WitnessGymError(
                    "No injection passed the construction oracle; no case was released"
                )
            # A rejected transformation is recorded, never silently claimed as applied.
            continue
        current = accepted_repo
    if snapshot(clean_repo, adapter.ignore_dirs) != original:
        raise WitnessGymError("Input repository changed during construction")
    copy_repo(current, root / "buggy", adapter.ignore_dirs)
    result = {
        "schema_version": 1,
        "accepted": True,
        "bug_id": bug["id"],
        "language": adapter.language,
        "applied_transformations": [
            r["spec_id"] for r in reports if r["stage"] == "transform" and r["accepted"]
        ],
        "stages": reports,
    }
    write_json(root / "result.json", result)
    return result


def evaluate(
    *,
    clean_repo: Path,
    buggy_repo: Path,
    output: Path,
    adapter: Adapter,
    report: str,
    agent: tuple[tuple[str, ...], tuple[str, ...]],
    execution_context: object = None,
    allow_local_execution: bool = False,
) -> dict:
    if not allow_local_execution:
        raise WitnessGymError(
            "Execution requires an isolated runner or explicit --allow-local-execution"
        )
    clean_before = snapshot(clean_repo, adapter.ignore_dirs)
    buggy_before = snapshot(buggy_repo, adapter.ignore_dirs)
    source_delta = changes(clean_before, buggy_before)
    if not source_delta or any(not under(p, adapter.production_roots) for p in source_delta):
        raise WitnessGymError("The input pair must differ only in production code")
    root = _new_output(output, (clean_repo, buggy_repo))
    workspace = root / "agent-workspace"
    copy_repo(buggy_repo, workspace, adapter.ignore_dirs)
    for name in adapter.hidden_tests:
        path = inside(workspace, name)
        if not path.is_file():
            raise WitnessGymError("A declared hidden construction witness is missing")
        path.unlink()
    baseline = snapshot(workspace, adapter.ignore_dirs)
    result = {
        "schema_version": 1,
        "accepted": False,
        "setting": "WithEC" if execution_context is not None else "NoEC",
    }
    try:
        details = {
            "bug_report": report,
            "language": adapter.language,
            "allowed_roots": list(adapter.test_roots),
        }
        if execution_context is not None:
            details["execution_context"] = execution_context
        _agent(
            argv=agent[0],
            env=agent[1],
            repo=workspace,
            stage="evaluate",
            instruction="Create a witness that exposes the reported bug. Change only allowed test files.",
            details=details,
            directory=root,
            timeout=adapter.timeout,
        )
        delta = _audit(baseline, workspace, adapter, adapter.test_roots)
        if any(not inside(workspace, p).is_file() for p in delta):
            raise WitnessGymError("Deleting tests is not an acceptable witness")
        checks = {}
        for label, source in [("clean", clean_repo), ("buggy", buggy_repo)]:
            verification = root / f"{label}-verification"
            copy_repo(source, verification, adapter.ignore_dirs)
            for name in adapter.hidden_tests:
                inside(verification, name).unlink()
            for name in delta:
                target = inside(verification, name)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(inside(workspace, name), target)
            checks[label] = _verify(
                verification, adapter, root / f"{label}-checks", buggy=label == "buggy"
            )
        result.update(
            {
                "accepted": all(c["accepted"] for c in checks.values()),
                "changed_test_files": delta,
                "checks": checks,
            }
        )
    except WitnessGymError as exc:
        result["reason"] = str(exc)
    if (
        snapshot(clean_repo, adapter.ignore_dirs) != clean_before
        or snapshot(buggy_repo, adapter.ignore_dirs) != buggy_before
    ):
        result.update({"accepted": False, "reason": "input_repository_changed"})
    write_json(root / "result.json", result)
    return result
