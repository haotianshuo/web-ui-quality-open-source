from __future__ import annotations

import pytest

from web_ui_quality import browser_standard as browser
from web_ui_quality.comparison_gate import evaluate_improvement_claim
from web_ui_quality.contracts import ContractViolation


_RUNTIME_VIEWPORTS = ((390, 844), (768, 1024), (1440, 900))


def _runtime_report(*, repaired: bool, reachable: bool = True) -> dict:
    records = []
    for index, (width, height) in enumerate(_RUNTIME_VIEWPORTS):
        actual = (width, height) if repaired or index else (820, 1775)
        mismatch = actual != (width, height)
        records.append(
            {
                "viewport": {"width": width, "height": height},
                "requestedViewport": {"width": width, "height": height},
                "actualBrowserViewport": {"width": actual[0], "height": actual[1]},
                "reportedEvidenceViewport": {"width": actual[0], "height": actual[1]},
                "viewportNormalization": {
                    "status": "MISMATCH" if mismatch else "MATCHED",
                    "requested": {"width": width, "height": height},
                    "actual": {"width": actual[0], "height": actual[1]},
                    "reported": {"width": actual[0], "height": actual[1]},
                },
                "status": "PASS_WITH_WARNINGS" if mismatch else "PASS",
                "evidenceStatus": "VERIFIED" if reachable else "NOT_VERIFIED",
                "httpStatus": 200 if reachable else None,
                "validRender": reachable,
                "stability": {"status": "STABLE"} if reachable else {"status": "NOT_VERIFIED"},
                "pageErrors": [],
                "criticalRequestFailures": [],
                "criticalBlockedRequests": [],
                "mutationFirewall": {"status": "PASS"},
                "resourceIntegrity": {"status": "PASS"} if reachable else {"status": "BLOCKED"},
                "networkPolicy": {"blockedRequestCount": 0, "blockedWebSocketCount": 0, "externalOriginsBlocked": False},
                "horizontalOverflow": False if repaired or index != 1 else True,
                "renderedQuality": {"status": "PASS" if repaired or index != 1 else "FAIL"},
            }
        )
    return {
        "status": "PASS" if repaired and reachable else "NOT_VERIFIED",
        "target": {"url": "https://app.test/orders"},
        "preflight": {"status": "READY", "browser": {"available": True}},
        "pageHealth": {"pageStatus": "NOT_VERIFIED"},
        "runtime": {
            "url": "https://app.test/orders",
            "viewports": [{"width": w, "height": h} for w, h in _RUNTIME_VIEWPORTS],
            "records": records if reachable else [],
        },
        "journey": {"journeyId": None, "status": "NOT_VERIFIED", "journey": [], "runs": []},
        "findings": [],
    }


def _report(page_status: str, journey_status: str, *, runs: bool = True) -> dict:
    return {
        "pageHealth": {"pageStatus": page_status},
        "journey": {
            "journeyId": "journey-430-primary",
            "status": journey_status,
            "journey": [{"action": "open", "target": "/"}],
            "runs": [{"status": journey_status, "step": "open"}] if runs else [],
        },
    }


def test_task_failure_with_recorded_outcome_remains_comparable() -> None:
    result = evaluate_improvement_claim(
        _report("TASK_FAILED", "TASK_FAILED"),
        _report("PASS", "PASS"),
        condition_match=True,
        target_match=True,
        safe_task_match=True,
    )

    assert result["beforeEvidenceUsable"] is True
    assert result["afterEvidenceUsable"] is True
    assert result["comparable"] is True
    assert result["status"] == "IMPROVEMENT_CLAIM_ALLOWED"


def test_environment_failure_is_not_comparable_even_when_after_passes() -> None:
    result = evaluate_improvement_claim(
        _report("RUNTIME_BROKEN", "TASK_FAILED"),
        _report("PASS", "PASS"),
        condition_match=True,
        target_match=True,
        safe_task_match=True,
    )

    assert result["beforeEvidenceUsable"] is False
    assert result["beforeEvidenceReason"] == "RUNTIME_BROKEN"
    assert result["comparable"] is False
    assert result["status"] == "INCONCLUSIVE"


