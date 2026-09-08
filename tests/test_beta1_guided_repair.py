from __future__ import annotations

import json
from pathlib import Path

import pytest

from web_ui_quality.contracts import ContractViolation, digest_json, hash_file
from web_ui_quality.host_bridge import verify_host_write_receipt
from web_ui_quality.outcome_verification import combine_repair_verification
from web_ui_quality.project_baseline import build_project_baseline, build_scope_baseline, compare_project_baseline
from web_ui_quality.project_tool_boundary import (
    plan_project_tool_execution,
    summarise_host_tool_results,
    verify_host_tool_result,
)


def _legacy_project(tmp_path: Path) -> tuple[Path, str]:
    project = tmp_path / "legacy"
    target_dir = project / "packages" / "orders" / "src"
    target_dir.mkdir(parents=True)
    target = "packages/orders/src/Button.tsx"
    (project / target).write_text("export const Button=()=> <button>OK</button>\n", encoding="utf-8")
    (project / "packages" / "orders" / "tsconfig.json").write_text('{"compilerOptions":{"strict":true}}', encoding="utf-8")
    (project / "package.json").write_text('{"devDependencies":{"typescript":"5.9.0"}}', encoding="utf-8")
    return project, target


def test_partial_large_repo_tracks_target_critical_context(tmp_path: Path):
    project, target = _legacy_project(tmp_path)
    # Force the global scan to stop before the nested target/config context.
    (project / "000.css").write_text("a{}", encoding="utf-8")
    baseline = build_project_baseline(project, max_files=1, target_files=[target])
    coverage = baseline["criticalContextCoverage"]
    assert coverage["status"] == "COMPLETE"
    assert "packages/orders/tsconfig.json" in coverage["indexed"]
    assert "package.json" in coverage["indexed"]
    assert baseline["targetCoverage"]["status"] == "COMPLETE"

    (project / "packages" / "orders" / "tsconfig.json").write_text('{"compilerOptions":{"strict":false}}', encoding="utf-8")
    comparison = compare_project_baseline(baseline, project, target_files=[target])
    assert comparison["status"] == "REVALIDATION_REQUIRED"
    assert comparison["patchScopeAssurance"] == "NOT_VERIFIED"
    assert "packages/orders/tsconfig.json" in comparison["criticalContextDrift"]


def test_scope_baseline_blocks_host_receipt_when_critical_context_drifts(tmp_path: Path):
    project, target = _legacy_project(tmp_path)
    baseline = build_project_baseline(project, max_files=1, target_files=[target])
    scope = build_scope_baseline(project, baseline, source_scope=[target])
    before = hash_file(project / target)
    (project / target).write_text("export const Button=()=> <button>Fixed</button>\n", encoding="utf-8")
    after = hash_file(project / target)
    (project / "packages" / "orders" / "tsconfig.json").write_text('{"compilerOptions":{"strict":false}}', encoding="utf-8")
    files = [{"path": target, "beforeSha256": before, "afterSha256": after}]
    receipt = {
        "runId": "wuq-0123456789abcdef", "taskId": "t", "sessionId": "s", "findingIds": ["F1"],
        "sourceScope": [target], "exclusions": [], "baselineDigest": baseline["baselineDigest"],
        "planDigest": "1"*64, "toolchainDigest": "2"*64, "verificationContextDigest": "3"*64,
        "scopeBaselineDigest": scope["scopeBaselineDigest"],
        "patchCandidateDigest": digest_json({"sourceScope": [target], "files": files}),
        "files": files,
    }
    with pytest.raises(ContractViolation) as caught:
        verify_host_write_receipt(
            project, receipt, task_id="t", session_id="s", finding_ids=["F1"], source_scope=[target],
            exclusions=[], run_id="wuq-0123456789abcdef", baseline=baseline, plan_digest="1"*64,
            toolchain_digest="2"*64, verification_context_digest="3"*64, scope_baseline=scope,
        )
    assert caught.value.code == "CRITICAL_CONTEXT_DRIFT"


def _tool_result(tmp_path: Path, *, exit_code: int = 0, timed_out: bool = False, policy: bool = True):
    project = tmp_path / f"tool-{exit_code}-{int(timed_out)}-{int(policy)}"
    bin_dir = project / "node_modules" / ".bin"
    bin_dir.mkdir(parents=True)
    tool = bin_dir / "tsc"
    tool.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    plan = plan_project_tool_execution(project, "tsc", args=["--noEmit"])
    receipt = {
        "planDigest": plan["planDigest"], "tool": plan["tool"], "executableSha256": plan["executableSha256"],
        "argv": plan["argv"], "cwd": plan["cwd"], "exitCode": exit_code, "stdout": "", "stderr": "type error" if exit_code else "",
        "timedOut": timed_out, "networkPolicyEnforced": policy, "resourcePolicyEnforced": policy,
        "filesystemPolicy": plan["filesystemPolicy"], "filesystemPolicyEnforced": policy, "unexpectedWrites": [],
    }
    return verify_host_tool_result(project, plan, receipt)


def test_failed_project_tool_cannot_be_overridden_by_visual_improvement(tmp_path: Path):
    trusted = _tool_result(tmp_path, exit_code=2)
    gate = summarise_host_tool_results([trusted])
    decision = combine_repair_verification(
        browser_outcome_status="IMPROVEMENT_CLAIM_ALLOWED",
        project_tool_status=gate["status"],
        patch_quality_status="QUALITY_OK",
    )
    assert gate["status"] == "FAIL"
    assert decision["status"] == "FAIL"
    assert "PROJECT_TOOL_FAILED" in decision["blockers"]


