from __future__ import annotations

import json
from pathlib import Path

from _ui_inventory_acceptance import run_ui_inventory_acceptance


ROOT = Path(__file__).resolve().parents[1]


def test_inventory_demo_typography_tokens_and_control_inheritance_are_measured() -> None:
    css = (ROOT / "examples/ui-inventory-demo/styles.css").read_text(encoding="utf-8")
    for token in (
        "--font-family-sans",
        "--font-size-body",
        "--font-size-control",
        "--font-size-title",
        "--font-weight-regular",
        "--font-weight-semibold",
        "--font-weight-bold",
        "--line-height-control",
        "--line-height-title",
    ):
        assert token in css
    assert "font-family: var(--font-family-sans)" in css
    assert "font-size: var(--font-size-control)" in css
    assert "font-weight: var(--font-weight-semibold)" in css

    run_ui_inventory_acceptance()

    report = json.loads((ROOT / "examples/ui-inventory-evidence/ui-inventory.json").read_text(encoding="utf-8"))
    typography = report["inventory"]["typography"]
    comparison = report["tokenComparison"]
    metrics = comparison["existingDesignSystemMetrics"]
    assert len(typography["fontFamilies"]) == 1
    assert typography["fontFamilies"][0]["value"] == "Arial, sans-serif"
    assert comparison["cssVariableCount"] >= 18
    assert metrics["tokenReuseRatio"] > 31.8
    assert metrics["consistencyScore"] > 49
    assert typography["fragmentationCandidates"] == []
    assert not any(item.get("type") == "TYPOGRAPHY_FRAGMENTATION" for item in report["topIssues"])
    assert typography["crossRoleTierPairs"]
