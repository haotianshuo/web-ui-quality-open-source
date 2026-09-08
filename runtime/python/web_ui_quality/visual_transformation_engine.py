"""Build implementation-shaped visual transformation concepts."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .design_simulation_engine import score_variant, simulate_journey


_CONCEPTS = (
    {
        "key": "workspace",
        "principles": ["保留任务上下文", "主次操作稳定", "状态在对象附近反馈"],
        "desktop": "稳定导航 + 任务列表 + 持续可见的详情工作区",
        "tablet": "列表与详情按任务切换，保留返回位置和筛选条件",
        "mobile": "单列任务流，底部主操作，详情使用全屏层级",
    },
    {
        "key": "guided",
        "principles": ["逐步披露", "即时校验", "明确完成与恢复"],
        "desktop": "分步任务区 + 上下文说明 + 持续可见的进度",
        "tablet": "单主栏步骤，相关说明按需展开",
        "mobile": "一步一屏，固定下一步，离线与草稿状态可见",
    },
    {
        "key": "focus",
        "principles": ["信息减法", "证据靠近决策", "单一主行动"],
        "desktop": "价值叙事 + 可信证据 + 聚焦行动区",
        "tablet": "短节奏内容块，关键证据前置",
        "mobile": "首屏价值与行动，后续内容按决策顺序排列",
    },
)


def _current_steps(journey: Mapping[str, Any]) -> list[dict[str, Any]]:
    result = []
    for stage in journey.get("stages", []):
        if not isinstance(stage, Mapping):
            continue
        result.append({
            "id": stage.get("id"),
            "label": stage.get("label"),
            "interaction": "navigate",
            "contextSwitch": bool(stage.get("frictions")),
            "recovery": False,
        })
    return result


def _proposed_steps(journey: Mapping[str, Any], concept_key: str) -> list[dict[str, Any]]:
    result = []
    stages = [stage for stage in journey.get("stages", []) if isinstance(stage, Mapping)]
    for index, stage in enumerate(stages):
        result.append({
            "id": stage.get("id"),
            "label": stage.get("label"),
            "interaction": "guided" if concept_key == "guided" else "in-context",
            "contextSwitch": False if index else bool(concept_key == "focus" and len(stages) > 3),
            "recovery": index == len(stages) - 1,
        })
    return result


def build_transformation_plan(
    consultation: Mapping[str, Any],
    journey: Mapping[str, Any],
    *,
    business_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    directions = [item for item in consultation.get("directions", []) if isinstance(item, Mapping)][:3]
    if not directions:
        return {
            "schemaVersion": "3.6",
            "status": "DISCOVERY_REQUIRED",
            "selectedVariantId": None,
            "variants": [],
            "clarificationQuestion": consultation.get("clarificationQuestion") or "最希望用户完成的核心任务是什么？",
        }
    problems = [item for item in consultation.get("topProblems", []) if isinstance(item, Mapping)][:3]
    variants = []
    for index, direction in enumerate(directions):
        concept = _CONCEPTS[index % len(_CONCEPTS)]
        variant_id = str(direction.get("id") or f"direction-{index + 1}")
        simulation = simulate_journey(
            _current_steps(journey),
            _proposed_steps(journey, concept["key"]),
            evidence_level="observed" if journey.get("evidence", {}).get("confidence") == "high" else "inferred",
        )
        variant = {
            "id": variant_id,
            "name": str(direction.get("name") or f"方向 {index + 1}"),
            "recommended": bool(direction.get("recommended", index == 0)),
            "whyRecommended": str(direction.get("whyRecommended") or direction.get("summary") or "覆盖当前最高优先级问题"),
            "outcome": str(direction.get("bestFor") or "让用户更清楚、更连续地完成核心任务"),
            "tradeoff": str(direction.get("tradeoff") or "需要用一个关键旅程切片验证适配性"),
            "experiencePrinciples": list(concept["principles"]),
            "responsiveComposition": {
                "desktop": concept["desktop"],
                "tablet": concept["tablet"],
                "mobile": concept["mobile"],
            },
            "screenPlan": [
                {
                    "stage": stage.get("label"),
                    "userGoal": stage.get("goal"),
                    "change": stage.get("opportunity"),
                    "states": ["default", "loading", "empty", "error", "success"] if stage.get("id") == journey.get("criticalStageId") else ["default", "loading", "error"],
                }
                for stage in journey.get("stages", []) if isinstance(stage, Mapping)
            ],
            "componentPlan": ["page-shell", "task-context", "primary-action", "inline-feedback", "recovery-panel"],
            "stateCoverage": ["loading", "empty", "error", "success", "permission-denied", "offline"],
            "implementationSlices": [
                {
                    "id": "critical-journey-slice",
                    "scope": f"只实现“{next((stage.get('label') for stage in journey.get('stages', []) if isinstance(stage, Mapping) and stage.get('id') == journey.get('criticalStageId')), '核心任务')}”及其错误恢复",
                    "sourceWriteAuthorized": False,
                    "acceptance": ["桌面、平板、手机均可完成", "键盘与触控路径可用", "加载、空、错误、成功状态明确", "现有业务规则不变"],
                }
            ],
            "journeySimulation": simulation,
        }
        variant["fit"] = score_variant(variant, recommended=variant["recommended"], journey_coverage=len(problems))
        variants.append(variant)
    selected = next((item["id"] for item in variants if item["recommended"]), variants[0]["id"])
    return {
        "schemaVersion": "3.6",
        "status": "TRANSFORMATION_READY",
        "before": {
            "authority": "SOURCE_GROUNDED_CANDIDATE",
            "summary": consultation.get("businessSummary"),
            "topProblemIds": [str(item.get("id") or f"problem-{index + 1}") for index, item in enumerate(problems)],
            "claimBoundary": "The current-state model is based on available source/evidence, not a verified production recording unless separately proven.",
        },
        "selectedVariantId": selected,
        "variants": variants,
        "handoff": {
            "sourceWriteAuthorized": False,
            "nextAction": "选择方向后生成范围明确的实现计划；修改源码前再次确认",
            "requiredInputs": ["目标项目", "核心任务", "受保护业务规则", "允许修改的源码范围"],
        },
        "businessContext": dict(business_context or {}),
    }
