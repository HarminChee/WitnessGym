from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.common.errors import InjectError, OrchestratorError, TransformError
from src.common.git_utils import assert_git_repo, git_diff_patch, git_is_clean, git_restore_all, git_rev
from src.common.io_utils import ensure_dir, write_json
from src.common.logging_utils import build_logger
from src.llmtool.claude_code import ClaudeCodeHeadless
from src.patterns.contract_checker import check_contract
from src.patterns.registry import PatternRegistry
from src.pipeline.anchor_finder import propose_anchors
from src.pipeline.commands_loader import find_command, load_commands
from src.pipeline.pattern_injector import AgentPatternInjector
from src.pipeline.trace_loader import find_trace, load_traces, normalize_methods, normalize_test_name
from src.pipeline.verify_runner import run_verify
from src.transform.operators.agent_operator import AgentOperatorConfig, AgentTransformOperator
from src.transform.registry import TransformRegistry


@dataclass(frozen=True)
class OrchestratorResult:
    run_dir: str
    ok: bool
    detail: str


def _utc_id(prefix: str) -> str:
    return f"{prefix}__{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}"


def _git_reset_clean(repo: Path) -> None:
    subprocess.run(["git", "-C", str(repo), "reset", "--hard"], check=True, capture_output=True, text=True)
    subprocess.run(["git", "-C", str(repo), "clean", "-fd"], check=True, capture_output=True, text=True)


def _git_diff_text(repo: str | Path) -> str:
    rp = Path(repo).resolve()
    try:
        return subprocess.run(["git", "-C", str(rp), "diff"], capture_output=True, text=True).stdout or ""
    except Exception:
        return ""


def _git_status_text(repo: str | Path) -> str:
    rp = Path(repo).resolve()
    try:
        return subprocess.run(["git", "-C", str(rp), "status", "-sb"], capture_output=True, text=True).stdout or ""
    except Exception:
        return ""


def _dump_step_artifacts(repo: str | Path, run_dir: str | Path, attempt: int, step: str) -> None:
    rd = Path(run_dir)
    rp = Path(repo).resolve()
    prefix = f"attempt_{attempt}.step_{step}"

    try:
        patch = subprocess.run(["git", "-C", str(rp), "diff"], capture_output=True, text=True).stdout or ""
    except Exception:
        patch = ""

    try:
        stat = subprocess.run(["git", "-C", str(rp), "diff", "--stat"], capture_output=True, text=True).stdout or ""
    except Exception:
        stat = ""

    try:
        names = subprocess.run(["git", "-C", str(rp), "diff", "--name-only"], capture_output=True, text=True).stdout or ""
    except Exception:
        names = ""

    try:
        status = subprocess.run(["git", "-C", str(rp), "status", "-sb"], capture_output=True, text=True).stdout or ""
    except Exception:
        status = ""

    (rd / f"{prefix}.diff.patch").write_text(patch, encoding="utf-8")
    (rd / f"{prefix}.diff.stat.txt").write_text(stat, encoding="utf-8")
    (rd / f"{prefix}.diff.names.txt").write_text(names, encoding="utf-8")
    (rd / f"{prefix}.git_status.txt").write_text(status, encoding="utf-8")


def _walk_strings(x: Any):
    if isinstance(x, dict):
        for v in x.values():
            yield from _walk_strings(v)
    elif isinstance(x, list):
        for v in x:
            yield from _walk_strings(v)
    elif isinstance(x, str):
        yield x


def _latest_post_git_diff(run_dir: str | Path) -> str:
    rd = Path(run_dir)
    llm_dir = rd / "llm_runs"
    if not llm_dir.exists():
        return ""
    cands = sorted(llm_dir.glob("*.claude.json"), key=lambda q: q.stat().st_mtime, reverse=True)
    for f in cands:
        try:
            obj = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(obj, dict):
            v = obj.get("post_git_diff")
            if isinstance(v, str) and v.strip():
                return v
            for ss in _walk_strings(obj):
                if "diff --git " in ss:
                    return ss
    return ""


