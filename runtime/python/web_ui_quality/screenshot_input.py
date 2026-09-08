"""Screenshot analysis and import into Design IR.

The built-in analyser is deterministic and local.  It extracts canvas geometry,
colour palette, visual regions, probable text bands, and layout hierarchy.  A
host may provide a multimodal overlay to add semantic labels, but the overlay is
kept separate from trusted write authority.
"""
from __future__ import annotations

from collections import deque
import json
from pathlib import Path
from typing import Any, Mapping

from .design_ir import build_document, make_node, summarise_design_ir, validate_design_ir
from .screenshot_experience import build_screenshot_experience_model


def capability() -> dict[str, Any]:
    try:
        import PIL  # type: ignore
        return {"available": True, "provider": "Pillow", "version": getattr(PIL, "__version__", "unknown")}
    except Exception:
        return {"available": False, "provider": "Pillow", "reason": "Reinstall web-ui-quality to restore its required Pillow dependency"}


def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#%02x%02x%02x" % rgb


def _palette(image: Any, count: int = 10) -> list[dict[str, Any]]:
    sample = image.convert("RGB")
    sample.thumbnail((320, 320))
    quantized = sample.quantize(colors=count, method=2)
    colors = quantized.getcolors(maxcolors=count * 4) or []
    palette = quantized.getpalette() or []
    total = max(1, sample.width * sample.height)
    result = []
    for amount, index in sorted(colors, reverse=True):
        start = index * 3
        rgb = tuple(palette[start:start+3])
        if len(rgb) != 3:
            continue
        result.append({"color": _rgb_to_hex(rgb), "coverage": round(amount / total, 4), "rgb": list(rgb)})
    return result


def _edge_components(image: Any) -> list[dict[str, int]]:
    from PIL import ImageFilter, ImageOps  # type: ignore

    original_w, original_h = image.size
    scale = min(1.0, 640 / max(original_w, original_h))
    small = image.convert("L").resize((max(1, round(original_w * scale)), max(1, round(original_h * scale))))
    edge = ImageOps.autocontrast(small.filter(ImageFilter.FIND_EDGES))
    # Dynamic threshold using a high percentile approximation from histogram.
    hist = edge.histogram()
    total = sum(hist); target = total * 0.86; running = 0; threshold = 48
    for value, amount in enumerate(hist):
        running += amount
        if running >= target:
            threshold = max(36, value)
            break
    width, height = edge.size
    pixels = edge.load()
    active = bytearray(width * height)
    for y in range(height):
        for x in range(width):
            if pixels[x, y] >= threshold:
                active[y * width + x] = 1
    seen = bytearray(width * height)
    components: list[dict[str, int]] = []
    min_area = max(8, int(width * height * 0.00012))
    for y0 in range(height):
        for x0 in range(width):
            idx = y0 * width + x0
            if not active[idx] or seen[idx]:
                continue
            queue = deque([(x0, y0)]); seen[idx] = 1
            min_x = max_x = x0; min_y = max_y = y0; count = 0
            while queue:
                x, y = queue.popleft(); count += 1
                min_x = min(min_x, x); max_x = max(max_x, x); min_y = min(min_y, y); max_y = max(max_y, y)
                for nx, ny in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
                    if 0 <= nx < width and 0 <= ny < height:
                        nidx = ny * width + nx
                        if active[nidx] and not seen[nidx]:
                            seen[nidx] = 1; queue.append((nx, ny))
            box_area = (max_x-min_x+1) * (max_y-min_y+1)
            if count < min_area or box_area < min_area * 2:
                continue
            factor = 1 / scale
            components.append({
                "x": round(min_x * factor), "y": round(min_y * factor),
                "width": max(1, round((max_x-min_x+1) * factor)),
                "height": max(1, round((max_y-min_y+1) * factor)),
                "edgePixels": count,
            })
    # Merge overlapping and near-contained boxes, then keep meaningful regions.
    components.sort(key=lambda box: box["width"] * box["height"], reverse=True)
    merged: list[dict[str, int]] = []
    for box in components:
        if box["width"] < 12 or box["height"] < 8:
            continue
        if any(_contains(existing, box, tolerance=6) for existing in merged):
            continue
        merged.append(box)
        if len(merged) >= 80:
            break
    return sorted(merged, key=lambda box: (box["y"], box["x"]))


def _contains(outer: Mapping[str, int], inner: Mapping[str, int], tolerance: int = 0) -> bool:
    return (
        inner["x"] >= outer["x"] - tolerance and inner["y"] >= outer["y"] - tolerance
        and inner["x"] + inner["width"] <= outer["x"] + outer["width"] + tolerance
        and inner["y"] + inner["height"] <= outer["y"] + outer["height"] + tolerance
    )


def _classify_region(box: Mapping[str, int], canvas: tuple[int, int]) -> str:
    width, height = canvas
    w = box["width"]; h = box["height"]; x = box["x"]; y = box["y"]
    ratio = w / max(1, h)
    area_ratio = (w * h) / max(1, width * height)
    if y < height * 0.13 and w > width * 0.55 and h < height * 0.18:
        return "section"
    if x < width * 0.22 and h > height * 0.45 and w < width * 0.35:
        return "section"
    if ratio > 7 and h < 72:
        return "text"
    if 2.2 < ratio <= 7 and h <= 72:
        return "button"
    if area_ratio > 0.08:
        return "card"
    if 0.75 <= ratio <= 1.35 and w <= 96 and h <= 96:
        return "icon"
    if ratio > 1.4:
        return "frame"
    return "unknown"


