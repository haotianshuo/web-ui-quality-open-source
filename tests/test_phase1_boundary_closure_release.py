from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _distribution_module():
    path = ROOT / "scripts" / "verify_distribution.py"
    spec = importlib.util.spec_from_file_location("wuq_verify_distribution_alpha2", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_alpha2_package_identity_is_distinct_from_frozen_kernel():
    from web_ui_quality.release_info import KERNEL_BASE_VERSION, KERNEL_VERSION, PACKAGE_VERSION
    plugin = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert PACKAGE_VERSION == "4.3.0"
    assert KERNEL_VERSION == "4.2.3"
    assert KERNEL_BASE_VERSION == "4.0.0-rc.1"
    assert plugin["version"] == PACKAGE_VERSION
    assert f'version = "{PACKAGE_VERSION}"' in pyproject


def test_composite_release_manifest_verifies_current_tree():
    module = _distribution_module()
    module._verify_composite_release(ROOT)


def test_composite_release_manifest_detects_phase1_tamper(tmp_path):
    clone = tmp_path / "web-ui-quality"
    shutil.copytree(
        ROOT,
        clone,
        ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", "dist", "build"),
    )
    target = clone / "runtime" / "python" / "web_ui_quality" / "phase1_claims.py"
    target.write_text(target.read_text(encoding="utf-8") + "\n# tamper regression\n", encoding="utf-8")
    module = _distribution_module()
    with pytest.raises(RuntimeError, match="package tree integrity mismatch"):
        module._verify_composite_release(clone)


def test_release_gate_uses_auto_discovered_browser_for_expectation(monkeypatch):
    module = _distribution_module()
    monkeypatch.setattr(
        module,
        "browser_runtime_capability",
        lambda _explicit: {"available": True, "executable": "C:/Program Files/Chrome/chrome.exe", "source": "auto"},
    )
    available, effective, capability = module._resolve_browser_for_gate(None)
    assert available is True
    assert effective == Path("C:/Program Files/Chrome/chrome.exe")
    assert capability["source"] == "auto"
