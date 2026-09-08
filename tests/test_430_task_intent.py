from __future__ import annotations

import pytest

from web_ui_quality.contracts import ContractViolation
from web_ui_quality.experience_fix import run_experience_fix
from web_ui_quality.task_intent_adapter import normalize_task_intent


@pytest.mark.parametrize(
    "text",
    (
        "帮我修好，但不要修改任何文件",
        "fix it but do not change any files",
    ),
)
def test_conflicting_write_and_read_only_request_is_fail_closed(text: str) -> None:
    result = normalize_task_intent(text)

    assert result["conflictStatus"] == "INTENT_CONFLICT"
    assert result["taskIntent"] == "REPAIR"
    assert result["mutation"] == "FORBIDDEN"
    assert result["writeAuthorized"] is False


def test_protected_subscope_is_preserved_without_whole_task_conflict() -> None:
    result = normalize_task_intent("修复手机端响应式，但不要碰登录逻辑")

    assert result["taskIntent"] == "REPAIR"
    assert result["conflictStatus"] == "NONE"
    assert result["writeRequested"] is True
    assert any("登录" in item for item in result["protectedScope"])


def test_experience_fix_stops_before_creating_artifacts_on_intent_conflict(tmp_path) -> None:
    with pytest.raises(ContractViolation) as caught:
        run_experience_fix(
            tmp_path / "project",
            tmp_path / "artifacts",
            request="帮我修好，但不要修改任何文件",
            task_id="task-intent-430",
            session_id="session-intent-430",
        )

    assert caught.value.code == "INTENT_CONFLICT"
    assert not (tmp_path / "project").exists()
    assert not (tmp_path / "artifacts").exists()