def test_unverified_project_tool_cannot_be_overridden_by_visual_improvement(tmp_path: Path):
    trusted = _tool_result(tmp_path, exit_code=0, timed_out=True)
    gate = summarise_host_tool_results([trusted])
    decision = combine_repair_verification(
        browser_outcome_status="IMPROVEMENT_CLAIM_ALLOWED",
        project_tool_status=gate["status"],
        patch_quality_status="QUALITY_OK",
    )
    assert gate["status"] == "NOT_VERIFIED"
    assert decision["status"] == "NOT_VERIFIED"


def test_patch_quality_risk_never_becomes_verified():
    decision = combine_repair_verification(
        browser_outcome_status="IMPROVEMENT_CLAIM_ALLOWED",
        project_tool_status="PASS",
        patch_quality_status="QUALITY_RISK",
    )
    assert decision["status"] == "REVIEW_REQUIRED"
    assert "PATCH_QUALITY_RISK" in decision["warnings"]


def test_run_cli_accepts_one_sentence_positional_request(tmp_path: Path, monkeypatch, capsys):
    from web_ui_quality import __main__ as cli
    project = tmp_path / "project"
    project.mkdir()
    observed = {}

    def fake_run(*args, **kwargs):
        observed.update(kwargs)
        return {"status": "PASS"}

    monkeypatch.setattr(cli, "run_experience_fix", fake_run)
    code = cli.main(["run", str(project), "修复订单页移动端错位，不要动登录逻辑", "--compact"])
    assert code == 0
    assert observed["request"] == "修复订单页移动端错位，不要动登录逻辑"
    capsys.readouterr()


def test_main_repair_flow_tool_fail_overrides_browser_improvement(tmp_path: Path, monkeypatch):
    from web_ui_quality.experience_fix import run_experience_fix

    project = tmp_path / "app"
    project.mkdir()
    source = project / "index.tsx"
    source.write_text("export const App=()=> <main>before</main>\n", encoding="utf-8")
    (project / "package.json").write_text('{"devDependencies":{"typescript":"5.9.0"}}', encoding="utf-8")
    bin_dir = project / "node_modules" / ".bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "tsc").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")

    def fake_acceptance(*args, **kwargs):
        output = Path(kwargs["output_dir"])
        is_after = output.name == "after"
        report = {
            "status": "PASS" if is_after else "FAIL",
            "pageHealth": {"pageStatus": "PASS" if is_after else "TASK_FAILED"},
            "journey": {
                "journeyId": "primary",
                "status": "PASS" if is_after else "FAIL",
                "journey": [{"action": "open", "target": "/"}],
                "runs": [{"status": "PASS" if is_after else "FAIL"}],
            },
            "findings": [], "topFindings": [],
            "deliveryConclusion": "after improved" if is_after else "before failed",
            "open": "index.html",
        }
        output.mkdir(parents=True, exist_ok=True)
        (output / "smart-acceptance-report.json").write_text(json.dumps(report), encoding="utf-8")
        return report

    monkeypatch.setattr("web_ui_quality.experience_fix.run_smart_acceptance", fake_acceptance)
    artifacts = tmp_path / "artifacts"
    first = run_experience_fix(
        project, artifacts, request="修复页面", mode="FIX_AND_VERIFY",
        task_id="task", session_id="session", url="http://example.test/", files=["index.tsx"],
    )
    run_dir = next(artifacts.glob("wuq-*"))
    plan_result = json.loads((run_dir / "report" / "fix-plan-result.json").read_text(encoding="utf-8"))
    binding = plan_result["hostReceiptBinding"]
    scope = plan_result["scopeBaseline"]
    before = next(row["sha256"] for row in scope["files"] if row["path"] == "index.tsx")
    source.write_text("export const App=()=> <main>after</main>\n", encoding="utf-8")
    after = hash_file(source)
    files = [{"path": "index.tsx", "beforeSha256": before, "afterSha256": after}]
    host_receipt = {
        **binding,
        "patchCandidateDigest": digest_json({"sourceScope": ["index.tsx"], "files": files}),
        "files": files,
    }
    tool_plan = plan_result["projectToolPlans"][0]
    host_tool_result = {
        "planDigest": tool_plan["planDigest"], "tool": tool_plan["tool"],
        "executableSha256": tool_plan["executableSha256"], "argv": tool_plan["argv"], "cwd": tool_plan["cwd"],
        "runBinding": tool_plan["runBinding"],
        "exitCode": 2, "stdout": "", "stderr": "TS2322: type error", "timedOut": False,
        "networkPolicyEnforced": True, "resourcePolicyEnforced": True,
        "filesystemPolicy": tool_plan["filesystemPolicy"], "filesystemPolicyEnforced": True, "unexpectedWrites": [],
    }

    second = run_experience_fix(
        project, artifacts, request="修复页面", mode="FIX_AND_VERIFY",
        task_id="task", session_id="session", url="http://example.test/", existing_run=run_dir,
        after_url="http://example.test/", files=["index.tsx"], host_write_receipt=host_receipt,
        host_tool_results=[host_tool_result],
    )
    assert first["runId"] == second["runId"]
    assert second["comparison"]["status"] == "IMPROVEMENT_CLAIM_ALLOWED"
    assert second["projectToolGate"]["status"] == "FAIL"
    assert second["repairVerification"]["status"] == "FAIL"
    assert second["status"] == "FAIL"
    assert second["repairReport"]["verificationSummary"]["projectTools"] == "FAIL"
    assert "不要把当前结果当成已修复" in second["repairReport"]["nextAction"]
