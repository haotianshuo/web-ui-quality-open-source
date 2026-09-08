"""Phase-1 Host apply request and post-write receipt verification.

This module contains no target-project write primitive. The Host performs the
actual edit. Runtime only validates a Host-issued ticket, prepares a sealed
request, and verifies the Host receipt against the observed filesystem state.
"""
from __future__ import annotations

import json
import hashlib
import hmac
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from .contracts import ContractViolation, canonical_json, digest_json, hash_file
from .phase1_authority import TrustedAuthorizationTicket, require_authorization_ticket, verify_authorization_ticket
from .phase1_boundaries import authorize_write_target, physical_target_identity, validate_write_ceiling, validate_write_physical_target
from .phase1_capabilities import TrustedCapabilitySnapshot, assess_required_channels, require_capability_snapshot
from .schema_validation import SchemaValidationError, validate_instance
from .release_info import PACKAGE_VERSION, KERNEL_VERSION, RECEIPT_PROTOCOL_VERSION

_APPLY_AUTHORITY = object()
_RECEIPT_AUTHORITY = object()


def _schema(name: str) -> dict[str, Any]:
    return json.loads((Path(__file__).with_name("schemas") / name).read_text(encoding="utf-8"))


def _body_digest(payload: Mapping[str, Any], digest_key: str) -> str:
    return digest_json({k: v for k, v in dict(payload).items() if k not in {digest_key, "integrityTag"}})


def build_target_digest(entries: Sequence[Mapping[str, Any]]) -> str:
    normalized = []
    for row in entries:
        normalized.append({
            "canonicalPath": str(row.get("canonicalPath") or "").replace("\\", "/"),
            "operation": str(row.get("operation") or ""),
            "expectedBeforeHash": str(row.get("expectedBeforeHash") or ""),
            "intendedAfterHash": str(row.get("intendedAfterHash") or ""),
        })
    normalized.sort(key=lambda item: (item["canonicalPath"], item["operation"]))
    if not normalized or any(not row["canonicalPath"] for row in normalized):
        raise ContractViolation("HOST_APPLY_TARGET_INVALID", ["$: non-empty target entries required"])
    return digest_json(normalized)


@dataclass(frozen=True, slots=True)
class TrustedHostApplyRequest:
    task_id: str
    ticket_digest: str
    target_digest: str
    baseline_digest: str
    reservation_ref: str
    entries: tuple[tuple[str, str, str, str], ...]
    _payload_json: str = field(repr=False, compare=False)
    _authority: object = field(repr=False, compare=False)

    def to_host_payload(self) -> dict[str, Any]:
        return json.loads(self._payload_json)

    def __reduce__(self):  # pragma: no cover
        raise TypeError("TrustedHostApplyRequest is process-local")


@dataclass(frozen=True, slots=True)
class TrustedHostWriteReceiptV2:
    receipt_digest: str
    ticket_digest: str
    task_id: str
    _payload_json: str = field(repr=False, compare=False)
    _authority: object = field(repr=False, compare=False)

    def to_dict(self) -> dict[str, Any]:
        return json.loads(self._payload_json)

    def __reduce__(self):  # pragma: no cover
        raise TypeError("TrustedHostWriteReceiptV2 is process-local")


