"""Minimal Phase-1 evidence provenance and mutation-epoch freshness contracts."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from .contracts import ContractViolation, canonical_json, digest_json
from .schema_validation import SchemaValidationError, validate_instance

_OBSERVATION_AUTHORITY = object()
_ALLOWED_SUBTYPES = {"SOURCE", "RUNTIME", "TEST", "BROWSER", "NETWORK", "FILE_STATE"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _schema() -> dict[str, Any]:
    return json.loads((Path(__file__).with_name("schemas") / "evidence-minimal-v1.schema.json").read_text(encoding="utf-8"))


def _validate(value: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(value)
    try:
        validate_instance(payload, _schema(), base_dir=Path(__file__).with_name("schemas"))
    except SchemaValidationError as error:
        raise ContractViolation("PHASE1_EVIDENCE_SCHEMA_INVALID", [f"$: {error}"]) from error
    return payload


@dataclass(frozen=True, slots=True)
class TrustedHostObservation:
    evidence_digest: str
    task_id: str
    subtype: str
    state_epoch: int
    _payload_json: str = field(repr=False, compare=False)
    _authority: object = field(repr=False, compare=False)

    def to_dict(self) -> dict[str, Any]:
        return json.loads(self._payload_json)

    def __reduce__(self):  # pragma: no cover
        raise TypeError("TrustedHostObservation is process-local")


def model_inferred_evidence(
    *,
    evidence_id: str,
    task_id: str,
    source_ref: str,
    payload: Mapping[str, Any],
    baseline_digest: str | None = None,
    environment_fingerprint: str | None = None,
) -> dict[str, Any]:
    value = {
        "schemaVersion": "1",
        "evidenceId": evidence_id,
        "taskId": task_id,
        "kind": "MODEL_INFERRED",
        "sourceRef": source_ref,
        "baselineDigest": baseline_digest,
        "environmentFingerprint": environment_fingerprint,
        "payloadDigest": digest_json(dict(payload)),
        "observedAt": None,
        "stateEpoch": None,
        "freshnessCheckedAt": None,
        "staleReason": None,
    }
    return _validate(value)


def bind_host_observation(
    *,
    evidence_id: str,
    task_id: str,
    subtype: str,
    source_ref: str,
    observation_payload: Mapping[str, Any],
    baseline_digest: str | None,
    environment_fingerprint: str | None,
    verifier: Callable[[Mapping[str, Any]], bool],
    state_epoch: int = 0,
    observed_at: str | None = None,
    freshness_checked_at: str | None = None,
) -> TrustedHostObservation:
    if subtype not in _ALLOWED_SUBTYPES:
        raise ContractViolation("HOST_OBSERVATION_SUBTYPE_INVALID", ["$: unsupported observed subtype"])
    if not isinstance(state_epoch, int) or isinstance(state_epoch, bool) or state_epoch < 0:
        raise ContractViolation("HOST_OBSERVATION_STATE_EPOCH_INVALID", ["$: stateEpoch must be a non-negative integer"])
    observed = observed_at or _now()
    envelope = {
        "taskId": task_id,
        "subtype": subtype,
        "sourceRef": source_ref,
        "baselineDigest": baseline_digest,
        "environmentFingerprint": environment_fingerprint,
        "payload": dict(observation_payload),
        "observedAt": observed,
        "stateEpoch": state_epoch,
    }
    if not callable(verifier) or verifier(envelope) is not True:
        raise ContractViolation("HOST_OBSERVATION_ATTESTATION_INVALID", ["$: Host observation attestation failed"])
    value = {
        "schemaVersion": "1",
        "evidenceId": evidence_id,
        "taskId": task_id,
        "kind": "HOST_OBSERVED",
        "observedSubtype": subtype,
        "sourceRef": source_ref,
        "baselineDigest": baseline_digest,
        "environmentFingerprint": environment_fingerprint,
        "payloadDigest": digest_json(dict(observation_payload)),
        "observedAt": observed,
        "stateEpoch": state_epoch,
        "freshnessCheckedAt": freshness_checked_at or _now(),
        "staleReason": None,
    }
    payload = _validate(value)
    return TrustedHostObservation(
        evidence_digest=digest_json(payload),
        task_id=task_id,
        subtype=subtype,
        state_epoch=state_epoch,
        _payload_json=canonical_json(payload),
        _authority=_OBSERVATION_AUTHORITY,
    )


def require_host_observation(value: TrustedHostObservation) -> TrustedHostObservation:
    if not isinstance(value, TrustedHostObservation) or value._authority is not _OBSERVATION_AUTHORITY:
        raise ContractViolation("TRUSTED_HOST_OBSERVATION_REQUIRED", ["$: trusted Host observation required"])
    return value


def stale_evidence(evidence: Mapping[str, Any] | TrustedHostObservation, *, reason: str) -> dict[str, Any]:
    if isinstance(evidence, TrustedHostObservation):
        base = evidence.to_dict()
    else:
        base = _validate(evidence)
    stale = {
        **base,
        "kind": "STALE",
        "freshnessCheckedAt": _now(),
        "staleReason": reason,
    }
    stale.pop("observedSubtype", None)
    return _validate(stale)


def evidence_payloads(values: Sequence[Mapping[str, Any] | TrustedHostObservation]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for value in values:
        if isinstance(value, TrustedHostObservation):
            out.append(require_host_observation(value).to_dict())
        else:
            out.append(_validate(value))
    return out


def evidence_can_support_verified(
    values: Sequence[Mapping[str, Any] | TrustedHostObservation],
    *,
    task_id: str,
    baseline_digest: str | None,
    environment_fingerprint: str | None,
    required_subtypes: Sequence[str],
    minimum_state_epoch: int = 0,
) -> tuple[bool, list[str]]:
    rows = evidence_payloads(values)
    reasons: list[str] = []
    if not rows:
        return False, ["EVIDENCE_MISSING"]
    observed = [row for row in rows if row.get("kind") == "HOST_OBSERVED"]
    if any(row.get("kind") == "STALE" for row in rows):
        reasons.append("EVIDENCE_STALE")
    if any(row.get("taskId") != task_id for row in observed):
        reasons.append("EVIDENCE_TASK_MISMATCH")
    if baseline_digest is not None and any(row.get("baselineDigest") != baseline_digest for row in observed):
        reasons.append("EVIDENCE_BASELINE_MISMATCH")
    if environment_fingerprint is not None and any(row.get("environmentFingerprint") != environment_fingerprint for row in observed):
        reasons.append("EVIDENCE_ENVIRONMENT_MISMATCH")
    if any(not row.get("freshnessCheckedAt") for row in observed):
        reasons.append("EVIDENCE_FRESHNESS_UNKNOWN")
    if any(not isinstance(row.get("stateEpoch"), int) for row in observed):
        reasons.append("EVIDENCE_STATE_EPOCH_UNKNOWN")
    elif any(int(row["stateEpoch"]) < int(minimum_state_epoch) for row in observed):
        reasons.append("EVIDENCE_STATE_EPOCH_STALE")
    available = {str(row.get("observedSubtype")) for row in observed}
    missing = sorted(set(required_subtypes) - available)
    if missing:
        reasons.extend(f"EVIDENCE_TYPE_MISSING:{item}" for item in missing)
    if not observed:
        reasons.append("HOST_OBSERVED_EVIDENCE_MISSING")
    return not reasons, sorted(dict.fromkeys(reasons))


__all__ = [
    "TrustedHostObservation", "model_inferred_evidence", "bind_host_observation", "require_host_observation",
    "stale_evidence", "evidence_payloads", "evidence_can_support_verified",
]
