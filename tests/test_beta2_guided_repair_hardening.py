from __future__ import annotations

import json
from pathlib import Path

import pytest

from web_ui_quality.contracts import ContractViolation, digest_json
from web_ui_quality.outcome_verification import combine_repair_verification
from web_ui_quality.project_baseline import build_project_baseline, compare_project_baseline, classify_post_repair_drift
from web_ui_quality.project_tool_boundary import plan_project_tool_execution, verify_host_tool_result, summarise_host_tool_results
from web_ui_quality.schema_validation import validate_instance

ROOT = Path(__file__).resolve().parents[1]


def _tool_fixture(tmp_path: Path):
    project = tmp_path / "project"
    bin_dir = project / "node_modules" / ".bin"
    bin_dir.mkdir(parents=True)
    tool = bin_dir / "tsc"
    tool.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    plan = plan_project_tool_execution(project, "tsc", args=["--noEmit"])
    return project, plan


def _receipt(plan: dict, **overrides):
    value = {
        "schemaVersion": "1",
        "planDigest": plan["planDigest"],
        "tool": plan["tool"],
        "executableSha256": plan["executableSha256"],
        "argv": plan["argv"],
        "cwd": plan["cwd"],
        "runBinding": plan.get("runBinding", {"runId": None, "taskId": None, "sessionId": None}),
        "exitCode": 0,
        "stdout": "",
        "stderr": "",
        "timedOut": False,
        "networkPolicyEnforced": True,
        "resourcePolicyEnforced": True,
        "filesystemPolicy": plan["filesystemPolicy"],
        "filesystemPolicyEnforced": True,
        "unexpectedWrites": [],
    }
    value.update(overrides)
    return value


def test_project_tool_plan_requires_read_only_project_and_result_schema(tmp_path: Path):
    project, plan = _tool_fixture(tmp_path)
    assert plan["schemaVersion"] == "2"
    assert plan["filesystemPolicy"] == "READ_ONLY_PROJECT"
    assert plan["allowedWriteRoots"] == []
    plan_schema = json.loads((ROOT / "schemas" / "project-tool-execution.schema.json").read_text(encoding="utf-8"))
    validate_instance(plan, plan_schema, base_dir=ROOT / "schemas")
    receipt = _receipt(plan)
    result_schema = json.loads((ROOT / "schemas" / "host-project-tool-result.schema.json").read_text(encoding="utf-8"))
    validate_instance(receipt, result_schema, base_dir=ROOT / "schemas")
    trusted = verify_host_tool_result(project, plan, receipt)
    assert trusted.to_dict()["status"] == "PASS"



def test_project_tool_result_cannot_replay_across_repair_runs(tmp_path: Path):
    project = tmp_path / "replay"
    bin_dir = project / "node_modules" / ".bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "tsc").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    plan = plan_project_tool_execution(
        project, "tsc", args=["--noEmit"], run_id="wuq-run-a", task_id="task-a", session_id="session-a"
    )
    receipt = _receipt(plan)
    receipt["runBinding"] = {"runId": "wuq-run-b", "taskId": "task-a", "sessionId": "session-a"}
    with pytest.raises(ContractViolation) as caught:
        verify_host_tool_result(project, plan, receipt)
    assert caught.value.code == "PROJECT_TOOL_RESULT_MISMATCH"


def test_filesystem_policy_not_confirmed_is_not_verified(tmp_path: Path):
    project, plan = _tool_fixture(tmp_path)
    receipt = _receipt(plan, filesystemPolicyEnforced=False)
    trusted = verify_host_tool_result(project, plan, receipt)
    row = trusted.to_dict()
    assert row["status"] == "NOT_VERIFIED"
    assert row["filesystemPolicyEnforced"] is False


def test_tool_unexpected_write_is_fail_even_when_exit_zero(tmp_path: Path):
    project, plan = _tool_fixture(tmp_path)
    receipt = _receipt(plan, unexpectedWrites=["src/unrelated.ts"])
    trusted = verify_host_tool_result(project, plan, receipt)
    gate = summarise_host_tool_results([trusted])
    assert gate["status"] == "FAIL"
    assert trusted.to_dict()["unexpectedWrites"] == ["src/unrelated.ts"]