def _sample_region_colour(image: Any, box: Mapping[str, int]) -> str:
    x1 = max(0, box["x"]); y1 = max(0, box["y"])
    x2 = min(image.width, x1 + box["width"]); y2 = min(image.height, y1 + box["height"])
    crop = image.convert("RGB").crop((x1, y1, x2, y2))
    if not crop.width or not crop.height:
        return "#ffffff"
    crop.thumbnail((32, 32))
    pixel_iter = crop.get_flattened_data() if hasattr(crop, "get_flattened_data") else crop.getdata()
    values = list(pixel_iter)
    if not values:
        return "#ffffff"
    values.sort(key=lambda rgb: sum(rgb))
    return _rgb_to_hex(values[len(values)//2])


def _overlay_index(overlay: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    if not overlay:
        return []
    items = overlay.get("elements")
    return [item for item in items if isinstance(item, Mapping)] if isinstance(items, list) else []


def _best_overlay(box: Mapping[str, int], overlay: list[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    best = None; best_iou = 0.0
    for item in overlay:
        bounds = item.get("bounds")
        if not isinstance(bounds, Mapping):
            continue
        try:
            ax1, ay1 = box["x"], box["y"]; ax2, ay2 = ax1 + box["width"], ay1 + box["height"]
            bx1, by1 = float(bounds["x"]), float(bounds["y"]); bx2, by2 = bx1 + float(bounds["width"]), by1 + float(bounds["height"])
        except (KeyError, TypeError, ValueError):
            continue
        ix = max(0.0, min(ax2, bx2) - max(ax1, bx1)); iy = max(0.0, min(ay2, by2) - max(ay1, by1))
        intersection = ix * iy
        union = box["width"] * box["height"] + (bx2-bx1)*(by2-by1) - intersection
        iou = intersection / max(1.0, union)
        if iou > best_iou:
            best_iou = iou; best = item
    return best if best_iou >= 0.18 else None


def analyse_screenshot(image_path: str | Path, *, multimodal_overlay: Mapping[str, Any] | None = None) -> dict[str, Any]:
    cap = capability()
    if not cap["available"]:
        return {"schemaVersion": "2.2", "status": "NOT_RUN", "capability": cap}
    from PIL import Image  # type: ignore

    source = Path(image_path).expanduser().resolve()
    with Image.open(source) as opened:
        image = opened.convert("RGB")
        width, height = image.size
        palette = _palette(image)
        boxes = _edge_components(image)
        overlay = _overlay_index(multimodal_overlay)
        children = []
        for index, box in enumerate(boxes):
            enriched = _best_overlay(box, overlay)
            node_type = str(enriched.get("type")) if enriched and enriched.get("type") else _classify_region(box, (width, height))
            content = str(enriched.get("text")) if enriched and enriched.get("text") is not None else None
            name = str(enriched.get("name")) if enriched and enriched.get("name") else f"Region {index+1}"
            semantics = {
                "confidence": round(float(enriched.get("confidence", 0.9) if enriched else 0.45), 3),
                "analysis": "multimodal-overlay" if enriched else "local-edge-segmentation",
            }
            children.append(make_node(
                f"screenshot-region-{index+1}", node_type, name=name, bounds=box,
                style={"background": _sample_region_colour(image, box)}, content=content,
                semantics=semantics, source={"provider": "screenshot", "path": source.name},
            ))
        root = make_node(
            "screenshot-canvas", "page", name=source.stem,
            bounds={"x": 0, "y": 0, "width": width, "height": height},
            style={"width": f"{width}px", "height": f"{height}px", "position": "relative", "background": palette[0]["color"] if palette else "#ffffff"},
            children=children, source={"provider": "screenshot", "path": source.name},
        )
        document = build_document(
            source_type="screenshot", source_name=source.name, roots=[root],
            canvas={"width": width, "height": height, "aspectRatio": round(width / max(1, height), 5)},
            metadata={
                "mode": image.mode, "palette": palette,
                "localRegionCount": len(boxes), "multimodalOverlayUsed": bool(multimodal_overlay),
                "analysisConfidence": "medium" if multimodal_overlay else "low-to-medium",
            },
            assets=[{"id": "source-screenshot", "type": "image", "path": source.name, "width": width, "height": height}],
        )
    errors = validate_design_ir(document)
    if errors:
        raise ValueError("invalid screenshot Design IR: " + "; ".join(errors[:5]))
    experience_model = build_screenshot_experience_model(document, overlay=multimodal_overlay)
    return {
        "schemaVersion": "2.2", "status": "PASS", "provider": "screenshot",
        "capability": cap, "designIr": document, "summary": summarise_design_ir(document),
        "experienceModel": experience_model,
        "limitations": [
            "Local screenshot analysis cannot reliably infer business meaning or hidden interactions.",
            "Text extraction is only available through an explicit multimodal overlay; OCR is not silently invoked.",
            "Visual regions are candidates for refinement rather than production component authority.",
        ],
    }


def import_screenshot(image_path: str | Path, output_dir: str | Path, *, multimodal_overlay: Mapping[str, Any] | None = None) -> dict[str, Any]:
    result = analyse_screenshot(image_path, multimodal_overlay=multimodal_overlay)
    out = Path(output_dir).expanduser().resolve(); out.mkdir(parents=True, exist_ok=True)
    if result.get("status") != "PASS":
        report_path = out / "import-report.json"
        report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        return {**result, "report": "import-report.json"}
    document = result.pop("designIr")
    ir_path = out / "design-ir.json"
    ir_path.write_text(json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    report = {**result, "designIr": "design-ir.json"}
    report_path = out / "import-report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return {**report, "report": "import-report.json"}
