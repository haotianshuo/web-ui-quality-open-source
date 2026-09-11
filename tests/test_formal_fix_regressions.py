from __future__ import annotations

from copy import deepcopy

import pytest

from web_ui_quality.comparison_gate import evaluate_improvement_claim
from web_ui_quality.intent_router import route_user_intent
from web_ui_quality.playwright_adapter import _normalize_viewport_observation
from web_ui_quality.task_intent_adapter import normalize_task_intent


VIEWPORTS = ((390, 844), (768, 1024), (1440, 900))
TARGET_URL = "http://fixture.test/index.html"


def test_mobile_css_viewport_normalization_ignores_scaled_inner_width():
    observation = _normalize_viewport_observation(
        (390, 844),
        {
            "innerWidth": 732,
            "innerHeight": 1585,
            "clientWidth": 390,
            "clientHeight": 844,
            "visualViewportWidth": 390,
            "visualViewportHeight": 844,
            "documentScrollWidth": 520,
        },
        {"viewports": [{"width": 390, "height": 844}]},
    )

    assert observation["status"] == "MATCHED"
    assert observation["actual"] == {"width": 390, "height": 844}


def _record(
    width: int,
    height: int,
    *,
    status: str = "PASS",
    evidence_status: str = "VERIFIED",
    readiness_status: str = "READY",
    page_errors: list[str] | None = None,
    auth_wall: bool = False,
    focus_missing: int | None = 0,
    focus_measured: int | None = 1,
    low_contrast: list[dict[str, object]] | None = None,
    clipped: list[dict[str, object]] | None = None,
    overflow: bool = False,
    omit_issue: str | None = None,
) -> dict[str, object]:
    issues: dict[str, object] = {
        "lowContrast": list(low_contrast or []),
        "clipped": list(clipped or []),
        "overflowViewport": [],
    }
    if omit_issue:
        issues.pop(omit_issue, None)
    keyboard_counts: dict[str, object] = {
        "focusAffordanceMeasured": focus_measured,
        "missingFocusAffordance": focus_missing,
        "coverageUnmeasured": 0,
    }
    record: dict[str, object] = {
        "viewport": {"width": width, "height": height},
        "requestedViewport": {"width": width, "height": height},
        "actualBrowserViewport": {"width": width, "height": height},
        "reportedEvidenceViewport": {"width": width, "height": height},
        "viewportNormalization": {
            "status": "MATCHED",
            "requested": {"width": width, "height": height},
            "actual": {"width": width, "height": height},
            "reported": {"width": width, "height": height},
        },
        "status": status,
        "evidenceStatus": evidence_status,
        "httpStatus": 200,
        "validRender": True,
        "stability": {"status": "STABLE"},
        "pageErrors": list(page_errors or []),
        "criticalRequestFailures": [],
        "criticalBlockedRequests": [],
        "mutationFirewall": {"status": "PASS"},
        "resourceIntegrity": {"status": "PASS"},
        "networkPolicy": {"externalOriginsBlocked": False},
        "horizontalOverflow": overflow,
        "metrics": {"authWallHint": auth_wall, "mainPresent": True, "bodyTextLength": 80},
        "readiness": {"status": readiness_status, "readyState": "complete", "mainPresent": True},
        "renderedQuality": {
            "status": "FAIL" if low_contrast or clipped else "PASS",
            "raw": {
                "issues": issues,
                "keyboardAudit": {
                    "status": "PASS",
                    "counts": keyboard_counts,
                    "coverage": {"complete": True},
                },
                "evidence": {"url": TARGET_URL, "hasMain": True, "h1Count": 1},
            },
        },
    }
    return record


def _report(
    records: list[dict[str, object]],
    *,
    page_status: str = "NOT_VERIFIED",
    runtime_url: str = TARGET_URL,
) -> dict[str, object]:
    return {
        "target": {"url": TARGET_URL},
        "pageHealth": {"pageStatus": page_status},
        "runtime": {"url": runtime_url, "records": records},
        "journey": {"journeyId": "formal-fix-regression", "status": "NOT_EXECUTED", "journey": [], "runs": []},
        "findings": [],
    }


