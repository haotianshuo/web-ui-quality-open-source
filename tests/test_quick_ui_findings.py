from __future__ import annotations

from web_ui_quality.quick_ui import summarize_top_ui_issues
from web_ui_quality.page_health import evaluate_page_health
from web_ui_quality.readiness import assess_readiness
from web_ui_quality.playwright_adapter import _structural_stability_signature
from web_ui_quality.smart_acceptance import _finding_candidates


def _record(*, page_status: str, evidence_status: str = "VERIFIED") -> dict:
    return {
        "pageHealth": {"pageStatus": page_status},
        "evidenceStatus": evidence_status,
        "status": "PASS",
        "viewport": {"width": 390, "height": 844},
        "renderedQuality": {
            "findings": [
                {
                    "id": "RENDER-CLIPPED-CONTENT",
                    "severity": "P1",
                    "title": "存在被隐藏溢出裁切的文本内容",
                    "samples": [{"selector": ".ticker-wrap"}],
                }
            ]
        },
        "experienceGeometry": {
            "viewports": [
                {
                    "fixedOcclusions": [{"overlay": "#boot", "target": "button:WORLD"}],
                    "overlaps": [],
                    "dialogs": [],
                    "navigation": [],
                }
            ]
        },
    }


def test_non_ready_page_does_not_promote_transient_geometry_to_ui_defects() -> None:
    issues = summarize_top_ui_issues([_record(page_status="NOT_VERIFIED", evidence_status="NOT_VERIFIED")], limit=10)

    assert [item["id"] for item in issues] == ["PAGE-NOT-VERIFIED"]


def test_ready_page_preserves_rendered_and_geometry_findings() -> None:
    issues = summarize_top_ui_issues([_record(page_status="REAL_PAGE_READY")], limit=10)

    assert {item["id"] for item in issues} == {"UI-FIXED-OCCLUSION", "RENDER-CLIPPED-CONTENT"}


def test_not_verified_evidence_blocks_visuals_even_when_page_status_is_ready() -> None:
    issues = summarize_top_ui_issues([_record(page_status="REAL_PAGE_READY", evidence_status="NOT_VERIFIED")], limit=10)

    assert [item["id"] for item in issues] == []


def test_blocked_page_keeps_independent_http_failure_visible() -> None:
    record = _record(page_status="RUNTIME_BROKEN", evidence_status="NOT_VERIFIED")
    record.update({"status": "FAIL", "httpStatus": 503, "errorMessage": "HTTP 503"})

    issues = summarize_top_ui_issues([record], limit=10)

    assert {item["id"] for item in issues} == {"PAGE-RUNTIME-BROKEN", "HTTP_SERVER_ERROR"}


def test_quick_ui_page_health_is_ready_when_capture_has_no_journey() -> None:
    readiness = assess_readiness(
        {"readyState": "complete", "mainPresent": True, "textLength": 120},
        http_status=200,
    )

    health = evaluate_page_health(readiness=readiness, resource_integrity={"status": "PASS"}, task_status="PASS")

    assert health["taskStatus"] == "PASS"
    assert health["pageStatus"] == "REAL_PAGE_READY"


def test_browser_stability_ignores_live_data_counters_but_not_layout_changes() -> None:
    first = {"readyState": "complete", "childCount": 100, "textLength": 1000, "scrollWidth": 390, "scrollHeight": 844}
    second = {"readyState": "complete", "childCount": 150, "textLength": 1200, "scrollWidth": 390, "scrollHeight": 844}
    changed_layout = {**second, "scrollHeight": 960}

    assert _structural_stability_signature(first) == _structural_stability_signature(second)
    assert _structural_stability_signature(first) != _structural_stability_signature(changed_layout)


def test_page_health_boundary_is_not_promoted_to_verified_ui_finding() -> None:
    candidates = _finding_candidates(
        url="http://localhost:3131/",
        quick_report={
            "topIssues": [{
                "id": "PAGE-DATA-NOT-READY",
                "title": "页面仍停留在加载或骨架状态",
                "userLabel": "现在会出错",
                "viewports": ["390x844"],
                "samples": [{"evidence": {}}],
            }],
            "records": [],
        },
        journey_report={"runs": []},
        preflight={"warnings": []},
    )

    assert candidates[0]["issueType"] == "RUNTIME_HEALTH"
    assert candidates[0]["evidenceKinds"] == ["runtime"]
    assert candidates[0]["verificationState"] == "NOT_VERIFIED"
    assert candidates[0]["resultLabel"] == "暂时无法确认"


def test_page_runtime_failure_remains_a_verified_runtime_finding() -> None:
    candidates = _finding_candidates(
        url="http://localhost:3131/",
        quick_report={
            "topIssues": [{
                "id": "PAGE-RUNTIME-BROKEN",
                "title": "页面运行时已经损坏",
                "userLabel": "现在会出错",
                "viewports": ["390x844"],
                "samples": [{"evidence": {}}],
            }],
            "records": [],
        },
        journey_report={"runs": []},
        preflight={"warnings": []},
    )

    assert candidates[0]["issueType"] == "RUNTIME_HEALTH"
    assert candidates[0]["evidenceKinds"] == ["runtime"]
    assert candidates[0]["verificationState"] == "VERIFIED"
