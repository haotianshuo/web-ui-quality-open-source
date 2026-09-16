"""Composite real-page readiness assessment."""
from __future__ import annotations

from typing import Any, Mapping


_RESOURCE_CONSOLE_PREFIX = "failed to load resource:"


def _is_resource_load_console_error(item: Mapping[str, Any]) -> bool:
    """Recognize a browser resource-load diagnostic without masking app errors.

    Chromium attaches the failed resource URL as the console message location
    and uses a stable diagnostic prefix.  Requiring both pieces keeps ordinary
    application ``console.error`` calls and unstructured evidence fail-closed.
    """

    if str(item.get("type") or "").casefold() != "error":
        return False
    location = item.get("location")
    if not isinstance(location, Mapping) or not str(location.get("url") or "").strip():
        return False
    text = str(item.get("text") or "").strip().casefold()
    return text.startswith(_RESOURCE_CONSOLE_PREFIX)


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
    # Only genuine console *errors* can break a page.  Warnings are collected as
    # evidence too, so without this type gate a benign console.warn would be
    # reported as an unhandled runtime error.
    runtime_console_errors = [
        item
        for item in console_errors
        if str(item.get("type") or "").casefold() == "error" and not _is_resource_load_console_error(item)
    ]
    reasons: list[str] = []
    if http_status in {401, 403} or auth_hint:
        status = "AUTH_REQUIRED"; reasons.append("authentication wall detected")
    elif page_errors or runtime_console_errors:
        status = "RUNTIME_BROKEN"; reasons.append("unhandled runtime error")
    elif core_resource_failures:
        status = "PARTIAL"; reasons.append("core resource failure")
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
