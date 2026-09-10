"""Evidence gate for Before/After comparability and improvement claims."""
from __future__ import annotations

from typing import Any, Mapping, Sequence
from urllib.parse import urlsplit

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


_BROWSER_RECORD_PASS = {"PASS", "PASS_WITH_WARNINGS"}


def _pair(value: Any) -> tuple[int, int] | None:
    if not isinstance(value, Mapping):
        return None
    try:
        width, height = int(value.get("width")), int(value.get("height"))
    except (TypeError, ValueError):
        return None
    return (width, height) if width > 0 and height > 0 else None


def _url_key(value: Any, *, route_only: bool = False) -> tuple[Any, ...] | None:
    if not isinstance(value, str) or not value.strip():
        return None
    parsed = urlsplit(value)
    if not parsed.scheme or not parsed.hostname:
        return None
    if route_only:
        return (parsed.path or "/", parsed.query)
    return (parsed.scheme.casefold(), parsed.hostname.casefold(), parsed.port or (443 if parsed.scheme == "https" else 80), parsed.path or "/", parsed.query)


def _runtime_side(
    report: Mapping[str, Any] | None,
    *,
    expected_viewports: Sequence[Sequence[int]],
    side: str,
) -> dict[str, Any]:
    source = report if isinstance(report, Mapping) else {}
    runtime = source.get("runtime") if isinstance(source.get("runtime"), Mapping) else {}
    records = [row for row in list(runtime.get("records") or []) if isinstance(row, Mapping)]
    expected: list[tuple[int, int]] = []
    for item in expected_viewports:
        try:
            if len(item) == 2:
                expected.append((int(item[0]), int(item[1])))
        except (TypeError, ValueError):
            continue
    expected_set = set(expected)
    reasons: list[str] = []
    target = source.get("target") if isinstance(source.get("target"), Mapping) else {}
    target_url = target.get("url")
    runtime_url = runtime.get("url")
    route_only = str(target.get("source") or "") == "local-static-project"
    if _url_key(target_url, route_only=route_only) is None or _url_key(runtime_url, route_only=route_only) is None:
        reasons.append("TARGET_URL_MISSING")
    elif _url_key(target_url, route_only=route_only) != _url_key(runtime_url, route_only=route_only):
        reasons.append("TARGET_URL_MISMATCH")
    if not records:
        reasons.append("NO_BROWSER_RECORDS")

    observed: dict[tuple[int, int], Mapping[str, Any]] = {}
    defect_signal = False
    clean_signal = True
    for record in records:
        requested = _pair(record.get("requestedViewport") or record.get("viewport"))
        actual = _pair(record.get("actualBrowserViewport"))
        reported = _pair(record.get("reportedEvidenceViewport"))
        normalization = record.get("viewportNormalization") if isinstance(record.get("viewportNormalization"), Mapping) else None
        if requested is None:
            reasons.append("REQUESTED_VIEWPORT_MISSING")
        else:
            if requested in observed:
                reasons.append("DUPLICATE_VIEWPORT_RECORD")
            else:
                observed[requested] = record
        if requested not in expected_set:
            reasons.append("UNEXPECTED_VIEWPORT")
        if actual is None:
            reasons.append("ACTUAL_BROWSER_VIEWPORT_MISSING")
        if reported is None:
            reasons.append("REPORTED_EVIDENCE_VIEWPORT_MISSING")
        if normalization is None:
            reasons.append("VIEWPORT_NORMALIZATION_MISSING")
        else:
            if str(normalization.get("status") or "NOT_VERIFIED") not in {"MATCHED", "MISMATCH"}:
                reasons.append("VIEWPORT_NORMALIZATION_NOT_VERIFIED")
            if _pair(normalization.get("requested")) != requested or _pair(normalization.get("actual")) != actual or _pair(normalization.get("reported")) != reported:
                reasons.append("VIEWPORT_NORMALIZATION_TRACE_MISMATCH")
        if actual is not None and reported is not None and actual != reported:
            reasons.append("ACTUAL_REPORTED_VIEWPORT_MISMATCH")

        status = str(record.get("status") or "").upper()
        evidence_status = str(record.get("evidenceStatus") or "").upper()
        if status not in _BROWSER_RECORD_PASS:
            reasons.append("BROWSER_RECORD_NOT_PASS")
        if evidence_status != "VERIFIED":
            reasons.append("BROWSER_EVIDENCE_NOT_VERIFIED")
        if not (isinstance(record.get("httpStatus"), int) and 200 <= record["httpStatus"] < 300):
            reasons.append("HTTP_OUTCOME_NOT_VERIFIED")
        if record.get("validRender") is not True:
            reasons.append("VALID_RENDER_NOT_VERIFIED")
        if str((record.get("stability") or {}).get("status") or "").upper() != "STABLE":
            reasons.append("BROWSER_STABILITY_NOT_VERIFIED")
        if record.get("pageErrors") or record.get("criticalRequestFailures") or record.get("criticalBlockedRequests"):
            reasons.append("BROWSER_RUNTIME_ERRORS")
        if str((record.get("mutationFirewall") or {}).get("status") or "").upper() != "PASS":
            reasons.append("MUTATION_FIREWALL_NOT_PASS")
        if str((record.get("resourceIntegrity") or {}).get("status") or "").upper() not in {"", "PASS"}:
            reasons.append("RESOURCE_INTEGRITY_NOT_PASS")

        mismatch = str((normalization or {}).get("status") or "NOT_VERIFIED") == "MISMATCH"
        warning = status == "PASS_WITH_WARNINGS" or bool(record.get("horizontalOverflow")) or str((record.get("renderedQuality") or {}).get("status") or "").upper() in {"FAIL", "PASS_WITH_WARNINGS"}
        defect_signal = defect_signal or mismatch or warning
        clean_signal = clean_signal and not mismatch and not bool(record.get("horizontalOverflow")) and status == "PASS" and str((record.get("renderedQuality") or {}).get("status") or "PASS").upper() == "PASS"

    if set(observed) != expected_set or len(records) != len(expected):
        reasons.append("VIEWPORT_MATRIX_INCOMPLETE")
    unique_reasons = sorted(set(reasons))
    return {
        "status": "SUFFICIENT" if not unique_reasons else "INSUFFICIENT",
        "side": side,
        "recordCount": len(records),
        "expectedViewports": [f"{width}x{height}" for width, height in expected],
        "observedViewports": [f"{width}x{height}" for width, height in sorted(observed)],
        "defectSignal": defect_signal,
        "clean": bool(records) and clean_signal and not unique_reasons,
        "reasons": unique_reasons,
        "reason": unique_reasons[0] if unique_reasons else None,
        "claimBoundary": "Only current WUQ Browser records with verified evidence, stable rendering, matching target route, complete requested viewports, and traceable viewport measurements can enter this comparison path.",
    }


