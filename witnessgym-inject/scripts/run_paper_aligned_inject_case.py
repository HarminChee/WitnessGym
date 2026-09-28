#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def default_project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def slug(text: str) -> str:
    return "".join(c if c.isalnum() or c in {"-", "_", "."} else "_" for c in text)


def find_single_run_dir(run_root: Path) -> str:
    run_dirs = sorted(p for p in run_root.iterdir() if p.is_dir() and p.name.startswith("inject__"))
    return str(run_dirs[-1]) if run_dirs else ""


def changed_files_from_patch(patch_path: Path) -> list[str]:
    if not patch_path.exists():
        return []
    files: list[str] = []
    for line in patch_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.startswith("diff --git "):
            continue
        parts = line.split()
        if len(parts) < 4:
            continue
        path = parts[2][2:] if parts[2].startswith("a/") else parts[2]
        if path not in files:
            files.append(path)
    return files


def patch_matches_paper_scope(run_dir: str, attempt_index: int) -> tuple[bool, dict[str, object]]:
    if not run_dir:
        return False, {"reason": "missing_run_dir", "changed_files": []}
    run_path = Path(run_dir)
    internal_attempt = attempt_index
    result_path = run_path / "result.json"
    if result_path.exists():
        try:
            internal_attempt = int(json.loads(result_path.read_text(encoding="utf-8")).get("attempt") or attempt_index)
        except Exception:
            internal_attempt = attempt_index
    patch_path = run_path / f"attempt_{internal_attempt}.diff.patch"
    changed = changed_files_from_patch(patch_path)
    prod_files = [p for p in changed if "/src/main/java/" in f"/{p}" and p.endswith(".java")]
    forbidden = [
        p
        for p in changed
        if "/src/test/" in f"/{p}"
        or p.endswith("/pom.xml")
        or p == "pom.xml"
        or p.endswith("build.gradle")
        or p.endswith("settings.gradle")
        or p in {"mvnw", "mvnw.cmd"}
    ]
    ok = bool(prod_files) and not forbidden
    return ok, {"changed_files": changed, "production_java_files": prod_files, "forbidden_files": forbidden, "patch_path": str(patch_path)}


def build_env(backend_mode: str, aws_region: str, model_id: str) -> dict[str, str]:
    env = os.environ.copy()
    if backend_mode == "bedrock":
        env["CLAUDE_CODE_USE_BEDROCK"] = "1"
        env["AWS_REGION"] = aws_region
        env["AWS_DEFAULT_REGION"] = aws_region
        env["ANTHROPIC_MODEL"] = model_id
        env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] = "1"
        for key in ["ANTHROPIC_API_KEY", "OPENAI_API_KEY", "DEEPSEEK_API_KEY", "MOONSHOT_API_KEY", "MINIMAX_API_KEY"]:
            env.pop(key, None)
    elif backend_mode == "env":
        if aws_region:
            env.setdefault("AWS_REGION", aws_region)
            env.setdefault("AWS_DEFAULT_REGION", aws_region)
        if model_id:
            env.setdefault("ANTHROPIC_MODEL", model_id)
    else:
        raise ValueError(f"Unsupported backend_mode: {backend_mode}")
    return env


