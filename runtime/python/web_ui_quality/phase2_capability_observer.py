"""Phase-2 capability shadow observation.

This module converts facts already produced by the authoritative Fixed Workflow
into mechanical or derived-deterministic signals.  It never mutates execution,
authority, evidence, Claim state, TaskResult, guidance, context, or exploration.

No semantic score is produced.  Signals are retained for later offline validity
analysis only; ``authorityEffect`` and ``adaptiveEffect`` are always ``NONE``.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Mapping, Sequence

from .contracts import digest_json
from .release_info import KERNEL_BASE_VERSION, PACKAGE_VERSION

OBSERVER_VERSION = "4.1.0-alpha.6-capability-shadow-v1"
SIGNAL_SCHEMA_VERSION = "1"
SUCCESS_STATES = {"PASS", "PASS_WITH_WARNINGS", "VERIFIED"}
FAILURE_STATES = {"FAIL", "FAILED", "ERROR"}


def _signal(
    code: str,
    *,
    kind: str,
    polarity: str,
    source: str,
    value: Any,
    capability_eligible: bool,
    reason_code: str,
) -> dict[str, Any]:
    core = {
        "kind": kind,
        "code": code,
        "polarity": polarity,
        "source": source,
        "value": value,
        "capabilityEligible": capability_eligible,
        "reasonCode": reason_code,
        "authorityEffect": "NONE",
        "adaptiveEffect": "NONE",
    }
    return {"signalId": digest_json(core), **core}


def _status(row: Any) -> str:
    if isinstance(row, Mapping):
        return str(row.get("status") or "UNKNOWN").upper()
    return "UNKNOWN"


def _tool_statuses(fixed_result: Mapping[str, Any]) -> list[str]:
    rows = fixed_result.get("projectToolEvidence")
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes, bytearray)):
        return []
    values: list[str] = []
    for row in rows:
        if isinstance(row, Mapping):
            values.append(str(row.get("status") or "UNKNOWN").upper())
    return values


def observe_capability_signals(
    *,
    selected_mode: str,
    intent_route: Mapping[str, Any],
    control_intent: Mapping[str, Any],
    fixed_result: Mapping[str, Any],
) -> dict[str, Any]:
    """Return non-authoritative mechanical/derived signals for offline study."""
    mechanical: list[dict[str, Any]] = []
    derived: list[dict[str, Any]] = []

    fixed_status = str(fixed_result.get("status") or "UNKNOWN").upper()
    task_status = _status(fixed_result.get("taskResult"))
    write_requested = bool(intent_route.get("writeRequested"))
    read_only = bool(intent_route.get("readOnlyRequired"))
    protected_count = len(control_intent.get("protectedScope") or [])
    receipt_present = isinstance(fixed_result.get("hostWriteReceipt"), Mapping)
    tool_statuses = _tool_statuses(fixed_result)
    tool_failures = sum(1 for value in tool_statuses if value in FAILURE_STATES)
    tool_passes = sum(1 for value in tool_statuses if value in SUCCESS_STATES)
    browser_before = isinstance(fixed_result.get("before"), Mapping)
    browser_after = isinstance(fixed_result.get("after"), Mapping)

    mechanical.extend([
        _signal(
            "FIXED_WORKFLOW_STATUS_OBSERVED", kind="MECHANICAL", polarity="NEUTRAL",
            source="fixed_result.status", value=fixed_status, capability_eligible=False,
            reason_code="AUTHORITATIVE_FIXED_WORKFLOW_OUTCOME_OBSERVED",
        ),
        _signal(
            "TASK_RESULT_STATUS_OBSERVED", kind="MECHANICAL", polarity="NEUTRAL",
            source="fixed_result.taskResult.status", value=task_status, capability_eligible=False,
            reason_code="AUTHORITATIVE_TASK_RESULT_OBSERVED",
        ),
        _signal(
            "WRITE_REQUEST_OBSERVED", kind="MECHANICAL", polarity="NEUTRAL",
            source="intent_route.writeRequested", value=write_requested, capability_eligible=False,
            reason_code="REQUEST_MUTATION_INTENT_OBSERVED",
        ),
        _signal(
            "READ_ONLY_BOUNDARY_OBSERVED", kind="MECHANICAL", polarity="NEUTRAL",
            source="intent_route.readOnlyRequired", value=read_only, capability_eligible=False,
            reason_code="READ_ONLY_CONSTRAINT_OBSERVED",
        ),
        _signal(
            "PROTECTED_SCOPE_COUNT_OBSERVED", kind="MECHANICAL", polarity="NEUTRAL",
            source="control_intent.protectedScope", value=protected_count, capability_eligible=False,
            reason_code="PROTECTED_SCOPE_METADATA_OBSERVED",
        ),
        _signal(
            "HOST_WRITE_RECEIPT_PRESENCE", kind="MECHANICAL", polarity="NEUTRAL",
            source="fixed_result.hostWriteReceipt", value=receipt_present, capability_eligible=False,
            reason_code="HOST_RECEIPT_PRESENCE_OBSERVED",
        ),
        _signal(
            "PROJECT_TOOL_FAILURE_COUNT", kind="MECHANICAL",
            polarity="NEGATIVE" if tool_failures else "NEUTRAL",
            source="fixed_result.projectToolEvidence", value=tool_failures,
            capability_eligible=bool(tool_statuses), reason_code="PROJECT_TOOL_RESULT_OBSERVED",
        ),
        _signal(
            "PROJECT_TOOL_PASS_COUNT", kind="MECHANICAL",
            polarity="POSITIVE" if tool_passes and not tool_failures else "NEUTRAL",
            source="fixed_result.projectToolEvidence", value=tool_passes,
            capability_eligible=bool(tool_statuses), reason_code="PROJECT_TOOL_RESULT_OBSERVED",
        ),
        _signal(
            "BROWSER_BEFORE_EVIDENCE_PRESENT", kind="MECHANICAL", polarity="NEUTRAL",
            source="fixed_result.before", value=browser_before, capability_eligible=False,
            reason_code="BEFORE_EVIDENCE_PRESENCE_OBSERVED",
        ),
        _signal(
            "BROWSER_AFTER_EVIDENCE_PRESENT", kind="MECHANICAL", polarity="NEUTRAL",
            source="fixed_result.after", value=browser_after, capability_eligible=False,
            reason_code="AFTER_EVIDENCE_PRESENCE_OBSERVED",
        ),
    ])

    # Derived signals are strict boolean contradictions/consistencies only.  No
    # semantic judgement or model-quality score is allowed here.
    if read_only and receipt_present:
        derived.append(_signal(
            "READ_ONLY_WITH_WRITE_RECEIPT_CONFLICT", kind="DERIVED_DETERMINISTIC", polarity="NEGATIVE",
            source="intent+receipt", value=True, capability_eligible=True,
            reason_code="READ_ONLY_REQUEST_HAS_WRITE_EVIDENCE",
        ))
    if tool_failures and (fixed_status in SUCCESS_STATES or task_status in SUCCESS_STATES):
        derived.append(_signal(
            "TOOL_FAILURE_WITH_SUCCESS_CLAIM_CONFLICT", kind="DERIVED_DETERMINISTIC", polarity="NEGATIVE",
            source="tool_results+fixed_outcome", value=True, capability_eligible=True,
            reason_code="FAILED_PROJECT_TOOL_COEXISTS_WITH_SUCCESS_CLAIM",
        ))
    if write_requested and not receipt_present and fixed_status in SUCCESS_STATES and selected_mode == "FIX_AND_VERIFY":
        derived.append(_signal(
            "WRITE_SUCCESS_WITHOUT_RECEIPT_CONFLICT", kind="DERIVED_DETERMINISTIC", polarity="NEGATIVE",
            source="intent+fixed_outcome+receipt", value=True, capability_eligible=True,
            reason_code="WRITE_SUCCESS_LACKS_HOST_RECEIPT",
        ))
    if fixed_status in {"NOT_VERIFIED", "BLOCKED"} or task_status in {"NOT_VERIFIED", "NOT_MEASURED", "BLOCKED"}:
        derived.append(_signal(
            "UNCERTAINTY_PRESERVED_BY_FIXED_WORKFLOW", kind="DERIVED_DETERMINISTIC", polarity="POSITIVE",
            source="fixed_outcome", value=True, capability_eligible=True,
            reason_code="INSUFFICIENT_OR_BLOCKED_EVIDENCE_NOT_PROMOTED_TO_SUCCESS",
        ))
    if tool_statuses and tool_failures == 0 and tool_passes == len(tool_statuses):
        derived.append(_signal(
            "PROJECT_TOOL_RESULTS_CONSISTENTLY_PASS", kind="DERIVED_DETERMINISTIC", polarity="POSITIVE",
            source="project_tool_results", value=True, capability_eligible=True,
            reason_code="ALL_OBSERVED_PROJECT_TOOLS_PASSED",
        ))

    all_signals = mechanical + derived
    polarity_counts = Counter(str(item["polarity"]) for item in all_signals)
    eligible = [item for item in all_signals if item.get("capabilityEligible")]
    value = {
        "schemaVersion": SIGNAL_SCHEMA_VERSION,
        "observerVersion": OBSERVER_VERSION,
        "packageVersion": PACKAGE_VERSION,
        "kernelBaseVersion": KERNEL_BASE_VERSION,
        "mode": "SHADOW_ONLY",
        "authoritative": False,
        "semanticSignalsUsed": False,
        "authorityEffect": "NONE",
        "adaptiveEffect": "NONE",
        "mechanicalSignals": mechanical,
        "derivedDeterministicSignals": derived,
        "summary": {
            "signalCount": len(all_signals),
            "capabilityEligibleSignalCount": len(eligible),
            "positiveCount": polarity_counts.get("POSITIVE", 0),
            "negativeCount": polarity_counts.get("NEGATIVE", 0),
            "neutralCount": polarity_counts.get("NEUTRAL", 0),
            "profileRecommendation": "NOT_EVALUATED_UNTIL_SIGNAL_VALIDITY_GATE",
            "clampRecommendation": "NOT_EVALUATED_UNTIL_SIGNAL_VALIDITY_GATE",
        },
        "claimBoundary": "Signals are observational research data only. They cannot alter authority, claims, TaskResult, guidance, checkpoints, context breadth, exploration, or the current run.",
    }
    value["signalSetDigest"] = digest_json(value)
    return value


__all__ = ["OBSERVER_VERSION", "SIGNAL_SCHEMA_VERSION", "observe_capability_signals"]
