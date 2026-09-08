#!/usr/bin/env python3
"""Run the independent 4.0.0-rc.1 trust-integrity acceptance suites."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime" / "python"
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from web_ui_quality.capability_registry import build_capability_registry  # noqa: E402
from web_ui_quality.release_info import PACKAGE_VERSION, RELEASE_STAGE  # noqa: E402

SUITES = (
    ("product-experience", "product_experience_acceptance.py"),
    ("security-and-evidence", "security_and_evidence_regression.py"),
    ("browser-safety", "browser_safety_regression.py"),
    ("trust-integrity-attack", "trust_integrity_attack_regression.py"),
    ("public-compatibility", "public_acceptance.py"),
    ("v2.3-contract", "v23_acceptance.py"),
    ("real-project-integration", "real_project_integration.py"),
    ("distribution-verification", "verify_distribution.py"),
)


def _run(script: str) -> dict[str, Any]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(RUNTIME)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        [sys.executable, "-B", str(ROOT / "scripts" / script)],
        cwd=ROOT, env=env, text=True, encoding="utf-8", errors="replace",
        capture_output=True,
    )
    stdout = completed.stdout.strip()
    try:
        payload = json.loads(stdout) if stdout else {}
    except json.JSONDecodeError:
        payload = {"status": "FAIL", "rawStdout": stdout[-4000:]}
    return {
        "script": script,
        "exitCode": completed.returncode,
        "status": "PASS" if completed.returncode == 0 and payload.get("status") == "PASS" else "FAIL",
        "result": payload,
        "stderr": completed.stderr.strip()[-4000:] or None,
    }


def main() -> int:
    from web_ui_quality.release_info import configure_stdout

    configure_stdout()
    suite_results = [{"id": name, **_run(script)} for name, script in SUITES]
    failed = [item for item in suite_results if item["status"] != "PASS"]
    capabilities = build_capability_registry()
    browser_verified = bool(capabilities.get("pythonPlaywright", {}).get("available"))
    result = {
        "schemaVersion": "1.1",
        "packageVersion": PACKAGE_VERSION,
        "releaseStage": RELEASE_STAGE,
        "status": "FAIL" if failed else "PASS",
        "suiteCount": len(suite_results),
        "passed": len(suite_results) - len(failed),
        "failed": len(failed),
        "suites": suite_results,
        "browserCapabilities": capabilities,
        "browserEnvironmentAvailable": browser_verified,
        "claimBoundary": "Suite PASS proves shipped contracts and packaged workflows only. It does not prove production Browser access, authenticated mutation, real-user preference, legal readiness, or causal business outcomes.",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
