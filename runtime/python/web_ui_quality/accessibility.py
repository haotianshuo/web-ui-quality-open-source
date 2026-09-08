"""axe-compatible four-state result model without bundling or running axe."""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from .contracts import ContractViolation, digest_json, redact_text


AXE_STATES = ("violations", "passes", "incomplete", "inapplicable")


def normalize_accessibility_result(value: Mapping[str, Any]) -> dict[str, object]:
    version = value.get("engineVersion")
    if not isinstance(version, str) or not version:
        raise ContractViolation("A11Y_ENGINE_VERSION_REQUIRED", ["$.engineVersion: required"])
    rule_set = value.get("ruleSet")
    coverage_scope = value.get("coverageScope")
    manual = value.get("manualReviewItems")
    if not isinstance(rule_set, str) or not rule_set or not isinstance(coverage_scope, list) or not coverage_scope or not isinstance(manual, list):
        raise ContractViolation("A11Y_COVERAGE_REQUIRED", ["$: ruleSet, non-empty coverageScope, and manualReviewItems required"])
    output: dict[str, list[dict[str, object]]] = {state: [] for state in AXE_STATES}
    for state in AXE_STATES:
        entries = value.get(state)
        if not isinstance(entries, Iterable) or isinstance(entries, (str, bytes, Mapping)):
            raise ContractViolation("A11Y_STATE_INVALID", [f"$.{state}: expected array"])
        for raw in entries:
            if not isinstance(raw, Mapping) or not isinstance(raw.get("ruleId"), str):
                raise ContractViolation("A11Y_STATE_INVALID", [f"$.{state}: ruleId required"])
            summary, redacted = redact_text(str(raw.get("failureSummary", "")))
            selector, selector_redacted = redact_text(str(raw.get("selector", "")))
            evidence_id = str(raw.get("evidenceId", ""))
            if state == "incomplete" and not evidence_id:
                raise ContractViolation("A11Y_INCOMPLETE_EVIDENCE_REQUIRED", ["$.incomplete.evidenceId: required"])
            output[state].append({
                "evidenceId": evidence_id,
                "ruleId": raw["ruleId"],
                "impact": str(raw.get("impact", "unknown")),
                "tags": sorted(set(str(item) for item in raw.get("tags", []))),
                "selector": selector[:160],
                "failureSummary": summary[:500],
                "redactionApplied": redacted or selector_redacted or bool(raw.get("redactionApplied")),
            })
        output[state].sort(key=lambda item: (str(item["ruleId"]), str(item["selector"])))
    incomplete_ids = {item["evidenceId"] for item in output["incomplete"]}
    normalized_manual = []
    for item in manual:
        if not isinstance(item, Mapping) or item.get("incompleteEvidenceId") not in incomplete_ids:
            raise ContractViolation("A11Y_MANUAL_REVIEW_INVALID", ["$.manualReviewItems: must reference incomplete evidence"])
        state = item.get("state", "pending")
        if state not in {"pending", "verified"}:
            raise ContractViolation("A11Y_MANUAL_REVIEW_INVALID", ["$.manualReviewItems.state: expected pending or verified"])
        normalized_manual.append({"incompleteEvidenceId": item["incompleteEvidenceId"], "state": state, "source": "manual"})
    unresolved = incomplete_ids - {item["incompleteEvidenceId"] for item in normalized_manual if item["state"] == "verified"}
    result = "FAIL" if output["violations"] else ("NOT_VERIFIED" if unresolved or not output["passes"] else "PASS")
    payload: dict[str, object] = {"engineVersion": version, "ruleSet": rule_set, "coverageScope": coverage_scope, **output, "manualReviewItems": normalized_manual, "result": result, "manualReviewRequired": bool(unresolved), "complianceClaim": False}
    payload["digest"] = digest_json(payload)
    return payload
