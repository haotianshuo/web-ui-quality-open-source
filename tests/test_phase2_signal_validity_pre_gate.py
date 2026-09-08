from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from web_ui_quality.phase1_shadow import build_shadow_observation
from web_ui_quality.phase2_signal_dataset import build_dataset_record, build_outcome_label, label_validity_eligibility
from web_ui_quality.phase2_signal_validity import analyze_signal_validity
from web_ui_quality.schema_validation import validate_instance

ROOT=Path(__file__).resolve().parents[1]


def _shadow(run: str, *, outcome_status="NOT_VERIFIED", tool_statuses=()):
    return build_shadow_observation(
        run_id=run,task_id=f"task-{run}",session_id="session",request="private-user-request",
        selected_mode="FIX_AND_VERIFY",target_kind="url",
        intent_route={"intent":"REPAIR_SMALL","specialty":None,"writeRequested":True,"readOnlyRequired":False},
        control_intent={"action":"FIX","profile":"standard","protectedScope":[]},
        fixed_result={"status":outcome_status,"taskResult":{"status":outcome_status},"projectToolEvidence":[{"tool":f"t-{i}","status":s} for i,s in enumerate(tool_statuses)]},
    )


def _label(run: str, outcome: str, *, source="EXTERNAL_ORACLE", independence="INDEPENDENT", split="DEVELOPMENT"):
    return build_outcome_label(
        run_id=run,task_id=f"task-{run}",session_id="session",source=source,outcome=outcome,
        independence=independence,split=split,evaluator_id="oracle",evidence_digest="a"*64,created_at="2026-08-11T00:00:00Z")


def test_unlabelled_rows_never_establish_predictive_validity():
    report=analyze_signal_validity([build_dataset_record(_shadow("u"))],minimum_independent_rows=1,minimum_signal_support=1)
    assert report["predictiveValidity"] == "NOT_MEASURED"
    assert report["preGateDecision"] == "NOT_READY_NO_INDEPENDENT_LABELS"


def test_fixed_workflow_proxy_cannot_self_validate_signal():
    row=build_dataset_record(_shadow("p",outcome_status="VERIFIED",tool_statuses=("FAIL",)),outcome_label=_label("p","BAD",source="FIXED_WORKFLOW_PROXY",independence="POTENTIALLY_DEPENDENT"))
    report=analyze_signal_validity([row],minimum_independent_rows=1,minimum_signal_support=1)
    assert report["independentlyLabelledRowCount"] == 0
    assert report["excludedReasonCounts"]["LABEL_SOURCE_NOT_CONFIRMATORY"] == 1


def test_holdout_labels_are_excluded_by_default():
    row=build_dataset_record(_shadow("h",outcome_status="VERIFIED",tool_statuses=("FAIL",)),outcome_label=_label("h","BAD",split="HOLDOUT"))
    report=analyze_signal_validity([row],minimum_independent_rows=1,minimum_signal_support=1)
    assert report["independentlyLabelledRowCount"] == 0
    assert report["excludedReasonCounts"]["HOLDOUT_EXCLUDED_BY_DEFAULT"] == 1
    explicit=analyze_signal_validity([row],include_holdout=True,minimum_independent_rows=1,minimum_signal_support=1)
    assert explicit["independentlyLabelledRowCount"] == 1
    assert explicit["analysisMode"] == "EXPLICIT_HOLDOUT_ANALYSIS"


def test_negative_signal_confusion_matrix_is_computed_mechanically():
    rows=[]
    for i in range(5):
        run=f"bad-{i}"; rows.append(build_dataset_record(_shadow(run,outcome_status="VERIFIED",tool_statuses=("FAIL",)),outcome_label=_label(run,"BAD")))
    for i in range(5):
        run=f"good-{i}"; rows.append(build_dataset_record(_shadow(run,outcome_status="NOT_VERIFIED",tool_statuses=()),outcome_label=_label(run,"GOOD")))
    report=analyze_signal_validity(rows,minimum_independent_rows=10,minimum_signal_support=3)
    metrics={m["code"]:m for m in report["signalMetrics"]}
    m=metrics["TOOL_FAILURE_WITH_SUCCESS_CLAIM_CONFLICT"]
    assert (m["tp"],m["fp"],m["fn"],m["tn"]) == (5,0,0,5)
    assert m["precision"] == 1.0 and m["recall"] == 1.0
    assert report["predictiveValidity"] == "PRE_GATE_MEASURED_DEVELOPMENT_ONLY"
    assert report["preGateDecision"] == "READY_FOR_PREREGISTERED_SIGNAL_VALIDITY_GATE"


