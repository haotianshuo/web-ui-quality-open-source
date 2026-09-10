from scripts.viewport_realization_acceptance import _viewport_checks


def _record(width=390, height=844, *, inner_width=None, inner_height=None):
    actual_width = width if inner_width is None else inner_width
    actual_height = height if inner_height is None else inner_height
    return {
        "viewport": {"width": width, "height": height},
        "requestedViewport": {"width": width, "height": height},
        "actualBrowserViewport": {"width": actual_width, "height": actual_height},
        "reportedEvidenceViewport": {"width": actual_width, "height": actual_height},
        "viewportNormalization": {
            "status": "MATCHED" if (actual_width, actual_height) == (width, height) else "MISMATCH",
            "requested": {"width": width, "height": height},
            "actual": {"width": actual_width, "height": actual_height},
            "reported": {"width": actual_width, "height": actual_height},
            "documentScrollWidth": width,
        },
        "metrics": {"innerWidth": actual_width, "innerHeight": actual_height, "documentScrollWidth": width},
        "horizontalOverflow": False,
        "pageErrors": [],
        "mutationFirewall": {"status": "PASS"},
        "renderedQuality": {"raw": {"viewport": {"width": width, "height": height}, "evidence": {"page": "home", "title": "首页", "pageEvidence": {"marker": "home", "path": "/index.html"}}}},
    }


def _report(records):
    return {"status": "NOT_VERIFIED", "records": records}


def test_viewport_checks_require_realized_layout_dimensions():
    records = [_record(), _record(768, 1024), _record(1440, 900)]
    assert _viewport_checks(_report(records), {"id": "home", "path": "/index.html", "title": "首页"})["viewportRealized"] is True
    records[0]["metrics"]["innerWidth"] = 980
    assert _viewport_checks(_report(records), {"id": "home", "path": "/index.html", "title": "首页"})["viewportRealized"] is False


def test_viewport_checks_keep_report_boundary_and_firewall_requirements():
    records = [_record(), _record(768, 1024), _record(1440, 900)]
    report = _report(records)
    assert _viewport_checks(report, {"id": "home", "path": "/index.html", "title": "首页"})["reportBoundaryPreserved"] is True
    records[1]["mutationFirewall"]["status"] = "FAIL"
    assert _viewport_checks(report, {"id": "home", "path": "/index.html", "title": "首页"})["mutationFirewallPass"] is False


def test_viewport_checks_require_explicit_three_way_trace_and_separate_scroll_width():
    records = [_record(), _record(768, 1024), _record(1440, 900)]
    checks = _viewport_checks(_report(records), {"id": "home", "path": "/index.html", "title": "首页"})

    assert checks["viewportEvidenceTraceable"] is True
    assert checks["documentScrollWidthSeparated"] is True

    records[0]["actualBrowserViewport"] = {"width": 980, "height": 844}
    records[0]["viewportNormalization"]["status"] = "MISMATCH"
    assert _viewport_checks(_report(records), {"id": "home", "path": "/index.html", "title": "首页"})["viewportEvidenceTraceable"] is False
