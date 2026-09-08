"""Deterministic verification budget selection and cache identity."""
from __future__ import annotations

from typing import Any, Mapping, Sequence
from .contracts import digest_json


def select_verification_budget(*, risk: str, affected_surfaces: int, changed_files: int, systemic: bool = False) -> dict[str, Any]:
    risk = str(risk).upper()
    affected = max(0, int(affected_surfaces))
    files = max(0, int(changed_files))
    if risk == "HIGH" or systemic or affected > 20 or files > 8:
        profile = "FULL"
        strategy = "REPRESENTATIVE_PLUS_INTEGRATION"
        route_cap = min(max(affected, 3), 50)
    elif risk == "MEDIUM" or affected > 3 or files > 2:
        profile = "STANDARD"
        strategy = "TARGETED_AFFECTED_SURFACES"
        route_cap = min(max(affected, 2), 12)
    else:
        profile = "MINIMAL"
        strategy = "TARGETED_CHANGED_SURFACES"
        route_cap = min(max(affected, 1), 4)
    return {
        "profile": profile,
        "strategy": strategy,
        "maxRoutes": route_cap,
        "serialHighRisk": risk == "HIGH",
        "cacheAllowed": True,
        "claimBoundary": "Budgeting may reduce redundant verification, never mandatory safety checks or evidence-integrity checks.",
    }


def verification_cache_key(conditions: Mapping[str, Any]) -> str:
    allowed = {key: conditions.get(key) for key in (
        "sourceDigest", "baselineDigest", "route", "viewport", "browserIdentity", "toolDigest", "configDigest", "authProfile", "dataState"
    )}
    return digest_json(allowed)


__all__ = ["select_verification_budget", "verification_cache_key"]
