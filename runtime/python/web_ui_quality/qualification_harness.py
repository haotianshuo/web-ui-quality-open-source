"""Small contract boundary for bounded qualification validation.

The harness consumes the frozen oracle class and task contract as data.  It
does not infer a repair workflow from a task label, wording style, or task ID,
and it never upgrades an observed result to the expected claim.
"""
from __future__ import annotations

from typing import Any, Mapping

from .contracts import ContractViolation, digest_json


_MUTATING_ORACLES = frozenset({
    "REPAIRED_VERIFIED",
    "REPAIRED_VERIFIED_SCOPE_PRESERVED",
    "RECOVERED_VERIFIED",
})


def _allowed_writes(task: Mapping[str, Any]) -> list[str]:
    raw = task.get("allowedWrites")
    if raw is None:
        return []
    if not isinstance(raw, (list, tuple)) or any(not isinstance(item, str) or not item.strip() for item in raw):
        raise ContractViolation("QUALIFICATION_TASK_CONTRACT_INVALID", ["$.allowedWrites: expected a list of non-empty paths"])
    return [item.strip().replace("\\", "/") for item in raw]


def expected_execution_contract(task: Mapping[str, Any]) -> dict[str, Any]:
    """Return the frozen execution/claim contract for one validation task."""
    if not isinstance(task, Mapping):
        raise ContractViolation("QUALIFICATION_TASK_CONTRACT_INVALID", ["$: expected a task mapping"])
    oracle_class = str(task.get("oracleClass") or "").strip().upper()
    category = str(task.get("category") or "").strip()
    property_name = str(task.get("property") or "").strip()
    if not oracle_class or not category or not property_name:
        raise ContractViolation(
            "QUALIFICATION_TASK_CONTRACT_INVALID",
            ["$: oracleClass, category, and property are required"],
        )
    allowed = _allowed_writes(task)
    mutating = oracle_class in _MUTATING_ORACLES and bool(allowed)
    basis = {
        "oracleClass": oracle_class,
        "category": category,
        "property": property_name,
        "allowedWrites": allowed,
        "protectedFiles": task.get("protectedFiles"),
    }
    return {
        "schemaVersion": "1",
        "mode": "FIX_AND_VERIFY" if mutating else "CHECK",
        "readOnly": not mutating,
        "expectedClaim": oracle_class,
        "oracleClass": oracle_class,
        "category": category,
        "property": property_name,
        "allowedWrites": allowed,
        "contractDigest": digest_json(basis),
        "claimBoundary": "Execution mode and expected claim come from the frozen oracle/task contract; neither grants write authority or changes an observed result.",
    }


def validate_frozen_task_result(task: Mapping[str, Any], result: Mapping[str, Any]) -> dict[str, Any]:
    """Compare an observed result with the frozen contract without coercion."""
    contract = expected_execution_contract(task)
    observed_result = result if isinstance(result, Mapping) else {}
    task_result = observed_result.get("taskResult") if isinstance(observed_result.get("taskResult"), Mapping) else observed_result
    observed_mode = str(observed_result.get("mode") or "").upper()
    # A validation ledger may carry the independently evaluated oracle claim
    # alongside the product TaskResult.  That explicit claim is authoritative
    # for this contract comparison; the generic TaskResult outcome remains
    # available for separate WUQ gate assertions.
    observed_claim = str(
        observed_result.get("finalClaim")
        or observed_result.get("claim")
        or task_result.get("outcome")
        or "NOT_VERIFIED"
    ).upper()
    mode_match = observed_mode == contract["mode"]
    claim_match = observed_claim == contract["expectedClaim"]
    return {
        "schemaVersion": "1",
        "status": "PASS" if mode_match and claim_match else "NOT_VERIFIED",
        "modeMatch": mode_match,
        "claimMatch": claim_match,
        "expectedMode": contract["mode"],
        "observedMode": observed_mode or None,
        "expectedClaim": contract["expectedClaim"],
        "observedClaim": observed_claim,
        "contractDigest": contract["contractDigest"],
        "claimBoundary": "A mismatch remains NOT_VERIFIED; the validator does not repair, reinterpret, or promote the result.",
    }


__all__ = ["expected_execution_contract", "validate_frozen_task_result"]
