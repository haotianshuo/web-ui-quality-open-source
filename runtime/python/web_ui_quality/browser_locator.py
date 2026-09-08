"""Browser executable discovery shared by Browser-backed workflows.

The product must not tell users to pass a browser path on one command while
silently ignoring the same path on another. This module centralizes explicit,
Playwright-bundled, PATH, and common desktop-install discovery.
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
from typing import Any

_BROWSER_NAMES = {
    "chromium": ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable", "chrome", "msedge"),
    "firefox": ("firefox",),
    "webkit": (),
}

# These codes are deliberately independent from human-readable ``reason``
# strings.  They are safe for receipts, doctor output, and release-gate
# comparisons across hosts with different paths and error messages.
RESOLUTION_REASON_CODES = frozenset({
    "BROWSER_EXECUTABLE_RESOLVED",
    "EXPLICIT_BROWSER_NOT_FOUND",
    "BROWSER_EXECUTABLE_NOT_FOUND",
})


def _desktop_candidates(browser_name: str) -> list[Path]:
    candidates: list[Path] = []
    if os.name == "nt":
        roots = [os.environ.get("PROGRAMFILES"), os.environ.get("PROGRAMFILES(X86)"), os.environ.get("LOCALAPPDATA")]
        roots = [Path(value) for value in roots if value]
        if browser_name == "chromium":
            suffixes = (
                Path("Google/Chrome/Application/chrome.exe"),
                Path("Google/Chrome Beta/Application/chrome.exe"),
                Path("Microsoft/Edge/Application/msedge.exe"),
                Path("Chromium/Application/chrome.exe"),
            )
        elif browser_name == "firefox":
            suffixes = (Path("Mozilla Firefox/firefox.exe"),)
        else:
            suffixes = ()
        for root in roots:
            candidates.extend(root / suffix for suffix in suffixes)
    elif sys_platform() == "darwin":
        if browser_name == "chromium":
            candidates.extend([
                Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
                Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"),
                Path.home() / "Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            ])
        elif browser_name == "firefox":
            candidates.append(Path("/Applications/Firefox.app/Contents/MacOS/firefox"))
    else:
        if browser_name == "chromium":
            candidates.extend([
                Path("/usr/bin/google-chrome"), Path("/usr/bin/google-chrome-stable"),
                Path("/usr/bin/chromium"), Path("/usr/bin/chromium-browser"),
                Path("/snap/bin/chromium"),
            ])
        elif browser_name == "firefox":
            candidates.append(Path("/usr/bin/firefox"))
    return candidates


def sys_platform() -> str:
    import sys
    return sys.platform


def resolve_browser_executable(
    browser_name: str = "chromium",
    *,
    explicit: str | Path | None = None,
    playwright_browser_type: Any | None = None,
) -> dict[str, Any]:
    """Return one deterministic Browser executable decision.

    Priority: explicit > Playwright bundled > PATH > common desktop installs.
    The returned mapping is safe to surface from ``doctor``.
    """
    if explicit:
        resolution_trace = ["explicit"]
        path = Path(explicit).expanduser().resolve()
        if path.is_file():
            return {
                "available": True,
                "executable": str(path),
                "source": "explicit",
                "reason": None,
                "reasonCode": "BROWSER_EXECUTABLE_RESOLVED",
                "resolutionTrace": resolution_trace,
            }
        return {
            "available": False,
            "executable": None,
            "source": "explicit",
            "reason": f"Explicit browser executable does not exist: {path}",
            "reasonCode": "EXPLICIT_BROWSER_NOT_FOUND",
            "resolutionTrace": resolution_trace,
        }

    resolution_trace: list[str] = []
    if playwright_browser_type is not None:
        resolution_trace.append("playwright")
        try:
            bundled = Path(str(playwright_browser_type.executable_path)).expanduser()
            if bundled.is_file():
                return {
                    "available": True,
                    "executable": str(bundled),
                    "source": "playwright",
                    "reason": None,
                    "reasonCode": "BROWSER_EXECUTABLE_RESOLVED",
                    "resolutionTrace": resolution_trace,
                }
        except Exception:
            pass

    resolution_trace.append("system-path")
    for name in _BROWSER_NAMES.get(browser_name, ()):
        located = shutil.which(name)
        if located:
            return {
                "available": True,
                "executable": str(Path(located)),
                "source": "system-path",
                "reason": None,
                "reasonCode": "BROWSER_EXECUTABLE_RESOLVED",
                "resolutionTrace": resolution_trace,
            }

    resolution_trace.append("desktop-install")
    for candidate in _desktop_candidates(browser_name):
        try:
            if candidate.is_file():
                return {
                    "available": True,
                    "executable": str(candidate),
                    "source": "desktop-install",
                    "reason": None,
                    "reasonCode": "BROWSER_EXECUTABLE_RESOLVED",
                    "resolutionTrace": resolution_trace,
                }
        except OSError:
            continue

    return {
        "available": False,
        "executable": None,
        "source": None,
        "reason": f"No usable {browser_name} executable was discovered.",
        "reasonCode": "BROWSER_EXECUTABLE_NOT_FOUND",
        "resolutionTrace": resolution_trace,
    }


__all__ = ["RESOLUTION_REASON_CODES", "resolve_browser_executable"]
