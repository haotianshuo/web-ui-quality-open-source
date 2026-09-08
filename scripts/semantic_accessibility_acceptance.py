"""Live, read-only semantic accessibility acceptance for the inventory demo."""
from __future__ import annotations

import argparse
import functools
import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import threading


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime" / "python"))

from web_ui_quality.browser_locator import resolve_browser_executable  # noqa: E402
from web_ui_quality.contracts import digest_json  # noqa: E402
from web_ui_quality.quick_ui import run_quick_ui  # noqa: E402
from web_ui_quality.release_info import EXPERIMENTAL_VERSION  # noqa: E402

PREVIOUS_EXPERIMENTAL_VERSION = "4.4.0-alpha.14-shadow"


VIEWPORTS = ((390, 844), (768, 1024), (1440, 900))
PAGES = (
    {"id": "home", "path": "/index.html", "title": "首页"},
    {"id": "users", "path": "/users.html", "title": "用户"},
    {"id": "settings", "path": "/settings.html", "title": "设置"},
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _scope_digest() -> tuple[str, list[dict[str, object]]]:
    rows = []
    demo = ROOT / "examples" / "ui-inventory-demo"
    for path in sorted(demo.rglob("*"), key=lambda item: item.relative_to(ROOT).as_posix().encode("utf-8")):
        if not path.is_file():
            continue
        data = path.read_bytes()
        rows.append({
            "path": path.relative_to(ROOT).as_posix(),
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        })
    h = hashlib.sha256()
    for row in rows:
        h.update(str(row["path"]).encode("utf-8"))
        h.update(b"\0")
        h.update(str(row["sha256"]).encode("ascii"))
        h.update(b"\n")
    return h.hexdigest(), rows


def _semantic_probe(page) -> dict:
    return page.evaluate(
        """
        () => {
          const text = (node) => (node?.textContent || '').trim().replace(/\\s+/g, ' ');
          const labelledByText = (node) => (node?.getAttribute('aria-labelledby') || '')
            .split(/\\s+/).filter(Boolean)
            .map((id) => text(document.getElementById(id))).filter(Boolean).join(' ');
          const explicitName = (node) => {
            const aria = (node.getAttribute('aria-label') || '').trim();
            const labelledBy = labelledByText(node);
            const id = node.getAttribute('id');
            const associated = id
              ? [...document.querySelectorAll('label[for]')]
                  .find((label) => label.getAttribute('for') === id)
              : null;
            const wrapping = node.closest('label');
            const labelText = text(associated || wrapping);
            return {
              explicit: Boolean(aria || labelledBy || labelText),
              source: aria ? 'aria-label' : labelledBy ? 'aria-labelledby' : labelText ? 'label' : null,
              name: aria || labelledBy || labelText || '',
            };
          };
          const controls = [...document.querySelectorAll('input, select, textarea')].map((node) => ({
            tag: node.tagName.toLowerCase(),
            id: node.id || null,
            placeholder: node.getAttribute('placeholder') || null,
            ...explicitName(node),
          }));
          const navs = [...document.querySelectorAll('nav')].map((node) => ({
            ariaLabel: node.getAttribute('aria-label') || null,
            labelledBy: labelledByText(node),
            name: (node.getAttribute('aria-label') || labelledByText(node) || '').trim(),
            explicit: Boolean((node.getAttribute('aria-label') || '').trim() || labelledByText(node)),
          }));
          const targetHeights = [...document.querySelectorAll('input, select, textarea, button, a[href]')]
            .filter((node) => {
              const style = getComputedStyle(node);
              const rect = node.getBoundingClientRect();
              return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
            })
            .map((node) => ({
              tag: node.tagName.toLowerCase(),
              selector: node.id ? `#${node.id}` : node.className ? `.${String(node.className).split(' ')[0]}` : node.tagName.toLowerCase(),
              height: Math.round(node.getBoundingClientRect().height * 100) / 100,
            }));
          return {
            marker: document.body?.dataset?.wuqPage || null,
            title: document.title || '',
            controls,
            navs,
            targetHeights,
            innerWidth: window.innerWidth,
            innerHeight: window.innerHeight,
            horizontalOverflow: document.documentElement.scrollWidth > window.innerWidth + 1,
          };
        }
        """
    )


def _semantic_checks(records: list[dict], *, require_explicit_names: bool) -> dict[str, bool]:
    controls = [item for record in records for item in record.get("semantic", {}).get("controls", [])]
    navs = [item for record in records for item in record.get("semantic", {}).get("navs", [])]
    return {
        "threeViewports": len(records) == 3,
        "pageIdentityMeasured": bool(records) and all(record.get("semantic", {}).get("marker") == record.get("expectedMarker") for record in records),
        "explicitControlNames": bool(controls) and all(item.get("explicit") for item in controls) if require_explicit_names else not all(item.get("explicit") for item in controls),
        "namedNavigationLandmarks": bool(navs) and all(item.get("explicit") for item in navs) if require_explicit_names else not all(item.get("explicit") for item in navs),
        "noPageHorizontalOverflow": bool(records) and all(not record.get("semantic", {}).get("horizontalOverflow") for record in records),
        "controlTargetsAtLeast44": bool(records) and all(float(item.get("height") or 0) >= 44 for record in records for item in record.get("semantic", {}).get("targetHeights", [])),
        "noPageErrors": bool(records) and all(not record.get("pageErrors") for record in records),
        "readOnlyRequests": bool(records) and all(not record.get("nonReadOnlyRequests") for record in records),
        "quickUiBoundaryPreserved": bool(records) and all(record.get("quickUiStatus") == "NOT_VERIFIED" for record in records),
    }


def _finding_counts(records: list[dict]) -> dict[str, int]:
    counts = {
        "UNLABELLED_FORM_CONTROL": 0,
        "UNNAMED_NAVIGATION_LANDMARK": 0,
        "SMALL_INTERACTIVE_TARGET": 0,
    }
    for record in records:
        semantic = record.get("semantic") or {}
        counts["UNLABELLED_FORM_CONTROL"] += sum(not item.get("explicit") for item in semantic.get("controls", []))
        counts["UNNAMED_NAVIGATION_LANDMARK"] += sum(not item.get("explicit") for item in semantic.get("navs", []))
        counts["SMALL_INTERACTIVE_TARGET"] += sum(
            float(item.get("height") or 0) < 44
            for item in semantic.get("targetHeights", [])
        )
    return counts


def _direct_page_records(base_url: str, page_spec: dict, browser_executable: str) -> list[dict]:
    from playwright.sync_api import sync_playwright

    records = []
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch(headless=True, executable_path=browser_executable)
        try:
            for width, height in VIEWPORTS:
                page = browser.new_page(viewport={"width": width, "height": height})
                page_errors: list[str] = []
                requests: list[str] = []
                page.on("pageerror", lambda error: page_errors.append(str(error)[:300]))
                page.on("request", lambda request: requests.append(request.method))
                response = page.goto(base_url + page_spec["path"], wait_until="domcontentloaded", timeout=10_000)
                page.wait_for_timeout(250)
                semantic = _semantic_probe(page)
                records.append({
                    "viewport": {"width": width, "height": height},
                    "expectedMarker": page_spec["id"],
                    "httpStatus": response.status if response else None,
                    "pageErrors": page_errors,
                    "nonReadOnlyRequests": [method for method in requests if method not in {"GET", "HEAD", "OPTIONS"}],
                    "semantic": semantic,
                })
                page.close()
        finally:
            browser.close()
    return records


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("baseline", "verify"), default="verify")
    args = parser.parse_args()
    demo = ROOT / "examples" / "ui-inventory-demo"
    output = ROOT / "examples" / ("alpha11-baseline-inventory-semantics-evidence" if args.mode == "baseline" else "inventory-semantic-evidence")
    output.mkdir(parents=True, exist_ok=True)
    scope_digest, scope_files = _scope_digest()
    handler = functools.partial(SimpleHTTPRequestHandler, directory=str(demo))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    page_rows = []
    browser_reason = None
    try:
        decision = resolve_browser_executable("chromium")
        if not decision.get("available"):
            browser_reason = str(decision.get("reason") or "browser unavailable")
        else:
            base_url = f"http://127.0.0.1:{server.server_port}"
            for page_spec in PAGES:
                page_output = output / f"page-{page_spec['id']}"
                quick_report = run_quick_ui(
                    base_url + page_spec["path"],
                    output_dir=page_output,
                    viewports=VIEWPORTS,
                    timeout_ms=10_000,
                )
                records = _direct_page_records(base_url, page_spec, str(decision["executable"]))
                for record in records:
                    record["quickUiStatus"] = quick_report.get("status")
                page_rows.append({
                    "id": page_spec["id"],
                    "path": page_spec["path"],
                    "title": page_spec["title"],
                    "status": "PENDING",
                    "quickUiStatus": quick_report.get("status"),
                    "quickUiReportDigest": quick_report.get("reportDigest"),
                    "quickUiReportSha256": _sha256(page_output / "quick-ui-report.json"),
                    "records": records,
                })
    except Exception as error:
        browser_reason = f"{type(error).__name__}: {error}"
    finally:
        server.shutdown()
        server.server_close()

    require_clean = args.mode == "verify"
    if browser_reason:
        aggregate = {
            "schemaVersion": "1",
            "runId": f"wuq-{PREVIOUS_EXPERIMENTAL_VERSION if args.mode == 'baseline' else EXPERIMENTAL_VERSION}-semantic-{args.mode}-20260906",
            "version": "4.4.0-alpha.13-shadow" if args.mode == "baseline" else EXPERIMENTAL_VERSION,
            "status": "NOT_VERIFIED",
            "reportStatus": "NOT_VERIFIED",
            "mode": args.mode,
            "browser": {"status": "NOT_VERIFIED", "reason": browser_reason},
            "scopeDigest": scope_digest,
            "scopeFiles": scope_files,
            "pages": [],
            "claimBoundary": "Semantic acceptance could not execute in a usable browser; no semantic or task outcome claim is made.",
        }
    else:
        for row in page_rows:
            checks = _semantic_checks(
                row["records"],
                require_explicit_names=require_clean,
            )
            row["checks"] = checks
            row["findingCounts"] = _finding_counts(row["records"])
            row["status"] = "PASS" if all(checks.values()) else "FAIL"
            row.pop("records", None)
        passed = bool(page_rows) and all(row["status"] == "PASS" for row in page_rows)
        aggregate = {
            "schemaVersion": "1",
            "runId": f"wuq-{PREVIOUS_EXPERIMENTAL_VERSION if args.mode == 'baseline' else EXPERIMENTAL_VERSION}-semantic-{args.mode}-20260906",
            "version": "4.4.0-alpha.13-shadow" if args.mode == "baseline" else EXPERIMENTAL_VERSION,
            "status": "BASELINE" if args.mode == "baseline" else "PASS" if passed else "FAIL",
            "reportStatus": "NOT_VERIFIED",
            "mode": args.mode,
            "browser": {"status": "PASS", "executable": str(decision["executable"])},
            "scopeDigest": scope_digest,
            "scopeFiles": scope_files,
            "pages": page_rows,
            "findingCounts": {
                "UNLABELLED_FORM_CONTROL": 0,
                "UNNAMED_NAVIGATION_LANDMARK": 0,
                "SMALL_INTERACTIVE_TARGET": 0,
            } if args.mode == "verify" else {
                key: sum(row["findingCounts"][key] for row in page_rows)
                for key in (
                    "UNLABELLED_FORM_CONTROL",
                    "UNNAMED_NAVIGATION_LANDMARK",
                    "SMALL_INTERACTIVE_TARGET",
                )
            },
            "claimBoundary": "This acceptance measures semantic labels, navigation landmark names, target geometry, page identity, read-only requests, and enclosing quick UI boundaries for three local inventory-demo pages in three browser viewports. It does not prove task outcomes, external project success, or Commercial GA eligibility.",
        }
    aggregate["aggregateDigest"] = digest_json(aggregate)
    (output / "semantic-acceptance.json").write_text(
        json.dumps(aggregate, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": aggregate["status"],
        "mode": aggregate["mode"],
        "pageStatuses": {row["id"]: row["status"] for row in aggregate["pages"]},
        "findingCounts": aggregate.get("findingCounts"),
        "scopeDigest": aggregate["scopeDigest"],
        "aggregateDigest": aggregate["aggregateDigest"],
        "claimBoundary": aggregate["claimBoundary"],
    }, ensure_ascii=False, indent=2))
    return 0 if aggregate["status"] in {"BASELINE", "PASS"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
