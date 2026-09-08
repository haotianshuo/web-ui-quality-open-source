"""Unified page understanding for source, screenshot, and rendered evidence.

This sidecar model classifies the product surface, inventories visible component
roles, and keeps provenance per dimension.  Low evidence remains unclassified
instead of being forced into the alphabetically first catalog entry.
"""
from __future__ import annotations

from collections import Counter
import re
from typing import Any, Mapping, Sequence

from .contracts import digest_json


_PAGE_TYPES: tuple[dict[str, Any], ...] = (
    {
        "id": "saas-dashboard",
        "label": "SaaS Dashboard",
        "keywords": ("dashboard", "overview", "analytics", "metric", "kpi", "chart", "insight", "总览", "概览", "指标", "趋势", "告警", "看板"),
        "task": "查看关键状态、发现异常并进入下一步处理",
    },
    {
        "id": "crm",
        "label": "CRM",
        "keywords": ("crm", "customer", "contact", "lead", "opportunity", "pipeline", "account", "客户", "联系人", "线索", "商机", "跟进", "销售"),
        "task": "查找客户、缩小范围并连续处理记录",
    },
    {
        "id": "erp",
        "label": "ERP / Operations",
        "keywords": ("erp", "inventory", "warehouse", "procurement", "manufacturing", "material", "purchase order", "stock", "库存", "仓库", "采购", "生产", "物料", "工单", "盘点"),
        "task": "核对高密度业务数据并安全完成批量或流程操作",
    },
    {
        "id": "landing-page",
        "label": "Landing Page",
        "keywords": ("hero", "pricing", "testimonial", "features", "get started", "start free", "book a demo", "landing", "首屏", "核心卖点", "立即体验", "免费试用", "预约演示"),
        "task": "快速理解价值、建立信任并选择下一步",
    },
    {
        "id": "ecommerce",
        "label": "E-commerce",
        "keywords": ("product", "cart", "checkout", "buy now", "price", "compare", "sku", "商品", "购物车", "结算", "购买", "价格", "参数", "规格"),
        "task": "理解商品、比较配置并完成购买决策",
    },
    {
        "id": "ai-product",
        "label": "AI Product",
        "keywords": ("ai assistant", "copilot", "prompt", "generate", "generation", "model", "conversation", "assistant", "人工智能", "智能助手", "提示词", "生成", "模型", "对话"),
        "task": "表达意图、等待生成、审阅结果并安全应用",
    },
    {
        "id": "mobile-workflow",
        "label": "Mobile Workflow",
        "keywords": ("mobile workflow", "mobile-workflow", "field", "scan", "offline", "bottom-nav", "bottom action", "safe-area", "现场", "扫码", "离线", "底部操作", "移动任务"),
        "task": "在移动环境中用单手完成一个清晰任务并可靠恢复",
    },
    {
        "id": "workflow",
        "label": "Workflow / Approval",
        "keywords": ("workflow", "approval", "stepper", "review", "status transition", "流程", "审批", "步骤", "状态流转"),
        "task": "理解当前阶段、完成允许操作并确认结果",
    },
    {
        "id": "content-feed",
        "label": "Content Feed",
        "keywords": ("feed", "recommend", "following", "for you", "信息流", "推荐", "关注"),
        "task": "浏览相关内容并用反馈校正后续内容",
    },
)

_COMPONENT_PATTERNS: tuple[tuple[str, str], ...] = (
    ("button", r"(?i)<button\b|role\s*=\s*['\"]button"),
    ("form", r"(?i)<form\b"),
    ("input", r"(?i)<(?:input|textarea|select)\b"),
    ("table", r"(?i)<table\b|role\s*=\s*['\"](?:grid|table)"),
    ("modal", r"(?i)<dialog\b|aria-modal\s*=\s*['\"]true|class\s*=\s*['\"][^'\"]*(?:modal|dialog)"),
    ("navigation", r"(?i)<nav\b|role\s*=\s*['\"]navigation"),
    ("card", r"(?i)class\s*=\s*['\"][^'\"]*\bcard\b"),
    ("tabs", r"(?i)role\s*=\s*['\"]tab(?:list)?|class\s*=\s*['\"][^'\"]*\btabs?\b"),
    ("filter", r"(?i)\bfilter(?:s|ing)?\b|筛选|过滤"),
    ("search", r"(?i)type\s*=\s*(?:['\"]search['\"]|search\b)|role\s*=\s*(?:['\"]search['\"]|search\b)|aria-label\s*=\s*['\"][^'\"]*(?:search|搜索)"),
    ("drawer", r"(?i)\b(?:drawer|side[-_ ]?panel|detail[-_ ]?pane)\b|详情抽屉"),
    ("kpi", r"(?i)\b(?:kpi|metric|statistic)\b|关键指标"),
    ("chart", r"(?i)<(?:canvas|svg)\b|\b(?:chart|graph|plot)\b|图表|趋势"),
    ("list", r"(?i)<(?:ul|ol)\b|role\s*=\s*['\"]list"),
    ("stepper", r"(?i)\b(?:stepper|steps|wizard)\b|步骤条|分步"),
    ("bulk-action", r"(?i)\b(?:bulk|batch)[-_ ]?(?:action|edit|update)\b|批量(?:操作|处理|更新)"),
    ("command-menu", r"(?i)\b(?:command[-_ ]?(?:menu|palette)|cmdk)\b|命令面板"),
)