def _latest_post_git_status(run_dir: str | Path) -> str:
    rd = Path(run_dir)
    llm_dir = rd / "llm_runs"
    if not llm_dir.exists():
        return ""
    cands = sorted(llm_dir.glob("*.claude.json"), key=lambda q: q.stat().st_mtime, reverse=True)
    for f in cands:
        try:
            obj = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(obj, dict):
            v = obj.get("post_git_status")
            if isinstance(v, str) and v.strip():
                return v
    return ""


def _parse_first_json_object(text: str):
    if not isinstance(text, str) or not text.strip():
        return None
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        else:
            if ch == '"':
                in_str = True
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    chunk = text[start : i + 1]
                    try:
                        return json.loads(chunk)
                    except Exception:
                        return None
    return None


def _classify_failure(stdout: str, stderr: str) -> str:
    t = (stdout or "") + "\n" + (stderr or "")
    k = t.lower()
    compile_signals = [
        "compilation failure",
        "compilation error",
        "cannot find symbol",
        "package does not exist",
        "maven-compiler-plugin",
        "error: cannot",
    ]
    for sig in compile_signals:
        if sig in k:
            return "COMPILE_ERROR"
    if "nullpointerexception" in k:
        return "NPE"
    if "assert" in k or "assertion" in k or "expected" in k:
        return "TEST_FAILURE"
    return "OTHER_FAIL"


def _eval_cond(expr: str, signals: dict) -> bool:
    if not isinstance(expr, str) or not expr.strip():
        return False
    safe = expr.strip().replace("&&", " and ").replace("||", " or ")
    safe = safe.replace("===", "==")
    safe = re.sub(r"[^a-zA-Z0-9_\s\=\!\<\>\(\)\"\'\.\-andor]", " ", safe)
    env = {
        "contract_ok": bool(signals.get("contract_ok")),
        "verify_rc": int(signals.get("verify_rc", 0)),
        "failure_type": str(signals.get("failure_type", "")),
    }
    try:
        return bool(eval(safe, {"__builtins__": {}}, env))
    except Exception:
        return False


def _plan_transform_tree(repo: Path, run_dir: Path, runner_script: Path, system_prompt_path: Path, pattern, ctx: dict, candidates: list[str]):
    sys_text = system_prompt_path.read_text(encoding="utf-8")
    lines = []
    lines.append("You are a TRANSFORM PLANNER. Do NOT edit code. Output ONLY one JSON object.")
    lines.append("")
    lines.append("Goal: produce a conditional transform plan (tree/graph) for a controlled bug injection pipeline.")
    lines.append("Executor will run depth-first; conditions are evaluated after each step using runtime signals.")
    lines.append("")
    lines.append("Available transform IDs (choose from this list only):")
    for tid in candidates:
        lines.append(f"- {tid}")
    lines.append("")
    lines.append("Signals available in conditions:")
    lines.append("- contract_ok: boolean")
    lines.append("- verify_rc: int")
    lines.append('- failure_type: "COMPILE_ERROR" | "TEST_FAILURE" | "OTHER_FAIL" | "NPE"')
    lines.append("")
    lines.append("Context:")
    lines.append(f"- pattern_id: {pattern.id}")
    lines.append(f"- pattern_scope: {pattern.scope}")
    lines.append(f"- trace_id: {ctx.get('trace_id','')}")
    lines.append(ctx.get("trace_summary", ""))
    lines.append("")
    lines.append("Output JSON schema:")
    lines.append("{")
    lines.append('  "version": 1,')
    lines.append('  "max_steps": 10,')
    lines.append('  "root": "<transform_id>",')
    lines.append('  "nodes": {')
    lines.append('    "<transform_id>": {')
    lines.append('      "next": [')
    lines.append('        {"when": "<boolean expr>", "to": "<transform_id or null>"},')
    lines.append('        {"when": "otherwise", "to": null}')
    lines.append("      ],")
    lines.append('      "notes": "<short rationale>"')
    lines.append("    }")
    lines.append("  }")
    lines.append("}")
    lines.append("")
    lines.append("Rules:")
    lines.append("- 'otherwise' matches if no prior rule matches.")
    lines.append("- root must be one of the available IDs.")
    lines.append("- do not reference transforms outside the list.")
    task_prompt = "\n".join(lines)

    client = ClaudeCodeHeadless(repo_root=repo, runner_script=runner_script)
    rr = client.run_checked(system_prompt=sys_text, task_prompt=task_prompt, out_dir=run_dir / "llm_runs", name="plan__transforms")

    raw = ""
    try:
        raw = Path(rr.output_json).read_text(encoding="utf-8")
    except Exception:
        raw = ""

    obj = None
    if raw:
        try:
            j = json.loads(raw)
            if isinstance(j, dict) and "content" in j and isinstance(j["content"], str):
                obj = _parse_first_json_object(j["content"])
            if obj is None:
                obj = _parse_first_json_object(raw)
        except Exception:
            obj = _parse_first_json_object(raw)

    if not isinstance(obj, dict):
        return None, str(rr.output_json)

    write_json(run_dir / "transform_plan.json", obj)
    return obj, str(rr.output_json)


