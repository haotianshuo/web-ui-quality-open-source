"""Composite real-page readiness assessment."""
from __future__ import annotations

from typing import Any, Mapping


def assess_readiness(
    metrics: Mapping[str, Any],
    *,
    http_status: int | None,
    page_errors: list[str] | None = None,
    console_errors: list[Mapping[str, Any]] | None = None,
    core_resource_failures: list[Mapping[str, Any]] | None = None,
    ready_selector_found: bool | None = None,
    timed_out: bool = False,
) -> dict[str, Any]:
    page_errors = list(page_errors or [])
    console_errors = list(console_errors or [])
    core_resource_failures = list(core_resource_failures or [])
    auth_hint = bool(metrics.get("authWallHint"))
    skeletons = int(metrics.get("skeletonCount") or metrics.get("loadingPlaceholderCount") or 0)
    loading = bool(metrics.get("loadingHint"))
    text_length = int(metrics.get("textLength") or metrics.get("bodyTextLength") or 0)
    ready_state = str(metrics.get("readyState") or "")
    main_present = bool(metrics.get("mainPresent", text_length >= 24))
    fonts = str(metrics.get("fontStatus") or metrics.get("fontsStatus") or "unknown")
    reasons: list[str] = []
    if http_status in {401, 403} or auth_hint:
        status = "AUTH_REQUIRED"; reasons.append("authentication wall detected")
    elif page_errors or any(str(item.get("type")) == "error" for item in console_errors):
        status = "RUNTIME_BROKEN"; reasons.append("unhandled runtime error")
    elif core_resource_failures:
        status = "RUNTIME_BROKEN"; reasons.append("core resource failure")
    elif skeletons > 0 or loading:
        status = "DATA_NOT_READY"; reasons.append("loading or skeleton state remains")
    elif timed_out:
        status = "TIMEOUT"; reasons.append("bounded readiness window expired")
    elif http_status is None or not 200 <= http_status < 300:
        status = "PARTIAL"; reasons.append("no valid 2xx document response")
    elif ready_state not in {"interactive", "complete"} or not main_present or text_length < 24:
        status = "PARTIAL"; reasons.append("main content is not representative")
    elif ready_selector_found is False:
        status = "PARTIAL"; reasons.append("project-specific ready selector not found")
    else:
        status = "READY"
    return {
        "status": status,
        "httpStatus": http_status,
        "readyState": ready_state,
        "mainPresent": main_present,
        "visibleTextLength": text_length,
        "skeletonCount": skeletons,
        "loading": loading,
        "fontStatus": fonts,
        "readySelectorFound": ready_selector_found,
        "reasons": reasons,
    }


__all__ = ["assess_readiness"]
