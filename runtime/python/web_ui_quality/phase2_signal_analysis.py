"""Offline summaries for non-authoritative capability shadow observations."""
from __future__ import annotations

from collections import Counter
from typing import Any, Iterable, Mapping

from .contracts import digest_json


def summarize_signal_observations(observations: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    code_counts: Counter[str] = Counter()
    eligible_counts: Counter[str] = Counter()
    polarity_counts: Counter[str] = Counter()
    run_count = 0
    for observation in observations:
        signal_obs = observation.get("capabilitySignalObservation")
        if not isinstance(signal_obs, Mapping):
            continue
        run_count += 1
        rows = list(signal_obs.get("mechanicalSignals") or []) + list(signal_obs.get("derivedDeterministicSignals") or [])
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            code = str(row.get("code") or "UNKNOWN")
            code_counts[code] += 1
            polarity_counts[str(row.get("polarity") or "NEUTRAL")] += 1
            if row.get("capabilityEligible") is True:
                eligible_counts[code] += 1
    value = {
        "schemaVersion": "1",
        "mode": "SHADOW_ONLY",
        "authoritative": False,
        "runCount": run_count,
        "signalCodeCounts": dict(sorted(code_counts.items())),
        "capabilityEligibleCodeCounts": dict(sorted(eligible_counts.items())),
        "polarityCounts": dict(sorted(polarity_counts.items())),
        "predictiveValidity": "NOT_MEASURED",
        "profileRecommendation": "NOT_EVALUATED_UNTIL_SIGNAL_VALIDITY_GATE",
        "authorityEffect": "NONE",
        "adaptiveEffect": "NONE",
        "claimBoundary": "This summary describes observed signal frequency only. It does not establish predictive validity, model capability, or permission to change autonomy.",
    }
    value["summaryDigest"] = digest_json(value)
    return value


__all__ = ["summarize_signal_observations"]