def _execute_transform_plan(plan: dict, candidates_by_id: dict, trans_operator, ctx: dict, run_dir: Path, attempt: int, repo: Path, base_step_index: int):
    root = plan.get("root")
    nodes = plan.get("nodes")
    max_steps = int(plan.get("max_steps", 10))
    seq = plan.get("sequence", None)

    applied = []
    step_idx = int(base_step_index)
    trace_path = run_dir / f"attempt_{attempt}.plan_trace.jsonl"

    def _append_trace(ev: dict) -> None:
        line = json.dumps(ev, ensure_ascii=False) + "\n"
        if not trace_path.exists():
            trace_path.write_text(line, encoding="utf-8", errors="ignore")
        else:
            trace_path.write_text(trace_path.read_text(encoding="utf-8", errors="ignore") + line, encoding="utf-8", errors="ignore")

    def _run_one(tid: str) -> None:
        nonlocal step_idx
        if tid not in candidates_by_id:
            _append_trace({"step_idx": step_idx, "cur": tid, "event": "missing_candidate"})
            return

        spec = candidates_by_id[tid]
        op_res = trans_operator.apply(spec=spec, context=ctx)
        write_json(run_dir / f"attempt_{attempt}.transform.{spec.id}.json", op_res.__dict__)
        transform_report = {}
        if isinstance(getattr(op_res, "metrics", None), dict):
            tr = op_res.metrics.get("transform_report")
            if isinstance(tr, dict):
                transform_report = tr
        write_json(run_dir / f"attempt_{attempt}.transform.{spec.id}.report.json", transform_report)
        if not op_res.ok:
            _append_trace({"step_idx": step_idx, "cur": tid, "transform_id": spec.id, "event": "transform_failed", "detail": op_res.detail})
            raise TransformError(f"Transform failed: {spec.id} {op_res.detail}")

        step_idx += 1
        _dump_step_artifacts(repo=repo, run_dir=run_dir, attempt=attempt, step=f"{step_idx:02d}_transform_{spec.id}")
        applied.append(spec.id)

        contract = check_contract(pattern=ctx.get("_pattern_obj"), repo=repo, context=ctx)
        ctx["contract_ok"] = bool(getattr(contract, "ok", False))
        write_json(run_dir / f"attempt_{attempt}.step_{step_idx:02d}.contract.json", getattr(contract, "__dict__", {"ok": ctx["contract_ok"]}))

        vr = run_verify(repo_root=repo, cmd=ctx.get("_verify_cmd"), timeout_s=ctx.get("_verify_timeout_s"))
        ctx["verify_rc"] = int(getattr(vr, "returncode", 0) or 0)
        ctx["failure_type"] = _classify_failure(getattr(vr, "stdout", ""), getattr(vr, "stderr", ""))
        write_json(run_dir / f"attempt_{attempt}.step_{step_idx:02d}.verify.json", getattr(vr, "__dict__", {"returncode": ctx["verify_rc"]}))

        _append_trace(
            {
                "step_idx": step_idx,
                "cur": tid,
                "transform_id": spec.id,
                "contract_ok": bool(ctx.get("contract_ok")),
                "verify_rc": int(ctx.get("verify_rc") or 0),
                "failure_type": str(ctx.get("failure_type") or ""),
                "applied": list(applied),
                "transform_report": transform_report,
                "selected_anchor": transform_report.get("edit_sites") if isinstance(transform_report, dict) else [],
                "expected_effect_on_stealth": transform_report.get("expected_effect_on_stealth") if isinstance(transform_report, dict) else "",
                "expected_effect_on_trigger_depth": transform_report.get("expected_effect_on_trigger_depth") if isinstance(transform_report, dict) else "",
            }
        )

    def _find_harden_id() -> str:
        for k in candidates_by_id.keys():
            lk = str(k).lower()
            if "fail_mode" in lk or "not_crash" in lk or "nonnull" in lk or "hardening" in lk:
                return str(k)
        return ""

    harden_id = _find_harden_id()
    harden_injected = False

    if isinstance(seq, list) and seq:
        queue = [str(x).strip() for x in seq if str(x).strip()]
        steps = 0
        while queue and steps < max_steps:
            steps += 1
            cur = queue.pop(0)
            _run_one(cur)

            ft = str(ctx.get("failure_type") or "")
            if (ft and ft != "TEST_FAILURE") and harden_id and (not harden_injected) and (harden_id not in applied):
                queue.insert(0, harden_id)
                harden_injected = True
                _append_trace({"step_idx": step_idx, "event": "inject_harden_next", "failure_type": ft, "harden_id": harden_id})

        return applied

    if not isinstance(root, str) or not isinstance(nodes, dict):
        return []

    cur = root
    steps = 0
    while isinstance(cur, str) and cur and steps < max_steps:
        steps += 1
        _run_one(cur)

        nd = nodes.get(cur)
        rules = nd.get("next", []) if isinstance(nd, dict) else []
        nxt = None
        if isinstance(rules, list):
            for rule in rules:
                if not isinstance(rule, dict):
                    continue
                when = rule.get("when", "")
                to = rule.get("to", None)
                if isinstance(when, str) and when.strip() == "otherwise":
                    if nxt is None:
                        nxt = to
                    continue
                sig = {"contract_ok": ctx.get("contract_ok"), "verify_rc": ctx.get("verify_rc"), "failure_type": ctx.get("failure_type")}
                if _eval_cond(when, sig):
                    nxt = to
                    break

        if isinstance(nxt, str) and nxt:
            cur = nxt
            continue
        break

    return applied


