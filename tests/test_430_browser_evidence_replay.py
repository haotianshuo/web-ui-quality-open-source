from __future__ import annotations

import pytest

from web_ui_quality import browser_standard as browser
from web_ui_quality.comparison_gate import evaluate_improvement_claim
from web_ui_quality.contracts import ContractViolation


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