def _pair_reports(kind: str, *, repaired: bool) -> tuple[dict[str, object], dict[str, object]]:
    rows: list[dict[str, object]] = []
    for width, height in VIEWPORTS:
        if kind == "runtime":
            rows.append(_record(
                width,
                height,
                status="PASS" if repaired else "NOT_VERIFIED",
                evidence_status="VERIFIED" if repaired else "NOT_VERIFIED",
                readiness_status="READY" if repaired else "RUNTIME_BROKEN",
                page_errors=[] if repaired else ["TypeError: missing status target"],
            ))
        elif kind == "focus":
            rows.append(_record(width, height, focus_missing=0 if repaired else 1))
        elif kind == "contrast":
            rows.append(_record(
                width,
                height,
                status="NOT_VERIFIED",
                evidence_status="NOT_VERIFIED",
                readiness_status="AUTH_REQUIRED",
                auth_wall=True,
                low_contrast=[] if repaired else [{"selector": "button:Sign in securely", "ratio": 1.5, "threshold": 4.5}],
            ))
        elif kind == "clipping":
            rows.append(_record(
                width,
                height,
                clipped=[] if repaired else [{"selector": "[data-testid='q28-card']", "scrollHeight": 180, "clientHeight": 96}],
            ))
        else:
            raise AssertionError(kind)
    before = _report(rows if not repaired else [], page_status="AUTH_REQUIRED" if kind == "contrast" else "NOT_VERIFIED")
    after_rows: list[dict[str, object]] = []
    for width, height in VIEWPORTS:
        if kind == "runtime":
            after_rows.append(_record(width, height, status="PASS", evidence_status="VERIFIED", readiness_status="READY"))
        elif kind == "focus":
            after_rows.append(_record(width, height, focus_missing=0))
        elif kind == "contrast":
            after_rows.append(_record(
                width,
                height,
                status="NOT_VERIFIED",
                evidence_status="NOT_VERIFIED",
                readiness_status="AUTH_REQUIRED",
                auth_wall=True,
                low_contrast=[],
            ))
        elif kind == "clipping":
            after_rows.append(_record(width, height, clipped=[]))
    before_rows = []
    for width, height in VIEWPORTS:
        if kind == "runtime":
            before_rows.append(_record(
                width,
                height,
                status="NOT_VERIFIED",
                evidence_status="NOT_VERIFIED",
                readiness_status="RUNTIME_BROKEN",
                page_errors=["TypeError: missing status target"],
            ))
        elif kind == "focus":
            before_rows.append(_record(width, height, focus_missing=1))
        elif kind == "contrast":
            before_rows.append(_record(
                width,
                height,
                status="NOT_VERIFIED",
                evidence_status="NOT_VERIFIED",
                readiness_status="AUTH_REQUIRED",
                auth_wall=True,
                low_contrast=[{"selector": "button:Sign in securely", "ratio": 1.5, "threshold": 4.5}],
            ))
        elif kind == "clipping":
            before_rows.append(_record(
                width,
                height,
                clipped=[{"selector": "[data-testid='q28-card']", "scrollHeight": 180, "clientHeight": 96}],
            ))
    return _report(before_rows, page_status="AUTH_REQUIRED" if kind == "contrast" else "NOT_VERIFIED"), _report(after_rows, page_status="AUTH_REQUIRED" if kind == "contrast" else "NOT_VERIFIED")


@pytest.mark.parametrize(
    ("kind", "request_text"),
    (
        ("runtime", "修复订阅页面状态一直出错的问题"),
        ("focus", "修复工作区页面用键盘操作时看不出当前焦点的问题"),
        ("contrast", "修复登录界面按钮文字看不清的问题"),
        ("clipping", "安全中心的提示内容显示不全，帮我处理好"),
    ),
)
def test_task_specific_browser_objective_closes_formal_completion_gap(kind: str, request_text: str) -> None:
    before, after = _pair_reports(kind, repaired=False)
    result = evaluate_improvement_claim(
        before,
        after,
        condition_match=True,
        target_match=True,
        safe_task_match=True,
        browser_viewports=VIEWPORTS,
        request=request_text,
    )

    assert result["status"] == "IMPROVEMENT_CLAIM_ALLOWED"
    assert result["comparable"] is True
    assert result["evidenceBasis"] == "BROWSER_TASK_OBJECTIVE"
    assert result["taskObjective"]["status"] == "PASS"


def test_q16_objective_is_stable_across_three_clean_state_evaluations() -> None:
    before, after = _pair_reports("contrast", repaired=False)
    for _ in range(3):
        result = evaluate_improvement_claim(
            deepcopy(before),
            deepcopy(after),
            condition_match=True,
            target_match=True,
            safe_task_match=True,
            browser_viewports=VIEWPORTS,
            request="修复登录界面按钮文字看不清的问题",
        )
        assert result["status"] == "IMPROVEMENT_CLAIM_ALLOWED"


