from __future__ import annotations

from scripts.control_affordance_acceptance import _control_checks


def _record(*, low_contrast=None, small_targets=None, heights=(44, 44)) -> dict:
    controls = [
        {"role": "input", "height": heights[0]},
        {"role": "button", "height": heights[1]},
    ]
    return {
        "renderedQuality": {
            "status": "PASS",
            "findings": [],
            "raw": {
                "issues": {"lowContrast": low_contrast or [], "smallTargets": small_targets or []},
                "evidence": {
                    "page": "home",
                    "title": "首页",
                    "pageEvidence": {"marker": "home", "path": "/index.html"},
                },
                "keyboardAudit": {"evidenceTier": "browser-measured", "coverage": {"status": "MEASURED"}, "counts": {"unvisitedSampled": 0, "outOfViewport": 0, "visited": 2}},
            },
        },
        "experienceGeometry": {"viewports": [{"buttons": controls}]},
        "horizontalOverflow": False,
        "pageErrors": [],
        "mutationFirewall": {"status": "PASS"},
    }


def _report(*records: dict) -> dict:
    return {"status": "NOT_VERIFIED", "records": list(records)}


def test_control_checks_require_clean_rendered_findings_and_44px_targets() -> None:
    report = _report(_record(), _record(), _record())
    checks = _control_checks(report, {"id": "home", "path": "/index.html", "title": "首页"})
    assert all(checks.values())


def test_control_checks_reject_residual_visual_findings_or_small_targets() -> None:
    report = _report(_record(low_contrast=[{"ratio": 4.1}]), _record(small_targets=[{"height": 40}]), _record(heights=(40, 44)))
    checks = _control_checks(report, {"id": "home", "path": "/index.html", "title": "首页"})
    assert checks["lowContrastResolved"] is False
    assert checks["smallTargetsResolved"] is False
    assert checks["controlTargetsMeasured"] is False
