from __future__ import annotations

from scripts.commercial_visual_acceptance import _visual_checks


def _report(findings=None, status="PASS"):
    return {
        "status": "NOT_VERIFIED",
        "records": [
            {"renderedQuality": {"status": status, "findings": findings or []}},
            {"renderedQuality": {"status": status, "findings": findings or []}},
            {"renderedQuality": {"status": status, "findings": findings or []}},
        ],
    }


def test_visual_acceptance_requires_clean_targeted_rendered_quality():
    checks = _visual_checks(_report())

    assert all(checks.values())


def test_visual_acceptance_rejects_a_targeted_rendered_finding():
    checks = _visual_checks(_report([{"id": "RENDER-SMALL-TARGET", "severity": "P2", "count": 1}]))

    assert checks["reportBoundaryPreserved"] is True
    assert checks["targetedVisualFindingsAbsent"] is False
    assert checks["noP1TargetedFinding"] is True