def test_missing_journey_outcome_is_not_comparable() -> None:
    result = evaluate_improvement_claim(
        _report("PASS", "PASS"),
        _report("PASS", "NOT_VERIFIED", runs=False),
        condition_match=True,
        target_match=True,
        safe_task_match=True,
    )

    assert result["afterEvidenceUsable"] is False
    assert result["afterEvidenceReason"] == "JOURNEY_OUTCOME_MISSING"
    assert result["status"] == "INCONCLUSIVE"


def test_verified_runtime_before_after_records_can_close_browser_claim_without_journey() -> None:
    result = evaluate_improvement_claim(
        _runtime_report(repaired=False),
        _runtime_report(repaired=True),
        condition_match=True,
        target_match=True,
        safe_task_match=True,
        browser_viewports=_RUNTIME_VIEWPORTS,
    )

    assert result["status"] == "IMPROVEMENT_CLAIM_ALLOWED"
    assert result["comparable"] is True
    assert result["evidenceBasis"] == "BROWSER_RUNTIME_RECORDS"
    assert result["browserEvidence"]["before"]["status"] == "SUFFICIENT"
    assert result["browserEvidence"]["after"]["status"] == "SUFFICIENT"


def test_unreachable_runtime_records_remain_not_verified() -> None:
    result = evaluate_improvement_claim(
        _runtime_report(repaired=False),
        _runtime_report(repaired=True, reachable=False),
        condition_match=True,
        target_match=True,
        safe_task_match=True,
        browser_viewports=_RUNTIME_VIEWPORTS,
    )

    assert result["status"] == "INCONCLUSIVE"
    assert result["comparable"] is False
    assert result["afterEvidenceReason"] in {"NOT_VERIFIED", "BROWSER_RUNTIME_EVIDENCE_INSUFFICIENT"}


def test_runtime_claim_rejects_missing_or_mismatched_viewport_evidence() -> None:
    before = _runtime_report(repaired=False)
    after = _runtime_report(repaired=True)
    after["runtime"]["records"][0]["reportedEvidenceViewport"] = {"width": 391, "height": 844}
    after["runtime"]["records"][0]["viewportNormalization"]["status"] = "MISMATCH"

    result = evaluate_improvement_claim(
        before,
        after,
        condition_match=True,
        target_match=True,
        safe_task_match=True,
        browser_viewports=_RUNTIME_VIEWPORTS,
    )

    assert result["status"] == "INCONCLUSIVE"
    assert result["comparable"] is False


def test_browser_runtime_evidence_requires_the_same_target_url() -> None:
    before = _runtime_report(repaired=False)
    after = _runtime_report(repaired=True)
    after["target"]["url"] = "https://app.test/other"

    result = evaluate_improvement_claim(
        before,
        after,
        condition_match=True,
        target_match=True,
        safe_task_match=True,
        browser_viewports=_RUNTIME_VIEWPORTS,
    )

    assert result["status"] == "INCONCLUSIVE"
    assert result["browserEvidence"]["after"]["reason"] == "TARGET_URL_MISMATCH"


def test_browser_runtime_evidence_requires_a_complete_viewport_matrix() -> None:
    before = _runtime_report(repaired=False)
    after = _runtime_report(repaired=True)
    after["runtime"]["records"] = after["runtime"]["records"][:2]

    result = evaluate_improvement_claim(
        before,
        after,
        condition_match=True,
        target_match=True,
        safe_task_match=True,
        browser_viewports=_RUNTIME_VIEWPORTS,
    )

    assert result["status"] == "INCONCLUSIVE"
    assert result["browserEvidence"]["after"]["reason"] == "VIEWPORT_MATRIX_INCOMPLETE"


def test_browser_run_guard_rejects_consumed_run_id() -> None:
    run_id = "wuq-replay-430-0001"
    browser._CONSUMED_RUN_IDS.discard(run_id)
    try:
        browser._CONSUMED_RUN_IDS.add(run_id)
        with pytest.raises(ContractViolation) as caught:
            browser.create_browser_run_guard(
                run_id=run_id,
                evidence_ref="evidence:replay-430",
                evidence_resolver=lambda reference: reference == "evidence:replay-430",
            )
        assert caught.value.code == "BROWSER_EVIDENCE_REPLAYED"
    finally:
        browser._CONSUMED_RUN_IDS.discard(run_id)
