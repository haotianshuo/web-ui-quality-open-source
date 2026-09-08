from scripts.viewport_realization_acceptance import _viewport_checks


def _record(width=390, height=844, *, inner_width=None, inner_height=None):
    return {
        "viewport": {"width": width, "height": height},
        "metrics": {"innerWidth": width if inner_width is None else inner_width, "innerHeight": height if inner_height is None else inner_height},
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
