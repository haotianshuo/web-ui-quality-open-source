"""Read-only preparation for an evidence-bound Host source fix."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from html import escape
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping
from urllib.parse import urlsplit

from .contracts import ContractViolation, digest_json
from .release_info import PACKAGE_VERSION
from .risk_tier import classify_risk_tier
from .change_budget import build_change_budget, evaluate_change_budget

_UI_SUFFIXES = {".html", ".css", ".scss", ".sass", ".less", ".js", ".jsx", ".ts", ".tsx", ".vue", ".svelte"}
_PATH_KEYS = {"sourcefile", "sourcepath", "componentpath", "ownerpath", "targetfile"}


def _safe_explicit(root: Path, values: Iterable[str]) -> list[str]:
    result: list[str] = []
    for item in values:
        raw = str(item).strip().replace("\\", "/")
        if not raw:
            continue
        pure = PurePosixPath(raw)
        if pure.is_absolute() or ".." in pure.parts:
            raise ContractViolation("SOURCE_SCOPE_ESCAPE", [f"$: {raw} escapes project root"])
        path = (root / pure).resolve()
        try:
            path.relative_to(root)
        except ValueError as error:
            raise ContractViolation("SOURCE_SCOPE_ESCAPE", [f"$: {raw} escapes project root"]) from error
        if not path.is_file() or path.is_symlink():
            raise ContractViolation("SOURCE_FILE_MISSING", [f"$: {raw} does not exist as a regular file"])
        result.append(path.relative_to(root).as_posix())
    return sorted(dict.fromkeys(result))


def _extract_path_strings(value: Any, *, key: str | None = None) -> list[str]:
    found: list[str] = []
    if isinstance(value, Mapping):
        for child_key, child in value.items():
            found.extend(_extract_path_strings(child, key=str(child_key)))
    elif isinstance(value, list):
        for child in value:
            found.extend(_extract_path_strings(child, key=key))
    elif isinstance(value, str):
        lower_key = (key or "").casefold()
        if lower_key in _PATH_KEYS:
            found.append(value)
    return found


def _scope_from_evidence(root: Path, evidence_path: Path | None) -> tuple[list[str], list[str]]:
    if evidence_path is None or not evidence_path.is_file():
        return [], []
    try:
        payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return [], ["Evidence file could not be parsed; source ownership remains unknown."]
    candidates = _extract_path_strings(payload)
    confirmed: list[str] = []
    rejected: list[str] = []
    for raw in candidates:
        normalized = raw.split("#", 1)[0].split(":", 1)[0].replace("\\", "/").lstrip("./")
        if not normalized or Path(normalized).suffix.lower() not in _UI_SUFFIXES:
            continue
        try:
            path = (root / normalized).resolve()
            path.relative_to(root)
        except (ValueError, OSError):
            rejected.append(raw)
            continue
        if path.is_file() and not path.is_symlink():
            confirmed.append(path.relative_to(root).as_posix())
        else:
            rejected.append(raw)
    return sorted(dict.fromkeys(confirmed)), sorted(dict.fromkeys(rejected))


def _first_text(*values: Any) -> str | None:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return None


def _confirmed_relative_file(root: Path, raw: Any) -> tuple[str | None, str | None]:
    value = str(raw or "").strip().replace("\\", "/")
    if not value:
        return None, None
    value = value.split("#", 1)[0]
    if ":" in value:
        value = value.split(":", 1)[0]
    if not value or value.startswith("/") or (len(value) >= 2 and value[1] == ":"):
        return None, "SOURCE_SCOPE_ESCAPE"
    pure = PurePosixPath(value)
    if pure.is_absolute() or ".." in pure.parts:
        return None, "SOURCE_SCOPE_ESCAPE"
    if pure.suffix.casefold() not in _UI_SUFFIXES:
        return None, "SOURCE_FILE_UNSUPPORTED"
    path = (root / pure).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        return None, "SOURCE_SCOPE_ESCAPE"
    if not path.is_file() or path.is_symlink():
        return None, "SOURCE_FILE_MISSING"
    return path.relative_to(root).as_posix(), None


def _source_range(finding: Mapping[str, Any], location: Mapping[str, Any]) -> dict[str, Any]:
    raw = finding.get("sourceRange")
    if not isinstance(raw, Mapping):
        raw = location.get("sourceRange") if isinstance(location.get("sourceRange"), Mapping) else {}
    line = finding.get("sourceLine") or location.get("line")
    start_line = raw.get("startLine") or raw.get("line") or line
    end_line = raw.get("endLine") or raw.get("line") or line
    try:
        start_line = int(start_line) if start_line is not None else None
        end_line = int(end_line) if end_line is not None else None
    except (TypeError, ValueError):
        start_line = end_line = None
    if start_line is None or start_line < 1 or end_line is None or end_line < start_line:
        return {"status": "NOT_MEASURED", "startLine": None, "startColumn": None, "endLine": None, "endColumn": None}
    return {
        "status": "MEASURED",
        "startLine": start_line,
        "startColumn": raw.get("startColumn"),
        "endLine": end_line,
        "endColumn": raw.get("endColumn"),
    }


def _mapping_link(kind: str, value: Any, *, evidence: str | None = None, status: str | None = None) -> dict[str, Any]:
    text = str(value or "").strip() if value is not None else ""
    return {
        "kind": kind,
        "value": text or None,
        "status": status or ("MEASURED" if text else "NOT_MEASURED"),
        "evidence": evidence,
    }


def build_repair_mapping(project_root: str | Path, finding: Mapping[str, Any]) -> dict[str, Any]:
    """Build a read-only, evidence-labelled mapping for one Finding.

    This function never searches by filename or edits a project. Missing links
    stay missing, and multiple explicit candidates stay ambiguous so a Host or
    user can make the required scope decision.
    """
    root = Path(project_root).expanduser().resolve()
    if not root.is_dir():
        raise ContractViolation("PROJECT_ROOT_INVALID", ["$: project root is not a directory"])
    location = finding.get("location") if isinstance(finding.get("location"), Mapping) else {}
    source = finding.get("source") if isinstance(finding.get("source"), Mapping) else {}
    target = finding.get("targetIdentity") if isinstance(finding.get("targetIdentity"), Mapping) else {}
    finding_id = _first_text(finding.get("id"), finding.get("findingId"), finding.get("fingerprint")) or "finding"

    route = _first_text(location.get("route"), finding.get("routeTemplate"), finding.get("route"), target.get("route"))
    if route is None:
        target_url = _first_text(target.get("url"), finding.get("url"))
        if target_url:
            route = urlsplit(target_url).path or "/"
    selector = _first_text(location.get("selector"), finding.get("selector"))
    component = _first_text(
        location.get("component"), finding.get("component"), finding.get("componentName"),
        source.get("component") if isinstance(source, Mapping) else None,
    )
    source_candidates = finding.get("sourceCandidates")
    if not isinstance(source_candidates, list):
        source_candidates = location.get("sourceCandidates") if isinstance(location.get("sourceCandidates"), list) else []
    source_candidates = [str(item).strip() for item in source_candidates if str(item).strip()]
    explicit_source = _first_text(
        location.get("file"), location.get("sourceFile"), finding.get("sourceFile"), finding.get("sourcePath"),
        source.get("file") if isinstance(source, Mapping) else None,
    )
    ambiguous_candidates: list[str] = []
    rejected_reason: str | None = None
    source_file: str | None = None
    source_evidence: str | None = None
    if len(set(source_candidates)) > 1 and explicit_source is None:
        for candidate in sorted(set(source_candidates)):
            confirmed, reason = _confirmed_relative_file(root, candidate)
            if confirmed:
                ambiguous_candidates.append(confirmed)
            elif reason:
                rejected_reason = reason
        source_evidence = "multiple-explicit-source-candidates"
    else:
        raw_source = explicit_source or (source_candidates[0] if source_candidates else None)
        source_file, rejected_reason = _confirmed_relative_file(root, raw_source)
        if source_file:
            source_evidence = "structured-finding-location" if explicit_source else "single-explicit-source-candidate"
        elif raw_source:
            source_evidence = "structured-source-rejected"

    source_range = _source_range(finding, location)
    chain = [
        _mapping_link("Finding", finding_id, evidence="structured-finding"),
        _mapping_link("Route", route, evidence="finding-route" if route else None),
        _mapping_link("Selector", selector, evidence="finding-selector" if selector else None),
        _mapping_link("Component", component, evidence="finding-component" if component else None),
        _mapping_link("Source File", source_file, evidence=source_evidence),
        {"kind": "Source Range", **source_range, "value": source_range.get("startLine")},
    ]
    if ambiguous_candidates:
        chain[-2] = {
            "kind": "Source File", "value": None, "status": "AMBIGUOUS",
            "evidence": source_evidence, "candidates": ambiguous_candidates,
        }
    missing = [item["kind"] for item in chain[1:] if item.get("status") == "NOT_MEASURED"]
    if rejected_reason:
        status = "REJECTED"
        confidence = "NONE"
    elif ambiguous_candidates:
        status = "AMBIGUOUS"
        confidence = "NONE"
    elif missing:
        status = "INCOMPLETE"
        confidence = "MEDIUM"
    else:
        status = "COMPLETE"
        confidence = "HIGH"
    if status == "COMPLETE":
        next_action = "系统已整理完整定位链；由 Host 审查 Patch Candidate 后决定是否应用。"
    elif status == "AMBIGUOUS":
        next_action = "系统找到了多个可能的源码文件；请 Host 或用户确认唯一文件后再生成候选，不按文件名猜测。"
    elif status == "REJECTED":
        next_action = "提供项目内的真实源码路径或结构化 Finding 证据后重试；当前路径已拒绝，未确认修改范围。"
    else:
        next_action = f"系统已整理可用定位信息；还缺少：{'、'.join(missing)}。Host 可继续补齐，不要求用户手工编辑内部协议。"
    return {
        "schemaVersion": "1",
        "findingId": finding_id,
        "status": status,
        "confidence": confidence,
        "scopeConfirmed": bool(source_file),
        "route": route,
        "selector": selector,
        "component": component,
        "sourceFile": source_file,
        "sourceRange": source_range,
        "missingLinks": missing,
        "ambiguousCandidates": ambiguous_candidates,
        "rejectedReason": rejected_reason,
        "chain": chain,
        "nextAction": next_action,
    }


def build_repair_mappings(project_root: str | Path, findings: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [build_repair_mapping(project_root, finding) for finding in findings if isinstance(finding, Mapping)]


def _html(plan: dict[str, Any]) -> str:
    files = "".join(f"<li><code>{escape(item['path'])}</code><span>{escape(item['reason'])}</span></li>" for item in plan["files"])
    if not files:
        files = "<li><strong>尚未确认源码所有者</strong><span>请由 Host 将 Finding 映射到组件和精确文件后再生成 Patch Candidate。</span></li>"
    goals = "".join(f"<li>{escape(item)}</li>" for item in plan["plannedOutcomes"])
    not_do = "".join(f"<li>{escape(item)}</li>" for item in plan["willNotDo"])
    mapping = plan.get("repairMapping") if isinstance(plan.get("repairMapping"), Mapping) else {}
    mapping_items = mapping.get("items") if isinstance(mapping.get("items"), list) else []
    mapping_html = "".join(
        f"<li><strong>{escape(str(item.get('findingId')))}</strong> · {escape(str(item.get('status')))} · "
        f"{escape(str(item.get('sourceFile') or '源码文件待确认'))} · {escape(str(item.get('nextAction')))}</li>"
        for item in mapping_items if isinstance(item, Mapping)
    ) or "<li>尚无结构化 Finding 映射；系统不会按文件名猜测。</li>"
    return f"""<!doctype html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>修复范围 · Web UI Quality {PACKAGE_VERSION}</title><style>
