"""Evidence-weighted UI product direction ranking.

The scorer combines rendered/static page facts with explicitly supplied business
context.  It never invents research: missing context is preserved as unknown and
lowers confidence instead of being silently guessed.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence


@dataclass(frozen=True, slots=True)
class PageProfile:
    tables: int = 0
    rows: int = 0
    columns: int = 0
    forms: int = 0
    controls: int = 0
    navs: int = 0
    details: int = 0
    metrics: int = 0
    operations: int = 0
    states: int = 0
    has_search: bool = False
    has_filter: bool = False
    has_pagination: bool = False
    has_steps: bool = False
    has_destructive_action: bool = False
    mobile_evidence: bool = False


def profile_from_facts(facts: Sequence[Any], model: Mapping[str, list[str]], css_text: str) -> PageProfile:
    tags: dict[str, int] = {}
    rows = columns = controls = metrics = 0
    text = ""
    for item in facts:
        for tag, count in getattr(item, "tags", {}).items():
            tags[tag] = tags.get(tag, 0) + count
        rows += getattr(item, "table_rows", 0)
        columns = max(columns, getattr(item, "max_table_columns", 0))
        controls += len(getattr(item, "controls", []))
        metrics += len(getattr(item, "metrics", []))
        text += " " + " ".join(getattr(item, "text", []))
    operations = {value.casefold() for value in model.get("operations", [])}
    lower = text.casefold()
    return PageProfile(
        tables=tags.get("table", 0), rows=rows, columns=columns,
        forms=tags.get("form", 0), controls=controls,
        navs=tags.get("nav", 0) + tags.get("aside", 0),
        details=tags.get("dl", 0) + tags.get("details", 0), metrics=metrics,
        operations=len(operations), states=len(model.get("states", [])),
        has_search=any(word in lower or word in operations for word in ("search", "搜索", "查询")),
        has_filter=any(word in lower or word in operations for word in ("filter", "筛选", "过滤")),
        has_pagination=any(word in lower for word in ("上一页", "下一页", "pagination", "page ")),
        has_steps=any(word in lower for word in ("下一步", "上一步", "step", "步骤")),
        has_destructive_action=any(word in lower for word in ("删除", "作废", "解绑", "delete", "remove", "revoke")),
        mobile_evidence="@media" in css_text.casefold() or "@container" in css_text.casefold(),
    )


def _candidate(name: str, score: int, reasons: list[str], risks: list[str]) -> dict[str, Any]:
    return {"name": name, "score": score, "reasons": reasons, "risks": risks, "businessAdjustments": []}


def _text(context: Mapping[str, Any], key: str) -> str:
    value = context.get(key)
    return str(value).strip().casefold() if value is not None else ""


def _items(context: Mapping[str, Any], key: str) -> list[str]:
    value = context.get(key, [])
    return [str(item).strip().casefold() for item in value if str(item).strip()] if isinstance(value, list) else []


def _adjust(candidate: dict[str, Any], points: int, reason: str) -> None:
    candidate["score"] += points
    candidate["businessAdjustments"].append({"points": points, "reason": reason})
    candidate["reasons"].append(reason)


def _apply_business_context(candidates: list[dict[str, Any]], context: Mapping[str, Any]) -> None:
    if not context or context.get("evidenceLevel") == "not_provided":
        return
    frequency = _text(context, "frequency")
    environment = _text(context, "environment")
    task = _text(context, "primaryTask")
    success = _text(context, "successMetric")
    pain = " ".join(_items(context, "knownPainPoints"))
    risks = " ".join(_items(context, "highRiskActions"))

    for item in candidates:
        name = item["name"]
        if any(token in frequency for token in ("高频", "每天", "每日", "频繁", "high", "daily")):
            if any(token in name for token in ("主从", "单页", "任务队列")):
                _adjust(item, 10, "业务上下文表明这是高频任务，应减少跳转与重复输入")
            if "独立详情" in name or "分步" in name:
                _adjust(item, -6, "高频任务不宜无证据增加页面往返或步骤")
        if any(token in frequency for token in ("低频", "偶尔", "monthly", "rare")):
            if "分步" in name or "独立详情" in name:
                _adjust(item, 5, "低频任务可接受更明确的引导与独立上下文")
        if any(token in environment for token in ("移动", "现场", "户外", "单手", "mobile", "field")):
            if "卡片" in name or "分步" in name or "任务队列" in name:
                _adjust(item, 10, "现场或移动环境要求更大的触控目标和更少并行信息")
            if "主从" in name:
                _adjust(item, -5, "移动环境下主从布局必须退化为清晰的视图切换")
        if any(token in environment for token in ("桌面", "办公室", "鼠标", "键盘", "desktop")):
            if "主从" in name or "单页" in name or "分析图表" in name:
                _adjust(item, 5, "桌面办公环境支持更高密度比较与并行上下文")
        if risks:
            if "拆分查看、编辑与审批" in name or "独立详情" in name:
                _adjust(item, 12, "已提供高风险操作，应隔离确认、权限与审计上下文")
            if "单页" in name or "主从" in name:
                _adjust(item, -4, "高风险操作与高频浏览混合时需要更强隔离")
        if any(token in task + " " + pain for token in ("比较", "核对", "批量", "compare", "scan")):
            if "主从" in name or "单页" in name:
                _adjust(item, 8, "核心任务包含比较或核对，应保留稳定的上下文和扫描效率")
            if "卡片" in name:
                _adjust(item, -7, "卡片会降低结构化横向比较效率")
        if any(token in task + " " + pain for token in ("深度阅读", "分享", "复杂编辑", "review", "share")):
            if "独立详情" in name:
                _adjust(item, 12, "核心任务需要深度阅读、分享或复杂编辑")
        if any(token in success for token in ("时间", "速度", "效率", "time", "speed")):
            if "主从" in name or "单页" in name or "任务队列" in name:
                _adjust(item, 7, "成功指标强调处理时间或效率")
        if any(token in success for token in ("错误", "准确", "合规", "error", "accuracy", "compliance")):
            if "分步" in name or "拆分" in name or "独立详情" in name:
                _adjust(item, 7, "成功指标强调准确性、错误率或合规性")


def rank_directions(
    page_modes: Sequence[str],
    profile: PageProfile,
    business_context: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    if "列表和详情" in page_modes:
        split_score = 45
        split_reasons = ["检测到结构化记录页面"]
        if profile.has_search or profile.has_filter:
            split_score += 15; split_reasons.append("存在高频搜索或筛选")
        if profile.rows >= 4 or profile.columns >= 4:
            split_score += 15; split_reasons.append("存在多记录或多字段比较需求")
        if profile.details:
            split_score += 15; split_reasons.append("页面已存在详情语义")
        if profile.mobile_evidence:
            split_score += 5; split_reasons.append("项目已有响应式基础")
        candidates.append(_candidate("列表—详情主从工作台", split_score, split_reasons,
            ["详情内容过长时需升级为独立详情页", "移动端必须切换视图而非压缩双栏"]))
        route_score = 38 + min(profile.details * 12, 24)
        route_reasons = ["独立路由适合深度阅读、分享和复杂编辑"]
        if profile.controls >= 8:
            route_score += 18; route_reasons.append("详情交互或字段较多")
        if profile.rows <= 2:
            route_score += 8; route_reasons.append("连续横向比较需求较弱")
        candidates.append(_candidate("独立详情路由", route_score, route_reasons,
            ["会增加高频返回成本", "需要明确保留筛选、分页和滚动上下文"]))
        card_score = 30
        card_reasons = ["卡片适合单条差异大且主操作突出的记录"]
        if profile.columns <= 3:
            card_score += 18; card_reasons.append("字段数量较少")
        if profile.mobile_evidence:
            card_score += 10; card_reasons.append("移动端是明确适配目标")
        if profile.rows > 8 or profile.columns > 5:
            card_score -= 15
        candidates.append(_candidate("优先字段卡片列表", card_score, card_reasons,
            ["不适合高密度横向比较", "不能把所有表格字段机械搬入卡片"]))
    elif "表单和向导" in page_modes:
        segmented = 48 + min(profile.controls, 12)
        segmented_reasons = ["表单字段需要按用户决策分组"]
        if not profile.has_steps:
            segmented += 12; segmented_reasons.append("未观察到严格顺序依赖")
        candidates.append(_candidate("单页分段任务表单", segmented, segmented_reasons,
            ["字段过多时需要章节导航", "条件字段必须保持焦点和错误定位"]))
        candidates.append(_candidate("分步向导", 42 + (24 if profile.has_steps else 0) + (8 if profile.controls >= 10 else 0),
            ["适合具有明确顺序和阶段结果的流程"], ["不应把可整体比较的字段强制拆散", "必须保留失败恢复与进度"]))
        candidates.append(_candidate("拆分查看、编辑与审批页面", 35 + (20 if profile.has_destructive_action else 0),
            ["角色或高风险操作混杂时应分离认知任务"], ["会扩大路由和权限验证范围"]))
    elif "Dashboard" in page_modes or "应用外壳" in page_modes:
        candidates.extend([
            _candidate("状态—异常—任务优先工作台", 70 + min(profile.metrics, 10),
                ["仪表盘应先回答当前情况与下一项工作", "指标需要时间范围和行动上下文"], ["避免同权重 KPI 卡片堆叠"]),
            _candidate("模块导航与任务队列分区", 58 + min(profile.navs * 5, 15),
                ["应用外壳需要稳定当前位置和高频入口"], ["中间宽度可能出现侧栏与内容挤压"]),
            _candidate("分析图表优先页面", 35 + min(profile.metrics * 4, 20),
                ["仅在趋势分析是首要任务时成立"], ["可能掩盖待处理任务和异常"]),
        ])
    else:
        candidates.extend([
            _candidate("项目内最小页面优化", 72, ["当前证据不足以支持结构性重做", "优先修复层级、状态和可达性"], ["仍需 Browser 证明真实改善"]),
            _candidate("局部信息架构重组", 55 + min(profile.operations * 3, 15), ["当多个操作竞争时需要重新排序与分组"], ["必须保护业务字段与流程"]),
            _candidate("整体视觉模板替换", 18, ["仅在项目没有可复用设计语言时考虑"], ["项目感弱、业务回归范围大"]),
        ])

    _apply_business_context(candidates, business_context or {})
    ranked = sorted(candidates, key=lambda item: (-item["score"], item["name"]))
    top = ranked[0]["score"] if ranked else 0
    second = ranked[1]["score"] if len(ranked) > 1 else 0
    context_provided = bool(business_context and business_context.get("evidenceLevel") == "provided")
    gap = top - second
    confidence = "high" if gap >= 20 and context_provided else "medium" if gap >= 8 else "low"
    for index, item in enumerate(ranked):
        item["status"] = "selected" if index == 0 else "rejected"
        item["confidence"] = confidence if index == 0 else None
        item["reason"] = "；".join(item.pop("reasons"))
        item["businessContextUsed"] = context_provided
    return ranked
