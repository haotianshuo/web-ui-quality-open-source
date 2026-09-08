from __future__ import annotations

from web_ui_quality.rendered_quality import _summarize_keyboard_audit


def _baseline(*, enabled: int = 2, focusable: int = 2, positive: int = 0) -> dict:
    base_style = {
        "outlineStyle": "none",
        "outlineWidth": 0,
        "outlineColor": "rgb(0, 0, 0)",
        "boxShadow": "none",
        "borderTopColor": "rgb(200, 200, 200)",
        "borderTopWidth": 1,
        "backgroundColor": "rgb(255, 255, 255)",
    }
    return {
        "interactiveCount": enabled,
        "enabledInteractiveCount": enabled,
        "focusableCount": focusable,
        "positiveTabIndexCount": positive,
        "focusables": [
            {"index": index, "selector": f"#control-{index}", "tabIndex": 0, "baseStyle": base_style}
            for index in range(focusable)
        ],
    }


def _observation(index: int, *, affordance: bool = True, in_viewport: bool = True) -> dict:
    return {
        "index": index,
        "focused": True,
        "selector": f"#control-{index}",
        "name": f"Control {index}",
        "role": "button",
        "tabIndex": 0,
        "inViewport": in_viewport,
        "focusVisible": affordance,
        "focusStyle": {
            "outlineStyle": "solid" if affordance else "none",
            "outlineWidth": 3 if affordance else 0,
            "outlineColor": "rgb(0, 100, 255)" if affordance else "rgb(0, 0, 0)",
            "boxShadow": "none",
            "borderTopColor": "rgb(200, 200, 200)",
            "borderTopWidth": 1,
            "backgroundColor": "rgb(255, 255, 255)",
        },
    }


def test_keyboard_audit_passes_with_reachable_visible_focus() -> None:
    result = _summarize_keyboard_audit(
        _baseline(),
        [_observation(0), _observation(1), _observation(0)],
    )

    assert result["status"] == "PASS"
    assert result["counts"]["visited"] == 3
    assert result["counts"]["focusAdvance"] == 2
    assert result["counts"]["missingFocusAffordance"] == 0
    assert result["findings"] == []


def test_keyboard_audit_blocks_when_focus_affordance_is_missing() -> None:
    result = _summarize_keyboard_audit(
        _baseline(),
        [_observation(0, affordance=False), _observation(1, affordance=False)],
    )

    assert result["status"] == "FAIL"
    assert result["counts"]["missingFocusAffordance"] == 2
    assert result["findings"][0]["id"] == "RENDER-KEYBOARD-FOCUS-AFFORDANCE"
    assert result["findings"][0]["reasonCode"] == "FOCUS_AFFORDANCE_MISSING"


def test_keyboard_audit_records_offscreen_focus_and_positive_tabindex() -> None:
    result = _summarize_keyboard_audit(
        _baseline(positive=1),
        [_observation(0, in_viewport=False), _observation(1)],
    )

    assert result["status"] == "FAIL"
    assert result["counts"]["outOfViewport"] == 1
    assert {item["id"] for item in result["findings"]} == {
        "RENDER-KEYBOARD-FOCUS-OFFSCREEN",
        "RENDER-KEYBOARD-POSITIVE-TABINDEX",
    }


def test_keyboard_audit_blocks_when_tab_skips_a_sampled_control() -> None:
    result = _summarize_keyboard_audit(
        _baseline(focusable=3),
        [_observation(0), _observation(2), _observation(0)],
    )

    assert result["status"] == "FAIL"
    assert result["counts"]["uniqueVisited"] == 2
    assert result["counts"]["unvisitedSampled"] == 1
    assert result["coverage"]["status"] == "MEASURED"
    assert result["findings"][-1]["id"] == "RENDER-KEYBOARD-COVERAGE"
    assert result["findings"][-1]["reasonCode"] == "TAB_SAMPLE_NOT_COVERED"


def test_keyboard_audit_preserves_not_applicable_and_unreachable_boundaries() -> None:
    not_applicable = _summarize_keyboard_audit(
        {"interactiveCount": 0, "enabledInteractiveCount": 0, "focusableCount": 0},
        (),
    )
    unreachable = _summarize_keyboard_audit(
        {"interactiveCount": 2, "enabledInteractiveCount": 2, "focusableCount": 0},
        (),
    )

    assert not_applicable["status"] == "NOT_APPLICABLE"
    assert not_applicable["reasonCode"] == "NO_ENABLED_INTERACTIVE_CONTROLS"
    assert unreachable["status"] == "FAIL"
    assert unreachable["reasonCode"] == "NO_KEYBOARD_REACHABLE_CONTROLS"
    assert unreachable["findings"][0]["id"] == "RENDER-KEYBOARD-UNREACHABLE"


def test_keyboard_audit_does_not_promote_focus_styles_beyond_the_sample_limit() -> None:
    baseline = _baseline(enabled=61, focusable=61)
    baseline["focusables"] = baseline["focusables"][:1]
    result = _summarize_keyboard_audit(baseline, [_observation(60, affordance=False)])

    assert result["status"] == "PASS_WITH_WARNINGS"
    assert result["reasonCode"] == "KEYBOARD_SAMPLE_LIMIT_REACHED"
    assert result["counts"]["focusAffordanceMeasured"] == 0
    assert result["counts"]["focusAffordanceUnmeasured"] == 1
    assert result["samples"][0]["focusAffordance"] == "not_measured"


def test_keyboard_audit_keeps_short_traversal_unverified() -> None:
    result = _summarize_keyboard_audit(_baseline(), [_observation(0)])

    assert result["status"] == "PASS_WITH_WARNINGS"
    assert result["reasonCode"] == "KEYBOARD_COVERAGE_NOT_MEASURED"
    assert result["coverage"]["status"] == "NOT_MEASURED"
