"""Neutral design intermediate representation used by Figma, screenshots, visual editing, and code generation.

The IR deliberately stores design intent rather than framework-specific source code.
It is safe to serialise, diff, edit, and hand to a host model.  It does not carry
write authority and it never stores access tokens.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from typing import Any, Iterable, Mapping

_ALLOWED_TYPES = {
    "document", "page", "frame", "section", "stack", "grid", "card", "text",
    "image", "icon", "button", "form", "input", "textarea", "select", "checkbox",
    "radio", "switch", "tabs", "table", "list", "list-item", "badge", "avatar",
    "divider", "navigation", "dialog", "drawer", "popover", "tooltip", "chart", "unknown",
}

_PRODUCT_LAYERS = ("Product", "Route", "Journey", "Region", "Component", "Interaction State")
_EVIDENCE_CLASSES = {"observed", "inferred", "declared", "unknown"}
_EVIDENCE_CHANNELS = ("source", "dom", "visual", "runtime")


def _clean_bounds(value: Mapping[str, Any] | None) -> dict[str, float] | None:
    if not value:
        return None
    out: dict[str, float] = {}
    for key in ("x", "y", "width", "height"):
        raw = value.get(key)
        if isinstance(raw, (int, float)):
            out[key] = round(float(raw), 3)
    return out if {"width", "height"}.issubset(out) else None


def _clean_style(style: Mapping[str, Any] | None) -> dict[str, Any]:
    if not style:
        return {}
    allowed = {
        "display", "layout", "direction", "gap", "padding", "margin", "width", "height",
        "minWidth", "maxWidth", "minHeight", "maxHeight", "background", "color", "border",
        "borderRadius", "shadow", "opacity", "fontFamily", "fontSize", "fontWeight",
        "lineHeight", "letterSpacing", "textAlign", "overflow", "position", "zIndex",
        "align", "justify", "wrap", "objectFit", "aspectRatio", "tokenRefs", "variants",
    }
    result: dict[str, Any] = {}
    for key, value in style.items():
        if key in allowed and value is not None:
            result[key] = deepcopy(value)
    return result


def make_node(
    node_id: str,
    node_type: str,
    *,
    name: str | None = None,
    bounds: Mapping[str, Any] | None = None,
    style: Mapping[str, Any] | None = None,
    content: str | None = None,
    semantics: Mapping[str, Any] | None = None,
    bindings: Mapping[str, Any] | None = None,
    children: Iterable[Mapping[str, Any]] | None = None,
    source: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a normalised IR node with deterministic field ordering."""
    kind = node_type if node_type in _ALLOWED_TYPES else "unknown"
    value: dict[str, Any] = {
        "id": str(node_id),
        "type": kind,
        "name": str(name or node_id),
        "style": _clean_style(style),
        "semantics": dict(semantics or {}),
        "bindings": dict(bindings or {}),
        "children": [normalise_node(item) for item in (children or [])],
    }
    clean_bounds = _clean_bounds(bounds)
    if clean_bounds:
        value["bounds"] = clean_bounds
    if content is not None:
        value["content"] = str(content)
    if source:
        value["source"] = dict(source)
    return value


def normalise_node(node: Mapping[str, Any]) -> dict[str, Any]:
    return make_node(
        str(node.get("id") or "node"),
        str(node.get("type") or "unknown"),
        name=str(node.get("name") or node.get("id") or "node"),
        bounds=node.get("bounds") if isinstance(node.get("bounds"), Mapping) else None,
        style=node.get("style") if isinstance(node.get("style"), Mapping) else None,
        content=node.get("content") if node.get("content") is not None else None,
        semantics=node.get("semantics") if isinstance(node.get("semantics"), Mapping) else None,
        bindings=node.get("bindings") if isinstance(node.get("bindings"), Mapping) else None,
        children=node.get("children") if isinstance(node.get("children"), list) else None,
        source=node.get("source") if isinstance(node.get("source"), Mapping) else None,
    )