def _runtime_claim_report(report: Mapping[str, Any], *, side: Mapping[str, Any], expected_viewports: Sequence[Sequence[int]]) -> dict[str, Any]:
    derived = dict(report)
    derived["pageHealth"] = {"pageStatus": "REAL_PAGE_READY"}
    journey_rows = [{"viewport": f"{int(item[0])}x{int(item[1])}", "status": "PASS"} for item in expected_viewports]
    derived["journey"] = {
        "journeyId": "browser-runtime-evidence",
        "status": "FAIL" if side.get("defectSignal") else "PASS",
        "journey": [{"action": "browser-load", "viewports": [row["viewport"] for row in journey_rows]}],
        "runs": [
            {**row, "status": "FAIL" if side.get("defectSignal") else "PASS", "outcomeProofCount": 1}
            for row in journey_rows
        ],
    }
    return derived


def _evaluate_improvement_claim_core(
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


def evaluate_improvement_claim(
    before_report: Mapping[str, Any] | None,
    after_report: Mapping[str, Any] | None,
    *,
    condition_match: bool,
    target_match: bool,
    safe_task_match: bool,
    browser_viewports: Sequence[Sequence[int]] | None = None,
) -> dict[str, Any]:
    result = _evaluate_improvement_claim_core(
        before_report, after_report,
        condition_match=condition_match, target_match=target_match, safe_task_match=safe_task_match,
    )
    if browser_viewports:
        before_runtime = _runtime_side(before_report, expected_viewports=browser_viewports, side="before")
        after_runtime = _runtime_side(after_report, expected_viewports=browser_viewports, side="after")
        runtime_evidence = {"before": before_runtime, "after": after_runtime}
        if result["status"] == "INCONCLUSIVE" and before_runtime["status"] == "SUFFICIENT" and after_runtime["status"] == "SUFFICIENT":
            if isinstance(before_report, Mapping) and isinstance(after_report, Mapping):
                derived = _evaluate_improvement_claim_core(
                    _runtime_claim_report(before_report, side=before_runtime, expected_viewports=browser_viewports),
                    _runtime_claim_report(after_report, side=after_runtime, expected_viewports=browser_viewports),
                    condition_match=condition_match, target_match=target_match, safe_task_match=safe_task_match,
                )
                derived["evidenceBasis"] = "BROWSER_RUNTIME_RECORDS"
                derived["browserEvidence"] = runtime_evidence
                derived["claimBoundary"] = "Browser runtime records may close the existing comparison gap only when the same target/conditions and complete verified Before/After viewport records are present; Host, drift, budget, and other Trust Kernel gates remain independent."
                return derived
        result["evidenceBasis"] = "JOURNEY_OUTCOME"
        result["browserEvidence"] = runtime_evidence
        if before_runtime["status"] != "SUFFICIENT" or after_runtime["status"] != "SUFFICIENT":
            if before_runtime["status"] != "SUFFICIENT":
                result["beforeEvidenceReason"] = "BROWSER_RUNTIME_EVIDENCE_INSUFFICIENT"
            if after_runtime["status"] != "SUFFICIENT":
                result["afterEvidenceReason"] = "BROWSER_RUNTIME_EVIDENCE_INSUFFICIENT"
    return result


__all__ = ["evaluate_improvement_claim"]
