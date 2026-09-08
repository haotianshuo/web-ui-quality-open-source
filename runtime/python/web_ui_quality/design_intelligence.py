"""Aesthetic candidate generation and ranking for enterprise UI modernisation.

The engine is deterministic and explainable.  It creates materially different
composition, typography, surface, motion, and navigation directions instead of
random colour swaps.  It does not claim human-designer equivalence; candidates
remain subject to Browser rendering and preference review.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from typing import Any, Iterable, Mapping

_ARCHETYPES: dict[str, dict[str, Any]] = {
    "calm-precision": {
        "name": "Calm Precision", "tone": ["reliable", "quiet", "high-trust"],
        "composition": "strict-grid-with-progressive-disclosure", "navigation": "stable-left-rail",
        "typography": {"character": "neutral-humanist", "contrast": "moderate", "numeric": "tabular"},
        "surface": "solid-layered", "radius": "medium", "motion": "short-functional",
        "iconography": "outline-consistent", "dataViz": "semantic-low-saturation",
        "signature": "calm focus ring and context-preserving detail panel",
        "bestFor": ["enterprise", "regulated", "operations", "professional"],
    },
    "spatial-clarity": {
        "name": "Spatial Clarity", "tone": ["premium", "minimal", "content-first"],
        "composition": "large-whitespace-with-floating-controls", "navigation": "adaptive-top-and-context-rail",
        "typography": {"character": "modern-grotesk", "contrast": "high", "numeric": "proportional"},
        "surface": "controlled-translucency", "radius": "large", "motion": "continuous-spatial",
        "iconography": "fine-outline", "dataViz": "single-accent-with-depth",
        "signature": "controls visually detach from content without obscuring it",
        "bestFor": ["executive", "content", "premium", "low-density"],
    },
    "vibrant-tech": {
        "name": "Vibrant Tech", "tone": ["modern", "energetic", "clear"],
        "composition": "modular-dashboard-with-brand-focus", "navigation": "compact-app-shell",
        "typography": {"character": "geometric-sans", "contrast": "high", "numeric": "tabular"},
        "surface": "crisp-solid", "radius": "small-medium", "motion": "responsive-spring-light",
        "iconography": "duotone-selective", "dataViz": "multi-accent-semantic",
        "signature": "brand focus is concentrated in status and action, not everywhere",
        "bestFor": ["technology", "growth", "saas", "consumer-enterprise"],
    },
    "editorial-data": {
        "name": "Editorial Data", "tone": ["authoritative", "analytical", "readable"],
        "composition": "asymmetric-reporting-grid", "navigation": "section-index-and-sticky-summary",
        "typography": {"character": "editorial-sans-serif-pair", "contrast": "very-high", "numeric": "tabular"},
        "surface": "paper-like", "radius": "small", "motion": "subtle-reveal",
        "iconography": "minimal-symbolic", "dataViz": "ink-first-accessible",
        "signature": "narrative hierarchy turns data into decisions",
        "bestFor": ["analytics", "education", "research", "finance"],
    },
    "kinetic-operations": {
        "name": "Kinetic Operations", "tone": ["fast", "dense", "commanding"],
        "composition": "multi-pane-command-center", "navigation": "keyboard-command-and-rail",
        "typography": {"character": "compact-industrial", "contrast": "high", "numeric": "tabular"},
        "surface": "dense-solid", "radius": "small", "motion": "micro-feedback-only",
        "iconography": "compact-functional", "dataViz": "alert-priority",
        "signature": "keyboard-first focus and immediate operational feedback",
        "bestFor": ["logistics", "manufacturing", "support", "high-frequency"],
    },
    "tactile-field": {
        "name": "Tactile Field", "tone": ["robust", "clear", "outdoor"],
        "composition": "single-task-stack-with-bottom-actions", "navigation": "step-and-next-task",
        "typography": {"character": "high-legibility", "contrast": "very-high", "numeric": "tabular"},
        "surface": "high-contrast-solid", "radius": "medium", "motion": "state-confirmation",
        "iconography": "filled-high-recognition", "dataViz": "minimal-status",
        "signature": "single-hand operation with offline and sync confidence",
        "bestFor": ["mobile-field", "warehouse", "maintenance", "outdoor"],
    },
    "warm-service": {
        "name": "Warm Service", "tone": ["helpful", "human", "reassuring"],
        "composition": "guided-content-with-supportive-summary", "navigation": "step-and-help",
        "typography": {"character": "humanist", "contrast": "moderate-high", "numeric": "proportional"},
        "surface": "soft-layered", "radius": "large", "motion": "gentle-feedback",
        "iconography": "rounded-outline", "dataViz": "soft-semantic",
        "signature": "explanations appear before errors and decisions",
        "bestFor": ["education", "health-service", "public-service", "novice"],
    },
    "neo-industrial": {
        "name": "Neo Industrial", "tone": ["technical", "durable", "distinct"],
        "composition": "exposed-grid-and-strong-dividers", "navigation": "rail-with-machine-status",
        "typography": {"character": "industrial-sans-mono-accent", "contrast": "high", "numeric": "tabular"},
        "surface": "matte-technical", "radius": "minimal", "motion": "mechanical-short",
        "iconography": "technical-line", "dataViz": "signal-colour",
        "signature": "machine-like status clarity without decorative noise",
        "bestFor": ["manufacturing", "iot", "engineering", "infrastructure"],
    },
    "luminous-ai": {
        "name": "Luminous AI", "tone": ["intelligent", "collaborative", "future-facing"],
        "composition": "conversation-canvas-with-artifact-rail", "navigation": "workspace-switcher",
        "typography": {"character": "clean-modern", "contrast": "high", "numeric": "proportional"},
        "surface": "layered-glow-restrained", "radius": "medium-large", "motion": "stream-and-tool-progress",
        "iconography": "outline-with-status-fill", "dataViz": "gradient-used-only-for-generation-state",
        "signature": "sources, tool state, and human adoption remain visible together",
        "bestFor": ["ai", "knowledge-work", "creative", "collaboration"],
    },
    "monochrome-focus": {
        "name": "Monochrome Focus", "tone": ["disciplined", "minimal", "timeless"],
        "composition": "content-axis-with-command-strip", "navigation": "minimal-context-nav",
        "typography": {"character": "neo-grotesk", "contrast": "very-high", "numeric": "tabular"},
        "surface": "monochrome-solid", "radius": "medium", "motion": "opacity-and-position",
        "iconography": "single-weight", "dataViz": "monochrome-plus-one-signal",
        "signature": "one accent colour carries all action semantics",
        "bestFor": ["brand-neutral", "professional", "content", "focus"],
    },
    "adaptive-brand": {
        "name": "Adaptive Brand", "tone": ["recognisable", "flexible", "consistent"],
        "composition": "existing-structure-refined", "navigation": "preserve-and-simplify",
        "typography": {"character": "project-derived", "contrast": "project-corrected", "numeric": "tabular"},
        "surface": "project-derived", "radius": "project-derived", "motion": "project-compatible",
        "iconography": "project-derived", "dataViz": "project-semantic-expanded",
        "signature": "modernisation feels native to the existing product",
        "bestFor": ["existing-design-system", "migration", "multi-brand", "low-risk"],
    },
    "dense-pro": {
        "name": "Dense Pro", "tone": ["expert", "efficient", "precise"],
        "composition": "dense-grid-with-customisable-panels", "navigation": "command-first",
        "typography": {"character": "compact-neutral", "contrast": "high", "numeric": "tabular"},
        "surface": "flat-separated", "radius": "small", "motion": "minimal",
        "iconography": "compact-outline", "dataViz": "comparison-first",
        "signature": "density is user-controlled and keyboard reachable",
        "bestFor": ["expert", "finance", "operations", "high-density"],
    },
}

_COMPOSITION_VARIANTS = (
    "balanced-grid", "asymmetric-focus", "split-command", "progressive-disclosure",
    "layered-command-center", "single-task-flow", "editorial-narrative", "artifact-canvas",
)

_DIRECTION_SPECS: tuple[dict[str, Any], ...] = (
    {
        "id": "conservative-repair",
        "name": "Conservative Repair",
        "archetypePool": ("adaptive-brand", "calm-precision", "monochrome-focus"),
        "structuralDimensions": {
            "layoutModel": "stable-shell-refined-regions",
            "informationArchitecture": "preserve-route-and-region-hierarchy",
            "navigationModel": "preserve-and-simplify",
            "densityModel": "project-derived-controlled",
            "interactionModel": "inline-progressive-disclosure",
            "responsiveModel": "preserve-breakpoints-reflow",
            "componentStrategy": "repair-existing-components",
        },
        "decisionFrame": "优先降低改造风险，保留用户已经学会的结构，只修复阻塞和不一致。",
    },
    {
        "id": "journey-focused",
        "name": "Journey Focused",
        "archetypePool": ("warm-service", "spatial-clarity", "tactile-field"),
        "structuralDimensions": {
            "layoutModel": "task-first-canvas-with-context-summary",
            "informationArchitecture": "journey-sequenced",
            "navigationModel": "contextual-step-navigation",
            "densityModel": "progressive-disclosure",
            "interactionModel": "guided-staged-flow",
            "responsiveModel": "journey-stack-and-bottom-actions",
            "componentStrategy": "compose-around-user-journeys",
        },
        "decisionFrame": "优先让用户更快完成关键任务，把复杂性放到可理解的步骤和状态里。",
    },
    {
        "id": "system-modernization",
        "name": "System Modernization",
        "archetypePool": ("dense-pro", "kinetic-operations", "vibrant-tech", "editorial-data"),
        "structuralDimensions": {
            "layoutModel": "modular-domain-workspace",
            "informationArchitecture": "domain-workspace-and-command-surfaces",
            "navigationModel": "unified-global-local-app-shell",
            "densityModel": "adaptive-configurable-density",
            "interactionModel": "command-context-panels-and-bulk-actions",
            "responsiveModel": "shell-to-bottom-actions",
            "componentStrategy": "tokenized-component-system",
        },
        "decisionFrame": "优先建立可持续演进的产品骨架，让新功能、数据和权限拥有清晰的落点。",
    },
)


def archetype_catalog() -> list[dict[str, Any]]:
    return [{"id": key, **deepcopy(value)} for key, value in _ARCHETYPES.items()]


def _context(plan: Mapping[str, Any]) -> Mapping[str, Any]:
    return plan.get("experienceModel") if isinstance(plan.get("experienceModel"), Mapping) else plan


def _fit_score(archetype_id: str, archetype: Mapping[str, Any], plan: Mapping[str, Any], design_ir: Mapping[str, Any] | None) -> tuple[int, list[str]]:
    model = _context(plan)
    score = 50
    reasons: list[str] = []
    haystack = " ".join(str(model.get(key, "")) for key in ("environment", "primaryTask", "brandPersonality", "informationDensity", "userExpertise", "taskType")).casefold()
    for term in archetype.get("bestFor", []):
        if str(term).casefold() in haystack:
            score += 10; reasons.append(f"业务上下文匹配 {term}")
    if model.get("devicePriority") == "mobile" and archetype_id == "tactile-field":
        score += 24; reasons.append("移动优先和单手操作匹配")
    if model.get("userExpertise") == "expert" and archetype_id in {"kinetic-operations", "dense-pro"}:
        score += 18; reasons.append("专家高频操作适合可控高密度")
    if model.get("userExpertise") == "novice" and archetype_id == "warm-service":
        score += 18; reasons.append("新手需要解释性与引导")
    if model.get("risk") == "high" and archetype_id in {"calm-precision", "adaptive-brand", "warm-service"}:
        score += 12; reasons.append("高风险任务需要稳定清晰而非视觉噪声")
    density = str(model.get("informationDensity") or "")
    if density == "high" and archetype_id in {"dense-pro", "kinetic-operations", "editorial-data"}:
        score += 14; reasons.append("高信息密度需要比较与分层")
    if design_ir:
        source_type = str((design_ir.get("source") or {}).get("type") or "")
        metadata = design_ir.get("metadata") if isinstance(design_ir.get("metadata"), Mapping) else {}
        semantic = metadata.get("deduplicatedSemanticCounts") if isinstance(metadata.get("deduplicatedSemanticCounts"), Mapping) else metadata.get("semanticCounts") if isinstance(metadata.get("semanticCounts"), Mapping) else {}
        if source_type in {"figma", "screenshot"} and archetype_id == "adaptive-brand":
            score += 10; reasons.append("视觉输入存在，优先保留原设计语言")
        if semantic.get("table", 0) or semantic.get("chart", 0):
            if archetype_id in {"editorial-data", "dense-pro", "kinetic-operations"}:
                score += min(18, 5 + int(semantic.get("table", 0)) + int(semantic.get("chart", 0))); reasons.append("数据表格与图表结构匹配")
        if semantic.get("form", 0) or semantic.get("input", 0):
            if archetype_id in {"calm-precision", "warm-service", "spatial-clarity"}:
                score += min(15, 4 + int(semantic.get("form", 0)) + int(semantic.get("input", 0))); reasons.append("表单与输入任务匹配")
        if semantic.get("navigation", 0) and archetype_id in {"adaptive-brand", "dense-pro", "calm-precision"}:
            score += min(12, 4 + int(semantic.get("navigation", 0))); reasons.append("现有导航结构可保留并收敛")
        framework = str(metadata.get("framework") or "")
        if framework in {"vue", "react", "svelte"} and archetype_id == "adaptive-brand":
            score += 4; reasons.append(f"{framework} 项目优先复用本地组件语言")
        token_count = len(design_ir.get("tokens", {})) if isinstance(design_ir.get("tokens"), Mapping) else 0
        if token_count and archetype_id == "adaptive-brand":
            score += 8; reasons.append("输入包含可复用设计 Token")
        signature = str(metadata.get("projectSignature") or design_ir.get("designDigest") or "")
        if signature:
            affinity = int(sha256(f"{signature}:{archetype_id}".encode()).hexdigest()[:4], 16) % 8
            score += affinity
            if affinity >= 6:
                reasons.append("项目结构指纹提供差异化排序")
    return min(100, score), reasons or ["通用企业体验适配"]


def _candidate(
    direction: Mapping[str, Any],
    archetype_id: str,
    archetype: Mapping[str, Any],
    score: int,
    reasons: list[str],
    index: int,
    plan: Mapping[str, Any],
) -> dict[str, Any]:
    model = _context(plan)
    metadata = plan.get("designInputProfile") if isinstance(plan.get("designInputProfile"), Mapping) else {}
    seed = str(metadata.get("projectSignature") or model.get("primaryTask") or "")
    variant_seed = int(sha256(f"{seed}:{archetype_id}:{index}".encode()).hexdigest()[:8], 16)
    composition = _COMPOSITION_VARIANTS[variant_seed % len(_COMPOSITION_VARIANTS)]
    density = "touch" if model.get("devicePriority") == "mobile" else "dense" if model.get("userExpertise") == "expert" and model.get("informationDensity") == "high" else "comfortable"
    direction_id = str(direction["id"])
    direction_name = str(direction["name"])
    structural_dimensions = dict(direction["structuralDimensions"])
    return {
        "id": f"candidate-{index+1}-{direction_id}",
        "name": direction_name,
        "direction": direction_id,
        "archetype": archetype_id,
        "score": score,
        "selectionReasons": reasons + [str(direction["decisionFrame"])],
        "decisionFrame": str(direction["decisionFrame"]),
        "structuralDimensions": structural_dimensions,
        "designDNA": {
            "tone": list(archetype["tone"]),
            "composition": composition,
            "baseComposition": archetype["composition"],
            "navigation": archetype["navigation"],
            "typography": deepcopy(archetype["typography"]),
            "surface": archetype["surface"],
            "radius": archetype["radius"],
            "motion": archetype["motion"],
            "iconography": archetype["iconography"],
            "dataVisualization": archetype["dataViz"],
            "density": density,
            "signatureMoment": archetype["signature"],
            "direction": direction_name,
            "structuralDimensions": structural_dimensions,
        },
        "experienceRules": [
            "主任务在首屏可识别，品牌表现不得覆盖任务层级",
            "装饰效果必须可关闭并支持 prefers-reduced-motion",
            "数据、错误和高风险状态不得只依赖颜色",
            "移动端优先重组信息而不是等比压缩桌面布局",
            "动效只解释状态变化、空间关系或操作结果",
        ],
        "antiPatterns": [
            "全页大面积玻璃模糊", "为了差异化牺牲表格可读性", "随机渐变和无语义阴影",
            "固定像素布局", "用动画延迟主任务", "每个组件使用不同圆角和图标语言",
        ],
        "reviewRequired": ["人工设计偏好", "真实内容长度", "品牌合法性", "三档响应式", "关键任务时间"],
    }


def generate_design_candidates(plan: Mapping[str, Any], *, design_ir: Mapping[str, Any] | None = None, count: int = 3, include_archetypes: Iterable[str] | None = None) -> dict[str, Any]:
    # Beta.3 permits 1–3 genuine directions. The default remains three for
    # compatibility with the existing redesign pipeline, but focused callers
    # no longer need to manufacture extra choices when no real trade-off exists.
    count = max(1, min(3, int(count)))
    allowed = list(include_archetypes or _ARCHETYPES.keys())
    ranked: list[tuple[int, str, list[str]]] = []
    for archetype_id in allowed:
        if archetype_id not in _ARCHETYPES:
            continue
        score, reasons = _fit_score(archetype_id, _ARCHETYPES[archetype_id], plan, design_ir)
        ranked.append((score, archetype_id, reasons))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    candidate_plan = deepcopy(dict(plan))
    if design_ir:
        meta = design_ir.get("metadata") if isinstance(design_ir.get("metadata"), Mapping) else {}
        candidate_plan["designInputProfile"] = {"projectSignature": meta.get("projectSignature") or design_ir.get("designDigest")}
    ranked_by_id = {archetype_id: (score, reasons) for score, archetype_id, reasons in ranked}
    fallback = ranked[0] if ranked else (50, "adaptive-brand", ["通用企业体验适配"])
    candidates: list[dict[str, Any]] = []
    for index, direction in enumerate(_DIRECTION_SPECS[:count]):
        choices = [item for item in direction["archetypePool"] if item in _ARCHETYPES and item in ranked_by_id]
        archetype_id = max(choices, key=lambda item: (ranked_by_id[item][0], item)) if choices else str(fallback[1])
        score, reasons = ranked_by_id.get(archetype_id, (int(fallback[0]), list(fallback[2])))
        candidates.append(_candidate(direction, archetype_id, _ARCHETYPES[archetype_id], score, reasons, index, candidate_plan))
    structural_dimensions = sorted({
        dimension
        for candidate in candidates
        for dimension in (candidate.get("structuralDimensions") or {})
    })
    pairwise: list[dict[str, Any]] = []
    for left_index, left in enumerate(candidates):
        for right in candidates[left_index + 1:]:
            left_dimensions = left.get("structuralDimensions") if isinstance(left.get("structuralDimensions"), Mapping) else {}
            right_dimensions = right.get("structuralDimensions") if isinstance(right.get("structuralDimensions"), Mapping) else {}
            distinct = sorted(dimension for dimension in structural_dimensions if left_dimensions.get(dimension) != right_dimensions.get(dimension))
            pairwise.append({
                "left": left["id"], "right": right["id"],
                "distinctDimensions": distinct, "distinctDimensionCount": len(distinct),
                "status": "PASS" if len(distinct) >= 3 else "FAIL",
            })
    difference_gate = {
        "status": "PASS" if 1 <= len(candidates) <= 3 and all(item["status"] == "PASS" for item in pairwise) else "FAIL",
        "gateType": "DECLARED_DIRECTION_CONTRACT_DIFFERENCE",
        "claimBoundary": "PASS proves the declared direction contracts differ; it does not prove rendered or candidate-IR structural difference.",
        "minimumDistinctDimensions": 3,
        "dimensions": structural_dimensions,
        "pairwise": pairwise,
        "allPairsPass": all(item["status"] == "PASS" for item in pairwise),
    }
    payload = {
        "schemaVersion": "2.2", "status": "CANDIDATES_READY",
        "candidateContractVersion": "1.0",
        "method": "context-ranked-product-directions",
        "candidates": candidates,
        "recommended": max(candidates, key=lambda item: (int(item.get("score", 0)), item["id"]))["id"] if candidates else None,
        "selected": None,
        "selectionPolicy": {
            "automaticSelectionIsRecommendationOnly": True,
            "humanPreferenceRequiredBeforeProduction": True,
            "candidateCount": len(candidates),
            "requiredCandidateCount": count,
            "availableDirections": [str(item["name"]) for item in _DIRECTION_SPECS],
            "directionContractDifferenceGate": "required",
        },
        "differenceGate": difference_gate,
    }
    payload["candidateDigest"] = sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return payload


def apply_candidate_to_plan(plan: Mapping[str, Any], candidate: Mapping[str, Any]) -> dict[str, Any]:
    result = deepcopy(dict(plan))
    result["designIntelligence"] = {
        "selectedCandidate": deepcopy(dict(candidate)),
        "selectionMode": "user-or-host-approved",
        "productionAuthority": False,
    }
    return result
