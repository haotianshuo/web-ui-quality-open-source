"""Normalize untrusted Provider evidence without changing frozen Schemas."""

from __future__ import annotations

import re
from typing import Any, Iterable, Mapping

from .contracts import ContractViolation, digest_json, redact_text
from .coverage import RuleRegistry
from .provider_contracts import ProviderEnvelope


PROVIDER_STATUSES = {"violation", "pass", "incomplete", "inapplicable", "error", "timeout", "unavailable"}
SAFE_PATH = re.compile(r"^[A-Za-z0-9._/-]+$")


def _location(value: Any) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise ContractViolation("PROVIDER_LOCATION_INVALID", ["$.location: expected object"])
    path = value.get("file")
    line = value.get("line")
    if not isinstance(path, str) or not SAFE_PATH.fullmatch(path) or path.startswith("/") or ".." in path.split("/"):
        raise ContractViolation("PROVIDER_LOCATION_INVALID", ["$.location.file: unsafe path"])
    if not isinstance(line, int) or line < 1:
        raise ContractViolation("PROVIDER_LOCATION_INVALID", ["$.location.line: positive integer required"])
    return {"file": path, "line": line}


def normalize_envelopes(
    envelopes: Iterable[Mapping[str, Any]],
    registry: RuleRegistry,
    *,
    registered_providers: set[str],
) -> dict[str, object]:
    issues: dict[str, dict[str, object]] = {}
    diagnostics: list[dict[str, object]] = []
    for raw in envelopes:
        contract_value = {
            "runId": raw.get("runId"), "providerId": raw.get("providerId"),
            "providerVersion": raw.get("providerVersion"), "target": raw.get("target"),
            "status": raw.get("status"), "ruleId": raw.get("ruleId"),
            "evidenceKind": raw.get("evidenceKind"), "evidenceSummary": raw.get("evidenceSummary"),
            "evidenceDigest": raw.get("evidenceHash"), "redactionApplied": raw.get("redactionApplied", False),
            "limitations": raw.get("limitations"), "attemptCount": raw.get("attemptCount"),
        }
        envelope = ProviderEnvelope.from_mapping(contract_value)
        status = envelope.status
        provider = envelope.provider_id
        rule_id = envelope.rule_id
        if status not in PROVIDER_STATUSES:
            raise ContractViolation("PROVIDER_STATUS_INVALID", ["$.status: unknown status"])
        if provider not in registered_providers:
            raise ContractViolation("PROVIDER_UNREGISTERED", ["$.providerId: not registered"])
        location = _location(raw.get("location"))
        summary, redacted = redact_text(envelope.evidence_summary)
        evidence_hash = envelope.evidence_digest
        if not isinstance(evidence_hash, str) or re.fullmatch(r"[0-9a-f]{64}", evidence_hash) is None:
            raise ContractViolation("PROVIDER_EVIDENCE_INVALID", ["$.evidenceHash: sha256 required"])
        if rule_id is None:
            diagnostics.append({
                "ruleId": None, "providerId": provider, "providerVersion": envelope.provider_version,
                "providerStatus": status, "mappedStatus": "NOT_VERIFIED",
                "evidenceKind": envelope.evidence_kind, "limitations": list(envelope.limitations),
                "attemptCount": envelope.attempt_count,
            })
            continue
        rule = registry.require(rule_id)
        if provider != rule.provider_id:
            raise ContractViolation("PROVIDER_RULE_MISMATCH", ["$.providerId: rule provider mismatch"])
        fingerprint = digest_json({"ruleId": rule_id, "location": location})
        source = {
            "providerId": provider, "providerVersion": envelope.provider_version,
            "runId": envelope.run_id, "evidenceHash": evidence_hash,
            "evidenceKind": envelope.evidence_kind, "limitations": list(envelope.limitations),
            "attemptCount": envelope.attempt_count,
        }
        if status == "violation":
            issue = issues.setdefault(fingerprint, {
                "fingerprint": fingerprint, "ruleId": rule_id, "location": location,
                "severity": rule.severity, "status": "violation", "evidenceSummary": summary,
                "redactionApplied": redacted or bool(raw.get("redactionApplied")), "sources": [],
            })
            if source not in issue["sources"]:
                issue["sources"].append(source)
        else:
            mapped = "NOT_VERIFIED" if status in {"incomplete", "error", "timeout", "unavailable"} else status
            diagnostics.append({
                "ruleId": rule_id, "providerId": provider, "providerVersion": envelope.provider_version,
                "providerStatus": status, "mappedStatus": mapped,
                "evidenceKind": envelope.evidence_kind, "limitations": list(envelope.limitations),
                "attemptCount": envelope.attempt_count,
            })
    normalized_issues = sorted(issues.values(), key=lambda item: str(item["fingerprint"]))
    for item in normalized_issues:
        item["sources"] = sorted(item["sources"], key=lambda value: (value["providerId"], value["runId"], value["evidenceHash"]))
    diagnostics.sort(key=lambda item: (str(item["ruleId"]), str(item["providerId"]), str(item["providerStatus"])))
    result = "FAIL" if normalized_issues else ("NOT_VERIFIED" if any(item["mappedStatus"] == "NOT_VERIFIED" for item in diagnostics) else "PASS")
    payload: dict[str, object] = {"issues": normalized_issues, "diagnostics": diagnostics, "result": result}
    payload["digest"] = digest_json(payload)
    return payload
