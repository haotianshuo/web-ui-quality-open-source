from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import _ui_inventory_acceptance as inventory_acceptance
from _ui_inventory_acceptance import run_ui_inventory_acceptance


ROOT = Path(__file__).resolve().parents[1]


def test_bundled_inventory_acceptance_confirms_cross_page_visual_consistency() -> None:
    result = run_ui_inventory_acceptance()
    assert result["reportStatus"] == "PASS"
    assert all(result["checks"].values())
    assert result["checks"]["buttonStylesConsistent"]
    assert result["checks"]["driftCleared"]
    assert result["checks"]["nearColorsCleared"]


def test_bundled_inventory_acceptance_does_not_turn_environment_into_product_failure(monkeypatch) -> None:
    payload = {
        "status": "NOT_VERIFIED_ENVIRONMENT",
        "reasonCode": "BROWSER_EXECUTABLE_UNAVAILABLE",
        "reason": "synthetic unavailable browser",
        "errors": [],
        "checks": None,
        "reportStatus": "NOT_VERIFIED",
    }
    monkeypatch.setattr(
        inventory_acceptance.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=2,
            stdout=json.dumps(payload),
            stderr="",
        ),
    )
    with pytest.raises(pytest.skip.Exception):
        test_bundled_inventory_acceptance_confirms_cross_page_visual_consistency()
