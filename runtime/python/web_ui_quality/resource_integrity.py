"""Classify resource failures without treating telemetry as a product blocker."""
from __future__ import annotations

from typing import Any, Iterable, Mapping
from urllib.parse import urlsplit

_CORE_TYPES = {"document", "script", "stylesheet", "xhr", "fetch", "font", "manifest"}
_TELEMETRY_HINTS = ("google-analytics", "googletagmanager", "segment.io", "sentry.io", "datadog", "newrelic", "mixpanel", "amplitude")


def _is_telemetry(url: str) -> bool:
    value = url.casefold()
    return any(item in value for item in _TELEMETRY_HINTS)


def classify_resource_events(events: Iterable[Mapping[str, Any]], *, page_origin: str | None = None) -> dict[str, Any]:
    core: list[dict[str, Any]] = []
    material_external: list[dict[str, Any]] = []
    telemetry: list[dict[str, Any]] = []
    other: list[dict[str, Any]] = []
    for raw in events:
        item = dict(raw)
        url = str(item.get("url") or "")
        resource_type = str(item.get("resourceType") or "unknown")
        event_origin = ""
        try:
            parsed = urlsplit(url)
            event_origin = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else str(item.get("origin") or "")
        except Exception:
            event_origin = str(item.get("origin") or "")
        item["origin"] = event_origin
        if _is_telemetry(url):
            item["classification"] = "NONCRITICAL_TELEMETRY_BLOCKED"
            telemetry.append(item)
        elif resource_type in _CORE_TYPES and (not page_origin or event_origin == page_origin or resource_type in {"document", "script", "stylesheet", "font"}):
            item["classification"] = "CORE_RESOURCE_FAILURE"
            core.append(item)
        elif resource_type in _CORE_TYPES:
            item["classification"] = "MATERIAL_EXTERNAL_RESOURCE_BLOCKED"
            material_external.append(item)
        else:
            item["classification"] = "OTHER_RESOURCE_WARNING"
            other.append(item)
    status = "BLOCKED" if core or material_external else "PASS_WITH_WARNINGS" if telemetry or other else "PASS"
    return {"status": status, "coreFailures": core, "materialExternalFailures": material_external, "telemetryWarnings": telemetry, "otherWarnings": other}


__all__ = ["classify_resource_events"]
