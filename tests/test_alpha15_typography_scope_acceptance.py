from __future__ import annotations

from web_ui_quality.ui_inventory import _issues, aggregate_inventory


def _typography_page(rows: list[dict]) -> dict:
    return {
        "path": "/typography",
        "url": "https://example.test/typography",
        "status": "scanned",
        "buttons": [], "inputs": [], "cards": [], "dialogs": [], "tables": [], "icons": [],
        "colors": [], "typography": rows, "radius": [], "spacing": [],
    }


def _type_rows(font_size: int, semantic_role: str, count: int) -> list[dict]:
    return [
        {
            "fontFamily": "Arial, sans-serif", "fontSize": font_size, "fontWeight": "400",
            "lineHeight": 20, "letterSpacing": 0, "tag": "p", "semanticRole": semantic_role,
        }
        for _ in range(count)
    ]


def test_alpha15_inventory_distinguishes_semantic_tiers_from_same_role_fragmentation() -> None:
    rows = (
        _type_rows(14, "control", 6)
        + _type_rows(14, "control-label", 3)
        + _type_rows(16, "body", 21)
        + _type_rows(24, "heading", 1)
    )
    report = aggregate_inventory([_typography_page(rows)], mode="full")
    typography = report["typography"]

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
    assert not any(item.get("type") == "TYPOGRAPHY_FRAGMENTATION" for item in _issues(report, None))
