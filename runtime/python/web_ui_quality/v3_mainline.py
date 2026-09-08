"""Public-run V3 binding helpers for the 4.2.3 trust closure.

The helpers never write the target project.  They bind a Host-proposed patch
candidate to the sealed run/source baseline and persist only an apply contract
under the WUQ artifact directory.  Host authority remains external.
"""
from __future__ import annotations

import json
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from .contracts import ContractViolation, digest_json
from .phase1_host_apply import build_target_digest
from .release_info import PACKAGE_VERSION, KERNEL_VERSION, RECEIPT_PROTOCOL_VERSION


def _release_manifest() -> dict[str, Any]:
    root = Path(__file__).resolve().parents[3]
    path = root / "RELEASE-MANIFEST.json"
    if not path.is_file():
        raise ContractViolation("PACKAGE_TREE_IDENTITY_UNAVAILABLE", ["$: RELEASE-MANIFEST.json is required for a public V3 Host apply binding"])
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ContractViolation("PACKAGE_TREE_IDENTITY_INVALID", ["$: release manifest is unreadable"]) from error
    digest = str(value.get("packageTreeDigest") or "")
    if value.get("packageVersion") != PACKAGE_VERSION or len(digest) != 64:
        raise ContractViolation("PACKAGE_TREE_IDENTITY_INVALID", ["$: release manifest identity does not match the running package"])
    return value


