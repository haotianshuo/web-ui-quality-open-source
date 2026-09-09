from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
_ENVIRONMENT_REASON_CODES = frozenset({
    "PLAYWRIGHT_UNAVAILABLE",
    "BROWSER_EXECUTABLE_UNAVAILABLE",
    "BROWSER_ADMINISTRATOR_BLOCKED",
})


def test_ui_inventory_acceptance_distinguishes_environment_from_product_failure() -> None:
    canonical = ROOT / "examples" / "ui-inventory-evidence" / "ui-inventory.json"
    before = canonical.read_bytes() if canonical.is_file() else None
    completed = subprocess.run(
        [sys.executable, "-B", "scripts/ui_inventory_acceptance.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    payload = json.loads(completed.stdout)
    status = payload.get("status")
    if status == "NOT_VERIFIED_ENVIRONMENT":
        assert completed.returncode == 2, payload
        assert payload.get("reasonCode") in _ENVIRONMENT_REASON_CODES, payload
        assert (canonical.read_bytes() if canonical.is_file() else None) == before
        return
    assert status == "PASS", payload
    assert completed.returncode == 0, completed.stderr or completed.stdout