def test_signal_metrics_never_emit_profile_or_clamp_recommendation():
    row=build_dataset_record(_shadow("x"),outcome_label=_label("x","GOOD"))
    report=analyze_signal_validity([row],minimum_independent_rows=1,minimum_signal_support=1)
    assert report["profileRecommendation"] == "NOT_EVALUATED_UNTIL_SIGNAL_VALIDITY_GATE"
    assert report["clampRecommendation"] == "NOT_EVALUATED_UNTIL_SIGNAL_VALIDITY_GATE"
    assert report["authorityEffect"] == report["adaptiveEffect"] == "NONE"


def test_outcome_label_binding_must_match_shadow_record():
    with pytest.raises(ValueError,match="binding mismatch"):
        build_dataset_record(_shadow("a"),outcome_label=_label("b","GOOD"))


def test_label_eligibility_requires_independence():
    assert label_validity_eligibility(_label("a","GOOD"))["eligible"] is True
    label=_label("a","GOOD",independence="UNKNOWN")
    assert label_validity_eligibility(label) == {"eligible":False,"reason":"LABEL_NOT_INDEPENDENT"}


def test_new_schemas_validate():
    schemas=ROOT/"schemas"
    label=_label("schema","GOOD")
    record=build_dataset_record(_shadow("schema"),outcome_label=label)
    report=analyze_signal_validity([record],minimum_independent_rows=1,minimum_signal_support=1)
    for filename,value in [("outcome-label-v1.schema.json",label),("shadow-signal-dataset-record-v1.schema.json",record),("signal-validity-report-v1.schema.json",report)]:
        schema=json.loads((schemas/filename).read_text(encoding="utf-8"))
        validate_instance(value,schema,base_dir=schemas)


def test_dataset_builder_collects_real_shadow_artifact_without_inventing_label(tmp_path: Path):
    observation=_shadow("real")
    path=tmp_path/"run"/"experimental"/"phase1-shadow"/"0001-observation.json"
    path.parent.mkdir(parents=True); path.write_text(json.dumps(observation),encoding="utf-8")
    dataset=tmp_path/"dataset.jsonl"
    completed=subprocess.run([sys.executable,str(ROOT/"scripts/phase2_build_shadow_dataset.py"),str(tmp_path),"--output",str(dataset)],cwd=ROOT,text=True,encoding="utf-8",errors="replace",capture_output=True)
    assert completed.returncode == 0, completed.stderr
    summary=json.loads(completed.stdout)
    assert summary["recordCount"] == 1 and summary["labelCount"] == 0
    row=json.loads(dataset.read_text(encoding="utf-8").strip())
    assert row["label"] is None
    assert row["authorityEffect"] == row["adaptiveEffect"] == "NONE"


def test_validity_cli_defaults_to_development_only(tmp_path: Path):
    row=build_dataset_record(_shadow("h2",outcome_status="VERIFIED",tool_statuses=("FAIL",)),outcome_label=_label("h2","BAD",split="HOLDOUT"))
    dataset=tmp_path/"dataset.jsonl"; dataset.write_text(json.dumps(row)+"\n",encoding="utf-8")
    completed=subprocess.run([sys.executable,str(ROOT/"scripts/phase2_signal_validity.py"),str(dataset),"--minimum-independent-rows","1","--minimum-signal-support","1"],cwd=ROOT,text=True,encoding="utf-8",errors="replace",capture_output=True)
    assert completed.returncode == 0, completed.stderr
    report=json.loads(completed.stdout)
    assert report["analysisMode"] == "DEVELOPMENT_ONLY"
    assert report["holdoutUsed"] is False
    assert report["predictiveValidity"] == "NOT_MEASURED"


def test_acceptance_runner_passes():
    completed=subprocess.run([sys.executable,str(ROOT/"scripts/phase2_signal_validity_acceptance.py")],cwd=ROOT,text=True,encoding="utf-8",errors="replace",capture_output=True)
    assert completed.returncode == 0, completed.stderr+completed.stdout
    result=json.loads(completed.stdout)
    assert result["status"] == "PASS"
    assert result["predictiveValidity"] == "NOT_MEASURED_REAL_WORLD"
    assert len(result["checks"]) >= 10
