"""Live, read-only acceptance for the Alpha.7 control-affordance repair."""
from __future__ import annotations

import functools
import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import threading


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "runtime" / "python"))

from scripts.keyboard_page_acceptance import _page_checks  # noqa: E402
from web_ui_quality.contracts import digest_json  # noqa: E402
from web_ui_quality.quick_ui import run_quick_ui  # noqa: E402


VIEWPORTS = ((390, 844), (768, 1024), (1440, 900))
PAGE_MATRIX = (
    {"id": "home", "path": "/index.html", "title": "首页"},
    {"id": "users", "path": "/users.html", "title": "用户"},
    {"id": "settings", "path": "/settings.html", "title": "设置"},
)
CONTROL_ROLES = {"input", "button"}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _raw(record: dict) -> dict:
    return (record.get("renderedQuality") or {}).get("raw") or {}


def _control_geometry(record: dict) -> list[dict]:
    geometry = record.get("experienceGeometry") or {}
    viewports = list(geometry.get("viewports") or [])
    if not viewports:
        return []
    return [item for item in (viewports[0].get("buttons") or []) if item.get("role") in CONTROL_ROLES]


def _control_checks(report: dict, page: dict) -> dict[str, bool]:
    records = list(report.get("records") or [])
    quality = [(record.get("renderedQuality") or {}) for record in records]
    raw_issues = [(_raw(record).get("issues") or {}) for record in records]
    controls = [_control_geometry(record) for record in records]
    return {
        "threeViewports": len(records) == len(VIEWPORTS),
        "reportBoundaryPreserved": report.get("status") == "NOT_VERIFIED",
        "pageIdentityMeasured": all(
            (_raw(record).get("evidence") or {}).get("page") == page["id"]
            and ((_raw(record).get("evidence") or {}).get("pageEvidence") or {}).get("marker") == page["id"]
            and ((_raw(record).get("evidence") or {}).get("pageEvidence") or {}).get("path") == page["path"]
            and (_raw(record).get("evidence") or {}).get("title") == page["title"]
            for record in records
        ),
        "renderedQualityMeasured": all(
            item.get("status") in {"PASS", "PASS_WITH_WARNINGS"} for item in quality
        ),
        "lowContrastResolved": all(not issue.get("lowContrast") for issue in raw_issues),
        "smallTargetsResolved": all(not issue.get("smallTargets") for issue in raw_issues),
        "noRenderedP1Findings": all(
            not any(item.get("severity") == "P1" for item in item.get("findings", []) if isinstance(item, dict))
            for item in quality
        ),
        "controlTargetsMeasured": all(
            len(items) >= 2 and all(float(item.get("height") or 0) >= 44 for item in items)
            for items in controls
        ),
        "noPageHorizontalOverflow": all(not record.get("horizontalOverflow") for record in records),
        "mutationFirewallPass": all((record.get("mutationFirewall") or {}).get("status") == "PASS" for record in records),
        "noPageErrors": all(not record.get("pageErrors") for record in records),
    }


def _control_rows(report: dict) -> list[dict]:
    rows = []
    for record in report.get("records") or []:
        metrics = record.get("metrics") or {}
        raw = _raw(record)
        quality = record.get("renderedQuality") or {}
        issues = raw.get("issues") or {}
        controls = _control_geometry(record)
        audit = raw.get("keyboardAudit") or {}
        rows.append({
            "requestedWidth": (record.get("viewport") or {}).get("width"),
            "requestedHeight": (record.get("viewport") or {}).get("height"),
            "innerWidth": metrics.get("innerWidth"),
            "innerHeight": metrics.get("innerHeight"),
            "visualViewportScale": metrics.get("visualViewportScale"),
            "reportStatus": quality.get("status"),
            "renderedFindingIds": [item.get("id") for item in quality.get("findings", []) if isinstance(item, dict)],
            "lowContrastCount": len(issues.get("lowContrast") or []),
            "smallTargetCount": len(issues.get("smallTargets") or []),
            "controlTargetHeights": [item.get("height") for item in controls],
            "minimumControlTargetHeight": min((float(item.get("height") or 0) for item in controls), default=None),
            "keyboardCoverageStatus": (audit.get("coverage") or {}).get("status"),
            "unvisitedSampled": (audit.get("counts") or {}).get("unvisitedSampled"),
            "outOfViewport": (audit.get("counts") or {}).get("outOfViewport"),
            "horizontalOverflow": record.get("horizontalOverflow"),
            "mutationFirewall": (record.get("mutationFirewall") or {}).get("status"),
            "pageErrors": list(record.get("pageErrors") or []),
        })
    return rows


def main() -> int:
    demo = ROOT / "examples" / "ui-inventory-demo"
    output = ROOT / "examples" / "control-affordance-evidence"
    handler = functools.partial(SimpleHTTPRequestHandler, directory=str(demo))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    page_rows = []
    try:
        base_url = f"http://127.0.0.1:{server.server_port}"
        for page in PAGE_MATRIX:
            page_output = output / f"page-{page['id']}"
            report = run_quick_ui(
                base_url + page["path"],
                output_dir=page_output,
                viewports=VIEWPORTS,
                timeout_ms=10_000,
            )
            page_checks = _page_checks(report, page)
            control_checks = _control_checks(report, page)
            checks = {"keyboard": page_checks, "controls": control_checks}
            page_rows.append({
                "id": page["id"],
                "path": page["path"],
                "title": page["title"],
                "status": "PASS" if all(all(group.values()) for group in checks.values()) else "FAIL",
                "reportStatus": report.get("status"),
                "reportDigest": report.get("reportDigest"),
                "reportSha256": _sha256(page_output / "quick-ui-report.json"),
                "checks": checks,
                "viewports": _control_rows(report),
            })
    finally:
        server.shutdown()
        server.server_close()

    passed = len(page_rows) == len(PAGE_MATRIX) and all(row["status"] == "PASS" for row in page_rows)
    aggregate = {
        "schemaVersion": "1",
        "runId": "wuq-4.4.0-alpha.7-shadow-control-final-20260906",
        "version": "4.4.0-alpha.7-shadow",
        "status": "PASS" if passed else "FAIL",
        "reportStatus": "NOT_VERIFIED",
        "pages": page_rows,
        "resolvedVisualFindings": {
            "status": "PASS" if passed else "FAIL",
            "ids": ["RENDER-LOW-CONTRAST", "RENDER-SMALL-TARGET"],
            "scope": "3 pages x 3 viewports",
            "basis": "Live rendered-quality evidence contains no lowContrast or smallTargets samples and every measured input/save control is at least 44px high",
        },
        "claimBoundary": "This acceptance proves local browser-rendered control findings, target geometry, page identity, keyboard boundaries, overflow, and browser firewall behavior for three demo pages. The enclosing quick UI reports remain NOT_VERIFIED for task outcomes and this is not a Commercial GA claim.",
    }
    aggregate["aggregateDigest"] = digest_json(aggregate)
    output.mkdir(parents=True, exist_ok=True)
    (output / "control-acceptance.json").write_text(json.dumps(aggregate, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": aggregate["status"],
        "pageCount": len(page_rows),
        "pageStatuses": {row["id"]: row["status"] for row in page_rows},
        "reportStatuses": {row["id"]: row["reportStatus"] for row in page_rows},
        "aggregateDigest": aggregate["aggregateDigest"],
        "resolvedVisualFindings": aggregate["resolvedVisualFindings"],
        "claimBoundary": aggregate["claimBoundary"],
    }, ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