def test_unexpected_project_drift_blocks_visual_success(tmp_path: Path):
    project = tmp_path / "app"
    project.mkdir()
    target = project / "Button.tsx"
    unrelated = project / "unrelated.ts"
    target.write_text("export const B=1\n", encoding="utf-8")
    unrelated.write_text("export const U=1\n", encoding="utf-8")
    baseline = build_project_baseline(project, target_files=["Button.tsx"])
    target.write_text("export const B=2\n", encoding="utf-8")
    unrelated.write_text("export const U=2\n", encoding="utf-8")
    comparison = compare_project_baseline(baseline, project, target_files=["Button.tsx"])
    drift = classify_post_repair_drift(comparison, expected_write_paths=["Button.tsx"])
    assert drift["status"] == "UNEXPECTED_DRIFT"
    assert drift["unexpected"] == ["unrelated.ts"]
    final = combine_repair_verification(
        browser_outcome_status="IMPROVEMENT_CLAIM_ALLOWED",
        project_tool_status="PASS",
        patch_quality_status="QUALITY_OK",
        project_drift_status=drift["status"],
    )
    assert final["status"] == "FAIL"
    assert "UNEXPECTED_PROJECT_DRIFT" in final["blockers"]


def _fake_repair_result(status: str = "VERIFIED") -> dict:
    return {
        "status": status,
        "activeCapabilities": ["internal-should-not-be-default"],
        "repairVerification": {"status": status},
        "repairReport": {
            "schemaVersion": "1",
            "status": status,
            "request": "修复订单页",
            "answers": {
                "whatYouAsked": "修复订单页",
                "whatWasReproduced": "已复现移动端错位",
                "rootCause": "SharedTable width",
                "whatChanged": ["src/SharedTable.tsx"],
                "howVerified": ["Browser PASS"],
                "remainingRiskOrUnknown": [],
            },
            "verificationSummary": {
                "overall": status,
                "browser": "IMPROVEMENT_CLAIM_ALLOWED",
                "projectTools": "PASS",
                "patchQuality": "QUALITY_OK",
                "projectDrift": "EXPECTED_ONLY",
                "hostWrite": "HOST_WRITE_VERIFIED",
            },
            "nextAction": "可以继续下一个问题。",
            "authentication": "anonymous",
            "taskState": {"runId": "wuq-test", "resumable": True, "resumeHint": "继续上次任务"},
            "claimBoundary": "bounded evidence",
        },
    }


def test_run_default_is_human_report_not_internal_json(tmp_path: Path, monkeypatch, capsys):
    from web_ui_quality import __main__ as cli
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.setattr(cli, "run_experience_fix", lambda *a, **k: _fake_repair_result("VERIFIED"))
    code = cli.main(["run", str(project), "修复订单页"])
    out = capsys.readouterr().out
    assert code == 0
    assert "结果：" in out and "已完成并验证" in out
    assert "验证了什么：" in out
    assert "activeCapabilities" not in out
    assert "Evidence graph" not in out
    assert "receipt protocol" not in out.casefold()
    assert not out.lstrip().startswith("{")


def test_run_json_is_stable_machine_contract(tmp_path: Path, monkeypatch, capsys):
    from web_ui_quality import __main__ as cli
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.setattr(cli, "run_experience_fix", lambda *a, **k: _fake_repair_result("VERIFIED"))
    code = cli.main(["run", str(project), "修复订单页", "--json"])
    value = json.loads(capsys.readouterr().out)
    assert code == 0
    assert value["executionStatus"] == "COMPLETED"
    assert value["repairStatus"] == "VERIFIED"
    assert "activeCapabilities" not in value
    assert value["repairReport"]["status"] == "VERIFIED"


@pytest.mark.parametrize(
    ("status", "expected"),
    [("VERIFIED", 0), ("REVIEW_REQUIRED", 2), ("NOT_VERIFIED", 3), ("FAIL", 4)],
)
def test_ci_exit_contract(tmp_path: Path, monkeypatch, capsys, status: str, expected: int):
    from web_ui_quality import __main__ as cli
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.setattr(cli, "run_experience_fix", lambda *a, **k: _fake_repair_result(status))
    code = cli.main(["run", str(project), "修复订单页", "--ci"])
    value = json.loads(capsys.readouterr().out)
    assert code == expected
    assert value["executionStatus"] == "COMPLETED"
    assert value["repairStatus"] == status


