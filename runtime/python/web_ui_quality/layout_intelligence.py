"""Deterministic layout intelligence for user-visible Web experience problems.

The analyser consumes bounded source snippets plus optional rendered observations.
Static source evidence and rendered geometry stay separate so a CSS heuristic can
never be promoted to Browser proof.
"""
from __future__ import annotations

from collections import Counter
import re
from typing import Any, Mapping, Sequence

from .contracts import digest_json


_CSS_BLOCK = re.compile(r"(?is)(?P<selector>[^{}]+)\{(?P<body>[^{}]*)\}")
_DECLARATION = re.compile(r"(?i)(?P<name>-{0,2}[a-z][\w-]*)\s*:\s*(?P<value>[^;{}]+)")
_FIXED_SIZE = re.compile(r"(?i)^\s*(?P<number>\d+(?:\.\d+)?)px\s*$")
_SPACING_PROPERTIES = {
    "gap", "row-gap", "column-gap", "padding", "padding-inline", "padding-block",
    "padding-left", "padding-right", "padding-top", "padding-bottom", "margin",
    "margin-inline", "margin-block", "margin-left", "margin-right", "margin-top", "margin-bottom",
}
_SEVERITY_COST = {"UX1": 12, "UX2": 7, "UX3": 3}


def _texts(sources: Sequence[Mapping[str, Any]], suffixes: tuple[str, ...]) -> str:
    return "\n".join(
        str(item.get("text") or "")
        for item in sources
        if str(item.get("path") or "").casefold().endswith(suffixes)
    )


def _number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result == result else None



def _has_rendered_authority(observed: Mapping[str, Any]) -> bool:
    raw = observed.get("evidenceTier") or observed.get("evidenceMode")
    value = str(raw or "").strip().casefold().replace("_", "-")
    return value in {"browser-measured", "rendered-observation", "mixed-rendered-and-static"}


def _normalise_viewports(observed: Mapping[str, Any]) -> list[dict[str, Any]]:
    value = observed.get("viewports")
    rows: list[dict[str, Any]] = []
    if isinstance(value, Mapping):
        for name, item in value.items():
            if isinstance(item, Mapping):
                rows.append({"id": str(name), **dict(item)})
    elif isinstance(value, list):
        for index, item in enumerate(value):
            if isinstance(item, Mapping):
                rows.append({"id": str(item.get("id") or item.get("name") or f"viewport-{index + 1}"), **dict(item)})
    return rows


def _finding(
    code: str,
    *,
    severity: str,
    title: str,
    explanation: str,
    impact: str,
    evidence: Any,
    recommendation: str,
    modern: str,
    fallback: str,
    verification: Sequence[str],
    confidence: str,
    evidence_mode: str,
) -> dict[str, Any]:
    return {
        "id": code,
        "severity": severity,
        "category": "layout",
        "title": title,
        "userExplanation": explanation,
        "userImpact": impact,
        "evidence": evidence,
        "recommendation": recommendation,
        "implementation": {"modern": modern, "fallback": fallback},
        "verification": list(verification),
        "confidence": confidence,
        "evidenceMode": evidence_mode,
    }


def _source_metrics(css: str) -> dict[str, Any]:
    flex = grid = absolute = overflow_hidden = 0
    container_queries = len(re.findall(r"(?i)@container\b", css))
    media_queries = len(re.findall(r"(?i)@media\b", css))
    fixed: list[dict[str, Any]] = []
    spacing: list[float] = []
    alignment: Counter[str] = Counter()
    for block in _CSS_BLOCK.finditer(css):
        selector = " ".join(block.group("selector").split())[:160]
        for match in _DECLARATION.finditer(block.group("body")):
            name = match.group("name").casefold()
            value = match.group("value").strip()
            lower = value.casefold()
            if name == "display" and re.search(r"\b(?:inline-)?flex\b", lower):
                flex += 1
            if name == "display" and re.search(r"\b(?:inline-)?grid\b", lower):
                grid += 1
            if name == "position" and lower == "absolute":
                absolute += 1
            if name == "overflow" and lower == "hidden":
                overflow_hidden += 1
            if name in {"align-items", "justify-content", "text-align"}:
                alignment[f"{name}:{lower}"] += 1
            if name in {"width", "min-width"}:
                size = _FIXED_SIZE.match(value)
                if size and float(size.group("number")) >= 720:
                    fixed.append({"selector": selector, "property": name, "value": value})
            if name in _SPACING_PROPERTIES:
                for number in re.findall(r"(?i)(\d+(?:\.\d+)?)px", value):
                    parsed = float(number)
                    if 0 < parsed <= 160:
                        spacing.append(parsed)
    unique_spacing = sorted(set(spacing))
    off_grid = [value for value in unique_spacing if value % 4 != 0]
    return {
        "flexContainers": flex,
        "gridContainers": grid,
        "containerQueries": container_queries,
        "mediaQueries": media_queries,
        "absolutePositionCount": absolute,
        "overflowHiddenCount": overflow_hidden,
        "largeFixedSizes": fixed,
        "spacingValuesPx": unique_spacing,
        "offGridSpacingValuesPx": off_grid,
        "alignmentPatterns": dict(sorted(alignment.items())),
    }


