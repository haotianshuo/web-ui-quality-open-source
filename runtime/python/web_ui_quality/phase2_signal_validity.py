"""Signal-validity pre-gate analysis for alpha.5.

This module measures only explicitly labelled offline rows.  It never emits a
capability score or an autonomy recommendation.  Development analysis excludes
HOLDOUT labels by default, and Fixed Workflow proxy labels cannot establish
predictive validity.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Iterable, Mapping

from .contracts import digest_json
from .phase2_signal_dataset import label_validity_eligibility


def _safe_rate(num: int, den: int) -> float | None:
    return None if den == 0 else num / den


def analyze_signal_validity(
    records: Iterable[Mapping[str, Any]],
    *,
    include_holdout: bool = False,
    minimum_independent_rows: int = 20,
    minimum_signal_support: int = 5,
) -> dict[str, Any]:
    rows = list(records)
    excluded = Counter()
    eligible_rows: list[Mapping[str, Any]] = []
    split_counts = Counter()
    label_source_counts = Counter()
    for record in rows:
        label = record.get("label") if isinstance(record, Mapping) else None
        if isinstance(label, Mapping):
            split_counts[str(label.get("split") or "UNKNOWN")] += 1
            label_source_counts[str(label.get("labelSource") or "UNKNOWN")] += 1
        eligibility = label_validity_eligibility(label if isinstance(label, Mapping) else None, include_holdout=include_holdout)
        if eligibility["eligible"]:
            eligible_rows.append(record)
        else:
            excluded[str(eligibility["reason"])] += 1

    universe: dict[str, dict[str, Any]] = {}
    for record in eligible_rows:
        for signal in record.get("signals") or []:
            if not isinstance(signal, Mapping) or signal.get("capabilityEligible") is not True:
                continue
            polarity = str(signal.get("polarity") or "NEUTRAL")
            if polarity not in {"POSITIVE", "NEGATIVE"}:
                continue
            code = str(signal.get("code") or "UNKNOWN")
            universe.setdefault(code, {"polarity": polarity})

    metrics: list[dict[str, Any]] = []
    for code in sorted(universe):
        polarity = universe[code]["polarity"]
        tp = fp = fn = tn = support = 0
        for record in eligible_rows:
            label = record.get("label") or {}
            outcome = str(label.get("outcome") or "INCONCLUSIVE")
            present = any(
                isinstance(signal, Mapping)
                and signal.get("capabilityEligible") is True
                and str(signal.get("code") or "") == code
                for signal in (record.get("signals") or [])
            )
            positive_class = outcome == ("GOOD" if polarity == "POSITIVE" else "BAD")
            if present:
                support += 1
                if positive_class: tp += 1
                else: fp += 1
            else:
                if positive_class: fn += 1
                else: tn += 1
        precision = _safe_rate(tp, tp + fp)
        recall = _safe_rate(tp, tp + fn)
        fpr = _safe_rate(fp, fp + tn)
        metrics.append({
            "code": code,
            "polarity": polarity,
            "support": support,
            "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "precision": precision,
            "recall": recall,
            "falsePositiveRate": fpr,
            "supportSufficient": support >= minimum_signal_support,
        })

    enough_rows = len(eligible_rows) >= minimum_independent_rows
    any_supported = any(item["supportSufficient"] for item in metrics)
    if not eligible_rows:
        predictive_validity = "NOT_MEASURED"
        gate = "NOT_READY_NO_INDEPENDENT_LABELS"
    elif not enough_rows:
        predictive_validity = "PRE_GATE_DATA_ONLY"
        gate = "NOT_READY_INSUFFICIENT_INDEPENDENT_ROWS"
    elif not any_supported:
        predictive_validity = "PRE_GATE_DATA_ONLY"
        gate = "NOT_READY_INSUFFICIENT_SIGNAL_SUPPORT"
    else:
        predictive_validity = "PRE_GATE_MEASURED_DEVELOPMENT_ONLY"
        gate = "READY_FOR_PREREGISTERED_SIGNAL_VALIDITY_GATE"

    value: dict[str, Any] = {
        "schemaVersion": "1",
        "analysisMode": "DEVELOPMENT_ONLY" if not include_holdout else "EXPLICIT_HOLDOUT_ANALYSIS",
        "authoritative": False,
        "recordCount": len(rows),
        "independentlyLabelledRowCount": len(eligible_rows),
        "minimumIndependentRows": minimum_independent_rows,
        "minimumSignalSupport": minimum_signal_support,
        "labelSourceCounts": dict(sorted(label_source_counts.items())),
        "splitCounts": dict(sorted(split_counts.items())),
        "excludedReasonCounts": dict(sorted(excluded.items())),
        "signalMetrics": metrics,
        "predictiveValidity": predictive_validity,
        "preGateDecision": gate,
        "profileRecommendation": "NOT_EVALUATED_UNTIL_SIGNAL_VALIDITY_GATE",
        "clampRecommendation": "NOT_EVALUATED_UNTIL_SIGNAL_VALIDITY_GATE",
        "authorityEffect": "NONE",
        "adaptiveEffect": "NONE",
        "holdoutUsed": bool(include_holdout),
        "claimBoundary": "Development metrics are research evidence only. They cannot grant authority or enable adaptive guidance. Fixed Workflow proxy labels and synthetic fixtures do not establish predictive validity.",
    }
    value["reportDigest"] = digest_json(value)
    return value


__all__ = ["analyze_signal_validity"]