def prepare_host_apply_request(
    project_root: str | Path,
    *,
    task_id: str,
    baseline_digest: str,
    entries: Sequence[Mapping[str, Any]],
    intent: str,
    write_ceiling: Mapping[str, Any],
    capability_snapshot: TrustedCapabilitySnapshot,
    ticket_payload: Mapping[str, Any],
    ticket_verifier: Callable[[Mapping[str, Any]], bool],
    reserve_ticket: Callable[[str, str], str],
    now: datetime | None = None,
) -> TrustedHostApplyRequest:
    """Prepare an EDIT-only Phase-1 request after Host authority validation."""

    snapshot = require_capability_snapshot(capability_snapshot)
    target_digest = build_target_digest(entries)
    ceiling = validate_write_ceiling(write_ceiling, now=now)
    ticket = verify_authorization_ticket(
        ticket_payload,
        verifier=ticket_verifier,
        task_id=task_id,
        baseline_digest=baseline_digest,
        target_digest=target_digest,
        write_ceiling_digest=str(ceiling["ceilingDigest"]),
        capability_snapshot_digest=snapshot.snapshot_digest,
        now=now,
    )
    assessment = assess_required_channels(
        [{"channelId": "fileEditControl", "minimumLevel": "ENFORCED", "purpose": "WRITE_SAFETY"}],
        snapshot,
    )
    if assessment["disposition"] != "ALLOW":
        raise ContractViolation("HOST_WRITE_CHANNEL_NOT_ENFORCED", ["$: fileEditControl is not ENFORCED by an authoritative Host snapshot"])
    normalized_entries: list[tuple[str, str, str, str]] = []
    seen: set[str] = set()
    seen_physical: dict[tuple[int, int], str] = {}
    for row in entries:
        operation = str(row.get("operation") or "")
        if operation != "EDIT":
            raise ContractViolation("PHASE1_OPERATION_NOT_SUPPORTED", ["$: Minimal Trust Contract Slice currently supports EDIT only"])
        rel = str(row.get("canonicalPath") or "").replace("\\", "/")
        if rel in seen:
            raise ContractViolation("HOST_APPLY_TARGET_INVALID", [f"$: duplicate target {rel}"])
        seen.add(rel)
        path = authorize_write_target(project_root, ceiling, relative_path=rel, operation=operation, intent=intent, now=now)
        if path.is_symlink() or not path.is_file():
            raise ContractViolation("HOST_APPLY_PRECONDITION_CHANGED", [f"$: {rel} is not a regular existing file"])
        physical = physical_target_identity(path)
        if physical in seen_physical:
            raise ContractViolation(
                "HOST_APPLY_PHYSICAL_TARGET_COLLISION",
                [f"$: {rel} aliases the same physical file as {seen_physical[physical]}"],
            )
        seen_physical[physical] = rel
        before = str(row.get("expectedBeforeHash") or "")
        actual = hash_file(path)
        if before != actual:
            raise ContractViolation("HOST_APPLY_PRECONDITION_CHANGED", [f"$: before hash mismatch for {rel}"])
        after = str(row.get("intendedAfterHash") or "")
        if len(after) != 64 or after == before:
            raise ContractViolation("HOST_APPLY_TARGET_INVALID", [f"$: invalid intended after hash for {rel}"])
        normalized_entries.append((rel, operation, before, after))
    if not callable(reserve_ticket):
        raise ContractViolation("HOST_TICKET_RESERVATION_REQUIRED", ["$: Host reservation callback required"])
    reservation = reserve_ticket(ticket.ticket_digest, ticket.nonce)
    if not isinstance(reservation, str) or not reservation.strip():
        raise ContractViolation("HOST_TICKET_RESERVATION_FAILED", ["$: Host did not reserve the single-use ticket"])
    body = {
        "schemaVersion": "1",
        "taskId": task_id,
        "ticketDigest": ticket.ticket_digest,
        "targetDigest": target_digest,
        "baselineDigest": baseline_digest,
        "writeDelegatedCeilingDigest": ceiling["ceilingDigest"],
        "capabilitySnapshotDigest": snapshot.snapshot_digest,
        "concurrencySemantics": ticket.to_dict().get("concurrencySemantics", "SINGLE_WRITER_SERIALIZED"),
        "reservationRef": reservation,
        "entries": [
            {"canonicalPath": rel, "operation": op, "expectedBeforeHash": before, "intendedAfterHash": after}
            for rel, op, before, after in normalized_entries
        ],
        "runtimeMayWrite": False,
        "hostExecutionRequired": True,
    }
    body["requestDigest"] = digest_json(body)
    return TrustedHostApplyRequest(
        task_id=task_id,
        ticket_digest=ticket.ticket_digest,
        target_digest=target_digest,
        baseline_digest=baseline_digest,
        reservation_ref=reservation,
        entries=tuple(normalized_entries),
        _payload_json=canonical_json(body),
        _authority=_APPLY_AUTHORITY,
    )


