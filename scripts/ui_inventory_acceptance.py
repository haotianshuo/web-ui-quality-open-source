from __future__ import annotations
import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import tempfile
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime" / "python"))
from web_ui_quality.contracts import ContractViolation
from web_ui_quality.ui_inventory import run_ui_inventory


_ENVIRONMENT_REASON_CODES = frozenset({
    "PLAYWRIGHT_UNAVAILABLE",
    "BROWSER_EXECUTABLE_UNAVAILABLE",
})


def main() -> int:
    demo = ROOT / "examples" / "ui-inventory-demo"
    out = ROOT / "examples" / "ui-inventory-evidence"
    handler = functools.partial(SimpleHTTPRequestHandler, directory=str(demo))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    environment_failure = None
    try:
        # Stage Browser output outside the canonical evidence directory. An
        # unavailable Browser must not leave a partial report or overwrite the
        # last known evidence with an environment result.
        with tempfile.TemporaryDirectory(prefix="wuq-ui-inventory-") as staged:
            try:
                report = run_ui_inventory(
                    f"http://127.0.0.1:{server.server_port}/index.html",
                    output_dir=staged,
                    project_root=demo,
                    mode="full",
                    max_pages=10,
                )
            except ContractViolation as error:
                if error.code not in _ENVIRONMENT_REASON_CODES:
                    raise
                environment_failure = error
            else:
                admin_blocked = report["stats"]["pagesScanned"] == 0 and any(
                    "ERR_BLOCKED_BY_ADMINISTRATOR" in str(item.get("reason") or "") for item in report.get("pages", [])
                )
                checks = {
                    "pagesScanned": report["stats"]["pagesScanned"] >= 3,
                    "buttons": report["inventory"]["components"]["button"]["count"] >= 3,
                    "buttonStylesConsistent": report["inventory"]["components"]["button"]["styleCount"] == 1,
                    "driftCleared": not any(x.get("type") == "BUTTON_PURPOSE_DRIFT" for x in report["inventory"]["driftCandidates"]),
                    "nearColorsCleared": not bool(report["inventory"]["colors"]["potentialDuplicates"]),
                    "html": (Path(staged) / "ui-inventory.html").is_file(),
                    "screenshots": len(list((Path(staged) / "screenshots").glob("*.png"))) >= 3,
                }
                if admin_blocked:
                    environment_failure = {
                        "status": "NOT_VERIFIED_ENVIRONMENT",
                        "reasonCode": "BROWSER_ADMINISTRATOR_BLOCKED",
                        "reason": "Browser navigation is blocked by Host administrator policy; no bypass was attempted.",
                        "errors": [],
                        "checks": checks,
                        "reportStatus": report.get("status"),
                    }
                else:
                    passed = all(checks.values())
                    if passed:
                        out.mkdir(parents=True, exist_ok=True)
                        for name in ("ui-inventory.json", "ui-inventory.html"):
                            (out / name).write_bytes((Path(staged) / name).read_bytes())
                        screenshots = out / "screenshots"
                        screenshots.mkdir(parents=True, exist_ok=True)
                        for shot in (Path(staged) / "screenshots").glob("*.png"):
                            (screenshots / shot.name).write_bytes(shot.read_bytes())
                    status = "PASS" if passed else "FAIL"
                    print(json.dumps({"status": status, "reason": None, "checks": checks, "reportStatus": report.get("status")}, ensure_ascii=False, indent=2))
                    return 0 if passed else 1
    finally:
        server.shutdown()
        server.server_close()
    if environment_failure is not None:
        if isinstance(environment_failure, ContractViolation):
            payload = {
                "status": "NOT_VERIFIED_ENVIRONMENT",
                "reasonCode": environment_failure.code,
                "reason": "Required Browser capability is unavailable; no Browser result was produced.",
                "errors": list(environment_failure.errors),
                "checks": None,
                "reportStatus": "NOT_VERIFIED",
            }
        else:
            payload = environment_failure
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 2
    raise RuntimeError("UI inventory acceptance ended without a result")

if __name__ == "__main__":
    raise SystemExit(main())
