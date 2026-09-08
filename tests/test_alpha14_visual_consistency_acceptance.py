from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_inventory_demo_save_button_uses_one_shared_visual_contract() -> None:
    fixture = (ROOT / "examples/ui-inventory-demo/alpha11-inventory-fixture.css").read_text(encoding="utf-8")
    assert "background: var(--primary)" in fixture
    assert "border-color: var(--primary)" in fixture
    assert "border-radius: var(--control-radius)" in fixture
    assert fixture.count("button.save") == 3

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

    report = json.loads((ROOT / "examples/ui-inventory-evidence/ui-inventory.json").read_text(encoding="utf-8"))
    inventory = report["inventory"]
    assert inventory["components"]["button"]["styleCount"] == 1
    assert inventory["colors"]["potentialDuplicates"] == []
    assert not any(item.get("type") == "BUTTON_PURPOSE_DRIFT" for item in inventory["driftCandidates"])
    assert report["tokenComparison"]["existingDesignSystemMetrics"]["consistencyScore"] > 58
