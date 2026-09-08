"""P0-A finding normalization and semantic identity.

Model prose is never accepted directly as a product Finding.  Candidates must
carry a supported issue type, evidence state, semantic target, expected and
observed outcomes, and a result label supported by the evidence.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping

from .contracts import ContractViolation, digest_json, redact_text

ISSUE_TYPES = {
    "NO_RESPONSE", "FALSE_SUCCESS", "RESULT_MISMATCH", "RESPONSIVE_BLOCK",
    "FEEDBACK_GAP", "RECOVERY_GAP", "ACCESSIBILITY_BLOCK",
    "COMPLETENESS_SUGGESTION", "RUNTIME_HEALTH", "VISUAL_FRICTION",
}
RESULT_LABELS = {"现在会出错", "用起来别扭", "建议考虑补充", "暂时无法确认"}
VERIFICATION_STATES = {"VERIFIED", "NOT_VERIFIED", "NOT_EXECUTED", "NOT_APPLICABLE"}
SEVERITIES = {"critical", "high", "medium", "low", "info"}
_VIEWPORT_CLASSES = {"mobile", "small-desktop", "desktop", "all", "unknown"}
_SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
_LABEL_ORDER = {"现在会出错": 0, "用起来别扭": 1, "暂时无法确认": 2, "建议考虑补充": 3}


def _required_text(raw: Mapping[str, Any], key: str) -> str:
    value = str(raw.get(key, "")).strip()
    if not value:
        raise ContractViolation("ACCEPTANCE_FINDING_INVALID", [f"$.{key}: non-empty string required"])
    return value


def _viewport_class(value: Any) -> str:
    text = str(value or "unknown").strip()
    return text if text in _VIEWPORT_CLASSES else "unknown"


def normalize_finding(raw: Mapping[str, Any], *, context_version: str) -> dict[str, Any]:
    issue_type = _required_text(raw, "issueType")
    if issue_type not in ISSUE_TYPES:
        raise ContractViolation("ACCEPTANCE_FINDING_INVALID", [f"$.issueType: unsupported {issue_type}"])
    result_label = _required_text(raw, "resultLabel")
    if result_label not in RESULT_LABELS:
        raise ContractViolation("ACCEPTANCE_FINDING_INVALID", ["$.resultLabel: unsupported label"])
    verification_state = str(raw.get("verificationState") or "NOT_VERIFIED")
    if verification_state not in VERIFICATION_STATES:
        raise ContractViolation("ACCEPTANCE_FINDING_INVALID", ["$.verificationState: unsupported state"])
    severity = str(raw.get("severity") or "medium")
    if severity not in SEVERITIES:
        raise ContractViolation("ACCEPTANCE_FINDING_INVALID", ["$.severity: unsupported severity"])
    if result_label == "现在会出错" and verification_state != "VERIFIED":
        raise ContractViolation(
            "ACCEPTANCE_FINDING_EVIDENCE_INSUFFICIENT",
            ["$: '现在会出错' requires VERIFIED evidence"],
        )

    target_identity = _required_text(raw, "targetIdentity")
    route_template = str(raw.get("routeTemplate") or "/").strip() or "/"
    semantic_target = _required_text(raw, "semanticTarget")
    state = str(raw.get("state") or "default").strip() or "default"
    viewport_class = _viewport_class(raw.get("viewportClass"))
    expected_key = _required_text(raw, "expectedOutcomeKey")
    observed_key = _required_text(raw, "observedOutcomeKey")
    rule_id = _required_text(raw, "ruleId")
    rule_version = str(raw.get("ruleVersion") or "1").strip()

    summary, redacted_summary = redact_text(_required_text(raw, "summary"))
    impact, redacted_impact = redact_text(_required_text(raw, "impact"))
    recommendation, redacted_recommendation = redact_text(_required_text(raw, "recommendation"))
    evidence_refs = [str(item).strip() for item in raw.get("evidenceRefs", []) if str(item).strip()]
    evidence_kinds = sorted({str(item).strip() for item in raw.get("evidenceKinds", []) if str(item).strip()})
    if verification_state == "VERIFIED" and not evidence_refs:
        raise ContractViolation("ACCEPTANCE_FINDING_EVIDENCE_INSUFFICIENT", ["$.evidenceRefs: required for VERIFIED"])

    fingerprint_payload = {
        "targetIdentity": target_identity,
        "routeTemplate": route_template,
        "issueType": issue_type,
        "semanticTarget": semantic_target,
        "state": state,
        "viewportClass": viewport_class if issue_type == "RESPONSIVE_BLOCK" else "all",
        "expectedOutcomeKey": expected_key,
        "observedOutcomeKey": observed_key,
        "ruleId": rule_id,
    }
    fingerprint = f"af-{digest_json(fingerprint_payload)[:20]}"
    return {
        "schemaVersion": "2",
        "contextVersion": context_version,
        "fingerprint": fingerprint,
        "targetIdentity": target_identity,
        "routeTemplate": route_template,
        "journeyId": raw.get("journeyId"),
        "stepId": raw.get("stepId"),
        "issueType": issue_type,
        "semanticTarget": semantic_target,
        "state": state,
        "viewportClass": viewport_class,
        "expectedOutcome": {
            "key": expected_key,
            "summary": str(raw.get("expectedOutcomeSummary") or expected_key),
        },
        "observedOutcome": {
            "key": observed_key,
            "summary": str(raw.get("observedOutcomeSummary") or observed_key),
        },
        "evidenceKinds": evidence_kinds,
        "evidenceRefs": evidence_refs,
        "ruleId": rule_id,
        "ruleVersion": rule_version,
        "verificationState": verification_state,
        "resultLabel": result_label,
        "severity": severity,
        "goalRelevance": str(raw.get("goalRelevance") or "UNRELATED") if str(raw.get("goalRelevance") or "UNRELATED") in {"DIRECT", "SUPPORTING", "UNRELATED"} else "UNRELATED",
        "summary": summary,
        "impact": impact,
        "recommendation": recommendation,
        "redactionApplied": redacted_summary or redacted_impact or redacted_recommendation,
    }


def normalize_findings(candidates: Iterable[Mapping[str, Any]], *, context_version: str) -> dict[str, Any]:
    findings: dict[str, dict[str, Any]] = {}
    errors: list[dict[str, Any]] = []
    for index, raw in enumerate(candidates):
        try:
            finding = normalize_finding(raw, context_version=context_version)
        except ContractViolation as error:
            errors.append({"index": index, "error": error.as_dict()})
            continue
        current = findings.get(finding["fingerprint"])
        if current is None:
            findings[finding["fingerprint"]] = finding
            continue
        merged_refs = sorted(set(current["evidenceRefs"]) | set(finding["evidenceRefs"]))
        current["evidenceRefs"] = merged_refs
        current["evidenceKinds"] = sorted(set(current["evidenceKinds"]) | set(finding["evidenceKinds"]))
        if _SEVERITY_ORDER[finding["severity"]] < _SEVERITY_ORDER[current["severity"]]:
            current["severity"] = finding["severity"]
        if _LABEL_ORDER[finding["resultLabel"]] < _LABEL_ORDER[current["resultLabel"]]:
            current["resultLabel"] = finding["resultLabel"]
    ordered = sorted(
        findings.values(),
        key=lambda item: (
            _LABEL_ORDER[item["resultLabel"]],
            _SEVERITY_ORDER[item["severity"]],
            item["fingerprint"],
        ),
    )
    payload = {"findings": ordered, "normalizationErrors": errors}
    payload["digest"] = digest_json(payload)
    return payload


def top_findings(findings: Iterable[Mapping[str, Any]], *, limit: int = 3) -> list[dict[str, Any]]:
    ordered = sorted(
        list(findings),
        key=lambda item: (
            _LABEL_ORDER.get(str(item.get("resultLabel")), 9),
            _SEVERITY_ORDER.get(str(item.get("severity")), 9),
            str(item.get("fingerprint")),
        ),
    )
    return [dict(item) for item in ordered[: max(0, limit)]]


__all__ = [
    "ISSUE_TYPES", "RESULT_LABELS", "VERIFICATION_STATES",
    "normalize_finding", "normalize_findings", "top_findings",
]
