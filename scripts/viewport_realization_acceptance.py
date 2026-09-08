"""Live, read-only acceptance for requested versus realized browser viewports."""
from __future__ import annotations

import functools
import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import threading


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime" / "python"))

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


def _viewport_checks(report: dict, page: dict) -> dict[str, bool]:
    records = list(report.get("records") or [])
    checks = {
        "threeViewports": len(records) == len(VIEWPORTS),
        "reportBoundaryPreserved": report.get("status") == "NOT_VERIFIED",
        "pageIdentityMeasured": True,
        "viewportRealized": True,
        "noHorizontalOverflow": True,
        "mutationFirewallPass": True,
        "noPageErrors": True,
    }
    if len(records) != len(VIEWPORTS):
        return checks
    for record, (width, height) in zip(records, VIEWPORTS):
        raw = _raw(record)
        evidence = raw.get("evidence") or {}
        page_evidence = evidence.get("pageEvidence") or {}
        metrics = record.get("metrics") or {}
        realized = raw.get("viewport") or {}
        checks["pageIdentityMeasured"] = checks["pageIdentityMeasured"] and (
            evidence.get("page") == page["id"]
            and page_evidence.get("marker") == page["id"]
            and page_evidence.get("path") == page["path"]
            and evidence.get("title") == page["title"]
        )
        checks["viewportRealized"] = checks["viewportRealized"] and (
            record.get("viewport") == {"width": width, "height": height}
            and metrics.get("innerWidth") == width
            and metrics.get("innerHeight") == height
            and realized.get("width") == width
            and realized.get("height") == height
        )
        checks["noHorizontalOverflow"] = checks["noHorizontalOverflow"] and not record.get("horizontalOverflow")
        checks["mutationFirewallPass"] = checks["mutationFirewallPass"] and (record.get("mutationFirewall") or {}).get("status") == "PASS"
        checks["noPageErrors"] = checks["noPageErrors"] and not record.get("pageErrors")
    return checks


def _viewport_rows(report: dict) -> list[dict]:
    rows = []
    for record in report.get("records") or []:
        metrics = record.get("metrics") or {}
        raw = _raw(record)
        rows.append({
            "requestedWidth": (record.get("viewport") or {}).get("width"),
            "requestedHeight": (record.get("viewport") or {}).get("height"),
            "innerWidth": metrics.get("innerWidth"),
            "innerHeight": metrics.get("innerHeight"),
            "realizedWidth": (raw.get("viewport") or {}).get("width"),
            "realizedHeight": (raw.get("viewport") or {}).get("height"),
            "visualViewportScale": metrics.get("visualViewportScale"),
            "horizontalOverflow": record.get("horizontalOverflow"),
            "renderedQualityStatus": (record.get("renderedQuality") or {}).get("status"),
            "renderedFindingIds": [item.get("id") for item in (record.get("renderedQuality") or {}).get("findings", []) if isinstance(item, dict)],
        })
    return rows


def main() -> int:
    demo = ROOT / "examples" / "ui-inventory-demo"
    output = ROOT / "examples" / "viewport-realization-evidence"
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
            checks = _viewport_checks(report, page)
            page_rows.append({
                "id": page["id"],
                "path": page["path"],
                "title": page["title"],
                "status": "PASS" if all(checks.values()) else "FAIL",
                "reportStatus": report.get("status"),
                "reportDigest": report.get("reportDigest"),
                "reportSha256": _sha256(page_output / "quick-ui-report.json"),
                "checks": checks,
                "viewports": _viewport_rows(report),
            })
    finally:
        server.shutdown()
        server.server_close()

    passed = len(page_rows) == len(PAGE_MATRIX) and all(row["status"] == "PASS" for row in page_rows)
    aggregate = {
        "schemaVersion": "1",
        "runId": f"wuq-{EXPERIMENTAL_VERSION}-viewport-final-20260906",
        "version": EXPERIMENTAL_VERSION,
        "status": "PASS" if passed else "FAIL",
        "reportStatus": "NOT_VERIFIED",
        "pages": page_rows,
        "claimBoundary": "This acceptance proves requested versus realized local browser viewport dimensions, page identity, overflow, and browser firewall behavior for three demo pages. It does not prove all visual findings, task outcomes, assistive-technology behavior, Real Codex Host behavior, or Commercial GA.",
    }
    aggregate["aggregateDigest"] = digest_json(aggregate)
    output.mkdir(parents=True, exist_ok=True)
    (output / "viewport-acceptance.json").write_text(json.dumps(aggregate, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": aggregate["status"],
        "pageCount": len(page_rows),
        "pageStatuses": {row["id"]: row["status"] for row in page_rows},
        "reportStatuses": {row["id"]: row["reportStatus"] for row in page_rows},
        "aggregateDigest": aggregate["aggregateDigest"],
        "claimBoundary": aggregate["claimBoundary"],
    }, ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
