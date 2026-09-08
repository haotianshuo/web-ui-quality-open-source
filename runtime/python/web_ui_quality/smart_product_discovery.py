"""Evidence-bounded product discovery for the one-sentence upgrade flow.

This stage converts a bounded source and screenshot scan into a human-readable
product understanding, at most three high-impact questions, an internal
execution brief, and a test plan.  It never treats source naming as proof of a
real organisation chart or screenshot geometry as proof of hidden behaviour.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import copy
from html import escape
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from .component_registry import detect_framework
from .release_info import release_identity
from .scope_policy import collect_project_sources
from .workflow_policy import (
    EVIDENCE_CLASSES,
    TrustedWorkflowApproval,
    confirmation_ledger,
    model_capability_profile,
    validate_confirmation,
)
from .screenshot_input import analyse_screenshot


_SOURCE_SUFFIXES = {
    ".html", ".htm", ".css", ".scss", ".less", ".js", ".jsx", ".ts", ".tsx",
    ".vue", ".svelte", ".json", ".yaml", ".yml", ".md", ".py", ".php",
    ".java", ".kt", ".cs", ".go", ".rb", ".sql",
}
_SENSITIVE_PARTS = {
    "secret", "secrets", "credential", "credentials", "private-key", "private_key",
    "access-token", "access_token", "refresh-token", "refresh_token", "passwords",
}

_ROLES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("system-admin", "系统管理员", ("systemadmin", "system-admin", "superadmin", "super-admin", "系统管理员", "超级管理员")),
    ("manufacturer-admin", "业务管理员", ("factoryadmin", "manufactureradmin", "tenantadmin", "businessadmin", "厂家管理员", "业务管理员")),
    ("reviewer", "审核员", ("reviewer", "auditor", "approver", "moderator", "审核员", "审批员", "复核员")),
    ("dealer", "经销商或代理商", ("dealer", "distributor", "reseller", "agency", "agent", "经销商", "代理商")),
    ("employee", "员工或销售", ("employee", "staff", "salesperson", "sales-user", "员工", "销售人员", "业务员")),
    ("editor", "剪辑或处理人员", ("editor", "producer", "processor", "剪辑员", "处理人员")),
    ("customer", "普通用户", ("customer", "member", "consumer", "enduser", "end-user", "普通用户", "会员")),
    ("operator", "运营人员", ("operator", "operations", "campaign-manager", "运营人员", "运营管理员")),
)

_ENTITIES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("video-asset", "视频素材", ("videoasset", "video_asset", "video-material", "素材视频", "视频素材")),
    ("media-asset", "内容素材", ("mediaasset", "media_asset", "media-library", "contentasset", "content-item", "素材库", "内容素材", "内容资源")),
    ("review-record", "审核记录", ("reviewrecord", "review_record", "approvalrecord", "审核记录", "审批记录")),
    ("assignment", "分配记录", ("assignment", "allocation", "distribution", "分配记录", "派发记录")),
    ("claim", "领取记录", ("claimrecord", "claim_record", "领取记录", "领用记录")),
    ("download", "下载记录", ("downloadrecord", "download_record", "下载记录")),
    ("activity", "活动或任务", ("campaign", "activity", "challenge", "task", "活动", "任务")),
    ("reward", "奖励", ("reward", "incentive", "bonus", "points", "奖励", "激励", "积分")),
    ("sop", "SOP 或操作步骤", ("sop", "procedure", "instruction", "stepversion", "步骤版本", "操作步骤")),
    ("customer-account", "客户或账户", ("customer", "account", "contact", "lead", "客户", "账户", "线索")),
    ("product-order", "商品或订单", ("product", "order", "cart", "checkout", "商品", "订单", "购物车")),
    ("ticket", "工单或请求", ("ticket", "request", "case", "工单", "请求单")),
)

_ACTIONS: tuple[tuple[str, str, int, tuple[str, ...]], ...] = (
    ("login", "登录", 5, ("login", "signin", "sign-in", "登录")),
    ("search", "查找", 10, ("search", "filter", "query", "查找", "搜索", "筛选")),
    ("upload", "上传", 20, ("upload", "uploader", "上传")),
    ("create", "创建", 25, ("create", "new-item", "新增", "创建")),
    ("submit", "提交", 30, ("submit", "commit", "提交")),
    ("review", "审核", 40, ("review", "audit", "moderate", "审核", "复核")),
    ("approve", "批准", 50, ("approve", "accept", "批准", "通过")),
    ("reject", "驳回", 51, ("reject", "deny", "驳回", "拒绝")),
    ("revise", "修改并重提", 55, ("revise", "resubmit", "re-submit", "重新提交", "修改后提交")),
    ("process", "剪辑或处理", 60, ("editvideo", "transcode", "process-media", "processing", "剪辑", "转码", "处理中")),
    ("assign", "分配", 70, ("assign", "allocate", "distribute", "分配", "派发")),
    ("claim", "领取", 80, ("claim", "receive-item", "领取", "领用")),
    ("download", "下载", 90, ("download", "export-file", "下载")),
    ("participate", "参与活动", 100, ("participate", "joincampaign", "join-campaign", "报名", "参与活动")),
    ("reward", "发放奖励", 110, ("grantreward", "issue-reward", "reward", "发放奖励", "奖励发放")),
    ("publish", "发布", 115, ("publish", "发布", "上线")),
    ("track", "追踪状态", 120, ("track", "history", "timeline", "追踪", "历史记录")),
)

_STATES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("draft", "草稿", ("draft", "草稿")),
    ("submitted", "已提交", ("submitted", "已提交")),
    ("pending-review", "待审核", ("pending_review", "pending-review", "awaitingreview", "待审核")),
    ("approved", "审核通过", ("approved", "审核通过", "已通过")),
    ("rejected", "已驳回", ("rejected", "declined", "已驳回", "审核驳回")),
    ("processing", "处理中", ("processing", "editing", "transcoding", "处理中", "剪辑中")),
    ("assigned", "已分配", ("assigned", "allocated", "已分配")),
    ("claimed", "已领取", ("claimed", "received", "已领取")),
    ("downloaded", "已下载", ("downloaded", "已下载")),
    ("active", "进行中", ("active", "in_progress", "in-progress", "进行中")),
    ("completed", "已完成", ("completed", "done", "已完成")),
    ("failed", "失败", ("failed", "error", "失败", "异常")),
    ("cancelled", "已取消", ("cancelled", "canceled", "已取消")),
)

_ROLE_CONTEXT = re.compile(r"\b(role|roles|permission|permissions|authorize|authorise|guard|policy|access)\b|rolepermissions?|角色|权限|鉴权|路由守卫", re.I)
_PERMISSION_CONTEXT = re.compile(r"\b(permission|permissions|authorize|authorise|guard|policy|access-control|hasrole|canaccess)\b|rolepermissions?|用户角色|角色权限|鉴权|路由守卫|数据权限", re.I)
_ROUTE_PATTERNS = (
    re.compile(r"(?:path|to|href)\s*[:=]\s*[\"'](/[^\"'#? ]{0,120})[\"']", re.I),
    re.compile(r"<Route\b[^>]*\bpath\s*=\s*[\"'](/[^\"']{0,120})[\"']", re.I),
)

MAX_QUESTIONS_PER_ROUND = 3

# A host may invoke the skill and plugin adapter in the same Python process.
# Keep one bounded, report-only understanding in that process so two adapters
# cannot independently ask the model to reconstruct the same source tree.  No
# source text is retained here; the exported cache remains the durable resume
# boundary and is still fingerprint-checked.
_PROCESS_DISCOVERY_CACHE: dict[tuple[str, str, str], dict[str, Any]] = {}
_PROCESS_DISCOVERY_CACHE_LIMIT = 8


def _humanise(value: str) -> str:
    value = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", value)
    value = re.sub(r"[-_]+", " ", value).strip()
    return " ".join(part for part in value.split() if part).strip()


def _is_sensitive(path: Path) -> bool:
    lowered = path.as_posix().casefold()
    return any(part in lowered for part in _SENSITIVE_PARTS) or path.suffix.casefold() in {".pem", ".key", ".p12", ".pfx"}


def _quick_scope_signature(root: Path) -> str:
    """Cheap resume check; content hashes are taken on a cache miss."""
    paths, skipped, hygiene = collect_project_sources(
        root,
        suffixes=_SOURCE_SUFFIXES,
        max_files=360,
        max_file_bytes=512_000,
        max_total_bytes=24 * 1024 * 1024,
    )
    digest = hashlib.sha256()
    digest.update(json.dumps({
        "candidateFiles": hygiene.get("candidateFiles"),
        "budgetExceeded": hygiene.get("budgetExceeded"),
        "budgetReason": hygiene.get("budgetReason"),
        "skipped": [(item.get("path"), item.get("reason")) for item in skipped],
    }, ensure_ascii=False, sort_keys=True).encode("utf-8"))
    for path in paths:
        try:
            stat = path.stat()
        except OSError:
            continue
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(f"{stat.st_size}:{stat.st_mtime_ns}".encode("ascii"))
    return digest.hexdigest()


def _input_signature(
    business_context: Mapping[str, Any] | None = None,
    screenshot_paths: Sequence[str | Path] = (),
    multimodal_overlay: Mapping[str, Any] | None = None,
) -> str:
    """Fingerprint non-source inputs so a cache cannot cross business context."""
    screenshots: list[dict[str, Any]] = []
    for value in screenshot_paths[:5]:
        path = Path(value).expanduser().resolve()
        try:
            stat = path.stat()
            screenshots.append({"path": path.as_posix(), "size": stat.st_size, "mtime": stat.st_mtime_ns})
        except OSError:
            screenshots.append({"path": path.as_posix(), "missing": True})
    payload = {
        "businessContext": dict(business_context or {}),
        "screenshots": screenshots,
        "multimodalOverlay": dict(multimodal_overlay or {}),
    }
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def _read_sources(root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    paths, skipped, hygiene = collect_project_sources(
        root,
        suffixes=_SOURCE_SUFFIXES,
        max_files=360,
        max_file_bytes=512_000,
        max_total_bytes=24 * 1024 * 1024,
    )
    sources: list[dict[str, Any]] = []
    sensitive_skips = 0
    for path in paths:
        relative = path.relative_to(root)
        if _is_sensitive(relative):
            sensitive_skips += 1
            continue
        try:
            raw = path.read_bytes()
            text = raw.decode("utf-8")
        except (OSError, UnicodeError):
            continue
        sources.append({
            "path": relative.as_posix(),
            "text": text,
            "lower": text.casefold(),
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        })
    scope = dict(hygiene)
    scope["readableFiles"] = len(sources)
    scope["sensitiveNameSkips"] = sensitive_skips
    scope["explicitSkippedFiles"] = int(scope.get("explicitSkippedFiles", len(skipped)))
    digest = hashlib.sha256()
    for source in sources:
        digest.update(str(source["path"]).encode("utf-8"))
        digest.update(str(source["sha256"]).encode("ascii"))
    scope["canonicalScan"] = {
        "id": digest.hexdigest(),
        "readCount": 1,
        "quickSignature": _quick_scope_signature(root),
        "cacheable": True,
        "duplicateScanCount": 0,
    }
    return sources, scope


def _first_evidence(source: Mapping[str, Any], term: str, evidence_type: str) -> dict[str, Any]:
    lower = str(source["lower"])
    offset = lower.find(term.casefold())
    line = str(source["text"])[:max(0, offset)].count("\n") + 1
    return {"type": evidence_type, "path": source["path"], "line": line, "match": term}


def _scan_concepts(
    sources: Sequence[Mapping[str, Any]],
    definitions: Sequence[tuple[str, str, Sequence[str]]],
    *,
    role_mode: bool = False,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for identifier, label, terms in definitions:
        score = 0
        files: set[str] = set()
        evidence: list[dict[str, Any]] = []
        contextual = False
        for source in sources:
            lower = str(source["lower"])
            matched = [(term, lower.count(term.casefold())) for term in terms if term.casefold() in lower]
            if not matched:
                continue
            amount = sum(count for _term, count in matched)
            if role_mode:
                local_context = False
                text = str(source["text"])
                for term, _count in matched:
                    for match in re.finditer(re.escape(term), text, re.I):
                        window = text[max(0, match.start() - 120):match.end() + 120]
                        if _ROLE_CONTEXT.search(window):
                            local_context = True
                            break
                    if local_context:
                        break
                if not local_context and not any(part in str(source["path"]).casefold() for part in ("role", "permission", "auth", "guard", "policy")):
                    continue
            else:
                local_context = True
            contextual = contextual or local_context
            score += min(amount, 12) * (3 if role_mode and local_context else 1)
            files.add(str(source["path"]))
            if len(evidence) < 4:
                term = max(matched, key=lambda item: item[1])[0]
                evidence.append(_first_evidence(source, term, "SOURCE_CONFIRMED" if local_context else "AI_INFERRED"))
        if score:
            confidence = min(0.96, 0.38 + min(score, 18) * 0.025 + min(len(files), 4) * 0.06)
            results.append({
                "id": identifier,
                "label": label,
                "score": score,
                "confidence": round(confidence, 3),
                "evidenceType": "SOURCE_CONFIRMED" if contextual else "AI_INFERRED",
                "sourceFiles": sorted(files),
                "evidence": evidence,
            })
    return sorted(results, key=lambda item: (-int(item["score"]), str(item["id"])))


def _scan_actions(sources: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    definitions = [(identifier, label, terms) for identifier, label, _order, terms in _ACTIONS]
    records = _scan_concepts(sources, definitions)
    order = {identifier: position for identifier, _label, position, _terms in _ACTIONS}
    for record in records:
        record["flowOrder"] = order[record["id"]]
    return records


def _extract_routes(root: Path, sources: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    for source in sources:
        path = str(source["path"])
        text = str(source["text"])
        candidates: list[tuple[str, int]] = []
        for pattern in _ROUTE_PATTERNS:
            candidates.extend((match.group(1), text[:match.start(1)].count("\n") + 1) for match in pattern.finditer(text))
        parts = Path(path).parts
        if "pages" in parts and Path(path).stem not in {"_app", "_document", "index"}:
            index = parts.index("pages")
            route_parts = list(parts[index + 1:])
            route_parts[-1] = Path(route_parts[-1]).stem
            candidates.append(("/" + "/".join(route_parts), 1))
        if "app" in parts and Path(path).stem == "page":
            index = parts.index("app")
            candidates.append(("/" + "/".join(parts[index + 1:-1]), 1))
        for route, line in candidates:
            route = re.sub(r"/+", "/", route).rstrip("/") or "/"
            if route.startswith("/api/") or len(route) > 120:
                continue
            record = found.setdefault(route, {"path": route, "evidenceType": "SOURCE_CONFIRMED", "evidence": []})
            if len(record["evidence"]) < 4:
                record["evidence"].append({"type": "SOURCE_CONFIRMED", "path": path, "line": line, "match": route})
    return [found[key] for key in sorted(found)][:40]


def _product_name(root: Path, sources: Sequence[Mapping[str, Any]], context: Mapping[str, Any]) -> tuple[str, str]:
    explicit = context.get("productName") or context.get("name")
    if explicit:
        return str(explicit).strip(), "USER_CONFIRMED"
    for source in sources:
        if Path(str(source["path"])).name == "package.json":
            try:
                value = json.loads(str(source["text"]))
            except json.JSONDecodeError:
                continue
            if isinstance(value, Mapping) and isinstance(value.get("displayName") or value.get("name"), str):
                return _humanise(str(value.get("displayName") or value.get("name"))).title(), "SOURCE_CONFIRMED"
    for source in sources:
        match = re.search(r"<title[^>]*>(.*?)</title>", str(source["text"]), re.I | re.S)
        if match:
            name = _humanise(re.sub(r"<[^>]+>", " ", match.group(1)))
            if 2 <= len(name) <= 80:
                return name, "SOURCE_CONFIRMED"
    return _humanise(root.name).title() or "Current Web Product", "AI_INFERRED"


def _product_type(context: Mapping[str, Any], entities: Sequence[Mapping[str, Any]], actions: Sequence[Mapping[str, Any]], sources: Sequence[Mapping[str, Any]]) -> tuple[str, dict[str, int], str]:
    explicit = str(context.get("productType") or "").strip()
    if explicit in {"crm", "saas", "landing", "commerce", "ai-product", "mobile"}:
        return explicit, {explicit: 100}, "USER_CONFIRMED"
    ids = {str(item["id"]) for item in entities}
    action_ids = {str(item["id"]) for item in actions}
    corpus = "\n".join(str(item["lower"]) for item in sources)
    scores = Counter({"saas": 2})
    if "customer-account" in ids:
        scores["crm"] += 8
    if "product-order" in ids:
        scores["commerce"] += 9
    if {"review", "approve", "assign"} & action_ids:
        scores["saas"] += 5
    if {"video-asset", "media-asset", "activity", "reward"} & ids:
        scores["saas"] += 7
    for term in ("hero", "pricing", "testimonial", "contact us", "立即咨询", "产品介绍"):
        if term in corpus:
            scores["landing"] += 2
    for term in ("prompt", "assistant", "llm", "model", "generate", "生成内容"):
        if term in corpus:
            scores["ai-product"] += 2
    for term in ("mobile-first", "bottom-navigation", "safe-area-inset", "pwa", "wechat", "小程序"):
        if term in corpus:
            scores["mobile"] += 2
    winner = max(scores, key=lambda key: (scores[key], key))
    return winner, dict(sorted(scores.items())), "SOURCE_CONFIRMED"


def _product_job(context: Mapping[str, Any], product_type: str, entities: Sequence[Mapping[str, Any]], actions: Sequence[Mapping[str, Any]]) -> tuple[str, str]:
    explicit = context.get("productJob") or context.get("productDescription")
    if explicit:
        return str(explicit).strip(), "USER_CONFIRMED"
    entity_ids = {str(item["id"]) for item in entities}
    action_ids = {str(item["id"]) for item in actions}
    if product_type == "crm":
        return "帮助团队查找客户、理解状态并推进下一步行动的客户运营系统", "AI_INFERRED"
    if product_type == "commerce":
        return "支持用户发现商品、完成交易并追踪订单的商业系统", "AI_INFERRED"
    if product_type == "landing":
        return "用于介绍产品、建立信任并促成咨询或注册的官网", "AI_INFERRED"
    if product_type == "ai-product":
        return "帮助用户发起 AI 任务、评审结果并继续协作的智能产品", "AI_INFERRED"
    if {"video-asset", "media-asset"} & entity_ids and len({"review", "assign", "claim", "download"} & action_ids) >= 2:
        suffix = "与活动激励" if {"activity", "reward"} & entity_ids else ""
        return f"面向多角色的内容素材审核、处理、分发{suffix}系统", "AI_INFERRED"
    labels = [str(item["label"]) for item in entities[:3]]
    operations = [str(item["label"]) for item in sorted(actions, key=lambda item: int(item["flowOrder"]))[:4]]
    if labels and operations:
        return f"围绕{'、'.join(labels)}完成{'、'.join(operations)}的业务系统", "AI_INFERRED"
    return "支持核心用户完成日常业务任务的 Web 系统", "AI_INFERRED"


def _role_map(roles: Sequence[Mapping[str, Any]], actions: Sequence[Mapping[str, Any]], entities: Sequence[Mapping[str, Any]], routes: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    mapped: list[dict[str, Any]] = []
    action_sources = {str(item["id"]): set(item.get("sourceFiles", [])) for item in actions}
    entity_sources = {str(item["id"]): set(item.get("sourceFiles", [])) for item in entities}
    for role in roles:
        sources = set(role.get("sourceFiles", []))
        role_actions = [item for item in actions if sources & action_sources[str(item["id"])]]
        role_entities = [item for item in entities if sources & entity_sources[str(item["id"])]]
        role_routes = [item for item in routes if any(e.get("path") in sources for e in item.get("evidence", []))]
        mapped.append({
            "id": role["id"], "label": role["label"], "evidenceType": role["evidenceType"],
            "confidence": role["confidence"],
            "actions": [item["label"] for item in role_actions[:8]],
            "dataObjects": [item["label"] for item in role_entities[:6]],
            "pages": [item["path"] for item in role_routes[:8]],
            "evidence": role.get("evidence", []),
        })
    return mapped


def _journeys(actions: Sequence[Mapping[str, Any]], states: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(actions, key=lambda item: int(item.get("flowOrder", 999)))
    action_ids = {str(item["id"]) for item in ordered}
    journeys: list[dict[str, Any]] = []
    main = [str(item["label"]) for item in ordered if item["id"] not in {"login", "track", "participate", "reward"}][:9]
    if len(main) >= 2:
        journeys.append({"id": "core-operation", "name": "核心业务闭环", "steps": main, "evidenceType": "SOURCE_CONFIRMED"})
    if {"submit", "review", "reject"}.issubset(action_ids):
        exception = [label for identifier, label in (("submit", "提交"), ("review", "审核"), ("reject", "驳回"), ("revise", "修改并重提"), ("approve", "审核通过")) if identifier in action_ids]
        journeys.append({"id": "review-recovery", "name": "审核与异常恢复", "steps": exception, "evidenceType": "SOURCE_CONFIRMED"})
    if {"participate", "reward"} & action_ids:
        activity = [label for identifier, label in (("search", "发现活动"), ("participate", "参与活动"), ("submit", "提交结果"), ("review", "结果审核"), ("reward", "获得奖励"), ("track", "查看记录")) if identifier in action_ids]
        if len(activity) >= 2:
            journeys.append({"id": "activity-reward", "name": "活动与奖励", "steps": activity, "evidenceType": "SOURCE_CONFIRMED"})
    if not journeys:
        state_labels = [str(item["label"]) for item in states[:6]]
        journeys.append({"id": "state-continuity", "name": "状态连续性", "steps": state_labels or ["进入页面", "理解当前状态", "完成下一步"], "evidenceType": "AI_INFERRED"})
    return journeys[:3]


def _protected_rules(context: Mapping[str, Any], actions: Sequence[Mapping[str, Any]], entities: Sequence[Mapping[str, Any]], sources: Sequence[Mapping[str, Any]]) -> list[str]:
    explicit: list[str] = []
    for key in ("mustPreserve", "protectedMeaning", "protectedRules"):
        value = context.get(key)
        if isinstance(value, list):
            explicit.extend(str(item).strip() for item in value if str(item).strip())
    action_ids = {str(item["id"]) for item in actions}
    action_scores = {str(item["id"]): int(item.get("score", 0)) for item in actions}
    entity_ids = {str(item["id"]) for item in entities}
    corpus = "\n".join(str(item["lower"]) for item in sources)
    inferred: list[str] = []
    if _PERMISSION_CONTEXT.search(corpus):
        inferred.append("角色、权限与数据可见范围")
    if {"approve", "reject"} & action_ids or action_scores.get("review", 0) >= 4:
        inferred.append("审核、批准与驳回规则")
    if "assignment" in entity_ids or action_scores.get("assign", 0) >= 2 or action_scores.get("claim", 0) >= 2:
        inferred.append("分配范围与领取资格")
    if "reward" in entity_ids or "reward" in action_ids:
        inferred.append("活动资格、奖励计算与发放规则")
    if any(term in corpus for term in ("version", "revision", "步骤版本", "素材版本")):
        inferred.append("业务对象与步骤版本")
    if any(term in corpus for term in ("auditlog", "audit_log", "operationlog", "history", "操作记录", "审计日志")):
        inferred.append("操作记录与审计历史")
    return list(dict.fromkeys(explicit + inferred))[:10]


def _questions(
    context: Mapping[str, Any], roles: Sequence[Mapping[str, Any]], actions: Sequence[Mapping[str, Any]],
    entities: Sequence[Mapping[str, Any]], journeys: Sequence[Mapping[str, Any]], confirmation: Mapping[str, Any],
    *, confirmation_trusted: bool = False,
) -> list[dict[str, Any]]:
    action_ids = {str(item["id"]) for item in actions}
    action_scores = {str(item["id"]): int(item.get("score", 0)) for item in actions}
    entity_ids = {str(item["id"]) for item in entities}
    role_options = [{"value": str(item["id"]), "label": str(item["label"])} for item in roles[:3]]
    candidates: list[dict[str, Any]] = []
    if "process" in action_ids and {"video-asset", "media-asset"} & entity_ids and not context.get("processingLocation"):
        candidates.append({
            "id": "processing-location", "question": "素材剪辑或处理主要发生在哪里？",
            "options": [{"value": "inside", "label": "系统内完成"}, {"value": "outside", "label": "外部完成后上传"}, {"value": "hybrid", "label": "两种方式都有"}],
            "currentInference": "hybrid", "changes": ["处理工作台", "进度保存", "版本管理", "测试范围"],
        })
    if "upload" in action_ids and len(roles) >= 2 and not context.get("uploaderRoles"):
        candidates.append({
            "id": "upload-actors", "question": "哪些角色可以上传或提交内容？",
            "options": role_options[:2] + [{"value": "multiple", "label": "多个业务角色"}],
            "currentInference": "multiple", "changes": ["移动上传入口", "权限矩阵", "失败恢复", "角色旅程"],
        })
    if ("reward" in action_ids or "reward" in entity_ids) and not context.get("rewardMode"):
        candidates.append({
            "id": "reward-mode", "question": "奖励如何发放？",
            "options": [{"value": "automatic", "label": "达成条件后自动发放"}, {"value": "manual", "label": "管理员审核后发放"}, {"value": "hybrid", "label": "部分自动、部分人工"}],
            "currentInference": "manual", "changes": ["活动状态", "异常处理", "后台审核", "通知与追踪"],
        })
    approval_signals = {identifier for identifier in ("review", "approve", "reject") if action_scores.get(identifier, 0) >= 2}
    if (len(approval_signals) >= 2 or action_scores.get("review", 0) >= 4) and not context.get("approvalMode"):
        candidates.append({
            "id": "approval-mode", "question": "核心审核是单人一步完成，还是存在多级审批？",
            "options": [{"value": "single", "label": "单人一步审核"}, {"value": "multi", "label": "多级审批"}, {"value": "mixed", "label": "按业务类型变化"}],
            "currentInference": "single", "changes": ["审批导航", "状态解释", "退回路径", "权限验证"],
        })
    if roles and not (context.get("primaryRole") or context.get("userRole")):
        primary_options = list(role_options)
        if len(primary_options) < 2:
            primary_options.extend([
                {"value": "frontline-operator", "label": "一线业务操作人员"},
                {"value": "manager-reviewer", "label": "管理或审核人员"},
            ])
        primary_options = list({item["value"]: item for item in primary_options}.values())[:3]
        candidates.append({
            "id": "primary-role", "question": "本次升级首先要服务哪类用户？",
            "options": primary_options, "currentInference": primary_options[0]["value"],
            "changes": ["首页优先级", "导航", "默认信息密度", "验收旅程"],
        })
    elif not roles and not (context.get("primaryRole") or context.get("userRole")):
        candidates.append({
            "id": "primary-role", "question": "谁最常使用这个系统完成核心任务？",
            "options": [
                {"value": "frontline-operator", "label": "一线业务操作人员"},
                {"value": "manager-reviewer", "label": "管理或审核人员"},
                {"value": "external-user", "label": "客户或外部参与者"},
            ],
            "currentInference": "frontline-operator",
            "changes": ["首页优先级", "导航", "权限假设边界", "验收旅程"],
        })
    if len(journeys) >= 2 and not context.get("primaryTask"):
        options = [{"value": str(item["id"]), "label": str(item["name"])} for item in journeys[:3]]
        candidates.append({
            "id": "priority-journey", "question": "哪条业务流程最值得优先保证？",
            "options": options, "currentInference": options[0]["value"],
            "changes": ["首个改造切片", "候选方案重心", "Browser 验收", "高管摘要"],
        })
    answers = confirmation.get("answers") if isinstance(confirmation.get("answers"), Mapping) else {}
    action = str(confirmation.get("action") or "")
    selected: list[dict[str, Any]] = []
    # Keep every high-impact question in the evidence ledger.  The workbench
    # shows only one round at a time, but silently dropping questions after the
    # first three would make an unresolved business rule look resolved.
    for index, candidate in enumerate(candidates):
        candidate["round"] = index // MAX_QUESTIONS_PER_ROUND + 1
        answer = answers.get(candidate["id"])
        if confirmation_trusted and answer is not None and str(answer).strip():
            candidate["status"] = "USER_CONFIRMED"
            candidate["answer"] = str(answer)
            candidate["evidenceType"] = "USER_CONFIRMED"
        elif answer is not None and str(answer).strip():
            candidate["status"] = "UNTRUSTED_INPUT"
            candidate["answer"] = str(answer)
            candidate["evidenceType"] = "UNKNOWN"
        elif action in {"continue", "continue-with-inference", "edit-one"}:
            candidate["status"] = "UNANSWERED"
            candidate["evidenceType"] = "UNKNOWN"
        else:
            candidate["status"] = "UNANSWERED"
            candidate["evidenceType"] = "UNKNOWN"
        candidate["inferenceEvidenceType"] = "AI_INFERRED"
        selected.append(candidate)
    return selected


def _screenshot_observations(paths: Sequence[str | Path], overlay: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    for index, value in enumerate(paths[:5]):
        source = Path(value).expanduser().resolve()
        result = analyse_screenshot(source, multimodal_overlay=overlay if index == 0 else None)
        summary = result.get("summary") if isinstance(result.get("summary"), Mapping) else {}
        metadata = result.get("designIr", {}).get("metadata", {}) if isinstance(result.get("designIr"), Mapping) else {}
        observations.append({
            "file": source.name, "status": result.get("status"), "evidenceType": "PAGE_OBSERVED",
            "canvas": summary.get("canvas"), "nodeCount": summary.get("nodeCount"),
            "multimodalOverlayUsed": bool(metadata.get("multimodalOverlayUsed")),
            "businessMeaningConfirmed": bool(metadata.get("multimodalOverlayUsed")),
            "limitation": "截图可确认真实构图；没有语义覆盖时不能确认隐藏业务规则。",
        })
    return observations


def _confidence(
    sources: Sequence[Mapping[str, Any]], routes: Sequence[Mapping[str, Any]], roles: Sequence[Mapping[str, Any]],
    actions: Sequence[Mapping[str, Any]], states: Sequence[Mapping[str, Any]], screenshots: Sequence[Mapping[str, Any]],
    context: Mapping[str, Any],
) -> float:
    value = 0.26
    value += min(0.18, len(sources) * 0.006)
    value += min(0.10, len(routes) * 0.014)
    value += min(0.14, len(roles) * 0.035)
    value += min(0.14, len(actions) * 0.014)
    value += min(0.08, len(states) * 0.01)
    value += min(0.05, len(screenshots) * 0.02)
    if context:
        value += 0.04
        supplied = sum(1 for key in ("productName", "productType", "productJob", "productDescription", "primaryTask", "primaryRole", "userRole", "devicePriority") if context.get(key))
        value += min(0.18, supplied * 0.035)
    return round(min(value, 0.95), 3)


def _context_roles(context: Mapping[str, Any]) -> list[dict[str, Any]]:
    values: list[str] = []
    for key in ("roles", "userRoles"):
        raw = context.get(key)
        if isinstance(raw, list):
            values.extend(str(item).strip() for item in raw if str(item).strip())
    for key in ("userRole", "primaryRole"):
        raw = context.get(key)
        if raw and str(raw).strip():
            values.append(str(raw).strip())
    records: list[dict[str, Any]] = []
    for index, label in enumerate(dict.fromkeys(values)):
        identifier = re.sub(r"[^a-z0-9]+", "-", label.casefold()).strip("-") or f"confirmed-role-{index + 1}"
        records.append({
            "id": identifier, "label": label, "score": 100, "confidence": 1.0,
            "evidenceType": "USER_CONFIRMED", "sourceFiles": [],
            "evidence": [{"type": "USER_CONFIRMED", "path": "business-context", "line": 1, "match": label}],
        })
    return records


def _execution_brief(report: Mapping[str, Any]) -> dict[str, Any]:
    questions = [item for item in report.get("questions", []) if isinstance(item, Mapping)]
    return {
        "schemaVersion": "1", "generator": release_identity(), "status": "INTERNAL_EXECUTION_BRIEF_READY",
        "internalOnly": True, "product": report.get("product"), "roles": report.get("rolePermissionMap"),
        "priorityJourneys": report.get("coreJourneys"), "protectedRules": report.get("protectedRules"),
        "devicePriority": report.get("devicePriority"), "businessObjects": report.get("businessObjects"),
        "states": report.get("states"),
        "unconfirmedAssumptions": [item["question"] for item in questions if item.get("status") == "UNANSWERED"],
        "confirmedAnswers": [{"id": item["id"], "answer": item.get("answer"), "evidenceType": item.get("evidenceType")} for item in questions if item.get("answer")],
        "userCorrection": report.get("confirmation", {}).get("corrections") if isinstance(report.get("confirmation"), Mapping) else {},
        "designConstraints": [
            "保留已识别的角色、权限、状态和受保护业务含义",
            "候选方案必须改变信息架构、导航或任务引导，而非只换色",
            "移动优先时不得把桌面布局简单缩小",
            "原项目保持不变，候选仅写入隔离输出",
        ],
        "claimBoundary": "这是内部执行简报，不是要求用户复制的提示词，也不是生产权限或业务规则证明。",
    }


def _test_plan(report: Mapping[str, Any]) -> dict[str, Any]:
    roles = [item for item in report.get("rolePermissionMap", []) if isinstance(item, Mapping)]
    journeys = [item for item in report.get("coreJourneys", []) if isinstance(item, Mapping)]
    mobile_first = str(report.get("devicePriority", "")).startswith("mobile")
    devices = [
        {"id": "mobile", "width": 390}, {"id": "tablet", "width": 768}, {"id": "desktop", "width": 1440}
    ] if mobile_first else [
        {"id": "desktop", "width": 1440}, {"id": "tablet", "width": 768}, {"id": "mobile", "width": 390}
    ]
    scenarios: list[dict[str, Any]] = []
    for index, journey in enumerate(journeys):
        actor = roles[index % len(roles)]["label"] if roles else "核心业务用户"
        scenarios.append({
            "id": f"journey-{index + 1}", "title": journey.get("name"), "actor": actor,
            "steps": journey.get("steps"), "status": "PLANNED_REQUIRES_SAFE_ENV",
            "evidenceRequired": ["SOURCE", "BROWSER", "USER_CONFIRMATION_IF_AMBIGUOUS"],
        })
    for role in roles[:5]:
        scenarios.append({
            "id": f"role-{role['id']}", "title": f"{role['label']}权限与可见范围", "actor": role["label"],
            "steps": ["使用本地或测试账号登录", "核对菜单与数据范围", "验证允许和禁止的操作", "检查跨角色状态连续性"],
            "status": "TEST_ACCOUNT_REQUIRED", "evidenceRequired": ["BROWSER", "USER_CONFIRMED_TEST_ACCOUNT"],
        })
    return {
        "schemaVersion": "1", "generator": release_identity(), "status": "TEST_PLAN_READY",
        "devices": devices, "scenarios": scenarios,
        "states": [item.get("label") for item in report.get("states", []) if isinstance(item, Mapping)],
        "safeExecution": {
            "sourceScan": "READ_ONLY", "productionAccounts": "FORBIDDEN", "mutatingBrowserActions": "NOT_AUTHORIZED",
            "testAccountsRequiredForRoleValidation": bool(roles), "browserUnavailableMeans": "NOT_VERIFIED",
        },
        "claimBoundary": "计划说明应该测试什么；只有在获准的本地、测试或预发布环境实际执行后，才形成 Browser 证据。",
    }


def build_product_discovery(
    project_root: str | Path,
    *,
    business_context: Mapping[str, Any] | None = None,
    screenshot_paths: Sequence[str | Path] = (),
    multimodal_overlay: Mapping[str, Any] | None = None,
    confirmation: Mapping[str, Any] | None = None,
    approval_receipt: TrustedWorkflowApproval | Mapping[str, Any] | None = None,
    model_profile: str | None = None,
) -> dict[str, Any]:
    """Build the product understanding used before diagnosis and design."""
    root = Path(project_root).expanduser().resolve(strict=True)
    context = dict(business_context or {})
    confirmation_value = dict(confirmation or {})
    quick_signature = _quick_scope_signature(root)
    input_signature = _input_signature(context, screenshot_paths, multimodal_overlay)

    # Reuse the canonical, unanswered report in-process.  Answer packets are
    # applied below through the same confirmation ledger, so a cached report
    # can never carry an approval into a new request.
    process_cache_key = (root.as_posix(), quick_signature, input_signature)
    cached_base = _PROCESS_DISCOVERY_CACHE.get(process_cache_key)
    if cached_base is not None:
        if confirmation_value:
            return apply_cached_product_confirmation(
                cached_base,
                confirmation_value,
                approval_receipt=approval_receipt,
                model_profile=model_profile,
            )
        result = copy.deepcopy(cached_base)
        stats = dict(result.get("scanStats") or {})
        stats.update({"cacheHit": True, "canonicalScanCount": 0, "duplicateScanCount": 0})
        result["scanStats"] = stats
        result["cacheReuse"] = {"status": "HIT", "source": "process-local-canonical-scan"}
        result["modelCapabilityProfile"] = model_capability_profile(model_profile)
        return result
    confirmation_validation = validate_confirmation(
        confirmation_value,
        approval=approval_receipt,
        required_scope="UNDERSTANDING",
    ) if confirmation_value else {
        "trusted": False,
        "status": "CURRENT_CONVERSATION_APPROVAL_REQUIRED",
        "reason": "尚未收到当前对话中的用户确认。",
        "scope": "UNDERSTANDING",
    }
    confirmation_trusted = bool(confirmation_validation.get("trusted"))
    sources, scope = _read_sources(root)
    code_sources = [
        item for item in sources
        if Path(str(item["path"])).suffix.casefold() not in {".md", ".css", ".scss", ".less"}
    ]
    scanned_roles = _scan_concepts(code_sources, _ROLES, role_mode=True)
    confirmed_roles = _context_roles(context)
    confirmed_labels = {str(item["label"]).casefold() for item in confirmed_roles}
    roles = confirmed_roles + [item for item in scanned_roles if str(item["label"]).casefold() not in confirmed_labels]
    entities = _scan_concepts(code_sources, _ENTITIES)
    actions = _scan_actions(code_sources)
    states = _scan_concepts(code_sources, _STATES)
    routes = _extract_routes(root, code_sources)
    name, name_evidence = _product_name(root, sources, context)
    product_type, type_scores, type_evidence = _product_type(context, entities, actions, sources)
    job, job_evidence = _product_job(context, product_type, entities, actions)
    corrections = confirmation_value.get("corrections") if isinstance(confirmation_value.get("corrections"), Mapping) else {}
    if corrections.get("productJob"):
        job, job_evidence = str(corrections["productJob"]).strip(), "USER_CONFIRMED"
    role_map = _role_map(roles, actions, entities, routes)
    journeys = _journeys(actions, states)
    screenshots = _screenshot_observations(screenshot_paths, multimodal_overlay)
    questions = _questions(
        context, role_map, actions, entities, journeys, confirmation_value,
        confirmation_trusted=confirmation_trusted,
    )
    primary_question = next((item for item in questions if item.get("id") == "primary-role" and item.get("status") != "UNANSWERED"), None)
    if primary_question:
        selected_role = str(primary_question.get("answer") or primary_question.get("currentInference") or "").strip()
        matching_index = next((index for index, item in enumerate(role_map) if str(item.get("id")) == selected_role), None)
        if matching_index is not None:
            role_map.insert(0, role_map.pop(matching_index))
        elif selected_role:
            selected_label = next(
                (str(item.get("label")) for item in primary_question.get("options", []) if isinstance(item, Mapping) and str(item.get("value")) == selected_role),
                _humanise(selected_role).title(),
            )
            role_evidence = "USER_CONFIRMED" if confirmation_trusted and primary_question.get("status") == "USER_CONFIRMED" else "UNKNOWN"
            resolved_role = {
                "id": selected_role, "label": selected_label, "score": 100 if role_evidence == "USER_CONFIRMED" else 1,
                "confidence": 1.0 if role_evidence == "USER_CONFIRMED" else 0.2,
                "evidenceType": role_evidence, "sourceFiles": [],
                "evidence": [{"type": role_evidence, "path": "product-confirmation" if role_evidence == "USER_CONFIRMED" else "system-inference", "line": 1, "match": selected_role}],
            }
            roles.append(resolved_role)
            role_map = _role_map(roles, actions, entities, routes)
    unanswered = sum(1 for item in questions if item.get("status") == "UNANSWERED")
    untrusted_answers = sum(1 for item in questions if item.get("status") == "UNTRUSTED_INPUT")
    total_rounds = max((int(item.get("round", 1)) for item in questions), default=1)
    active_round = next(
        (int(item.get("round", 1)) for item in questions if item.get("status") in {"UNANSWERED", "UNTRUSTED_INPUT"}),
        1,
    )
    active_questions = [item for item in questions if int(item.get("round", 1)) == active_round]
    deferred_questions = [item for item in questions if int(item.get("round", 1)) > active_round]
    action = str(confirmation_value.get("action") or "")
    if action == "audit-only":
        status = "PRODUCT_DISCOVERY_AUDIT_ONLY"
    elif not confirmation_trusted:
        # A complete-looking scan still needs the operator to verify the
        # model's understanding in the current conversation.  High confidence
        # is evidence quality, not authorization or shared business meaning.
        status = confirmation_validation.get("status") if confirmation_value else "PRODUCT_UNDERSTANDING_REVIEW_REQUIRED"
    else:
        status = "PRODUCT_UNDERSTANDING_REVIEW_REQUIRED" if unanswered else "PRODUCT_UNDERSTANDING_READY"
    device_priority = str(context.get("devicePriority") or "").strip()
    if not device_priority:
        device_priority = "mobile-first" if product_type == "mobile" or any("mobile" in str(item["path"]) for item in routes) else "desktop-first-with-mobile-guardrail"
    confidence = _confidence(sources, routes, roles, actions, states, screenshots, context)
    evidence_types = {
        "SOURCE_CONFIRMED": sum(1 for group in (roles, entities, actions, states) for item in group if item.get("evidenceType") == "SOURCE_CONFIRMED"),
        "PAGE_OBSERVED": sum(1 for item in screenshots if str(item.get("status") or "").upper() in {"PASS", "READY", "OBSERVED"}),
        "AI_INFERRED": sum(1 for value in (name_evidence, type_evidence, job_evidence) if value == "AI_INFERRED"),
        "USER_CONFIRMED": sum(1 for value in (name_evidence, type_evidence, job_evidence) if value == "USER_CONFIRMED") + sum(1 for item in questions if item.get("status") == "USER_CONFIRMED") + (1 if corrections and confirmation_trusted else 0),
        "PACKAGE_VERIFIED": 0,
        "RUNTIME_OBSERVED": 0,
        "UNKNOWN": unanswered + untrusted_answers,
        "CONFLICTED": sum(1 for item in questions if item.get("status") == "CONFLICTED"),
        "NOT_VERIFIED": sum(1 for item in screenshots if str(item.get("status") or "").upper() not in {"PASS", "READY", "OBSERVED"}),
        "SYNTHETIC_HYPOTHESIS": 0,
    }
    ledger = confirmation_ledger(questions, confirmation_validation)
    material_unknowns = [
        item for item in ledger
        if item.get("evidenceType") in {"UNKNOWN", "CONFLICTED"} or item.get("status") in {"UNANSWERED", "UNTRUSTED_INPUT"}
    ]
    scope_incomplete = bool(scope.get("budgetExceeded"))
    if scope_incomplete:
        material_unknowns.append({
            "id": "discovery-scope-budget",
            "question": "当前源码范围超过一次安全只读扫描的预算，是否要先缩小或分批提供范围？",
            "status": "UNVERIFIED_SCOPE",
            "evidenceType": "UNKNOWN",
            "currentInference": None,
            "answer": None,
            "impact": ["整体业务逻辑", "权限与状态完整性", "诊断可信度"],
            "owner": "current-conversation-user",
        })
        status = "DISCOVERY_SCOPE_INCOMPLETE"
    profile = model_capability_profile(model_profile)
    if material_unknowns:
        confidence_label = "暂定"
    else:
        confidence_label = "高" if confidence >= 0.82 else "中" if confidence >= 0.58 else "低"
    report: dict[str, Any] = {
        "schemaVersion": "2", "generator": release_identity(), "status": status,
        "product": {"name": name, "type": product_type, "job": job, "nameEvidence": name_evidence, "typeEvidence": type_evidence, "jobEvidence": job_evidence, "classificationScores": type_scores},
        "framework": detect_framework(root), "devicePriority": device_priority,
        "confidence": {"score": confidence, "percent": round(confidence * 100), "label": confidence_label, "decisionReady": not material_unknowns and confirmation_trusted},
        "rolePermissionMap": role_map, "routes": routes,
        "businessObjects": [{key: item[key] for key in ("id", "label", "confidence", "evidenceType", "evidence")} for item in entities[:12]],
        "operations": [{key: item[key] for key in ("id", "label", "flowOrder", "confidence", "evidenceType", "evidence")} for item in actions[:16]],
        "states": [{key: item[key] for key in ("id", "label", "confidence", "evidenceType", "evidence")} for item in states[:16]],
        "coreJourneys": journeys, "protectedRules": _protected_rules(context, actions, entities, sources),
        "screenshotObservations": screenshots, "questions": questions,
        "questionPolicy": {
            "maximumPerRound": MAX_QUESTIONS_PER_ROUND,
            "roundsByDefault": total_rounds,
            "activeRound": active_round,
            "totalHighImpactQuestions": len(questions),
            "visibleQuestionIds": [str(item.get("id")) for item in active_questions],
            "deferredQuestionIds": [str(item.get("id")) for item in deferred_questions],
            "roundComplete": not any(item.get("status") in {"UNANSWERED", "UNTRUSTED_INPUT"} for item in active_questions),
            "nextRound": active_round + 1 if deferred_questions else None,
            "unanswered": unanswered,
            "untrustedAnswers": untrusted_answers,
            "scopeIncomplete": scope_incomplete,
            "mayProceedWithInference": False,
        },
        "evidenceSummary": evidence_types, "evidenceClasses": list(EVIDENCE_CLASSES), "scopeHygiene": scope,
        "confirmation": {
            "action": action or None,
            "corrections": corrections if confirmation_trusted else {},
            "allHighImpactQuestionsResolved": unanswered == 0 and untrusted_answers == 0,
            "validation": confirmation_validation,
            "ledger": ledger,
        },
        "materialUnknowns": material_unknowns,
        "recommendedMode": "diagnose" if len(role_map) < 3 else "diagnose",
        "workflowState": "AWAITING_USER_CONFIRMATION" if status != "PRODUCT_UNDERSTANDING_READY" else "DIAGNOSIS",
        "modelCapabilityProfile": profile,
        "syntheticEvidencePolicy": {
            "acceptedClasses": list(EVIDENCE_CLASSES),
            "syntheticDataMayGuideTests": True,
            "syntheticDataMayAuthorizeWork": False,
            "syntheticDataMayAppearAsUserFeedback": False,
        },
        "scanStats": {
            "canonicalScanId": scope.get("canonicalScan", {}).get("id"),
            "cacheHit": False,
            "canonicalScanCount": 1,
            "duplicateScanCount": 0,
            "inputSignature": input_signature,
        },
        "sourceProjectChanged": False,
        "claimBoundary": "源码确认系统可能如何工作，页面观察确认用户实际看见什么；AI 推断、未知项、合成研究和未验证环境不会被冒充为真实权限、用户反馈或生产验证。",
    }
    report["executionBrief"] = _execution_brief(report)
    report["testPlan"] = _test_plan(report)
    if not confirmation_value:
        _PROCESS_DISCOVERY_CACHE[process_cache_key] = copy.deepcopy(report)
        while len(_PROCESS_DISCOVERY_CACHE) > _PROCESS_DISCOVERY_CACHE_LIMIT:
            _PROCESS_DISCOVERY_CACHE.pop(next(iter(_PROCESS_DISCOVERY_CACHE)))
    return report


def discovery_business_context(report: Mapping[str, Any]) -> dict[str, Any]:
    product = report.get("product") if isinstance(report.get("product"), Mapping) else {}
    roles = [item for item in report.get("rolePermissionMap", []) if isinstance(item, Mapping)]
    journeys = [item for item in report.get("coreJourneys", []) if isinstance(item, Mapping)]
    primary_steps = journeys[0].get("steps", []) if journeys else []
    return {
        "productName": product.get("name"), "productType": product.get("type"),
        "primaryRole": roles[0].get("label") if roles else None,
        "primaryTask": " → ".join(str(item) for item in primary_steps) if primary_steps else None,
        "devicePriority": report.get("devicePriority"),
        "entities": [item.get("label") for item in report.get("businessObjects", []) if isinstance(item, Mapping)],
        "operations": [item.get("label") for item in report.get("operations", []) if isinstance(item, Mapping)],
        "states": [item.get("label") for item in report.get("states", []) if isinstance(item, Mapping)],
        "mustPreserve": list(report.get("protectedRules", [])),
    }


def load_cached_product_discovery(
    project_root: str | Path,
    output_dir: str | Path,
    *,
    business_context: Mapping[str, Any] | None = None,
    screenshot_paths: Sequence[str | Path] = (),
    multimodal_overlay: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Reuse an unchanged understanding scan during a conversational resume.

    Only the cheap path/size/mtime signature is used to decide whether the
    cache can be read.  A changed signature invalidates the understanding and
    forces a fresh read-only scan and a new confirmation round.
    """
    root = Path(project_root).expanduser().resolve(strict=True)
    output = Path(output_dir).expanduser().resolve()
    report_path = output / "system-understanding" / "system-understanding.json"
    if not report_path.is_file():
        return None
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(report, Mapping):
        return None
    if report.get("sourceProjectChanged") is not False or list(report.get("evidenceClasses") or []) != list(EVIDENCE_CLASSES):
        return None
    stored = report.get("scopeHygiene") if isinstance(report.get("scopeHygiene"), Mapping) else {}
    canonical = stored.get("canonicalScan") if isinstance(stored.get("canonicalScan"), Mapping) else {}
    expected = str(canonical.get("quickSignature") or "")
    if not expected or expected != _quick_scope_signature(root):
        return None
    expected_input = str((report.get("scanStats") or {}).get("inputSignature") or "")
    if expected_input and expected_input != _input_signature(business_context, screenshot_paths, multimodal_overlay):
        return None
    result = dict(report)
    for name, key in (("execution-brief.json", "executionBrief"), ("test-plan.json", "testPlan")):
        path = output / "system-understanding" / name
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            loaded = None
        if isinstance(loaded, Mapping):
            result[key] = dict(loaded)
    stats = dict(result.get("scanStats") or {})
    stats.update({
        "canonicalScanId": canonical.get("id"),
        "cacheHit": True,
        "canonicalScanCount": 0,
        "duplicateScanCount": 0,
    })
    result["scanStats"] = stats
    result["workflowState"] = "AWAITING_USER_CONFIRMATION" if result.get("status") != "PRODUCT_UNDERSTANDING_READY" else "DIAGNOSIS"
    result["cacheReuse"] = {"status": "HIT", "source": "system-understanding.json"}
    return result


