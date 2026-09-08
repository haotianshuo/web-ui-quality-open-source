"""Figma REST/JSON import into Web UI Quality Design IR.

The importer supports offline Figma JSON exports and explicit REST fetching.  It
never writes access tokens to reports or output files.  Network access is opt-in.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
from typing import Any, Iterable, Mapping
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

from .design_ir import build_document, make_node, summarise_design_ir, validate_design_ir

_FIGMA_URL = re.compile(r"/(?:file|design|proto)/([A-Za-z0-9_-]+)(?:/|$)")


def parse_figma_reference(value: str) -> dict[str, str | None]:
    """Parse a Figma file URL or raw file key without accepting arbitrary hosts."""
    text = value.strip()
    if "://" not in text:
        if not re.fullmatch(r"[A-Za-z0-9_-]{6,}", text):
            raise ValueError("invalid Figma file key")
        return {"fileKey": text, "nodeId": None}
    parsed = urlparse(text)
    if parsed.hostname not in {"figma.com", "www.figma.com"}:
        raise ValueError("Figma URL must use figma.com")
    match = _FIGMA_URL.search(parsed.path)
    if not match:
        raise ValueError("Figma file key not found in URL")
    node_id = None
    for part in parsed.query.split("&"):
        if part.startswith("node-id="):
            node_id = part.split("=", 1)[1].replace("-", ":")
    return {"fileKey": match.group(1), "nodeId": node_id}


def fetch_figma_json(
    reference: str,
    *,
    token: str | None = None,
    token_env: str = "FIGMA_ACCESS_TOKEN",
    node_ids: Iterable[str] | None = None,
    timeout: float = 30.0,
) -> dict[str, Any]:
    ref = parse_figma_reference(reference)
    secret = token or os.environ.get(token_env)
    if not secret:
        raise ValueError(f"Figma token is required via argument or {token_env}")
    requested = list(dict.fromkeys(str(item) for item in (node_ids or []) if item))
    if ref.get("nodeId") and not requested:
        requested = [str(ref["nodeId"])]
    file_key = quote(str(ref["fileKey"]), safe="")
    if requested:
        endpoint = f"https://api.figma.com/v1/files/{file_key}/nodes?ids={quote(','.join(requested), safe=',:')}"
    else:
        endpoint = f"https://api.figma.com/v1/files/{file_key}"
    request = Request(endpoint, headers={"X-Figma-Token": secret, "Accept": "application/json", "User-Agent": "web-ui-quality/2.2"})
    with urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed official host after validation
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Figma response must be an object")
    return payload


def _paint(paints: Any) -> str | None:
    if not isinstance(paints, list):
        return None
    for item in paints:
        if not isinstance(item, Mapping) or item.get("visible") is False:
            continue
        color = item.get("color")
        if isinstance(color, Mapping):
            r = round(float(color.get("r", 0)) * 255)
            g = round(float(color.get("g", 0)) * 255)
            b = round(float(color.get("b", 0)) * 255)
            a = float(item.get("opacity", color.get("a", 1)))
            return f"rgba({r}, {g}, {b}, {round(a, 3)})"
    return None


def _stroke(node: Mapping[str, Any]) -> str | None:
    color = _paint(node.get("strokes"))
    if not color:
        return None
    width = node.get("strokeWeight", 1)
    return f"{width}px solid {color}"


def _shadow(effects: Any) -> str | None:
    if not isinstance(effects, list):
        return None
    values: list[str] = []
    for effect in effects:
        if not isinstance(effect, Mapping) or effect.get("visible") is False or effect.get("type") not in {"DROP_SHADOW", "INNER_SHADOW"}:
            continue
        offset = effect.get("offset") or {}
        color = effect.get("color") or {}
        r = round(float(color.get("r", 0)) * 255); g = round(float(color.get("g", 0)) * 255); b = round(float(color.get("b", 0)) * 255)
        a = round(float(color.get("a", 0.25)), 3)
        inset = "inset " if effect.get("type") == "INNER_SHADOW" else ""
        values.append(f"{inset}{offset.get('x',0)}px {offset.get('y',0)}px {effect.get('radius',0)}px {effect.get('spread',0)}px rgba({r},{g},{b},{a})")
    return ", ".join(values) or None


def _node_type(node: Mapping[str, Any]) -> str:
    figma_type = str(node.get("type") or "").upper()
    name = str(node.get("name") or "").casefold()
    if figma_type == "TEXT": return "text"
    if figma_type in {"FRAME", "COMPONENT", "INSTANCE", "COMPONENT_SET"}:
        if any(term in name for term in ("button", "按钮")): return "button"
        if any(term in name for term in ("input", "field", "输入")): return "input"
        if any(term in name for term in ("card", "卡片")): return "card"
        if any(term in name for term in ("dialog", "modal", "弹窗")): return "dialog"
        if any(term in name for term in ("drawer", "抽屉")): return "drawer"
        if any(term in name for term in ("tab", "标签")): return "tabs"
        if any(term in name for term in ("table", "表格")): return "table"
        return "frame"
    if figma_type == "SECTION": return "section"
    if figma_type in {"RECTANGLE", "ELLIPSE", "VECTOR", "LINE", "STAR", "POLYGON", "BOOLEAN_OPERATION"}:
        fills = node.get("fills")
        if isinstance(fills, list) and any(isinstance(item, Mapping) and item.get("type") == "IMAGE" for item in fills):
            return "image"
        return "icon" if (node.get("absoluteBoundingBox") or {}).get("width", 999) <= 48 else "unknown"
    return "unknown"


def _style(node: Mapping[str, Any]) -> dict[str, Any]:
    style: dict[str, Any] = {}
    box = node.get("absoluteBoundingBox") or {}
    if box.get("width") is not None: style["width"] = f"{round(float(box['width']),2)}px"
    if box.get("height") is not None: style["height"] = f"{round(float(box['height']),2)}px"
    fill = _paint(node.get("fills"))
    if fill: style["background"] = fill
    stroke = _stroke(node)
    if stroke: style["border"] = stroke
    radius = node.get("cornerRadius")
    if radius is None and isinstance(node.get("rectangleCornerRadii"), list):
        radius = " ".join(f"{item}px" for item in node["rectangleCornerRadii"])
    if radius is not None: style["borderRadius"] = f"{radius}px" if isinstance(radius, (int, float)) else radius
    shadow = _shadow(node.get("effects"))
    if shadow: style["shadow"] = shadow
    if node.get("opacity") is not None: style["opacity"] = node.get("opacity")
    layout = node.get("layoutMode")
    if layout in {"HORIZONTAL", "VERTICAL"}:
        style.update({"display": "flex", "direction": "row" if layout == "HORIZONTAL" else "column"})
        if node.get("itemSpacing") is not None: style["gap"] = f"{node.get('itemSpacing')}px"
        paddings = [node.get("paddingTop", 0), node.get("paddingRight", 0), node.get("paddingBottom", 0), node.get("paddingLeft", 0)]
        if any(paddings): style["padding"] = " ".join(f"{value}px" for value in paddings)
        style["align"] = str(node.get("counterAxisAlignItems") or "").casefold()
        style["justify"] = str(node.get("primaryAxisAlignItems") or "").casefold()
    text_style = node.get("style")
    if isinstance(text_style, Mapping):
        mapping = {
            "fontFamily": "fontFamily", "fontSize": "fontSize", "fontWeight": "fontWeight",
            "lineHeightPx": "lineHeight", "letterSpacing": "letterSpacing", "textAlignHorizontal": "textAlign",
        }
        for source_key, target_key in mapping.items():
            value = text_style.get(source_key)
            if value is not None:
                style[target_key] = f"{value}px" if source_key in {"fontSize", "lineHeightPx", "letterSpacing"} and isinstance(value, (int, float)) else value
        text_color = _paint(node.get("fills"))
        if text_color: style["color"] = text_color
    return style


def _semantic(node: Mapping[str, Any], ir_type: str) -> dict[str, Any]:
    name = str(node.get("name") or "")
    semantic: dict[str, Any] = {"sourceType": node.get("type")}
    if ir_type in {"button", "input", "select", "checkbox", "radio", "switch"}:
        semantic["role"] = ir_type
        semantic["accessibleName"] = name
    if node.get("componentId"): semantic["componentId"] = node.get("componentId")
    if node.get("componentProperties"): semantic["variants"] = node.get("componentProperties")
    if node.get("constraints"): semantic["constraints"] = node.get("constraints")
    return semantic


def _convert_node(node: Mapping[str, Any]) -> dict[str, Any]:
    ir_type = _node_type(node)
    box = node.get("absoluteBoundingBox") if isinstance(node.get("absoluteBoundingBox"), Mapping) else None
    children = [_convert_node(child) for child in node.get("children", []) if isinstance(child, Mapping)]
    return make_node(
        str(node.get("id") or "figma-node"), ir_type,
        name=str(node.get("name") or node.get("id") or "Figma node"),
        bounds=box, style=_style(node), content=node.get("characters") if ir_type == "text" else None,
        semantics=_semantic(node, ir_type), children=children,
        source={"provider": "figma", "nodeId": node.get("id"), "nodeType": node.get("type")},
    )


def _root_nodes(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    if isinstance(payload.get("document"), Mapping):
        document = payload["document"]
        return [item for item in document.get("children", []) if isinstance(item, Mapping)] or [document]
    nodes = payload.get("nodes")
    if isinstance(nodes, Mapping):
        result: list[Mapping[str, Any]] = []
        for entry in nodes.values():
            if isinstance(entry, Mapping) and isinstance(entry.get("document"), Mapping):
                result.append(entry["document"])
        return result
    raise ValueError("unsupported Figma payload: expected document or nodes")


def convert_figma_payload(payload: Mapping[str, Any], *, source_name: str = "figma-file") -> dict[str, Any]:
    roots = [_convert_node(node) for node in _root_nodes(payload)]
    document = build_document(
        source_type="figma", source_name=source_name, roots=roots,
        metadata={
            "name": payload.get("name"), "version": payload.get("version"),
            "lastModified": payload.get("lastModified"), "editorType": payload.get("editorType"),
            "componentCount": len(payload.get("components", {})) if isinstance(payload.get("components"), Mapping) else 0,
            "styleCount": len(payload.get("styles", {})) if isinstance(payload.get("styles"), Mapping) else 0,
        },
    )
    errors = validate_design_ir(document)
    if errors:
        raise ValueError("invalid converted Design IR: " + "; ".join(errors[:5]))
    return document


def import_figma_json(input_path: str | Path, output_dir: str | Path) -> dict[str, Any]:
    source = Path(input_path).expanduser().resolve()
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("Figma JSON root must be an object")
    document = convert_figma_payload(payload, source_name=source.name)
    return _write_bundle(document, output_dir, {"mode": "offline-json", "source": source.name})


def fetch_and_import_figma(reference: str, output_dir: str | Path, *, token: str | None = None, token_env: str = "FIGMA_ACCESS_TOKEN", node_ids: Iterable[str] | None = None) -> dict[str, Any]:
    payload = fetch_figma_json(reference, token=token, token_env=token_env, node_ids=node_ids)
    ref = parse_figma_reference(reference)
    document = convert_figma_payload(payload, source_name=f"figma:{ref['fileKey']}")
    return _write_bundle(document, output_dir, {"mode": "figma-rest", "fileKey": ref["fileKey"], "nodeIds": list(node_ids or ([ref["nodeId"]] if ref.get("nodeId") else [])), "tokenPersisted": False})


def _write_bundle(document: Mapping[str, Any], output_dir: str | Path, import_meta: Mapping[str, Any]) -> dict[str, Any]:
    out = Path(output_dir).expanduser().resolve(); out.mkdir(parents=True, exist_ok=True)
    ir_path = out / "design-ir.json"
    ir_path.write_text(json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    report = {
        "schemaVersion": "2.2", "status": "PASS", "provider": "figma",
        "import": dict(import_meta), "summary": summarise_design_ir(document),
        "designIr": "design-ir.json",
        "limitations": [
            "Figma constraints and variants are preserved as metadata but do not automatically become production business logic.",
            "Fonts, remote images, variables and component libraries may require separate asset access.",
            "REST rate limits and plan entitlements are controlled by Figma.",
        ],
    }
    report_path = out / "import-report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return {**report, "report": "import-report.json"}
