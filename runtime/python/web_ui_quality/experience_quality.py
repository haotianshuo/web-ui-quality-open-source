"""Measure whether an Experience Fusion plan is ready to implement and validate.

This is not an aesthetic score.  It exposes missing inputs and weak contracts so
users can distinguish a persuasive preview from a production-ready plan.
"""
from __future__ import annotations

from typing import Any, Mapping

from .experience_modernization import _grounded_task, _responsive_composition, expected_state_ids


def evaluate_plan_readiness(plan: Mapping[str, Any]) -> dict[str, Any]:
    model = plan.get("experienceModel") or {}
    skeleton = plan.get("selectedSkeleton") or {}
    interaction = plan.get("interactionContract") or {}
    repairs = plan.get("uxRepairPlan") or {}
    design = plan.get("projectDesignSystem") or {}
    visual = plan.get("visualSystem") or {}

    confidence_score = {"high": 100, "medium": 72, "low": 38}.get(str(model.get("confidence")), 35)
    pattern_score = int(skeleton.get("score") or 0)
    states = list(interaction.get("contextualStates") or [])
    interaction_patterns = list(interaction.get("selectedInteractionPatterns") or [])
    state_score = min(100, len(states) * 12)
    interaction_score = min(100, len(interaction_patterns) * 18)
    repair_score = int(repairs.get("score") or 55)
    raw_consistency = float((design.get("metrics") or {}).get("consistencyScore") or 0)
    consistency = int(round(raw_consistency * 100 if 0 < raw_consistency <= 1 else raw_consistency))
    consistency = max(0, min(100, consistency))
    if int(design.get("cssFiles") or 0) == 0:
        consistency = 45
    visual_score = 100 if visual.get("dtcg") and visual.get("css") else 55
    responsive_score = 100 if _responsive_composition(skeleton) else 45
    state_contracts = [item for item in interaction.get("stateCoverage", []) if isinstance(item, Mapping)]
    state_ids = {str(item.get("id") or "") for item in state_contracts}
    required_state_ids = expected_state_ids(model)
    hard_gates = {
        "primaryTaskGrounded": _grounded_task(model),
        "patternSelected": bool(skeleton.get("id")),
        "stateRecoveryComplete": bool(state_contracts)
        and required_state_ids.issubset(state_ids)
        and all(item.get("action") and item.get("persistence") and item.get("a11y") for item in state_contracts),
        "responsiveComposition": responsive_score == 100,
        "keyboardAndFocusContract": bool(interaction.get("keyboard")),
    }
    blockers = [key for key, passed in hard_gates.items() if not passed]

    dimensions = {
        "businessContext": confidence_score,
        "patternFit": pattern_score,
        "interactionCoverage": interaction_score,
        "stateRecovery": state_score,
        "uxRepairBaseline": repair_score,
        "projectConsistency": consistency,
        "visualSystemCompleteness": visual_score,
        "responsiveContract": responsive_score,
    }
    weights = {
        "businessContext": 0.14, "patternFit": 0.16, "interactionCoverage": 0.14,
        "stateRecovery": 0.14, "uxRepairBaseline": 0.12, "projectConsistency": 0.10,
        "visualSystemCompleteness": 0.10, "responsiveContract": 0.10,
    }
    total = round(sum(dimensions[key] * weights[key] for key in dimensions))
    gaps: list[str] = []
    if confidence_score < 70: gaps.append("补齐角色、频率、环境、风险和成功指标")
    if pattern_score < 65: gaps.append("推荐骨架适配度偏低，需人工确认或选择替代方案")
    if interaction_score < 60: gaps.append("核心操作缺少完整反馈、失败和恢复合同")
    if state_score < 70: gaps.append("关键状态覆盖不足")
    if repair_score < 70: gaps.append("现有页面仍有明显布局、响应式或交互债务")
    if consistency < 60: gaps.append("现有设计 Token 和样式复用不足")
    status = "IMPLEMENTATION_READY" if total >= 80 and not gaps[:2] and not blockers else "REVIEW_READY" if total >= 65 and not blockers else "DISCOVERY_REQUIRED"
    return {
        "schemaVersion": "2.0",
        "status": status,
        "score": total,
        "dimensions": dimensions,
        "gaps": gaps,
        "hardGates": hard_gates,
        "blockers": blockers,
        "meaning": "评估方案是否具备实施条件，不代表最终视觉审美或真实用户效果。",
        "nextGate": "真实 Browser 三档视口、关键旅程和人工偏好验证" if status != "DISCOVERY_REQUIRED" else "补齐业务与页面证据",
    }
