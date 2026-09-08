"""UI Experience Core: business model, pattern, visual system, and state plan."""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from .contracts import digest_json
from .experience_model import build_experience_model
from .interaction_states import build_interaction_contract
from .pattern_library import get_pattern, route_patterns
from .visual_system import build_visual_system, direction_catalog
from .experience_catalog import (
    catalog_metrics, contextual_states, get_component, get_skeleton, route_skeletons,
    select_interactions,
)
from .ux_repair import analyze_ux_sources
from .design_system_map import build_design_system_map
from .experience_quality import evaluate_plan_readiness
from .experience_modernization import build_modernization_strategy
from .experience_engine import build_experience_diagnosis


def build_experience_core(
    business_context: Mapping[str, Any] | None,
    business_model: Mapping[str, Sequence[str]],
    page_modes: Sequence[str],
    observed_profile: Mapping[str, Any],
    *,
    style_override: str | None = None,
    pattern_override: str | None = None,
    skeleton_override: str | None = None,
    sources: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    model = build_experience_model(business_context, business_model, observed_profile, page_modes=page_modes).to_dict()
    patterns = route_patterns(model, page_modes, observed_profile)
    if pattern_override:
        forced = get_pattern(pattern_override).to_dict()
        forced.update({"score": 100, "reasons": ["用户明确指定页面模式"], "penalties": [], "status": "selected", "confidence": "user-confirmed", "selectionMode": "user-override"})
        patterns = [forced] + [item for item in patterns if item.get("id") != pattern_override]
    selected = patterns[0]
    skeletons = route_skeletons(selected["id"], model, observed_profile)
    selected_skeleton = skeletons[0]
    if skeleton_override:
        forced_skeleton = get_skeleton(skeleton_override)
        forced_skeleton.update({"score": 100, "reasons": ["用户明确指定页面骨架"], "selectionMode": "user-override"})
        selected_skeleton = forced_skeleton
        skeletons = [selected_skeleton] + [item for item in skeletons if item.get("id") != skeleton_override]
    visual = build_visual_system(model, selected["id"], override=style_override)
    interaction = build_interaction_contract(model, selected)
    required_states = list(selected_skeleton.get("states") or [item.get("id", "") for item in interaction.get("stateCoverage", [])])
    interaction["contextualStates"] = contextual_states(selected["id"], required_states)
    interaction_intents = list(selected_skeleton.get("interactions") or selected.get("primaryInteractions", []))
    interaction["selectedInteractionPatterns"] = select_interactions(interaction_intents, model)
    source_items = list(sources or [])
    ux_repair = analyze_ux_sources(source_items, observed_profile) if source_items else {"schemaVersion":"1.0","score":None,"findingCount":0,"findings":[],"quickWins":[],"structuralRepairs":[],"principles":[]}
    design_map = build_design_system_map(source_items) if source_items else {"schemaVersion":"1.0","cssFiles":0,"cssVariableCount":0,"metrics":{"tokenReuseRatio":0,"colourTokenRatio":0,"spacingGridCoherence":0,"consistencyScore":0},"semanticAliases":{},"inventory":{},"dtcg":{},"compatibilityCss":"","recommendations":[]}
    modern = _modern_technology_contract(selected)
    implementation = _implementation_plan(selected, visual, interaction, model)
    implementation["selectedSkeleton"] = selected_skeleton["id"]
    implementation["uxRepairPriorities"] = [item.get("id") for item in ux_repair.get("quickWins", [])[:5]] + [item.get("id") for item in ux_repair.get("structuralRepairs", [])[:5]]
    implementation["designSystemCompatibility"] = design_map.get("metrics", {})
    plan: dict[str, Any] = {
        "schemaVersion":"3.0", "experienceModel":model, "selectedPattern":selected,
        "selectedSkeleton":selected_skeleton, "skeletonAlternatives":skeletons[1:],
        "patternAlternatives":patterns[1:], "visualSystem":visual, "interactionContract":interaction,
        "uxRepairPlan":ux_repair, "projectDesignSystem":design_map,
        "modernTechnology":modern, "implementationPlan":implementation,
        "styleCatalog":direction_catalog(),
        "library": {
            "metrics":catalog_metrics(),
            "selectedComponents":[get_component(component_id) for component_id in selected_skeleton.get("components", [])],
            "catalogArtifact":"experience-library.json",
        },
        "acceptance": {
            "product":["主任务更易理解", "步骤不增加", "信息优先级符合业务", "高风险动作被合理隔离"],
            "visual":["移动、中间、桌面构图成立", "字体和状态清晰", "设计方向与项目语言兼容", "动效支持 reduced motion"],
            "interaction":interaction["acceptanceCriteria"],
            "evidence":["同条件 before/after", "一个关键旅程", "适用状态验证", "人工八维评审", "未验证项明确"],
        },
    }
    plan["experienceDiagnosis"] = build_experience_diagnosis(
        source_items,
        model,
        page_modes=page_modes,
    )
    plan["modernizationStrategy"] = build_modernization_strategy(plan)
    plan["qualityReadiness"] = evaluate_plan_readiness(plan)
    plan["experienceDigest"] = digest_json(plan)
    return plan


def _modern_technology_contract(pattern: Mapping[str, Any]) -> dict[str, Any]:
    requested = list(pattern.get("modernFeatures", []))
    support = {
        "container-queries":{"use":"组件按所在容器重组，而非只依赖 viewport", "fallback":"媒体查询和单列流", "policy":"默认启用"},
        "view-transitions":{"use":"列表—详情、主题和状态切换保持连续性", "fallback":"即时切换", "policy":"特性检测后启用"},
        "scroll-state-queries":{"use":"sticky 区域进入固定状态后改变边界和密度", "fallback":"常驻边框/阴影", "policy":"渐进增强"},
        "scroll-driven-animation":{"use":"长页面章节和进度的克制反馈", "fallback":"无动画静态提示", "policy":"仅非关键内容"},
        "anchor-positioning":{"use":"帮助、筛选和弹出层相对触发点定位", "fallback":"普通绝对定位或 dialog", "policy":"特性检测"},
        "popover-api":{"use":"非模态上下文帮助和轻量操作", "fallback":"dialog 或内联区域", "policy":"不用于关键确认"},
    }
    return {"features":[{"id":feature, **support.get(feature, {"use":"按需", "fallback":"基础 HTML/CSS", "policy":"实验"})} for feature in requested], "principles":["现代技术必须有退化路径", "不为新技术牺牲可访问性", "不在高密度数据区滥用透明和动效", "默认尊重 reduced motion"]}


def _implementation_plan(pattern: Mapping[str, Any], visual: Mapping[str, Any], interaction: Mapping[str, Any], model: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "phase1Structure":["确认内容优先级和页面骨架", f"实施 {pattern['name']} 的桌面/中间/移动构图", "保留业务对象、字段和操作语义"],
        "phase2Visual":[f"应用 {visual['directionName']} Token", "建立字体、表面、边界、状态和密度规则", "先实现纯色稳定层，再对导航/控制层渐进增强材质"],
        "phase3Interaction":["实现主操作和反馈合同", "覆盖适用状态和错误恢复", "恢复筛选、选中、滚动、焦点和草稿"],
        "phase4Validation":["浏览器三档视口", "关键旅程", "状态切换", "人工视觉评审", "真实用户任务指标"],
        "controlPoints":["视觉方向可覆盖", "模式可退回备选方案", "现代 CSS 特性均有 fallback", "高风险动作逐项批准", "不在未验证时宣称改善"],
        "applicability": {"confidence":model.get("confidence"), "unresolvedQuestions":model.get("unresolvedQuestions", [])},
    }
