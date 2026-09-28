from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import re
import subprocess

from src.common.io_utils import read_text
from .schema import Pattern

@dataclass(frozen=True)
class ContractFinding:
    key: str
    ok: bool
    detail: str

@dataclass(frozen=True)
class ContractReport:
    pattern_id: str
    ok: bool
    findings: list[ContractFinding]

def _search_repo_text(repo: Path, needle: str, max_hits: int = 50) -> int:
    hits = 0
    for path in repo.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in [".java", ".kt", ".scala", ".xml", ".properties", ".md", ".txt", ".py", ".js", ".ts"]:
            continue
        try:
            s = read_text(path)
        except Exception:
            continue
        if needle in s:
            hits += s.count(needle)
            if hits >= max_hits:
                return hits
    return hits

def _git_diff(repo: Path) -> str:
    try:
        return subprocess.run(["git", "-C", str(repo), "diff"], capture_output=True, text=True).stdout or ""
    except Exception:
        return ""

def _extract_required_forbidden(pattern: Any) -> tuple[list[str], list[str]]:
    req: list[str] = []
    forb: list[str] = []

    v = getattr(pattern, "required_elements", None)
    if isinstance(v, list):
        req = list(v)

    v = getattr(pattern, "forbidden_elements", None)
    if isinstance(v, list):
        forb = list(v)

    sc = getattr(pattern, "structure_constraints", None)

    if isinstance(sc, dict):
        if not req:
            v = sc.get("required_elements")
            if isinstance(v, list):
                req = list(v)
        if not forb:
            v = sc.get("forbidden_elements")
            if isinstance(v, list):
                forb = list(v)

    if sc is not None and not isinstance(sc, dict):
        if not req:
            v = getattr(sc, "required_elements", None)
            if isinstance(v, list):
                req = list(v)
        if not forb:
            v = getattr(sc, "forbidden_elements", None)
            if isinstance(v, list):
                forb = list(v)

    return req, forb

def _infer_nested_from_patch(t: str) -> bool:
    if not t.strip():
        return False
    pats = [
        r"\bMap<", r"\bList<", r"\bHashMap\b", r"\bArrayList\b", r"\bLinkedHashMap\b", r"\bLinkedList\b",
        r"\.get\(", r"\.put\(", r"\.computeIfAbsent\(", r"\.containsKey\(",
        r"\w+\(\)\.\w+\(", r"\.\w+\.\w+",
    ]
    hits = 0
    for p in pats:
        hits += len(re.findall(p, t))
        if hits >= 3:
            return True
    return False

def _infer_deep_deref_from_patch(t: str) -> bool:
    if not t.strip():
        return False
    if re.search(r"get\(\)\.get\(", t):
        return True
    if re.search(r"\.\w+\.\w+\.\w+", t):
        return True
    if re.search(r"\bparams\.\w+", t):
        return True
    return False

def _infer_multi_hop_from_patch(t: str) -> bool:
    if not t.strip():
        return False
    names = re.findall(r"\bprivate\s+[\w\<\>\[\],\s]+\s+(\w+)\s*\(", t)
    uniq = []
    seen = set()
    for n in names:
        if n not in seen:
            seen.add(n)
            uniq.append(n)
    if len(uniq) < 2:
        return False
    call_hits = 0
    for n in uniq[:10]:
        call_hits += len(re.findall(rf"\b{re.escape(n)}\s*\(", t))
    return call_hits >= 4

