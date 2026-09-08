from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from web_ui_quality.context_packet import build_relevant_context_packet, context_recall
from web_ui_quality.contracts import ContractViolation, digest_json
from web_ui_quality.host_bridge import (
    TrustedHostWriteReceipt,
    build_repair_scope_revert_plan,
    validate_repair_scope_revert_plan,
)
from web_ui_quality.project_baseline import build_project_baseline
from web_ui_quality.schema_validation import validate_instance, validation_errors
from web_ui_quality.task_result import build_task_result

ROOT = Path(__file__).resolve().parents[1]


def _verified_result(*, global_coverage: str = "PARTIAL") -> dict:
    return {
        "status": "VERIFIED",
        "runId": "wuq-beta3",
        "taskId": "task-beta3",
        "mode": "FIX_AND_VERIFY",
        "taskGoal": {"goal": "修复订单页", "nonGoals": ["登录逻辑"]},
        "projectBaseline": {
            "completenessStatus": "INDETERMINATE" if global_coverage == "PARTIAL" else "COMPLETE",
            "targetCoverage": {"status": "COMPLETE"},
            "criticalContextCoverage": {"status": "COMPLETE"},
        },
        "projectDriftGate": {
            "status": "EXPECTED_ONLY",
            "globalCoverage": global_coverage,
            "targetCoverageComplete": True,
            "criticalContextCoverageComplete": True,
        },
        "repairVerification": {"status": "VERIFIED", "blockers": [], "warnings": []},
        "repairReport": {
            "schemaVersion": "1",
            "status": "VERIFIED",
            "request": "修复订单页",
            "answers": {
                "whatYouAsked": "修复订单页",
                "whatWasReproduced": "移动端错位已复现",
                "rootCause": "SharedTable breakpoint",
                "whatChanged": ["src/SharedTable.tsx"],
                "howVerified": ["Browser PASS"],
                "remainingRiskOrUnknown": [],
            },
            "verificationSummary": {
                "overall": "VERIFIED", "browser": "IMPROVEMENT_CLAIM_ALLOWED",
                "projectTools": "PASS", "patchQuality": "QUALITY_OK",
                "projectDrift": "EXPECTED_ONLY", "hostWrite": "HOST_WRITE_VERIFIED",
            },
            "nextAction": "可以继续下一个问题。",
            "authentication": "anonymous",
            "taskState": {"runId": "wuq-beta3", "resumable": True, "resumeHint": "继续上次任务"},
            "claimBoundary": "bounded",
        },
    }


def test_task_result_verified_requires_explicit_coverage_schema():
    value = build_task_result(_verified_result())
    schema = json.loads((ROOT / "schemas" / "task-result.schema.json").read_text(encoding="utf-8"))
    validate_instance(value, schema, base_dir=ROOT / "schemas")
    assert value["outcome"] == "VERIFIED"
    assert value["coverage"]["patchScope"] == "COMPLETE"
    assert value["coverage"]["globalProject"] == "PARTIAL"
    broken = dict(value)
    broken.pop("coverage")
    assert validation_errors(broken, schema, base_dir=ROOT / "schemas")


def test_verified_human_report_discloses_partial_global_coverage(monkeypatch, tmp_path: Path, capsys):
    from web_ui_quality import __main__ as cli
    project = tmp_path / "app"
    project.mkdir()
    monkeypatch.setattr(cli, "run_experience_fix", lambda *a, **k: _verified_result())
    code = cli.main(["run", str(project), "修复订单页"])
    out = capsys.readouterr().out
    assert code == 0
    assert "结果：" in out and "已完成并验证" in out
    assert "覆盖范围：修改范围=COMPLETE" in out
    assert "未覆盖整个仓库" in out
    assert "--expert-json" not in out


def test_check_mode_gets_human_task_report_instead_of_expert_json(monkeypatch, tmp_path: Path, capsys):
    from web_ui_quality import __main__ as cli
    project = tmp_path / "app"
    project.mkdir()
    check_result = {
        "status": "PASS", "runId": "wuq-check", "taskId": "task-check", "mode": "CHECK",
        "taskGoal": {"goal": "先别改，只看看", "nonGoals": ["登录页"]},
        "projectBaseline": {"completenessStatus": "COMPLETE", "targetCoverage": {"status": "COMPLETE"}, "criticalContextCoverage": {"status": "COMPLETE"}},
        "before": {"deliveryConclusion": "页面观察完成", "topFindings": []},
        "checkpoint": {"checkpointId": "cp"},
    }
    monkeypatch.setattr(cli, "run_experience_fix", lambda *a, **k: check_result)
    code = cli.main(["run", str(project), "先别改，只看看"])
    out = capsys.readouterr().out
    assert code == 0
    assert "结果：" in out and "已完成但部分未验证" in out
    assert "改了什么：" in out and "本次没有记录源码修改" in out
    assert "--expert-json" not in out


