from __future__ import annotations

import json
from pathlib import Path

import pytest

from web_ui_quality.contracts import ContractViolation, digest_json, hash_file
from web_ui_quality.design_intelligence import generate_design_candidates
from web_ui_quality.host_bridge import require_verified_host_write, verify_host_write_receipt
from web_ui_quality.project_baseline import build_project_baseline, build_scope_baseline, compare_project_baseline
from web_ui_quality.project_tool_boundary import (
    require_verified_host_tool_result,
    plan_project_tool_execution,
    verify_host_tool_result,
)

ROOT = Path(__file__).resolve().parents[1]


def test_large_project_target_coverage_is_independent_of_global_scan_limit(tmp_path: Path):
    project = tmp_path / "legacy"
    project.mkdir()
    for index in range(5001):
        (project / f"file-{index:04d}.css").write_text(f"a{{z-index:{index}}}", encoding="utf-8")
    target = "file-5000.css"
    baseline = build_project_baseline(project, target_files=[target])
    comparison = compare_project_baseline(baseline, project, target_files=[target])

    assert baseline["truncated"] is True
    assert baseline["completenessStatus"] == "INDETERMINATE"
    assert baseline["targetCoverage"]["status"] == "COMPLETE"
    assert target in {row["path"] for row in baseline["files"]}
    assert comparison["status"] == "TARGET_MATCH_GLOBAL_PARTIAL"
    assert comparison["patchScopeAssurance"] == "VERIFIED"
    assert comparison["requiresRebase"] is False


def test_partial_global_baseline_can_verify_exact_scope_receipt(tmp_path: Path):
    project = tmp_path / "legacy"
    project.mkdir()
    for index in range(3):
        (project / f"f{index}.css").write_text("a{}", encoding="utf-8")
    baseline = build_project_baseline(project, max_files=1)
    target = "f2.css"
    before = hash_file(project / target)
    scope = build_scope_baseline(project, baseline, source_scope=[target])
    (project / target).write_text("a{color:red}", encoding="utf-8")
    after = hash_file(project / target)
    source_scope = [target]
    candidate_digest = digest_json({"sourceScope": source_scope, "files": [{"path": target, "beforeSha256": before, "afterSha256": after}]})
    receipt = {
        "runId": "wuq-0123456789abcdef", "taskId": "t", "sessionId": "s", "findingIds": ["F1"],
        "sourceScope": source_scope, "exclusions": [], "baselineDigest": baseline["baselineDigest"],
        "planDigest": "1"*64, "toolchainDigest": "2"*64, "verificationContextDigest": "3"*64,
        "scopeBaselineDigest": scope["scopeBaselineDigest"], "patchCandidateDigest": candidate_digest,
        "files": [{"path": target, "beforeSha256": before, "afterSha256": after}],
    }
    trusted = verify_host_write_receipt(
        project, receipt, task_id="t", session_id="s", finding_ids=["F1"], source_scope=source_scope,
        exclusions=[], run_id="wuq-0123456789abcdef", baseline=baseline, plan_digest="1"*64,
        toolchain_digest="2"*64, verification_context_digest="3"*64, scope_baseline=scope,
    )
    assert require_verified_host_write(trusted) is trusted


def _tool_fixture(tmp_path: Path):
    project = tmp_path / "project"
    bin_dir = project / "node_modules" / ".bin"
    bin_dir.mkdir(parents=True)
    tool = bin_dir / "tsc"
    tool.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    return project, plan_project_tool_execution(project, "tsc", args=["--noEmit"])


def test_host_project_tool_result_is_bound_to_exact_plan_and_binary(tmp_path: Path):
    project, plan = _tool_fixture(tmp_path)
    receipt = {
        "planDigest": plan["planDigest"], "tool": "tsc", "executableSha256": plan["executableSha256"],
        "argv": plan["argv"], "cwd": ".", "exitCode": 0, "stdout": "", "stderr": "",
        "timedOut": False, "networkPolicyEnforced": True, "resourcePolicyEnforced": True,
        "filesystemPolicy": plan["filesystemPolicy"], "filesystemPolicyEnforced": True, "unexpectedWrites": [],
    }
    trusted = verify_host_tool_result(project, plan, receipt)
    assert trusted.to_dict()["status"] == "PASS"
    assert trusted.to_dict()["evidenceAuthority"] == "CONDITIONAL_PROJECT_TOOL_EVIDENCE"
    assert require_verified_host_tool_result(trusted) is trusted


def test_host_project_tool_result_rejects_tampered_argv(tmp_path: Path):
    project, plan = _tool_fixture(tmp_path)
    receipt = {
        "planDigest": plan["planDigest"], "tool": "tsc", "executableSha256": plan["executableSha256"],
        "argv": ["--emitDeclarationOnly"], "cwd": ".", "exitCode": 0, "stdout": "", "stderr": "",
        "timedOut": False, "networkPolicyEnforced": True, "resourcePolicyEnforced": True,
        "filesystemPolicy": plan["filesystemPolicy"], "filesystemPolicyEnforced": True, "unexpectedWrites": [],
    }
    with pytest.raises(ContractViolation) as caught:
        verify_host_tool_result(project, plan, receipt)
    assert caught.value.code == "PROJECT_TOOL_RESULT_MISMATCH"


def test_candidate_recommendation_is_not_silent_selection_and_gate_is_honest():
    result = generate_design_candidates({"experienceModel": {"primaryTask": "Review orders", "risk": "high"}})
    scores = {row["id"]: row["score"] for row in result["candidates"]}
    assert result["selected"] is None
    assert result["recommended"] in scores
    assert scores[result["recommended"]] == max(scores.values())
    assert result["differenceGate"]["gateType"] == "DECLARED_DIRECTION_CONTRACT_DIFFERENCE"
    assert "does not prove rendered" in result["differenceGate"]["claimBoundary"]


def test_current_root_api_matches_explicit_alpha10_manifest():
    import web_ui_quality
    manifest = json.loads((ROOT / "runtime/python/web_ui_quality/public-api-manifest.json").read_text(encoding="utf-8"))
    assert manifest["packageVersion"] == "4.3.0"
    assert manifest["kernelVersion"] == "4.2.3"
    assert manifest["kernelBaseVersion"] == "4.0.0-rc.1"
    assert manifest["count"] == len(web_ui_quality.__all__)
    assert manifest["exports"] == list(web_ui_quality.__all__)
    assert manifest["stable"] == ["run"]


def test_public_help_points_to_run_not_compatibility_entry():
    text = (ROOT / "runtime/python/web_ui_quality/__main__.py").read_text(encoding="utf-8")
    assert "默认使用 experience-fix" not in text
    assert "普通任务使用 run" in text
