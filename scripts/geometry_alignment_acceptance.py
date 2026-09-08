"""Live, read-only acceptance for the Alpha.11 inventory fixture repair."""
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

from scripts.control_affordance_acceptance import _control_checks, _control_geometry  # noqa: E402
from scripts.keyboard_page_acceptance import _page_checks  # noqa: E402
from web_ui_quality.contracts import digest_json  # noqa: E402
from web_ui_quality.quick_ui import run_quick_ui  # noqa: E402
from web_ui_quality.release_info import EXPERIMENTAL_VERSION  # noqa: E402


VIEWPORTS = ((390, 844), (768, 1024), (1440, 900))
PAGE_MATRIX = (
    {"id": "home", "path": "/index.html", "title": "首页"},
    {"id": "users", "path": "/users.html", "title": "用户"},
    {"id": "settings", "path": "/settings.html", "title": "设置"},
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _raw(record: dict) -> dict:
    return (record.get("renderedQuality") or {}).get("raw") or {}


def _alignment_checks(report: dict, page: dict) -> dict[str, bool]:
    records = list(report.get("records") or [])
    geometries = [list((record.get("experienceGeometry") or {}).get("viewports") or []) for record in records]
    page_checks = _page_checks(report, page)
    control_checks = _control_checks(report, page)
    return {
        "threeViewports": len(records) == len(VIEWPORTS),
        "reportBoundaryPreserved": report.get("status") == "NOT_VERIFIED",
        "alignmentGeometryMeasured": all(len(items) == 1 for items in geometries),
        "alignmentWithinThreshold": all(
            value is None or float(value) <= 4
            for items in geometries
            for value in [items[0].get("alignmentDeviationPx") if items else None]
        ),
        "noAlignmentDriftTopIssue": not any(item.get("id") == "UI-ALIGNMENT-DRIFT" for item in report.get("topIssues", [])),
        "keyboardChecksPreserved": all(page_checks.values()),
        "controlChecksPreserved": all(control_checks.values()),
    }


def _alignment_rows(report: dict) -> list[dict]:
    rows = []
    for record in report.get("records") or []:
        metrics = record.get("metrics") or {}
        raw = _raw(record)
        geometries = list((record.get("experienceGeometry") or {}).get("viewports") or [])
        geometry = geometries[0] if geometries else {}
        rows.append({
            "requestedWidth": (record.get("viewport") or {}).get("width"),
            "requestedHeight": (record.get("viewport") or {}).get("height"),
            "innerWidth": metrics.get("innerWidth"),
            "innerHeight": metrics.get("innerHeight"),
            "visualViewportScale": metrics.get("visualViewportScale"),
            "alignmentDeviationPx": geometry.get("alignmentDeviationPx"),
            "alignmentAnchorCount": len(geometry.get("visual", {}).get("headings", []) or []),
            "topIssueIds": [item.get("id") for item in report.get("topIssues", []) if isinstance(item, dict)],
            "renderedFindingIds": [item.get("id") for item in (record.get("renderedQuality") or {}).get("findings", []) if isinstance(item, dict)],
            "controlTargetHeights": [item.get("height") for item in _control_geometry(record)],
            "horizontalOverflow": record.get("horizontalOverflow"),
            "mutationFirewall": (record.get("mutationFirewall") or {}).get("status"),
            "pageErrors": list(record.get("pageErrors") or []),
        })
    return rows


def main() -> int:
    demo = ROOT / "examples" / "ui-inventory-demo"
    output = ROOT / "examples" / "alignment-geometry-evidence"
    handler = functools.partial(SimpleHTTPRequestHandler, directory=str(demo))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    page_rows = []
    try:
        base_url = f"http://127.0.0.1:{server.server_port}"
        for page in PAGE_MATRIX:
            page_output = output / f"page-{page['id']}"
            report = run_quick_ui(base_url + page["path"], output_dir=page_output, viewports=VIEWPORTS, timeout_ms=10_000)
            checks = _alignment_checks(report, page)
            page_rows.append({
                "id": page["id"],
                "path": page["path"],
                "title": page["title"],
                "status": "PASS" if all(checks.values()) else "FAIL",
                "reportStatus": report.get("status"),
                "reportDigest": report.get("reportDigest"),
                "reportSha256": _sha256(page_output / "quick-ui-report.json"),
                "checks": checks,
                "viewports": _alignment_rows(report),
            })
    finally:
        server.shutdown()
        server.server_close()

    passed = len(page_rows) == len(PAGE_MATRIX) and all(row["status"] == "PASS" for row in page_rows)
    aggregate = {
        "schemaVersion": "1",
        "runId": f"wuq-{EXPERIMENTAL_VERSION}-alignment-final-20260906",
        "version": EXPERIMENTAL_VERSION,
        "status": "PASS" if passed else "FAIL",
        "reportStatus": "NOT_VERIFIED",
        "pages": page_rows,
        "resolvedGeometryAdvisory": {
            "status": "PASS" if passed else "FAIL",
            "id": "UI-ALIGNMENT-DRIFT",
            "scope": "3 pages x 3 viewports",
            "basis": "Structural card containers are excluded from the content-anchor comparison; the same render, keyboard, control, overflow, and firewall checks remain enforced",
        },
        "claimBoundary": "This acceptance proves local browser geometry-measurement behavior and preserves the bounded page/control checks for three demo pages. Enclosing quick UI reports remain NOT_VERIFIED for task outcomes; this is not a Commercial GA claim.",
    }
    aggregate["aggregateDigest"] = digest_json(aggregate)
    output.mkdir(parents=True, exist_ok=True)
    (output / "alignment-acceptance.json").write_text(json.dumps(aggregate, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": aggregate["status"],
        "pageCount": len(page_rows),
        "pageStatuses": {row["id"]: row["status"] for row in page_rows},
        "reportStatuses": {row["id"]: row["reportStatus"] for row in page_rows},
        "aggregateDigest": aggregate["aggregateDigest"],
        "resolvedGeometryAdvisory": aggregate["resolvedGeometryAdvisory"],
        "claimBoundary": aggregate["claimBoundary"],
    }, ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