def _text(sources: Sequence[Mapping[str, Any]]) -> str:
    return "\n".join(str(item.get("text") or "") for item in sources)


def _content_text(sources: Sequence[Mapping[str, Any]]) -> str:
    """Exclude stylesheets from semantic and component evidence.

    Shared CSS often contains selectors for every route in a product. Treating
    those selector names as visible page content cross-contaminates page type
    and component inventory, especially for multi-surface applications.
    """

    style_suffixes = (".css", ".scss", ".sass", ".less", ".styl", ".stylus")
    selected = [
        str(item.get("text") or "")
        for item in sources
        if not str(item.get("path") or "").casefold().endswith(style_suffixes)
    ]
    return "\n".join(selected) if selected else _text(sources)


def _count(pattern: str, text: str) -> int:
    return len(re.findall(pattern, text))


def _inventory(text: str) -> list[dict[str, Any]]:
    result = []
    for component, pattern in _COMPONENT_PATTERNS:
        count = _count(pattern, text)
        if count:
            result.append({
                "type": component,
                "count": count,
                "evidenceTier": "source-static",
                "confidence": "high" if component in {"button", "form", "input", "table", "navigation"} else "medium",
            })
    return result


def _component_counts(inventory: Sequence[Mapping[str, Any]]) -> Counter[str]:
    return Counter({str(item.get("type")): int(item.get("count") or 0) for item in inventory})


