#!/usr/bin/env python3
"""Independent Product Evidence acceptance retained in Beta.4 for Product Evidence Foundation.

This gate validates the Product Evidence contracts directly. Benchmark-harness
and privacy-egress qualification are intentionally separate release gates so
release validation executes each authority exactly once.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime" / "python"
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from web_ui_quality.context_packet import build_relevant_context_packet, context_recall  # noqa: E402
from web_ui_quality.project_baseline import build_project_baseline  # noqa: E402
from web_ui_quality.release_info import PACKAGE_VERSION  # noqa: E402
from web_ui_quality.schema_validation import validate_instance  # noqa: E402
from web_ui_quality.task_result import build_task_result  # noqa: E402

EXPECTED_VERSION = "4.3.0"


def _fixture_result() -> dict:
    return {
        "status": "VERIFIED", "runId": "wuq-acceptance", "taskId": "task-acceptance", "mode": "FIX_AND_VERIFY",
        "taskGoal": {"goal": "修复移动端订单页", "nonGoals": ["登录逻辑"]},
        "projectBaseline": {
            "completenessStatus": "INDETERMINATE",
            "targetCoverage": {"status": "COMPLETE"},
            "criticalContextCoverage": {"status": "COMPLETE"},
        },
        "projectDriftGate": {
            "status": "EXPECTED_ONLY", "globalCoverage": "PARTIAL",
            "targetCoverageComplete": True, "criticalContextCoverageComplete": True,
        },
        "repairVerification": {"status": "VERIFIED", "blockers": [], "warnings": []},
        "repairReport": {
            "status": "VERIFIED", "request": "修复移动端订单页",
            "answers": {
                "whatYouAsked": "修复移动端订单页", "whatWasReproduced": "问题已复现",
                "rootCause": "shared source candidate", "whatChanged": ["src/Table.tsx"],
                "howVerified": ["Browser PASS"], "remainingRiskOrUnknown": [],
            },
            "verificationSummary": {
                "overall": "VERIFIED", "browser": "IMPROVEMENT_CLAIM_ALLOWED", "projectTools": "PASS",
                "patchQuality": "QUALITY_OK", "projectDrift": "EXPECTED_ONLY", "hostWrite": "HOST_WRITE_VERIFIED",
            },
            "nextAction": "继续下一个问题。", "taskState": {"runId": "wuq-acceptance", "resumable": True},
        },
    }


def _context_smoke() -> tuple[float, float]:
    with tempfile.TemporaryDirectory(prefix="wuq-product-evidence-") as temp:
        project = Path(temp)
        root_source = project / "src" / "Table.tsx"
        root_source.parent.mkdir(parents=True)
        root_source.write_text("export const Table = () => null\n", encoding="utf-8")
        (project / "src" / "Login.tsx").write_text("export const Login = () => null\n", encoding="utf-8")
        baseline = build_project_baseline(project, target_files=["src/Table.tsx"])
        packet = build_relevant_context_packet(
            project,
            request="修复移动端订单表格，不要动登录逻辑",
            task_goal={"goal": "修复移动端订单表格", "nonGoals": ["登录逻辑"]},
            baseline=baseline,
            explicit_source_scope=["src/Table.tsx"],
        )
        recall = context_recall(packet, ["src/Table.tsx"], k=5)
        protected = 1.0 if "登录逻辑" in packet.get("mandatoryContext", {}).get("protectedScope", []) else 0.0
        return float(recall.get("recall", 0.0)), protected


def main() -> int:
    if PACKAGE_VERSION != EXPECTED_VERSION:
        raise SystemExit(f"version mismatch: {PACKAGE_VERSION}")
    public = ROOT / "schemas" / "task-result.schema.json"
    packaged = RUNTIME / "web_ui_quality" / "schemas" / "task-result.schema.json"
    if public.read_bytes() != packaged.read_bytes():
        raise SystemExit("task-result schema bundles differ")
    schema = json.loads(public.read_text(encoding="utf-8"))
    task_result = build_task_result(_fixture_result())
    validate_instance(task_result, schema, base_dir=ROOT / "schemas")
    if task_result["coverage"]["globalProject"] != "PARTIAL" or task_result["coverage"]["patchScope"] != "COMPLETE":
        raise SystemExit("TaskResult coverage disclosure failed")
    root_recall, protected_recall = _context_smoke()
    if root_recall != 1.0 or protected_recall != 1.0:
        raise SystemExit("Relevant Context Packet acceptance failed")
    result = {
        "status": "PASS",
        "version": PACKAGE_VERSION,
        "taskResult": "PASS",
        "coverageContract": "PASS",
        "contextPacket": "PASS",
        "contextRootSourceRecallAt5": root_recall,
        "protectedScopeRecall": protected_recall,
        "externalReleaseGates": {
            "faultInjectionHarness": "SEPARATE_GATE",
            "privacyEgressPolicy": "SEPARATE_GATE",
            "hostAgentBenchmark": "NOT_VERIFIED_HOST_AUTOMATION",
        },
        "claimBoundary": "This acceptance proves the TaskResult, coverage, and deterministic context-packet contracts. Harness and privacy have separate release gates. It does not claim model repair accuracy, False VERIFIED rate, pass@k, cost, or variance.",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
