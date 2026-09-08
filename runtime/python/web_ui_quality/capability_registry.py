"""One capability registry shared by doctor and execution workflows."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

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


def build_capability_registry(browser_executable: str | Path | None = None) -> dict[str, Any]:
    python_browser = _python_playwright(browser_executable)
    node_browser = browser_runtime_capability(browser_executable)
    providers = external_capabilities()
    navigation = bool(python_browser.get("available"))
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


__all__ = ["build_capability_registry"]
