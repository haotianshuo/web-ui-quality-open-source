"""Strict internal contracts for untrusted Provider evidence.

These values are deliberately not persisted as a ninth public schema.  Adapters
may construct them, but they cannot authorize execution or determine severity.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any, Mapping

from .contracts import ContractViolation, digest_json, redact_text


PROVIDER_STATUSES = frozenset(
    {"violation", "pass", "incomplete", "inapplicable", "error", "timeout", "unavailable"}
)
EVIDENCE_KINDS = frozenset({"static", "browser", "accessibility", "candidate_patch"})
_ID_RE = re.compile(r"[a-z0-9]+(?:[._-][a-z0-9]+)*")
_RULE_RE = re.compile(r"[A-Z0-9]+(?:-[A-Z0-9]+)+")
_SHA_RE = re.compile(r"[0-9a-f]{64}")


def _identifier(value: Any, path: str) -> str:
    if not isinstance(value, str) or _ID_RE.fullmatch(value) is None:
        raise ContractViolation("PROVIDER_CONTRACT_INVALID", [f"{path}: invalid identifier"])
    return value


def normalize_target(value: Any, path: str = "$.target") -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractViolation("PROVIDER_CONTRACT_INVALID", [f"{path}: expected relative target"])
    normalized = value.replace("\\", "/")
    pure = PurePosixPath(normalized)
    if pure.is_absolute() or ".." in pure.parts or re.match(r"^[A-Za-z]:", normalized):
        raise ContractViolation("PROVIDER_SCOPE_ESCAPE", [f"{path}: unsafe relative target"])
    return pure.as_posix()


@dataclass(frozen=True)
class ProviderEnvelope:
    run_id: str
    provider_id: str
    provider_version: str
    target: str
    status: str
    rule_id: str | None
    evidence_kind: str
    evidence_summary: str
    evidence_digest: str
    redaction_applied: bool
    limitations: tuple[str, ...] = ()
    attempt_count: int = 1

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ProviderEnvelope":
        required = {
            "runId", "providerId", "providerVersion", "target", "status", "ruleId",
            "evidenceKind", "evidenceSummary", "evidenceDigest", "redactionApplied",
            "limitations", "attemptCount",
        }
        if not isinstance(value, Mapping) or set(value) != required:
            raise ContractViolation("PROVIDER_CONTRACT_INVALID", ["$: unexpected or missing fields"])
        run_id = _identifier(value["runId"], "$.runId")
        provider_id = _identifier(value["providerId"], "$.providerId")
        version = value["providerVersion"]
        if not isinstance(version, str) or not version.strip() or len(version) > 64:
            raise ContractViolation("PROVIDER_CONTRACT_INVALID", ["$.providerVersion: invalid"])
        status = value["status"]
        if status not in PROVIDER_STATUSES:
            raise ContractViolation("PROVIDER_CONTRACT_INVALID", ["$.status: unknown Provider status"])
        rule_id = value["ruleId"]
        if rule_id is not None and (not isinstance(rule_id, str) or _RULE_RE.fullmatch(rule_id) is None):
            raise ContractViolation("PROVIDER_CONTRACT_INVALID", ["$.ruleId: invalid rule identifier"])
        if status in {"violation", "pass"} and rule_id is None:
            raise ContractViolation("PROVIDER_CONTRACT_INVALID", ["$.ruleId: required for adjudicable status"])
        kind = value["evidenceKind"]
        if kind not in EVIDENCE_KINDS:
            raise ContractViolation("PROVIDER_CONTRACT_INVALID", ["$.evidenceKind: unknown evidence kind"])
        summary = value["evidenceSummary"]
        if not isinstance(summary, str) or not summary.strip() or len(summary) > 512:
            raise ContractViolation("PROVIDER_CONTRACT_INVALID", ["$.evidenceSummary: invalid"])
        safe_summary, changed = redact_text(summary)
        if changed:
            raise ContractViolation("PROVIDER_EVIDENCE_NOT_REDACTED", ["$.evidenceSummary: sensitive value"])
        evidence_digest = value["evidenceDigest"]
        if not isinstance(evidence_digest, str) or _SHA_RE.fullmatch(evidence_digest) is None:
            raise ContractViolation("PROVIDER_CONTRACT_INVALID", ["$.evidenceDigest: expected sha256"])
        redaction = value["redactionApplied"]
        if not isinstance(redaction, bool):
            raise ContractViolation("PROVIDER_CONTRACT_INVALID", ["$.redactionApplied: expected boolean"])
        limitations = value["limitations"]
        if not isinstance(limitations, list) or any(not isinstance(item, str) or not item.strip() for item in limitations):
            raise ContractViolation("PROVIDER_CONTRACT_INVALID", ["$.limitations: expected string array"])
        attempt = value["attemptCount"]
        if not isinstance(attempt, int) or isinstance(attempt, bool) or attempt not in {1, 2, 3}:
            raise ContractViolation("PROVIDER_CONTRACT_INVALID", ["$.attemptCount: expected 1, 2, or 3"])
        return cls(run_id, provider_id, version, normalize_target(value["target"]), status, rule_id,
                   kind, safe_summary, evidence_digest, redaction, tuple(limitations), attempt)

    @property
    def digest(self) -> str:
        return digest_json({
            "attemptCount": self.attempt_count, "evidenceDigest": self.evidence_digest,
            "evidenceKind": self.evidence_kind, "evidenceSummary": self.evidence_summary,
            "limitations": list(self.limitations), "providerId": self.provider_id,
            "providerVersion": self.provider_version, "redactionApplied": self.redaction_applied,
            "ruleId": self.rule_id, "runId": self.run_id, "status": self.status,
            "target": self.target,
        })

