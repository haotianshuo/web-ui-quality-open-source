"""Independent shadow qualification harness for 4.1 alpha.6.

This layer is offline and non-authoritative.  It distinguishes production shadow
runs from controlled benchmark fixtures and synthetic tests so that controlled
or synthetic evidence can never silently become a real-world validity claim.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Iterable, Mapping

from .contracts import digest_json
from .phase2_signal_dataset import label_validity_eligibility
from .phase2_signal_validity import analyze_signal_validity
from .release_info import KERNEL_BASE_VERSION, PACKAGE_VERSION

QUALIFICATION_VERSION = "4.1.0-alpha.6-independent-shadow-qualification-v1"
DATA_ORIGINS = {"PRODUCTION_SHADOW", "CONTROLLED_BENCHMARK", "SYNTHETIC_FIXTURE"}
PROVENANCE_LEVELS = {"HOST_ATTESTED", "BENCHMARK_CONTROLLER_ATTESTED", "DECLARED_ONLY", "TEST_ONLY"}
REPO_SCALES = {"SMALL", "MEDIUM", "LARGE", "UNKNOWN"}
RISK_TIERS = {"T0", "T1", "T2", "T3", "T4", "UNKNOWN"}


def build_qualification_plan(
    *,
    plan_id: str,
    created_at: str,
    minimum_real_world_rows: int = 50,
    minimum_task_families: int = 5,
    minimum_hosts: int = 1,
    minimum_models: int = 1,
    minimum_signal_support: int = 10,
    minimum_precision: float = 0.70,
    minimum_recall: float = 0.50,
    maximum_false_positive_rate: float = 0.20,
) -> dict[str, Any]:
    ints = (minimum_real_world_rows, minimum_task_families, minimum_hosts, minimum_models, minimum_signal_support)
    if any(int(v) < 1 for v in ints):
        raise ValueError("qualification minimums must be positive")
    rates = (minimum_precision, minimum_recall, maximum_false_positive_rate)
    if any(float(v) < 0 or float(v) > 1 for v in rates):
        raise ValueError("qualification rates must be in [0,1]")
    value: dict[str, Any] = {
        "schemaVersion": "1",
        "qualificationVersion": QUALIFICATION_VERSION,
        "packageVersion": PACKAGE_VERSION,
        "kernelBaseVersion": KERNEL_BASE_VERSION,
        "planId": plan_id,
        "analysisSplit": "DEVELOPMENT",
        "holdoutPolicy": "EXCLUDE_UNTIL_PREREGISTERED_GATE",
        "realWorldEligibility": {
            "dataOrigin": "PRODUCTION_SHADOW",
            "requiredProvenanceIntegrity": "HOST_ATTESTED",
            "requiredLabelIndependence": "INDEPENDENT",
            "allowedLabelSources": ["EXTERNAL_ORACLE", "HOST_ACCEPTANCE", "HUMAN_BLIND_REVIEW"],
        },
        "minimums": {
            "realWorldRows": int(minimum_real_world_rows),
            "taskFamilies": int(minimum_task_families),
            "hosts": int(minimum_hosts),
            "models": int(minimum_models),
            "signalSupport": int(minimum_signal_support),
        },
        "signalThresholds": {
            "minimumPrecision": float(minimum_precision),
            "minimumRecall": float(minimum_recall),
            "maximumFalsePositiveRate": float(maximum_false_positive_rate),
        },
        "createdAt": created_at,
        "authorityEffect": "NONE",
        "adaptiveEffect": "NONE",
        "claimBoundary": "This plan can qualify research evidence only. Passing it cannot grant write authority or activate adaptive guidance; a later preregistered Phase 3.5 gate is still required.",
    }
    value["planDigest"] = digest_json(value)
    return value


def build_qualification_case(
    record: Mapping[str, Any],
    *,
    data_origin: str,
    provenance_integrity: str,
    provenance_evidence_digest: str,
    task_family: str,
    host_id: str,
    model_id: str,
    reasoning_mode: str,
    repo_scale: str,
    risk_tier: str,
    captured_at: str,
) -> dict[str, Any]:
    origin = str(data_origin).upper()
    provenance = str(provenance_integrity).upper()
    scale = str(repo_scale).upper()
    risk = str(risk_tier).upper()
    if origin not in DATA_ORIGINS:
        raise ValueError("unknown data origin")
    if provenance not in PROVENANCE_LEVELS:
        raise ValueError("unknown provenance integrity")
    if scale not in REPO_SCALES:
        raise ValueError("unknown repo scale")
    if risk not in RISK_TIERS:
        raise ValueError("unknown risk tier")
    binding = record.get("taskBinding")
    if not isinstance(binding, Mapping) or not all(str(binding.get(k) or "") for k in ("runId", "taskId", "sessionId")):
        raise ValueError("dataset record task binding incomplete")
    dataset_digest = str(record.get("datasetRecordDigest") or "")
    if not dataset_digest:
        raise ValueError("dataset record digest missing")
    value: dict[str, Any] = {
        "schemaVersion": "1",
        "qualificationVersion": QUALIFICATION_VERSION,
        "packageVersion": PACKAGE_VERSION,
        "kernelBaseVersion": KERNEL_BASE_VERSION,
        "datasetRecordDigest": dataset_digest,
        "taskBinding": {k: str(binding[k]) for k in ("runId", "taskId", "sessionId")},
        "dataOrigin": origin,
        "provenanceIntegrity": provenance,
        "provenanceEvidenceDigest": str(provenance_evidence_digest),
        "strata": {
            "taskFamily": str(task_family),
            "hostId": str(host_id),
            "modelId": str(model_id),
            "reasoningMode": str(reasoning_mode),
            "repoScale": scale,
            "riskTier": risk,
        },
        "datasetRecord": dict(record),
        "capturedAt": captured_at,
        "authorityEffect": "NONE",
        "adaptiveEffect": "NONE",
        "claimBoundary": "Qualification cases are offline research evidence. Origin/provenance declarations do not change the authoritative task result or model permissions.",
    }
    value["caseDigest"] = digest_json(value)
    value["caseId"] = value["caseDigest"]
    return value


def qualification_case_eligibility(case: Mapping[str, Any], *, include_holdout: bool = False) -> dict[str, Any]:
    record = case.get("datasetRecord")
    if not isinstance(record, Mapping):
        return {"eligible": False, "class": "EXCLUDED", "reason": "DATASET_RECORD_MISSING"}
    label = record.get("label")
    eligibility = label_validity_eligibility(label if isinstance(label, Mapping) else None, include_holdout=include_holdout)
    if not eligibility["eligible"]:
        return {"eligible": False, "class": "EXCLUDED", "reason": eligibility["reason"]}
    origin = str(case.get("dataOrigin") or "UNKNOWN").upper()
    provenance = str(case.get("provenanceIntegrity") or "UNKNOWN").upper()
    if origin == "PRODUCTION_SHADOW":
        if provenance != "HOST_ATTESTED":
            return {"eligible": False, "class": "EXCLUDED", "reason": "PRODUCTION_PROVENANCE_NOT_HOST_ATTESTED"}
        return {"eligible": True, "class": "REAL_WORLD", "reason": "ELIGIBLE_REAL_WORLD_CASE"}
    if origin == "CONTROLLED_BENCHMARK":
        if provenance != "BENCHMARK_CONTROLLER_ATTESTED":
            return {"eligible": False, "class": "EXCLUDED", "reason": "BENCHMARK_PROVENANCE_NOT_CONTROLLER_ATTESTED"}
        if str(label.get("labelSource") or "") != "EXTERNAL_ORACLE":
            return {"eligible": False, "class": "EXCLUDED", "reason": "BENCHMARK_REQUIRES_EXTERNAL_ORACLE_LABEL"}
        return {"eligible": True, "class": "CONTROLLED", "reason": "ELIGIBLE_CONTROLLED_ORACLE_CASE"}
    return {"eligible": False, "class": "EXCLUDED", "reason": "SYNTHETIC_NOT_QUALIFICATION_EVIDENCE"}


def _binding_key(case: Mapping[str, Any]) -> tuple[str, str, str]:
    b = case.get("taskBinding") if isinstance(case, Mapping) else None
    if not isinstance(b, Mapping):
        return ("", "", "")
    return tuple(str(b.get(k) or "") for k in ("runId", "taskId", "sessionId"))  # type: ignore[return-value]


def _coverage(cases: list[Mapping[str, Any]]) -> dict[str, Any]:
    def uniq(field: str) -> list[str]:
        values = set()
        for case in cases:
            strata = case.get("strata")
            if isinstance(strata, Mapping):
                value = str(strata.get(field) or "UNKNOWN")
                if value: values.add(value)
        return sorted(values)
    return {
        "rowCount": len(cases),
        "taskFamilies": uniq("taskFamily"),
        "hosts": uniq("hostId"),
        "models": uniq("modelId"),
        "reasoningModes": uniq("reasoningMode"),
        "repoScales": uniq("repoScale"),
        "riskTiers": uniq("riskTier"),
    }


def _candidate_signals(validity: Mapping[str, Any], plan: Mapping[str, Any]) -> list[dict[str, Any]]:
    thresholds = plan.get("signalThresholds") if isinstance(plan.get("signalThresholds"), Mapping) else {}
    mins = plan.get("minimums") if isinstance(plan.get("minimums"), Mapping) else {}
    pmin = float(thresholds.get("minimumPrecision", 1.0))
    rmin = float(thresholds.get("minimumRecall", 1.0))
    fmax = float(thresholds.get("maximumFalsePositiveRate", 0.0))
    support_min = int(mins.get("signalSupport", 1))
    candidates=[]
    for metric in validity.get("signalMetrics") or []:
        if not isinstance(metric, Mapping): continue
        p=metric.get("precision"); r=metric.get("recall"); f=metric.get("falsePositiveRate")
        ok = (
            int(metric.get("support") or 0) >= support_min
            and p is not None and float(p) >= pmin
            and r is not None and float(r) >= rmin
            and f is not None and float(f) <= fmax
        )
        if ok:
            candidates.append({"code": str(metric.get("code")), "polarity": str(metric.get("polarity")), "support": int(metric.get("support") or 0), "precision": p, "recall": r, "falsePositiveRate": f})
    return candidates


def analyze_shadow_qualification(
    cases: Iterable[Mapping[str, Any]],
    plan: Mapping[str, Any],
    *,
    include_holdout: bool = False,
) -> dict[str, Any]:
    rows = list(cases)
    excluded = Counter()
    real: list[Mapping[str, Any]] = []
    controlled: list[Mapping[str, Any]] = []
    seen_bindings: set[tuple[str, str, str]] = set()
    duplicate_bindings = 0
    for case in rows:
        key = _binding_key(case)
        if key in seen_bindings:
            duplicate_bindings += 1
            excluded["DUPLICATE_TASK_BINDING"] += 1
            continue
        seen_bindings.add(key)
        e = qualification_case_eligibility(case, include_holdout=include_holdout)
        if not e["eligible"]:
            excluded[str(e["reason"])] += 1
        elif e["class"] == "REAL_WORLD":
            real.append(case)
        elif e["class"] == "CONTROLLED":
            controlled.append(case)

    real_records = [case["datasetRecord"] for case in real]
    controlled_records = [case["datasetRecord"] for case in controlled]
    mins = plan.get("minimums") if isinstance(plan.get("minimums"), Mapping) else {}
    signal_support = int(mins.get("signalSupport", 1))
    real_validity = analyze_signal_validity(real_records, include_holdout=include_holdout, minimum_independent_rows=max(1, int(mins.get("realWorldRows", 1))), minimum_signal_support=signal_support)
    controlled_validity = analyze_signal_validity(controlled_records, include_holdout=include_holdout, minimum_independent_rows=1, minimum_signal_support=signal_support)
    real_cov = _coverage(real)
    controlled_cov = _coverage(controlled)
    coverage_checks = {
        "minimumRealWorldRows": real_cov["rowCount"] >= int(mins.get("realWorldRows", 1)),
        "minimumTaskFamilies": len(real_cov["taskFamilies"]) >= int(mins.get("taskFamilies", 1)),
        "minimumHosts": len(real_cov["hosts"]) >= int(mins.get("hosts", 1)),
        "minimumModels": len(real_cov["models"]) >= int(mins.get("models", 1)),
    }
    candidates = _candidate_signals(real_validity, plan)
    if not real:
        qualification_status = "NOT_MEASURED_REAL_WORLD"
        decision = "NOT_READY_NO_REAL_WORLD_CASES"
    elif not all(coverage_checks.values()):
        qualification_status = "REAL_WORLD_DATA_INSUFFICIENT"
        decision = "NOT_READY_COVERAGE_REQUIREMENTS"
    elif not candidates:
        qualification_status = "REAL_WORLD_PRE_GATE_MEASURED"
        decision = "NOT_READY_NO_SIGNAL_MEETS_PREREGISTERED_THRESHOLDS"
    else:
        qualification_status = "REAL_WORLD_PRE_GATE_MEASURED"
        decision = "READY_FOR_PHASE3_5_PREREGISTRATION"

    value: dict[str, Any] = {
        "schemaVersion": "1",
        "qualificationVersion": QUALIFICATION_VERSION,
        "packageVersion": PACKAGE_VERSION,
        "kernelBaseVersion": KERNEL_BASE_VERSION,
        "planDigest": str(plan.get("planDigest") or ""),
        "analysisMode": "DEVELOPMENT_ONLY" if not include_holdout else "EXPLICIT_HOLDOUT_ANALYSIS",
        "authoritative": False,
        "caseCount": len(rows),
        "duplicateTaskBindingCount": duplicate_bindings,
        "realWorldCoverage": real_cov,
        "controlledCoverage": controlled_cov,
        "excludedReasonCounts": dict(sorted(excluded.items())),
        "coverageChecks": coverage_checks,
        "realWorldSignalValidity": real_validity,
        "controlledSignalValidity": controlled_validity,
        "candidateSignals": candidates,
        "qualificationStatus": qualification_status,
        "qualificationDecision": decision,
        "controlledEvidenceStatus": "CONTROLLED_ORACLE_MEASURED" if controlled else "NOT_MEASURED_CONTROLLED",
        "realWorldEvidenceStatus": "MEASURED_PRE_GATE_ONLY" if real else "NOT_MEASURED",
        "profileRecommendation": "NOT_EVALUATED_UNTIL_PHASE3_5_GATE",
        "clampRecommendation": "NOT_EVALUATED_UNTIL_PHASE3_5_GATE",
        "authorityEffect": "NONE",
        "adaptiveEffect": "NONE",
        "claimBoundary": "Qualification distinguishes production shadow, controlled benchmark, and synthetic evidence. Controlled or synthetic evidence cannot satisfy the real-world gate. Passing this pre-gate cannot activate adaptive guidance.",
    }
    value["reportDigest"] = digest_json(value)
    return value


__all__ = [
    "QUALIFICATION_VERSION",
    "build_qualification_plan",
    "build_qualification_case",
    "qualification_case_eligibility",
    "analyze_shadow_qualification",
]
