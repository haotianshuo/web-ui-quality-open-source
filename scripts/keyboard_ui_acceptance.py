"""Live, read-only keyboard acceptance for the bundled commercial demo states."""
from __future__ import annotations

import functools
import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime" / "python"))

from web_ui_quality.contracts import digest_json  # noqa: E402
from web_ui_quality.quick_ui import run_quick_ui  # noqa: E402
from web_ui_quality.release_info import EXPERIMENTAL_VERSION  # noqa: E402


VIEWPORTS = ((390, 844), (768, 1024), (1440, 900))
STATE_MATRIX = (
    {"id": "initial", "query": "", "emptyVisible": False, "listItemCount": 4, "detailTitle": "Northstar Logistics"},
    {"id": "risk-filter", "query": "?state=risk-filter", "emptyVisible": False, "listItemCount": 1, "detailTitle": "Fieldnote Labs"},
    {"id": "empty-search", "query": "?state=empty-search", "emptyVisible": True, "listItemCount": 0, "detailTitle": None},
    {"id": "selected-risk", "query": "?state=selected-risk", "emptyVisible": False, "listItemCount": 4, "detailTitle": "Fieldnote Labs"},
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _raw(record: dict) -> dict:
    return (record.get("renderedQuality") or {}).get("raw") or {}


def _state_checks(report: dict, state: dict) -> dict[str, bool]:
    records = list(report.get("records") or [])
    audits = [_raw(record).get("keyboardAudit") for record in records]
    state_evidence = [(_raw(record).get("evidence") or {}).get("stateEvidence") for record in records]
    return {
        "threeViewports": len(records) == 3,
        "reportBoundaryPreserved": report.get("status") == "NOT_VERIFIED",
        "stateEvidenceMeasured": all(
            isinstance(item, dict) and item.get("marker") == state["id"] for item in state_evidence
        ),
        "stateDomMatches": all(
            isinstance(item, dict)
            and item.get("marker") == state["id"]
            and bool(item.get("emptyVisible")) == bool(state["emptyVisible"])
            and item.get("listItemCount") == state["listItemCount"]
            and item.get("detailTitle") == state["detailTitle"]
            for item in state_evidence
        ),
        "keyboardAuditMeasured": all(
            isinstance(audit, dict) and audit.get("evidenceTier") == "browser-measured" for audit in audits
        ),
        "keyboardAuditNotFailing": all(
            isinstance(audit, dict)
            and audit.get("status") in {"PASS", "PASS_WITH_WARNINGS"}
            and not any(item.get("severity") == "P1" for item in audit.get("findings", []) if isinstance(item, dict))
            for audit in audits
        ),
        "keyboardCoverageMeasured": all(
            isinstance(audit, dict)
            and (audit.get("coverage") or {}).get("status") == "MEASURED"
            and int((audit.get("counts") or {}).get("coverageUnmeasured") or 0) == 0
            for audit in audits
        ),
        "tabCoveredSample": all(
            isinstance(audit, dict)
            and int((audit.get("counts") or {}).get("unvisitedSampled") or 0) == 0
            for audit in audits
        ),
        "tabReachedControl": all(
            isinstance(audit, dict) and int((audit.get("counts") or {}).get("visited") or 0) > 0
            for audit in audits
        ),
        "focusStayedInViewport": all(
            isinstance(audit, dict) and int((audit.get("counts") or {}).get("outOfViewport") or 0) == 0
            for audit in audits
        ),
        "focusAffordanceSufficient": all(
            isinstance(audit, dict)
            and int((audit.get("counts") or {}).get("missingFocusAffordance") or 0) * 2
            < max(1, int((audit.get("counts") or {}).get("visited") or 0))
            for audit in audits
        ),
        "noPageHorizontalOverflow": all(not record.get("horizontalOverflow") for record in records),
        "mutationFirewallPass": all((record.get("mutationFirewall") or {}).get("status") == "PASS" for record in records),
    }


def _viewport_rows(report: dict) -> list[dict]:
    rows = []
    for record in report.get("records") or []:
        viewport = record.get("viewport") or {}
        audit = _raw(record).get("keyboardAudit") or {}
        counts = audit.get("counts") or {}
        coverage = audit.get("coverage") or {}
        rows.append({
            "width": viewport.get("width"),
            "height": viewport.get("height"),
            "interactive": counts.get("interactive"),
            "focusable": counts.get("focusable"),
            "steps": counts.get("stepsAttempted"),
            "visited": counts.get("visited"),
            "uniqueVisited": counts.get("uniqueVisited"),
            "sampledFocusable": counts.get("sampledFocusable"),
            "unvisitedSampled": counts.get("unvisitedSampled"),
            "coverageStatus": coverage.get("status"),
            "coverageUnmeasured": counts.get("coverageUnmeasured"),
            "outOfViewport": counts.get("outOfViewport"),
            "focusAffordanceMeasured": counts.get("focusAffordanceMeasured"),
            "focusAffordanceUnmeasured": counts.get("focusAffordanceUnmeasured"),
            "missingFocusAffordance": counts.get("missingFocusAffordance"),
            "positiveTabIndex": counts.get("positiveTabIndex"),
        })
    return rows


def main() -> int:
    demo = ROOT / "examples" / "commercial-demo"
    output = ROOT / "examples" / "keyboard-ui-evidence"
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
            checks = _state_checks(report, state)
            state_rows.append({
                "id": state["id"],
                "query": state["query"],
                "status": "PASS" if all(checks.values()) else "FAIL",
                "reportStatus": report.get("status"),
                "reportDigest": report.get("reportDigest"),
                "reportSha256": _sha256(state_output / "quick-ui-report.json"),
                "checks": checks,
                "viewports": _viewport_rows(report),
            })
    finally:
        server.shutdown()
        server.server_close()

    passed = all(row["status"] == "PASS" for row in state_rows) and len(state_rows) == len(STATE_MATRIX)
    aggregate = {
        "schemaVersion": "1",
        "runId": f"wuq-{EXPERIMENTAL_VERSION}-keyboard-state-final-20260906",
        "version": EXPERIMENTAL_VERSION,
        "status": "PASS" if passed else "FAIL",
        "reportStatus": "NOT_VERIFIED",
        "states": state_rows,
        "claimBoundary": "Keyboard and state checks cover four local demo states in three browser viewports. Each enclosing quick UI report remains NOT_VERIFIED because task outcome measurement is not run here; this is not a Commercial GA claim.",
    }
    aggregate["aggregateDigest"] = digest_json(aggregate)
    output.mkdir(parents=True, exist_ok=True)
    (output / "state-acceptance.json").write_text(json.dumps(aggregate, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": aggregate["status"],
        "stateCount": len(state_rows),
        "stateStatuses": {row["id"]: row["status"] for row in state_rows},
        "reportStatuses": {row["id"]: row["reportStatus"] for row in state_rows},
        "aggregateDigest": aggregate["aggregateDigest"],
        "claimBoundary": aggregate["claimBoundary"],
    }, ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
