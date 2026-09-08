"""Deterministic patch-quality guardrails relative to the sealed project baseline."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Mapping

from .project_baseline import build_project_baseline


def evaluate_patch_quality(
    project_root: str | Path,
    baseline: Mapping[str, Any],
    *,
    source_scope: Iterable[str],
) -> dict[str, Any]:
    current = build_project_baseline(project_root)
    before = {str(row.get("path")): row for row in baseline.get("files", []) if isinstance(row, Mapping)}
    after = {str(row.get("path")): row for row in current.get("files", []) if isinstance(row, Mapping)}
    risks: list[dict[str, Any]] = []
    for rel in sorted({str(x).replace("\\", "/") for x in source_scope}):
        old = before.get(rel, {}).get("qualitySignals", {}) if isinstance(before.get(rel), Mapping) else {}
        new = after.get(rel, {}).get("qualitySignals", {}) if isinstance(after.get(rel), Mapping) else {}
        for signal, label in (("important", "NEW_IMPORTANT"), ("inlineStyle", "NEW_INLINE_STYLE"), ("magicPixel", "NEW_MAGIC_PIXEL")):
            delta = int(new.get(signal, 0) or 0) - int(old.get(signal, 0) or 0)
            if delta > 0:
                risks.append({"file": rel, "code": label, "delta": delta})
        if Path(rel).name in {"package.json", "package-lock.json", "pnpm-lock.yaml", "yarn.lock", "bun.lockb"}:
            if before.get(rel, {}).get("sha256") != after.get(rel, {}).get("sha256"):
                risks.append({"file": rel, "code": "DEPENDENCY_SURFACE_CHANGED", "delta": 1})
    status = "QUALITY_RISK" if risks else "QUALITY_OK"
    return {
        "schemaVersion": "1",
        "status": status,
        "risks": risks,
        "checkedFiles": sorted({str(x).replace("\\", "/") for x in source_scope}),
        "claimBoundary": "Deterministic debt signals do not prove general maintainability or architectural quality.",
    }


__all__ = ["evaluate_patch_quality"]
