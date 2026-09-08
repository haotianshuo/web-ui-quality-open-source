"""Deterministic journey simulation used to compare experience concepts."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def _normalise_steps(steps: Sequence[Any]) -> list[dict[str, Any]]:
    result = []
    for index, item in enumerate(steps):
        if isinstance(item, Mapping):
            result.append({
                "id": str(item.get("id") or f"step-{index + 1}"),
                "label": str(item.get("label") or item.get("name") or f"步骤 {index + 1}"),
                "interaction": str(item.get("interaction") or "navigate"),
                "contextSwitch": bool(item.get("contextSwitch", False)),
                "recovery": bool(item.get("recovery", False)),
            })
        else:
            result.append({"id": f"step-{index + 1}", "label": str(item), "interaction": "navigate", "contextSwitch": False, "recovery": False})
    return result


def simulate_journey(
    current_steps: Sequence[Any],
    proposed_steps: Sequence[Any],
    *,
    evidence_level: str = "inferred",
) -> dict[str, Any]:
    """Compare two explicit step sets without pretending to measure real users."""
    current = _normalise_steps(current_steps)
    proposed = _normalise_steps(proposed_steps)
    if not current or not proposed:
        return {
            "status": "INSUFFICIENT_STEPS",
            "current": current,
            "proposed": proposed,
            "estimatedDelta": None,
            "claimBoundary": "No task-efficiency estimate is produced without both journeys.",
        }
    current_switches = sum(step["contextSwitch"] for step in current)
    proposed_switches = sum(step["contextSwitch"] for step in proposed)
    return {
        "status": "SIMULATION_READY",
        "current": current,
        "proposed": proposed,
        "estimatedDelta": {
            "stepCount": len(proposed) - len(current),
            "contextSwitches": proposed_switches - current_switches,
            "recoveryCoverage": sum(step["recovery"] for step in proposed) - sum(step["recovery"] for step in current),
        },
        "confidence": "medium" if evidence_level == "observed" else "low",
        "evidenceLevel": evidence_level,
        "claimBoundary": "This is a structural simulation. Validate time, success and preference with real users or trusted telemetry.",
    }


def score_variant(variant: Mapping[str, Any], *, recommended: bool, journey_coverage: int) -> dict[str, Any]:
    """Explain concept ranking using stable, user-facing factors."""
    state_coverage = len(variant.get("stateCoverage", []))
    implementation_slices = len(variant.get("implementationSlices", []))
    score = min(100, 45 + (18 if recommended else 0) + min(20, journey_coverage * 5) + min(12, state_coverage * 2) + (5 if implementation_slices else 0))
    return {
        "diagnosticFit": score,
        "factors": {
            "topProblemCoverage": journey_coverage,
            "stateCoverage": state_coverage,
            "boundedFirstSlice": bool(implementation_slices),
            "sourceRecommendation": recommended,
        },
        "measuredOutcome": False,
    }