def require_host_apply_request(value: TrustedHostApplyRequest) -> TrustedHostApplyRequest:
    if not isinstance(value, TrustedHostApplyRequest) or value._authority is not _APPLY_AUTHORITY:
        raise ContractViolation("TRUSTED_HOST_APPLY_REQUEST_REQUIRED", ["$: trusted Host apply request required"])
    return value


def verify_host_write_receipt_v2(
    project_root: str | Path,
    receipt: Mapping[str, Any],
    *,
    apply_request: TrustedHostApplyRequest,
    receipt_verifier: Callable[[Mapping[str, Any]], bool],
    consume_ticket: Callable[[str, str], bool],
) -> TrustedHostWriteReceiptV2:
    request = require_host_apply_request(apply_request)
    payload = dict(receipt)
    try:
        validate_instance(payload, _schema("host-write-receipt-v2.schema.json"), base_dir=Path(__file__).with_name("schemas"))
    except SchemaValidationError as error:
        raise ContractViolation("HOST_WRITE_RECEIPT_V2_SCHEMA_INVALID", [f"$: {error}"]) from error
    if payload.get("receiptDigest") != _body_digest(payload, "receiptDigest"):
        raise ContractViolation("HOST_WRITE_RECEIPT_V2_TAMPERED", ["$.receiptDigest: mismatch"])
    if not callable(receipt_verifier) or receipt_verifier(payload) is not True:
        raise ContractViolation("HOST_WRITE_RECEIPT_V2_ATTESTATION_INVALID", ["$: Host receipt attestation failed"])
    if payload.get("taskId") != request.task_id or payload.get("authorizationTicketDigest") != request.ticket_digest:
        raise ContractViolation("HOST_WRITE_RECEIPT_V2_BINDING_MISMATCH", ["$: task/ticket binding mismatch"])
    request_payload = request.to_host_payload()
    if payload.get("concurrencySemantics") != request_payload.get("concurrencySemantics"):
        raise ContractViolation("HOST_WRITE_RECEIPT_V2_BINDING_MISMATCH", ["$.concurrencySemantics: mismatch"])
    if payload.get("actualOperation") != "EDIT":
        raise ContractViolation("HOST_WRITE_RECEIPT_V2_BINDING_MISMATCH", ["$.actualOperation: Minimal Trust Contract Slice expects EDIT"])
    if payload.get("applyResult") != "APPLIED":
        raise ContractViolation("HOST_WRITE_NOT_APPLIED", [f"$.applyResult: {payload.get('applyResult')}"])
    rows = payload.get("entries", [])
    expected = {rel: (op, before, after) for rel, op, before, after in request.entries}
    if {str(row.get("canonicalPath")) for row in rows} != set(expected):
        raise ContractViolation("HOST_WRITE_RECEIPT_V2_BINDING_MISMATCH", ["$.entries: exact target set required"])
    root = Path(project_root).expanduser().resolve()
    for row in rows:
        rel = str(row.get("canonicalPath") or "").replace("\\", "/")
        op, before, intended_after = expected[rel]
        if row.get("actualOperation") != op or row.get("entryResult") != "APPLIED":
            raise ContractViolation("HOST_WRITE_RECEIPT_V2_BINDING_MISMATCH", [f"$.entries[{rel}]: operation/result mismatch"])
        if row.get("actualBeforeHash") != before or row.get("actualAfterHash") != intended_after:
            raise ContractViolation("HOST_WRITE_RECEIPT_V2_BINDING_MISMATCH", [f"$.entries[{rel}]: before/after mismatch"])
        try:
            path = validate_write_physical_target(root, rel)
        except ContractViolation as error:
            raise ContractViolation("HOST_WRITE_RECEIPT_V2_PATH_ALIAS_OR_ESCAPE", [f"$: {rel}: {error.code}"]) from error
        if not path.is_file() or hash_file(path) != intended_after:
            raise ContractViolation("HOST_WRITE_RECEIPT_V2_ACTUAL_STATE_MISMATCH", [f"$: current file state does not match receipt for {rel}"])
    if not callable(consume_ticket) or consume_ticket(request.ticket_digest, request.reservation_ref) is not True:
        raise ContractViolation("HOST_TICKET_CONSUMPTION_FAILED", ["$: Host did not confirm single-use ticket consumption"])
    return TrustedHostWriteReceiptV2(
        receipt_digest=str(payload["receiptDigest"]),
        ticket_digest=request.ticket_digest,
        task_id=request.task_id,
        _payload_json=canonical_json(payload),
        _authority=_RECEIPT_AUTHORITY,
    )


