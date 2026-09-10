from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from web_ui_quality import __main__ as cli
from web_ui_quality import smart_acceptance
from web_ui_quality.contracts import ContractViolation
from web_ui_quality.error_classifier import classify_runtime_error
from web_ui_quality.experience_fix import run_experience_fix
from web_ui_quality.repair_report import build_repair_report
from web_ui_quality.smart_acceptance import _preflight, run_smart_acceptance
from web_ui_quality.task_intent_adapter import normalize_task_intent
from web_ui_quality.task_result import build_task_result


def _render(task: dict, *, source_result: dict | None = None) -> str:
    stream = io.StringIO()
    cli._emit_human_repair_report(source_result or {"taskResult": task}, stream=stream)
    return stream.getvalue()


def test_check_and_explain_flow_is_read_only_and_human_summarized() -> None:
    check = normalize_task_intent("帮我看看这个页面哪里有问题")
    explain = normalize_task_intent("只解释这个页面哪里有问题")

    assert check["taskIntent"] == "CHECK"
    assert explain["taskIntent"] == "EXPLAIN"
    assert check["writeAuthorized"] is False
    assert explain["readOnlyRequired"] is True

    task = build_task_result(
        {
            "status": "COMPLETED",
            "runId": "plain-check-430",
            "taskId": "plain-check-430",
            "mode": "CHECK",
            "before": {"topFindings": [{"summary": "移动端按钮被裁切"}]},
        },
        request="帮我看看这个页面哪里有问题",
    )
    rendered = _render(task)
    assert "结果：" in rendered
    assert "改了什么：" in rendered
    assert "验证了什么：" in rendered
    assert "下一步：" in rendered


def test_repair_and_verify_only_flows_keep_authority_separate() -> None:
    repair = normalize_task_intent("把最严重的三个问题修掉")
    verify = normalize_task_intent("验证刚才的修改有没有回归")

    assert repair["taskIntent"] == "REPAIR"
    assert repair["writeRequested"] is True
    assert repair["requiresHostApproval"] is True
    assert repair["writeAuthorized"] is False
    assert verify["taskIntent"] == "VERIFY_ONLY"
    assert verify["writeRequested"] is False
    assert verify["writeAuthorized"] is False


def test_login_guidance_is_browser_facing_and_does_not_require_protocol_files() -> None:
    result = classify_runtime_error(http_status=401)
    text = " ".join(
        [str(result.get("message") or result.get("userMessage") or "")]
        + [str(item) for item in result.get("actions", result.get("recoveryActions", []))]
    )

    assert result["category"] == "AUTH_REQUIRED"
    assert "登录" in text or "权限" in text
    assert "storage-state.json" not in text
    assert "Receipt" not in text


def test_browser_unavailable_is_not_verified_and_has_plain_language(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        smart_acceptance,
        "playwright_capability",
        lambda _executable=None: {"available": False, "reason": "test-only unavailable"},
    )

    preflight = _preflight(
        None,
        url="https://example.test/login",
        environment={"effectivePolicy": "local"},
    )

    assert preflight["status"] == "NOT_VERIFIED"
    assert preflight["canContinue"] is False
    assert "Browser" in preflight["plainSummary"]
    assert "源码" in preflight["plainSummary"]
    assert "Traceback" not in preflight["plainSummary"]


def test_intent_conflict_fails_closed_before_artifacts(tmp_path: Path) -> None:
    with pytest.raises(ContractViolation) as caught:
        run_experience_fix(
            tmp_path / "project",
            tmp_path / "artifacts",
            request="帮我修好，但不要修改任何文件",
            task_id="plain-conflict-430",
            session_id="plain-conflict-session-430",
        )

    assert caught.value.code == "INTENT_CONFLICT"
    assert not (tmp_path / "project").exists()
    assert not (tmp_path / "artifacts").exists()


