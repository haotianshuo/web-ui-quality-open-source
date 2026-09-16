from __future__ import annotations

from web_ui_quality.quick_ui import summarize_top_ui_issues


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
