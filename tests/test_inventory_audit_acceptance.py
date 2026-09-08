from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_bundled_inventory_acceptance_confirms_cross_page_visual_consistency() -> None:
    completed = subprocess.run(
        [sys.executable, "-B", "scripts/ui_inventory_acceptance.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    result = json.loads(completed.stdout)
    assert result["status"] == "PASS"
    assert result["reportStatus"] == "PASS"
    assert all(result["checks"].values())
    assert result["checks"]["buttonStylesConsistent"]
    assert result["checks"]["driftCleared"]
    assert result["checks"]["nearColorsCleared"]
