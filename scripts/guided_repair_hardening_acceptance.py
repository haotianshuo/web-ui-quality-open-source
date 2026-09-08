#!/usr/bin/env python3
"""Independent Beta.2 acceptance for Guided Repair trust and human/CI contracts."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile

from web_ui_quality.outcome_verification import combine_repair_verification
from web_ui_quality.project_baseline import build_project_baseline, compare_project_baseline, classify_post_repair_drift
from web_ui_quality.project_tool_boundary import plan_project_tool_execution, verify_host_tool_result, summarise_host_tool_results


def main() -> int:
    checks: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(prefix="wuq-beta2-") as temp:
        root = Path(temp) / "project"
        tool_dir = root / "node_modules" / ".bin"
        tool_dir.mkdir(parents=True)
        tool = tool_dir / "tsc"
        tool.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        target = root / "Button.tsx"
        other = root / "other.ts"
        target.write_text("export const B=1\n", encoding="utf-8")
        other.write_text("export const O=1\n", encoding="utf-8")

        plan = plan_project_tool_execution(
            root, "tsc", args=["--noEmit"], run_id="wuq-beta2-acceptance", task_id="task", session_id="session"
        )
        checks.append({"name": "tool-filesystem-plan", "status": "PASS" if plan.get("filesystemPolicy") == "READ_ONLY_PROJECT" else "FAIL"})
        checks.append({"name": "tool-run-binding", "status": "PASS" if plan.get("runBinding", {}).get("runId") == "wuq-beta2-acceptance" else "FAIL"})
        receipt = {
            "planDigest": plan["planDigest"], "tool": plan["tool"], "executableSha256": plan["executableSha256"],
            "argv": plan["argv"], "cwd": plan["cwd"], "runBinding": plan["runBinding"],
            "exitCode": 0, "stdout": "", "stderr": "",
            "timedOut": False, "networkPolicyEnforced": True, "resourcePolicyEnforced": True,
            "filesystemPolicy": plan["filesystemPolicy"], "filesystemPolicyEnforced": True,
            "unexpectedWrites": ["other.ts"],
        }
        tool_gate = summarise_host_tool_results([verify_host_tool_result(root, plan, receipt)])
        checks.append({"name": "unexpected-tool-write-blocked", "status": "PASS" if tool_gate.get("status") == "FAIL" else "FAIL"})

        baseline = build_project_baseline(root, target_files=["Button.tsx"])
        target.write_text("export const B=2\n", encoding="utf-8")
        other.write_text("export const O=2\n", encoding="utf-8")
        drift = classify_post_repair_drift(compare_project_baseline(baseline, root, target_files=["Button.tsx"]), expected_write_paths=["Button.tsx"])
        final = combine_repair_verification(
            browser_outcome_status="IMPROVEMENT_CLAIM_ALLOWED", project_tool_status="PASS",
            patch_quality_status="QUALITY_OK", project_drift_status=drift.get("status", "NOT_VERIFIED"),
        )
        checks.append({"name": "unexpected-baseline-drift-blocks-verified", "status": "PASS" if final.get("status") == "FAIL" else "FAIL"})

    status = "PASS" if all(item["status"] == "PASS" for item in checks) else "FAIL"
    print(json.dumps({"status": status, "checks": checks}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
