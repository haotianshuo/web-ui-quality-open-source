"""TaskResult v2.1 aggregation with status/reason/resource separation."""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from .contracts import ContractViolation, digest_json

KERNEL_VERSION = "4.1.0-alpha.6-phase1-task-kernel"
_ALLOWED_TERMINATION = {
    "NONE", "DEADLOCK_DETECTED", "TOKEN_LIMIT_REACHED", "COST_LIMIT_REACHED", "TIMEOUT", "TOOL_UNAVAILABLE",
    "RECOVERY_REQUIRED", "AUTHORITY_REQUIRED", "HOST_CAPABILITY_INSUFFICIENT", "LEDGER_RECOVERY_REQUIRED",
    "INVALID_TASK_CONTRACT", "AGGREGATION_INCOMPLETE", "REQUIRED_CLAIM_INVALIDATED",
}
_ALLOWED_RESOURCE = {"SUFFICIENT", "EXHAUSTED", "UNKNOWN", "MORE_RESOURCE_REQUIRED"}


def aggregate_task_result(
    *,
    task_id: str,
    task_contract_digest: str,
    required_claim_ids: Sequence[str],
    optional_claim_ids: Sequence[str],
    claims: Sequence[Mapping[str, Any]],
    capability_snapshot_digest: str,
    environment_fingerprint: str,
    termination_reason: str = "NONE",
    resource_disposition: str = "SUFFICIENT",
    integrity_ok: bool = True,
    recovery_required: bool = False,
) -> dict[str, Any]:
    """Aggregate required Claim states without allowing success to dilute failure.

    PARTIAL is reserved for unresolved-but-not-failed mixtures. A Required Claim
    that is NOT_VERIFIED or INVALIDATED takes precedence over any sibling that is
    VERIFIED.
    """
    if not required_claim_ids or len(set(required_claim_ids)) != len(required_claim_ids):
        status, termination_reason = "FAILED", "INVALID_TASK_CONTRACT"
    elif termination_reason not in _ALLOWED_TERMINATION or resource_disposition not in _ALLOWED_RESOURCE:
        raise ContractViolation("TASK_RESULT_INPUT_INVALID", ["$: invalid termination/resource state"])
    elif not integrity_ok:
        status, termination_reason = "FAILED", "LEDGER_RECOVERY_REQUIRED"
    elif recovery_required:
        status, termination_reason = "BLOCKED", "RECOVERY_REQUIRED"
    elif termination_reason != "NONE":
        status = "BLOCKED"
    else:
        by_id = {str(row.get("claimId")): row for row in claims}
        if any(cid not in by_id for cid in required_claim_ids):
            status, termination_reason = "FAILED", "AGGREGATION_INCOMPLETE"
        else:
            required = [by_id[cid] for cid in required_claim_ids]
            if any(row.get("taskId") != task_id for row in required):
                status, termination_reason = "FAILED", "INVALID_TASK_CONTRACT"
            elif any(row.get("status") == "BLOCKED" for row in required):
                status, termination_reason = "BLOCKED", "HOST_CAPABILITY_INSUFFICIENT"
            elif any(row.get("status") == "INVALIDATED" for row in required):
                status, termination_reason = "BLOCKED", "REQUIRED_CLAIM_INVALIDATED"
            elif any(row.get("status") == "NOT_VERIFIED" for row in required):
                status = "NOT_VERIFIED"
            elif all(row.get("status") == "VERIFIED" for row in required):
                status = "VERIFIED"
            elif all(row.get("status") == "NOT_MEASURED" for row in required):
                status = "NOT_MEASURED"
            elif any(row.get("status") == "VERIFIED" for row in required):
                # Remaining required claims are unresolved or NOT_MEASURED, not
                # authoritatively failed/invalidated (handled above).
                status = "PARTIAL"
            elif any(row.get("status") == "NOT_MEASURED" for row in required):
                status = "NOT_MEASURED"
            else:
                status, termination_reason = "FAILED", "AGGREGATION_INCOMPLETE"
    reason_codes = [] if termination_reason == "NONE" else [termination_reason]
    value = {
        "schemaVersion": "2.1",
        "taskId": task_id,
        "taskContractDigest": task_contract_digest,
        "requiredClaimIds": list(required_claim_ids),
        "optionalClaimIds": list(optional_claim_ids),
        "claimDigests": sorted({str(row.get("claimDigest")) for row in claims if row.get("claimDigest")}),
        "capabilitySnapshotDigest": capability_snapshot_digest,
        "environmentFingerprint": environment_fingerprint,
        "status": status,
        "terminationReason": termination_reason,
        "resourceDisposition": resource_disposition,
        "reasonCodes": reason_codes,
        "kernelVersion": KERNEL_VERSION,
    }
    value["taskResultDigest"] = digest_json(value)
    return value


__all__ = ["KERNEL_VERSION", "aggregate_task_result"]
