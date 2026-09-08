#!/usr/bin/env python3
"""Small RC closure acceptance for the consolidated repair trust chain."""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime" / "python"
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from web_ui_quality.change_budget import build_change_budget, evaluate_change_budget  # noqa: E402
from web_ui_quality.control_intent import parse_control_intent  # noqa: E402
from web_ui_quality.evidence_graph import build_evidence_graph  # noqa: E402
from web_ui_quality.intent_router import route_user_intent  # noqa: E402
from web_ui_quality.outcome_verification import combine_repair_verification  # noqa: E402
from web_ui_quality.release_info import PACKAGE_VERSION, configure_stdout  # noqa: E402
from web_ui_quality.risk_tier import classify_risk_tier  # noqa: E402

EXPECTED_VERSION = "4.3.0"


def _intent(text: str, *, task: str, specialty: str | None, control: str, read_only: bool) -> str:
    routed = route_user_intent(text)
    parsed = parse_control_intent(text)
    if routed.get("taskIntent") != task:
        raise RuntimeError(f"taskIntent={routed.get('taskIntent')!r}")
    if routed.get("specialty") != specialty:
        raise RuntimeError(f"specialty={routed.get('specialty')!r}")
    if parsed.get("action") != control:
        raise RuntimeError(f"control action={parsed.get('action')!r}")
    if bool(routed.get("readOnlyRequired")) is not read_only:
        raise RuntimeError(f"readOnlyRequired={routed.get('readOnlyRequired')!r}")
    if routed.get("writeAuthorized") is not False:
        raise RuntimeError("intent routing must never grant write authority")
    return f"{task}+{specialty or 'GENERAL'} / {control}"


def _budget_gate() -> str:
    budget = build_change_budget("只修 Button.tsx", risk_tier="T1", explicit_files=["src/Button.tsx"])
    gate = evaluate_change_budget(budget, changed_files=["src/Button.tsx", "src/App.tsx"], changed_lines=20)
    decision = combine_repair_verification(
        browser_outcome_status="IMPROVEMENT_CLAIM_ALLOWED",
        project_tool_status="PASS",
        patch_quality_status="QUALITY_OK",
        project_drift_status="PASS",
        change_budget_status=gate["status"],
    )
    if gate["status"] != "BLOCKED" or decision["status"] != "NOT_VERIFIED":
        raise RuntimeError("Change Budget no longer blocks VERIFIED")
    return "scope expansion BLOCKED -> final NOT_VERIFIED"


def _receipt_graph() -> str:
    graph = build_evidence_graph({
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
    })
    if graph.get("status") != "INCOMPLETE" or "host-write-receipt" not in graph.get("requiredMissing", []):
        raise RuntimeError("missing Host receipt no longer leaves the evidence graph incomplete")
    return "missing Host receipt -> Evidence Graph INCOMPLETE"


def _t4() -> str:
    routed = route_user_intent("修复登录权限菜单")
    risk = classify_risk_tier("修复登录权限菜单", source_scope=["src/auth/RoleMenu.tsx"])
    if routed.get("taskIntent") != "REPAIR_SMALL" or routed.get("specialty") != "SECURITY":
        raise RuntimeError("security repair routing differs")
    if risk.get("tier") != "T4" or risk.get("requiresExplicitUserApproval") is not True:
        raise RuntimeError("security repair no longer escalates to T4")
    return "REPAIR+SECURITY -> T4, Host authority still required"


def main() -> int:
    configure_stdout()
    checks = [
        ("CV-001", lambda: EXPECTED_VERSION if PACKAGE_VERSION == EXPECTED_VERSION else (_ for _ in ()).throw(RuntimeError(PACKAGE_VERSION))),
        ("CV-002", lambda: _intent("修复响应式断点错位", task="REPAIR_SMALL", specialty="RESPONSIVE", control="FIX", read_only=False)),
        ("CV-003", lambda: _intent("不要改代码，只检查响应式问题", task="EXPLAIN", specialty="RESPONSIVE", control="CHECK", read_only=True)),
        ("CV-004", lambda: _intent("修复无障碍按钮问题", task="REPAIR_SMALL", specialty="ACCESSIBILITY", control="FIX", read_only=False)),
        ("CV-005", lambda: _intent("优化这个页面的响应式布局", task="REPAIR_SMALL", specialty="RESPONSIVE", control="FIX", read_only=False)),
        ("CV-006", _t4),
        ("CV-007", lambda: _intent("修复订单页移动端错位，不要修改登录逻辑", task="REPAIR_SMALL", specialty=None, control="FIX", read_only=False)),
        ("CV-008", _budget_gate),
        ("CV-009", _receipt_graph),
    ]
    rows = []
    failed = False
    for check_id, fn in checks:
        try:
            rows.append({"id": check_id, "status": "PASS", "detail": fn()})
        except Exception as error:
            failed = True
            rows.append({"id": check_id, "status": "FAIL", "detail": f"{type(error).__name__}: {error}"})
    print(json.dumps({"status": "FAIL" if failed else "PASS", "version": EXPECTED_VERSION, "checks": rows}, ensure_ascii=False, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
