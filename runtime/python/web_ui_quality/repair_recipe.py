"""User-centred UX Repair Recipe generation."""
from __future__ import annotations

import uuid
from typing import Any, Iterable, Mapping


def build_repair_recipe(finding: Mapping[str, Any], *, confirmed: bool = False) -> dict[str, Any]:
    finding_id = str(finding.get("id") or finding.get("findingId") or finding.get("ruleId") or finding.get("fingerprint") or "unknown")
    repair = str(finding.get("repair") or finding.get("recommendation") or "需要结合真实页面证据确定修复。")
    modern = str(finding.get("modern") or finding.get("modernOption") or "仅在支持环境中采用更现代的实现。")
    fallback = str(finding.get("fallback") or finding.get("compatibilityFallback") or "保留基础、广泛兼容的实现路径。")
    verification = list(finding.get("verification") or [])
    if not verification:
        verification = [
            "390×844、768×1024、1440×900 下复测相关任务",
            "确认修复后没有页面级横向滚动、遮挡或主操作不可见",
            "在 200% 字体缩放和 Reduced Motion 条件下确认任务仍可理解",
        ]
    return {
        "repairId": f"repair-{uuid.uuid4().hex[:16]}",
        "findingIds": [finding_id],
        "userImpact": str(finding.get("impact") or finding.get("userImpact") or finding.get("summary") or ""),
        "recommendedRepair": repair,
        "modernOption": modern,
        "compatibilityFallback": fallback,
        "verification": verification,
        "confidence": str(finding.get("confidence") or "MEDIUM").upper(),
        "repairClass": "STRUCTURAL_REPAIR" if str(finding.get("category")) in {"layout", "interaction", "visual-system", "layering"} else "QUICK_WIN",
        "sourceScope": list(finding.get("sourceScope") or ([finding.get("source", {}).get("path")] if isinstance(finding.get("source"), dict) and finding.get("source", {}).get("path") else [])),
        "evidenceRefs": list(finding.get("evidenceRefs") or []),
        "evidenceClass": "FORMAL_FINDING" if confirmed else "REPAIR_HINT",
    }


def build_repair_recipes(findings: Iterable[Mapping[str, Any]], *, confirmed_ids: Iterable[str] = ()) -> list[dict[str, Any]]:
    confirmed = set(str(item) for item in confirmed_ids)
    return [build_repair_recipe(item, confirmed=str(item.get("id") or item.get("findingId") or item.get("ruleId") or item.get("fingerprint")) in confirmed) for item in findings]


__all__ = ["build_repair_recipe", "build_repair_recipes"]
