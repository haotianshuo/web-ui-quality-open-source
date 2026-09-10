"""One capability registry shared by doctor and execution workflows."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Mapping

from .external_providers import capabilities as external_capabilities
from .production_validation import browser_runtime_capability
from .condition_registry import STANDARD_VIEWPORTS
from .browser_locator import resolve_browser_executable
from .playwright_adapter import playwright_capability


def _module_present(name: str) -> bool:
    """Probe an optional module without letting a missing parent package escape.

    ``importlib.util.find_spec`` imports every parent package before resolving
    the leaf, so probing a submodule of an uninstalled distribution raises
    ``ModuleNotFoundError`` instead of returning ``None``.  Capability discovery
    must degrade, never crash, when an optional dependency is absent.
    """
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, AttributeError, ValueError):
        return False


def _python_playwright(browser_executable: str | Path | None = None) -> dict[str, Any]:
    module_available = _module_present("playwright.sync_api")
    decision: dict[str, Any] = resolve_browser_executable("chromium", explicit=browser_executable)
    if module_available:
        try:
            capability = playwright_capability(browser_executable)
            decision = {
                "available": bool(capability.get("available")),
                "executable": capability.get("executable"),
                "source": capability.get("executableSource"),
                "reason": capability.get("reason"),
            }
        except Exception:
            pass
    executable_available = bool(decision.get("available"))
    available = bool(module_available and executable_available)
    if available:
        reason = None
        reason_code = "CAPABILITY_AVAILABLE"
        repair = None
    elif not module_available and executable_available:
        reason = f"Chrome/Chromium executable found at {decision.get('executable')}, but the Python Playwright driver module is missing."
        reason_code = "PYTHON_PLAYWRIGHT_MODULE_MISSING"
        repair = "Install `web-ui-quality[browser]`; the detected desktop browser can then be used without downloading a separate Playwright browser binary. --browser-executable only selects an executable after the Playwright driver is available."
    elif module_available and not executable_available:
        reason = decision.get("reason") or "Python Playwright is installed, but no usable Chrome/Chromium executable was found."
        reason_code = "PYTHON_BROWSER_EXECUTABLE_MISSING"
        repair = "Install Chrome/Edge/Chromium or pass --browser-executable. The executable option does not replace the Playwright driver."
    else:
        reason = "Python Playwright driver is missing and no usable Chrome/Chromium executable was discovered."
        reason_code = "PYTHON_PLAYWRIGHT_AND_BROWSER_MISSING"
        repair = "Install `web-ui-quality[browser]` and Chrome/Edge/Chromium. --browser-executable selects a browser only after Playwright is installed."
    return {
        "available": available,
        "runtime": "python-playwright",
        "moduleAvailable": module_available,
        "browserExecutableAvailable": executable_available,
        "browser": "chromium" if available else None,
        "executable": decision.get("executable"),
        "executableSource": decision.get("source"),
        "reason": reason,
        "reasonCode": reason_code,
        "resolutionTrace": list(decision.get("resolutionTrace") or []),
        "repair": repair,
        "driverContract": "Playwright is the Browser driver; Chrome/Edge/Chromium is the executable. --browser-executable does not bypass Playwright.",
    }


_CAPABILITY_STATES = frozenset({"AVAILABLE", "BLOCKED", "MISSING", "NOT_MEASURED"})


def _capability_state(value: str, *, field: str) -> str:
    state = str(value or "NOT_MEASURED").upper()
    if state not in _CAPABILITY_STATES:
        raise ValueError(f"unsupported Browser capability state for {field}: {state}")
    return state


def build_browser_capability_clarity(
    python_browser: Mapping[str, Any],
    node_browser: Mapping[str, Any],
    *,
    navigation_authorized: str = "NOT_MEASURED",
    target_reachable: str = "NOT_MEASURED",
    evidence_collected: str = "NOT_MEASURED",
    verification_status: str = "NOT_MEASURED",
) -> dict[str, Any]:
    """Project launch prerequisites separately from task-level Browser proof.

    The optional task-level states are descriptive inputs for a run result. The
    default doctor projection deliberately leaves them unmeasured; a local
    driver/executable probe cannot authorize navigation or create evidence.
    """
    browser_installed = bool(
        python_browser.get("browserExecutableAvailable")
        or python_browser.get("executable")
        or node_browser.get("executable")
    )
    driver_available = bool(python_browser.get("moduleAvailable"))
    launch_ready = bool(python_browser.get("available"))
    if launch_ready:
        launch_status = "AVAILABLE"
    elif browser_installed or driver_available:
        launch_status = "BLOCKED"
    else:
        launch_status = "MISSING"
    if launch_status == "AVAILABLE":
        next_action = "提供安全的目标 URL 并执行本次任务；当前状态只表示可启动 Browser，不表示已完成验证。"
        reason_code = "BROWSER_CAPABILITY_READY_NOT_VERIFIED"
    elif launch_status == "BLOCKED":
        next_action = "补齐缺失的 Browser 驱动或可执行文件，然后重新运行；当前没有导航或验证证据。"
        reason_code = "BROWSER_CAPABILITY_PARTIAL"
    else:
        next_action = "安装 Playwright 驱动和 Chrome/Edge/Chromium 后重新运行 doctor；当前没有 Browser 能力。"
        reason_code = "BROWSER_CAPABILITY_MISSING"
    return {
        "status": launch_status,
        "reasonCode": reason_code,
        "browserInstalled": "AVAILABLE" if browser_installed else "MISSING",
        "driverAvailable": "AVAILABLE" if driver_available else "MISSING",
        "launchStatus": launch_status,
        "navigationAuthorized": _capability_state(navigation_authorized, field="navigationAuthorized"),
        "targetReachable": _capability_state(target_reachable, field="targetReachable"),
        "evidenceCollected": _capability_state(evidence_collected, field="evidenceCollected"),
        "verificationStatus": _capability_state(verification_status, field="verificationStatus"),
        "driverProvider": "python-playwright",
        "claimBoundary": "AVAILABLE means Browser Installed plus Driver Available for launch only; navigation authorization, target reachability, evidence, and verification require an actual bounded task run.",
        "nextAction": next_action,
    }


def build_capability_registry(browser_executable: str | Path | None = None) -> dict[str, Any]:
    python_browser = _python_playwright(browser_executable)
    node_browser = browser_runtime_capability(browser_executable)
    providers = external_capabilities()
    navigation = bool(python_browser.get("available"))
    browser_clarity = build_browser_capability_clarity(python_browser, node_browser)
    return {
        "pageNavigation": {"available": navigation, "provider": "python-playwright" if navigation else None},
        "pageScreenshot": {"available": navigation, "provider": "python-playwright" if navigation else None},
        "domInspection": {"available": navigation, "provider": "python-playwright" if navigation else None},
        "uiAssetInventory": {
            "available": navigation,
            "provider": "python-playwright" if navigation else None,
            "readOnly": True,
            "routeDiscovery": ["runtime-links", "source-routes"],
            "assets": ["button", "input", "card", "dialog", "table", "icon", "color", "typography", "radius", "spacing"],
            "driftDetection": True,
            "designTokenComparison": True,
        },
        "safeInteraction": {"available": navigation, "provider": "python-playwright", "maximumDefaultAuthority": "A1", "mutationFirewall": "GET_HEAD_OPTIONS_ONLY", "reversibleProbeRequired": True},
        "networkObservation": {"available": navigation, "provider": "python-playwright" if navigation else None, "recordsMethodOriginResourceType": True},
        "multiViewport": {"available": navigation, "viewports": [f"{w}x{h}" for w, h in STANDARD_VIEWPORTS], "authoritativeSource": "condition_registry.STANDARD_VIEWPORTS"},
        "pythonPlaywright": python_browser,
        "nodeCandidateValidation": node_browser,
        "browserCapability": browser_clarity,
        "lighthouse": providers.get("lighthouse", {}),
        "axe": providers.get("axe", {}),
        "browserStatus": "AVAILABLE" if navigation else "NOT_AVAILABLE",
        "fallbackCapabilities": [
            "source analysis",
            "static DOM analysis",
            "CSS responsive risk analysis",
            "route and component structure analysis",
        ],
        "degradedCapabilities": [] if navigation else [
            "source analysis",
            "static DOM analysis",
            "CSS responsive risk analysis",
            "route and component structure analysis",
        ],
    }


__all__ = ["build_browser_capability_clarity", "build_capability_registry"]
