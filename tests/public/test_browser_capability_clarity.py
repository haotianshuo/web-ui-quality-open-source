from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

from web_ui_quality.capability_registry import build_browser_capability_clarity


ROOT = Path(__file__).resolve().parents[2]


def _capability(*, driver: bool, executable: bool, available: bool) -> dict[str, object]:
    return {
        "moduleAvailable": driver,
        "browserExecutableAvailable": executable,
        "available": available,
    }


def test_capability_projection_separates_launch_from_verification() -> None:
    ready = build_browser_capability_clarity(_capability(driver=True, executable=True, available=True), {})
    assert ready["status"] == "AVAILABLE"
    assert ready["browserInstalled"] == "AVAILABLE"
    assert ready["driverAvailable"] == "AVAILABLE"
    assert ready["launchStatus"] == "AVAILABLE"
    assert ready["navigationAuthorized"] == "NOT_MEASURED"
    assert ready["targetReachable"] == "NOT_MEASURED"
    assert ready["evidenceCollected"] == "NOT_MEASURED"
    assert ready["verificationStatus"] == "NOT_MEASURED"
    assert "does not mean" in ready["claimBoundary"] or "only" in ready["claimBoundary"]

    partial = build_browser_capability_clarity(_capability(driver=False, executable=True, available=False), {})
    assert partial["status"] == "BLOCKED"
    assert partial["browserInstalled"] == "AVAILABLE"
    assert partial["driverAvailable"] == "MISSING"
    assert partial["verificationStatus"] == "NOT_MEASURED"

    missing = build_browser_capability_clarity(_capability(driver=False, executable=False, available=False), {})
    assert missing["status"] == "MISSING"
    assert missing["browserInstalled"] == "MISSING"
    assert missing["driverAvailable"] == "MISSING"


def test_blocked_navigation_never_becomes_browser_evidence() -> None:
    blocked = build_browser_capability_clarity(
        _capability(driver=True, executable=True, available=True),
        {},
        navigation_authorized="BLOCKED",
    )
    assert blocked["launchStatus"] == "AVAILABLE"
    assert blocked["navigationAuthorized"] == "BLOCKED"
    assert blocked["targetReachable"] == "NOT_MEASURED"
    assert blocked["evidenceCollected"] == "NOT_MEASURED"
    assert blocked["verificationStatus"] == "NOT_MEASURED"


def test_doctor_exposes_capability_layers_without_claiming_verification() -> None:
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(ROOT / "runtime" / "python")
    completed = subprocess.run(
        [sys.executable, "-B", "scripts/run_runtime.py", "doctor", "--compact"],
        cwd=ROOT,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr.decode("utf-8", errors="replace")
    payload = json.loads(completed.stdout.decode("utf-8"))
    clarity = payload["browserCapability"]
    assert payload["browserStatusMeaning"] == "LOCAL_LAUNCH_PREREQUISITES_ONLY"
    assert clarity["navigationAuthorized"] == "NOT_MEASURED"
    assert clarity["targetReachable"] == "NOT_MEASURED"
    assert clarity["evidenceCollected"] == "NOT_MEASURED"
    assert clarity["verificationStatus"] == "NOT_MEASURED"


def test_readme_browser_onboarding_names_driver_and_executable_paths() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert 'pip install -e ".[browser]"' in readme
    assert "PYTHON_PLAYWRIGHT_MODULE_MISSING" in readme
    assert "PYTHON_BROWSER_EXECUTABLE_MISSING" in readme
    assert "playwright install chromium" in readme
