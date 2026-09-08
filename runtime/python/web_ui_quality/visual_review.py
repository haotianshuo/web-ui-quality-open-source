"""Contract for human or vision-model qualitative UI review.

Pixel changes and rendered checks cannot decide whether a design is better.
This contract records an explicit reviewer judgement with per-dimension reasons
and keeps unreviewed evidence separate from accepted visual quality.
"""
from __future__ import annotations

from typing import Any, Mapping

from .contracts import ContractViolation

DIMENSIONS = ("task", "hierarchy", "composition", "rhythm", "visual", "interaction", "responsive", "projectFit")
STATUSES = {"NOT_REVIEWED", "APPROVED", "CHANGES_REQUESTED", "REJECTED"}


def review_template() -> dict[str, Any]:
    return {
        "schemaVersion": "1", "reviewerType": "human-or-vision-provider", "status": "NOT_REVIEWED",
        "dimensions": {name: {"score": None, "reason": ""} for name in DIMENSIONS},
        "hardRedLines": [], "strengths": [], "changesRequired": [], "evidenceRefs": [],
    }


def normalize_visual_review(value: Mapping[str, Any] | None) -> dict[str, Any]:
    if value is None:
        return review_template()
    status = str(value.get("status", "NOT_REVIEWED")).upper()
    if status not in STATUSES:
        raise ContractViolation("VISUAL_REVIEW_INVALID", ["$.status: unsupported"])
    raw_dims = value.get("dimensions", {})
    if not isinstance(raw_dims, Mapping):
        raise ContractViolation("VISUAL_REVIEW_INVALID", ["$.dimensions: expected object"])
    dims: dict[str, Any] = {}
    for name in DIMENSIONS:
        raw = raw_dims.get(name, {})
        if not isinstance(raw, Mapping):
            raw = {}
        score = raw.get("score")
        if score is not None:
            score = int(score)
            if not 0 <= score <= 100:
                raise ContractViolation("VISUAL_REVIEW_INVALID", [f"$.dimensions.{name}.score: 0..100"])
        dims[name] = {"score": score, "reason": str(raw.get("reason", "")).strip()}
        if status != "NOT_REVIEWED" and (score is None or not dims[name]["reason"]):
            raise ContractViolation("VISUAL_REVIEW_INVALID", [f"$.dimensions.{name}: reviewed status requires score and reason"])
    def strings(key: str) -> list[str]:
        raw = value.get(key, [])
        return [str(x).strip() for x in raw if str(x).strip()] if isinstance(raw, list) else []
    result = {
        "schemaVersion": "1", "reviewerType": str(value.get("reviewerType", "human-or-vision-provider")),
        "status": status, "dimensions": dims, "hardRedLines": strings("hardRedLines"),
        "strengths": strings("strengths"), "changesRequired": strings("changesRequired"),
        "evidenceRefs": strings("evidenceRefs"),
    }
    scores = [item["score"] for item in dims.values() if item["score"] is not None]
    result["overallScore"] = round(sum(scores) / len(scores)) if scores else None
    if result["hardRedLines"] and status == "APPROVED":
        raise ContractViolation("VISUAL_REVIEW_INVALID", ["$: hard red lines cannot coexist with APPROVED"])
    return result


def review_prompt(report: Mapping[str, Any]) -> str:
    browser = report.get("browserComparisonReport", {})
    plan = report.get("productizationPlan", {})
    return "\n".join([
        "Review the before/after UI as a product designer. Do not infer unobserved business facts.",
        f"Recommended direction: {plan.get('recommendation', 'unknown')}",
        f"Before: {browser.get('beforeRef', 'NOT_VERIFIED')}",
        f"After: {browser.get('afterRef', 'NOT_VERIFIED')}",
        "Score task, hierarchy, composition, rhythm, visual consistency, interaction credibility, responsive behavior, and project fit from 0-100.",
        "For every dimension provide a short evidence-based reason. List hard red lines separately.",
        "Return JSON matching the visual-review template.",
    ])
