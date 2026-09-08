from __future__ import annotations

from web_ui_quality.orchestrator import _apply_maturity_hard_gates


def test_high_score_is_capped_when_browser_is_unverified() -> None:
    status, gate = _apply_maturity_hard_gates(
        95,
        browser_status="NOT_VERIFIED",
        overall_result="PASS",
        blocking_findings=(),
    )

    assert status == "CONTROLLED_BETA"
    assert gate["status"] == "CAPPED"
    assert gate["cap"] == "CONTROLLED_BETA"


def test_p1_finding_blocks_maturity() -> None:
    status, gate = _apply_maturity_hard_gates(
        95,
        browser_status="PASS",
        overall_result="PASS",
        blocking_findings=({"severity": "P1"},),
    )

    assert status == "NOT_READY"
    assert gate["status"] == "BLOCKED"
    assert "P0_OR_P1_FINDING" in gate["reasons"]


def test_overall_failure_blocks_maturity() -> None:
    status, gate = _apply_maturity_hard_gates(
        95,
        browser_status="PASS",
        overall_result="FAIL",
        blocking_findings=(),
    )

    assert status == "NOT_READY"
    assert "OVERALL_RESULT_FAIL" in gate["reasons"]


def test_healthy_score_uses_existing_maturity_thresholds() -> None:
    pilot, _ = _apply_maturity_hard_gates(80, browser_status="PASS", overall_result="PASS", blocking_findings=())
    beta, _ = _apply_maturity_hard_gates(60, browser_status="PASS", overall_result="PASS", blocking_findings=())
    experimental, _ = _apply_maturity_hard_gates(40, browser_status="PASS", overall_result="PASS", blocking_findings=())

    assert pilot == "PILOT_READY"
    assert beta == "CONTROLLED_BETA"
    assert experimental == "EXPERIMENTAL"
