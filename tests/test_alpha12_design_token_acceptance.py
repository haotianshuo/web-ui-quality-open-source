from __future__ import annotations

import json
from pathlib import Path

from _ui_inventory_acceptance import run_ui_inventory_acceptance


ROOT = Path(__file__).resolve().parents[1]


def test_inventory_demo_design_tokens_and_focus_contract_are_measured() -> None:
    css = (ROOT / "examples/ui-inventory-demo/styles.css").read_text(encoding="utf-8")
    for token in ("--background", "--surface", "--text", "--border", "--primary", "--focus"):
        assert token in css
    assert "var(--primary)" in css
    assert "button:focus-visible" in css
    assert ".nav a:focus-visible" in css

    run_ui_inventory_acceptance()

    report = json.loads((ROOT / "examples/ui-inventory-evidence/ui-inventory.json").read_text(encoding="utf-8"))
    comparison = report["tokenComparison"]
    metrics = comparison["existingDesignSystemMetrics"]
    assert comparison["cssVariableCount"] >= 9
    assert metrics["tokenReuseRatio"] > 0
    assert metrics["colourTokenRatio"] > 0
    assert metrics["consistencyScore"] > 25
    assert comparison["uniqueColorCoveragePercent"] >= 87.5
    assert not any(item.get("type") == "TOKEN_BYPASS_CANDIDATE" for item in report["topIssues"])
