"""Deterministic 4.2.3 claim evaluator with V3 Host-receipt binding."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Sequence

from .contracts import ContractViolation, digest_json
from .phase1_capabilities import TrustedCapabilitySnapshot, assess_required_channels, require_capability_snapshot
from .phase1_evidence import TrustedHostObservation, evidence_can_support_verified, evidence_payloads
from .phase1_host_apply import (
    TrustedHostWriteReceiptV2,
    TrustedHostWriteReceiptV3,
    receipt_v3_current_state_matches,
    require_host_write_receipt_v2,
    require_host_write_receipt_v3,
)
from .release_info import KERNEL_VERSION, PACKAGE_VERSION, RECEIPT_PROTOCOL_VERSION

CLAIM_KERNEL_VERSION = KERNEL_VERSION


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _time(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def _v3_receipt_reasons(
    receipt: TrustedHostWriteReceiptV3,
    *,
    claim_contract: Mapping[str, Any],
    baseline_digest: str | None,
    run_id: str | None,
    session_id: str | None,
    activation_id: str | None,
    target_digest: str | None,
    change_set_digest: str | None,
    package_tree_digest: str | None,
    verification_policy_digest: str | None,
    evaluated_at: str,
    minimum_receipt_epoch: int,
) -> list[str]:
    value = require_host_write_receipt_v3(receipt)
    reasons: list[str] = []
    required_expected = {
        "runId": run_id,
        "sessionId": session_id,
        "activationId": activation_id,
        "targetDigest": target_digest,
        "changeSetDigest": change_set_digest,
        "packageTreeDigest": package_tree_digest,
        "verificationPolicyDigest": verification_policy_digest,
    }
    if any(not isinstance(v, str) or not v for v in required_expected.values()) or not baseline_digest:
        return ["CLAIM_WRITE_BINDING_INCOMPLETE"]
    if value.task_id != str(claim_contract["taskId"]): reasons.append("HOST_WRITE_RECEIPT_TASK_MISMATCH")
    if value.run_id != run_id: reasons.append("HOST_WRITE_RECEIPT_RUN_MISMATCH")
    if value.session_id != session_id: reasons.append("HOST_WRITE_RECEIPT_SESSION_MISMATCH")
    if value.activation_id != activation_id: reasons.append("HOST_WRITE_RECEIPT_ACTIVATION_MISMATCH")
    if value.baseline_digest != baseline_digest: reasons.append("HOST_WRITE_RECEIPT_BASELINE_MISMATCH")
    if value.target_digest != target_digest: reasons.append("HOST_WRITE_RECEIPT_TARGET_MISMATCH")
    if value.change_set_digest != change_set_digest: reasons.append("HOST_WRITE_RECEIPT_CHANGESET_MISMATCH")
    if value.package_tree_digest != package_tree_digest: reasons.append("HOST_WRITE_RECEIPT_PACKAGE_MISMATCH")
    if value.verification_policy_digest != verification_policy_digest: reasons.append("HOST_WRITE_RECEIPT_POLICY_MISMATCH")
    if value.freshness_epoch < minimum_receipt_epoch: reasons.append("HOST_WRITE_RECEIPT_EPOCH_STALE")
    payload = value.to_dict()
    if payload.get("pluginVersion") != PACKAGE_VERSION or payload.get("kernelVersion") != KERNEL_VERSION or payload.get("receiptProtocolVersion") != RECEIPT_PROTOCOL_VERSION:
        reasons.append("HOST_WRITE_RECEIPT_VERSION_MISMATCH")
    try:
        when = _time(evaluated_at)
        if _time(value.issued_at) > when or _time(value.expires_at) <= when:
            reasons.append("HOST_WRITE_RECEIPT_EXPIRED")
    except (TypeError, ValueError):
        reasons.append("HOST_WRITE_RECEIPT_TIME_INVALID")
    if not receipt_v3_current_state_matches(value):
        reasons.append("HOST_WRITE_RECEIPT_POST_APPLY_DRIFT")
    return reasons


def evaluate_claim(
    claim_contract: Mapping[str, Any],
    *,
    capability_snapshot: TrustedCapabilitySnapshot,
    evidence: Sequence[Mapping[str, Any] | TrustedHostObservation],
    predicates: Sequence[bool] | None,
    receipts: Sequence[TrustedHostWriteReceiptV3 | TrustedHostWriteReceiptV2] = (),
    requires_write_receipt: bool = False,
    baseline_digest: str | None = None,
    evaluated_at: str | None = None,
    minimum_state_epoch: int = 0,
    run_id: str | None = None,
    session_id: str | None = None,
    activation_id: str | None = None,
    target_digest: str | None = None,
    change_set_digest: str | None = None,
    package_tree_digest: str | None = None,
    verification_policy_digest: str | None = None,
    minimum_receipt_epoch: int = 1,
    consume_receipt: Callable[[str, str, str], bool] | None = None,
) -> dict[str, Any]:
    """Evaluate one claim without using model confidence or natural-language self-report.

    A write-backed 4.2.3 VERIFIED claim requires exactly one trusted V3 receipt,
    exact task/run/session/activation/baseline/target/package/policy binding,
    fresh current file state, and Host-backed one-time receipt consumption.
    """
    required_fields = {"claimId", "taskId", "claimRole", "statement", "verificationContractId", "baselineId", "environmentFingerprint", "requiredEvidenceTypes", "requiredChannels"}
    missing = sorted(required_fields - set(claim_contract))
    if missing:
        raise ContractViolation("CLAIM_CONTRACT_INVALID", [f"$.{key}: required" for key in missing])
    snapshot = require_capability_snapshot(capability_snapshot)
    channel_result = assess_required_channels(claim_contract["requiredChannels"], snapshot)
    rows = evidence_payloads(evidence)
    status = "EVALUATING"
    reasons: list[str] = []
    freshness = "FRESH"
    evaluated = evaluated_at or _now()

    v3_receipts: list[TrustedHostWriteReceiptV3] = []
    legacy_receipts: list[TrustedHostWriteReceiptV2] = []
    for item in receipts:
        if isinstance(item, TrustedHostWriteReceiptV3):
            v3_receipts.append(require_host_write_receipt_v3(item))
        elif isinstance(item, TrustedHostWriteReceiptV2):
            legacy_receipts.append(require_host_write_receipt_v2(item))
        else:
            raise ContractViolation("TRUSTED_HOST_WRITE_RECEIPT_V3_REQUIRED", ["$: receipt is not a trusted V3/V2 receipt"])

    if channel_result["disposition"] == "BLOCK":
        status = "BLOCKED"; reasons.append("HOST_CAPABILITY_INSUFFICIENT")
    elif channel_result["disposition"] == "NOT_MEASURED":
        status = "NOT_MEASURED"; reasons.append("MEASUREMENT_CAPABILITY_INSUFFICIENT")
    elif any(row.get("kind") == "STALE" for row in rows):
        status = "INVALIDATED"; freshness = "STALE"; reasons.append("EVIDENCE_STALE")
    else:
        supported, evidence_reasons = evidence_can_support_verified(
            evidence, task_id=str(claim_contract["taskId"]), baseline_digest=baseline_digest,
            environment_fingerprint=str(claim_contract["environmentFingerprint"]),
            required_subtypes=list(claim_contract["requiredEvidenceTypes"]), minimum_state_epoch=minimum_state_epoch,
        )
        if not supported:
            if "EVIDENCE_STATE_EPOCH_STALE" in evidence_reasons or "EVIDENCE_STALE" in evidence_reasons:
                status = "INVALIDATED"; freshness = "STALE"
            elif any(token in r for r in evidence_reasons for token in ("MISMATCH", "FRESHNESS_UNKNOWN", "STATE_EPOCH_UNKNOWN")):
                status = "BLOCKED"
            else:
                status = "NOT_MEASURED"
            reasons.extend(evidence_reasons)
        elif requires_write_receipt:
            if legacy_receipts:
                status = "BLOCKED"; reasons.append("LEGACY_RECEIPT_NOT_SUFFICIENT_FOR_VERIFIED")
            elif len(v3_receipts) != 1:
                status = "BLOCKED"; reasons.append("HOST_WRITE_RECEIPT_REQUIRED" if not v3_receipts else "HOST_WRITE_RECEIPT_CARDINALITY_INVALID")
            else:
                reasons.extend(_v3_receipt_reasons(
                    v3_receipts[0], claim_contract=claim_contract, baseline_digest=baseline_digest, run_id=run_id,
                    session_id=session_id, activation_id=activation_id, target_digest=target_digest,
                    change_set_digest=change_set_digest, package_tree_digest=package_tree_digest,
                    verification_policy_digest=verification_policy_digest, evaluated_at=evaluated,
                    minimum_receipt_epoch=minimum_receipt_epoch,
                ))
                if reasons:
                    status = "BLOCKED"
                elif predicates is None or len(predicates) == 0:
                    status = "NOT_MEASURED"; reasons.append("PREDICATE_MEASUREMENT_MISSING")
                elif any(value is not True for value in predicates):
                    status = "NOT_VERIFIED"; reasons.append("PREDICATE_FAILED")
                elif not callable(consume_receipt):
                    status = "BLOCKED"; reasons.append("HOST_RECEIPT_CONSUMPTION_REQUIRED")
                elif consume_receipt(v3_receipts[0].receipt_digest, v3_receipts[0].nonce, str(claim_contract["claimId"])) is not True:
                    status = "BLOCKED"; reasons.append("HOST_WRITE_RECEIPT_REPLAYED")
                else:
                    status = "VERIFIED"
        elif predicates is None or len(predicates) == 0:
            status = "NOT_MEASURED"; reasons.append("PREDICATE_MEASUREMENT_MISSING")
        elif any(value is not True for value in predicates):
            status = "NOT_VERIFIED"; reasons.append("PREDICATE_FAILED")
        else:
            status = "VERIFIED"

    trusted_receipts = [*v3_receipts, *legacy_receipts]
    receipt_digests = [item.receipt_digest for item in trusted_receipts]
    evidence_ids = [str(row["evidenceId"]) for row in rows]
    evaluation_input = {
        "claimContract": dict(claim_contract), "capabilitySnapshotDigest": snapshot.snapshot_digest,
        "evidenceDigests": [digest_json(row) for row in rows], "receiptDigests": receipt_digests,
        "predicates": list(predicates or []), "minimumStateEpoch": minimum_state_epoch,
        "writeBinding": {"runId": run_id, "sessionId": session_id, "activationId": activation_id, "targetDigest": target_digest, "changeSetDigest": change_set_digest, "packageTreeDigest": package_tree_digest, "verificationPolicyDigest": verification_policy_digest, "minimumReceiptEpoch": minimum_receipt_epoch},
    }
    value = {
        "schemaVersion": "2", "claimId": str(claim_contract["claimId"]), "taskId": str(claim_contract["taskId"]),
        "claimRole": str(claim_contract["claimRole"]), "statement": str(claim_contract["statement"]),
        "verificationContractId": str(claim_contract["verificationContractId"]), "baselineId": str(claim_contract["baselineId"]),
        "environmentFingerprint": str(claim_contract["environmentFingerprint"]), "requiredEvidenceTypes": list(claim_contract["requiredEvidenceTypes"]),
        "evidenceIds": evidence_ids, "requiredChannels": [dict(item) for item in claim_contract["requiredChannels"]],
        "capabilitySnapshotDigest": snapshot.snapshot_digest, "receiptDigests": receipt_digests, "status": status,
        "reasonCodes": sorted(dict.fromkeys(reasons)), "freshnessSummary": freshness, "evaluatedAt": evaluated,
        "kernelVersion": CLAIM_KERNEL_VERSION, "evaluationInputDigest": digest_json(evaluation_input),
    }
    value["claimDigest"] = digest_json(value)
    return value


__all__ = ["CLAIM_KERNEL_VERSION", "evaluate_claim"]