def _plan_transform_tree_policy(candidates: list[str], ctx: dict[str, Any]) -> dict[str, Any]:
    cands = [c for c in candidates if isinstance(c, str) and c.strip()]
    if not cands:
        return {}

    def pick_one(pred):
        for c in cands:
            if pred(c):
                return c
        return None

    harden = pick_one(lambda x: "fail_mode" in x.lower() or "not_crash" in x.lower() or "nonnull" in x.lower() or "hardening" in x.lower())

    seq = []
    for c in cands:
        if c not in seq:
            seq.append(c)

    if harden and harden not in seq:
        seq.append(harden)

    nodes: dict[str, Any] = {}
    for i, cur in enumerate(seq):
        nxt = seq[i + 1] if i + 1 < len(seq) else ""
        nodes[cur] = {"id": cur, "next": [{"when": "otherwise", "to": nxt}]}

    return {"mode": "full_chain", "root": seq[0], "sequence": seq, "max_steps": len(seq), "nodes": nodes}


def _safe_read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _cmd_to_str(cmd: Any) -> str:
    if cmd is None:
        return ""
    if isinstance(cmd, str):
        return cmd.strip()
    if isinstance(cmd, (list, tuple)):
        parts = []
        for x in cmd:
            if x is None:
                continue
            xs = str(x).strip()
            if xs:
                parts.append(xs)
        return " ".join(parts).strip()
    return str(cmd).strip()


