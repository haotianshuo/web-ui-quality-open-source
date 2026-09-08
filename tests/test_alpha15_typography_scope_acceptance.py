from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_alpha15_inventory_distinguishes_semantic_tiers_from_same_role_fragmentation() -> None:
    report = json.loads((ROOT / "examples/ui-inventory-evidence/ui-inventory.json").read_text(encoding="utf-8"))
    typography = report["inventory"]["typography"]

    assert typography["fragmentationCandidates"] == []
    assert typography["crossRoleTierPairs"] == [
        {
            "values": [14.0, 16.0],
            "roles": ["body", "control", "control-label"],
            "roleCounts": [
                {"semanticRole": "body", "counts": [0, 21]},
                {"semanticRole": "control", "counts": [6, 0]},
                {"semanticRole": "control-label", "counts": [3, 0]},
            ],
        }
    ]
    assert set(typography["semanticRoleCounts"]) == {"body", "control", "control-label", "heading"}
    assert not any(item.get("type") == "TYPOGRAPHY_FRAGMENTATION" for item in report["topIssues"])
