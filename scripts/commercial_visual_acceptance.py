"""Live, read-only rendered-quality acceptance for the commercial demo states."""
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
sys.path.insert(0, str(ROOT / "scripts"))

from web_ui_quality.contracts import digest_json  # noqa: E402
from web_ui_quality.quick_ui import run_quick_ui  # noqa: E402
from web_ui_quality.release_info import EXPERIMENTAL_VERSION  # noqa: E402
from keyboard_ui_acceptance import (  # noqa: E402
    STATE_MATRIX,
    VIEWPORTS,
    _sha256,
    _state_checks,
    _viewport_rows,
)


TARGETED_FINDING_IDS = frozenset({
    "RENDER-LOW-CONTRAST",
    "RENDER-OVERSIZED-CONTROL",
    "RENDER-SMALL-TARGET",
    "RENDER-TINY-TEXT",
})


def _rendered_findings(report: dict) -> list[dict]:
    findings = []
    for record in report.get("records") or []:
        viewport = record.get("viewport") or {}
        for finding in (record.get("renderedQuality") or {}).get("findings") or []:
            if not isinstance(finding, dict):
                continue
            findings.append({
                "id": finding.get("id"),
                "severity": finding.get("severity"),
                "count": finding.get("count"),
                "width": viewport.get("width"),
                "height": viewport.get("height"),
            })
    return findings


def _count_findings(findings: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for finding in findings:
        finding_id = str(finding.get("id") or "UNKNOWN")
        counts[finding_id] = counts.get(finding_id, 0) + int(finding.get("count") or 0)
    return dict(sorted(counts.items()))


def _visual_checks(report: dict) -> dict[str, bool]:
    records = list(report.get("records") or [])
    findings = _rendered_findings(report)
    targeted = [item for item in findings if item.get("id") in TARGETED_FINDING_IDS]
    rendered_statuses = [
        (record.get("renderedQuality") or {}).get("status")
        for record in records
    ]
    return {
        "threeViewports": len(records) == 3,
        "reportBoundaryPreserved": report.get("status") == "NOT_VERIFIED",
        "renderedQualityMeasured": bool(records) and all(
            status in {"PASS", "PASS_WITH_WARNINGS"} for status in rendered_statuses
        ),
        "targetedVisualFindingsAbsent": not targeted,
        "noP1TargetedFinding": not any(
            item.get("severity") == "P1" for item in targeted
        ),
    }


def main() -> int:
    demo = ROOT / "examples" / "commercial-demo"
    output = ROOT / "examples" / "commercial-visual-evidence"
    output.mkdir(parents=True, exist_ok=True)
    handler = functools.partial(SimpleHTTPRequestHandler, directory=str(demo))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    state_rows = []
    try:
        base_url = f"http://127.0.0.1:{server.server_port}/index.html"
        for state in STATE_MATRIX:
            state_output = output / f"state-{state['id']}"
            report = run_quick_ui(
                base_url + state["query"],
                output_dir=state_output,
                viewports=VIEWPORTS,
                timeout_ms=10_000,
            )
            state_checks = _state_checks(report, state)
            visual_checks = _visual_checks(report)
            findings = _rendered_findings(report)
            checks = {**state_checks, **visual_checks}
            state_rows.append({
                "id": state["id"],
                "query": state["query"],
                "status": "PASS" if all(checks.values()) else "FAIL",
                "reportStatus": report.get("status"),
                "reportDigest": report.get("reportDigest"),
                "reportSha256": _sha256(state_output / "quick-ui-report.json"),
                "checks": checks,
                "renderedFindingCounts": _count_findings(findings),
                "renderedFindings": findings,
                "viewports": _viewport_rows(report),
            })
    finally:
        server.shutdown()
        server.server_close()

    passed = all(row["status"] == "PASS" for row in state_rows) and len(state_rows) == len(STATE_MATRIX)
    aggregate = {
        "schemaVersion": "1",
        "runId": f"wuq-{EXPERIMENTAL_VERSION}-commercial-visual-final-20260906",
        "version": EXPERIMENTAL_VERSION,
        "status": "PASS" if passed else "FAIL",
        "reportStatus": "NOT_VERIFIED",
        "states": state_rows,
        "targetedFindings": sorted(TARGETED_FINDING_IDS),
        "claimBoundary": "Rendered-quality findings are measured for four local commercial-demo states in three browser viewports. The targeted low-contrast, tiny-text, small-target, and oversized-control findings are absent when this acceptance passes; enclosing quick UI reports remain NOT_VERIFIED and this is not a Commercial GA claim.",
    }
    aggregate["aggregateDigest"] = digest_json(aggregate)
    (output / "state-acceptance.json").write_text(
        json.dumps(aggregate, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": aggregate["status"],
        "stateCount": len(state_rows),
        "stateStatuses": {row["id"]: row["status"] for row in state_rows},
        "reportStatuses": {row["id"]: row["reportStatus"] for row in state_rows},
        "renderedFindingCounts": {
            row["id"]: row["renderedFindingCounts"] for row in state_rows
        },
        "aggregateDigest": aggregate["aggregateDigest"],
        "claimBoundary": aggregate["claimBoundary"],
    }, ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