def _archive_dataset_case(req, run_dir: Path, repo: Path, attempt: int, applied_transforms: list[str]) -> str:
    dataset_root = getattr(req, "dataset_root", None)
    if not dataset_root:
        dataset_root = Path("out/dataset")
    dataset_root = Path(dataset_root)

    repo_name = Path(getattr(req, "repo_root", repo)).name
    pattern_id = getattr(req, "pattern_id", "unknown_pattern")
    run_id = run_dir.name

    out_dir = dataset_root / repo_name / pattern_id / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        result = _safe_read_json(run_dir / "result.json")
        vr = _safe_read_json(run_dir / f"attempt_{attempt}.verify.json")
        contract = _safe_read_json(run_dir / f"attempt_{attempt}.contract.json")
        planner = _safe_read_json(run_dir / f"attempt_{attempt}.planner.json")

        meta = {
            "repo_name": repo_name,
            "pattern_id": pattern_id,
            "run_id": run_id,
            "attempt": int(attempt),
            "trace_id": str(getattr(req, "trace_id", "")),
            "created_at": datetime.utcnow().isoformat() + "Z",
            "applied_transforms": list(applied_transforms or []),
            "result": result,
            "verify": {
                "returncode": vr.get("returncode"),
                "stderr_head": (vr.get("stderr") or "")[:800],
                "stdout_head": (vr.get("stdout") or "")[:800],
            },
            "contract_ok": bool(contract.get("ok", False)),
            "contract": contract,
            "plan": planner,
        }

        changed = []
        diff_names = run_dir / f"attempt_{attempt}.step_01_inject.diff.names.txt"
        if diff_names.exists():
            changed = [x.strip() for x in diff_names.read_text(encoding="utf-8", errors="ignore").splitlines() if x.strip()]
        else:
            try:
                rr = subprocess.run(["git", "-C", str(repo), "diff", "--name-only"], capture_output=True, text=True)
                changed = [x.strip() for x in (rr.stdout or "").splitlines() if x.strip()]
            except Exception:
                changed = []

        prod, tests = [], []
        for rel in changed:
            r = rel.replace("\\", "/")
            if "/test/" in r or r.endswith("Test.java") or r.endswith("TestCase.java"):
                tests.append(r)
            else:
                prod.append(r)

        snapshot_dir = out_dir / "snapshot"
        prod_dir = snapshot_dir / "production"
        test_dir = snapshot_dir / "tests"
        prod_dir.mkdir(parents=True, exist_ok=True)
        test_dir.mkdir(parents=True, exist_ok=True)

        def _copy_rel(relpath: str, dstroot: Path):
            src = repo / relpath
            if not src.exists() or not src.is_file():
                return
            dst = dstroot / relpath
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

        for r in prod:
            _copy_rel(r, prod_dir)
        for r in tests:
            _copy_rel(r, test_dir)

        meta["changed_files"] = {"all": changed, "production": prod, "tests": tests}
        (out_dir / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        repro_cmd = ""
        if isinstance(result, dict):
            repro_cmd = _cmd_to_str(result.get("repro_cmd"))
        (out_dir / "repro_cmd.txt").write_text((repro_cmd + "\n") if repro_cmd else "\n", encoding="utf-8")

        bug_card = []
        bug_card.append("TASK: Write an alternative triggering test (anti-hit) for a known injected bug.")
        bug_card.append("")
        bug_card.append(f"Repository: {repo_name}")
        bug_card.append(f"Pattern ID: {pattern_id}")
        bug_card.append(f"Trace/Test ID: {str(getattr(req, 'trace_id', ''))}")
        bug_card.append("")
        bug_card.append("Known facts:")
        bug_card.append("- Production code has been modified to include an injected bug of the above pattern.")
        bug_card.append("- The bug is located in one or more production files listed below (do not assume exact line numbers).")
        bug_card.append("- Your goal is to add a new test or extend existing tests to deterministically trigger the bug.")
        bug_card.append("- Do not inspect diffs/patches for exact line-level details. Use only file-level location + black-box behavior.")
        bug_card.append("")
        if repro_cmd:
            bug_card.append("Reproduction command (must run verbatim):")
            bug_card.append(repro_cmd)
            bug_card.append("")
        obs = ""
        if isinstance(result, dict):
            obs = result.get("observed_exception") or ""
        if isinstance(obs, str) and obs.strip():
            bug_card.append("Observed failure signal (non-exhaustive):")
            bug_card.append(obs[:1200])
            bug_card.append("")
        if prod:
            bug_card.append("Modified production files:")
            for r in prod:
                bug_card.append(f"- {r}")
            bug_card.append("")
        bug_card.append("Constraints:")
        bug_card.append("- Do not change production code.")
        bug_card.append("- Add/modify tests only.")
        bug_card.append("- Avoid brittle assertions tied to exact formatting; prefer semantic checks.")
        bug_card.append("- Keep the test minimal but deterministic.")
        bug_card.append("")
        (out_dir / "bug_card.txt").write_text("\n".join(bug_card).rstrip() + "\n", encoding="utf-8")

        diff_dir = out_dir / "diff"
        diff_dir.mkdir(parents=True, exist_ok=True)

        def _copy_if_exists(fp: Path):
            if fp.exists() and fp.is_file():
                shutil.copy2(fp, diff_dir / fp.name)

        for fp in run_dir.glob(f"attempt_{attempt}.step_*.*"):
            _copy_if_exists(fp)
        for fp in run_dir.glob(f"attempt_{attempt}.transform.*.json"):
            _copy_if_exists(fp)

        for fp in [
            run_dir / "result.json",
            run_dir / "inputs.json",
            run_dir / "pattern.json",
            run_dir / "transform_chain.json",
            run_dir / f"attempt_{attempt}.verify.json",
            run_dir / f"attempt_{attempt}.contract.json",
            run_dir / f"attempt_{attempt}.planner.json",
            run_dir / f"attempt_{attempt}.plan_trace.jsonl",
            run_dir / f"attempt_{attempt}.diff.patch",
            run_dir / f"attempt_{attempt}.git_status.txt",
            run_dir / f"attempt_{attempt}.inject.json",
        ]:
            _copy_if_exists(fp)

        return str(out_dir)

    except Exception as e:
        try:
            (out_dir / "archive_error.json").write_text(json.dumps({"error": str(e)}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        except Exception:
            pass
        raise


def run_injection(req: Any) -> OrchestratorResult:
    repo = Path(req.repo_root)
    assert_git_repo(repo)
    git_root = subprocess.run(["git", "-C", str(repo), "rev-parse", "--show-toplevel"],
        check=True, capture_output=True, text=True).stdout.strip()
    if Path(git_root).resolve() != repo.resolve():
        raise OrchestratorError("Injection input must be the repository root, not a subdirectory")
    if not git_is_clean(repo):
        raise OrchestratorError("Input repository has uncommitted files. Use a clean disposable copy; automatic cleanup is disabled.")
    run_id = _utc_id("inject")
    run_dir = Path(req.run_root) / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    logger = build_logger("witnessgym", run_id=run_id, component="orchestrator")

    repo = Path(req.repo_root)
    assert_git_repo(repo)
    base_rev = git_rev(repo)

    write_json(
        run_dir / "inputs.json",
        {
            "repo_root": str(repo),
            "base_rev": base_rev,
            "pattern_id": req.pattern_id,
            "transform_ids": req.transform_ids,
            "traces_path": str(req.traces_path),
            "commands_path": str(req.commands_path),
            "trace_id": req.trace_id,
            "max_attempts": req.max_attempts,
            "verify_timeout_s": req.verify_timeout_s,
            "dataset_root": str(getattr(req, "dataset_root", "")) if getattr(req, "dataset_root", None) is not None else "",
            "archive_dataset": bool(getattr(req, "archive_dataset", True)),
            "auto_clean_after": bool(getattr(req, "auto_clean_after", True)),
        },
    )

    patreg = PatternRegistry.load(Path("src/patterns/specs"))
    pattern = patreg.get(req.pattern_id)
    write_json(run_dir / "pattern.json", pattern.raw)

    trreg = TransformRegistry.load(Path("src/transform/specs"))
    raw_tids = req.transform_ids
    if isinstance(raw_tids, str):
        tid_list = raw_tids.split() if raw_tids.strip() else []
    elif isinstance(raw_tids, (list, tuple)):
        tid_list = [str(x).strip() for x in raw_tids if str(x).strip()]
    else:
        tid_list = []
    auto_mode = bool(tid_list and tid_list[0] == "AUTO") or ("AUTO" in tid_list)
    transform_ids = [tid for tid in tid_list if tid != "AUTO"]
    selected_transforms = [trreg.get(tid) for tid in transform_ids]
    write_json(run_dir / "transform_chain.json", [t.raw for t in selected_transforms])

    traces_data = load_traces(req.traces_path)
    trace_obj = find_trace(traces_data, req.trace_id)
    methods = normalize_methods(trace_obj)
    test_name = normalize_test_name(trace_obj)
    cmd_data = load_commands(req.commands_path)
    test_cmd = find_command(cmd_data, trace_obj, req.trace_id)

    anchors = propose_anchors(methods, limit=12)
    trace_summary = json.dumps(
        {
            "trace_id": req.trace_id,
            "test_name": test_name,
            "methods_count": len(methods),
        },
        ensure_ascii=False,
        indent=2,
    )

    base_context: dict[str, Any] = {
        "language": pattern.language,
        "trace_id": req.trace_id,
        "test_name": test_name,
        "trace_summary": trace_summary,
        "callstack_depth": max(0, len(methods)),
        "anchors": [a.__dict__ for a in anchors],
        "allowed_files": [],
    }

    write_json(
        run_dir / "anchor_report.json",
        {
            "anchors": [a.__dict__ for a in anchors],
            "methods_count": len(methods),
            "test_name": test_name,
        },
    )

    injector = AgentPatternInjector(
        repo_root=repo,
        runner_script=req.runner_script,
        system_prompt_path=req.system_prompt_path,
        run_dir=run_dir / "llm_runs",
    )

    agent_cfg = AgentOperatorConfig(
        runner_script=Path(req.runner_script),
        system_prompt_path=Path(req.system_prompt_path),
    )
    trans_operator = AgentTransformOperator(repo_root=repo, cfg=agent_cfg, run_dir=run_dir / "llm_runs")

    attempt = 0
    last_err = None

    try:
        while attempt < int(req.max_attempts):
            attempt += 1
            logger.info(f"attempt={attempt} start", extra={"extra": {"attempt": attempt}})

            git_restore_all(repo)

            ctx = dict(base_context)
            try:
                inj_res = injector.apply(pattern=pattern, trace_context=ctx)
                ctx.update(inj_res.context_updates)

                write_json(
                    run_dir / f"attempt_{attempt}.inject.json",
                    {
                        "ok": inj_res.ok,
                        "detail": inj_res.detail,
                        "llm_output_path": inj_res.llm_output_path,
                        "context_updates": inj_res.context_updates,
                        "report": inj_res.report,
                    },
                )
                write_json(
                    run_dir / f"attempt_{attempt}.inject.report.json",
                    inj_res.report if isinstance(inj_res.report, dict) else {},
                )

                diff_names = subprocess.run(["git", "-C", str(repo), "diff", "--name-only"], capture_output=True, text=True).stdout.strip()
                if not diff_names:
                    raise RuntimeError("inject_no_diff")

                patch_after_inj = _git_diff_text(repo)
                if not patch_after_inj.strip():
                    raise RuntimeError("inject_no_diff")

                _dump_step_artifacts(repo=repo, run_dir=run_dir, attempt=attempt, step="01_inject")

                use_planner = bool(auto_mode)
                candidates_by_id = {t.id: t for t in selected_transforms}
                applied: list[str] = []

                if use_planner and candidates_by_id:
                    ctx["_pattern_obj"] = pattern
                    ctx["_verify_cmd"] = test_cmd
                    ctx["_verify_timeout_s"] = req.verify_timeout_s

                    plan_obj = _plan_transform_tree_policy(candidates=list(candidates_by_id.keys()), ctx=ctx)
                    write_json(
                        run_dir / f"attempt_{attempt}.planner.json",
                        {"ok": bool(plan_obj), "mode": "policy", "llm_output_path": "", "plan": plan_obj},
                    )
                    if not plan_obj:
                        raise RuntimeError("planner_failed_no_plan")

                    applied = _execute_transform_plan(
                        plan=plan_obj,
                        candidates_by_id=candidates_by_id,
                        trans_operator=trans_operator,
                        ctx=ctx,
                        run_dir=run_dir,
                        attempt=attempt,
                        repo=repo,
                        base_step_index=1,
                    )
                else:
                    for i, spec in enumerate(selected_transforms, start=1):
                        op_res = trans_operator.apply(spec=spec, context=ctx)
                        write_json(run_dir / f"attempt_{attempt}.transform.{spec.id}.json", op_res.__dict__)

                        transform_report = {}
                        if isinstance(getattr(op_res, "metrics", None), dict):
                            tr = op_res.metrics.get("transform_report")
                            if isinstance(tr, dict):
                                transform_report = tr
                        write_json(run_dir / f"attempt_{attempt}.transform.{spec.id}.report.json", transform_report)

                        if not op_res.ok:
                            raise TransformError(f"Transform failed: {spec.id} {op_res.detail}")
                        _dump_step_artifacts(repo=repo, run_dir=run_dir, attempt=attempt, step=f"{i+1:02d}_transform_{spec.id}")
                        applied.append(spec.id)

                ctx["applied_transforms"] = applied

                patch_text = _latest_post_git_diff(run_dir)
                if not patch_text.strip():
                    patch_text = _git_diff_text(repo)
                (run_dir / f"attempt_{attempt}.diff.patch").write_text(patch_text, encoding="utf-8")

                status_text = _latest_post_git_status(run_dir)
                if not status_text.strip():
                    status_text = _git_status_text(repo)
                (run_dir / f"attempt_{attempt}.git_status.txt").write_text(status_text, encoding="utf-8")

                ctx["last_status"] = status_text
                ctx["last_patch"] = patch_text

                contract = check_contract(pattern=pattern, repo=repo, context=ctx)
                write_json(run_dir / f"attempt_{attempt}.contract.json", contract.__dict__)
                contract_ok = bool(contract.ok)

                vr = run_verify(repo_root=repo, cmd=test_cmd, timeout_s=req.verify_timeout_s)
                write_json(run_dir / f"attempt_{attempt}.verify.json", vr.__dict__)

                ok_final = bool(contract_ok) and (vr.returncode != 0)

                write_json(
                    run_dir / "result.json",
                    {
                        "ok": ok_final,
                        "attempt": attempt,
                        "detail": ("success" if ok_final else "completed"),
                        "base_rev": base_rev,
                        "final_rev": git_rev(repo),
                        "repro_cmd": test_cmd,
                    },
                )

                if ok_final and bool(getattr(req, "archive_dataset", True)):
                    _archive_dataset_case(
                        req=req,
                        run_dir=run_dir,
                        repo=repo,
                        attempt=attempt,
                        applied_transforms=list(applied),
                    )

                logger.info(
                    "finished",
                    extra={"extra": {"attempt": attempt, "ok": ok_final, "contract_ok": contract_ok, "verify_returncode": vr.returncode}},
                )

                return OrchestratorResult(run_dir=str(run_dir), ok=ok_final, detail=("success" if ok_final else "completed"))

            except Exception as e:
                last_err = str(e)
                write_json(run_dir / f"attempt_{attempt}.error.json", {"error": last_err})
                logger.info("attempt_failed", extra={"extra": {"attempt": attempt, "error": last_err}})

        write_json(run_dir / "result.json", {"ok": False, "detail": "failed", "last_error": last_err})
        return OrchestratorResult(run_dir=str(run_dir), ok=False, detail="failed")

    finally:
        if bool(getattr(req, "auto_clean_after", True)):
            try:
                _git_reset_clean(repo)
            except Exception:
                pass
