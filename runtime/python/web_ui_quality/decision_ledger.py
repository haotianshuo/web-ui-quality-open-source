"""Append-only Decision / Trade-off Ledger with supersession history."""
from __future__ import annotations

from typing import Any, Iterable, Mapping
import hmac
import uuid

from .contracts import ContractViolation, digest_json
from .governance_artifacts import now_iso, read_json, write_json_atomic
from .experience_run import _mac, _read_config

_ARTIFACT = "governance/decision-ledger.json"
_STATUSES = {"PROPOSED", "SELECTED", "VERIFICATION_PENDING", "VERIFIED", "REJECTED", "SUPERSEDED"}


def _load(run_dir, create=False) -> dict[str, Any]:
    try:
        value = read_json(run_dir, _ARTIFACT, code="DECISION_LEDGER_MISSING")
    except ContractViolation:
        if not create:
            raise
        body = {"schemaVersion": "1", "entries": [], "updatedAt": now_iso()}
        digest = digest_json(body)
        _, key = _read_config(run_dir)
        value = {**body, "ledgerDigest": digest, "integrityMac": _mac(key, {"artifact": "decision-ledger", "ledgerDigest": digest})}
        write_json_atomic(run_dir, _ARTIFACT, value, replace=False)
        return value
    body = {k: v for k, v in value.items() if k not in {"ledgerDigest", "integrityMac"}}
    if value.get("ledgerDigest") != digest_json(body):
        raise ContractViolation("DECISION_LEDGER_TAMPERED", ["$.ledgerDigest: mismatch"])
    _, key = _read_config(run_dir)
    expected_mac = _mac(key, {"artifact": "decision-ledger", "ledgerDigest": value.get("ledgerDigest")})
    if not hmac.compare_digest(str(value.get("integrityMac") or ""), expected_mac):
        raise ContractViolation("DECISION_LEDGER_TAMPERED", ["$.integrityMac: trusted-key verification failed"])
    if not isinstance(value.get("entries"), list):
        raise ContractViolation("DECISION_LEDGER_MALFORMED", ["$.entries: array required"])
    return value


def _save(run_dir, ledger: Mapping[str, Any]) -> dict[str, Any]:
    body = {k: v for k, v in dict(ledger).items() if k not in {"ledgerDigest", "integrityMac"}}
    body["updatedAt"] = now_iso()
    digest = digest_json(body)
    _, key = _read_config(run_dir)
    sealed = {**body, "ledgerDigest": digest, "integrityMac": _mac(key, {"artifact": "decision-ledger", "ledgerDigest": digest})}
    write_json_atomic(run_dir, _ARTIFACT, sealed)
    return sealed


def create_decision(run_dir, *, issue: str, evidence: Iterable[Mapping[str, Any] | str], constraints: Iterable[str], options: Iterable[Mapping[str, Any]], selected_option: str, rationale: str, rejected_options: Iterable[str] = (), expected_outcome: Iterable[str] = (), risks: Iterable[str] = (), risk_triggers: Iterable[str] = (), verification_plan: Iterable[str] = (), related_findings: Iterable[str] = (), related_patches: Iterable[str] = (), status: str = "SELECTED", decision_id: str | None = None, supersedes: str | None = None) -> dict[str, Any]:
    if status not in _STATUSES:
        raise ContractViolation("DECISION_STATUS_INVALID", [f"$: {status}"])
    ledger = _load(run_dir, create=True)
    did = decision_id or f"dec-{uuid.uuid4().hex[:12]}"
    if any(e.get("decisionId") == did for e in ledger["entries"]):
        raise ContractViolation("DECISION_ID_EXISTS", [f"$: {did}"])
    item = {
        "decisionId": did, "issue": issue, "evidence": list(evidence), "constraints": list(constraints),
        "options": list(options), "tradeoffs": [o.get("tradeoffs") for o in options if isinstance(o, Mapping) and o.get("tradeoffs")],
        "selectedOption": selected_option, "rationale": rationale, "rejectedOptions": list(rejected_options),
        "expectedOutcome": list(expected_outcome), "risks": list(risks), "riskTriggers": list(risk_triggers),
        "verificationPlan": list(verification_plan), "status": status, "relatedFindings": list(related_findings),
        "relatedPatches": list(related_patches), "supersedes": supersedes, "supersededBy": None, "createdAt": now_iso(),
    }
    ledger["entries"].append(item)
    _save(run_dir, ledger)
    return item


def supersede_decision(run_dir, decision_id: str, **replacement) -> dict[str, Any]:
    ledger = _load(run_dir)
    idx = next((i for i, e in enumerate(ledger["entries"]) if e.get("decisionId") == decision_id), None)
    if idx is None:
        raise ContractViolation("DECISION_NOT_FOUND", [f"$: {decision_id}"])
    old = ledger["entries"][idx]
    if old.get("supersededBy"):
        raise ContractViolation("DECISION_ALREADY_SUPERSEDED", [f"$: {decision_id}"])
    new_id = replacement.pop("decision_id", None) or f"dec-{uuid.uuid4().hex[:12]}"
    new_item = {
        **old, **replacement, "decisionId": new_id, "supersedes": decision_id, "supersededBy": None,
        "createdAt": now_iso(), "status": replacement.get("status", "SELECTED"),
    }
    ledger["entries"][idx] = {**old, "status": "SUPERSEDED", "supersededBy": new_id}
    ledger["entries"].append(new_item)
    _save(run_dir, ledger)
    return new_item


def update_verification_status(run_dir, decision_id: str, status: str) -> dict[str, Any]:
    if status not in {"VERIFICATION_PENDING", "VERIFIED", "REJECTED"}:
        raise ContractViolation("DECISION_STATUS_INVALID", [f"$: {status}"])
    ledger = _load(run_dir)
    idx = next((i for i, e in enumerate(ledger["entries"]) if e.get("decisionId") == decision_id), None)
    if idx is None:
        raise ContractViolation("DECISION_NOT_FOUND", [f"$: {decision_id}"])
    if ledger["entries"][idx].get("supersededBy"):
        raise ContractViolation("DECISION_SUPERSEDED_IMMUTABLE", [f"$: {decision_id}"])
    ledger["entries"][idx] = {**ledger["entries"][idx], "status": status, "verificationUpdatedAt": now_iso()}
    _save(run_dir, ledger)
    return ledger["entries"][idx]


def load_decision_ledger(run_dir) -> dict[str, Any]:
    return _load(run_dir)
