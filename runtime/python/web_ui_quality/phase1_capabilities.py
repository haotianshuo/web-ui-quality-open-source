"""Phase-1 typed Host capability contracts for the 4.1 experimental branch.

The module is deliberately read-only. It validates Host-provided capability
snapshots and computes deterministic dispositions; it never grants write
authority and never mutates a target project.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from .contracts import ContractViolation, canonical_json, digest_json
from .schema_validation import SchemaValidationError, validate_instance

LEVEL = {"UNKNOWN": 0, "UNAVAILABLE": 1, "ADVISORY": 2, "DETECT_ONLY": 3, "ENFORCED": 4}
PURPOSE_DISPOSITION = {
    "WRITE_SAFETY": "BLOCK",
    "INTEGRITY": "BLOCK",
    "CONTEXT_ISOLATION_REQUIRED": "BLOCK",
    "MEASUREMENT": "NOT_MEASURED",
    "OPTIONAL_TELEMETRY": "ADVISORY",
    "IDENTITY_REQUIRED": "BLOCK",
}
_ALLOWED_KINDS = {"MUTATION", "OBSERVATION", "IDENTITY", "TELEMETRY", "CONTEXT_CONTROL", "EXECUTION_CONTROL", "PERSISTENCE"}

_CHANNEL_KIND = {
    "fileEditControl": "MUTATION", "fileCreateControl": "MUTATION", "fileDeleteControl": "MUTATION",
    "fileRenameControl": "MUTATION", "shellWriteControl": "MUTATION", "subprocessWriteControl": "MUTATION",
    "formatterWriteControl": "MUTATION", "packageScriptWriteControl": "MUTATION", "gitMutationControl": "MUTATION",
    "fileReadControl": "OBSERVATION", "browserControl": "OBSERVATION", "testExecutionTelemetry": "OBSERVATION",
    "toolEventTelemetry": "OBSERVATION", "networkReadControl": "OBSERVATION",
    "taskIdentity": "IDENTITY", "modelIdentity": "IDENTITY", "modelVersionIdentity": "IDENTITY",
    "reasoningModeIdentity": "IDENTITY", "tokenTelemetry": "TELEMETRY", "costTelemetry": "TELEMETRY",
    "wallClockTelemetry": "TELEMETRY", "guidanceInjection": "CONTEXT_CONTROL", "contextShaping": "CONTEXT_CONTROL",
    "redactionControl": "CONTEXT_CONTROL", "contextIsolation": "CONTEXT_CONTROL", "crossTaskMemoryControl": "CONTEXT_CONTROL",
    "secretAccessControl": "CONTEXT_CONTROL", "checkpointControl": "EXECUTION_CONTROL", "processControl": "EXECUTION_CONTROL",
    "toolInvocationControl": "EXECUTION_CONTROL", "claimResultStorage": "PERSISTENCE",
}
_SNAPSHOT_AUTHORITY = object()


def _schema(name: str) -> dict[str, Any]:
    path = Path(__file__).with_name("schemas") / name
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_time(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as error:
        raise ContractViolation("CAPABILITY_TIME_INVALID", ["$: invalid ISO-8601 time"]) from error


def _is_expired(value: str | None, now: datetime | None = None) -> bool:
    stamp = _parse_time(value)
    if stamp is None:
        return False
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return stamp <= current


def _digest_without(value: Mapping[str, Any], *keys: str) -> str:
    return digest_json({k: v for k, v in dict(value).items() if k not in set(keys)})


def _validate_assessment(row: Mapping[str, Any]) -> None:
    kind = row.get("kind")
    if kind not in _ALLOWED_KINDS:
        raise ContractViolation("CAPABILITY_KIND_INVALID", [f"$.channelAssessments[{row.get('channelId','?')}].kind: unsupported"])
    expected_kind = _CHANNEL_KIND.get(str(row.get("channelId") or ""))
    if expected_kind is not None and kind != expected_kind:
        raise ContractViolation("CAPABILITY_KIND_MISMATCH", [f"$.channelAssessments[{row.get('channelId','?')}].kind: expected {expected_kind}"])
    if row.get("capabilityLevel") not in LEVEL:
        raise ContractViolation("CAPABILITY_LEVEL_INVALID", [f"$.channelAssessments[{row.get('channelId','?')}].capabilityLevel: unsupported"])
    expected = _digest_without(row, "assessmentDigest")
    if row.get("assessmentDigest") != expected:
        raise ContractViolation("CAPABILITY_ASSESSMENT_TAMPERED", [f"$.channelAssessments[{row.get('channelId','?')}].assessmentDigest: mismatch"])
    level = str(row.get("capabilityLevel"))
    if kind == "MUTATION":
        if level == "ENFORCED" and not all(bool(row.get(k)) for k in ("canPrevent", "canAttribute", "canBindReceipt", "canBlockReplay")):
            raise ContractViolation("CAPABILITY_DECLARATION_INVALID", [f"$.channelAssessments[{row.get('channelId','?')}]: ENFORCED mutation is missing required guarantees"])
        if level == "DETECT_ONLY" and (not bool(row.get("canDetect")) or not bool(row.get("canAttribute")) or bool(row.get("canPrevent"))):
            raise ContractViolation("CAPABILITY_DECLARATION_INVALID", [f"$.channelAssessments[{row.get('channelId','?')}]: DETECT_ONLY mutation is inconsistent"])
    elif kind == "OBSERVATION":
        if level in {"DETECT_ONLY", "ENFORCED"} and not bool(row.get("canObserve")):
            raise ContractViolation("CAPABILITY_DECLARATION_INVALID", [f"$.channelAssessments[{row.get('channelId','?')}]: observable capability is required"])
    elif kind == "IDENTITY":
        if level in {"DETECT_ONLY", "ENFORCED"} and not str(row.get("authoritativeSource") or ""):
            raise ContractViolation("CAPABILITY_DECLARATION_INVALID", [f"$.channelAssessments[{row.get('channelId','?')}]: identity source is required"])
    elif kind == "TELEMETRY":
        if row.get("quality") not in {"AUTHORITATIVE", "ESTIMATED", "UNKNOWN"}:
            raise ContractViolation("CAPABILITY_DECLARATION_INVALID", [f"$.channelAssessments[{row.get('channelId','?')}].quality: invalid"])
    elif kind == "CONTEXT_CONTROL":
        if level == "ENFORCED" and not bool(row.get("canRestrict")):
            raise ContractViolation("CAPABILITY_DECLARATION_INVALID", [f"$.channelAssessments[{row.get('channelId','?')}]: ENFORCED context control must restrict"])
    elif kind == "EXECUTION_CONTROL":
        if level == "ENFORCED" and not bool(row.get("canBlock")):
            raise ContractViolation("CAPABILITY_DECLARATION_INVALID", [f"$.channelAssessments[{row.get('channelId','?')}]: ENFORCED execution control must block"])
    elif kind == "PERSISTENCE":
        if level in {"DETECT_ONLY", "ENFORCED"} and not (bool(row.get("canPersist")) and bool(row.get("canReadBack"))):
            raise ContractViolation("CAPABILITY_DECLARATION_INVALID", [f"$.channelAssessments[{row.get('channelId','?')}]: persistence capability is incomplete"])


@dataclass(frozen=True, slots=True)
class TrustedCapabilitySnapshot:
    """Process-local binding of a schema-valid Host capability snapshot."""

    snapshot_digest: str
    authoritative: bool
    _payload_json: str = field(repr=False, compare=False)
    _authority: object = field(repr=False, compare=False)

    def to_dict(self) -> dict[str, Any]:
        return json.loads(self._payload_json)

    def __reduce__(self):  # pragma: no cover - defensive
        raise TypeError("TrustedCapabilitySnapshot is process-local")


def verify_capability_snapshot(
    snapshot: Mapping[str, Any],
    *,
    verifier: Callable[[Mapping[str, Any]], bool] | None = None,
    now: datetime | None = None,
) -> TrustedCapabilitySnapshot:
    """Validate a Host snapshot without allowing Runtime to self-sign it.

    ``LOCAL_DIGEST_ONLY`` snapshots can support DETECT_ONLY reasoning but are not
    authoritative enough to preserve an ENFORCED level. Signed/opaque snapshots
    require an external Host verifier callable.
    """

    payload = dict(snapshot)
    try:
        validate_instance(payload, _schema("host-capability-snapshot-v1.1.schema.json"), base_dir=Path(__file__).with_name("schemas"))
    except SchemaValidationError as error:
        raise ContractViolation("HOST_CAPABILITY_SCHEMA_INVALID", [f"$: {error}"]) from error
    if _is_expired(payload.get("validUntil"), now):
        raise ContractViolation("HOST_CAPABILITY_SNAPSHOT_EXPIRED", ["$.validUntil: snapshot expired"])
    rows = payload.get("channelAssessments", [])
    seen: set[str] = set()
    for row in rows:
        channel = str(row.get("channelId"))
        if channel in seen:
            raise ContractViolation("HOST_CAPABILITY_DUPLICATE_CHANNEL", [f"$.channelAssessments: duplicate {channel}"])
        seen.add(channel)
        _validate_assessment(row)
        if _is_expired(row.get("validUntil"), now):
            raise ContractViolation("HOST_CAPABILITY_CHANNEL_EXPIRED", [f"$.channelAssessments[{channel}].validUntil: channel assessment expired"])
    expected = _digest_without(payload, "snapshotDigest", "integrityTag")
    if payload.get("snapshotDigest") != expected:
        raise ContractViolation("HOST_CAPABILITY_SNAPSHOT_TAMPERED", ["$.snapshotDigest: mismatch"])
    mechanism = payload.get("integrityMechanism")
    authoritative = False
    if mechanism in {"HOST_SIGNATURE", "HMAC_SHA256", "OPAQUE_HOST_ATTESTATION"}:
        if not callable(verifier) or verifier(payload) is not True:
            raise ContractViolation("HOST_CAPABILITY_ATTESTATION_INVALID", ["$: Host attestation could not be verified"])
        authoritative = True
    elif mechanism != "LOCAL_DIGEST_ONLY":
        raise ContractViolation("HOST_CAPABILITY_ATTESTATION_INVALID", ["$.integrityMechanism: unsupported"])
    return TrustedCapabilitySnapshot(
        snapshot_digest=str(payload["snapshotDigest"]),
        authoritative=authoritative,
        _payload_json=canonical_json(payload),
        _authority=_SNAPSHOT_AUTHORITY,
    )


def require_capability_snapshot(value: TrustedCapabilitySnapshot) -> TrustedCapabilitySnapshot:
    if not isinstance(value, TrustedCapabilitySnapshot) or value._authority is not _SNAPSHOT_AUTHORITY:
        raise ContractViolation("TRUSTED_CAPABILITY_SNAPSHOT_REQUIRED", ["$: verified Host capability snapshot required"])
    return value


def _effective_level(row: Mapping[str, Any], *, authoritative_snapshot: bool) -> str:
    level = str(row.get("capabilityLevel", "UNKNOWN"))
    if level == "ENFORCED" and not authoritative_snapshot:
        return "DETECT_ONLY"
    return level


def assess_required_channels(
    requirements: Sequence[Mapping[str, Any]],
    snapshot: TrustedCapabilitySnapshot,
) -> dict[str, Any]:
    trusted = require_capability_snapshot(snapshot)
    payload = trusted.to_dict()
    rows = {str(row["channelId"]): row for row in payload.get("channelAssessments", [])}
    if not requirements:
        raise ContractViolation("REQUIRED_CHANNELS_EMPTY", ["$: at least one required channel is required"])
    unmet: list[dict[str, Any]] = []
    weakest = "ENFORCED"
    dispositions: list[str] = []
    for req in requirements:
        channel = str(req.get("channelId") or "")
        required = str(req.get("minimumLevel") or "UNKNOWN")
        purpose = str(req.get("purpose") or "")
        if required not in LEVEL or purpose not in PURPOSE_DISPOSITION or not channel:
            raise ContractViolation("REQUIRED_CHANNEL_INVALID", ["$: malformed required channel"])
        row = rows.get(channel)
        actual = "UNKNOWN" if row is None else _effective_level(row, authoritative_snapshot=trusted.authoritative)
        if LEVEL[actual] < LEVEL[weakest]:
            weakest = actual
        if LEVEL[actual] < LEVEL[required]:
            unmet.append({"channelId": channel, "actual": actual, "required": required, "purpose": purpose})
            dispositions.append(PURPOSE_DISPOSITION[purpose])
    if not unmet:
        return {"status": "SATISFIED", "weakest": weakest, "unmet": [], "disposition": "ALLOW", "snapshotDigest": trusted.snapshot_digest}
    disposition = "BLOCK" if "BLOCK" in dispositions else "NOT_MEASURED" if "NOT_MEASURED" in dispositions else "ADVISORY"
    return {"status": "INSUFFICIENT", "weakest": weakest, "unmet": unmet, "disposition": disposition, "snapshotDigest": trusted.snapshot_digest}


def resolve_mvhc(requirement_set: Mapping[str, Any], snapshot: TrustedCapabilitySnapshot) -> dict[str, Any]:
    try:
        validate_instance(dict(requirement_set), _schema("mvhc-requirement-set-v1.schema.json"), base_dir=Path(__file__).with_name("schemas"))
    except SchemaValidationError as error:
        raise ContractViolation("MVHC_SCHEMA_INVALID", [f"$: {error}"]) from error
    result = assess_required_channels(requirement_set["requirements"], snapshot)
    if result["status"] == "SATISFIED":
        mode = "ENFORCED" if result["weakest"] == "ENFORCED" and snapshot.authoritative else "DETECT_ONLY"
    elif result["disposition"] == "BLOCK":
        mode = "UNSUPPORTED"
    else:
        mode = "ADVISORY"
    return {**result, "trustMode": mode}


__all__ = [
    "LEVEL", "PURPOSE_DISPOSITION", "TrustedCapabilitySnapshot", "verify_capability_snapshot",
    "require_capability_snapshot", "assess_required_channels", "resolve_mvhc",
]
