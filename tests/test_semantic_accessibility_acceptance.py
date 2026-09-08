from __future__ import annotations

from scripts.semantic_accessibility_acceptance import _finding_counts, _semantic_checks


def _records(*, explicit: bool):
    return [
        {
            "expectedMarker": page,
            "pageErrors": [],
            "nonReadOnlyRequests": [],
            "quickUiStatus": "NOT_VERIFIED",
            "semantic": {
                "marker": page,
                "controls": [{"explicit": explicit, "height": 44}],
                "navs": [{"explicit": explicit}],
                "targetHeights": [{"height": 44}],
                "horizontalOverflow": False,
            },
        }
        for page in ("home", "users", "settings")
    ]


def test_semantic_acceptance_requires_explicit_names():
    checks = _semantic_checks(_records(explicit=True), require_explicit_names=True)

    assert all(checks.values())


def test_semantic_acceptance_exposes_baseline_findings():
    records = _records(explicit=False)
    checks = _semantic_checks(records, require_explicit_names=False)

    assert checks["explicitControlNames"] is True
    assert checks["namedNavigationLandmarks"] is True
    assert _finding_counts(records) == {
        "UNLABELLED_FORM_CONTROL": 3,
        "UNNAMED_NAVIGATION_LANDMARK": 3,
        "SMALL_INTERACTIVE_TARGET": 0,
    }
