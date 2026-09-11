from __future__ import annotations

import pytest

from web_ui_quality.qualification_harness import (
    expected_execution_contract,
    validate_frozen_task_result,
)


def _task(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "taskId": "Q27",
        "category": "natural-language-end-to-end",
        "oracleClass": "CLEAN_CONFIRMED",
        "property": "clean-responsive-page",
        "allowedWrites": [],
        "protectedFiles": "all-tracked",
    }
    value.update(overrides)
    return value


def test_clean_oracle_contract_selects_check_without_task_id_special_case() -> None:
    contract = expected_execution_contract(_task())

    assert contract["mode"] == "CHECK"
    assert contract["expectedClaim"] == "CLEAN_CONFIRMED"
    assert contract["readOnly"] is True


@pytest.mark.parametrize(
    ("oracle_class", "category", "allowed", "mode"),
    (
        ("REPAIRED_VERIFIED", "normal-repair", ["styles.css"], "FIX_AND_VERIFY"),
        ("REPAIRED_VERIFIED_SCOPE_PRESERVED", "scope-protected", ["styles.css"], "FIX_AND_VERIFY"),
        ("FINDING_CONFIRMED", "read-only-true-defect", [], "CHECK"),
        ("NOT_VERIFIED", "evidence-insufficient", [], "CHECK"),
    ),
)
def test_execution_mode_is_derived_from_oracle_and_task_contract(
    oracle_class: str, category: str, allowed: list[str], mode: str
) -> None:
    contract = expected_execution_contract(
        _task(taskId="arbitrary-task-name", oracleClass=oracle_class, category=category, allowedWrites=allowed)
    )

    assert contract["mode"] == mode
    assert contract["expectedClaim"] == oracle_class


def test_result_validation_uses_expected_oracle_claim_and_mode() -> None:
    task = _task(taskId="natural-language-name")
    result = {"mode": "CHECK", "taskResult": {"outcome": "CLEAN_CONFIRMED"}}

    checked = validate_frozen_task_result(task, result)

    assert checked["status"] == "PASS"
    assert checked["modeMatch"] is True
    assert checked["claimMatch"] is True


def test_result_validation_rejects_false_claim_and_mode() -> None:
    task = _task(taskId="natural-language-name")
    result = {"mode": "FIX_AND_VERIFY", "taskResult": {"outcome": "VERIFIED"}}

    checked = validate_frozen_task_result(task, result)

    assert checked["status"] == "NOT_VERIFIED"
    assert checked["modeMatch"] is False
    assert checked["claimMatch"] is False
