from __future__ import annotations

from web_ui_quality.orchestrator import _apply_maturity_hard_gates


def test_not_measured_browser_is_capped_even_with_a_high_score() -> None:
    status, gate = _apply_maturity_hard_gates(
        99,
        browser_status="NOT_MEASURED",
        overall_result="PASS",
        blocking_findings=(),
    )

    assert status == "CONTROLLED_BETA"
    assert gate["status"] == "CAPPED"
    assert gate["cap"] == "CONTROLLED_BETA"


def test_browser_failure_is_a_hard_not_ready_gate() -> None:
    status, gate = _apply_maturity_hard_gates(
        99,
        browser_status="FAIL",
        overall_result="PASS",
        blocking_findings=(),
    )

    assert status == "NOT_READY"
    assert gate["status"] == "BLOCKED"
    assert "BROWSER_FAIL" in gate["reasons"]


def test_p0_and_p1_findings_are_hard_not_ready_gates() -> None:
    for severity in ("P0", "P1"):
        status, gate = _apply_maturity_hard_gates(
            99,
            browser_status="PASS",
            overall_result="PASS",
            blocking_findings=({"severity": severity},),
        )

        assert status == "NOT_READY"
        assert gate["status"] == "BLOCKED"
        assert "P0_OR_P1_FINDING" in gate["reasons"]


def test_healthy_scores_keep_the_existing_thresholds() -> None:
    assert _apply_maturity_hard_gates(80, browser_status="PASS", overall_result="PASS", blocking_findings=())[0] == "PILOT_READY"
    assert _apply_maturity_hard_gates(60, browser_status="PASS", overall_result="PASS", blocking_findings=())[0] == "CONTROLLED_BETA"