def test_clean_read_only_request_runs_inspection_without_repair_artifacts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "index.html").write_text("<main>clean</main>\n", encoding="utf-8")

    def fake_acceptance(*args, **kwargs):
        output = Path(kwargs["output_dir"])
        report = {
            "status": "PASS",
            "pageHealth": {"pageStatus": "PASS"},
            "preflight": {"status": "READY", "blockers": [], "warnings": [], "browser": {"available": True}},
            "runtime": {"records": []},
            "journey": {"status": "PASS", "journey": [], "runs": []},
            "findings": [],
            "topFindings": [],
            "deliveryConclusion": "clean",
            "open": "index.html",
        }
        output.mkdir(parents=True, exist_ok=True)
        (output / "smart-acceptance-report.json").write_text(json.dumps(report), encoding="utf-8")
        return report

    monkeypatch.setattr("web_ui_quality.experience_fix.run_smart_acceptance", fake_acceptance)
    result = run_experience_fix(
        project,
        tmp_path / "artifacts",
        request="检查这个页面有没有横向滚动；没有问题就明确说明，不要为了找问题修改文件。",
        mode="FIX_AND_VERIFY",
        task_id="plain-clean-check-430",
        session_id="plain-clean-check-session-430",
    )

    assert result["mode"] == "CHECK"
    assert result["controlIntent"]["action"] == "CHECK"
    assert result["taskResult"]["kind"] == "INSPECTION"
    assert result["taskResult"]["outcome"] == "COMPLETED"
    assert "fixPlan" not in result
    assert "repairReport" not in result
    assert result.get("hostWriteReceipt") is None
    assert "HOST_RECEIPT_REQUIRED" not in json.dumps(result, ensure_ascii=False)


def test_safe_defaults_are_recorded_in_a_short_settings_summary(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    report = run_smart_acceptance(project, output_dir=tmp_path / "acceptance")

    summary = report["coverageSummary"]["settingsSummary"]
    assert summary["viewports"] == ["390x844", "768x1024", "1440x900"]
    assert summary["checkDepth"] == "页面健康 + Top 3 + 一次安全旅程"
    assert summary["riskLevel"] == "LOW_READ_ONLY"
    assert "已使用安全默认设置" in summary["plainSummary"]
    assert report["preflight"]["status"] == "NOT_VERIFIED"


def test_failure_recovery_offers_continue_retry_and_narrow_scope_without_manual_files() -> None:
    report = build_repair_report(
        request="修复移动端错位",
        status="NOT_VERIFIED",
        reproduced="Before recorded",
        root_cause="Unknown",
        changes=(),
        verification=(),
        risks=("Browser evidence missing",),
        unverified=("After not executed",),
        resumable=True,
        run_id="plain-recovery-430",
    )
    next_action = report["nextAction"]
    assert "继续上次任务" in next_action
    assert "重试" in next_action
    assert "缩小范围" in next_action
    assert "Receipt" not in next_action

    task = build_task_result(
        {
            "status": "FAIL",
            "runId": "plain-recovery-430",
            "taskId": "plain-recovery-430",
            "mode": "FIX_AND_VERIFY",
            "taskGoal": {"goal": "修复移动端错位", "nonGoals": ["登录逻辑"]},
            "repairVerification": {"status": "FAIL", "blockers": ["Browser"], "warnings": []},
            "repairReport": report,
        }
    )
    assert task["protectedScope"] == ["登录逻辑"]
    rendered = _render(task)
    assert "继续上次任务" in rendered
    assert "重试" in rendered
    assert "缩小范围" in rendered


def test_default_human_surface_hides_protocol_details() -> None:
    task = {
        "kind": "REPAIR",
        "outcome": "NOT_VERIFIED",
        "changes": [],
        "verification": {"browser": "NOT_MEASURED", "hostWrite": "HOST_WRITE_RECEIPT_V3_REQUIRED"},
        "coverage": {"patchScope": "UNKNOWN", "target": "UNKNOWN", "criticalContext": "UNKNOWN", "globalProject": "UNKNOWN"},
        "nextAction": "重试或缩小范围后继续上次任务",
        "taskState": {"resumable": True},
    }
    rendered = _render(task)
    for internal in ("Receipt", "HMAC", "packageTreeDigest", "runBindingDigest", "Host Result JSON"):
        assert internal not in rendered
