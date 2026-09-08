"""Deterministic evaluator capability routing with an immutable safety floor."""
from __future__ import annotations

from typing import Any, Iterable

from .contracts import ContractViolation

MANDATORY_CAPABILITIES = ("PageHealth", "EvidenceIntegrity")
_STANDARD_COMMON = {"Accessibility", "Interaction", "Responsive"}
_PAGE_CAPABILITIES = {
    "login": {"Form", "AuthenticationUX"},
    "table": {"Table", "DataDensity", "Overflow", "ResponsiveTable"},
    "marketing": {"CTAHierarchy", "ContentHierarchy", "Conversion", "TrustSignals"},
    "component": {"ComponentQuality"},
}
_FULL = set().union(*_PAGE_CAPABILITIES.values(), _STANDARD_COMMON, {"Navigation", "VisualHierarchy", "ContentQuality", "ResourceIntegrity"})


def infer_page_type(*, route: str | None = None, dom_features: Iterable[str] = (), component_type: str | None = None) -> str:
    text = " ".join([route or "", component_type or "", *[str(x) for x in dom_features]]).casefold()
    if any(x in text for x in ("login", "sign-in", "signin", "password", "auth")):
        return "login"
    if any(x in text for x in ("table", "grid", "datatable", "rows")):
        return "table"
    if any(x in text for x in ("landing", "hero", "pricing", "marketing", "cta")):
        return "marketing"
    return "component" if component_type else "generic"


def route_capabilities(*, task: str = "check", profile: str = "standard", page_type: str | None = None, route: str | None = None, dom_features: Iterable[str] = (), component_type: str | None = None, risk: str = "LOW", intent: str | None = None, disabled: Iterable[str] = ()) -> dict[str, Any]:
    if profile not in {"minimal", "standard", "full"}:
        raise ContractViolation("CAPABILITY_PROFILE_INVALID", [f"$: {profile}"])
    resolved = page_type or infer_page_type(route=route, dom_features=dom_features, component_type=component_type)
    active = set(MANDATORY_CAPABILITIES)
    reasons = {cap: "mandatory safety floor" for cap in MANDATORY_CAPABILITIES}
    if profile == "full":
        for cap in _FULL:
            active.add(cap); reasons[cap] = "full profile requested"
    else:
        page_caps = _PAGE_CAPABILITIES.get(resolved, set())
        for cap in page_caps:
            active.add(cap); reasons[cap] = f"matched {resolved} page characteristics"
        if profile == "standard":
            for cap in _STANDARD_COMMON:
                active.add(cap); reasons[cap] = "standard cross-cutting evaluator"
        elif profile == "minimal" and resolved == "component":
            active.add("ComponentQuality"); reasons["ComponentQuality"] = "focused component task"
    if str(risk).upper() == "HIGH":
        for cap in ("Accessibility", "Interaction", "ResourceIntegrity"):
            active.add(cap); reasons[cap] = "high-risk safety escalation"
    disabled_set = {str(x) for x in disabled}
    forbidden = disabled_set & set(MANDATORY_CAPABILITIES)
    if forbidden:
        raise ContractViolation("MANDATORY_CAPABILITY_DISABLE_FORBIDDEN", [f"$: cannot disable {sorted(forbidden)}"])
    active -= disabled_set
    universe = _FULL | set(MANDATORY_CAPABILITIES)
    skipped = [{"capability": cap, "reason": "explicitly disabled" if cap in disabled_set else "not required by resolved profile/context"} for cap in sorted(universe - active)]
    return {
        "schemaVersion": "1", "profile": profile, "pageType": resolved, "task": task, "intent": intent,
        "risk": str(risk).upper(), "activeCapabilities": sorted(active), "skippedCapabilities": skipped,
        "mandatoryCapabilities": list(MANDATORY_CAPABILITIES), "reasons": reasons,
    }
