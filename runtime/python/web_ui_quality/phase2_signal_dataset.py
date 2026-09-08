"""Phase-2 shadow dataset contracts for signal-validity preparation.

The dataset layer is deliberately offline and non-authoritative.  It may join
production shadow observations with explicit outcome labels, but it cannot alter
execution, authority, claims, TaskResult, guidance, checkpoints, context, or
exploration.
"""
from __future__ import annotations

from typing import Any, Mapping

from .contracts import digest_json
from .release_info import KERNEL_BASE_VERSION, PACKAGE_VERSION

DATASET_VERSION = "4.1.0-alpha.6-shadow-dataset-v1"
ELIGIBLE_LABEL_SOURCES = {"EXTERNAL_ORACLE", "HOST_ACCEPTANCE", "HUMAN_BLIND_REVIEW"}
NON_CONFIRMATORY_LABEL_SOURCES = {"FIXED_WORKFLOW_PROXY", "SYNTHETIC_FIXTURE"}
OUTCOMES = {"GOOD", "BAD", "INCONCLUSIVE"}
SPLITS = {"DEVELOPMENT", "HOLDOUT", "EXTERNAL"}


def build_outcome_label(
    *,
    run_id: str,
    task_id: str,
    session_id: str,
    source: str,
    outcome: str,
    independence: str,
    split: str,
    evaluator_id: str,
    evidence_digest: str,
    created_at: str,
) -> dict[str, Any]:
    source = str(source).upper()
    outcome = str(outcome).upper()
    independence = str(independence).upper()
    split = str(split).upper()
    if source not in ELIGIBLE_LABEL_SOURCES | NON_CONFIRMATORY_LABEL_SOURCES:
        raise ValueError("unknown outcome label source")
    if outcome not in OUTCOMES:
        raise ValueError("unknown outcome")
    if independence not in {"INDEPENDENT", "POTENTIALLY_DEPENDENT", "UNKNOWN"}:
        raise ValueError("unknown independence state")
    if split not in SPLITS:
        raise ValueError("unknown dataset split")
    value: dict[str, Any] = {
        "schemaVersion": "1",
        "packageVersion": PACKAGE_VERSION,
        "kernelBaseVersion": KERNEL_BASE_VERSION,
        "taskBinding": {"runId": run_id, "taskId": task_id, "sessionId": session_id},
        "labelSource": source,
        "outcome": outcome,
        "independence": independence,
        "split": split,
        "evaluatorId": evaluator_id,
        "evidenceDigest": evidence_digest,
        "createdAt": created_at,
        "authorityEffect": "NONE",
        "adaptiveEffect": "NONE",
        "claimBoundary": "Outcome labels are research annotations only. They cannot alter the current or historical authoritative run result.",
    }
    core = dict(value)
    value["labelDigest"] = digest_json(core)
    value["labelId"] = value["labelDigest"]
    return value


def label_validity_eligibility(label: Mapping[str, Any] | None, *, include_holdout: bool = False) -> dict[str, Any]:
    if not isinstance(label, Mapping):
        return {"eligible": False, "reason": "UNLABELED"}
    source = str(label.get("labelSource") or "UNKNOWN").upper()
    outcome = str(label.get("outcome") or "INCONCLUSIVE").upper()
    independence = str(label.get("independence") or "UNKNOWN").upper()
    split = str(label.get("split") or "DEVELOPMENT").upper()
    if source not in ELIGIBLE_LABEL_SOURCES:
        return {"eligible": False, "reason": "LABEL_SOURCE_NOT_CONFIRMATORY"}
    if independence != "INDEPENDENT":
        return {"eligible": False, "reason": "LABEL_NOT_INDEPENDENT"}
    if outcome == "INCONCLUSIVE":
        return {"eligible": False, "reason": "OUTCOME_INCONCLUSIVE"}
    if split == "HOLDOUT" and not include_holdout:
        return {"eligible": False, "reason": "HOLDOUT_EXCLUDED_BY_DEFAULT"}
    return {"eligible": True, "reason": "ELIGIBLE_INDEPENDENT_LABEL"}


def _signal_rows(observation: Mapping[str, Any]) -> list[dict[str, Any]]:
    signal_obs = observation.get("capabilitySignalObservation")
    if not isinstance(signal_obs, Mapping):
        return []
    rows: list[dict[str, Any]] = []
    for group in ("mechanicalSignals", "derivedDeterministicSignals"):
        values = signal_obs.get(group)
        if not isinstance(values, list):
            continue
        for row in values:
            if not isinstance(row, Mapping):
                continue
            rows.append({
                "code": str(row.get("code") or "UNKNOWN"),
                "kind": str(row.get("kind") or "UNKNOWN"),
                "polarity": str(row.get("polarity") or "NEUTRAL"),
                "capabilityEligible": bool(row.get("capabilityEligible")),
                "present": True,
            })
    return sorted(rows, key=lambda item: (item["code"], item["kind"], item["polarity"]))


def build_dataset_record(
    observation: Mapping[str, Any],
    *,
    outcome_label: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    binding = observation.get("taskBinding")
    if not isinstance(binding, Mapping):
        raise ValueError("shadow observation missing taskBinding")
    binding_value = {
        "runId": str(binding.get("runId") or ""),
        "taskId": str(binding.get("taskId") or ""),
        "sessionId": str(binding.get("sessionId") or ""),
    }
    if not all(binding_value.values()):
        raise ValueError("shadow observation task binding is incomplete")
    if outcome_label is not None:
        label_binding = outcome_label.get("taskBinding") if isinstance(outcome_label, Mapping) else None
        if not isinstance(label_binding, Mapping) or any(str(label_binding.get(k) or "") != binding_value[k] for k in binding_value):
            raise ValueError("outcome label task binding mismatch")
    signal_obs = observation.get("capabilitySignalObservation")
    signal_digest = signal_obs.get("signalSetDigest") if isinstance(signal_obs, Mapping) else None
    record: dict[str, Any] = {
        "schemaVersion": "1",
        "datasetVersion": DATASET_VERSION,
        "packageVersion": PACKAGE_VERSION,
        "kernelBaseVersion": KERNEL_BASE_VERSION,
        "taskBinding": binding_value,
        "observationDigest": str(observation.get("observationDigest") or digest_json(observation)),
        "signalSetDigest": str(signal_digest or ""),
        "signals": _signal_rows(observation),
        "label": dict(outcome_label) if isinstance(outcome_label, Mapping) else None,
        "authorityEffect": "NONE",
        "adaptiveEffect": "NONE",
        "claimBoundary": "Dataset records are offline research artifacts. Joining a label never changes the authoritative Fixed Workflow outcome.",
    }
    record["datasetRecordDigest"] = digest_json(record)
    return record


__all__ = [
    "DATASET_VERSION",
    "ELIGIBLE_LABEL_SOURCES",
    "build_dataset_record",
    "build_outcome_label",
    "label_validity_eligibility",
]