def apply_cached_product_confirmation(
    cached_report: Mapping[str, Any],
    confirmation: Mapping[str, Any],
    *,
    approval_receipt: TrustedWorkflowApproval | Mapping[str, Any] | None = None,
    model_profile: str | None = None,
) -> dict[str, Any]:
    """Apply a new answer round without rereading an unchanged source tree.

    The source-derived question set is already present in the cache.  This
    helper updates only the answer/evidence ledger and regenerated handoff
    artifacts, so a multi-round conversation does not make the model or plugin
    repeat the canonical token-heavy reconstruction.
    """
    result = copy.deepcopy(dict(cached_report))
    confirmation_value = dict(confirmation or {})
    validation = validate_confirmation(
        confirmation_value,
        approval=approval_receipt,
        required_scope="UNDERSTANDING",
    ) if confirmation_value else {
        "trusted": False,
        "status": "CURRENT_CONVERSATION_APPROVAL_REQUIRED",
        "reason": "尚未收到当前对话中的用户确认。",
        "scope": "UNDERSTANDING",
    }
    trusted = bool(validation.get("trusted"))
    answers = confirmation_value.get("answers") if isinstance(confirmation_value.get("answers"), Mapping) else {}
    questions = [item for item in result.get("questions", []) if isinstance(item, Mapping)]
    updated_questions: list[dict[str, Any]] = []
    for raw in questions:
        item = dict(raw)
        answer = answers.get(str(item.get("id")))
        if answer is not None and str(answer).strip():
            item["answer"] = str(answer)
            if trusted:
                item["status"] = "USER_CONFIRMED"
                item["evidenceType"] = "USER_CONFIRMED"
            else:
                item["status"] = "UNTRUSTED_INPUT"
                item["evidenceType"] = "UNKNOWN"
        elif item.get("status") in {"USER_CONFIRMED", "INFERENCE_ACCEPTED"} and not trusted:
            item["status"] = "UNTRUSTED_INPUT"
            item["evidenceType"] = "UNKNOWN"
        updated_questions.append(item)
    result["questions"] = updated_questions
    unanswered = sum(1 for item in updated_questions if item.get("status") == "UNANSWERED")
    untrusted_answers = sum(1 for item in updated_questions if item.get("status") == "UNTRUSTED_INPUT")
    total_rounds = max((int(item.get("round", 1)) for item in updated_questions), default=1)
    active_round = next(
        (int(item.get("round", 1)) for item in updated_questions if item.get("status") in {"UNANSWERED", "UNTRUSTED_INPUT"}),
        total_rounds,
    )
    active_questions = [item for item in updated_questions if int(item.get("round", 1)) == active_round]
    deferred_questions = [item for item in updated_questions if int(item.get("round", 1)) > active_round]
    action = str(confirmation_value.get("action") or "").strip().casefold()
    if action == "audit-only":
        status = "PRODUCT_DISCOVERY_AUDIT_ONLY"
    elif not trusted:
        status = str(validation.get("status") or "CURRENT_CONVERSATION_APPROVAL_REQUIRED")
    else:
        status = "PRODUCT_UNDERSTANDING_REVIEW_REQUIRED" if (unanswered or untrusted_answers) else "PRODUCT_UNDERSTANDING_READY"
    if bool((result.get("questionPolicy") or {}).get("scopeIncomplete")):
        status = "DISCOVERY_SCOPE_INCOMPLETE"
    old_policy = result.get("questionPolicy") if isinstance(result.get("questionPolicy"), Mapping) else {}
    result["questionPolicy"] = {
        **dict(old_policy),
        "maximumPerRound": MAX_QUESTIONS_PER_ROUND,
        "roundsByDefault": total_rounds,
        "activeRound": active_round,
        "totalHighImpactQuestions": len(updated_questions),
        "visibleQuestionIds": [str(item.get("id")) for item in active_questions],
        "deferredQuestionIds": [str(item.get("id")) for item in deferred_questions],
        "roundComplete": not any(item.get("status") in {"UNANSWERED", "UNTRUSTED_INPUT"} for item in active_questions),
        "nextRound": active_round + 1 if deferred_questions else None,
        "unanswered": unanswered,
        "untrustedAnswers": untrusted_answers,
        "mayProceedWithInference": False,
    }
    ledger = confirmation_ledger(updated_questions, validation)
    material_unknowns = [
        item for item in ledger
        if item.get("evidenceType") in {"UNKNOWN", "CONFLICTED"} or item.get("status") in {"UNANSWERED", "UNTRUSTED_INPUT"}
    ]
    if bool((result.get("questionPolicy") or {}).get("scopeIncomplete")):
        material_unknowns.append({
            "id": "discovery-scope-budget",
            "question": "当前源码范围超过一次安全只读扫描的预算，是否要先缩小或分批提供范围？",
            "status": "UNVERIFIED_SCOPE",
            "evidenceType": "UNKNOWN",
            "currentInference": None,
            "answer": None,
            "impact": ["整体业务逻辑", "权限与状态完整性", "诊断可信度"],
            "owner": "current-conversation-user",
        })
    result["status"] = status
    result["materialUnknowns"] = material_unknowns
    result["confirmation"] = {
        "action": action or None,
        "corrections": confirmation_value.get("corrections") if trusted and isinstance(confirmation_value.get("corrections"), Mapping) else {},
        "allHighImpactQuestionsResolved": unanswered == 0 and untrusted_answers == 0,
        "validation": validation,
        "ledger": ledger,
    }
    confidence = dict(result.get("confidence") or {})
    confidence["decisionReady"] = not material_unknowns and trusted
    confidence["label"] = "暂定" if material_unknowns else confidence.get("label", "中")
    result["confidence"] = confidence
    base_evidence = dict(result.get("evidenceSummary") or {})
    prior_user_count = sum(1 for item in questions if item.get("status") == "USER_CONFIRMED")
    base_evidence["USER_CONFIRMED"] = max(0, int(base_evidence.get("USER_CONFIRMED", 0)) - prior_user_count) + sum(1 for item in updated_questions if item.get("status") == "USER_CONFIRMED")
    base_evidence["UNKNOWN"] = unanswered + untrusted_answers + (1 if bool((result.get("questionPolicy") or {}).get("scopeIncomplete")) else 0)
    base_evidence["CONFLICTED"] = sum(1 for item in updated_questions if item.get("status") == "CONFLICTED")
    result["evidenceSummary"] = base_evidence
    result["workflowState"] = "DIAGNOSIS" if status == "PRODUCT_UNDERSTANDING_READY" else "AWAITING_USER_CONFIRMATION"
    result["modelCapabilityProfile"] = model_capability_profile(model_profile)
    result["executionBrief"] = _execution_brief(result)
    result["testPlan"] = _test_plan(result)
    stats = dict(result.get("scanStats") or {})
    stats.update({"cacheHit": True, "canonicalScanCount": 0, "duplicateScanCount": 0})
    result["scanStats"] = stats
    result["cacheReuse"] = {"status": "HIT", "source": "system-understanding.json", "answerRoundOnly": True}
    return result