def test_after_receipt_restores_exact_run_instead_of_latest(tmp_path: Path, monkeypatch, capsys):
    from web_ui_quality import __main__ as cli
    project = tmp_path / "project"
    project.mkdir()
    artifacts = project / ".wuq" / "runs"
    exact = artifacts / "wuq-exact"
    latest = artifacts / "wuq-latest"
    exact.mkdir(parents=True)
    latest.mkdir(parents=True)
    stable_task_id = f"cli-task-{digest_json({'target': str(project.resolve())})[:16]}"
    receipt = tmp_path / "receipt.json"
    receipt.write_text(json.dumps({"runId": "wuq-exact"}), encoding="utf-8")

    def fake_load(path):
        assert Path(path) == exact
        return {"taskId": stable_task_id, "sessionId": "session-exact"}

    def forbidden_latest(*args, **kwargs):
        raise AssertionError("latest compatible lookup must not run when receipt.runId is present")

    observed = {}
    def fake_run(*args, **kwargs):
        observed.update(kwargs)
        return _fake_repair_result("VERIFIED")

    monkeypatch.setattr(cli, "load_experience_run", fake_load)
    monkeypatch.setattr(cli, "find_latest_compatible_run", forbidden_latest)
    monkeypatch.setattr(cli, "run_experience_fix", fake_run)
    code = cli.main([
        "run", str(project), "验证修复", "--after-url", "http://example.test/",
        "--host-write-receipt", str(receipt), "--json",
    ])
    capsys.readouterr()
    assert code == 0
    assert Path(observed["existing_run"]) == exact
    assert observed["session_id"] == "session-exact"


def test_main_repair_flow_unexpected_unrelated_drift_blocks_verified(tmp_path: Path, monkeypatch):
    from web_ui_quality.contracts import hash_file
    from web_ui_quality.experience_fix import run_experience_fix

    project = tmp_path / "app-e2e"
    project.mkdir()
    source = project / "index.tsx"
    unrelated = project / "unrelated.ts"
    source.write_text("export const App=()=> <main>before</main>\n", encoding="utf-8")
    unrelated.write_text("export const U=1\n", encoding="utf-8")
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
                "journeyId": "primary", "status": "PASS" if is_after else "FAIL",
                "journey": [{"action": "open", "target": "/"}],
                "runs": [{"status": "PASS" if is_after else "FAIL"}],
            },
            "findings": [], "topFindings": [],
            "deliveryConclusion": "after improved" if is_after else "before failed", "open": "index.html",
        }
        output.mkdir(parents=True, exist_ok=True)
        (output / "smart-acceptance-report.json").write_text(json.dumps(report), encoding="utf-8")
        return report

    monkeypatch.setattr("web_ui_quality.experience_fix.run_smart_acceptance", fake_acceptance)
    artifacts = tmp_path / "artifacts-e2e"
    run_experience_fix(
        project, artifacts, request="修复页面", mode="FIX_AND_VERIFY", task_id="task", session_id="session",
        url="http://example.test/", files=["index.tsx"],
    )
    run_dir = next(artifacts.glob("wuq-*"))
    plan_result = json.loads((run_dir / "report" / "fix-plan-result.json").read_text(encoding="utf-8"))
    binding = plan_result["hostReceiptBinding"]
    scope = plan_result["scopeBaseline"]
    before = next(row["sha256"] for row in scope["files"] if row["path"] == "index.tsx")
    source.write_text("export const App=()=> <main>after</main>\n", encoding="utf-8")
    # Simulate a project-owned tool/plugin mutating an unrelated source file.
    unrelated.write_text("export const U=2\n", encoding="utf-8")
    after = hash_file(source)
    files = [{"path": "index.tsx", "beforeSha256": before, "afterSha256": after}]
    host_receipt = {
        **binding,
        "patchCandidateDigest": digest_json({"sourceScope": ["index.tsx"], "files": files}),
        "files": files,
    }
    tool_plan = plan_result["projectToolPlans"][0]
    host_tool_result = _receipt(tool_plan)

    result = run_experience_fix(
        project, artifacts, request="修复页面", mode="FIX_AND_VERIFY", task_id="task", session_id="session",
        url="http://example.test/", existing_run=run_dir, after_url="http://example.test/", files=["index.tsx"],
        host_write_receipt=host_receipt, host_tool_results=[host_tool_result],
    )
    assert result["comparison"]["status"] == "IMPROVEMENT_CLAIM_ALLOWED"
    assert result["projectToolGate"]["status"] == "PASS"
    assert result["projectDriftGate"]["status"] == "UNEXPECTED_DRIFT"
    assert result["projectDriftGate"]["unexpected"] == ["unrelated.ts"]
    assert result["repairVerification"]["status"] == "FAIL"
    assert "UNEXPECTED_PROJECT_DRIFT" in result["repairVerification"]["blockers"]
    assert result["repairReport"]["verificationSummary"]["projectDrift"] == "UNEXPECTED_DRIFT"
