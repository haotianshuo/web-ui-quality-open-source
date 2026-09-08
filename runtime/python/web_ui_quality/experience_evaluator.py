"""Outcome-oriented experience evaluation for before/after UI changes."""
from __future__ import annotations

from typing import Any, Mapping


def _number(value: Any) -> float | None:
    try: return float(value)
    except (TypeError, ValueError): return None


def _improvement(before: float | None, after: float | None, lower_is_better: bool) -> dict[str, Any]:
    if before is None or after is None:
        return {"status":"NOT_MEASURED", "before":before, "after":after, "changePercent":None}
    if before == 0:
        change = 0.0 if after == 0 else None
    else:
        change = ((before - after) / before * 100) if lower_is_better else ((after - before) / abs(before) * 100)
    improved = (after < before) if lower_is_better else (after > before)
    stable = abs(after - before) < 1e-9
    return {"status":"IMPROVED" if improved else "STABLE" if stable else "REGRESSED", "before":before, "after":after, "changePercent":round(change,2) if change is not None else None}


def evaluate_experience(before: Mapping[str, Any] | None, after: Mapping[str, Any] | None, *, visual_review: Mapping[str, Any] | None = None) -> dict[str, Any]:
    before = before or {}; after = after or {}; visual_review = visual_review or {}
    definitions = {
        "taskCompletionMs": True, "steps": True, "errors": True, "horizontalOverflowCount": True,
        "criticalIssues": True, "stateCoverage": False, "mobilePassRate": False, "projectConsistency": False,
        "visualPreference": False, "accessibilityScore": False, "performanceScore": False,
    }
    metrics = {name: _improvement(_number(before.get(name)), _number(after.get(name)), lower) for name, lower in definitions.items()}
    measured = [item for item in metrics.values() if item["status"] != "NOT_MEASURED"]
    improved = sum(item["status"] == "IMPROVED" for item in measured); regressed = sum(item["status"] == "REGRESSED" for item in measured)
    dimensions = {
        "taskEfficiency": _dimension(metrics, ("taskCompletionMs", "steps", "errors")),
        "visualQuality": _dimension(metrics, ("visualPreference", "projectConsistency")),
        "responsive": _dimension(metrics, ("mobilePassRate", "horizontalOverflowCount")),
        "stateAndRecovery": _dimension(metrics, ("stateCoverage", "errors")),
        "technicalQuality": _dimension(metrics, ("criticalIssues", "accessibilityScore", "performanceScore")),
    }
    review_status = str(visual_review.get("status") or "NOT_REVIEWED")
    if regressed:
        status = "REGRESSED"
    elif measured and improved >= max(2, len(measured)//2) and review_status in {"APPROVED", "PASS", "NOT_REVIEWED"}:
        status = "IMPROVED" if review_status != "NOT_REVIEWED" else "IMPROVEMENT_CANDIDATE"
    elif measured:
        status = "MIXED"
    else:
        status = "NOT_MEASURED"
    return {
        "status": status, "metrics": metrics, "dimensions": dimensions,
        "measurementCoverage": round(len(measured) / len(definitions) * 100),
        "visualReviewStatus": review_status,
        "conclusion": _conclusion(status),
        "requiredNextEvidence": _next_evidence(metrics, visual_review),
    }


def _dimension(metrics: Mapping[str, Mapping[str, Any]], names: tuple[str, ...]) -> dict[str, Any]:
    values = [metrics[name] for name in names if metrics[name]["status"] != "NOT_MEASURED"]
    if not values: return {"status":"NOT_MEASURED", "score":None}
    score = sum({"IMPROVED":100,"STABLE":70,"REGRESSED":20}.get(item["status"],40) for item in values) / len(values)
    return {"status":"PASS" if score >= 80 else "PASS_WITH_WARNINGS" if score >= 55 else "FAIL", "score":round(score), "evidenceCount":len(values)}


def _conclusion(status: str) -> str:
    return {
        "IMPROVED":"任务、视觉或技术指标形成一致改善，并有定性评审支持。",
        "IMPROVEMENT_CANDIDATE":"定量指标显示改善，但仍需人工视觉或真实用户评审。",
        "MIXED":"部分指标改善，部分稳定或证据不足，不能宣称整体提升。",
        "REGRESSED":"至少一项已测关键指标退化，需要回退或继续迭代。",
        "NOT_MEASURED":"尚未提供足够的 before/after 指标。",
    }[status]


def _next_evidence(metrics: Mapping[str, Mapping[str, Any]], review: Mapping[str, Any]) -> list[str]:
    missing = [name for name, value in metrics.items() if value["status"] == "NOT_MEASURED"]
    result = [f"补充 {name} 的同条件 before/after" for name in missing[:5]]
    if str(review.get("status") or "NOT_REVIEWED") == "NOT_REVIEWED": result.append("完成八维人工视觉与交互评审")
    if not result: result.append("使用真实用户或代表用户复核任务结果")
    return result
