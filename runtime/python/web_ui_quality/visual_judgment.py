"""Evidence-based visual improvement judgment.

Pixel difference only proves that pixels changed.  This module combines the
browser's rendered-quality measurements, runtime regressions, overflow, and a
structured human/vision review to produce a conservative improvement verdict.
It never labels a page improved from pixel change alone.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence


def _records_by_viewport(browser: Mapping[str, Any], label: str) -> dict[tuple[int, int], Mapping[str, Any]]:
    result: dict[tuple[int, int], Mapping[str, Any]] = {}
    for item in browser.get("records", []):
        if item.get("label") != label:
            continue
        viewport = item.get("viewport", {})
        try:
            key = (int(viewport["width"]), int(viewport["height"]))
        except (KeyError, TypeError, ValueError):
            continue
        result[key] = item
    return result


def _runtime_problem_count(record: Mapping[str, Any]) -> int:
    return (
        len(record.get("console", []))
        + len(record.get("pageErrors", []))
        + len(record.get("requestFailures", []))
        + (1 if record.get("horizontalOverflow") else 0)
    )


def judge_visual_improvement(
    browser: Mapping[str, Any],
    visual_review: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return IMPROVED, REGRESSED, STABLE, or INCONCLUSIVE with evidence."""

    before = _records_by_viewport(browser, "before")
    after = _records_by_viewport(browser, "after")
    common = sorted(set(before) & set(after))
    comparisons: list[dict[str, Any]] = []
    score_deltas: list[float] = []
    issue_deltas: list[int] = []
    runtime_deltas: list[int] = []

    for viewport in common:
        left, right = before[viewport], after[viewport]
        if left.get("status") == "FAIL" or right.get("status") == "FAIL":
            continue
        lq, rq = left.get("renderedQuality", {}), right.get("renderedQuality", {})
        left_score, right_score = lq.get("overallScore"), rq.get("overallScore")
        if isinstance(left_score, (int, float)) and isinstance(right_score, (int, float)):
            score_delta = float(right_score) - float(left_score)
            score_deltas.append(score_delta)
        else:
            score_delta = None
        left_issues = sum(int(x.get("count", 1)) for x in lq.get("findings", []))
        right_issues = sum(int(x.get("count", 1)) for x in rq.get("findings", []))
        issue_delta = right_issues - left_issues
        issue_deltas.append(issue_delta)
        runtime_delta = _runtime_problem_count(right) - _runtime_problem_count(left)
        runtime_deltas.append(runtime_delta)
        comparisons.append({
            "viewport": {"width": viewport[0], "height": viewport[1]},
            "renderedScoreBefore": left_score,
            "renderedScoreAfter": right_score,
            "renderedScoreDelta": score_delta,
            "findingCountBefore": left_issues,
            "findingCountAfter": right_issues,
            "findingDelta": issue_delta,
            "runtimeProblemDelta": runtime_delta,
        })

    review = visual_review or {}
    review_status = str(review.get("status", "NOT_REVIEWED"))
    review_score = review.get("overallScore")
    reasons: list[str] = []
    confidence = "low"

    if browser.get("status") == "FAIL" or not comparisons:
        verdict = "INCONCLUSIVE"
        reasons.append("缺少可比较的成功 Browser 记录。")
    elif review_status in {"REJECTED", "CHANGES_REQUESTED"}:
        verdict = "REGRESSED"
        reasons.append("结构化人工/视觉评审拒绝当前方案或要求修改。")
        confidence = "high"
    else:
        avg_score_delta = sum(score_deltas) / len(score_deltas) if score_deltas else 0.0
        total_issue_delta = sum(issue_deltas)
        total_runtime_delta = sum(runtime_deltas)
        materially_changed = any(
            isinstance(item.get("changedPixelRatio"), (int, float))
            and item.get("changedPixelRatio", 0) >= 0.003
            for item in browser.get("visualDiff", [])
        )
        positive_review = review_status == "APPROVED" and isinstance(review_score, (int, float)) and review_score >= 70
        negative_review = isinstance(review_score, (int, float)) and review_score < 55

        if total_runtime_delta > 0 or total_issue_delta > 2 or negative_review:
            verdict = "REGRESSED"
            reasons.append("改版后新增运行时问题、渲染问题或评审低分。")
            confidence = "high" if review_status != "NOT_REVIEWED" else "medium"
        elif (avg_score_delta >= 4 or total_issue_delta < 0) and total_runtime_delta <= 0 and (positive_review or review_status == "NOT_REVIEWED"):
            verdict = "IMPROVED" if positive_review else "IMPROVEMENT_CANDIDATE"
            reasons.append("渲染质量分提高或可见问题减少，且没有新增运行时回归。")
            if not positive_review:
                reasons.append("尚缺人工/视觉语义评审，因此只能标记为改善候选。")
            confidence = "high" if positive_review else "medium"
        elif abs(avg_score_delta) < 2 and total_issue_delta == 0 and total_runtime_delta == 0:
            verdict = "STABLE" if materially_changed else "INCONCLUSIVE"
            reasons.append("改版前后可测质量基本持平。")
            confidence = "medium" if materially_changed else "low"
        else:
            verdict = "INCONCLUSIVE"
            reasons.append("证据方向不一致，无法仅凭像素或启发式分数判断好坏。")

    return {
        "status": verdict,
        "confidence": confidence,
        "comparisons": comparisons,
        "reviewStatus": review_status,
        "reviewScore": review_score,
        "reasons": reasons,
        "rule": "Pixel difference proves change only; improvement requires rendered/runtime evidence and preferably structured review.",
    }
