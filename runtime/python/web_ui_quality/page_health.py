"""Page health is evaluated before visual quality and cannot be overridden by it."""
from __future__ import annotations

from typing import Any, Mapping

_PRIORITY = {
    "RUNTIME_BROKEN": 0,
    "AUTH_REQUIRED": 1,
    "RESTRICTED_RENDER": 2,
    "DATA_NOT_READY": 3,
    "TASK_FAILED": 4,
    "NOT_VERIFIED": 5,
    "VISUAL_FINDINGS": 6,
    "PASS": 7,
    "SIMULATED_PREVIEW": 5,
    "REAL_PAGE_READY": 7,
}


def _most_severe(values: list[str]) -> str:
    return min(values, key=lambda item: _PRIORITY.get(item, 99)) if values else "NOT_VERIFIED"


def evaluate_page_health(
    *,
    readiness: Mapping[str, Any] | None,
    resource_integrity: Mapping[str, Any] | None,
    runtime_errors: list[Any] | None = None,
    auth_required: bool = False,
    task_status: str | None = None,
    visual_findings: int = 0,
    browser_executed: bool = True,
    simulated: bool = False,
) -> dict[str, Any]:
    readiness = dict(readiness or {})
    resources = dict(resource_integrity or {})
    runtime_errors = list(runtime_errors or [])
    runtime_status = "RUNTIME_BROKEN" if runtime_errors or readiness.get("status") == "RUNTIME_BROKEN" else "PASS"
    network_status = "RESTRICTED_RENDER" if resources.get("status") == "BLOCKED" else "PASS_WITH_WARNINGS" if resources.get("status") == "PASS_WITH_WARNINGS" else "PASS"
    auth_status = "AUTH_REQUIRED" if auth_required or readiness.get("status") == "AUTH_REQUIRED" else "PASS"
    readiness_status = str(readiness.get("status") or "NOT_VERIFIED")
    data_status = "DATA_NOT_READY" if readiness_status == "DATA_NOT_READY" else "NOT_VERIFIED" if readiness_status in {"PARTIAL", "TIMEOUT"} else "PASS"
    normalized_task = task_status or "NOT_VERIFIED"
    if normalized_task in {"FAIL", "FAIL_NOT_RESTORED", "FAIL_NO_STATE_CHANGE", "BLOCKED_MUTATION_ATTEMPT"}:
        normalized_task = "TASK_FAILED"
    elif normalized_task in {"PASS", "PASS_RESTORED"}:
        normalized_task = "PASS"
    else:
        normalized_task = "NOT_VERIFIED"
    visual_status = "VISUAL_FINDINGS" if visual_findings else "PASS"
    candidates = [runtime_status, auth_status, network_status, data_status, normalized_task, visual_status]
    if not browser_executed:
        candidates.append("NOT_VERIFIED")
    if simulated:
        candidates.append("SIMULATED_PREVIEW")
    page_status = _most_severe(candidates)
    if page_status == "PASS" and readiness.get("status") == "READY" and browser_executed and not simulated:
        page_status = "REAL_PAGE_READY"
    elif page_status == "PASS" and simulated:
        page_status = "SIMULATED_PREVIEW"
    return {
        "pageStatus": page_status,
        "runtimeStatus": runtime_status,
        "networkStatus": network_status,
        "authStatus": auth_status,
        "dataStatus": data_status,
        "taskStatus": normalized_task,
        "visualStatus": visual_status,
        "browserExecuted": bool(browser_executed),
        "simulated": bool(simulated),
        "blockingPriority": _PRIORITY.get(page_status, 99),
        "visualCanOverride": False,
    }


__all__ = ["evaluate_page_health"]