def require_host_write_receipt_v2(value: TrustedHostWriteReceiptV2) -> TrustedHostWriteReceiptV2:
    if not isinstance(value, TrustedHostWriteReceiptV2) or value._authority is not _RECEIPT_AUTHORITY:
        raise ContractViolation("TRUSTED_HOST_WRITE_RECEIPT_V2_REQUIRED", ["$: verified Host receipt required"])
    return value


@dataclass(frozen=True, slots=True)
class TrustedHostApplyRequestV3:
    task_id: str
    run_id: str
    session_id: str
    activation_id: str
    package_tree_digest: str
    baseline_digest: str
    target_digest: str
    change_set_digest: str
    verification_policy_digest: str
    nonce: str
    issued_at: str
    expires_at: str
    expected_host_identity: str
    expected_attestation_identity: str
    freshness_epoch: int
    base_request: TrustedHostApplyRequest = field(repr=False, compare=False)
    _authority: object = field(repr=False, compare=False)

    def to_host_payload(self) -> dict[str, Any]:
        base = self.base_request.to_host_payload()
        return {
            **base,
            "schemaVersion": "3",
            "receiptProtocolVersion": RECEIPT_PROTOCOL_VERSION,
            "pluginVersion": PACKAGE_VERSION,
            "kernelVersion": KERNEL_VERSION,
            "packageTreeDigest": self.package_tree_digest,
            "activationId": self.activation_id,
            "runId": self.run_id,
            "sessionId": self.session_id,
            "changeSetDigest": self.change_set_digest,
            "verificationPolicyDigest": self.verification_policy_digest,
            "nonce": self.nonce,
            "issuedAt": self.issued_at,
            "expiresAt": self.expires_at,
            "freshnessEpoch": self.freshness_epoch,
            "expectedHostIdentity": self.expected_host_identity,
            "expectedAttestationIdentity": self.expected_attestation_identity,
        }

    def __reduce__(self):  # pragma: no cover
        raise TypeError("TrustedHostApplyRequestV3 is process-local")


@dataclass(frozen=True, slots=True)
class TrustedHostWriteReceiptV3:
    receipt_digest: str
    task_id: str
    run_id: str
    session_id: str
    activation_id: str
    package_tree_digest: str
    baseline_digest: str
    target_digest: str
    change_set_digest: str
    verification_policy_digest: str
    nonce: str
    issued_at: str
    expires_at: str
    freshness_epoch: int
    _payload_json: str = field(repr=False, compare=False)
    _project_root: str = field(repr=False, compare=False)
    _authority: object = field(repr=False, compare=False)

    def to_dict(self) -> dict[str, Any]:
        return json.loads(self._payload_json)

    def __reduce__(self):  # pragma: no cover
        raise TypeError("TrustedHostWriteReceiptV3 is process-local")


