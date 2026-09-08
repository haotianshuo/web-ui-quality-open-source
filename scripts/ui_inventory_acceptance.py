from __future__ import annotations
import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime" / "python"))
from web_ui_quality.ui_inventory import run_ui_inventory


def main() -> int:
    demo = ROOT / "examples" / "ui-inventory-demo"
    out = ROOT / "examples" / "ui-inventory-evidence"
    handler = functools.partial(SimpleHTTPRequestHandler, directory=str(demo))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        report = run_ui_inventory(f"http://127.0.0.1:{server.server_port}/index.html", output_dir=out, project_root=demo, mode="full", max_pages=10)
    finally:
        server.shutdown(); server.server_close()
    admin_blocked = report["stats"]["pagesScanned"] == 0 and any(
        "ERR_BLOCKED_BY_ADMINISTRATOR" in str(item.get("reason") or "") for item in report.get("pages", [])
    )
    checks = {
        "pagesScanned": report["stats"]["pagesScanned"] >= 3,
        "buttons": report["inventory"]["components"]["button"]["count"] >= 3,
        "buttonStylesConsistent": report["inventory"]["components"]["button"]["styleCount"] == 1,
        "driftCleared": not any(x.get("type") == "BUTTON_PURPOSE_DRIFT" for x in report["inventory"]["driftCandidates"]),
        "nearColorsCleared": not bool(report["inventory"]["colors"]["potentialDuplicates"]),
        "html": (out / "ui-inventory.html").is_file(),
        "screenshots": len(list((out / "screenshots").glob("*.png"))) >= 3,
    }
    if admin_blocked:
        status = "NOT_VERIFIED_ENVIRONMENT"
        reason = "Browser navigation is blocked by Host administrator policy; no bypass was attempted."
        code = 2
    else:
        status = "PASS" if all(checks.values()) else "FAIL"
        reason = None
        code = 0 if all(checks.values()) else 1
    print(json.dumps({"status": status, "reason": reason, "checks": checks, "reportStatus": report.get("status")}, ensure_ascii=False, indent=2))
    return code

if __name__ == "__main__":
    raise SystemExit(main())
