"""Host-issued Phase-1 write ticket verification.

Runtime can verify and bind an externally issued ticket, but it has no issuer
secret and exposes no API capable of minting write authority.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from .contracts import ContractViolation, canonical_json, digest_json
from .schema_validation import SchemaValidationError, validate_instance

_TICKET_AUTHORITY = object()


def _schema() -> dict[str, Any]:
    return json.loads((Path(__file__).with_name("schemas") / "authorization-ticket-v2.schema.json").read_text(encoding="utf-8"))


def _body_digest(payload: Mapping[str, Any]) -> str:
    return digest_json({k: v for k, v in dict(payload).items() if k not in {"ticketDigest", "integrityTag"}})


def _time(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as error:
        raise ContractViolation("AUTHORIZATION_TICKET_TIME_INVALID", ["$: invalid ticket time"]) from error


@dataclass(frozen=True, slots=True)
class TrustedAuthorizationTicket:
    ticket_digest: str
    task_id: str
    nonce: str
    _payload_json: str = field(repr=False, compare=False)
    _authority: object = field(repr=False, compare=False)

    def to_dict(self) -> dict[str, Any]:
        return json.loads(self._payload_json)

    def __reduce__(self):  # pragma: no cover - defensive
        raise TypeError("TrustedAuthorizationTicket is process-local")


def verify_authorization_ticket(
    ticket: Mapping[str, Any],
    *,
    verifier: Callable[[Mapping[str, Any]], bool],
    task_id: str,
    baseline_digest: str,
    target_digest: str,
    write_ceiling_digest: str,
    capability_snapshot_digest: str,
    now: datetime | None = None,
) -> TrustedAuthorizationTicket:
    payload = dict(ticket)
    try:
        validate_instance(payload, _schema(), base_dir=Path(__file__).with_name("schemas"))
    except SchemaValidationError as error:
        raise ContractViolation("AUTHORIZATION_TICKET_SCHEMA_INVALID", [f"$: {error}"]) from error
    if payload.get("ticketDigest") != _body_digest(payload):
        raise ContractViolation("AUTHORIZATION_TICKET_TAMPERED", ["$.ticketDigest: mismatch"])
    if not callable(verifier) or verifier(payload) is not True:
        raise ContractViolation("AUTHORIZATION_TICKET_ATTESTATION_INVALID", ["$: Host ticket attestation failed"])
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    if _time(str(payload["issuedAt"])) > current:
        raise ContractViolation("AUTHORIZATION_TICKET_NOT_YET_VALID", ["$.issuedAt: future ticket"])
    if _time(str(payload["expiresAt"])) <= current:
        raise ContractViolation("AUTHORIZATION_TICKET_EXPIRED", ["$.expiresAt: expired"])
    expected = {
        "taskId": task_id,
        "baselineDigest": baseline_digest,
        "targetDigest": target_digest,
        "writeDelegatedCeilingDigest": write_ceiling_digest,
        "capabilitySnapshotDigest": capability_snapshot_digest,
    }
    mismatches = [key for key, value in expected.items() if payload.get(key) != value]
    if mismatches:
        raise ContractViolation("AUTHORIZATION_TICKET_BINDING_MISMATCH", [f"$.{key}: mismatch" for key in mismatches])
    if payload.get("singleUse") is not True:
        raise ContractViolation("AUTHORIZATION_TICKET_NOT_SINGLE_USE", ["$.singleUse: must be true"])
    return TrustedAuthorizationTicket(
        ticket_digest=str(payload["ticketDigest"]),
        task_id=str(payload["taskId"]),
        nonce=str(payload["nonce"]),
        _payload_json=canonical_json(payload),
        _authority=_TICKET_AUTHORITY,
    )


def require_authorization_ticket(value: TrustedAuthorizationTicket) -> TrustedAuthorizationTicket:
    if not isinstance(value, TrustedAuthorizationTicket) or value._authority is not _TICKET_AUTHORITY:
        raise ContractViolation("TRUSTED_AUTHORIZATION_TICKET_REQUIRED", ["$: verified Host authorization ticket required"])
    return value


__all__ = ["TrustedAuthorizationTicket", "verify_authorization_ticket", "require_authorization_ticket"]