def make_product_node(
    node_id: str,
    layer: str,
    *,
    name: str,
    evidence_class: str,
    observed: Iterable[str] = (),
    inferred: Iterable[str] = (),
    declared: Iterable[str] = (),
    unknown: Iterable[str] = (),
    evidence_channels: Mapping[str, Iterable[str]] | None = None,
    source_paths: Iterable[str] = (),
    source_owner: str = "project",
    confidence: float = 0.5,
    risk_level: str = "unknown",
    risk_reasons: Iterable[str] = (),
    responsive_status: str = "unknown",
    responsive_rules: Iterable[str] = (),
    design_system_status: str = "unknown",
    design_system_origin: str = "unknown",
    semantics: Mapping[str, Any] | None = None,
    children: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Create one portable product-model node without promoting inference to fact."""
    resolved_layer = layer if layer in _PRODUCT_LAYERS else "Component"
    resolved_class = evidence_class if evidence_class in _EVIDENCE_CLASSES else "unknown"
    channels = evidence_channels if isinstance(evidence_channels, Mapping) else {}
    score = max(0.0, min(float(confidence), 1.0))
    if score >= 0.8:
        confidence_level = "high"
    elif score >= 0.5:
        confidence_level = "medium"
    else:
        confidence_level = "low"
    return {
        "id": str(node_id),
        "layer": resolved_layer,
        "name": str(name),
        "evidenceClass": resolved_class,
        "evidence": {
            "observed": [str(item) for item in observed],
            "inferred": [str(item) for item in inferred],
            "declared": [str(item) for item in declared],
            "unknown": [str(item) for item in unknown],
            "channels": {
                channel: [str(item) for item in channels.get(channel, [])]
                for channel in _EVIDENCE_CHANNELS
            },
        },
        "sourceOwnership": {
            "owner": str(source_owner),
            "authority": "read-only-reference",
            "paths": sorted({str(item).replace("\\", "/") for item in source_paths if str(item)}),
        },
        "confidence": {"score": round(score, 3), "level": confidence_level},
        "risk": {"level": risk_level if risk_level in {"low", "medium", "high", "unknown"} else "unknown", "reasons": [str(item) for item in risk_reasons]},
        "responsiveBehavior": {
            "status": responsive_status if responsive_status in _EVIDENCE_CLASSES else "unknown",
            "rules": [str(item) for item in responsive_rules],
        },
        "designSystemOrigin": {
            "status": design_system_status if design_system_status in _EVIDENCE_CLASSES else "unknown",
            "value": str(design_system_origin),
        },
        "semantics": dict(semantics or {}),
        "children": [normalise_product_node(item) for item in children],
    }


def normalise_product_node(node: Mapping[str, Any]) -> dict[str, Any]:
    evidence = node.get("evidence") if isinstance(node.get("evidence"), Mapping) else {}
    confidence = node.get("confidence") if isinstance(node.get("confidence"), Mapping) else {}
    risk = node.get("risk") if isinstance(node.get("risk"), Mapping) else {}
    responsive = node.get("responsiveBehavior") if isinstance(node.get("responsiveBehavior"), Mapping) else {}
    origin = node.get("designSystemOrigin") if isinstance(node.get("designSystemOrigin"), Mapping) else {}
    ownership = node.get("sourceOwnership") if isinstance(node.get("sourceOwnership"), Mapping) else {}
    return make_product_node(
        str(node.get("id") or "product-node"),
        str(node.get("layer") or "Component"),
        name=str(node.get("name") or node.get("id") or "Product node"),
        evidence_class=str(node.get("evidenceClass") or "unknown"),
        observed=evidence.get("observed", []) if isinstance(evidence.get("observed"), list) else [],
        inferred=evidence.get("inferred", []) if isinstance(evidence.get("inferred"), list) else [],
        declared=evidence.get("declared", []) if isinstance(evidence.get("declared"), list) else [],
        unknown=evidence.get("unknown", []) if isinstance(evidence.get("unknown"), list) else [],
        evidence_channels=evidence.get("channels") if isinstance(evidence.get("channels"), Mapping) else None,
        source_paths=ownership.get("paths", []) if isinstance(ownership.get("paths"), list) else [],
        source_owner=str(ownership.get("owner") or "project"),
        confidence=float(confidence.get("score", 0.5)) if isinstance(confidence.get("score", 0.5), (int, float)) else 0.5,
        risk_level=str(risk.get("level") or "unknown"),
        risk_reasons=risk.get("reasons", []) if isinstance(risk.get("reasons"), list) else [],
        responsive_status=str(responsive.get("status") or "unknown"),
        responsive_rules=responsive.get("rules", []) if isinstance(responsive.get("rules"), list) else [],
        design_system_status=str(origin.get("status") or "unknown"),
        design_system_origin=str(origin.get("value") or "unknown"),
        semantics=node.get("semantics") if isinstance(node.get("semantics"), Mapping) else None,
        children=node.get("children", []) if isinstance(node.get("children"), list) else [],
    )


def _default_product_model(source_type: str, source_name: str, roots: list[dict[str, Any]]) -> dict[str, Any]:
    channel = "visual" if source_type in {"figma", "screenshot"} else "source"
    top_regions: list[dict[str, Any]] = []
    for index, root in enumerate(roots):
        component = make_product_node(
            f"pm-component-{index + 1}", "Component", name=str(root.get("name") or root.get("type") or "Interface"),
            evidence_class="observed", observed=[f"{source_type} input contains a {root.get('type', 'node')} root"],
            unknown=["Runtime behaviour and business meaning are not proven by this input."],
            evidence_channels={channel: [f"root:{root.get('id', index + 1)}"]}, source_owner="external-reference" if channel == "visual" else "project",
            confidence=0.75, responsive_status="unknown", design_system_status="unknown",
            children=[make_product_node(
                f"pm-state-{index + 1}", "Interaction State", name="Unverified runtime state", evidence_class="unknown",
                unknown=["No runtime state observation is available."], source_owner="external-reference" if channel == "visual" else "project",
                confidence=0.2, responsive_status="unknown",
            )],
        )
        top_regions.append(make_product_node(
            f"pm-region-{index + 1}", "Region", name=str(root.get("name") or "Interface region"),
            evidence_class="inferred", inferred=["A visual root is treated as a product region for planning."],
            evidence_channels={channel: [f"root:{root.get('id', index + 1)}"]}, source_owner="external-reference" if channel == "visual" else "project",
            confidence=0.6, responsive_status="unknown", children=[component],
        ))
    journey = make_product_node(
        "pm-journey-primary", "Journey", name="Primary journey", evidence_class="unknown",
        unknown=["No user journey was declared or observed."], confidence=0.2, responsive_status="unknown", children=top_regions,
    )
    route = make_product_node(
        "pm-route-primary", "Route", name="Primary route", evidence_class="unknown",
        unknown=["No route evidence was supplied."], confidence=0.2, responsive_status="unknown", children=[journey],
    )
    return make_product_node(
        "pm-product", "Product", name=source_name, evidence_class="declared" if source_type in {"figma", "manual", "experience-plan"} else "observed",
        declared=[f"Input declares product name {source_name}"] if source_type in {"figma", "manual", "experience-plan"} else [],
        observed=[f"Input source name is {source_name}"] if source_type not in {"figma", "manual", "experience-plan"} else [],
        evidence_channels={channel: [f"source-type:{source_type}"]}, source_owner="external-reference" if channel == "visual" else "project",
        confidence=0.65, responsive_status="unknown", children=[route],
    )


def build_document(
    *,
    source_type: str,
    source_name: str,
    roots: Iterable[Mapping[str, Any]],
    canvas: Mapping[str, Any] | None = None,
    metadata: Mapping[str, Any] | None = None,
    tokens: Mapping[str, Any] | None = None,
    assets: Iterable[Mapping[str, Any]] | None = None,
    product_model: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    normalised_roots = [normalise_node(item) for item in roots]
    document = {
        "schemaVersion": "2.2",
        "source": {"type": source_type, "name": source_name},
        "canvas": dict(canvas or {}),
        "metadata": dict(metadata or {}),
        "tokens": dict(tokens or {}),
        "assets": [dict(item) for item in (assets or [])],
        "roots": normalised_roots,
        "productModelVersion": "2.0",
        "productModel": normalise_product_node(product_model) if isinstance(product_model, Mapping) else _default_product_model(source_type, source_name, normalised_roots),
    }
    document["designDigest"] = design_ir_digest(document)
    return document


def walk_nodes(document_or_node: Mapping[str, Any]) -> Iterable[dict[str, Any]]:
    if "roots" in document_or_node:
        stack = list(reversed(document_or_node.get("roots", [])))
    else:
        stack = [document_or_node]
    while stack:
        current = stack.pop()
        if isinstance(current, Mapping):
            node = dict(current)
            yield node
            children = node.get("children")
            if isinstance(children, list):
                stack.extend(reversed(children))


def node_index(document: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(node.get("id")): node for node in walk_nodes(document) if node.get("id")}


def validate_design_ir(document: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if document.get("schemaVersion") != "2.2":
        errors.append("$.schemaVersion must equal 2.2")
    if not isinstance(document.get("source"), Mapping):
        errors.append("$.source must be an object")
    roots = document.get("roots")
    if not isinstance(roots, list) or not roots:
        errors.append("$.roots must contain at least one node")
    seen: set[str] = set()
    for node in walk_nodes(document):
        node_id = str(node.get("id") or "")
        if not node_id:
            errors.append("node id is required")
        elif node_id in seen:
            errors.append(f"duplicate node id: {node_id}")
        else:
            seen.add(node_id)
        if node.get("type") not in _ALLOWED_TYPES:
            errors.append(f"{node_id}: unsupported node type {node.get('type')!r}")
        if not isinstance(node.get("children", []), list):
            errors.append(f"{node_id}: children must be a list")
    if document.get("productModelVersion") != "2.0":
        errors.append("$.productModelVersion must equal 2.0")
    product_model = document.get("productModel")
    if not isinstance(product_model, Mapping):
        errors.append("$.productModel must be an object")
    else:
        product_seen: set[str] = set()

        def validate_product_node(node: Mapping[str, Any], expected_index: int) -> None:
            node_id = str(node.get("id") or "")
            if not node_id:
                errors.append("product model node id is required")
            elif node_id in product_seen:
                errors.append(f"duplicate product model node id: {node_id}")
            else:
                product_seen.add(node_id)
            expected_layer = _PRODUCT_LAYERS[min(expected_index, len(_PRODUCT_LAYERS) - 1)]
            if node.get("layer") != expected_layer:
                errors.append(f"{node_id}: expected product layer {expected_layer!r}")
            if node.get("evidenceClass") not in _EVIDENCE_CLASSES:
                errors.append(f"{node_id}: invalid evidenceClass")
            evidence = node.get("evidence")
            if not isinstance(evidence, Mapping):
                errors.append(f"{node_id}: evidence must be an object")
            else:
                for evidence_class in _EVIDENCE_CLASSES:
                    if not isinstance(evidence.get(evidence_class), list):
                        errors.append(f"{node_id}: evidence.{evidence_class} must be a list")
                channels = evidence.get("channels")
                if not isinstance(channels, Mapping) or any(not isinstance(channels.get(channel), list) for channel in _EVIDENCE_CHANNELS):
                    errors.append(f"{node_id}: all evidence channels must be lists")
            children = node.get("children")
            if not isinstance(children, list):
                errors.append(f"{node_id}: children must be a list")
                return
            if expected_index == len(_PRODUCT_LAYERS) - 1 and children:
                errors.append(f"{node_id}: Interaction State cannot have child product nodes")
            for child in children:
                if isinstance(child, Mapping):
                    validate_product_node(child, expected_index + 1)
                else:
                    errors.append(f"{node_id}: product child must be an object")

        validate_product_node(product_model, 0)
    return errors


def design_ir_digest(document: Mapping[str, Any]) -> str:
    payload = deepcopy(dict(document))
    payload.pop("designDigest", None)
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256(encoded).hexdigest()


def summarise_design_ir(document: Mapping[str, Any]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    depth_max = 0

    def visit(node: Mapping[str, Any], depth: int) -> None:
        nonlocal depth_max
        kind = str(node.get("type") or "unknown")
        counts[kind] = counts.get(kind, 0) + 1
        depth_max = max(depth_max, depth)
        for child in node.get("children", []) if isinstance(node.get("children"), list) else []:
            if isinstance(child, Mapping):
                visit(child, depth + 1)

    for root in document.get("roots", []) if isinstance(document.get("roots"), list) else []:
        if isinstance(root, Mapping):
            visit(root, 1)
    product_count = 0
    product_depth = 0

    def visit_product(node: Mapping[str, Any], depth: int) -> None:
        nonlocal product_count, product_depth
        product_count += 1
        product_depth = max(product_depth, depth)
        for child in node.get("children", []) if isinstance(node.get("children"), list) else []:
            if isinstance(child, Mapping):
                visit_product(child, depth + 1)

    if isinstance(document.get("productModel"), Mapping):
        visit_product(document["productModel"], 1)
    return {
        "nodeCount": sum(counts.values()),
        "typeCounts": dict(sorted(counts.items())),
        "maxDepth": depth_max,
        "assetCount": len(document.get("assets", [])) if isinstance(document.get("assets"), list) else 0,
        "tokenCount": len(document.get("tokens", {})) if isinstance(document.get("tokens"), Mapping) else 0,
        "digest": document.get("designDigest") or design_ir_digest(document),
        "productModelNodeCount": product_count,
        "productModelMaxDepth": product_depth,
    }
