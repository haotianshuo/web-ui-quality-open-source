"""Versioned business context for smart acceptance.

The legacy :func:`normalize` surface is retained for 3.x callers.  The v2
helpers add provenance, stable context identity, and explicit downstream
invalidation without treating model inference as user-confirmed fact.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from .contracts import digest_json

_CONTEXT_FIELDS = (
    "primaryRole", "primaryTask", "coreObject", "successState", "successMetric",
    "frequency", "environment", "devicePriority",
)
_LIST_FIELDS = ("keyTasks", "highRiskActions", "mustPreserve", "knownPainPoints")


def _text(value: Mapping[str, Any], key: str) -> str | None:
    raw = value.get(key)
    return str(raw).strip() if raw is not None and str(raw).strip() else None


def _items(value: Mapping[str, Any], key: str) -> list[str]:
    raw = value.get(key, [])
    if not isinstance(raw, list):
        return []
    result: list[str] = []
    for item in raw:
        text = str(item).strip()
        if text and text not in result:
            result.append(text)
    return result


def normalize(value: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return the legacy 3.x shape used by existing product modules."""
    value = value or {}
    return {
        "primaryRole": _text(value, "primaryRole"),
        "frequency": _text(value, "frequency"),
        "environment": _text(value, "environment"),
        "primaryTask": _text(value, "primaryTask"),
        "successMetric": _text(value, "successMetric"),
        "highRiskActions": _items(value, "highRiskActions"),
        "mustPreserve": _items(value, "mustPreserve"),
        "knownPainPoints": _items(value, "knownPainPoints"),
        "evidenceLevel": "provided" if value else "not_provided",
    }


def build_context_v2(
    value: Mapping[str, Any] | None,
    *,
    parent_version: str | None = None,
    reason: str = "initial",
    default_environment: str | None = None,
    inferred: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a stable, provenance-aware v2 Business Context.

    Values supplied in ``value`` are considered user/project supplied.  Values
    in ``inferred`` remain explicitly marked as AI inference and never become
    confirmed merely because the run continues.
    """
    supplied = dict(value or {})
    inferred_values = dict(inferred or {})
    facts: dict[str, Any] = {}
    sources: dict[str, str] = {}
    confirmed: list[str] = []
    inferred_fields: list[str] = []

    for key in _CONTEXT_FIELDS:
        actual = _text(supplied, key)
        source = "user_or_project"
        if actual is None:
            actual = _text(inferred_values, key)
            source = "ai_inferred"
        if actual is None and key == "environment" and default_environment:
            actual = default_environment
            source = "runtime_observed"
        facts[key] = actual
        if actual is not None:
            sources[key] = source
            (inferred_fields if source == "ai_inferred" else confirmed).append(key)

    for key in _LIST_FIELDS:
        actual_items = _items(supplied, key)
        source = "user_or_project"
        if not actual_items:
            actual_items = _items(inferred_values, key)
            source = "ai_inferred"
        facts[key] = actual_items
        if actual_items:
            sources[key] = source
            (inferred_fields if source == "ai_inferred" else confirmed).append(key)

    identity_payload = {
        "parentVersion": parent_version,
        "reason": reason,
        "facts": facts,
        "sources": sources,
    }
    context_version = f"ctx-{digest_json(identity_payload)[:16]}"
    return {
        "schemaVersion": "2",
        "contextVersion": context_version,
        "parentVersion": parent_version,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "createdReason": reason,
        "facts": facts,
        "sources": sources,
        "confirmedFields": sorted(set(confirmed)),
        "inferredFields": sorted(set(inferred_fields)),
        "status": "ACTIVE",
        "summary": context_summary(facts),
    }


def context_summary(facts: Mapping[str, Any]) -> str:
    role = facts.get("primaryRole")
    core = facts.get("coreObject")
    task = facts.get("primaryTask")
    if not role and not task:
        return "当前未找到足够证据确认主要用户角色和关键任务；本次只按页面可用性与主要操作可发现性检查，不让未确认假设影响结论。"
    parts: list[str] = []
    if role:
        parts.append(f"主要用户可能是「{role}」")
    if core:
        parts.append(f"核心对象可能是「{core}」")
    if task:
        parts.append(f"关键任务可能是「{task}」")
    return "；".join(parts) + "。以上未由用户或项目明确确认的内容仍按推断处理。"


def mark_stale(artifact: Mapping[str, Any], *, current_context_version: str) -> dict[str, Any]:
    """Return an auditable stale copy when an artifact uses an old context."""
    result = dict(artifact)
    artifact_version = result.get("contextVersion")
    if artifact_version and artifact_version != current_context_version:
        result["status"] = "STALE"
        result["staleReason"] = "BUSINESS_CONTEXT_VERSION_MISMATCH"
        result["currentContextVersion"] = current_context_version
    return result


__all__ = ["normalize", "build_context_v2", "context_summary", "mark_stale"]