def _parse_time(value: str, *, code: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError) as error:
        raise ContractViolation(code, ["$: invalid receipt time"]) from error
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def prepare_host_apply_request_v3(
    project_root: str | Path,
    *,
    task_id: str,
    run_id: str,
    session_id: str,
    activation_id: str,
    package_tree_digest: str,
    baseline_digest: str,
    entries: Sequence[Mapping[str, Any]],
    change_set_digest: str | None,
    verification_policy_digest: str,
    expected_host_identity: str,
    expected_attestation_identity: str,
    freshness_epoch: int,
    intent: str,
    write_ceiling: Mapping[str, Any],
    capability_snapshot: TrustedCapabilitySnapshot,
    ticket_payload: Mapping[str, Any],
    ticket_verifier: Callable[[Mapping[str, Any]], bool],
    reserve_ticket: Callable[[str, str], str],
    now: datetime | None = None,
) -> TrustedHostApplyRequestV3:
    """Prepare a V3 Host request while preserving Runtime's no-write boundary."""
    for name, value in {"runId": run_id, "sessionId": session_id, "activationId": activation_id, "expectedHostIdentity": expected_host_identity, "expectedAttestationIdentity": expected_attestation_identity}.items():
        if not isinstance(value, str) or not value.strip():
            raise ContractViolation("HOST_APPLY_V3_BINDING_INVALID", [f"$.{name}: required"])
    for name, value in {"packageTreeDigest": package_tree_digest, "verificationPolicyDigest": verification_policy_digest}.items():
        if not isinstance(value, str) or len(value) != 64:
            raise ContractViolation("HOST_APPLY_V3_BINDING_INVALID", [f"$.{name}: sha256 required"])
    if not isinstance(freshness_epoch, int) or freshness_epoch < 1:
        raise ContractViolation("HOST_APPLY_V3_BINDING_INVALID", ["$.freshnessEpoch: positive integer required"])
    base = prepare_host_apply_request(
        project_root, task_id=task_id, baseline_digest=baseline_digest, entries=entries, intent=intent,
        write_ceiling=write_ceiling, capability_snapshot=capability_snapshot, ticket_payload=ticket_payload,
        ticket_verifier=ticket_verifier, reserve_ticket=reserve_ticket, now=now,
    )
    ticket = dict(ticket_payload)
    target_digest = base.target_digest
    change_digest = str(change_set_digest or target_digest)
    if len(change_digest) != 64:
        raise ContractViolation("HOST_APPLY_V3_BINDING_INVALID", ["$.changeSetDigest: sha256 required"])
    return TrustedHostApplyRequestV3(
        task_id=task_id, run_id=run_id, session_id=session_id, activation_id=activation_id,
        package_tree_digest=package_tree_digest, baseline_digest=baseline_digest, target_digest=target_digest,
        change_set_digest=change_digest, verification_policy_digest=verification_policy_digest,
        nonce=str(ticket.get("nonce") or ""), issued_at=str(ticket.get("issuedAt") or ""), expires_at=str(ticket.get("expiresAt") or ""),
        expected_host_identity=expected_host_identity, expected_attestation_identity=expected_attestation_identity,
        freshness_epoch=freshness_epoch, base_request=base, _authority=_APPLY_AUTHORITY,
    )


def require_host_apply_request_v3(value: TrustedHostApplyRequestV3) -> TrustedHostApplyRequestV3:
    if not isinstance(value, TrustedHostApplyRequestV3) or value._authority is not _APPLY_AUTHORITY:
        raise ContractViolation("TRUSTED_HOST_APPLY_REQUEST_V3_REQUIRED", ["$: trusted V3 Host apply request required"])
    return value


