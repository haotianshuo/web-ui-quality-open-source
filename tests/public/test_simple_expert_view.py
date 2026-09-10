from __future__ import annotations

import io

from web_ui_quality import __main__ as cli
from web_ui_quality.task_result import build_task_result


def _render(task: dict[str, object]) -> str:
    stream = io.StringIO()
    cli._emit_human_repair_report({"taskResult": task}, stream=stream)
    return stream.getvalue()


def test_default_view_answers_the_five_user_questions_without_protocol_terms() -> None:
    task = build_task_result(
        {
            "status": "SCOPE_NOT_CONFIRMED",
            "mode": "FIX_AND_VERIFY",
            "runId": "simple-view-public",
            "taskId": "simple-view-public",
            "repairReport": {
                "status": "SCOPE_NOT_CONFIRMED",
                "request": "修复移动端按钮错位",
                "answers": {
                    "whatWasReproduced": "移动端按钮位置异常",
                    "whatChanged": [],
                    "rootCause": "源码归属尚未确认",
                    "remainingRiskOrUnknown": ["浏览器验证未完成"],
                },
                "nextAction": "补充 Finding 后继续",
            },
        },
        request="修复移动端按钮错位",
    )
    rendered = _render(task)

    for section in ("结果：", "改了什么：", "验证了什么：", "下一步："):
        assert section in rendered
    for internal in ("Receipt", "HMAC", "packageTreeDigest", "runBindingDigest", "Host Result JSON"):
        assert internal not in rendered
    assert "未验证" in rendered or "验证" in rendered


def test_machine_task_result_retains_detail_for_non_default_consumers() -> None:
    task = build_task_result(
        {
            "status": "NOT_VERIFIED",
            "mode": "FIX_AND_VERIFY",
            "runId": "expert-view-public",
            "taskId": "expert-view-public",
            "hostWriteReceipt": {"protocol": "V3", "receiptDigest": "redacted-test-digest"},
            "repairReport": {"status": "NOT_VERIFIED", "evidenceGraph": {"nodes": ["finding"]}},
        },
        request="verify the patch",
    )

    assert task["kind"] == "REPAIR"
    assert task["repairReport"]["evidenceGraph"] == {"nodes": ["finding"]}
    assert task["review"]["available"] is False
