"""Detect whether repeated findings share one source-level root cause."""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Mapping, Sequence


def _root(item: Mapping[str, Any]) -> str | None:
    for key in ("rootSource", "sourcePath", "componentPath", "sourceFile"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.replace("\\", "/")
    location = item.get("location")
    if isinstance(location, Mapping):
        value = location.get("file") or location.get("path")
        if isinstance(value, str) and value.strip():
            return value.replace("\\", "/")
    return None


def analyze_repair_scope(findings: Sequence[Mapping[str, Any]], *, minimum_occurrences: int = 2) -> dict[str, Any]:
    groups: dict[str, list[str]] = defaultdict(list)
    unresolved: list[str] = []
    for index, item in enumerate(findings):
        fid = str(item.get("findingId") or item.get("id") or item.get("fingerprint") or f"finding-{index+1}")
        root = _root(item)
        if root:
            groups[root].append(fid)
        else:
            unresolved.append(fid)
    systemic = [
        {"rootSource": root, "findingIds": ids, "affectedCount": len(ids), "strategy": "ONE_PATCH_N_VERIFICATIONS"}
        for root, ids in sorted(groups.items()) if len(ids) >= minimum_occurrences
    ]
    if systemic:
        return {
            "repairScope": "SYSTEMIC_ROOT_CAUSE",
            "systemicCandidates": systemic,
            "unresolvedFindingIds": unresolved,
            "requiresScopeExpansionReview": True,
            "claimBoundary": "Shared source mapping is a scope-planning signal; impact must be verified on affected surfaces before integration.",
        }
    return {
        "repairScope": "LOCAL_REPAIR",
        "systemicCandidates": [],
        "unresolvedFindingIds": unresolved,
        "requiresScopeExpansionReview": False,
    }


__all__ = ["analyze_repair_scope"]
