"""Screenshot-to-experience sidecar modelling.

Pixels remain candidate evidence.  This module turns screenshot Design IR and an
optional host semantic overlay into page-type, structure, component, task, and
interaction candidates without pretending local edge segmentation is OCR.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Iterable, Mapping

from .contracts import digest_json


_TYPE_ALIASES = {
    "grid": "table", "data-grid": "table", "datatable": "table",
    "dialog": "modal", "sheet": "drawer", "side-panel": "drawer",
    "metric": "kpi", "stat": "kpi", "statistic": "kpi",
    "plot": "chart", "graph": "chart",
    "searchbox": "search", "textbox": "input",
}
_PAGE_TERMS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("saas-dashboard", ("dashboard", "overview", "kpi", "metric", "chart", "analytics", "总览", "指标", "趋势", "告警")),
    ("crm", ("crm", "customer", "contact", "lead", "pipeline", "客户", "联系人", "线索", "商机", "跟进")),
    ("erp", ("erp", "inventory", "warehouse", "procurement", "manufacturing", "库存", "仓库", "采购", "生产", "物料")),
    ("landing-page", ("hero", "pricing", "testimonial", "features", "get started", "landing", "核心卖点", "免费试用", "预约演示")),
    ("ecommerce", ("product", "cart", "checkout", "buy", "price", "商品", "购物车", "结算", "购买", "价格", "规格")),
    ("mobile-workflow", ("field", "scan", "offline", "bottom action", "现场", "扫码", "离线", "移动任务")),
    ("workflow", ("workflow", "approval", "step", "review", "流程", "审批", "步骤")),
)


def _walk(nodes: Iterable[Mapping[str, Any]], *, depth: int = 0) -> Iterable[tuple[Mapping[str, Any], int]]:
    for node in nodes:
        if not isinstance(node, Mapping):
            continue
        yield node, depth
        children = node.get("children")
        if isinstance(children, list):
            yield from _walk((item for item in children if isinstance(item, Mapping)), depth=depth + 1)


def _normalise_type(value: Any) -> str:
    raw = str(value or "unknown").strip().casefold().replace("_", "-")
    return _TYPE_ALIASES.get(raw, raw)


def _overlay_elements(overlay: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    if not overlay:
        return []
    value = overlay.get("elements")
    return [item for item in value if isinstance(item, Mapping)] if isinstance(value, list) else []


def _bounds_iou(left: Any, right: Any) -> float:
    if not isinstance(left, Mapping) or not isinstance(right, Mapping):
        return 0.0
    try:
        ax1 = float(left["x"]); ay1 = float(left["y"])
        ax2 = ax1 + float(left["width"]); ay2 = ay1 + float(left["height"])
        bx1 = float(right["x"]); by1 = float(right["y"])
        bx2 = bx1 + float(right["width"]); by2 = by1 + float(right["height"])
    except (KeyError, TypeError, ValueError):
        return 0.0
    intersection = max(0.0, min(ax2, bx2) - max(ax1, bx1)) * max(0.0, min(ay2, by2) - max(ay1, by1))
    union = max(0.0, (ax2 - ax1) * (ay2 - ay1)) + max(0.0, (bx2 - bx1) * (by2 - by1)) - intersection
    return intersection / max(1.0, union)


def _component_inventory(document: Mapping[str, Any], overlay: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    confidence: dict[str, float] = {}
    provenance: dict[str, Counter[str]] = {}
    applied_overlay_nodes: list[tuple[str, Mapping[str, Any]]] = []
    roots = document.get("roots")
    if isinstance(roots, list):
        for node, _depth in _walk(item for item in roots if isinstance(item, Mapping)):
            node_type = _normalise_type(node.get("type"))
            if node_type not in {"page", "frame", "section", "stack", "text", "unknown"}:
                counts[node_type] += 1
                semantics = node.get("semantics") if isinstance(node.get("semantics"), Mapping) else {}
                try:
                    value = float(semantics.get("confidence") or 0.35)
                except (TypeError, ValueError):
                    value = 0.35
                confidence[node_type] = max(confidence.get(node_type, 0.0), value)
                analysis = str(semantics.get("analysis") or "").casefold()
                tier = "screenshot-overlay" if "overlay" in analysis else "local-visual-segmentation"
                provenance.setdefault(node_type, Counter())[tier] += 1
                if tier == "screenshot-overlay" and isinstance(node.get("bounds"), Mapping):
                    applied_overlay_nodes.append((node_type, node["bounds"]))

    for item in _overlay_elements(overlay):
        node_type = _normalise_type(item.get("type") or item.get("role"))
        already_counted = any(
            applied_type == node_type and _bounds_iou(applied_bounds, item.get("bounds")) >= 0.18
            for applied_type, applied_bounds in applied_overlay_nodes
        )
        if node_type != "unknown" and not already_counted:
            counts[node_type] += 1
            try:
                value = float(item.get("confidence") or 0.6)
            except (TypeError, ValueError):
                value = 0.6
            confidence[node_type] = max(confidence.get(node_type, 0.0), value)
            provenance.setdefault(node_type, Counter())["screenshot-overlay"] += 1
    return [
        {
            "type": component,
            "count": count,
            "confidence": round(min(0.95, confidence.get(component, 0.35)), 3),
            "evidenceTier": (
                "screenshot-overlay"
                if provenance.get(component, Counter()).get("screenshot-overlay")
                else "local-visual-segmentation"
            ),
        }
        for component, count in sorted(counts.items())
    ]


def _visual_structure(document: Mapping[str, Any]) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = []
    roots = document.get("roots")
    max_depth = 0
    if isinstance(roots, list):
        for node, depth in _walk(item for item in roots if isinstance(item, Mapping)):
            max_depth = max(max_depth, depth)
            bounds = node.get("bounds")
            if isinstance(bounds, Mapping):
                try:
                    nodes.append({
                        "type": _normalise_type(node.get("type")),
                        "depth": depth,
                        "x": float(bounds.get("x") or 0),
                        "y": float(bounds.get("y") or 0),
                        "width": float(bounds.get("width") or 0),
                        "height": float(bounds.get("height") or 0),
                    })
                except (TypeError, ValueError):
                    pass
    x_clusters = len({round(item["x"] / 8) * 8 for item in nodes if item["width"] > 20})
    y_clusters = len({round(item["y"] / 8) * 8 for item in nodes if item["height"] > 8})
    large_regions = sorted(nodes, key=lambda item: item["width"] * item["height"], reverse=True)[:8]
    return {
        "nodeCount": len(nodes),
        "maxDepth": max_depth,
        "alignmentClusters": {"x": x_clusters, "y": y_clusters},
        "largeRegions": large_regions,
        "hierarchyStatus": "HIERARCHICAL" if max_depth >= 2 else "FLAT_CANDIDATE",
    }


def _page_candidates(
    inventory: list[dict[str, Any]],
    structure: Mapping[str, Any],
    overlay: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    counts = Counter({str(item["type"]): int(item["count"]) for item in inventory})
    texts = " ".join(
        str(item.get(key) or "")
        for item in _overlay_elements(overlay)
        for key in ("text", "name", "label", "type", "role")
    ).casefold()
    ranked: list[dict[str, Any]] = []
    explicit = overlay.get("pageType") if overlay else None
    for page_id, terms in _PAGE_TERMS:
        score = 0.0
        evidence: list[str] = []
        hits = [term for term in terms if term.casefold() in texts]
        if hits:
            score += min(0.48, len(hits) * 0.09)
            evidence.append("overlay terms: " + ", ".join(hits[:6]))
        if page_id == "saas-dashboard" and (counts["kpi"] >= 2 or counts["chart"]):
            score += 0.28; evidence.append("KPI/chart regions")
        if page_id == "crm" and counts["table"] and (counts["search"] or counts["drawer"]):
            score += 0.24; evidence.append("table + search/detail")
        if page_id == "erp" and counts["table"] and counts["input"] >= 4:
            score += 0.22; evidence.append("dense table/input workspace")
        if page_id == "landing-page" and (counts["hero"] or counts["button"]) and not counts["table"]:
            score += 0.18; evidence.append("hero/action without data grid")
        if page_id == "ecommerce" and (counts["product"] or counts["price"]):
            score += 0.25; evidence.append("product/price regions")
        if page_id == "mobile-workflow":
            canvas = structure.get("largeRegions") or []
            if canvas:
                widest = max((item.get("width") or 0 for item in canvas), default=0)
                tallest = max((item.get("height") or 0 for item in canvas), default=0)
                if tallest > widest * 1.25:
                    score += 0.16; evidence.append("portrait canvas")
        if isinstance(explicit, str) and explicit == page_id:
            score += 0.55; evidence.append("explicit host overlay pageType")
        elif isinstance(explicit, Mapping) and explicit.get("id") == page_id:
            supplied = float(explicit.get("confidence") or 0.6)
            score += min(0.6, max(0.0, supplied) * 0.6); evidence.append("host overlay pageType")
        ranked.append({"id": page_id, "confidence": round(min(0.95, score), 3), "evidence": evidence})
    return sorted(ranked, key=lambda item: (-item["confidence"], item["id"]))


def _user_tasks(overlay: Mapping[str, Any] | None, page_id: str, confidence: float) -> list[dict[str, Any]]:
    value = overlay.get("userTasks") if overlay else None
    if isinstance(value, list):
        result = []
        for item in value:
            if isinstance(item, Mapping):
                task = str(item.get("task") or item.get("label") or "").strip()
                if task:
                    result.append({"task": task, "confidence": round(float(item.get("confidence") or 0.6), 3), "evidenceTier": "host-overlay"})
            elif str(item).strip():
                result.append({"task": str(item).strip(), "confidence": 0.55, "evidenceTier": "host-overlay"})
        if result:
            return result
    defaults = {
        "saas-dashboard": "查看关键状态并处理异常",
        "crm": "查找并连续处理客户记录",
        "erp": "核对业务数据并完成安全操作",
        "landing-page": "理解价值并选择下一步",
        "ecommerce": "比较商品并完成购买决策",
        "mobile-workflow": "在移动环境完成当前任务",
        "workflow": "理解阶段并完成允许的下一步",
    }
    if page_id in defaults and confidence >= 0.45:
        return [{"task": defaults[page_id], "confidence": round(confidence * 0.65, 3), "evidenceTier": "page-type-candidate", "confirmed": False}]
    return []


def _interaction_patterns(inventory: list[dict[str, Any]], overlay: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    supplied = overlay.get("interactionPatterns") if overlay else None
    result: list[dict[str, Any]] = []
    if isinstance(supplied, list):
        for item in supplied:
            if isinstance(item, Mapping):
                result.append({**dict(item), "evidenceTier": "host-overlay"})
            elif str(item).strip():
                result.append({"id": str(item).strip(), "evidenceTier": "host-overlay", "confidence": 0.55})
    counts = Counter({str(item["type"]): int(item["count"]) for item in inventory})
    inferred = (
        ("search-filter", counts["search"] and counts["filter"]),
        ("list-detail", counts["table"] and counts["drawer"]),
        ("dashboard-drilldown", counts["kpi"] and (counts["chart"] or counts["table"])),
        ("form-submit", counts["form"] or counts["input"] >= 3),
        ("modal-task", counts["modal"]),
    )
    existing = {str(item.get("id")) for item in result}
    for pattern_id, present in inferred:
        if present and pattern_id not in existing:
            result.append({"id": pattern_id, "evidenceTier": "screenshot-inferred", "confidence": 0.4, "verificationNeeded": "真实操作验证"})
    return result


def build_screenshot_experience_model(
    design_ir: Mapping[str, Any],
    *,
    overlay: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a candidate experience model from screenshot Design IR."""

    inventory = _component_inventory(design_ir, overlay)
    structure = _visual_structure(design_ir)
    candidates = _page_candidates(inventory, structure, overlay)
    top = candidates[0] if candidates else {"id": "unclassified", "confidence": 0.0, "evidence": []}
    second_confidence = candidates[1]["confidence"] if len(candidates) > 1 else 0.0
    classified = top["confidence"] >= 0.45 and top["confidence"] - second_confidence >= 0.08
    page_type = {
        "id": top["id"] if classified else "unclassified",
        "confidence": top["confidence"] if classified else round(max(0.0, top["confidence"]), 3),
        "evidence": top.get("evidence", []) if classified else [],
    }
    tasks = _user_tasks(overlay, page_type["id"], float(page_type["confidence"]))
    visual_hierarchy = overlay.get("visualHierarchy") if overlay and isinstance(overlay.get("visualHierarchy"), Mapping) else {
        "status": "CANDIDATE_ONLY",
        "firstGlance": None,
        "secondGlance": None,
        "evidenceTier": "local-visual-segmentation",
        "verificationNeeded": ["用多模态或人工评审确认真实阅读顺序"],
    }
    unresolved = []
    if page_type["id"] == "unclassified":
        unresolved.append("页面类型证据不足")
    if not tasks:
        unresolved.append("截图不能可靠推断用户任务")
    if not overlay:
        unresolved.append("未提供语义 overlay；本地分析不执行 OCR")
    result: dict[str, Any] = {
        "schemaVersion": "3.1",
        "status": "EXPERIENCE_MODEL_READY" if classified and tasks else "DISCOVERY_REQUIRED",
        "pageType": page_type,
        "pageTypeCandidates": candidates[:5],
        "structure": structure,
        "componentInventory": inventory,
        "userTasks": tasks,
        "interactionPatterns": _interaction_patterns(inventory, overlay),
        "visualHierarchy": visual_hierarchy,
        "evidenceMode": "screenshot-plus-host-overlay" if overlay else "local-visual-segmentation",
        "unresolvedQuestions": unresolved,
        "claimBoundary": "截图模型只提供候选页面结构和语义；隐藏交互、业务规则、权限与用户结果必须由源码、Browser 或用户证据确认。",
    }
    result["digest"] = digest_json(result)
    return result


__all__ = ["build_screenshot_experience_model"]
