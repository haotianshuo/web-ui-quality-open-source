"""Executive product-experience reporting with explicit claim boundaries."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def _metric(metric_id: str, label: str, definition: str, source: str) -> dict[str, Any]:
    return {
        "id": metric_id,
        "label": label,
        "definition": definition,
        "source": source,
        "baseline": None,
        "target": None,
        "status": "MEASUREMENT_REQUIRED",
    }


def build_executive_report(
    product_name: str,
    score: int | None,
    diagnosis: Sequence[str],
    recommendation: Mapping[str, Any],
) -> dict[str, Any]:
    """Compatibility API for a concise, honest executive report."""
    direction = str(recommendation.get("name") or recommendation.get("direction") or "体验优化方案")
    return {
        "schemaVersion": "3.6",
        "product": product_name,
        "experienceScore": score,
        "scoreStatus": "DIAGNOSTIC_ONLY" if score is not None else "BASELINE_REQUIRED",
        "executiveSummary": f"当前应优先处理核心任务中的体验摩擦，并以“{direction}”作为第一验证方向。",
        "businessProblems": [str(item) for item in diagnosis[:3]],
        "recommendedTransformation": {
            "direction": direction,
            "reason": str(recommendation.get("reason") or recommendation.get("whyRecommended") or "优先覆盖影响最大的用户任务"),
            "tradeoff": str(recommendation.get("tradeoff") or "需要以小范围验证确认真实收益"),
        },
        "successMetrics": [
            _metric("task-success", "核心任务完成率", "完成定义明确的核心任务且无关键错误的会话比例", "任务分析或可控埋点"),
            _metric("time-on-task", "任务完成时间", "从任务入口到成功反馈的中位时长", "可用性测试或匿名事件"),
            _metric("recovery", "异常恢复率", "遇到错误、离线或冲突后最终完成任务的比例", "错误与恢复事件"),
        ],
        "claimBoundary": "No business outcome improvement is claimed until a baseline and post-change observation exist.",
    }


def build_executive_brief(
    product_name: str,
    score_report: Mapping[str, Any],
    consultation: Mapping[str, Any],
    transformation: Mapping[str, Any],
    measurement: Mapping[str, Any],
) -> dict[str, Any]:
    problems = [item for item in consultation.get("topProblems", []) if isinstance(item, Mapping)][:3]
    variants = [item for item in transformation.get("variants", []) if isinstance(item, Mapping)]
    selected_id = transformation.get("selectedVariantId")
    selected = next((item for item in variants if item.get("id") == selected_id), variants[0] if variants else {})
    base = build_executive_report(
        product_name,
        score_report.get("experienceScore"),
        [str(item.get("title") or "体验问题") for item in problems],
        selected,
    )
    base.update({
        "decision": {
            "recommendation": selected.get("name"),
            "whyNow": selected.get("whyRecommended") or selected.get("outcome"),
            "firstSlice": (selected.get("implementationSlices") or [None])[0],
            "approvalRequiredBeforeSourceWrite": True,
        },
        "investmentShape": {
            "approach": "vertical-slice",
            "phases": ["建立基线", "实现一个关键旅程切片", "三端验证", "观察真实结果后再扩展"],
            "avoid": "在没有证据的情况下进行全量视觉重做",
        },
        "measurementReadiness": measurement.get("readiness"),
    })
    return base