def ensure_git_baseline(repo: Path) -> None:
    """Make the copied workspace usable by the core inject pipeline."""
    has_git = (repo / ".git").exists()
    head = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--verify", "HEAD"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if has_git and head.returncode == 0:
        return

    subprocess.run(["git", "-C", str(repo), "init"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "WITNESSGYM Reviewer"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "witnessgym@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    commit_env = os.environ.copy()
    commit_env.update(
        {
            "GIT_AUTHOR_NAME": "WITNESSGYM Reviewer",
            "GIT_AUTHOR_EMAIL": "witnessgym@example.invalid",
            "GIT_COMMITTER_NAME": "WITNESSGYM Reviewer",
            "GIT_COMMITTER_EMAIL": "witnessgym@example.invalid",
        }
    )
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-m", "WITNESSGYM clean template baseline"],
        env=commit_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", default=str(default_project_root()))
    ap.add_argument("--repo-template", required=True)
    ap.add_argument("--trace-id", required=True)
    ap.add_argument("--pattern-id", required=True)
    ap.add_argument("--transform-ids", nargs="*", default=[])
    ap.add_argument("--traces", required=True)
    ap.add_argument("--commands", required=True)
    ap.add_argument("--workspace-root", required=True)
    ap.add_argument("--out-root", required=True)
    ap.add_argument("--dataset-root", required=True)
    ap.add_argument("--runner-script", default="")
    ap.add_argument("--system-prompt", default="")
    ap.add_argument("--backend-mode", choices=["bedrock", "env"], default="bedrock")
    ap.add_argument("--aws-region", default=os.environ.get("AWS_REGION", "us-west-2"))
    ap.add_argument("--model-id", default=os.environ.get("BEDROCK_MODEL_ID", ""))
    ap.add_argument("--max-attempts", type=int, default=3)
    ap.add_argument("--verify-timeout-s", type=int, default=1200)
    ap.add_argument("--python", default=sys.executable)
    args = ap.parse_args()

    if args.backend_mode == "bedrock" and not args.model_id:
        raise SystemExit("Missing --model-id or BEDROCK_MODEL_ID for bedrock mode")

    project_root = Path(args.project_root).resolve()
    bench_root = project_root / "witnessgym-runtime"
    runner_script = Path(args.runner_script).resolve() if args.runner_script else bench_root / "scripts" / "run_claude_headless.py"
    system_prompt = Path(args.system_prompt).resolve() if args.system_prompt else bench_root / "prompts" / "system" / "inject.system.txt"
    repo_template = Path(args.repo_template).resolve()
    traces_path = Path(args.traces).resolve()
    commands_path = Path(args.commands).resolve()
    workspace_root = Path(args.workspace_root).resolve()
    out_root = Path(args.out_root).resolve()
    dataset_root = Path(args.dataset_root).resolve()
    if any(p.is_relative_to(repo_template) for p in (workspace_root, out_root, dataset_root)):
        raise SystemExit("Run outputs must be outside the repository template")

    case_key = f"{slug(repo_template.name)}__{slug(args.trace_id)}__{slug(args.pattern_id)}"
    case_out = out_root / case_key
    case_out.mkdir(parents=True, exist_ok=False)

    summary: dict[str, object] = {
        "case_key": case_key,
        "repo_template": str(repo_template),
        "trace_id": args.trace_id,
        "pattern_id": args.pattern_id,
        "transform_ids": list(args.transform_ids),
        "paper_aligned_max_attempts": args.max_attempts,
        "attempts": [],
        "ok": False,
    }

    env = build_env(args.backend_mode, args.aws_region, args.model_id)

    for attempt_idx in range(1, args.max_attempts + 1):
        attempt_dir = case_out / f"attempt_{attempt_idx:02d}"
        repo_workspace = workspace_root / case_key / f"attempt_{attempt_idx:02d}" / "repo"
        run_root = attempt_dir / "run_root"
        if repo_workspace.parent.exists():
            raise SystemExit("Attempt workspace already exists; choose a fresh workspace root")
        shutil.copytree(repo_template, repo_workspace)
        ensure_git_baseline(repo_workspace)
        run_root.mkdir(parents=True, exist_ok=True)
        dataset_root.mkdir(parents=True, exist_ok=True)

        cmd = [
            args.python,
            "-m",
            "src.cli.inject",
            "--repo",
            str(repo_workspace),
            "--pattern-id",
            args.pattern_id,
            "--traces",
            str(traces_path),
            "--commands",
            str(commands_path),
            "--trace-id",
            args.trace_id,
            "--run-root",
            str(run_root),
            "--dataset-root",
            str(dataset_root),
            "--auto-clean-after",
            "0",
            "--runner-script",
            str(runner_script),
            "--system-prompt",
            str(system_prompt),
            "--max-attempts",
            "1",
            "--verify-timeout-s",
            str(args.verify_timeout_s),
        ]
        if args.transform_ids:
            cmd.extend(["--transform-ids", "AUTO", *args.transform_ids])

        completed = subprocess.run(
            cmd,
            cwd=str(bench_root),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )

        (attempt_dir / "cmd.txt").write_text(" ".join(cmd) + "\n", encoding="utf-8")
        (attempt_dir / "stdout.txt").write_text(completed.stdout or "", encoding="utf-8", errors="ignore")
        (attempt_dir / "stderr.txt").write_text(completed.stderr or "", encoding="utf-8", errors="ignore")

        run_dir = find_single_run_dir(run_root)
        paper_scope_ok, paper_scope = patch_matches_paper_scope(run_dir, 1)
        attempt_ok = completed.returncode == 0 and paper_scope_ok
        attempt_result = {
            "attempt_index": attempt_idx,
            "returncode": completed.returncode,
            "run_dir": run_dir,
            "workspace": str(repo_workspace),
            "paper_scope_ok": paper_scope_ok,
            "paper_scope": paper_scope,
            "ok": attempt_ok,
        }
        summary["attempts"].append(attempt_result)
        (attempt_dir / "attempt_result.json").write_text(json.dumps(attempt_result, indent=2) + "\n", encoding="utf-8")

        if attempt_ok:
            summary["ok"] = True
            summary["successful_attempt_index"] = attempt_idx
            break

    (case_out / "case_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    if not summary["ok"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