def verify_host_write_receipt_v3(
    project_root: str | Path,
    receipt: Mapping[str, Any],
    *,
    apply_request: TrustedHostApplyRequestV3,
    receipt_verifier: Callable[[Mapping[str, Any]], bool],
    consume_ticket: Callable[[str, str], bool],
    now: datetime | None = None,
) -> TrustedHostWriteReceiptV3:
    request = require_host_apply_request_v3(apply_request)
    payload = dict(receipt)
    try:
        validate_instance(payload, _schema("host-write-receipt-v3.schema.json"), base_dir=Path(__file__).with_name("schemas"))
    except SchemaValidationError as error:
        raise ContractViolation("HOST_WRITE_RECEIPT_V3_SCHEMA_INVALID", [f"$: {error}"]) from error
    if payload.get("receiptDigest") != _body_digest(payload, "receiptDigest"):
        raise ContractViolation("HOST_WRITE_RECEIPT_V3_TAMPERED", ["$.receiptDigest: mismatch"])
    if not callable(receipt_verifier) or receipt_verifier(payload) is not True:
        raise ContractViolation("HOST_WRITE_RECEIPT_V3_ATTESTATION_INVALID", ["$: Host receipt attestation failed"])
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    issued = _parse_time(str(payload.get("issuedAt")), code="HOST_WRITE_RECEIPT_V3_TIME_INVALID")
    expires = _parse_time(str(payload.get("expiresAt")), code="HOST_WRITE_RECEIPT_V3_TIME_INVALID")
    if issued > current or expires <= current or expires <= issued:
        raise ContractViolation("HOST_WRITE_RECEIPT_V3_EXPIRED", ["$: receipt is outside its freshness window"])
    expected = {
        "receiptProtocolVersion": RECEIPT_PROTOCOL_VERSION, "pluginVersion": PACKAGE_VERSION, "kernelVersion": KERNEL_VERSION,
        "packageTreeDigest": request.package_tree_digest, "activationId": request.activation_id, "runId": request.run_id,
        "sessionId": request.session_id, "taskId": request.task_id, "nonce": request.nonce,
        "baselineDigest": request.baseline_digest, "targetDigest": request.target_digest, "changeSetDigest": request.change_set_digest,
        "verificationPolicyDigest": request.verification_policy_digest, "hostIdentity": request.expected_host_identity,
        "attestationIdentity": request.expected_attestation_identity, "authorizationTicketDigest": request.base_request.ticket_digest,
        "freshnessEpoch": request.freshness_epoch,
    }
    mismatches = [key for key, value in expected.items() if payload.get(key) != value]
    if mismatches:
        raise ContractViolation("HOST_WRITE_RECEIPT_V3_BINDING_MISMATCH", [f"$.{key}: mismatch" for key in mismatches])
    if payload.get("actualOperation") != "EDIT" or payload.get("applyResult") != "APPLIED":
        raise ContractViolation("HOST_WRITE_RECEIPT_V3_BINDING_MISMATCH", ["$: only fully applied EDIT is supported"])
    expected_entries = {rel: (op, before, after) for rel, op, before, after in request.base_request.entries}
    rows = payload.get("entries") or []
    if {str(row.get("canonicalPath")) for row in rows} != set(expected_entries):
        raise ContractViolation("HOST_WRITE_RECEIPT_V3_BINDING_MISMATCH", ["$.entries: exact target set required"])
    root = Path(project_root).expanduser().resolve()
    for row in rows:
        rel = str(row.get("canonicalPath") or "").replace("\\", "/")
        op, before, intended_after = expected_entries[rel]
        if row.get("actualOperation") != op or row.get("entryResult") != "APPLIED" or row.get("actualBeforeHash") != before or row.get("actualAfterHash") != intended_after:
            raise ContractViolation("HOST_WRITE_RECEIPT_V3_BINDING_MISMATCH", [f"$.entries[{rel}]: operation/hash mismatch"])
        try:
            path = validate_write_physical_target(root, rel)
        except ContractViolation as error:
            raise ContractViolation("HOST_WRITE_RECEIPT_V3_PATH_ALIAS_OR_ESCAPE", [f"$: {rel}: {error.code}"]) from error
        if not path.is_file() or hash_file(path) != intended_after:
            raise ContractViolation("HOST_WRITE_RECEIPT_V3_ACTUAL_STATE_MISMATCH", [f"$: current file state does not match receipt for {rel}"])
    if not callable(consume_ticket) or consume_ticket(request.base_request.ticket_digest, request.base_request.reservation_ref) is not True:
        raise ContractViolation("HOST_TICKET_CONSUMPTION_FAILED", ["$: Host did not confirm single-use ticket consumption"])
    return TrustedHostWriteReceiptV3(
        receipt_digest=str(payload["receiptDigest"]), task_id=request.task_id, run_id=request.run_id, session_id=request.session_id,
        activation_id=request.activation_id, package_tree_digest=request.package_tree_digest, baseline_digest=request.baseline_digest,
        target_digest=request.target_digest, change_set_digest=request.change_set_digest, verification_policy_digest=request.verification_policy_digest,
        nonce=request.nonce, issued_at=str(payload["issuedAt"]), expires_at=str(payload["expiresAt"]), freshness_epoch=int(payload["freshnessEpoch"]),
        _payload_json=canonical_json(payload), _project_root=str(root), _authority=_RECEIPT_AUTHORITY,
    )



