from __future__ import annotations

import pytest

from web_ui_quality.task_intent_adapter import normalize_task_intent


@pytest.mark.parametrize(
    ("text", "public_intent", "internal_intent"),
    (
        ("看看这个页面哪里有问题", "CHECK", "DIAGNOSE"),
        ("check this page", "CHECK", "DIAGNOSE"),
        ("只解释，不改代码", "EXPLAIN", "EXPLAIN"),
        ("read only", "EXPLAIN", "EXPLAIN"),
        ("修一下移动端按钮错位", "REPAIR", "REPAIR_SMALL"),
        ("请修改按钮颜色", "REPAIR", "REPAIR_SMALL"),
        ("please change the button color", "REPAIR", "REPAIR_SMALL"),
        ("帮我调整移动端布局", "REPAIR", "REPAIR_SMALL"),
        ("验证刚才的修改", "VERIFY_ONLY", "VERIFY_ONLY"),
        ("regression check", "VERIFY_ONLY", "VERIFY_ONLY"),
        ("重新设计这个产品", "REPAIR", "TRANSFORM"),
        ("what changed on this page", "CHECK", "DIAGNOSE"),
        ("", "CHECK", "DIAGNOSE"),
    ),
)
def test_short_request_routing_matrix(text: str, public_intent: str, internal_intent: str) -> None:
    result = normalize_task_intent(text)
    assert result["taskIntent"] == public_intent
    assert result["internalTaskIntent"] == internal_intent
    assert result["writeAuthorized"] is False


def test_write_request_requires_host_and_conflicting_read_only_wins() -> None:
    repair = normalize_task_intent("请修改按钮颜色")
    assert repair["writeRequested"] is True
    assert repair["requiresHostApproval"] is True
    assert repair["readOnlyRequired"] is False

    conflict = normalize_task_intent("请修改按钮颜色，但不要修改任何文件")
    assert conflict["taskIntent"] == "REPAIR"
    assert conflict["conflictStatus"] == "INTENT_CONFLICT"
    assert conflict["writeRequested"] is True
    assert conflict["writeAuthorized"] is False
    assert conflict["mutation"] == "FORBIDDEN"
