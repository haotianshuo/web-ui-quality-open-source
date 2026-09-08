from __future__ import annotations

import json
from pathlib import Path

from web_ui_quality.intent_router import route_user_intent
from web_ui_quality.schema_validation import validate_instance
from web_ui_quality.ui_inventory import _stabilize_report_urls, aggregate_inventory, discover_source_routes
from web_ui_quality.release_info import PACKAGE_VERSION


def _button(*, color: str, height: float, radius: float) -> dict:
    return {
        "selector": ".save",
        "tag": "button",
        "role": None,
        "text": "保存",
        "disabled": False,
        "bounds": {"x": 0, "y": 0, "width": 90, "height": height},
        "style": {
            "height": height,
            "paddingTop": 8,
            "paddingRight": 16,
            "paddingBottom": 8,
            "paddingLeft": 16,
            "fontSize": 14,
            "fontWeight": "600",
            "color": "rgb(255, 255, 255)",
            "backgroundColor": color,
            "borderTopColor": color,
            "borderTopWidth": 1,
            "borderTopLeftRadius": radius,
            "boxShadow": "none",
            "opacity": 1,
        },
    }


def _page(path: str, button: dict, color: str, radius: float) -> dict:
    return {
        "path": path,
        "url": "https://example.test" + path,
        "status": "scanned",
        "buttons": [button],
        "inputs": [], "cards": [], "dialogs": [], "tables": [], "icons": [],
        "colors": [color, "rgb(255,255,255)"],
        "typography": [{"fontFamily": "Arial", "fontSize": 14, "fontWeight": "400", "lineHeight": 20, "letterSpacing": 0, "tag": "p"}],
        "radius": [radius], "spacing": [16],
    }


def test_inventory_request_routes_to_specialized_audit() -> None:
    routed = route_user_intent("请扫描全站 UI，统计所有按钮和风格")
    assert routed["intent"] == "specialized-audit"


def test_source_route_discovery_handles_next_dynamic_route(tmp_path: Path) -> None:
    page = tmp_path / "app" / "users" / "[id]" / "page.tsx"
    page.parent.mkdir(parents=True)
    page.write_text("export default function Page(){ return <button>保存</button> }", encoding="utf-8")
    rows = discover_source_routes(tmp_path)
    item = next(row for row in rows if row["path"] == "/users/[id]")
    assert item["template"] == "/users/:param"


def test_aggregate_finds_button_styles_near_colors_and_drift() -> None:
    pages = [
        _page("/a", _button(color="rgb(22, 119, 255)", height=40, radius=8), "rgb(22, 119, 255)", 8),
        _page("/b", _button(color="rgb(23, 120, 255)", height=38, radius=7), "rgb(23, 120, 255)", 7),
        _page("/c", _button(color="rgb(24, 121, 255)", height=36, radius=6), "rgb(24, 121, 255)", 6),
    ]
    report = aggregate_inventory(pages, mode="full")
    buttons = report["components"]["button"]
    assert buttons["count"] == 3
    assert buttons["styleCount"] == 3
    assert buttons["similarStyleClusters"]
    assert report["colors"]["potentialDuplicates"]
    assert any(item["type"] == "BUTTON_PURPOSE_DRIFT" and item["pageCount"] == 3 for item in report["driftCandidates"])


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


def test_typography_fragmentation_scopes_same_role_and_keeps_cross_role_tiers_visible() -> None:
    report = aggregate_inventory(
        [_typography_page(_type_rows(14, "control", 3) + _type_rows(16, "body", 3))],
        mode="full",
    )
    typography = report["typography"]
    assert typography["fragmentationCandidates"] == []
    assert typography["crossRoleTierPairs"] == [
        {
            "values": [14.0, 16.0],
            "roles": ["body", "control"],
            "roleCounts": [
                {"semanticRole": "body", "counts": [0, 3]},
                {"semanticRole": "control", "counts": [3, 0]},
            ],
        }
    ]


def test_typography_fragmentation_still_flags_adjacent_sizes_within_one_role() -> None:
    report = aggregate_inventory(
        [_typography_page(_type_rows(14, "body", 3) + _type_rows(16, "body", 3))],
        mode="full",
    )
    assert report["typography"]["fragmentationCandidates"] == [
        {"semanticRole": "body", "values": [14.0, 16.0], "counts": [3, 3]}
    ]


def test_persisted_inventory_urls_remove_only_ephemeral_loopback_ports() -> None:
    value = {
        "local": "http://127.0.0.1:43127/index.html",
        "localHttps": "https://localhost:5443/a?b=1#c",
        "ipv6": "http://[::1]:8080/a",
        "external": "https://example.test:8443/a",
        "text": "port 43127 is not a URL",
    }
    assert _stabilize_report_urls(value) == {
        "local": "http://127.0.0.1/index.html",
        "localHttps": "https://localhost/a?b=1#c",
        "ipv6": "http://[::1]/a",
        "external": "https://example.test:8443/a",
        "text": "port 43127 is not a URL",
    }


def test_ui_inventory_schema_is_bundled_and_validates_minimal_report() -> None:
    root = Path(__file__).resolve().parents[1]
    schema_path = root / "schemas" / "ui-inventory.schema.json"
    packaged = root / "runtime" / "python" / "web_ui_quality" / "schemas" / "ui-inventory.schema.json"
    assert schema_path.read_bytes() == packaged.read_bytes()
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    minimal = {
        "schemaVersion": "1", "producer": "web-ui-quality-ui-inventory", "packageVersion": PACKAGE_VERSION,
        "status": "PASS", "readOnly": True, "mode": "full",
        "stats": {"pagesDiscovered": 1, "pagesScanned": 1, "pagesFailed": 0, "pagesSkipped": 0},
        "pages": [{"path": "/", "status": "scanned"}],
        "inventory": {"components": {}, "colors": {}, "typography": {}, "radius": {}, "spacing": {}, "driftCandidates": [], "pageProfiles": []},
    }
    validate_instance(minimal, schema, base_dir=schema_path.parent)