def check_contract(pattern: Pattern, repo: str | Path, context: dict[str, Any]) -> ContractReport:
    rp = Path(repo)
    findings: list[ContractFinding] = []

    patch_text = _git_diff(rp)

    req_elems, forb_elems = _extract_required_forbidden(pattern)

    callstack_depth = int(context.get("callstack_depth", 0))
    if "at_least_three_methods_on_call_stack" in set(req_elems):
        ok = callstack_depth >= 3
        findings.append(ContractFinding(key="callstack_depth>=3", ok=ok, detail=f"callstack_depth={callstack_depth}"))

    forb = set(forb_elems)
    if "obvious_dead_branches_such_as_if_false" in forb:
        hits = _search_repo_text(rp, "if (false)")
        ok = hits == 0
        findings.append(ContractFinding(key="forbid_if_false", ok=ok, detail=f"hits={hits}"))

    if "changes_to_public_API_signatures" in forb:
        changed_public_api = bool(context.get("changed_public_api", False))
        ok = not changed_public_api
        findings.append(ContractFinding(key="forbid_public_api_change", ok=ok, detail=f"changed_public_api={changed_public_api}"))

    if "immediate_null_check_on_the_nested_field" in forb:
        immediate_null_check = bool(context.get("immediate_null_check", False))
        ok = not immediate_null_check
        findings.append(ContractFinding(key="forbid_immediate_null_check", ok=ok, detail=f"immediate_null_check={immediate_null_check}"))

    required = set(req_elems)
    if "complex_data_structure_with_nested_field_or_element" in required:
        has_nested = bool(context.get("has_nested_structure", False)) or _infer_nested_from_patch(patch_text) or _infer_nested_from_patch_v2(patch_text)
        findings.append(ContractFinding(key="require_nested_structure", ok=has_nested, detail=f"has_nested_structure={has_nested}"))

    if "parameter_or_collection_passed_through_multiple_helpers" in required:
        multi_hop = bool(context.get("multi_hop_param", False)) or _infer_multi_hop_from_patch(patch_text) or _infer_multi_hop_from_patch_v2(patch_text)
        findings.append(ContractFinding(key="require_multi_hop_param", ok=multi_hop, detail=f"multi_hop_param={multi_hop}"))

    if "deep_callee_that_uses_the_nested_field" in required:
        has_deep_deref = bool(context.get("deep_deref", False)) or _infer_deep_deref_from_patch(patch_text) or _infer_deep_deref_from_patch_v2(patch_text)
        findings.append(ContractFinding(key="require_deep_deref", ok=has_deep_deref, detail=f"deep_deref={has_deep_deref}"))

    ok_all = all(f.ok for f in findings) if findings else True
    pid = getattr(pattern, "id", "UNKNOWN_PATTERN")
    return ContractReport(pattern_id=pid, ok=ok_all, findings=findings)

def _infer_nested_from_patch_v2(t: str) -> bool:
    if not t:
        return False
    if re.search(r"\bclass\s+\w+\b", t) and re.search(r"\bstatic\s+class\s+\w+\b", t):
        return True
    if re.search(r"\bContext\b", t) and re.search(r"\bmetadata\b", t):
        return True
    if re.search(r"\bnew\s+\w+\b", t) and re.search(r"\.\w+\s*=", t):
        return True
    return False

def _infer_multi_hop_from_patch_v2(t: str) -> bool:
    if not t:
        return False
    methods = re.findall(r"^\+\s*(public|private|protected)\s+[\w\<\>\[\]]+\s+(\w+)\s*\(", t, flags=re.M)
    names = [m[1] for m in methods]
    if len(set(names)) >= 2:
        return True
    if re.search(r"\bprepare\w*\s*\(", t) and re.search(r"\bcompute\w*\s*\(", t):
        return True
    if re.search(r"\bprocess\w*\s*\(", t) and re.search(r"\bextract\w*\s*\(", t):
        return True
    return False

def _infer_deep_deref_from_patch_v2(t: str) -> bool:
    if not t:
        return False
    if re.search(r"\.\w+\.\w+", t) and re.search(r"=\s*null", t):
        return True
    if re.search(r"\bcontext\.\w+\.\w+", t) and not re.search(r"==\s*null", t):
        return True
    if re.search(r"\bcontext\.\w+\s*\+\s*", t):
        return True
    return False
