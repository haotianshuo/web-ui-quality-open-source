from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from web_ui_quality.schema_validation import validate_instance

ROOT = Path(__file__).resolve().parents[1]


def _run(*args: str) -> dict:
    completed = subprocess.run([sys.executable, "-B", "scripts/agent_benchmark_qualification.py", *args], cwd=ROOT, text=True, encoding="utf-8", errors="replace", capture_output=True, check=True)
    return json.loads(completed.stdout)


def _conditions():
    return {"reasoningMode":"test","permissionProfile":"test","toolPolicy":"deny","browserCondition":"not-used","authCondition":"anonymous","os":"test","runtime":"python","contextPolicy":"wuq-relevant-context-v1","wuqVersion":"4.0.0-rc.1","fixtureVersion":"fault-injection-v2"}


def test_fault_harness_host_workspace_does_not_leak_ground_truth(tmp_path: Path):
    completed = subprocess.run([sys.executable, "-B", "scripts/fault_injection_harness.py", "--prepare-all", str(tmp_path / "controller"), "--repetitions", "2"], cwd=ROOT, text=True, encoding="utf-8", errors="replace", capture_output=True, check=True)
    value = json.loads(completed.stdout)
    assert value["runCount"] == 80
    assert value["workspaceIsolation"] == "SEPARATE_FILESYSTEM_ROOTS"
    plan_text = (tmp_path / "controller" / "benchmark-plan.json").read_text(encoding="utf-8")
    assert "cleanContent" not in plan_text and "rootSource" not in plan_text and "evaluatorRoot" not in plan_text
    assert Path(value["hostWorkspaceRoot"]).resolve().parent != (tmp_path / "controller").resolve()


def test_agent_benchmark_self_test_qualifies_protocol_not_model():
    value = _run("self-test")
    assert value["status"] == "PASS"
    assert value["plannedRuns"] == 120
    assert value["immutableIngest"] == "PASS"
    assert value["conditionFingerprint"] == "PASS"
    assert value["agentLoopStatus"] == "NOT_VERIFIED_HOST_AUTOMATION"


def test_host_result_schema_rejects_ground_truth_self_claims():
    schema = json.loads((ROOT / "schemas" / "agent-benchmark-result.schema.json").read_text(encoding="utf-8"))
    valid = {"schemaVersion":"4","kind":"HOST_RESULT","protocolVersion":"4","runId":"case-r01","caseId":"case","repetition":1,"conditionDigest":"a"*64,"host":{"name":"codex","version":"x","model":"gpt"},"conditions":_conditions(),"observation":{"outcome":"NOT_VERIFIED","rootCauseFiles":[],"regressions":[]},"metrics":{"wallTimeSeconds":None,"inputTokens":None,"outputTokens":None,"costUsd":None,"hostInteractions":None},"claimBoundary":"Host report only"}
    validate_instance(valid, schema, base_dir=ROOT / "schemas")
    invalid = json.loads(json.dumps(valid)); invalid["observation"]["groundTruthRepaired"] = True
    from web_ui_quality.schema_validation import validation_errors
    assert validation_errors(invalid, schema, base_dir=ROOT / "schemas")


def test_aggregate_reports_no_agent_measurement_before_external_results(tmp_path: Path):
    controller = tmp_path / "controller"
    _run("prepare", str(controller), "--repetitions", "1")
    value = _run("aggregate", str(controller))
    assert value["agentLoopStatus"] == "NOT_VERIFIED_HOST_AUTOMATION"
    assert value["completedRuns"] == 0
    assert value["falseVerified"]["rateAmongVerifiedClaims"] is None
    assert value["empiricalPassAtK"]["pass@1"] is None


def test_fault_harness_self_test_checks_path_separation_and_no_leaks():
    completed = subprocess.run([sys.executable, "-B", "scripts/fault_injection_harness.py", "--self-test"], cwd=ROOT, text=True, encoding="utf-8", errors="replace", capture_output=True, check=True)
    value = json.loads(completed.stdout)
    assert value["status"] == "PASS"
    assert value["workspaceRootSeparation"] == "PASS"
    assert value["groundTruthLeakCount"] == 0
    assert value["contextRecallStatus"] == "MEASURED_NOT_A_HARNESS_GATE"
    assert value["agentLoopStatus"] == "NOT_VERIFIED_HOST_AGENT"
    assert value["hostAutomationStatus"] == "NOT_VERIFIED_HOST_AUTOMATION"