def _candidate_entries(candidate: Mapping[str, Any], *, source_scope: Sequence[str], scope_baseline: Mapping[str, Any]) -> list[dict[str, str]]:
    rows = candidate.get("entries")
    if not isinstance(rows, list) or not rows:
        raise ContractViolation("HOST_PATCH_CANDIDATE_INVALID", ["$.entries: non-empty array required"])
    baseline = {str(row.get("path")): str(row.get("sha256")) for row in list(scope_baseline.get("files") or []) if isinstance(row, Mapping)}
    expected_scope = sorted(dict.fromkeys(str(x).replace("\\", "/") for x in source_scope))
    normalized: list[dict[str, str]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise ContractViolation("HOST_PATCH_CANDIDATE_INVALID", ["$.entries: object entries required"])
        rel = str(row.get("canonicalPath") or "").replace("\\", "/")
        op = str(row.get("operation") or "EDIT").upper()
        before = str(row.get("expectedBeforeHash") or "")
        after = str(row.get("intendedAfterHash") or "")
        if rel not in expected_scope or op != "EDIT" or len(before) != 64 or len(after) != 64 or before == after:
            raise ContractViolation("HOST_PATCH_CANDIDATE_SCOPE_MISMATCH", [f"$.entries[{rel or '?'}]: exact EDIT scope and distinct sha256 hashes required"])
        if baseline.get(rel) != before:
            raise ContractViolation("HOST_PATCH_CANDIDATE_BASELINE_MISMATCH", [f"$.entries[{rel}].expectedBeforeHash: does not match sealed scope baseline"])
        normalized.append({"canonicalPath": rel, "operation": "EDIT", "expectedBeforeHash": before, "intendedAfterHash": after})
    normalized.sort(key=lambda row: row["canonicalPath"])
    if [row["canonicalPath"] for row in normalized] != expected_scope:
        raise ContractViolation("HOST_PATCH_CANDIDATE_SCOPE_MISMATCH", ["$.entries: candidate target set must exactly match the confirmed source scope"])
    return normalized


def build_public_v3_apply_binding(
    *,
    candidate: Mapping[str, Any],
    run_id: str,
    task_id: str,
    session_id: str,
    baseline_digest: str,
    plan_digest: str,
    source_scope: Sequence[str],
    exclusions: Sequence[str],
    scope_baseline: Mapping[str, Any],
    change_budget: Mapping[str, Any] | None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build a persisted V3 apply binding from a pre-write Host patch candidate."""
    if str(candidate.get("runId") or "") != run_id or str(candidate.get("taskId") or "") != task_id or str(candidate.get("sessionId") or "") != session_id:
        raise ContractViolation("HOST_PATCH_CANDIDATE_RUN_MISMATCH", ["$: patch candidate must bind the current run/task/session"])
    host_identity = str(candidate.get("hostIdentity") or "").strip()
    attestation_identity = str(candidate.get("attestationIdentity") or "").strip()
    if not host_identity or not attestation_identity:
        raise ContractViolation("HOST_PATCH_CANDIDATE_IDENTITY_MISSING", ["$: hostIdentity and attestationIdentity are required before a V3 apply binding can be prepared"])
    entries = _candidate_entries(candidate, source_scope=source_scope, scope_baseline=scope_baseline)
    max_files = int((change_budget or {}).get("maxFiles") or len(entries))
    if len(entries) > max_files:
        raise ContractViolation("CHANGE_BUDGET_EXCEEDED", [f"$.entries: {len(entries)} files exceeds maxFiles={max_files}"])
    target_digest = build_target_digest(entries)
    change_set_digest = digest_json({"entries": entries, "planDigest": plan_digest})
    release = _release_manifest()
    issued = now or datetime.now(timezone.utc)
    if issued.tzinfo is None:
        issued = issued.replace(tzinfo=timezone.utc)
    expires = issued + timedelta(minutes=30)
    activation_id = "activation-" + digest_json({"runId": run_id, "sessionId": session_id, "planDigest": plan_digest})[:24]
    nonce = secrets.token_hex(16)
    policy = {
        "policy": "WUQ_PUBLIC_REPAIR_V3",
        "packageVersion": PACKAGE_VERSION,
        "receiptProtocolVersion": RECEIPT_PROTOCOL_VERSION,
        "sourceScope": list(source_scope),
        "exclusions": list(exclusions),
        "changeBudget": dict(change_budget or {}),
        "legacyReceiptCanVerify": False,
    }
    verification_policy_digest = digest_json(policy)
    authorization = {
        "kind": "HOST_APPLY_BINDING_ONLY",
        "writeAuthorized": False,
        "hostApprovalRequired": True,
        "runId": run_id,
        "taskId": task_id,
        "sessionId": session_id,
        "activationId": activation_id,
        "baselineDigest": baseline_digest,
        "targetDigest": target_digest,
        "changeSetDigest": change_set_digest,
        "planDigest": plan_digest,
        "nonce": nonce,
        "expiresAt": expires.isoformat(),
    }
    authorization_ticket_digest = digest_json(authorization)
    value = {
        "schemaVersion": "3-mainline-binding",
        "receiptProtocolVersion": RECEIPT_PROTOCOL_VERSION,
        "pluginVersion": PACKAGE_VERSION,
        "kernelVersion": KERNEL_VERSION,
        "packageTreeDigest": release["packageTreeDigest"],
        "activationId": activation_id,
        "runId": run_id,
        "sessionId": session_id,
        "taskId": task_id,
        "nonce": nonce,
        "issuedAt": issued.isoformat(),
        "expiresAt": expires.isoformat(),
        "freshnessEpoch": 1,
        "baselineDigest": baseline_digest,
        "targetDigest": target_digest,
        "changeSetDigest": change_set_digest,
        "verificationPolicyDigest": verification_policy_digest,
        "hostIdentity": host_identity,
        "attestationIdentity": attestation_identity,
        "authorizationTicketDigest": authorization_ticket_digest,
        "entries": entries,
        "policy": policy,
        "writeAuthorized": False,
        "hostApprovalRequired": True,
        "hostIntegrityRequirement": "HMAC_SHA256_FROM_EXTERNAL_HOST_KEY",
        "claimBoundary": "This binding is a pre-write target/change-set contract. It grants no Runtime write authority; only a Host with the external attestation key may apply and attest the change.",
    }
    value["bindingDigest"] = digest_json(value)
    return value


def persist_public_v3_apply_binding(run_dir: str | Path, binding: Mapping[str, Any]) -> Path:
    path = Path(run_dir).resolve() / "report" / "host-apply-binding-v3.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if existing.get("bindingDigest") != binding.get("bindingDigest"):
            raise ContractViolation("HOST_APPLY_BINDING_IMMUTABLE", ["$: a different V3 apply binding already exists for this run"])
        return path
    path.write_text(json.dumps(dict(binding), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def load_public_v3_apply_binding(run_dir: str | Path) -> dict[str, Any]:
    path = Path(run_dir).resolve() / "report" / "host-apply-binding-v3.json"
    if not path.is_file():
        raise ContractViolation("HOST_APPLY_BINDING_V3_REQUIRED", ["$: prepare a V3 Host apply binding from the pre-write patch candidate before After verification"])
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ContractViolation("HOST_APPLY_BINDING_V3_INVALID", ["$: persisted V3 apply binding is unreadable"]) from error
    digest = value.pop("bindingDigest", None)
    actual = digest_json(value)
    value["bindingDigest"] = digest
    if digest != actual:
        raise ContractViolation("HOST_APPLY_BINDING_V3_TAMPERED", ["$.bindingDigest: mismatch"])
    return value


def build_v3_revert_plan(receipt: Mapping[str, Any]) -> dict[str, Any]:
    files = [
        {"path": str(row.get("canonicalPath")), "expectedCurrentSha256": str(row.get("actualAfterHash")), "targetBeforeSha256": str(row.get("actualBeforeHash"))}
        for row in list(receipt.get("entries") or []) if isinstance(row, Mapping)
    ]
    body = {
        "schemaVersion": "2", "kind": "REPAIR_SCOPE_REVERT", "runId": receipt.get("runId"), "taskId": receipt.get("taskId"),
        "sessionId": receipt.get("sessionId"), "scope": "REPAIR_SCOPE", "files": files, "hostExecutionRequired": True,
        "runtimeMayWrite": False, "claimBoundary": "Revert is bounded to exact V3 verified entries and still requires Host execution; Runtime stores no prior file bytes.",
    }
    body["planDigest"] = digest_json(body)
    return body


__all__ = ["build_public_v3_apply_binding", "persist_public_v3_apply_binding", "load_public_v3_apply_binding", "build_v3_revert_plan"]
