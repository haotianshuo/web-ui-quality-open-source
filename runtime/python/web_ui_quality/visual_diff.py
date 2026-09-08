"""Perceptual screenshot comparison backed by the required Pillow runtime."""
from __future__ import annotations
from pathlib import Path
from typing import Any


def capability() -> dict[str, Any]:
    try:
        import PIL  # noqa
        return {"available": True, "engine": "Pillow"}
    except Exception:
        return {"available": False, "engine": None, "install": "reinstall web-ui-quality to restore its required Pillow dependency"}


def compare_images(before: str | Path, after: str | Path, *, diff_path: str | Path | None = None, threshold: int = 18) -> dict[str, Any]:
    try:
        from PIL import Image, ImageChops
    except ImportError as error:
        return {"status": "NOT_RUN", "reason": "Pillow unavailable", "error": type(error).__name__}
    try:
        a = Image.open(before).convert("RGBA"); b = Image.open(after).convert("RGBA")
    except Exception as error:
        return {"status": "FAIL", "reason": "image load failed", "error": type(error).__name__}
    if a.size != b.size:
        return {"status": "FAIL", "reason": "image dimensions differ", "beforeSize": list(a.size), "afterSize": list(b.size)}
    diff = ImageChops.difference(a, b).convert("RGB")
    pixels = list(diff.get_flattened_data() if hasattr(diff, "get_flattened_data") else diff.getdata())
    total = max(len(pixels), 1)
    changed = sum(1 for p in pixels if max(p) > threshold)
    mean_delta = sum(sum(p) / 3 for p in pixels) / total
    if diff_path:
        mask = diff.point(lambda value: 255 if value > threshold else 0)
        mask.save(diff_path)
    return {"status": "COMPUTED", "reviewStatus": "NOT_REVIEWED", "changedPixelRatio": round(changed / total, 6), "meanChannelDelta": round(mean_delta, 3), "threshold": threshold, "diffRef": Path(diff_path).name if diff_path else None}