def _understanding_html(report: Mapping[str, Any]) -> str:
    product = report.get("product") if isinstance(report.get("product"), Mapping) else {}
    confidence = report.get("confidence") if isinstance(report.get("confidence"), Mapping) else {}
    roles = [item for item in report.get("rolePermissionMap", []) if isinstance(item, Mapping)]
    journeys = [item for item in report.get("coreJourneys", []) if isinstance(item, Mapping)]
    questions = [item for item in report.get("questions", []) if isinstance(item, Mapping)]
    policy = report.get("questionPolicy") if isinstance(report.get("questionPolicy"), Mapping) else {}
    active_round = int(policy.get("activeRound") or 1)
    visible_questions = [item for item in questions if int(item.get("round", 1)) == active_round]
    deferred_questions = [item for item in questions if int(item.get("round", 1)) > active_round]
    role_html = "".join(f'<span class="chip">{escape(str(item.get("label")))}</span>' for item in roles) or '<span class="chip muted">尚未从源码确认具体角色</span>'
    flow_html = "".join(
        f'<article class="flow"><b>{escape(str(item.get("name")))}</b><p>{" <i>→</i> ".join(escape(str(step)) for step in item.get("steps", []))}</p></article>'
        for item in journeys
    )
    question_html = "".join(
        '<fieldset data-question="{id}"><legend>{index}. {question}</legend><p>{changes}</p><div class="options">{options}</div></fieldset>'.format(
            id=escape(str(item.get("id"))), index=index + 1, question=escape(str(item.get("question"))),
            changes=escape("会影响：" + "、".join(str(value) for value in item.get("changes", []))),
            options="".join(
                f'<label><input type="radio" name="{escape(str(item.get("id")))}" value="{escape(str(option.get("value")))}"><span>{escape(str(option.get("label")))}</span></label>'
                for option in item.get("options", []) if isinstance(option, Mapping)
            ),
        ) for index, item in enumerate(visible_questions)
    ) or '<p class="resolved">源码与已提供信息足以开始；目前没有会实质改变方案的必答问题。</p>'
    evidence = report.get("evidenceSummary") if isinstance(report.get("evidenceSummary"), Mapping) else {}
    evidence_html = "".join(f'<li><span>{escape(label)}</span><b>{int(evidence.get(key, 0))}</b></li>' for key, label in (
        ("SOURCE_CONFIRMED", "源码确认"), ("PAGE_OBSERVED", "页面观察"), ("AI_INFERRED", "AI 推断"),
        ("USER_CONFIRMED", "用户确认"), ("UNKNOWN", "未知待确认"), ("CONFLICTED", "存在冲突"),
    ))
    question_ids = [str(item.get("id")) for item in visible_questions]
    all_question_ids = [str(item.get("id")) for item in questions]
    deferred_question_ids = [str(item.get("id")) for item in deferred_questions]
    prior_answers = {
        str(item.get("id")): str(item.get("answer"))
        for item in questions
        if item.get("answer") and item.get("status") == "USER_CONFIRMED"
    }
    deferred_html = (
        f'<p class="notice">本轮最多确认 {MAX_QUESTIONS_PER_ROUND} 项；还有 {len(deferred_questions)} 项会在本轮回答后显示。所有高影响问题都确认后才会进入下一阶段。</p>'
        if deferred_questions else ""
    )
    if deferred_questions:
        deferred_html += '<p class="notice">完成全部轮次后，主按钮会变为“已核对，交给当前对话确认”。</p>'
    scope_warning_html = (
        '<p class="notice" style="background:#fff4d6;color:#7a5710">当前安全扫描范围未覆盖全部候选源码；诊断会暂停，直到范围缩小或补充分批扫描。不要把未读取的业务规则当作已理解。</p>'
        if bool((policy.get("scopeIncomplete"))) else ""
    )
    primary_action_label = "保存本轮，继续确认" if deferred_questions else "已核对，交给当前对话确认"
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(str(product.get('name')))} · 系统理解</title><style>
:root{{--ink:#17211c;--muted:#637168;--paper:#eef3f0;--surface:#fff;--line:#d7e1db;--brand:#116b4d;--soft:#dff3e9;--dark:#0d281e;font-family:Inter,"Segoe UI","PingFang SC",sans-serif}}*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink)}}button,input,textarea{{font:inherit}}main{{max-width:1180px;margin:auto;padding:24px 16px 120px}}.hero{{padding:clamp(28px,6vw,64px);border-radius:30px;background:radial-gradient(circle at 90% 0,#2d8c6a66,transparent 36%),var(--dark);color:#fff}}.eyebrow{{color:#9ed5bf;font-size:12px;letter-spacing:.14em;text-transform:uppercase}}h1{{margin:14px 0 10px;font-size:clamp(40px,7vw,78px);line-height:.95;letter-spacing:-.06em}}.job{{max-width:850px;color:#c5d7cf;font-size:18px;line-height:1.65}}.confidence{{display:flex;flex-wrap:wrap;gap:10px;margin-top:22px}}.confidence span{{padding:9px 12px;border:1px solid #ffffff26;border-radius:99px;background:#ffffff0d}}.grid{{display:grid;grid-template-columns:1.15fr .85fr;gap:16px;margin-top:16px}}section{{padding:24px;border:1px solid var(--line);border-radius:22px;background:var(--surface)}}h2{{margin:0 0 14px;font-size:24px;letter-spacing:-.03em}}.chips{{display:flex;flex-wrap:wrap;gap:8px}}.chip{{padding:8px 10px;border-radius:99px;background:var(--soft);color:var(--brand);font-weight:750;font-size:12px}}.chip.muted{{background:#edf1ef;color:var(--muted)}}.flow{{padding:14px;border-radius:15px;background:#f5f8f6;margin-top:9px}}.flow p{{margin:7px 0 0;color:var(--muted);line-height:1.7}}.flow i{{padding:0 5px;color:var(--brand);font-style:normal}}.evidence{{list-style:none;padding:0;margin:0}}.evidence li{{display:flex;justify-content:space-between;padding:10px 0;border-bottom:1px solid var(--line)}}.evidence span{{color:var(--muted)}}.questions{{margin-top:16px}}fieldset{{margin:12px 0;padding:18px;border:1px solid var(--line);border-radius:17px}}legend{{padding:0 7px;font-weight:850}}fieldset>p{{color:var(--muted);font-size:12px}}.options{{display:flex;flex-wrap:wrap;gap:8px}}.options label{{position:relative}}.options input{{position:absolute;opacity:0}}.options span{{display:block;padding:10px 12px;border:1px solid var(--line);border-radius:11px;cursor:pointer}}.options input:checked+span{{border-color:var(--brand);background:var(--soft);color:var(--brand)}}.resolved{{padding:16px;border-radius:14px;background:var(--soft);color:var(--brand)}}.correction{{display:none;margin-top:14px}}.correction.open{{display:grid;gap:8px}}textarea{{width:100%;min-height:90px;padding:12px;border:1px solid var(--line);border-radius:12px;resize:vertical}}.actions{{position:fixed;left:50%;bottom:16px;translate:-50% 0;width:min(900px,calc(100% - 24px));display:flex;gap:9px;padding:12px;border-radius:18px;background:#10251df2;box-shadow:0 24px 70px #0004;backdrop-filter:blur(16px)}}.actions button{{flex:1;min-height:48px;border:1px solid #ffffff24;border-radius:11px;background:transparent;color:#fff;font-weight:800;cursor:pointer}}.actions .primary{{background:#d3f3e2;color:#0e583f}}.notice{{color:var(--muted);line-height:1.6;font-size:13px}}@media(max-width:760px){{.grid{{grid-template-columns:1fr}}.actions{{display:grid;grid-template-columns:1fr 1fr}}.actions .primary{{grid-column:1/-1;grid-row:1}}}}@media(prefers-reduced-motion:reduce){{*{{scroll-behavior:auto!important}}}}
</style></head><body><main><header class="hero"><span class="eyebrow">Web UI Quality {escape(str(report.get('generator', {}).get('version', '')))} · 智能系统理解</span><h1>我理解这是……</h1><p class="job">{escape(str(product.get('job')))}</p><div class="confidence"><span>{escape(str(product.get('name')))}</span><span>{escape(str(product.get('type')))}</span><span>识别置信度 {escape(str(confidence.get('percent')))}% · {escape(str(confidence.get('label')))}</span><span>{escape(str(report.get('devicePriority')))}</span></div></header>{scope_warning_html}<div class="grid"><section><h2>已识别的应用角色</h2><div class="chips">{role_html}</div><p class="notice">这里只表示应用权限角色，不等同于企业真实组织架构。</p><h2>核心业务闭环</h2>{flow_html}</section><section><h2>证据状态</h2><ul class="evidence">{evidence_html}</ul><p class="notice">源码确认系统可能如何工作；页面观察确认真实构图；AI 推断仍可修正；未知项不会被当作事实。下载的回答文件本身也不构成授权。</p><a href="system-understanding.json">查看完整理解与证据 →</a></section></div><section class="questions"><h2>只确认会改变方案的地方（第 {active_round} 轮）</h2>{question_html}{deferred_html}<div class="correction" id="correction"><label for="correction-text">只写需要修正的那一处</label><textarea id="correction-text" placeholder="例如：剪辑不在系统内完成，而是外部完成后上传。"></textarea></div><p id="message" class="notice" role="status"></p></section></main><div class="actions"><button class="primary" data-action="confirm-understanding">{escape(primary_action_label)}</button><button data-action="edit-one">修改一处</button><button data-action="audit-only">暂时只看检测结果</button></div><script>
const questionIds={json.dumps(question_ids, ensure_ascii=False)};const allQuestionIds={json.dumps(all_question_ids, ensure_ascii=False)};const priorAnswers={json.dumps(prior_answers, ensure_ascii=False)};const correction=document.getElementById('correction');const message=document.getElementById('message');let editOpen=false;function selection(){{const current=Object.fromEntries(questionIds.map(id=>{{const field=document.querySelector(`input[name="${{id}}"]:checked`);return [id,field?field.value:null]}}).filter(([,value])=>value));return Object.assign({{}},priorAnswers,current)}}function download(action){{const answers=selection();if(action==='confirm-understanding'&&allQuestionIds.some(id=>!answers[id])){{message.textContent='请先回答当前及后续每个高影响问题；不能用“一律继续”替代确认。';return}}if(action==='edit-one'&&!document.getElementById('correction-text').value.trim()){{message.textContent='请写下需要修正的具体内容。';return}}const note=document.getElementById('correction-text').value.trim();const value={{schemaVersion:'2',action,answers,corrections:note?{{note}}:{{}},source:'system-understanding-response',requiresCurrentConversationApproval:true,approvalReceipt:null}};const blob=new Blob([JSON.stringify(value,null,2)+'\\n'],{{type:'application/json'}});const link=document.createElement('a');link.href=URL.createObjectURL(blob);link.download='product-confirmation.json';link.click();setTimeout(()=>URL.revokeObjectURL(link.href),1000);message.textContent='回答已准备；还需要当前对话中的用户确认，文件本身不会触发升级。'}}document.querySelectorAll('[data-action]').forEach(button=>button.addEventListener('click',()=>{{const action=button.dataset.action;if(action==='edit-one'&&!editOpen){{editOpen=true;correction.classList.add('open');document.getElementById('correction-text').focus();button.textContent='保存这处修正';return}}download(action)}}));
</script><script>
// Replace the primary handler so deferred rounds can be saved without asking
// the user to answer invisible questions. The original project is untouched;
// this only controls the response packet workbench.
(()=>{{
  const primary=document.querySelector('[data-action="confirm-understanding"]');
  if(!primary) return;
  const replacement=primary.cloneNode(true); primary.replaceWith(replacement);
  const questionIds={json.dumps(question_ids, ensure_ascii=False)};
  const deferredQuestionIds={json.dumps(deferred_question_ids, ensure_ascii=False)};
  const priorAnswers={json.dumps(prior_answers, ensure_ascii=False)};
  const message=document.getElementById('message');
  replacement.addEventListener('click',()=>{{
    const current=Object.fromEntries(questionIds.map(id=>{{const field=document.querySelector(`input[name="${{id}}"]:checked`);return [id,field?field.value:null]}}).filter(([,value])=>value));
    const answers=Object.assign({{}},priorAnswers,current);
    if(questionIds.some(id=>!answers[id])){{message.textContent='请先回答本轮每个高影响问题。';return;}}
    const action=deferredQuestionIds.length?'continue-round':'confirm-understanding';
    const note=(document.getElementById('correction-text')?.value||'').trim();
    const value={{schemaVersion:'2',action,answers,corrections:note?{{note}}:{{}},source:'system-understanding-response',requiresCurrentConversationApproval:true,approvalReceipt:null}};
    const blob=new Blob([JSON.stringify(value,null,2)+'\\n'],{{type:'application/json'}});
    const link=document.createElement('a');link.href=URL.createObjectURL(blob);link.download='product-confirmation.json';link.click();setTimeout(()=>URL.revokeObjectURL(link.href),1000);
    message.textContent=deferredQuestionIds.length?'本轮回答已准备；交给当前对话后会显示下一轮。':'回答已准备；还需要当前对话中的用户确认，文件本身不会触发升级。';
  }});
}})();
</script></body></html>"""


def export_product_discovery(report: Mapping[str, Any], output_dir: str | Path) -> dict[str, str]:
    output = Path(output_dir).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    report_value = dict(report)
    brief = report_value.pop("executionBrief", {})
    test_plan = report_value.pop("testPlan", {})
    (output / "system-understanding.json").write_text(json.dumps(report_value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output / "execution-brief.json").write_text(json.dumps(brief, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output / "test-plan.json").write_text(json.dumps(test_plan, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    scope = report_value.get("scopeHygiene") if isinstance(report_value.get("scopeHygiene"), Mapping) else {}
    canonical = scope.get("canonicalScan") if isinstance(scope.get("canonicalScan"), Mapping) else {}
    (output / "scan-cache.json").write_text(json.dumps({
        "schemaVersion": "1",
        "policy": "reuse-only-when-quick-signature-matches",
        "canonicalScan": canonical,
        "inputSignature": (report_value.get("scanStats") or {}).get("inputSignature"),
        "sourceProjectChanged": False,
        "claimBoundary": "缓存只复用未变化的只读理解扫描；它不授予用户确认或写入权限。",
    }, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output / "index.html").write_text(_understanding_html(report), encoding="utf-8")
    return {
        "understanding": "system-understanding.json", "workbench": "index.html", "scanCache": "scan-cache.json",
        "executionBrief": "execution-brief.json", "testPlan": "test-plan.json",
    }
