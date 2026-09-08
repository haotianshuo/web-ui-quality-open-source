#!/usr/bin/env python3
"""Independent product acceptance for A7 Repair & Modernization Consolidation."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "runtime" / "python"))

from web_ui_quality.__main__ import _COMMAND_LIFECYCLE, _PUBLIC_COMMANDS, _COMPATIBILITY_COMMANDS, _parser
from web_ui_quality.auth_profiles import save_auth_profile, load_auth_profile
from web_ui_quality.capability_registry import build_capability_registry
from web_ui_quality.contracts import ContractViolation
from web_ui_quality.experience_run import create_experience_run, seal_before
from web_ui_quality.patch_quality import evaluate_patch_quality
from web_ui_quality.project_baseline import attach_project_baseline, compare_project_baseline, load_project_baseline
from web_ui_quality.project_tool_boundary import plan_project_tool_execution
from web_ui_quality.release_info import PACKAGE_VERSION
from web_ui_quality.repair_report import build_repair_report
from web_ui_quality.systemic_repair import analyze_repair_scope
from web_ui_quality.verification_budget import select_verification_budget

EXPECTED = "4.3.0"


def main() -> int:
    checks: list[dict[str, str]] = []
    if PACKAGE_VERSION != EXPECTED:
        raise RuntimeError(f"version mismatch: {PACKAGE_VERSION}")

    parser = _parser()
    action = next(item for item in parser._actions if item.__class__.__name__ == "_SubParsersAction")
    visible = {item.dest for item in action._choices_actions}
    if visible != _PUBLIC_COMMANDS or _PUBLIC_COMMANDS != {"run", "doctor", "auth", "expert"}:
        raise RuntimeError(f"public facade mismatch: {sorted(visible)}")
    if any(_COMMAND_LIFECYCLE.get(name) != "compatibility" for name in _COMPATIBILITY_COMMANDS):
        raise RuntimeError("legacy commands are not lifecycle-classified as compatibility")
    checks.append({"id": "A7-001", "status": "PASS"})

    with tempfile.TemporaryDirectory(prefix="wuq-a7-") as raw:
        tmp = Path(raw)
        project = tmp / "legacy"
        (project / "src" / "components").mkdir(parents=True)
        button = project / "src" / "components" / "Button.tsx"
        button.write_text("export const Button=()=> <button>OK</button>\n", encoding="utf-8")
        (project / "package.json").write_text('{"dependencies":{"react":"18"}}', encoding="utf-8")
        run = create_experience_run(tmp / "artifacts", task_id="legacy-task", session_id="s1", mode="FIX_AND_VERIFY", target={"kind":"project","projectRoot":str(project)}, conditions={"browser":"chromium"})
        run_dir = Path(run["runDir"])
        baseline = attach_project_baseline(run_dir, project)
        seal_before(run_dir)
        if load_project_baseline(run_dir)["baselineDigest"] != baseline["baselineDigest"]:
            raise RuntimeError("sealed baseline could not be reloaded")
        button.write_text("export const Button=()=> <button>Changed</button>\n", encoding="utf-8")
        drift = compare_project_baseline(baseline, project, target_files=["src/components/Button.tsx"])
        if drift["status"] != "REBASE_REQUIRED":
            raise RuntimeError("target-file drift did not require rebase")
        checks.append({"id": "A7-002", "status": "PASS"})

        systemic = analyze_repair_scope([
            {"id":"F-1","sourcePath":"src/components/Button.tsx"},
            {"id":"F-2","sourcePath":"src/components/Button.tsx"},
        ])
        if systemic["repairScope"] != "SYSTEMIC_ROOT_CAUSE":
            raise RuntimeError("systemic root cause was not recognized")
        checks.append({"id": "A7-003", "status": "PASS"})

        button.write_text("export const Button=()=> <button style={{marginTop:'44px'}}>Changed</button> // !important\n", encoding="utf-8")
        quality = evaluate_patch_quality(project, baseline, source_scope=["src/components/Button.tsx"])
        if quality["status"] != "QUALITY_RISK":
            raise RuntimeError("patch quality failed to detect new debt")
        checks.append({"id": "A7-004", "status": "PASS"})

        bin_dir = project / "node_modules" / ".bin"
        bin_dir.mkdir(parents=True)
        (bin_dir / "tsc").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        plan = plan_project_tool_execution(project, "tsc", args=["--noEmit"])
        if plan["execution"] != "HOST_GATED" or plan["runtimeMayExecute"] is not False:
            raise RuntimeError("project tool boundary is not Host-gated")
        try:
            plan_project_tool_execution(project, "tsc", args=["--outDir", "dist"])
        except ContractViolation as error:
            if error.code != "PROJECT_TOOL_WRITE_FORBIDDEN":
                raise
        else:
            raise RuntimeError("write-producing project tool args were accepted")
        checks.append({"id": "A7-005", "status": "PASS"})

        profile_store = tmp / "profiles"
        os.environ["WUQ_PROFILE_STORE"] = str(profile_store)
        state = tmp / "storage-state.json"
        state.write_text('{"cookies":[],"origins":[]}', encoding="utf-8")
        save_auth_profile("staging-admin", state, allowed_origins=["https://example.test"])
        if load_auth_profile("staging-admin")["storageStateSha256"] == "":
            raise RuntimeError("auth profile is not digest-bound")
        checks.append({"id": "A7-006", "status": "PASS"})

        budget = select_verification_budget(risk="MEDIUM", affected_surfaces=12, changed_files=1, systemic=True)
        if budget["profile"] != "FULL" or budget["strategy"] != "REPRESENTATIVE_PLUS_INTEGRATION":
            raise RuntimeError("systemic verification budget is not escalated")
        checks.append({"id": "A7-007", "status": "PASS"})

        report = build_repair_report(
            request="修复订单页移动端问题", status="PLAN_READY", reproduced="Before evidence recorded",
            root_cause="SharedButton", changes=["Patch candidate prepared"], verification=["Host approval required"],
            risks=[], unverified=["After not yet executed"], resumable=True, run_id="wuq-test", authentication="profile:staging-admin",
        )
        if report["taskState"]["resumeHint"] != "继续上次任务" or "rootCause" not in report["answers"]:
            raise RuntimeError("Repair Report does not preserve progressive disclosure")
        checks.append({"id": "A7-008", "status": "PASS"})

    browser = build_capability_registry().get("pythonPlaywright", {})
    if "driverContract" not in browser or "browserExecutableAvailable" not in browser:
        raise RuntimeError("doctor capability does not distinguish driver/executable prerequisites")
    checks.append({"id": "A7-009", "status": "PASS"})

    compat = json.loads((ROOT / "runtime" / "python" / "web_ui_quality" / "public-compatibility-baseline.json").read_text(encoding="utf-8"))
    if compat.get("capturedFrom") != "4.0.0a6" or compat.get("count") != 221:
        raise RuntimeError("a6 compatibility export baseline is not frozen")
    checks.append({"id": "A7-010", "status": "PASS"})

    print(json.dumps({"status":"PASS","version":PACKAGE_VERSION,"scope":"REPAIR_MODERNIZATION_CONSOLIDATION","checks":checks}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