def analyze_layout(
    sources: Sequence[Mapping[str, Any]],
    observed: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a layout model and explain user-visible problems in plain language."""

    observed = observed or {}
    rendered_observed = observed if _has_rendered_authority(observed) else {}
    css = _texts(sources, (".css", ".scss", ".sass", ".less", ".html", ".htm", ".vue", ".svelte", ".jsx", ".tsx"))
    metrics = _source_metrics(css)
    findings: list[dict[str, Any]] = []
    viewport_results: list[dict[str, Any]] = []

    fixed = metrics["largeFixedSizes"]
    if fixed:
        findings.append(_finding(
            "LAYOUT-FIXED-WIDTH",
            severity="UX1",
            title="固定宽度让页面无法随可用空间重组",
            explanation="页面把主要区域锁在较大的像素宽度上，窄屏时容易被裁切，宽屏时也无法合理分配空间。",
            impact="用户可能需要横向滚动，或在中间宽度看到拥挤、错位和被遮挡的操作。",
            evidence={"count": len(fixed), "examples": fixed[:5]},
            recommendation="为主区域定义可伸缩容器、合理最大宽度和明确的窄屏重组，而不是等比缩小桌面页面。",
            modern="使用 Grid minmax()、clamp()、max-inline-size 与组件级 Container Queries。",
            fallback="使用 Flex/Grid、百分比宽度和媒体查询切换单列或局部滚动。",
            verification=("320/390px 无页面级横向滚动", "768px 有明确重组", "1440px 内容不过度拉伸"),
            confidence="high",
            evidence_mode="static-source",
        ))

    if metrics["absolutePositionCount"] >= 6:
        findings.append(_finding(
            "LAYOUT-ABSOLUTE-OVERUSE",
            severity="UX1",
            title="页面依赖绝对定位维持排版",
            explanation="多个主要区域靠坐标摆放，看似对齐，但内容变长、字体放大或设备变化后关系会断裂。",
            impact="用户会看到文字覆盖、控件漂移、空白异常，放大页面时尤其明显。",
            evidence={"absolutePositionCount": metrics["absolutePositionCount"]},
            recommendation="让主要区域回到正常文档流，用网格和弹性布局表达结构关系。",
            modern="以 CSS Grid、subgrid 和容器查询管理区域关系；绝对定位只用于局部装饰和标记。",
            fallback="使用 Flex/Grid 基础布局与媒体查询。",
            verification=("200% 缩放无重叠", "长文案不覆盖相邻控件", "三档视口结构稳定"),
            confidence="high",
            evidence_mode="static-source",
        ))

    spacing = metrics["spacingValuesPx"]
    off_grid = metrics["offGridSpacingValuesPx"]
    if len(spacing) >= 9 and len(off_grid) / max(1, len(spacing)) >= 0.35:
        findings.append(_finding(
            "LAYOUT-SPACING-RHYTHM",
            severity="UX2",
            title="页面间距缺少稳定节奏",
            explanation="相近模块使用了过多不同间距，区域之间的亲疏关系不清楚，页面显得零散。",
            impact="用户需要额外判断哪些内容属于同一任务，扫读速度和整体秩序感下降。",
            evidence={"uniqueSpacingValuesPx": spacing[:30], "offGridRatio": round(len(off_grid) / len(spacing), 3)},
            recommendation="把间距收敛到少量语义级别，并让组件内部、模块之间和页面分区形成递进关系。",
            modern="使用响应式 spacing tokens 与 clamp()，由容器密度选择 token。",
            fallback="使用 4px/8px 基准的固定语义间距变量。",
            verification=("同类组件使用同一间距 token", "分组关系仅看间距也可理解", "移动和桌面节奏一致"),
            confidence="medium",
            evidence_mode="static-source",
        ))

    body_overflow_hidden = bool(re.search(r"(?is)(?:html|body)[^{]*\{[^}]*overflow\s*:\s*hidden", css))
    if body_overflow_hidden:
        findings.append(_finding(
            "LAYOUT-BODY-OVERFLOW-HIDDEN",
            severity="UX1",
            title="页面级内容可能被直接裁掉",
            explanation="根页面关闭了溢出显示，超出视口的内容可能既不可见也无法滚动到。",
            impact="小屏、缩放、错误提示或长内容状态下，用户可能无法看到并完成关键操作。",
            evidence="html/body overflow:hidden",
            recommendation="只在明确的局部容器管理滚动，并为固定栏和弹层保留内容空间。",
            modern="使用 dvh、滚动容器与 overscroll-behavior 管理应用壳层。",
            fallback="恢复页面滚动，仅对局部媒体/画布裁切。",
            verification=("400% 缩放内容仍可达", "软键盘打开后当前字段可见", "长错误信息不被裁切"),
            confidence="high",
            evidence_mode="static-source",
        ))

    for row in _normalise_viewports(rendered_observed):
        name = str(row.get("id"))
        width = _number(row.get("clientWidth") or row.get("viewportWidth") or row.get("width"))
        scroll_width = _number(row.get("scrollWidth"))
        content_width = _number(row.get("contentWidth") or row.get("mainContentWidth"))
        min_gap = _number(row.get("minimumGapPx") or row.get("minGapPx"))
        alignment_deviation = _number(row.get("alignmentDeviationPx"))
        issues: list[str] = []
        geometry = width is not None and scroll_width is not None
        if geometry and scroll_width > width + 1:
            issues.append("horizontal-overflow")
            findings.append(_finding(
                f"LAYOUT-HORIZONTAL-OVERFLOW-{name.upper()}",
                severity="UX1",
                title=f"{name} 视口出现页面级横向滚动",
                explanation="页面内容比可见区域更宽，用户需要左右拖动才能看到完整信息。",
                impact="阅读顺序被打断，关键按钮或字段可能停留在屏幕外，移动端操作尤其困难。",
                evidence={"viewport": name, "clientWidth": width, "scrollWidth": scroll_width, "overflowPx": round(scroll_width - width, 2)},
                recommendation="定位造成溢出的拥有者，让组件重组或只让确需比较的数据区局部滚动。",
                modern="使用 minmax(0,1fr)、overflow-wrap:anywhere、容器查询和尺寸约束。",
                fallback="媒体查询切换单列；宽表仅在自身容器滚动。",
                verification=("document scrollWidth <= clientWidth", "键盘焦点不会滚到不可见页面外", "表格滚动不带动整页"),
                confidence="high",
                evidence_mode="rendered-observation",
            ))
        if width and content_width:
            ratio = content_width / width
            if width >= 1200 and ratio > 0.94:
                issues.append("content-too-wide")
                findings.append(_finding(
                    f"LAYOUT-CONTENT-TOO-WIDE-{name.upper()}",
                    severity="UX2",
                    title="主要内容在大屏上拉得过宽",
                    explanation="内容几乎铺满整个大屏，文本行、表格扫描和模块关系变得松散。",
                    impact="用户视线移动距离增加，更难比较相关字段，也更容易错过右侧状态和操作。",
                    evidence={"viewport": name, "contentWidth": content_width, "viewportWidth": width, "ratio": round(ratio, 3)},
                    recommendation="为阅读内容设置最大宽度；数据密集页面用有意义的增列或主从分栏利用空间。",
                    modern="使用 clamp()、max-inline-size 与自适应 Grid 轨道。",
                    fallback="居中 max-width 容器或固定的主从分栏。",
                    verification=("正文行长适宜", "相关字段处于同一视觉范围", "大屏新增空间承载有用上下文"),
                    confidence="high",
                    evidence_mode="rendered-observation",
                ))
            elif width >= 1200 and ratio < 0.55:
                issues.append("space-waste")
                findings.append(_finding(
                    f"LAYOUT-SPACE-WASTE-{name.upper()}",
                    severity="UX2",
                    title="大屏空间没有转化为更高的任务效率",
                    explanation="页面仍保持手机式单列，大片空白没有承载比较信息、上下文或下一步。",
                    impact="专业用户需要更多滚动和页面切换，桌面优势没有被利用。",
                    evidence={"viewport": name, "contentWidth": content_width, "viewportWidth": width, "ratio": round(ratio, 3)},
                    recommendation="仅在任务需要时增加列、详情面板、摘要或辅助上下文，保留可读行长。",
                    modern="使用自适应 Grid 与容器查询逐步展开信息。",
                    fallback="在桌面媒体查询中增加主从分栏。",
                    verification=("桌面减少滚动或上下文切换", "内容仍保持清晰焦点", "移动端核心任务不丢失"),
                    confidence="high",
                    evidence_mode="rendered-observation",
                ))
        if min_gap is not None and min_gap < 8:
            issues.append("crowded")
            findings.append(_finding(
                f"LAYOUT-CROWDED-{name.upper()}",
                severity="UX2",
                title=f"{name} 视口中的操作和内容过于拥挤",
                explanation="相邻控件之间缺少足够间隔，页面难以扫读，触控时也更容易误操作。",
                impact="用户判断分组变慢，按钮和筛选项容易点错。",
                evidence={"viewport": name, "minimumGapPx": min_gap},
                recommendation="优先保留主动作，把低频动作收进更多菜单，并为可触控控件留出清晰间隔。",
                modern="使用密度 token 与容器查询切换工具栏布局。",
                fallback="在窄屏换行或纵向排列操作。",
                verification=("操作组最小间隔达到项目 token", "移动端无动作挤压", "主动作始终可识别"),
                confidence="high",
                evidence_mode="rendered-observation",
            ))
        if alignment_deviation is not None and alignment_deviation > 4:
            issues.append("misalignment")
            findings.append(_finding(
                f"LAYOUT-ALIGNMENT-{name.upper()}",
                severity="UX2",
                title="跨区域对齐线不一致",
                explanation="标题、内容和操作没有共享稳定的起始线，页面看起来缺乏秩序。",
                impact="用户扫读时需要不断重新寻找起点，信息层级更难理解。",
                evidence={"viewport": name, "alignmentDeviationPx": alignment_deviation},
                recommendation="建立页面栅格和共享容器，让标题、正文、表格和操作落在同一组对齐线上。",
                modern="使用 Grid/subgrid 共享列轨道。",
                fallback="复用容器宽度、padding 和列模板变量。",
                verification=("主要区域起始线偏差不超过项目阈值", "长内容不破坏对齐"),
                confidence="high",
                evidence_mode="rendered-observation",
            ))
        viewport_results.append({
            "id": name,
            "width": width,
            "scrollWidth": scroll_width,
            "contentWidth": content_width,
            "geometryObserved": geometry,
            "issues": issues,
            "status": "FAIL" if issues else "PASS" if geometry else "NOT_VERIFIED",
        })

    findings.sort(key=lambda item: ({"UX1": 0, "UX2": 1, "UX3": 2}.get(item["severity"], 9), item["id"]))
    result: dict[str, Any] = {
        "schemaVersion": "3.1",
        "status": "FAIL" if any(item["severity"] == "UX1" for item in findings) else "PASS_WITH_WARNINGS" if findings else "PASS",
        "model": {
            "layoutSystems": {"flex": metrics["flexContainers"], "grid": metrics["gridContainers"]},
            "containerStrategy": {
                "containerQueries": metrics["containerQueries"],
                "mediaQueries": metrics["mediaQueries"],
            },
            "sizing": {"largeFixedSizes": fixed},
            "spacing": {
                "valuesPx": spacing,
                "offGridValuesPx": off_grid,
            },
            "alignment": metrics["alignmentPatterns"],
            "overflow": {"hiddenDeclarations": metrics["overflowHiddenCount"], "rootHidden": body_overflow_hidden},
        },
        "viewports": viewport_results,
        "findings": findings,
        "score": max(0, 100 - sum(_SEVERITY_COST.get(item["severity"], 1) for item in findings)),
        "claimBoundary": "静态源码只能识别布局风险；只有带 geometryObserved=true 的视口记录能证明当前渲染几何。",
    }
    result["digest"] = digest_json(result)
    return result


__all__ = ["analyze_layout"]
