from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
_ENVIRONMENT_REASON_CODES = frozenset({
    "PLAYWRIGHT_UNAVAILABLE",
    "BROWSER_EXECUTABLE_UNAVAILABLE",
    "BROWSER_ADMINISTRATOR_BLOCKED",
})


def run_ui_inventory_acceptance() -> dict:
    completed = subprocess.run(
        [sys.executable, "-B", "scripts/ui_inventory_acceptance.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    if not completed.stdout.strip():
        raise AssertionError(completed.stderr or "UI inventory acceptance emitted no JSON")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise AssertionError(completed.stdout) from error
    if completed.returncode == 2:
        assert payload.get("status") == "NOT_VERIFIED_ENVIRONMENT", payload
        assert payload.get("reasonCode") in _ENVIRONMENT_REASON_CODES, payload
        pytest.skip(f"Browser acceptance not verified: {payload['reasonCode']}")
    assert completed.returncode == 0, completed.stderr or completed.stdout
    assert payload.get("status") == "PASS", payload
    return payload
