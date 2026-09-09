from __future__ import annotations

import json
from pathlib import Path

from _ui_inventory_acceptance import run_ui_inventory_acceptance


ROOT = Path(__file__).resolve().parents[1]


def test_inventory_demo_save_button_uses_one_shared_visual_contract() -> None:
    fixture = (ROOT / "examples/ui-inventory-demo/alpha11-inventory-fixture.css").read_text(encoding="utf-8")
    assert "background: var(--primary)" in fixture
    assert "border-color: var(--primary)" in fixture
    assert "border-radius: var(--control-radius)" in fixture
    assert fixture.count("button.save") == 3

    run_ui_inventory_acceptance()

    report = json.loads((ROOT / "examples/ui-inventory-evidence/ui-inventory.json").read_text(encoding="utf-8"))
    inventory = report["inventory"]
    assert inventory["components"]["button"]["styleCount"] == 1
    assert inventory["colors"]["potentialDuplicates"] == []
    assert not any(item.get("type") == "BUTTON_PURPOSE_DRIFT" for item in inventory["driftCandidates"])
    assert report["tokenComparison"]["existingDesignSystemMetrics"]["consistencyScore"] > 58