body{{margin:0;background:#f5f7f6;color:#17211d;font:15px/1.65 system-ui,-apple-system,'Segoe UI',sans-serif}}main{{max-width:860px;margin:auto;padding:40px 20px 72px}}header,.card{{background:#fff;border:1px solid #d9e4de;border-radius:20px;padding:24px;margin-bottom:16px}}h1{{margin:0 0 8px;font-size:32px}}h2{{font-size:19px}}p,span{{color:#5d6a63}}li{{margin:9px 0}}code{{display:block;color:#123b2e;font-weight:700}}.notice{{border-left:4px solid #166b4f}}</style></head><body><main>
<header><p>Web UI Quality {PACKAGE_VERSION}</p><h1>{escape(plan['userTitle'])}</h1><p>Runtime 只准备证据和 Patch Candidate；Codex Host 执行实际写入，随后 Runtime 校验文件 Hash 并进行 After 复测。</p></header>
<section class=\"card\"><h2>计划解决</h2><ul>{goals}</ul></section><section class=\"card\"><h2>定位链</h2><ul>{mapping_html}</ul></section><section class=\"card\"><h2>源码范围</h2><ul>{files}</ul></section>
<section class=\"card\"><h2>不会执行</h2><ul>{not_do}</ul></section><section class=\"card notice\"><h2>下一步</h2><p>{escape(plan['nextAction'])}</p></section>
</main></body></html>"""


def prepare_fix_workflow(
    project_root: str | Path,
    output_dir: str | Path,
    *,
    files: Iterable[str] = (),
    evidence: str | Path | None = None,
    goal: str = "修复已确认的 Web UI 问题",
    request: str | None = None,
) -> dict[str, Any]:
    root = Path(project_root).expanduser().resolve()
    if not root.is_dir():
        raise ContractViolation("PROJECT_ROOT_INVALID", ["$: project root is not a directory"])
    output = Path(output_dir).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    explicit = _safe_explicit(root, files)
    evidence_path = Path(evidence).expanduser().resolve() if evidence else None
    mapped, rejected = _scope_from_evidence(root, evidence_path)
    evidence_payload: Mapping[str, Any] = {}
    if evidence_path is not None and evidence_path.is_file():
        try:
            loaded = json.loads(evidence_path.read_text(encoding="utf-8"))
            evidence_payload = loaded if isinstance(loaded, Mapping) else {}
        except (OSError, UnicodeError, json.JSONDecodeError):
            evidence_payload = {}
    raw_findings = evidence_payload.get("topFindings") or evidence_payload.get("findings") or evidence_payload.get("findingCandidates") or []
    if isinstance(raw_findings, Mapping):
        raw_findings = [raw_findings]
    mappings = build_repair_mappings(root, raw_findings) if isinstance(raw_findings, list) else []
    mapping_scope = sorted({str(item["sourceFile"]) for item in mappings if item.get("sourceFile")})
    scope = explicit or mapped or mapping_scope
    source = "explicit-host-scope" if explicit else "finding-evidence" if mapped else "finding-mapping" if mapping_scope else "unconfirmed"
    confirmed = bool(scope)
    legacy_risk = "R1" if len(scope) == 1 else "R2" if len(scope) > 1 else "UNKNOWN"
    risk_tier = classify_risk_tier(request or goal, source_scope=scope)
    change_budget = build_change_budget(request or goal, risk_tier=risk_tier["tier"], explicit_files=explicit)
    budget_gate = evaluate_change_budget(change_budget, changed_files=scope)
    budget_blocked = budget_gate["status"] == "BLOCKED"
    mapping_status = (
        "COMPLETE" if mappings and all(item.get("status") == "COMPLETE" for item in mappings)
        else "AMBIGUOUS" if any(item.get("status") == "AMBIGUOUS" for item in mappings)
        else "INCOMPLETE" if mappings else "NOT_AVAILABLE"
    )
    mapping_ready = not mappings or mapping_status == "COMPLETE"
    status = (
        "CHANGE_BUDGET_EXCEEDED" if budget_blocked else
        "PATCH_CANDIDATE_REQUIRED" if confirmed and mapping_ready else
        "MAPPING_REVIEW_REQUIRED" if confirmed else
        "SCOPE_NOT_CONFIRMED"
    )
    mapping_next_action = next((str(item.get("nextAction")) for item in mappings if item.get("status") != "COMPLETE"), None)
    plan: dict[str, Any] = {
        "schemaVersion": "2",
        "producer": "web-ui-quality-fix-preparation",
        "packageVersion": PACKAGE_VERSION,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "mode": "read-only-patch-preparation",
        "goal": goal,
        "userTitle": "修改范围超过预算" if budget_blocked else "已确认修复源码范围" if confirmed and mapping_ready else "需要确认定位链" if confirmed else "尚不能安全确定修改文件",
        "plannedOutcomes": ["修复已确认的可见体验问题", "保留业务规则、路由、数据行为和现有框架", "在相同任务、页面状态和三视口下复测"],
        "files": [{"path": value, "changeType": "candidate", "reason": "由显式 Host 范围或 Finding 源码证据确认"} for value in scope],
        "scopeSource": source,
        "scopeConfirmed": confirmed,
        "repairMapping": {"status": mapping_status, "items": mappings, "nextAction": mapping_next_action},
        "unresolvedEvidencePaths": rejected,
        "evidenceRef": "evidence://finding-source-map" if evidence_path and evidence_path.is_file() else None,
        "risk": legacy_risk,
        "riskTier": risk_tier,
        "changeBudget": change_budget,
        "changeBudgetGate": budget_gate,
        "validationPlan": ["390x844 真实页面复测", "768x1024 断点复测", "1440x900 桌面回归", "相同 Journey 与 Outcome Proof", "无新增 P0/P1 回归"],
        "willNotDo": ["Runtime 不直接写项目", "不自动安装依赖", "不改变后端接口、权限或持久化规则", "不访问生产数据", "不提交、推送或发布"],
        "writeAuthorized": False,
        "hostBridgeAction": "submitPatchCandidate" if confirmed and not budget_blocked and mapping_ready else "submitFixApproval",
        "sourceProjectChanged": False,
        "nextAction": (
            "当前候选范围超过 Change Budget；必须由用户/Host 明确扩大范围后生成新的绑定计划，不能沿用当前授权。"
            if budget_blocked else
            "由 Host 生成并展示精确 Patch Candidate，完成写入后回传 Hash Receipt。" if confirmed and mapping_ready else
            mapping_next_action or "请提供结构化 Finding 证据；系统会自动整理 Route、Selector、Component、Source File 和 Source Range，缺失部分再由 Host 确认。"
        ),
        "approvalBoundary": "Runtime cannot authenticate authorization or write project files. Only the Host may apply a shown Patch Candidate.",
    }
    plan["planDigest"] = digest_json(plan)
    (output / "fix-plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    (output / "index.html").write_text(_html(plan), encoding="utf-8")
    (output / "summary.md").write_text(
        f"# 修改准备\n\n- 状态：`{status}`\n- 风险：`{legacy_risk}` / `{risk_tier['tier']}`\n- Change Budget：最多 `{change_budget['maxFiles']}` 个文件 / `{change_budget['maxChangedLines']}` 行\n- Budget Gate：`{budget_gate['status']}`\n- Runtime 未修改项目。\n\n" + ("\n".join(f"- `{item}`" for item in scope) if scope else "- 尚无可确认的源码范围。") + "\n",
        encoding="utf-8",
    )
    return {**plan, "open": "index.html", "plan": "fix-plan.json"}


__all__ = ["build_repair_mapping", "build_repair_mappings", "prepare_fix_workflow"]