@pytest.mark.parametrize("kind", ("runtime", "focus", "contrast", "clipping"))
def test_missing_or_stale_task_measurement_never_becomes_verified(kind: str) -> None:
    before, after = _pair_reports(kind, repaired=False)
    if kind == "focus":
        for row in after["runtime"]["records"]:
            row["renderedQuality"]["raw"]["keyboardAudit"]["counts"].pop("missingFocusAffordance")
    elif kind == "contrast":
        for row in after["runtime"]["records"]:
            row["renderedQuality"]["raw"]["issues"].pop("lowContrast")
    elif kind == "clipping":
        for row in after["runtime"]["records"]:
            row["renderedQuality"]["raw"]["issues"]["clipped"] = [{"selector": "stale", "scrollHeight": 120, "clientHeight": 96}]
    else:
        for row in after["runtime"]["records"]:
            row["pageErrors"] = ["TypeError: still broken"]
            row["status"] = "NOT_VERIFIED"
            row["evidenceStatus"] = "NOT_VERIFIED"
            row["readiness"]["status"] = "RUNTIME_BROKEN"

    result = evaluate_improvement_claim(
        before,
        after,
        condition_match=True,
        target_match=True,
        safe_task_match=True,
        browser_viewports=VIEWPORTS,
        request={
            "runtime": "修复页面运行时错误",
            "focus": "修复键盘焦点不可见",
            "contrast": "修复按钮文字看不清",
            "clipping": "修复提示内容显示不全",
        }[kind],
    )
    assert result["status"] != "IMPROVEMENT_CLAIM_ALLOWED"


def test_wrong_target_incomplete_matrix_and_unreachable_after_remain_unverified() -> None:
    before, after = _pair_reports("focus", repaired=False)

    wrong_target = deepcopy(after)
    wrong_target["target"]["url"] = "http://fixture.test/other.html"
    result = evaluate_improvement_claim(
        before, wrong_target, condition_match=True, target_match=True, safe_task_match=True,
        browser_viewports=VIEWPORTS, request="修复键盘焦点不可见",
    )
    assert result["status"] != "IMPROVEMENT_CLAIM_ALLOWED"

    incomplete = deepcopy(after)
    incomplete["runtime"]["records"] = incomplete["runtime"]["records"][:2]
    result = evaluate_improvement_claim(
        before, incomplete, condition_match=True, target_match=True, safe_task_match=True,
        browser_viewports=VIEWPORTS, request="修复键盘焦点不可见",
    )
    assert result["status"] != "IMPROVEMENT_CLAIM_ALLOWED"

    unreachable = deepcopy(after)
    unreachable["runtime"]["records"] = []
    result = evaluate_improvement_claim(
        before, unreachable, condition_match=True, target_match=True, safe_task_match=True,
        browser_viewports=VIEWPORTS, request="修复键盘焦点不可见",
    )
    assert result["status"] != "IMPROVEMENT_CLAIM_ALLOWED"


def test_unrecognized_changed_field_does_not_create_a_false_verified_claim() -> None:
    before, after = _pair_reports("focus", repaired=False)
    for row in before["runtime"]["records"]:
        row["customMetric"] = {"before": True}
    for row in after["runtime"]["records"]:
        row["customMetric"] = {"after": True}
        row["renderedQuality"]["raw"]["keyboardAudit"]["counts"]["missingFocusAffordance"] = 1
    result = evaluate_improvement_claim(
        before, after, condition_match=True, target_match=True, safe_task_match=True,
        browser_viewports=VIEWPORTS, request="修复一个未定义的页面问题",
    )
    assert result["status"] != "IMPROVEMENT_CLAIM_ALLOWED"


def test_scoped_write_is_not_whole_task_read_only() -> None:
    result = normalize_task_intent(
        "修复用量详情页在手机上的横向溢出。只允许改 styles.css；其它文件包括 package.json 和 README.md 都禁止修改。"
    )

    assert result["taskIntent"] == "REPAIR"
    assert result["conflictStatus"] == "NONE"
    assert result["writeRequested"] is True
    assert result["readOnlyRequired"] is False
    assert result["scopeIntent"] == "WRITE_ALLOWED_WITH_SCOPE"
    assert result["allowedWriteScope"] == ["styles.css"]
    assert any("package.json" in item for item in result["protectedScope"])
    assert result["requiresHostApproval"] is True


@pytest.mark.parametrize(
    "text",
    (
        "安全中心的提示内容在手机上显示不全，帮我处理好，并确认完整内容能看见。",
        "请修复 Security Center 的提示内容显示不全问题。",
        "调整安全设置页面的移动端布局。",
    ),
)
def test_business_name_security_words_do_not_trigger_specialized_audit(text: str) -> None:
    result = route_user_intent(text)

    assert result["taskIntent"] == "REPAIR_SMALL"
    assert result["specializedAuditRequired"] is False


def test_explicit_security_audit_still_routes_to_specialized_audit() -> None:
    result = route_user_intent("请做一次安全审计，检查这个页面有没有安全问题")

    assert result["taskIntent"] == "SPECIALIZED_AUDIT"
    assert result["specializedAuditRequired"] is True
