"""Responsive experience analysis with explicit static/rendered evidence levels."""
from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from .contracts import digest_json

STANDARD_VIEWPORTS = {"desktop": 1440, "tablet": 768, "mobile": 390}
_COST = {"UX1": 12, "UX2": 7, "UX3": 3}
_SUFFIXES = (".css", ".scss", ".sass", ".less", ".html", ".htm", ".vue", ".svelte", ".jsx", ".tsx")
_BLOCK = re.compile(r"(?is)(?P<selector>[^{}]+)\{(?P<body>[^{}]*)\}")
_DECL = re.compile(r"(?i)(?P<name>-{0,2}[a-z][\w-]*)\s*:\s*(?P<value>[^;{}]+)")
_MEDIA = re.compile(r"(?i)@media[^{}]*max-width\s*:\s*(\d+(?:\.\d+)?)px")
_PAGE_TYPES = {"dashboard", "crm", "erp", "landing", "mobile"}


def _num(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result == result else None


def _bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    value = str(value).strip().casefold()
    if value in {"true", "yes", "pass", "visible", "usable"}:
        return True
    if value in {"false", "no", "fail", "hidden", "unusable"}:
        return False
    return None


def _first(row: Mapping[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = _num(row.get(key))
        if value is not None:
            return value
    return None


def _flag(row: Mapping[str, Any], *keys: str) -> bool | None:
    for key in keys:
        value = _bool(row.get(key))
        if value is not None:
            return value
    return None


def _maps(value: Any) -> list[Mapping[str, Any]]:
    return [item for item in value if isinstance(item, Mapping)] if isinstance(value, (list, tuple)) else []



def _has_rendered_authority(observed: Mapping[str, Any]) -> bool:
    raw = observed.get("evidenceTier") or observed.get("evidenceMode")
    value = str(raw or "").strip().casefold().replace("_", "-")
    return value in {"browser-measured", "rendered-observation", "mixed-rendered-and-static"}


def _viewports(observed: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = observed.get("viewports")
    rows: list[dict[str, Any]] = []
    if isinstance(raw, Mapping):
        rows = [{"id": str(name), **dict(item)} for name, item in raw.items() if isinstance(item, Mapping)]
    elif isinstance(raw, (list, tuple)):
        rows = [{"id": str(item.get("id") or item.get("name") or f"viewport-{index + 1}"), **dict(item)}
                for index, item in enumerate(raw) if isinstance(item, Mapping)]
    elif any(key in observed for key in ("clientWidth", "viewportWidth", "scrollWidth")):
        rows = [{"id": str(observed.get("id") or "observed"), **dict(observed)}]
    result = []
    for index, row in enumerate(rows):
        width = _first(row, "clientWidth", "viewportWidth", "innerWidth", "width")
        height = _first(row, "clientHeight", "viewportHeight", "innerHeight", "height")
        result.append({**row, "id": str(row.get("id") or f"viewport-{index + 1}"), "width": width, "height": height})
    return sorted(result, key=lambda item: (item["width"] is None, -(item["width"] or 0), item["id"]))


def _role(width: float | None) -> str:
    if width is None:
        return "unknown"
    return "desktop" if width >= 1200 else "tablet" if width >= 600 else "mobile"


def _finding(
    code: str, severity: str, title: str, explanation: str, impact: str,
    evidence: Any, recommendation: str, verification: Sequence[str],
    confidence: str, evidence_mode: str,
) -> dict[str, Any]:
    return {
        "id": code, "severity": severity, "category": "responsive", "title": title,
        "userExplanation": explanation, "userImpact": impact, "evidence": evidence,
        "recommendation": recommendation,
        "implementation": {
            "modern": "优先用 Grid/Flex、Container Queries、clamp()/minmax()、dvh 与 safe-area 渐进增强。",
            "fallback": "使用媒体查询、基础 Flex/Grid、局部滚动和稳定内容占位。",
        },
        "verification": list(verification), "confidence": confidence, "evidenceMode": evidence_mode,
    }


def _profile(text: str) -> dict[str, Any]:
    breakpoints = sorted({float(value) for value in _MEDIA.findall(text)})
    blocks = []
    for match in _BLOCK.finditer(text):
        declarations = {item.group("name").casefold(): item.group("value").strip()
                        for item in _DECL.finditer(match.group("body"))}
        blocks.append((" ".join(match.group("selector").split())[:160], declarations))
    no_wrap = [
        selector for selector, decl in blocks
        if any(word in selector.casefold() for word in ("toolbar", "actions", "filters", "button-group"))
        and "flex" in decl.get("display", "").casefold()
        and decl.get("flex-wrap", "nowrap").casefold() == "nowrap"
    ]
    dialogs = [
        {"selector": selector, "width": decl.get("width") or decl.get("min-width") or "",
         "height": decl.get("height") or decl.get("min-height") or ""}
        for selector, decl in blocks
        if any(word in selector.casefold() for word in ("dialog", "modal", "drawer"))
        and any(key in decl for key in ("width", "min-width", "height", "min-height"))
    ]
    tables = len(re.findall(r"(?i)<table\b", text))
    navs = len(re.findall(r"(?i)<nav\b|role\s*=\s*['\"]navigation['\"]", text))
    return {
        "mediaBreakpointsPx": breakpoints,
        "containerQueries": len(re.findall(r"(?i)@container\b", text)),
        "tables": tables,
        "dialogs": len(re.findall(r"(?i)<dialog\b|role\s*=\s*['\"]dialog['\"]", text)),
        "navigationRegions": navs,
        "buttons": len(re.findall(r"(?i)<button\b|role\s*=\s*['\"]button['\"]", text)),
        "fixedBottomAction": bool(re.search(r"(?is)position\s*:\s*fixed[^{}]{0,320}\bbottom\s*:", text)),
        "safeAreaInsets": bool(re.search(r"env\(safe-area-inset-", text, re.I)),
        "tableLocalScrollStrategy": bool(re.search(
            r"(?is)(?:table-container|table-wrapper|data-grid|responsive-table)[^{}]*\{[^{}]*overflow-x\s*:\s*(?:auto|scroll)", text)),
        "noWrapToolbars": no_wrap,
        "fixedDialogs": dialogs,
        "complexDesktopComposition": bool(tables or navs or dialogs or re.search(r"(?i)grid-template-columns\s*:", text)),
        "hasIntermediateRecomposition": bool(any(650 <= value <= 1100 for value in breakpoints) or re.search(r"(?i)@container\b", text)),
    }


def _page_type(text: str, observed: Mapping[str, Any]) -> dict[str, Any]:
    aliases = {
        "saas-dashboard": "dashboard", "operations-dashboard": "dashboard", "仪表盘": "dashboard",
        "客户关系管理": "crm", "customer-relationship-management": "crm",
        "企业资源计划": "erp", "enterprise-resource-planning": "erp",
        "marketing": "landing", "marketing-landing": "landing", "着陆页": "landing",
        "field": "mobile", "mobile-field": "mobile", "移动现场": "mobile",
    }
    for key in ("pageType", "page_type", "archetype", "productType"):
        raw = aliases.get(str(observed.get(key) or "").strip().casefold(), str(observed.get(key) or "").strip().casefold())
        if raw in _PAGE_TYPES:
            return {"id": raw, "confidence": "high", "evidenceMode": "explicit-observation", "reasons": [f"observed.{key}"]}
    lower = text.casefold()
    keywords = {
        "dashboard": ("dashboard", "仪表盘", "kpi", "趋势", "待处理", "异常队列"),
        "crm": ("crm", "客户", "线索", "商机", "联系人", "销售跟进"),
        "erp": ("erp", "库存", "物料", "采购", "生产订单", "批次", "仓库"),
        "landing": ("landing", "hero", "pricing", "features", "start free", "立即购买", "免费试用"),
        "mobile": ("移动现场", "巡检", "扫码", "拍照", "离线", "弱网", "field task"),
    }
    scores = {kind: sum(token in lower for token in values) for kind, values in keywords.items()}
    ranked = sorted(scores, key=lambda kind: (-scores[kind], kind))
    winner = ranked[0]
    if scores[winner] == 0:
        return {"id": "generic", "confidence": "low", "evidenceMode": "static-source", "reasons": []}
    confidence = "medium" if scores[winner] >= 2 and scores[winner] > scores[ranked[1]] else "low"
    return {"id": winner, "confidence": confidence, "evidenceMode": "static-source",
            "reasons": [token for token in keywords[winner] if token in lower][:5]}


_COMPOSITIONS = {
    "dashboard": {
        "desktop": ("状态摘要、异常队列、趋势与下一步任务形成主次分区", ["异常与风险", "下一步任务", "支持判断的指标"]),
        "tablet": ("摘要压缩为两列，异常队列先于趋势，任务区独立成段", ["异常", "任务", "关键趋势"]),
        "mobile": ("状态、最高优先异常和单一下一步组成单列流", ["当前状态", "需处理异常", "一个明确动作"]),
    },
    "crm": {
        "desktop": ("搜索筛选、客户列表与同页详情组成稳定主从工作台", ["查找客户", "当前客户", "下一步销售动作"]),
        "tablet": ("列表主导，详情在可调分栏或上下区域呈现", ["筛选结果", "选中对象", "关键动作"]),
        "mobile": ("客户列表与详情使用连续视图切换", ["搜索筛选", "客户摘要", "联系或跟进"]),
    },
    "erp": {
        "desktop": ("高密度数据区、批量操作与审计状态分区", ["可比较数据", "异常校验", "受控批量动作"]),
        "tablet": ("关键列优先的局部滚动数据区，批量动作收敛", ["关键字段", "校验状态", "当前批次动作"]),
        "mobile": ("任务化摘要、关键字段与独立详情/编辑视图", ["对象状态", "差异", "安全下一步"]),
    },
    "landing": {
        "desktop": ("Hero 价值主张、单一主 CTA、信任证据与产品叙事", ["用户价值", "主 CTA", "可信证据"]),
        "tablet": ("Hero 与产品证据由并列转为主次上下结构", ["价值主张", "主 CTA", "核心能力"]),
        "mobile": ("短价值主张、单一 CTA、关键证据的单列叙事", ["一句价值", "立即行动", "信任结果"]),
    },
    "mobile": {
        "desktop": ("任务管理与回看视图，不模拟移动操作区", ["任务队列", "同步状态", "异常回看"]),
        "tablet": ("大触控单列任务与可见步骤进度", ["当前任务", "证据采集", "下一步"]),
        "mobile": ("单手步骤任务、离线状态与安全区内固定主操作", ["当前对象", "当前步骤", "可恢复主操作"]),
    },
}

_COMPOSITIONS["generic"] = {
    "desktop": ("保持主任务、内容和操作的稳定页面结构", ["主任务", "核心内容", "下一步"]),
    "tablet": ("根据可用空间减少并列区域并保留任务上下文", ["主任务", "关键内容", "可达操作"]),
    "mobile": ("单列呈现核心任务并提供明确返回和恢复路径", ["当前任务", "当前状态", "主要操作"]),
}


def build_composition_plan(page_type: str, *, confidence: str = "low", evidence_mode: str = "static-source") -> dict[str, Any]:
    """Build the desktop/tablet/mobile composition contract for one page type."""

    basis = page_type if page_type in _COMPOSITIONS else "generic"
    plan: dict[str, Any] = {
        "pageType": page_type if page_type in _PAGE_TYPES else "generic",
        "templateBasis": basis, "confidence": confidence, "evidenceMode": evidence_mode,
        "candidateOnly": evidence_mode not in {"rendered-observation", "mixed-rendered-and-static"},
    }
    adaptations = {
        "desktop": "利用桌面空间承载有用上下文，避免无意义拉伸。",
        "tablet": "必须有不同于桌面等比缩小的中间重组。",
        "mobile": "保留核心任务能力，导航、弹层、表格和固定操作不得崩坏。",
    }
    for role, width in STANDARD_VIEWPORTS.items():
        layout, priority = _COMPOSITIONS[basis][role]
        plan[role] = {
            "targetWidth": width, "layout": layout, "priority": priority,
            "adaptation": adaptations[role],
            "verification": [f"{width}px 无页面级横向滚动", "主任务、状态和恢复路径可达"],
        }
    return plan


def _box(item: Mapping[str, Any]) -> tuple[float | None, float | None, float | None, float | None]:
    value = item.get("bounds") if isinstance(item.get("bounds"), Mapping) else item.get("rect") if isinstance(item.get("rect"), Mapping) else item
    return _first(value, "x", "left"), _first(value, "y", "top"), _first(value, "width", "clientWidth"), _first(value, "height", "clientHeight")


def _observed_issues(row: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    width = _first(row, "clientWidth", "viewportWidth", "innerWidth", "width")
    height = _first(row, "clientHeight", "viewportHeight", "innerHeight", "height")
    result: dict[str, list[dict[str, Any]]] = {
        "buttons": [], "tables": [], "dialogs": [], "navigation": [], "fixedActions": [],
    }
    for index, button in enumerate(_maps(row.get("buttons"))):
        _, _, item_width, item_height = _box(button)
        reasons = []
        if _flag(button, "clipped", "textClipped") is True:
            reasons.append("label-clipped")
        if _flag(button, "overlap", "overlapped", "occluded") is True:
            reasons.append("overlap")
        if item_width is not None and item_width < 44:
            reasons.append("width-below-44")
        if item_height is not None and item_height < 44:
            reasons.append("height-below-44")
        if reasons:
            result["buttons"].append({"index": index, "selector": button.get("selector"), "width": item_width, "height": item_height, "reasons": reasons})
    aggregate = _first(row, "squeezedButtonCount", "buttonOverflowCount", "clippedButtonCount")
    if aggregate and aggregate > 0:
        result["buttons"].append({"count": int(aggregate), "reasons": ["reported-button-squeeze"]})

    tables = _maps(row.get("tables"))
    if not tables and isinstance(row.get("table"), Mapping):
        tables = [row["table"]]
    for index, table in enumerate(tables):
        client = _first(table, "clientWidth", "containerWidth", "width")
        scroll = _first(table, "scrollWidth", "contentWidth")
        visible = _first(table, "visibleColumns")
        total = _first(table, "totalColumns", "columns")
        reasons = []
        if _flag(table, "usable", "taskUsable") is False:
            reasons.append("reported-unusable")
        if client is not None and scroll is not None and scroll > client + 1 and _flag(table, "localHorizontalScroll", "localScroll", "scrollContainer", "overflowXAuto") is not True:
            reasons.append("overflow-without-local-scroll")
        if visible is not None and total is not None and total >= 4 and visible < min(3, total):
            reasons.append("critical-columns-lost")
        if (_first(table, "minimumColumnWidth", "minColumnWidth") or 999) < 72:
            reasons.append("columns-squeezed")
        if reasons:
            result["tables"].append({"index": index, "clientWidth": client, "scrollWidth": scroll, "visibleColumns": visible, "totalColumns": total, "reasons": reasons})

    dialogs = _maps(row.get("dialogs"))
    if not dialogs and isinstance(row.get("dialog"), Mapping):
        dialogs = [row["dialog"]]
    for index, dialog in enumerate(dialogs):
        x, y, item_width, item_height = _box(dialog)
        right = _first(dialog, "right") or (x + item_width if x is not None and item_width is not None else None)
        bottom = _first(dialog, "bottom") or (y + item_height if y is not None and item_height is not None else None)
        reasons = []
        if width is not None and ((item_width or 0) > width + 1 or (right or 0) > width + 1):
            reasons.append("horizontal-offscreen")
        if height is not None and ((item_height or 0) > height + 1 or (bottom or 0) > height + 1):
            reasons.append("vertical-offscreen")
        if _flag(dialog, "contentReachable", "scrollable") is False:
            reasons.append("content-unreachable")
        if reasons:
            result["dialogs"].append({"index": index, "rect": {"x": x, "y": y, "width": item_width, "height": item_height}, "reasons": reasons})

    nav_value = row.get("navigation")
    navs = [nav_value] if isinstance(nav_value, Mapping) else _maps(nav_value) or _maps(row.get("navigations"))
    for index, item in enumerate(navs):
        reasons = []
        if _flag(item, "overflow", "horizontalOverflow") is True:
            reasons.append("navigation-overflow")
        if (_first(item, "wrappedRows", "rowCount") or 1) > 1:
            reasons.append("navigation-wrapped")
        if (_first(item, "offscreenItemCount", "hiddenRequiredItemCount") or 0) > 0:
            reasons.append("required-items-offscreen")
        if _role(width) == "mobile" and _flag(item, "visible", "navigationVisible") is False and _flag(item, "menuButtonVisible", "mobileToggleVisible") is not True:
            reasons.append("no-mobile-navigation-entry")
        if reasons:
            result["navigation"].append({"index": index, "reasons": reasons})

    bars = _maps(row.get("fixedActionBars")) or _maps(row.get("fixedActions"))
    if not bars and isinstance(row.get("fixedActionBar"), Mapping):
        bars = [row["fixedActionBar"]]
    for index, bar in enumerate(bars):
        reasons = []
        if _flag(bar, "obscuresContent", "contentObscured") is True or _flag(row, "fixedActionObscuresContent") is True:
            reasons.append("content-obscured")
        if _flag(bar, "keyboardOverlap", "coveredByKeyboard") is True or _flag(row, "keyboardOverlap", "softKeyboardOverlap") is True:
            reasons.append("soft-keyboard-overlap")
        safe_bottom = _first(row, "safeAreaBottom", "safeAreaInsetBottom") or 0
        if _role(width) == "mobile" and safe_bottom > 0 and _flag(bar, "safeAreaApplied", "usesSafeArea") is False:
            reasons.append("safe-area-not-applied")
        if reasons:
            result["fixedActions"].append({"index": index, "safeAreaBottom": safe_bottom, "reasons": reasons})
    return result


def analyze_responsive_experience(
    sources: Sequence[Mapping[str, Any]],
    observed: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Analyse standard and arbitrary viewports without promoting static guesses."""

    observed = observed or {}
    rendered_observed = observed if _has_rendered_authority(observed) else {}
    text = "\n".join(str(item.get("text") or "") for item in sources if str(item.get("path") or "").casefold().endswith(_SUFFIXES))
    profile = _profile(text)
    page_type = _page_type(text, observed)
    rows = _viewports(rendered_observed)
    findings: list[dict[str, Any]] = []

    static_specs = [
        (profile["complexDesktopComposition"] and not profile["hasIntermediateRecomposition"],
         "RESPONSIVE-INTERMEDIATE-RECOMPOSITION-MISSING", "UX1", "页面缺少中间宽度的专门重组",
         "页面只有桌面和手机两种思路，768px 左右仍会停留在拥挤的桌面布局。",
         {"mediaBreakpointsPx": profile["mediaBreakpointsPx"], "containerQueries": profile["containerQueries"]},
         "为平板、分屏和窄桌面定义独立的信息优先级和结构变化。"),
        (bool(profile["noWrapToolbars"]), "RESPONSIVE-BUTTON-GROUP-NOWRAP", "UX2", "操作组没有窄屏收敛策略",
         "工具栏固定为单行，文案变长或空间变窄时按钮会互相挤压。",
         {"selectors": profile["noWrapToolbars"][:8]}, "保留一个主操作，允许次要操作换行或进入更多菜单。"),
        (profile["tables"] > 0 and not profile["tableLocalScrollStrategy"], "RESPONSIVE-TABLE-STRATEGY-MISSING", "UX1",
         "数据表格没有明确的窄屏使用策略",
         "表格会随页面压缩或撑宽，但没有定义关键列、比较方式和局部滚动。",
         {"tableCount": profile["tables"]}, "定义关键列、最小列宽、局部滚动和列表—详情切换。"),
        (profile["fixedBottomAction"] and not profile["safeAreaInsets"], "RESPONSIVE-FIXED-ACTION-SAFE-AREA", "UX1",
         "固定操作区没有适配移动安全区",
         "底部操作栏没有为系统手势区、最后一项内容和软键盘预留空间。",
         "fixed bottom action without safe-area-inset", "同步处理 safe-area、内容占位和软键盘路径。"),
    ]
    for applies, code, severity, title, explanation, evidence, recommendation in static_specs:
        if applies:
            findings.append(_finding(
                code, severity, title, explanation,
                "用户可能看不到或无法操作完成主任务所需的内容。",
                evidence, recommendation,
                ("1440/768/390 三档构图成立", "主任务能力不丢失", "无页面级横向滚动"),
                "medium" if severity == "UX2" else "high", "static-source",
            ))

    oversized = []
    for item in profile["fixedDialogs"]:
        width = re.fullmatch(r"\s*(\d+(?:\.\d+)?)px\s*", item["width"], re.I)
        height = re.fullmatch(r"\s*(\d+(?:\.\d+)?)px\s*", item["height"], re.I)
        if (width and float(width.group(1)) > 390) or (height and float(height.group(1)) > 720):
            oversized.append(item)
    if oversized:
        findings.append(_finding(
            "RESPONSIVE-DIALOG-FIXED-SIZE", "UX1", "弹窗尺寸可能超过移动视口",
            "弹窗使用大号固定像素尺寸，手机、软键盘和放大模式下无法自动收敛。",
            "标题、错误、确认或关闭入口可能停在屏幕外。",
            {"examples": oversized[:6]}, "限制弹窗宽高并建立内部滚动和软键盘适配。",
            ("390px 弹窗完整位于视口内", "标题、当前字段和操作均可达"), "high", "static-source",
        ))

    viewport_results = []
    for row in rows:
        width = row["width"]
        client = _first(row, "clientWidth", "viewportWidth", "innerWidth") or width
        scroll = _first(row, "scrollWidth", "documentScrollWidth", "bodyScrollWidth")
        measured = client is not None and scroll is not None
        issues: list[str] = []
        if measured and scroll > client + 1:
            issues.append("page-horizontal-overflow")
            findings.append(_finding(
                f"RESPONSIVE-PAGE-OVERFLOW-{row['id'].upper()}", "UX1",
                f"{row['id']} 视口出现页面级横向滚动",
                "页面整体比可见区域更宽，用户必须左右拖动才能看到完整任务。",
                "阅读顺序被打断，按钮、字段或导航可能停在屏幕外。",
                {"viewport": row["id"], "clientWidth": client, "scrollWidth": scroll, "overflowPx": round(scroll - client, 2)},
                "让造成溢出的组件重组；只有需要比较的数据区可以局部滚动。",
                ("document.scrollWidth <= clientWidth", "焦点不会移动到页面外"), "high", "rendered-observation",
            ))
        observed_issues = _observed_issues(row)
        labels = {
            "buttons": ("button-squeeze", "按钮被挤压", "操作标签被截断、重叠或缩到难以点击。", "按主次收敛操作并保持至少 44×44px 触控区。"),
            "tables": ("table-unusable", "表格无法可靠使用", "关键列被压缩或丢失，宽内容没有限制在局部滚动区。", "保留比较语义，定义关键列、局部滚动和连续详情视图。"),
            "dialogs": ("dialog-offscreen", "弹窗超出屏幕", "弹窗内容或操作越过视口边界。", "限制弹窗宽高，确保标题、字段、错误和操作可达。"),
            "navigation": ("navigation-collapse", "导航失去可用结构", "导航被截断、换行或隐藏，却没有稳定入口。", "定义各档导航收敛方式并恢复当前位置和焦点。"),
            "fixedActions": ("fixed-action-obstruction", "固定操作区遮挡任务", "固定按钮覆盖内容、软键盘或系统安全区。", "同步处理安全区、软键盘、内容占位和操作栏高度。"),
        }
        for key, (issue, title, explanation, recommendation) in labels.items():
            if observed_issues[key]:
                issues.append(issue)
                findings.append(_finding(
                    f"RESPONSIVE-{issue.upper()}-{row['id'].upper()}", "UX1",
                    f"{row['id']} 视口中的{title}", explanation,
                    "用户可能无法理解、继续或安全退出当前任务。",
                    {"viewport": row["id"], "examples": observed_issues[key][:8]},
                    recommendation, ("问题元素完整可见", "键盘和触控均可完成主任务"),
                    "high", "rendered-observation",
                ))
        viewport_results.append({
            "id": row["id"], "role": _role(width), "width": width, "height": row["height"],
            "geometryObserved": measured, "issues": issues,
            "status": "FAIL" if issues else "PASS" if measured else "NOT_VERIFIED",
        })

    raw_by_role: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        raw_by_role.setdefault(_role(row["width"]), row)
    if all(role in raw_by_role for role in STANDARD_VIEWPORTS):
        signatures = {role: str(raw_by_role[role].get("compositionSignature") or raw_by_role[role].get("layoutSignature") or "") for role in STANDARD_VIEWPORTS}
        columns = {role: _first(raw_by_role[role], "columnCount", "layoutColumns", "visibleColumns") for role in STANDARD_VIEWPORTS}
        signature_holds_at_tablet = bool(
            signatures["desktop"] and signatures["desktop"] == signatures["tablet"]
        )
        columns_equal_all = columns["desktop"] is not None and len(set(columns.values())) == 1
        columns_hold_until_mobile = bool(
            columns["desktop"] is not None and columns["tablet"] == columns["desktop"] and columns["mobile"] not in {None, columns["desktop"]}
        )
        unchanged = signature_holds_at_tablet or columns_equal_all or columns_hold_until_mobile
        if unchanged:
            findings.append(_finding(
                "RESPONSIVE-INTERMEDIATE-OBSERVED-UNCHANGED", "UX1", "768px 仍在使用桌面构图",
                "中间宽度没有重新安排内容，只等到手机宽度才突然切换。",
                "平板、分屏和窄桌面用户承受最拥挤的一档体验。",
                {"signatures": signatures, "columns": columns}, "为 768px 定义独立重组。",
                ("768px 不再是桌面等比压缩", "三档任务能力一致"), "high", "rendered-observation",
            ))

    unique = {item["id"]: item for item in findings}
    findings = sorted(unique.values(), key=lambda item: ({"UX1": 0, "UX2": 1, "UX3": 2}.get(item["severity"], 9), item["id"]))
    rendered = [item for item in findings if item["evidenceMode"] == "rendered-observation"]
    measured_viewports = [item for item in viewport_results if item["geometryObserved"]]
    evidence_mode = "mixed-rendered-and-static" if measured_viewports and len(rendered) != len(findings) else "rendered-observation" if measured_viewports else "static-source"
    status = (
        "FAIL" if any(item["severity"] == "UX1" and item["evidenceMode"] == "rendered-observation" for item in findings)
        else "PASS_WITH_WARNINGS" if findings else "PASS" if measured_viewports else "NOT_VERIFIED"
    )
    result: dict[str, Any] = {
        "schemaVersion": "3.1", "status": status,
        "analysisStatus": "MEASURED" if measured_viewports else "CANDIDATE_ONLY",
        "pageType": page_type, "sourceProfile": profile,
        "standardViewports": {
            role: {"targetWidth": width, "observed": any(item["width"] is not None and abs(item["width"] - width) <= 2 for item in viewport_results)}
            for role, width in STANDARD_VIEWPORTS.items()
        },
        "viewports": viewport_results,
        "compositionPlan": build_composition_plan(page_type["id"], confidence=page_type["confidence"], evidence_mode=evidence_mode),
        "findings": findings,
        "evidenceSummary": {
            "sourceFiles": len(sources), "observedViewportCount": len(rows),
            "geometryViewportCount": len(measured_viewports), "renderedFindingCount": len(rendered),
            "staticCandidateCount": len(findings) - len(rendered),
        },
        "score": max(0, 100 - sum(_COST.get(item["severity"], 1) for item in findings)),
        "claimBoundary": "静态源码发现只代表响应式风险候选；只有 evidenceMode=rendered-observation 的 Finding 能证明对应视口当前存在问题。",
    }
    result["digest"] = digest_json(result)
    return result


__all__ = ["STANDARD_VIEWPORTS", "analyze_responsive_experience", "build_composition_plan"]
