from __future__ import annotations

import importlib.util
from pathlib import Path


def _release_gate_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "release_gate.py"
    spec = importlib.util.spec_from_file_location("wuq_release_gate_430_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_python_browser_qualification_is_independent_and_live() -> None:
    gate = _release_gate_module()
    worker = {
        "stdoutSha256": "b" * 64,
        "browserReceipt": {
            "status": "PASS",
            "test": "tests/test_420_browser_security.py",
            "sha256": "a" * 64,
        },
        "execution": {"commandDigest": "c" * 64},
    }
    result = gate._python_browser_qualification(
        {"playwright": "PASS", "browserRuntime": "PASS"},
        [
            {
                "command": ["python", "-m", "pytest", "-q", "tests/test_420_browser_security.py"],
                "status": "PASS",
                "exitCode": 0,
            }
        ],
        "tests/test_420_browser_security.py",
        worker,
    )

    assert result["runtime"] == "python-playwright"
    assert result["executed"] is True
    assert result["status"] == "PASS"
    assert result["browserBacked"] is True
    assert result["receiptSha256"] == "a" * 64
    assert result["executionRecord"]["commandDigest"] == "c" * 64


def test_python_browser_qualification_does_not_infer_execution_from_preflight() -> None:
    gate = _release_gate_module()
    result = gate._python_browser_qualification(
        {"playwright": "PASS", "browserRuntime": "PASS"},
        [],
        "tests/test_420_browser_security.py",
    )

    assert result["moduleAvailable"] is True
    assert result["browserExecutableAvailable"] is True
    assert result["executed"] is False
    assert result["status"] == "NOT_VERIFIED"


def test_python_browser_qualification_rejects_pass_without_live_receipt() -> None:
    gate = _release_gate_module()
    result = gate._python_browser_qualification(
        {"playwright": "PASS", "browserRuntime": "PASS"},
        [{"command": ["python", "-m", "pytest", "tests/test_420_browser_security.py"], "status": "PASS", "exitCode": 0}],
        "tests/test_420_browser_security.py",
        {"stdoutSha256": "b" * 64, "execution": {"commandDigest": "c" * 64}, "browserReceipt": None},
    )
    assert result["status"] == "NOT_VERIFIED"
    assert result["browserBacked"] is False
