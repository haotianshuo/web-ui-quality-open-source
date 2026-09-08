import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

_RELEASE_SPEC = importlib.util.spec_from_file_location("wuq_release_script", Path(__file__).resolve().parents[1] / "scripts" / "release.py")
assert _RELEASE_SPEC is not None and _RELEASE_SPEC.loader is not None
release = importlib.util.module_from_spec(_RELEASE_SPEC)
_RELEASE_SPEC.loader.exec_module(release)
from web_ui_quality.change_budget import build_change_budget, evaluate_change_budget
from web_ui_quality.control_intent import parse_control_intent
from web_ui_quality.evidence_graph import build_evidence_graph
from web_ui_quality.intent_router import route_user_intent
from web_ui_quality.outcome_verification import combine_repair_verification
from web_ui_quality.risk_tier import classify_risk_tier


def test_repair_specialty_is_not_downgraded_to_read_only_audit():
    cases = [
        ("修复响应式断点错位", "RESPONSIVE"),
        ("修复无障碍按钮问题", "ACCESSIBILITY"),
        ("修复性能问题", "PERFORMANCE"),
        ("优化这个页面的响应式布局", "RESPONSIVE"),
    ]
    for text, specialty in cases:
        routed = route_user_intent(text)
        control = parse_control_intent(text)
        assert routed["taskIntent"] == "REPAIR_SMALL"
        assert routed["intent"] == "fix"
        assert routed["specialty"] == specialty
        assert routed["writeRequested"] is True
        assert routed["readOnlyRequired"] is False
        assert routed["writeAuthorized"] is False
        assert control["action"] == "FIX"
        assert control["mutation"] == "HOST_GATED"
        assert control["requiresHostApproval"] is True


def test_explicit_read_only_overrides_specialty_and_optimization_language():
    routed = route_user_intent("不要改代码，只检查响应式问题")
    control = parse_control_intent("不要改代码，只检查响应式问题")
    assert routed["taskIntent"] == "EXPLAIN"
    assert routed["specialty"] == "RESPONSIVE"
    assert routed["writeRequested"] is False
    assert routed["readOnlyRequired"] is True
    assert control["action"] == "CHECK"
    assert control["mutation"] == "FORBIDDEN"

    routed = route_user_intent("告诉我这个页面应该怎么优化")
    control = parse_control_intent("告诉我这个页面应该怎么优化")
    assert routed["intent"] == "inspect"
    assert routed["writeRequested"] is False
    assert routed["readOnlyRequired"] is True
    assert control["mutation"] == "FORBIDDEN"


def test_protected_scope_clause_does_not_cancel_repair_action():
    text = "修复订单页移动端错位，不要修改登录逻辑"
    routed = route_user_intent(text)
    control = parse_control_intent(text)
    assert routed["taskIntent"] == "REPAIR_SMALL"
    assert routed["specialty"] is None
    assert control["action"] == "FIX"
    assert "登录逻辑" in control["protectedScope"]


def test_security_repair_remains_t4_without_granting_authority():
    routed = route_user_intent("修复登录权限菜单")
    risk = classify_risk_tier("修复登录权限菜单", source_scope=["src/auth/RoleMenu.tsx"])
    assert routed["taskIntent"] == "REPAIR_SMALL"
    assert routed["specialty"] == "SECURITY"
    assert routed["writeAuthorized"] is False
    assert risk["tier"] == "T4"
    assert risk["requiresExplicitUserApproval"] is True
    assert risk["hostWriteStillRequired"] is True


def test_budget_block_cannot_be_upgraded_by_other_green_gates():
    budget = build_change_budget(
        "只修 Button.tsx",
        risk_tier="T1",
        explicit_files=["src/Button.tsx"],
    )
    gate = evaluate_change_budget(
        budget,
        changed_files=["src/Button.tsx", "src/App.tsx"],
        changed_lines=20,
    )
    assert gate["status"] == "BLOCKED"

    decision = combine_repair_verification(
        browser_outcome_status="IMPROVEMENT_CLAIM_ALLOWED",
        project_tool_status="PASS",
        patch_quality_status="QUALITY_OK",
        project_drift_status="PASS",
        change_budget_status=gate["status"],
    )
    assert decision["status"] == "NOT_VERIFIED"
    assert "CHANGE_BUDGET_EXCEEDED" in decision["blockers"]


def test_missing_host_receipt_keeps_evidence_chain_incomplete():
    result = {
        "mode": "FIX_AND_VERIFY",
        "status": "VERIFIED",
        "taskGoal": {"goal": "repair"},
        "projectBaseline": {"baselineDigest": "baseline"},
        "before": {"status": "PASS"},
        "scopeBaseline": {"files": ["src/Button.tsx"]},
        "riskTier": {"tier": "T1"},
        "changeBudget": {"status": "PASS"},
        "after": {"status": "PASS"},
        "projectToolGate": {"status": "PASS"},
        "patchQuality": {"status": "QUALITY_OK"},
        "projectDriftGate": {"status": "PASS"},
        "comparison": {"status": "IMPROVEMENT_CLAIM_ALLOWED"},
        "repairVerification": {"status": "VERIFIED"},
        # hostWriteReceipt intentionally omitted
    }
    graph = build_evidence_graph(result)
    assert graph["status"] == "INCOMPLETE"
    assert "host-write-receipt" in graph["requiredMissing"]


def test_archive_audit_allows_historical_rc_heading_only_in_history_surface():
    audit = release._audit_entries([
        ("web-ui-quality/references/history/README.md", b"## 4.0.0-rc.1 Closure\n", 0o644),
    ])
    assert audit["status"] == "PASS"
    with pytest.raises(SystemExit):
        release._audit_entries([("web-ui-quality/README.md", b"## 4.0.0-rc.1 Closure\n", 0o644)])


def test_archive_audit_still_rejects_historical_rc_heading():
    with pytest.raises(SystemExit):
        release._audit_entries([
            ("web-ui-quality/README.md", b"## 3.2.0 RC1\n", 0o644),
        ])


def test_release_run_keeps_default_timeout_for_ordinary_commands(monkeypatch):
    observed = {}

    def fake_run(*_args, **kwargs):
        observed.update(kwargs)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(release.subprocess, "run", fake_run)
    release._run(["python", "ordinary-gate.py"])

    assert observed["timeout"] == release.DEFAULT_GATE_TIMEOUT_SECONDS == 180


def test_release_validate_uses_full_gate_worker_timeout_with_cleanup_margin(monkeypatch):
    observed = {}

    monkeypatch.setattr(release, "_validate_identity", lambda: None)
    monkeypatch.setattr(release, "_validate_python", lambda: 0)
    monkeypatch.setattr(release, "_entries", lambda: [])
    monkeypatch.setattr(release, "_audit_entries", lambda _entries: {"status": "PASS"})

    def fake_run(command, env=None, *, timeout_s=release.DEFAULT_GATE_TIMEOUT_SECONDS):
        observed.update(command=command, env=env, timeout_s=timeout_s)

    monkeypatch.setattr(release, "_run", fake_run)
    result = release.validate()

    assert result["status"] == "PASS"
    assert observed["command"][-4:] == ["scripts/release_gate.py", "--mode", "full", "--compact"]
    assert observed["timeout_s"] == release.FULL_RELEASE_GATE_TIMEOUT_SECONDS == 960
    assert observed["timeout_s"] > release.DEFAULT_GATE_TIMEOUT_SECONDS
