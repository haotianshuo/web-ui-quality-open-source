"""Frozen design context and two-pass critique for applicable design work."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Mapping

from .contracts import ContractViolation, digest_json


FIELDS = ("theme", "audience", "uniqueTask", "brandConstraints", "approvedAssets", "content", "viewports", "tokens", "protectedPages")


def _known_context_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip()) and value.strip() not in {"UNKNOWN", "NOT_VERIFIED"}
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def freeze_design_context(value: Mapping[str, Any]) -> dict[str, object]:
    context = {key: value.get(key, "UNKNOWN") for key in FIELDS}
    if any(item is None or item == "" for item in context.values()):
        raise ContractViolation("DESIGN_CONTEXT_INVALID", ["$: empty fields must be UNKNOWN or NOT_VERIFIED"])
    payload: dict[str, object] = {"context": context}
    payload["digest"] = digest_json(payload)
    return payload


def build_project_reference(
    *,
    source_files: Sequence[str],
    tokens: Sequence[str],
    roles: Sequence[str],
    entities: Sequence[str],
    operations: Sequence[str],
    states: Sequence[str],
    page_modes: Sequence[str],
    archetype: str,
    constraints: Sequence[str] = (),
    design_context: Mapping[str, Any] | None = None,
) -> dict[str, object]:
    """Turn observed project language into a bounded, honest reference summary.

    This is intentionally derived from the audited page and local source tree. It
    does not fetch external design systems or infer approval from a token name.
    """

    paths = sorted({str(path).replace("\\", "/") for path in source_files if str(path).strip()})
    token_values = sorted({str(token) for token in tokens if str(token).strip()})
    component_paths = [
        path for path in paths
        if any(part.casefold() in {"component", "components"} for part in path.split("/"))
    ]
    supplied = dict(design_context) if isinstance(design_context, Mapping) else {}
    observed_context: dict[str, Any] = {
        "theme": supplied.get("theme", "由当前页面 CSS/HTML 观察" if token_values else "NOT_VERIFIED"),
        "audience": supplied.get("audience", list(roles) or "NOT_VERIFIED"),
        "uniqueTask": supplied.get("uniqueTask", list(operations) or "NOT_VERIFIED"),
        "brandConstraints": supplied.get("brandConstraints", list(constraints) or "NOT_VERIFIED"),
        "approvedAssets": supplied.get("approvedAssets", "NOT_VERIFIED"),
        "content": supplied.get("content", list(entities) or "NOT_VERIFIED"),
        "viewports": supplied.get("viewports", "NOT_VERIFIED"),
        "tokens": supplied.get("tokens", token_values or "NOT_VERIFIED"),
        "protectedPages": supplied.get("protectedPages", paths or "NOT_VERIFIED"),
    }
    frozen = freeze_design_context(observed_context)
    supplied_complete = all(_known_context_value(supplied.get(field)) for field in FIELDS)
    reference_status = "VERIFIED" if supplied_complete else "PARTIAL" if any(
        (token_values, component_paths, roles, entities, operations, states)
    ) else "NOT_VERIFIED"
    limitations: list[str] = []
    if not supplied_complete:
        limitations.append("项目未提供完整的已批准设计上下文；当前摘要只消费页面、Token 和本地源文件观察。")
    if not component_paths:
        limitations.append("未检出可复用组件目录，组件成熟度保持 NOT_VERIFIED。")

    return {
        "status": reference_status,
        "sourceFiles": paths,
        "contextSources": [path for path in paths if path.casefold().endswith((".html", ".htm", ".css"))],
        "tokens": token_values,
        "components": component_paths,
        "pageModes": sorted({str(item) for item in page_modes}),
        "archetype": str(archetype),
        "designContext": frozen["context"],
        "designContextDigest": frozen["digest"],
        "limitations": limitations,
        "externalFallbackUsed": False,
        "externalFallbackStatus": "NOT_VERIFIED",
    }


def critique_design(context: Mapping[str, Any], candidate: Mapping[str, Any], *, task_kind: str = "new_ui") -> dict[str, object]:
    frozen = freeze_design_context(context)
    if task_kind not in {"new_ui", "significant_reshape", "design_system", "precision_fix", "ordinary_audit"}:
        raise ContractViolation("DESIGN_TASK_KIND_INVALID", ["$.taskKind: unknown"])
    if task_kind in {"precision_fix", "ordinary_audit"}:
        payload = {"applicability": "not_applicable", "firstPass": None, "secondPass": [], "result": "NOT_VERIFIED", "reason": "设计两遍批评不适用于微改或普通审核"}
        payload["digest"] = digest_json(payload)
        return payload
    first_pass = {
        area: dict(candidate.get(area, {})) if isinstance(candidate.get(area), Mapping) else {}
        for area in ("colorRoles", "fontRoles", "layoutConcept", "memoryPoint")
    }
    decisions: list[dict[str, str]] = []
    for area in ("colorRoles", "fontRoles", "layoutConcept", "memoryPoint"):
        raw = candidate.get(area)
        if not isinstance(raw, Mapping) or not str(raw.get("proposal", "")).strip() or not str(raw.get("basis", "")).strip():
            decisions.append({"area": area, "decision": "reject", "reason": "缺少候选或需求/资产依据"})
        else:
            decision = "keep" if bool(raw.get("preservesApprovedMaster", False)) else "modify"
            reason = str(raw["basis"]) if decision == "keep" else "必须先映射到现有 Token/批准设计再保留"
            decisions.append({"area": area, "decision": decision, "reason": reason})
    visual_status = "NOT_VERIFIED" if context.get("browserScreenshot") in {None, "", "NOT_VERIFIED"} else "verified"
    payload: dict[str, object] = {
        "applicability": "applicable", "contextDigest": frozen["digest"],
        "firstPass": first_pass, "secondPass": decisions,
        "designPlanStatus": "complete", "visualEvidenceStatus": visual_status,
        "result": "NOT_VERIFIED",
    }
    payload["digest"] = digest_json(payload)
    return payload