def verify_persisted_host_write_receipt_v3(
    project_root: str | Path,
    receipt: Mapping[str, Any],
    *,
    binding: Mapping[str, Any],
    hmac_key: bytes | str | None,
    now: datetime | None = None,
) -> TrustedHostWriteReceiptV3:
    """Verify a V3 receipt against a persisted public-run apply binding.

    The persisted binding is read-only planning evidence, not write authority.
    VERIFIED requires a Host-provided HMAC key supplied outside the project
    plus exact package/run/session/task/target/change-set/policy/file-state
    binding. Runtime never creates the Host integrity tag.
    """
    payload = dict(receipt)
    try:
        validate_instance(payload, _schema("host-write-receipt-v3.schema.json"), base_dir=Path(__file__).with_name("schemas"))
    except SchemaValidationError as error:
        raise ContractViolation("HOST_WRITE_RECEIPT_V3_SCHEMA_INVALID", [f"$: {error}"]) from error
    if payload.get("receiptDigest") != _body_digest(payload, "receiptDigest"):
        raise ContractViolation("HOST_WRITE_RECEIPT_V3_TAMPERED", ["$.receiptDigest: mismatch"])
    if hmac_key is None or hmac_key == b"" or hmac_key == "":
        raise ContractViolation("HOST_WRITE_RECEIPT_V3_ATTESTATION_UNAVAILABLE", ["$: set the Host-provisioned WUQ_HOST_RECEIPT_HMAC_KEY outside the target project before After verification"])
    key = hmac_key.encode("utf-8") if isinstance(hmac_key, str) else bytes(hmac_key)
    expected_tag = "hmac:" + hmac.new(key, str(payload.get("receiptDigest") or "").encode("utf-8"), hashlib.sha256).hexdigest()
    if payload.get("integrityMechanism") != "HMAC_SHA256" or not hmac.compare_digest(str(payload.get("integrityTag") or ""), expected_tag):
        raise ContractViolation("HOST_WRITE_RECEIPT_V3_ATTESTATION_INVALID", ["$: Host receipt HMAC attestation failed"])
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    issued = _parse_time(str(payload.get("issuedAt")), code="HOST_WRITE_RECEIPT_V3_TIME_INVALID")
    expires = _parse_time(str(payload.get("expiresAt")), code="HOST_WRITE_RECEIPT_V3_TIME_INVALID")
    if issued > current or expires <= current or expires <= issued:
        raise ContractViolation("HOST_WRITE_RECEIPT_V3_EXPIRED", ["$: receipt is outside its freshness window"])
    required = {
        "receiptProtocolVersion": RECEIPT_PROTOCOL_VERSION,
        "pluginVersion": PACKAGE_VERSION,
        "kernelVersion": KERNEL_VERSION,
        "packageTreeDigest": binding.get("packageTreeDigest"),
        "activationId": binding.get("activationId"),
        "runId": binding.get("runId"),
        "sessionId": binding.get("sessionId"),
        "taskId": binding.get("taskId"),
        "nonce": binding.get("nonce"),
        "baselineDigest": binding.get("baselineDigest"),
        "targetDigest": binding.get("targetDigest"),
        "changeSetDigest": binding.get("changeSetDigest"),
        "verificationPolicyDigest": binding.get("verificationPolicyDigest"),
        "hostIdentity": binding.get("hostIdentity"),
        "attestationIdentity": binding.get("attestationIdentity"),
        "authorizationTicketDigest": binding.get("authorizationTicketDigest"),
        "freshnessEpoch": binding.get("freshnessEpoch"),
    }
    mismatches = [key for key, value in required.items() if payload.get(key) != value]
    if mismatches:
        raise ContractViolation("HOST_WRITE_RECEIPT_V3_BINDING_MISMATCH", [f"$.{key}: mismatch" for key in mismatches])
    if payload.get("actualOperation") not in {"EDIT", "CHANGE_SET"} or payload.get("applyResult") != "APPLIED":
        raise ContractViolation("HOST_WRITE_RECEIPT_V3_BINDING_MISMATCH", ["$: applied EDIT/CHANGE_SET required"])
    expected_entries = {
        str(row.get("canonicalPath") or "").replace("\\", "/"): (
            str(row.get("operation") or "EDIT"),
            str(row.get("expectedBeforeHash") or ""),
            str(row.get("intendedAfterHash") or ""),
        )
        for row in list(binding.get("entries") or []) if isinstance(row, Mapping)
    }
    rows = list(payload.get("entries") or [])
    if not expected_entries or {str(row.get("canonicalPath") or "").replace("\\", "/") for row in rows} != set(expected_entries):
        raise ContractViolation("HOST_WRITE_RECEIPT_V3_BINDING_MISMATCH", ["$.entries: exact pre-authorized target set required"])
    root = Path(project_root).expanduser().resolve()
    for row in rows:
        rel = str(row.get("canonicalPath") or "").replace("\\", "/")
        op, before, intended_after = expected_entries[rel]
        if row.get("actualOperation") != op or row.get("entryResult") != "APPLIED" or row.get("actualBeforeHash") != before or row.get("actualAfterHash") != intended_after:
            raise ContractViolation("HOST_WRITE_RECEIPT_V3_BINDING_MISMATCH", [f"$.entries[{rel}]: operation/hash mismatch"])
        try:
            path = validate_write_physical_target(root, rel)
        except ContractViolation as error:
            raise ContractViolation("HOST_WRITE_RECEIPT_V3_PATH_ALIAS_OR_ESCAPE", [f"$: {rel}: {error.code}"]) from error
        if not path.is_file() or hash_file(path) != intended_after:
            raise ContractViolation("HOST_WRITE_RECEIPT_V3_ACTUAL_STATE_MISMATCH", [f"$: current file state does not match receipt for {rel}"])
    return TrustedHostWriteReceiptV3(
        receipt_digest=str(payload["receiptDigest"]), task_id=str(binding.get("taskId")), run_id=str(binding.get("runId")),
        session_id=str(binding.get("sessionId")), activation_id=str(binding.get("activationId")),
        package_tree_digest=str(binding.get("packageTreeDigest")), baseline_digest=str(binding.get("baselineDigest")),
        target_digest=str(binding.get("targetDigest")), change_set_digest=str(binding.get("changeSetDigest")),
        verification_policy_digest=str(binding.get("verificationPolicyDigest")), nonce=str(binding.get("nonce")),
        issued_at=str(payload["issuedAt"]), expires_at=str(payload["expiresAt"]), freshness_epoch=int(payload["freshnessEpoch"]),
        _payload_json=canonical_json(payload), _project_root=str(root), _authority=_RECEIPT_AUTHORITY,
    )

