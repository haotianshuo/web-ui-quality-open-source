"""Optional adapters for established audit engines.

No provider is downloaded implicitly.  The host must install and pin the engine
or explicitly pass a local executable/script path.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .contracts import ContractViolation
from .secure_browser_context import chromium_launch_security_args


def capabilities() -> dict[str, Any]:
    lighthouse = shutil.which("lighthouse")
    return {
        "lighthouse": {
            "available": bool(lighthouse), "executable": lighthouse,
            "install": "npm install --global lighthouse@<pinned-version>",
            "implicitDownload": False,
        },
        "axe": {
            "available": False,
            "reason": "run through Playwright with caller-supplied local axe.min.js",
            "implicitDownload": False,
        },
    }


def run_lighthouse(
    url: str,
    *,
    output_dir: str | Path,
    categories: tuple[str, ...] = ("performance", "accessibility", "best-practices", "seo"),
    timeout_s: int = 120,
    executable: str | Path | None = None,
    allow_no_sandbox: bool = False,
    outer_isolation_attested: bool = False,
) -> dict[str, Any]:
    binary = str(executable) if executable else shutil.which("lighthouse")
    if not binary or not Path(binary).exists():
        return {"status": "NOT_RUN", "reason": "Pinned local Lighthouse CLI unavailable", "implicitDownload": False}
    out = Path(output_dir); out.mkdir(parents=True, exist_ok=True); report = out / "lighthouse.json"
    try:
        chrome_flags = chromium_launch_security_args(allow_no_sandbox=allow_no_sandbox, outer_isolation_attested=outer_isolation_attested)
    except ContractViolation as error:
        return {"status": "NOT_RUN", "reason": error.code, "implicitDownload": False, "browserSecurity": "BLOCKED"}
    command = [binary, url, "--output=json", f"--output-path={report}", "--quiet", f"--chrome-flags={' '.join(chrome_flags)}", f"--only-categories={','.join(categories)}"]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout_s, check=False)
        if completed.returncode != 0 or not report.exists():
            return {"status": "FAIL", "exitCode": completed.returncode, "stderr": completed.stderr[-1200:], "implicitDownload": False}
        raw = json.loads(report.read_text(encoding="utf-8")); cats = raw.get("categories", {})
        scores = {name: round(float(value.get("score") or 0) * 100) for name, value in cats.items()}
        status = "FAIL" if any(score < 50 for score in scores.values()) else "PASS_WITH_WARNINGS" if any(score < 80 for score in scores.values()) else "PASS"
        audits = raw.get("audits", {})
        opportunities = []
        for audit_id, audit in audits.items():
            score = audit.get("score")
            if isinstance(score, (int, float)) and score < 0.9 and audit.get("title"):
                opportunities.append({"id": audit_id, "title": str(audit.get("title")), "score": score, "displayValue": audit.get("displayValue")})
        return {"status": status, "reportRef": report.name, "scores": scores, "opportunities": opportunities[:30], "implicitDownload": False}
    except Exception as error:
        return {"status": "FAIL", "error": type(error).__name__, "message": str(error)[:500], "implicitDownload": False}


def _axe_status(violations: list[dict[str, Any]], incomplete: list[dict[str, Any]]) -> tuple[str, dict[str, int]]:
    counts = {"critical": 0, "serious": 0, "moderate": 0, "minor": 0, "unknown": 0}
    for item in violations:
        impact = str(item.get("impact") or "unknown")
        counts[impact if impact in counts else "unknown"] += 1
    if counts["critical"] or counts["serious"]:
        return "FAIL", counts
    if violations or incomplete:
        return "PASS_WITH_WARNINGS", counts
    return "PASS", counts


def run_axe(page: Any, axe_script: str | Path) -> dict[str, Any]:
    path = Path(axe_script)
    if not path.is_file():
        return {"status": "NOT_RUN", "reason": "local axe script not found"}
    page.add_script_tag(path=str(path))
    result = page.evaluate("async () => await axe.run(document, {resultTypes:['violations','incomplete','passes','inapplicable']})")
    violations = result.get("violations", [])
    incomplete = result.get("incomplete", [])
    status, impacts = _axe_status(violations, incomplete)
    return {
        "status": status, "violations": violations, "incomplete": incomplete,
        "impactCounts": impacts, "passesCount": len(result.get("passes", [])),
        "inapplicableCount": len(result.get("inapplicable", [])),
    }
