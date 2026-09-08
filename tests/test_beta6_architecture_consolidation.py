from pathlib import Path

from web_ui_quality.change_budget import build_change_budget, evaluate_change_budget
from web_ui_quality.evidence_graph import build_evidence_graph
from web_ui_quality.fix_workflow import prepare_fix_workflow
from web_ui_quality.intent_router import route_user_intent
from web_ui_quality.outcome_verification import combine_repair_verification
from web_ui_quality.risk_tier import classify_risk_tier


def test_intent_router_distinguishes_verify_explain_repair_and_transform():
    verify = route_user_intent("检查刚才 Codex 改的有没有回归")
    assert verify["taskIntent"] == "VERIFY_ONLY"
    assert verify["intent"] == "inspect"
    assert verify["readOnlyRequired"] is True
    assert verify["writeAuthorized"] is False

    explain = route_user_intent("不要改代码，只告诉我这个页面哪里有问题")
    assert explain["taskIntent"] == "EXPLAIN"
    assert explain["intent"] == "inspect"
    assert explain["writeRequested"] is False

    repair = route_user_intent("修复订单页移动端错位，不要动登录逻辑")
    assert repair["taskIntent"] == "REPAIR_SMALL"
    assert repair["intent"] == "fix"
    assert repair["writeRequested"] is True
    assert repair["writeAuthorized"] is False

    transform = route_user_intent("整体重新设计这个旧 CRM，但先不要改原项目")
    assert transform["taskIntent"] == "TRANSFORM"
    assert transform["intent"] == "redesign"
    assert transform["productDiscoveryRequired"] is True


def test_risk_tier_does_not_treat_protected_non_goal_as_mutation():
    result = classify_risk_tier(
        "修复订单页移动端错位，不要动登录逻辑",
        source_scope=["src/orders/layout.css"],
    )
    assert result["tier"] == "T0"
    assert result["hostWriteStillRequired"] is True


def test_risk_tier_escalates_actual_auth_scope():
    result = classify_risk_tier(
        "修复登录后角色菜单状态",
        source_scope=["src/auth/RoleMenu.tsx"],
    )
    assert result["tier"] == "T4"
    assert result["requiresExplicitUserApproval"] is True
    assert result["minimumVerificationProfile"] == "FULL"


def test_change_budget_blocks_explicit_scope_expansion():
    budget = build_change_budget(
        "只修这个按钮，其他地方不要动",
        risk_tier="T1",
        explicit_files=["src/Button.tsx"],
    )
    gate = evaluate_change_budget(
        budget,
        changed_files=["src/Button.tsx", "src/App.tsx"],
    )
    assert gate["status"] == "BLOCKED"
    assert any("EXPLICIT_SCOPE_EXCEEDED" in item for item in gate["blockers"])


def test_change_budget_is_an_independent_verified_gate():
    decision = combine_repair_verification(
        browser_outcome_status="IMPROVEMENT_CLAIM_ALLOWED",
        project_tool_status="PASS",
        patch_quality_status="QUALITY_OK",
        project_drift_status="PASS",
        change_budget_status="BLOCKED",
    )
    assert decision["status"] == "NOT_VERIFIED"
    assert "CHANGE_BUDGET_EXCEEDED" in decision["blockers"]


def test_fix_workflow_binds_risk_budget_and_plan_digest(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    target = project / "Button.tsx"
    target.write_text("export const Button = () => null\n", encoding="utf-8")
    report = prepare_fix_workflow(
        project,
        tmp_path / "out",
        files=["Button.tsx"],
        request="只修这个按钮的移动端间距",
    )
    assert report["scopeConfirmed"] is True
    assert report["riskTier"]["tier"] in {"T0", "T1"}
    assert report["changeBudget"]["maxFiles"] == 1
    assert report["changeBudgetGate"]["status"] == "PASS"
    assert len(report["planDigest"]) == 64


def test_evidence_graph_exposes_verified_dependency_chain():
    result = {
        "mode": "FIX_AND_VERIFY",
        "status": "VERIFIED",
        "taskGoal": {"goal": "fix"},
        "projectBaseline": {"baselineDigest": "a" * 64},
        "before": {"status": "PASS"},
        "scopeBaseline": {"scopeBaselineDigest": "b" * 64},
        "riskTier": {"tier": "T1"},
        "changeBudget": {"maxFiles": 3},
        "hostWriteReceipt": {"files": [{"path": "Button.tsx"}]},
        "after": {"status": "PASS"},
        "projectToolGate": {"status": "PASS"},
        "patchQuality": {"status": "QUALITY_OK"},
        "projectDriftGate": {"status": "PASS"},
        "comparison": {"status": "IMPROVEMENT_CLAIM_ALLOWED"},
        "repairVerification": {"status": "VERIFIED"},
    }
    graph = build_evidence_graph(result)
    assert graph["status"] == "COMPLETE_VERIFIED_CHAIN"
    assert graph["requiredMissing"] == []
    assert any(edge == {"from": "host-write-receipt", "to": "repair-verification"} for edge in graph["edges"])
    assert len(graph["graphDigest"]) == 64