def _score_page_types(
    text: str,
    inventory: Sequence[Mapping[str, Any]],
    model: Mapping[str, Any],
    page_modes: Sequence[str],
    screenshot_model: Mapping[str, Any],
    observed: Mapping[str, Any],
) -> list[dict[str, Any]]:
    lower = text.casefold()
    counts = _component_counts(inventory)
    mode_text = " ".join(str(item) for item in page_modes).casefold()
    context = " ".join(str(model.get(key) or "") for key in ("primaryTask", "taskType", "environment", "informationDensity", "productType", "consultantIntent")).casefold()
    declared_family = str(model.get("productType") or "").strip().casefold()
    declared_intent = str(model.get("consultantIntent") or "").strip().casefold()
    explicit_page_type = {
        "crm": "crm", "landing": "landing-page", "commerce": "ecommerce",
        "ecommerce": "ecommerce", "ai-product": "ai-product", "mobile": "mobile-workflow",
    }.get(declared_family)
    if explicit_page_type is None and declared_intent == "crm-saas":
        explicit_page_type = "crm"
    elif explicit_page_type is None and declared_intent == "mobile":
        explicit_page_type = "mobile-workflow"
    ranked: list[dict[str, Any]] = []
    screenshot_type = screenshot_model.get("pageType")
    screenshot_candidates = screenshot_model.get("pageTypeCandidates")
    observed_type = observed.get("pageType")

    for item in _PAGE_TYPES:
        score = 0
        evidence: list[dict[str, Any]] = []
        hits = [term for term in item["keywords"] if term.casefold() in lower or term.casefold() in context]
        if hits:
            gained = min(48, len(hits) * 8)
            score += gained
            evidence.append({"tier": "source-static", "fact": f"matched terms: {', '.join(hits[:8])}", "weight": gained})
        page_id = item["id"]
        if explicit_page_type == page_id:
            score += 42
            evidence.append({"tier": "explicit-business-context", "fact": f"declared product family: {declared_family or declared_intent}", "weight": 42})
        if page_id == "saas-dashboard":
            if counts["kpi"] >= 2 or counts["chart"] >= 1:
                score += 24; evidence.append({"tier": "source-static", "fact": "KPI/chart structure", "weight": 24})
            if "dashboard" in mode_text:
                score += 20; evidence.append({"tier": "source-inferred", "fact": "legacy page mode Dashboard", "weight": 20})
        elif page_id == "crm":
            if counts["search"] and counts["table"]:
                score += 18; evidence.append({"tier": "source-static", "fact": "search + table workbench", "weight": 18})
            if counts["drawer"]:
                score += 9; evidence.append({"tier": "source-static", "fact": "detail/peek surface", "weight": 9})
            if "列表和详情" in mode_text:
                score += 12; evidence.append({"tier": "source-inferred", "fact": "list-detail mode", "weight": 12})
        elif page_id == "erp":
            if counts["table"] and (counts["input"] >= 6 or counts["bulk-action"]):
                score += 22; evidence.append({"tier": "source-static", "fact": "dense editable/bulk data workspace", "weight": 22})
        elif page_id == "landing-page":
            h1 = _count(r"(?i)<h1\b", text)
            primary_cta = _count(r"(?i)(?:primary|cta|hero)[-_ ]?(?:button|action)?", text)
            if h1 and primary_cta:
                score += 22; evidence.append({"tier": "source-static", "fact": "H1 + hero/CTA path", "weight": 22})
            if counts["table"] or counts["bulk-action"]:
                score -= 12
        elif page_id == "ecommerce":
            if re.search(r"(?i)(?:price|amount|currency|¥|￥|\$|立即购买|加入购物车)", text):
                score += 18; evidence.append({"tier": "source-static", "fact": "price/purchase evidence", "weight": 18})
        elif page_id == "mobile-workflow":
            if str(model.get("devicePriority")) == "mobile" or str(model.get("environment")) == "mobile-field":
                score += 30; evidence.append({"tier": "explicit-or-source-inferred", "fact": "mobile device priority/environment", "weight": 30})
            if re.search(r"(?i)safe-area-inset|100dvh|bottom[-_ ]?(?:nav|action)", text):
                score += 15; evidence.append({"tier": "source-static", "fact": "mobile shell CSS", "weight": 15})
        elif page_id == "workflow":
            if counts["stepper"] or str(model.get("taskType")) == "review-confirm":
                score += 18; evidence.append({"tier": "source-static", "fact": "step/review workflow", "weight": 18})
        elif page_id == "content-feed" and counts["list"] >= 2:
            score += 8

        if isinstance(observed_type, str) and observed_type == page_id:
            score += 35; evidence.append({"tier": "rendered-observation", "fact": "observed pageType", "weight": 35})
        if isinstance(screenshot_type, Mapping) and screenshot_type.get("id") == page_id:
            confidence = float(screenshot_type.get("confidence") or 0)
            gained = round(35 * max(0.0, min(1.0, confidence)))
            score += gained; evidence.append({"tier": "screenshot-inferred", "fact": "screenshot pageType", "weight": gained})
        elif isinstance(screenshot_type, str) and screenshot_type == page_id:
            score += 20; evidence.append({"tier": "screenshot-inferred", "fact": "screenshot pageType label", "weight": 20})
        if isinstance(screenshot_candidates, list):
            for candidate in screenshot_candidates:
                if isinstance(candidate, Mapping) and candidate.get("id") == page_id:
                    gained = round(20 * float(candidate.get("confidence") or 0))
                    score += gained; evidence.append({"tier": "screenshot-inferred", "fact": "screenshot candidate", "weight": gained})
                    break
        ranked.append({"id": page_id, "label": item["label"], "score": max(0, min(100, score)), "evidence": evidence})

    return sorted(ranked, key=lambda item: (-item["score"], item["id"]))