def test_context_packet_keeps_protected_scope_and_recalls_root_source(tmp_path: Path):
    project = tmp_path / "project"
    root = project / "src" / "components" / "TableContainer.css"
    root.parent.mkdir(parents=True)
    root.write_text(".table { overflow-x: hidden; } /* mobile table overflow */\n", encoding="utf-8")
    (project / "src" / "App.tsx").write_text("export const App=()=>null\n", encoding="utf-8")
    baseline = build_project_baseline(project)
    packet = build_relevant_context_packet(
        project,
        request="订单 mobile table overflow 被裁掉",
        task_goal={"goal": "定位表格问题", "nonGoals": ["src/auth/**"]},
        baseline=baseline,
        max_source_refs=3,
    )
    recall = context_recall(packet, ["src/components/TableContainer.css"], k=3)
    assert recall["recall"] == 1.0
    assert packet["mandatoryContext"]["protectedScope"] == ["src/auth/**"]
    assert packet["mandatoryContext"]["writeAuthority"] == "HOST_ONLY"


def _trusted_receipt() -> TrustedHostWriteReceipt:
    payload = {
        "runId": "wuq-1", "taskId": "task-1", "sessionId": "session-1",
        "files": [{"path": "src/App.tsx", "beforeSha256": "a" * 64, "afterSha256": "b" * 64}],
    }
    # Tests construct the class directly only to exercise the downstream plan;
    # process authority is intentionally opaque outside host_bridge.
    import web_ui_quality.host_bridge as bridge
    return TrustedHostWriteReceipt(payload, digest_json(payload), bridge._TRUSTED_HOST_WRITE_AUTHORITY)


def test_revert_plan_is_repair_scope_only_and_tamper_evident():
    plan = build_repair_scope_revert_plan(_trusted_receipt())
    assert plan["scope"] == "REPAIR_SCOPE"
    assert plan["runtimeMayWrite"] is False
    assert plan["hostExecutionRequired"] is True
    assert validate_repair_scope_revert_plan(plan)["status"] == "VALID"
    tampered = json.loads(json.dumps(plan))
    tampered["files"][0]["targetBeforeSha256"] = "c" * 64
    with pytest.raises(ContractViolation) as caught:
        validate_repair_scope_revert_plan(tampered)
    assert caught.value.code == "REVERT_PLAN_TAMPERED"


def test_fault_injection_harness_qualifies_infrastructure_without_fake_agent_claim():
    completed = subprocess.run(
        [sys.executable, "-B", "scripts/fault_injection_harness.py", "--self-test"],
        cwd=ROOT, text=True, encoding="utf-8", errors="replace", capture_output=True, check=True,
    )
    value = json.loads(completed.stdout)
    assert value["status"] == "PASS"
    assert value["caseCount"] >= 10
    assert value["caseCount"] == 40
    assert 0.0 <= value["contextRootSourceRecallAt5"] <= 1.0
    assert value["contextRecallStatus"] == "MEASURED_NOT_A_HARNESS_GATE"
    assert value["protectedScopeRecall"] == 1.0
    assert value["agentLoopStatus"] == "NOT_VERIFIED_HOST_AGENT"
    assert value["agentCost"] == "NOT_MEASURED"


def test_privacy_egress_policy_is_executable_release_gate():
    completed = subprocess.run(
        [sys.executable, "-B", "scripts/privacy_egress_acceptance.py"],
        cwd=ROOT, text=True, encoding="utf-8", errors="replace", capture_output=True, check=True,
    )
    value = json.loads(completed.stdout)
    assert value["status"] == "PASS"
    assert "figma_input.py" in value["explicitNetworkExceptions"]
    assert value["unapprovedNetworkImports"] == []


def test_task_result_keeps_beta2_json_aliases_while_new_fields_are_primary():
    value = build_task_result(_verified_result(global_coverage="COMPLETE"))
    assert value["executionStatus"] == "COMPLETED"
    assert value["repairStatus"] == "VERIFIED"
    assert value["repairReport"]["status"] == "VERIFIED"
    assert value["kind"] == "REPAIR"
    assert value["outcome"] == "VERIFIED"


def test_design_candidates_support_one_to_three_without_forced_padding():
    from web_ui_quality.design_intelligence import generate_design_candidates
    one = generate_design_candidates({"experienceModel": {"primaryTask": "fix one color"}}, count=1)
    two = generate_design_candidates({"experienceModel": {"primaryTask": "compare two layouts"}}, count=2)
    three = generate_design_candidates({"experienceModel": {"primaryTask": "modernize product"}}, count=3)
    assert len(one["candidates"]) == 1
    assert len(two["candidates"]) == 2
    assert len(three["candidates"]) == 3
    assert one["differenceGate"]["status"] == "PASS"
    assert one["differenceGate"]["pairwise"] == []
    assert two["selectionPolicy"]["requiredCandidateCount"] == 2
