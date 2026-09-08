from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

from web_ui_quality.browser_locator import resolve_browser_executable
from web_ui_quality.browser_provider import unavailable_browser_capability
from web_ui_quality.capability_registry import _python_playwright


ROOT = Path(__file__).resolve().parents[1]


def _release_gate_module():
    path = ROOT / "scripts" / "release_gate.py"
    spec = importlib.util.spec_from_file_location("wuq_release_gate_alpha16_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_browser_resolution_exposes_stable_codes_and_fallback_trace(tmp_path, monkeypatch):
    existing = tmp_path / "chrome.exe"
    existing.write_bytes(b"stub")
    selected = resolve_browser_executable("chromium", explicit=existing)
    assert selected["available"] is True
    assert selected["reasonCode"] == "BROWSER_EXECUTABLE_RESOLVED"
    assert selected["resolutionTrace"] == ["explicit"]

    missing = resolve_browser_executable("chromium", explicit=tmp_path / "missing.exe")
    assert missing["available"] is False
    assert missing["reasonCode"] == "EXPLICIT_BROWSER_NOT_FOUND"
    assert missing["resolutionTrace"] == ["explicit"]

    bundled = tmp_path / "bundled-chrome"
    bundled.write_bytes(b"stub")
    fallback = resolve_browser_executable(
        "chromium", playwright_browser_type=SimpleNamespace(executable_path=str(bundled))
    )
    assert fallback["source"] == "playwright"
    assert fallback["reasonCode"] == "BROWSER_EXECUTABLE_RESOLVED"
    assert fallback["resolutionTrace"] == ["playwright"]

    monkeypatch.setattr("web_ui_quality.browser_locator.shutil.which", lambda _name: None)
    monkeypatch.setattr("web_ui_quality.browser_locator._desktop_candidates", lambda _name: [])
    unavailable = resolve_browser_executable("chromium")
    assert unavailable["reasonCode"] == "BROWSER_EXECUTABLE_NOT_FOUND"
    assert unavailable["resolutionTrace"] == ["system-path", "desktop-install"]


def test_python_capability_reason_code_distinguishes_driver_from_browser(tmp_path, monkeypatch):
    chrome = tmp_path / "chrome.exe"
    chrome.write_bytes(b"stub")
    monkeypatch.setattr("web_ui_quality.capability_registry._module_present", lambda _name: False)
    result = _python_playwright(chrome)
    assert result["available"] is False
    assert result["reasonCode"] == "PYTHON_PLAYWRIGHT_MODULE_MISSING"
    assert result["resolutionTrace"] == ["explicit"]


def test_node_capability_reason_code_distinguishes_missing_module(monkeypatch):
    import web_ui_quality.production_validation as module

    monkeypatch.setattr(module.shutil, "which", lambda _name: "node")
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            stdout=json.dumps({"module": False, "error": "MODULE_NOT_FOUND"}),
            stderr="",
            returncode=0,
        ),
    )
    monkeypatch.setattr(
        module,
        "resolve_browser_executable",
        lambda *_args, **_kwargs: {
            "available": True,
            "executable": "C:/chrome.exe",
            "source": "desktop-install",
            "reasonCode": "BROWSER_EXECUTABLE_RESOLVED",
            "resolutionTrace": ["system-path", "desktop-install"],
        },
    )
    result = module.browser_runtime_capability()
    assert result["available"] is False
    assert result["moduleAvailable"] is False
    assert result["reasonCode"] == "NODE_PLAYWRIGHT_MODULE_MISSING"
    assert result["resolutionTrace"] == ["system-path", "desktop-install"]


def test_release_gate_reports_dependency_reason_codes(monkeypatch):
    gate = _release_gate_module()
    monkeypatch.setattr(gate, "_safe_find_spec", lambda *_args, **_kwargs: (True, None))
    monkeypatch.setattr(
        gate,
        "resolve_browser_executable",
        lambda *_args, **_kwargs: {
            "available": False,
            "reason": "No usable chromium executable was discovered.",
            "reasonCode": "BROWSER_EXECUTABLE_NOT_FOUND",
            "resolutionTrace": ["system-path", "desktop-install"],
        },
    )
    result = gate._dependency_preflight("full")
    assert result["reasonCode"] == "RELEASE_GATE_DEPENDENCY_MISSING"
    assert result["browserReasonCode"] == "BROWSER_EXECUTABLE_NOT_FOUND"
    assert result["dependencyReasonCodes"] == ["BROWSER_EXECUTABLE_NOT_FOUND"]
    assert result["browserResolutionTrace"] == ["system-path", "desktop-install"]


def test_unavailable_provider_has_a_machine_reason_code():
    result = unavailable_browser_capability("playwright", "optional dependency is absent")
    assert result["result"] == "NOT_VERIFIED"
    assert result["reasonCode"] == "BROWSER_PROVIDER_UNAVAILABLE"
