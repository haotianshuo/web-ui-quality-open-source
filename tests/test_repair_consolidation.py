from __future__ import annotations

import json
from pathlib import Path

import pytest

from web_ui_quality.auth_profiles import load_auth_profile, save_auth_profile
from web_ui_quality.capability_registry import _python_playwright
from web_ui_quality.contracts import ContractViolation
from web_ui_quality.experience_run import create_experience_run, seal_before
from web_ui_quality.patch_quality import evaluate_patch_quality
from web_ui_quality.project_baseline import attach_project_baseline, build_project_baseline, compare_project_baseline, load_project_baseline
from web_ui_quality.project_tool_boundary import plan_project_tool_execution
from web_ui_quality.systemic_repair import analyze_repair_scope
from web_ui_quality.verification_budget import select_verification_budget


def _run(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "src").mkdir()
    (project / "src" / "Button.tsx").write_text("export const Button=()=> <button>ok</button>\n", encoding="utf-8")
    run = create_experience_run(
        tmp_path / "artifacts", task_id="task-1", session_id="session-1", mode="FIX_AND_VERIFY",
        target={"kind": "project", "projectRoot": str(project)}, conditions={"browser": "chromium"},
    )
    return project, Path(run["runDir"])


def test_baseline_is_file_indexed_and_reuses_before_seal(tmp_path: Path):
    project, run_dir = _run(tmp_path)
    baseline = attach_project_baseline(run_dir, project)
    assert baseline["fileCount"] == 1
    assert baseline["files"][0]["path"] == "src/Button.tsx"
    seal_before(run_dir)
    loaded = load_project_baseline(run_dir)
    assert loaded["baselineDigest"] == baseline["baselineDigest"]


def test_baseline_tamper_is_caught_by_existing_experience_integrity(tmp_path: Path):
    project, run_dir = _run(tmp_path)
    attach_project_baseline(run_dir, project)
    seal_before(run_dir)
    path = run_dir / "before" / "project-baseline.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    value["fileCount"] = 99
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(ContractViolation) as caught:
        load_project_baseline(run_dir)
    assert caught.value.code in {"BASELINE_TAMPERED", "EVIDENCE_MANIFEST_MISMATCH"}


def test_target_file_drift_requires_rebase(tmp_path: Path):
    project, _ = _run(tmp_path)
    baseline = build_project_baseline(project)
    target = project / "src" / "Button.tsx"
    target.write_text("export const Button=()=> <button>changed</button>\n", encoding="utf-8")
    result = compare_project_baseline(baseline, project, target_files=["src/Button.tsx"])
    assert result["status"] == "REBASE_REQUIRED"
    assert result["targetFileDrift"] == ["src/Button.tsx"]


def test_toolchain_drift_requires_revalidation(tmp_path: Path):
    project, _ = _run(tmp_path)
    (project / "package.json").write_text('{"scripts":{}}', encoding="utf-8")
    baseline = build_project_baseline(project)
    (project / "package.json").write_text('{"scripts":{"test":"vitest"}}', encoding="utf-8")
    result = compare_project_baseline(baseline, project)
    assert result["status"] == "REVALIDATION_REQUIRED"
    assert "package.json" in result["toolchainDrift"]


def test_systemic_root_cause_prefers_one_patch_n_verifications():
    result = analyze_repair_scope([
        {"id": "F-1", "sourcePath": "src/components/Button.tsx"},
        {"id": "F-2", "sourcePath": "src/components/Button.tsx"},
        {"id": "F-3", "sourcePath": "src/pages/Other.tsx"},
    ])
    assert result["repairScope"] == "SYSTEMIC_ROOT_CAUSE"
    assert result["systemicCandidates"][0]["strategy"] == "ONE_PATCH_N_VERIFICATIONS"


def test_patch_quality_detects_new_important_and_inline_style(tmp_path: Path):
    project, _ = _run(tmp_path)
    baseline = build_project_baseline(project)
    target = project / "src" / "Button.tsx"
    target.write_text("export const Button=()=> <button style={{marginTop:'17px'}}>ok</button> // !important\n", encoding="utf-8")
    result = evaluate_patch_quality(project, baseline, source_scope=["src/Button.tsx"])
    assert result["status"] == "QUALITY_RISK"
    codes = {row["code"] for row in result["risks"]}
    assert {"NEW_IMPORTANT", "NEW_INLINE_STYLE"} <= codes


def test_project_tool_execution_is_plan_only_and_host_gated(tmp_path: Path):
    project, _ = _run(tmp_path)
    bin_dir = project / "node_modules" / ".bin"
    bin_dir.mkdir(parents=True)
    tool = bin_dir / "tsc"
    tool.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    plan = plan_project_tool_execution(project, "tsc", args=["--noEmit"])
    assert plan["runtimeMayExecute"] is False
    assert plan["execution"] == "HOST_GATED"
    assert plan["evidenceAuthority"] == "CONDITIONAL_PROJECT_TOOL_EVIDENCE"
    assert len(plan["executableSha256"]) == 64


def test_project_tool_execution_blocks_write_flags(tmp_path: Path):
    project, _ = _run(tmp_path)
    bin_dir = project / "node_modules" / ".bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "eslint").write_text("stub", encoding="utf-8")
    with pytest.raises(ContractViolation) as caught:
        plan_project_tool_execution(project, "eslint", args=["--fix"])
    assert caught.value.code == "PROJECT_TOOL_WRITE_FORBIDDEN"


def test_auth_profile_detects_state_replacement(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("WUQ_PROFILE_STORE", str(tmp_path / "profiles"))
    state = tmp_path / "state.json"
    state.write_text('{"cookies":[],"origins":[]}', encoding="utf-8")
    saved = save_auth_profile("staging-admin", state, allowed_origins=["https://example.test"])
    assert saved["name"] == "staging-admin"
    assert load_auth_profile("staging-admin")["allowedOrigins"] == ["https://example.test"]
    state.write_text('{"cookies":[{"name":"changed"}],"origins":[]}', encoding="utf-8")
    with pytest.raises(ContractViolation) as caught:
        load_auth_profile("staging-admin")
    assert caught.value.code == "AUTH_PROFILE_STALE"


def test_browser_doctor_precisely_distinguishes_driver_from_executable(tmp_path: Path, monkeypatch):
    chrome = tmp_path / "chrome"
    chrome.write_text("stub", encoding="utf-8")
    import web_ui_quality.capability_registry as module
    monkeypatch.setattr(module, "_module_present", lambda name: False)
    result = module._python_playwright(chrome)
    assert result["moduleAvailable"] is False
    assert result["browserExecutableAvailable"] is True
    assert "driver module is missing" in result["reason"]
    assert "does not bypass Playwright" in result["driverContract"]


def test_verification_budget_uses_systemic_scope_as_cost_signal():
    local = select_verification_budget(risk="LOW", affected_surfaces=1, changed_files=1)
    systemic = select_verification_budget(risk="MEDIUM", affected_surfaces=12, changed_files=1, systemic=True)
    assert local["profile"] == "MINIMAL"
    assert systemic["profile"] == "FULL"
    assert systemic["maxRoutes"] <= 50


def test_compatibility_export_baseline_is_frozen_at_a6_surface():
    path = Path(__file__).resolve().parents[1] / "runtime" / "python" / "web_ui_quality" / "public-compatibility-baseline.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    assert value["capturedFrom"] == "4.0.0a6"
    assert value["count"] == 221
    assert len(value["exports"]) == 221