def require_host_write_receipt_v3(value: TrustedHostWriteReceiptV3) -> TrustedHostWriteReceiptV3:
    if not isinstance(value, TrustedHostWriteReceiptV3) or value._authority is not _RECEIPT_AUTHORITY:
        raise ContractViolation("TRUSTED_HOST_WRITE_RECEIPT_V3_REQUIRED", ["$: verified V3 Host receipt required"])
    return value


def receipt_v3_current_state_matches(value: TrustedHostWriteReceiptV3) -> bool:
    receipt = require_host_write_receipt_v3(value)
    root = Path(receipt._project_root).resolve()
    payload = receipt.to_dict()
    try:
        for row in payload.get("entries") or []:
            rel = str(row.get("canonicalPath") or "").replace("\\", "/")
            path = validate_write_physical_target(root, rel)
            if not path.is_file() or hash_file(path) != str(row.get("actualAfterHash") or ""):
                return False
    except (OSError, ContractViolation):
        return False
    return True


__all__ = [
    "build_target_digest", "TrustedHostApplyRequest", "TrustedHostWriteReceiptV2",
    "prepare_host_apply_request", "require_host_apply_request", "verify_host_write_receipt_v2",
    "require_host_write_receipt_v2",
    "TrustedHostApplyRequestV3", "TrustedHostWriteReceiptV3", "prepare_host_apply_request_v3",
    "verify_persisted_host_write_receipt_v3",
    "require_host_apply_request_v3", "verify_host_write_receipt_v3", "require_host_write_receipt_v3",
    "receipt_v3_current_state_matches",
]