def _structure(text: str, inventory: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    roles = (
        ("header", r"(?i)<header\b"),
        ("navigation", r"(?i)<nav\b|role\s*=\s*['\"]navigation"),
        ("main", r"(?i)<main\b|role\s*=\s*['\"]main"),
        ("aside", r"(?i)<aside\b|role\s*=\s*['\"]complementary"),
        ("footer", r"(?i)<footer\b"),
        ("section", r"(?i)<section\b"),
    )
    result = [{"role": role, "count": _count(pattern, text), "evidenceTier": "source-static"} for role, pattern in roles if _count(pattern, text)]
    component_counts = _component_counts(inventory)
    if component_counts["table"] and component_counts["drawer"]:
        result.append({"role": "list-detail-workspace", "count": 1, "evidenceTier": "source-inferred"})
    if component_counts["kpi"] or component_counts["chart"]:
        result.append({"role": "metric-overview", "count": max(component_counts["kpi"], 1), "evidenceTier": "source-inferred"})
    return result


def _interaction_patterns(inventory: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    counts = _component_counts(inventory)
    patterns: list[dict[str, Any]] = []
    candidates = (
        ("search-filter", counts["search"] and counts["filter"], "查找并缩小结果范围"),
        ("list-detail", counts["table"] and counts["drawer"], "在保留列表上下文时查看详情"),
        ("bulk-processing", counts["bulk-action"], "选择后批量处理记录"),
        ("dashboard-drilldown", counts["kpi"] and (counts["chart"] or counts["table"]), "从摘要进入可操作明细"),
        ("multi-step-form", counts["form"] and counts["stepper"], "按依赖顺序完成表单"),
        ("command-efficiency", counts["command-menu"], "用统一命令入口执行高频动作"),
    )
    for pattern_id, present, meaning in candidates:
        if present:
            patterns.append({"id": pattern_id, "meaning": meaning, "evidenceTier": "source-inferred", "confidence": "medium"})
    return patterns


def build_page_understanding(
    sources: Sequence[Mapping[str, Any]],
    experience_model: Mapping[str, Any] | None = None,
    *,
    page_modes: Sequence[str] = (),
    screenshot_model: Mapping[str, Any] | None = None,
    observed: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a provenance-aware understanding shared by diagnosis and preview."""

    experience_model = experience_model or {}
    screenshot_model = screenshot_model or {}
    observed = observed or {}
    source_text = _content_text(sources)
    inventory = _inventory(source_text)
    candidates = _score_page_types(source_text, inventory, experience_model, page_modes, screenshot_model, observed)
    top = candidates[0]
    second = candidates[1] if len(candidates) > 1 else {"score": 0}
    margin = top["score"] - second["score"]
    if top["score"] >= 32 and margin >= 8:
        classification_status = "CLASSIFIED"
        confidence = "high" if top["score"] >= 65 and margin >= 15 else "medium"
        selected: dict[str, Any] = {"id": top["id"], "label": top["label"], "confidence": confidence, "score": top["score"], "evidence": top["evidence"]}
    elif top["score"] >= 20:
        classification_status = "AMBIGUOUS"
        selected = {"id": "unclassified", "label": "Unclassified", "confidence": "low", "score": top["score"], "evidence": []}
        confidence = "low"
    else:
        classification_status = "UNCLASSIFIED"
        selected = {"id": "unclassified", "label": "Unclassified", "confidence": "low", "score": top["score"], "evidence": []}
        confidence = "low"

    explicit_task = str(experience_model.get("primaryTask") or "").strip()
    screenshot_tasks = screenshot_model.get("userTasks")
    screenshot_task = ""
    if isinstance(screenshot_tasks, list) and screenshot_tasks:
        first = screenshot_tasks[0]
        screenshot_task = str(first.get("task") if isinstance(first, Mapping) else first).strip()
    page_rule = next((item for item in _PAGE_TYPES if item["id"] == selected["id"]), None)
    inferred_task = str(page_rule["task"]) if page_rule else ""
    primary_task = explicit_task or screenshot_task or inferred_task or None
    task_provenance = "explicit-business-context" if explicit_task else "screenshot-inferred" if screenshot_task else "page-type-candidate" if inferred_task else "unknown"

    hierarchy = screenshot_model.get("visualHierarchy")
    if not isinstance(hierarchy, Mapping):
        hierarchy = {
            "status": "CANDIDATE_ONLY",
            "firstGlance": primary_task,
            "secondGlance": "关键状态、判断依据和下一步" if primary_task else None,
            "evidenceTier": "source-inferred",
            "verificationNeeded": ["在相同视口截图中验证实际视觉显著性和阅读顺序"],
        }

    unresolved: list[str] = []
    if selected["id"] == "unclassified":
        unresolved.append("页面类型证据不足；需要业务上下文、截图语义或真实 DOM/Browser 证据")
    if not explicit_task:
        unresolved.append("首要用户任务尚未由用户或业务证据确认")
    if not inventory:
        unresolved.append("未从静态源码识别到可用组件角色")
    if hierarchy.get("status") != "OBSERVED":
        unresolved.append("第一/第二视觉焦点尚未通过截图或 Browser 观察验证")

    provenance = {
        "pageType": "mixed-source-and-screenshot" if screenshot_model else "source-inferred",
        "primaryTask": task_provenance,
        "componentRoles": "source-static",
        "structure": "source-static-and-inferred",
        "interactionPatterns": "source-inferred",
        "visualHierarchy": str(hierarchy.get("evidenceTier") or "source-inferred"),
    }
    result: dict[str, Any] = {
        "schemaVersion": "3.1",
        "selectionPolicyVersion": "page-understanding-3.1",
        "status": classification_status,
        "pageType": selected,
        "pageTypeCandidates": candidates[:5],
        "primaryTask": {"value": primary_task, "provenance": task_provenance, "confirmed": bool(explicit_task)},
        "structure": _structure(source_text, inventory),
        "componentInventory": inventory,
        "interactionPatterns": _interaction_patterns(inventory),
        "visualHierarchy": hierarchy,
        "provenance": provenance,
        "confidence": confidence,
        "unresolvedQuestions": unresolved,
        "claimBoundary": "源码和截图可以支持页面类型与组件候选；隐藏交互、权限、真实焦点和用户结果必须由 Browser 或用户研究验证。",
    }
    result["digest"] = digest_json(result)
    return result


__all__ = ["build_page_understanding"]
