"""Evidence gate for Before/After comparability and improvement claims."""
from __future__ import annotations

from typing import Any, Mapping

from .contracts import digest_json

_HEALTH_RANK = {
    "RUNTIME_BROKEN": 0,
    "AUTH_REQUIRED": 1,
    "RESTRICTED_RENDER": 2,
    "DATA_NOT_READY": 3,
    "TASK_FAILED": 4,
    "NOT_VERIFIED": 5,
    "SIMULATED_PREVIEW": 5,
    "VISUAL_FINDINGS": 6,
    "REAL_PAGE_READY": 7,
    "PASS": 7,
}
_PASS = {"PASS", "PASS_RESTORED"}
_FAIL = {"FAIL", "FAIL_NOT_RESTORED", "FAIL_NO_STATE_CHANGE", "BLOCKED_MUTATION_ATTEMPT"}
_UNUSABLE_EVIDENCE_HEALTH = {
    "RUNTIME_BROKEN",
    "AUTH_REQUIRED",
    "RESTRICTED_RENDER",
    "DATA_NOT_READY",
    "NOT_VERIFIED",
    "SIMULATED_PREVIEW",
}


def _journey(report: Mapping[str, Any] | None) -> dict[str, Any]:
    source = report if isinstance(report, Mapping) else {}
    raw_value = source.get("journey") or {}
    raw = dict(raw_value) if isinstance(raw_value, Mapping) else {}
    journey = list(raw.get("journey") or [])
    return {
        "id": raw.get("journeyId"),
        "status": str(raw.get("status") or "NOT_VERIFIED"),
        "definitionDigest": digest_json(journey) if journey else None,
        "outcomeDigest": digest_json(raw.get("runs") or []) if raw.get("runs") else None,
        "hasOutcome": bool(raw.get("runs")) and str(raw.get("status") or "") not in {"NOT_VERIFIED", "NOT_EXECUTED", ""},
    }


def _evidence_usability(
    report: Mapping[str, Any] | None,
    *,
    page_health: str,
    journey: Mapping[str, Any],
) -> tuple[bool, str | None]:
    """Return whether a side can participate in a Before/After claim.

    A real task failure is still usable evidence when the journey outcome was
    recorded.  Environment/render/auth failures are not comparable evidence,
    even if the opposite side later passes.
    """
    if not isinstance(report, Mapping):
        return False, "MISSING_REPORT"
    health = str(page_health or "NOT_VERIFIED").upper()
    if health in _UNUSABLE_EVIDENCE_HEALTH:
        return False, health
    if not bool(journey.get("hasOutcome")):
        return False, "JOURNEY_OUTCOME_MISSING"
    return True, None


def _high_findings(report: Mapping[str, Any] | None) -> set[str]:
    rows = list((report or {}).get("findings") or [])
    return {
        str(item.get("findingId") or item.get("id") or item.get("fingerprint"))
        for item in rows
        if isinstance(item, Mapping) and str(item.get("severity")) in {"P0", "P1"}
    }


def evaluate_improvement_claim(
    before_report: Mapping[str, Any] | None,
    after_report: Mapping[str, Any] | None,
    *,
    condition_match: bool,
    target_match: bool,
    safe_task_match: bool,
) -> dict[str, Any]:
    before_journey = _journey(before_report)
    after_journey = _journey(after_report)
    before_health = str(((before_report or {}).get("pageHealth") or {}).get("pageStatus") or "NOT_VERIFIED")
    after_health = str(((after_report or {}).get("pageHealth") or {}).get("pageStatus") or "NOT_VERIFIED")
    before_rank = _HEALTH_RANK.get(before_health, 5)
    after_rank = _HEALTH_RANK.get(after_health, 5)
    before_evidence_usable, before_evidence_reason = _evidence_usability(
        before_report,
        page_health=before_health,
        journey=before_journey,
    )
    after_evidence_usable, after_evidence_reason = _evidence_usability(
        after_report,
        page_health=after_health,
        journey=after_journey,
    )
    before_high = _high_findings(before_report)
    after_high = _high_findings(after_report)
    new_regressions = sorted(after_high - before_high)

    same_journey = bool(
        before_journey["id"]
        and before_journey["id"] == after_journey["id"]
        and before_journey["definitionDigest"] == after_journey["definitionDigest"]
    )
    comparable = bool(
        condition_match
        and target_match
        and safe_task_match
        and same_journey
        and before_journey["hasOutcome"]
        and after_journey["hasOutcome"]
        and before_evidence_usable
        and after_evidence_usable
    )

    regressed = bool(
        comparable
        and (
            after_rank < before_rank
            or (before_journey["status"] in _PASS and after_journey["status"] not in _PASS)
            or new_regressions
        )
    )
    improved = bool(
        comparable
        and not regressed
        and (
            (before_journey["status"] in _FAIL and after_journey["status"] in _PASS)
            or after_rank > before_rank
            or len(after_high) < len(before_high)
        )
    )

    if regressed:
        status = "REGRESSED"
    elif improved:
        status = "IMPROVEMENT_CLAIM_ALLOWED"
    elif comparable:
        status = "COMPARABLE_NO_PROVEN_IMPROVEMENT"
    else:
        status = "INCONCLUSIVE"
    return {
        "status": status,
        "comparable": comparable,
        "improvementClaimAllowed": status == "IMPROVEMENT_CLAIM_ALLOWED",
        "sameJourney": same_journey,
        "safeTaskMatch": safe_task_match,
        "targetMatch": target_match,
        "conditionMatch": condition_match,
        "beforeJourney": before_journey,
        "afterJourney": after_journey,
        "beforeHealth": before_health,
        "afterHealth": after_health,
        "beforeEvidenceUsable": before_evidence_usable,
        "beforeEvidenceReason": before_evidence_reason,
        "afterEvidenceUsable": after_evidence_usable,
        "afterEvidenceReason": after_evidence_reason,
        "newHighSeverityRegressions": new_regressions,
        "claimBoundary": "An improvement claim requires the same task, journey, target and non-source conditions; usable Before/After outcomes; an observed better result; and no new higher-severity regression.",
    }


__all__ = ["evaluate_improvement_claim"]
