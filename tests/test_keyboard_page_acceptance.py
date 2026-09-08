from __future__ import annotations

from scripts.keyboard_page_acceptance import _page_checks


def _report(*, marker: str = "home", path: str = "/index.html", title: str = "首页") -> dict:
    audit = {
        "evidenceTier": "browser-measured",
        "status": "PASS",
        "coverage": {"status": "MEASURED"},
        "findings": [],
        "counts": {
            "coverageUnmeasured": 0,
            "missingFocusAffordance": 0,
            "outOfViewport": 0,
            "unvisitedSampled": 0,
            "visited": 2,
        },
    }
    raw = {
        "keyboardAudit": audit,
        "evidence": {
            "page": marker,
            "pageEvidence": {"marker": marker, "path": path},
            "title": title,
        },
    }
    record = {"renderedQuality": {"raw": raw}, "horizontalOverflow": False, "mutationFirewall": {"status": "PASS"}}
    return {"status": "NOT_VERIFIED", "records": [record, record, record]}


def test_page_checks_require_measured_marker_and_keyboard_boundaries() -> None:
    checks = _page_checks(_report(), {"id": "home", "path": "/index.html", "title": "首页"})
    assert all(checks.values())


def test_page_checks_reject_wrong_page_identity() -> None:
    checks = _page_checks(_report(marker="users", path="/users.html", title="用户"), {"id": "home", "path": "/index.html", "title": "首页"})
    assert checks["pageIdentityMeasured"] is False
    assert checks["pageTitlesMeasured"] is False
