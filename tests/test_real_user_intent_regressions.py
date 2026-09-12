from __future__ import annotations

import pytest

from web_ui_quality.task_intent_adapter import normalize_task_intent


@pytest.mark.parametrize(
    ("text", "allowed", "protected"),
    (
        ("只允许修改 styles.css，其他文件禁止修改", "styles.css", "其他文件"),
        ("只能改 app.js，别碰任何其他文件", "app.js", "任何其他文件"),
        ("可以修，但是只准改 index.html", "index.html", None),
        ("只修改这个组件，配置文件不要碰", "这个组件", "配置文件"),
        ("Only modify styles.css. Do not touch other files.", "styles.css", "other files"),
        ("You may fix it, but change app.js only.", "app.js", None),
        ("Modify index.html and leave everything else unchanged.", "index.html", "everything else"),
        ("Only this file may be changed.", "this file", None),
        ("styles.css だけ変更してください", "styles.css", None),
    ),
)
def test_scoped_write_requests_remain_host_gated_and_not_read_only(
    text: str, allowed: str, protected: str | None
) -> None:
    result = normalize_task_intent(text)

    assert result["taskIntent"] == "REPAIR"
    assert result["internalTaskIntent"] == "REPAIR_SMALL"
    assert result["writeRequested"] is True
    assert result["readOnlyRequired"] is False
    assert result["mutation"] == "HOST_GATED"
    assert result["scopeIntent"] == "WRITE_ALLOWED_WITH_SCOPE"
    assert result["requiresHostApproval"] is True
    assert result["writeAuthorized"] is False
    assert allowed in result["allowedWriteScope"]
    if protected:
        assert any(protected in item for item in result["protectedScope"])


@pytest.mark.parametrize(
    "text",
    (
        "change nothing",
        "touch nothing",
        "make no changes",
        "leave everything unchanged",
        "no edits, please",
        "sin modificar ningún archivo",
        "何も変更しないでください",
    ),
)
def test_negative_mutation_language_is_whole_task_read_only(text: str) -> None:
    result = normalize_task_intent(text)

    assert result["taskIntent"] in {"CHECK", "EXPLAIN"}
    assert result["writeRequested"] is False
    assert result["readOnlyRequired"] is True
    assert result["mutation"] == "FORBIDDEN"
    assert result["scopeIntent"] == "READ_ONLY"
    assert result["requiresHostApproval"] is False
    assert result["writeAuthorized"] is False


@pytest.mark.parametrize(
    "text",
    (
        "check whether the earlier fix caused regressions",
        "check if the previous fix introduced a regression",
        "verify that the previous fix did not break mobile layout",
        "confirm the earlier repair still works",
        "check the fix for regressions",
        "see whether the fix introduced new errors",
        "comprueba si la corrección anterior causó una regresión",
    ),
)
def test_verification_requests_never_become_repairs(text: str) -> None:
    result = normalize_task_intent(text)

    assert result["taskIntent"] == "VERIFY_ONLY"
    assert result["internalTaskIntent"] == "VERIFY_ONLY"
    assert result["writeRequested"] is False
    assert result["readOnlyRequired"] is True
    assert result["mutation"] == "FORBIDDEN"
    assert result["requiresHostApproval"] is False
    assert result["writeAuthorized"] is False


def test_compound_repair_and_no_change_request_is_an_explicit_conflict() -> None:
    result = normalize_task_intent("repair this issue, but touch nothing in the project")

    assert result["taskIntent"] == "REPAIR"
    assert result["writeRequested"] is True
    assert result["readOnlyRequired"] is True
    assert result["conflictStatus"] == "INTENT_CONFLICT"
    assert result["scopeIntent"] == "INTENT_CONFLICT"
    assert result["mutation"] == "FORBIDDEN"
    assert result["requiresHostApproval"] is False
    assert result["writeAuthorized"] is False


def test_polite_tails_punctuation_and_newlines_do_not_change_semantics() -> None:
    base = normalize_task_intent("Fix the button, but do not modify any files")
    variants = (
        "Fix the button, but do not modify any files, please.",
        "Fix the button, but do not modify any files now",
        "Fix the button, but do not modify any files\nthanks",
        "Fix the button, but do not modify any files; if possible",
    )
    fields = ("taskIntent", "writeRequested", "readOnlyRequired", "mutation", "scopeIntent", "conflictStatus")
    for variant in variants:
        result = normalize_task_intent(variant)
        assert {field: result[field] for field in fields} == {field: base[field] for field in fields}
        assert result["writeAuthorized"] is False


def test_plain_repair_remains_a_host_gated_request() -> None:
    result = normalize_task_intent("fix the button please")

    assert result["taskIntent"] == "REPAIR"
    assert result["writeRequested"] is True
    assert result["readOnlyRequired"] is False
    assert result["mutation"] == "HOST_GATED"
    assert result["requiresHostApproval"] is True
    assert result["writeAuthorized"] is False
