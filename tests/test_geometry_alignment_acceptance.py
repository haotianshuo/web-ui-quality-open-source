from __future__ import annotations

from scripts.geometry_alignment_acceptance import _alignment_checks


def _record(*, deviation=None) -> dict:
    return {
        "renderedQuality": {
            "status": "PASS",
            "findings": [],
            "raw": {
                "issues": {"lowContrast": [], "smallTargets": []},
                "evidence": {"page": "home", "title": "首页", "pageEvidence": {"marker": "home", "path": "/index.html"}},
                "keyboardAudit": {"evidenceTier": "browser-measured", "status": "PASS", "findings": [], "coverage": {"status": "MEASURED"}, "counts": {"unvisitedSampled": 0, "outOfViewport": 0, "visited": 2}},
            },
        },
        "experienceGeometry": {"viewports": [{"alignmentDeviationPx": deviation, "visual": {"headings": [{"text": "首页"}]}, "buttons": [{"role": "input", "height": 44}, {"role": "button", "height": 44}]}]},
        "horizontalOverflow": False,
        "pageErrors": [],
        "mutationFirewall": {"status": "PASS"},
    }


def _report(records, *, top_issues=None) -> dict:
    return {"status": "NOT_VERIFIED", "records": records, "topIssues": top_issues or []}


def test_alignment_checks_accept_structural_container_safe_geometry() -> None:
    records = [_record(), _record(), _record()]
    checks = _alignment_checks(_report(records), {"id": "home", "path": "/index.html", "title": "首页"})
    assert all(checks.values())


def test_alignment_checks_reject_residual_alignment_advisory() -> None:
    records = [_record(deviation=12.5), _record(), _record()]
    checks = _alignment_checks(_report(records, top_issues=[{"id": "UI-ALIGNMENT-DRIFT"}]), {"id": "home", "path": "/index.html", "title": "首页"})
    assert checks["alignmentWithinThreshold"] is False
    assert checks["noAlignmentDriftTopIssue"] is False
