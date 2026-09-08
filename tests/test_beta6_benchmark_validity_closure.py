from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from agent_benchmark_qualification import _load, _save, _synthetic_host_result, ingest
from fault_injection_harness import load_cases, prepare_all, prepare_case, score_host_observation
from web_ui_quality.contracts import ContractViolation
from web_ui_quality.context_packet import build_relevant_context_packet, context_retrieval_metrics
from web_ui_quality.project_baseline import build_project_baseline


def test_all_40_instances_are_unique_archetypes():
    cases = load_cases(corpus="v2")
    assert len(cases) == 40
    assert len({row["archetype"] for row in cases}) == 40
    assert len({row["request"] for row in cases}) == 40


def test_corpus_has_source_executable_and_no_mutation_oracles():
    kinds = {str(o["type"]) for c in load_cases(corpus="v2") for o in c["oracle"]}
    assert {"FILE_CONTAINS", "NODE_SCRIPT", "NO_MUTATION"} <= kinds
    assert sum(any(o["type"] == "NODE_SCRIPT" for o in c["oracle"]) for c in load_cases(corpus="v2")) >= 8


def test_harness_measures_all_applicable_cases_not_first_12():
    completed = subprocess.run([sys.executable, "-B", "scripts/fault_injection_harness.py", "--self-test"], cwd=ROOT, text=True, encoding="utf-8", errors="replace", capture_output=True, check=True)
    value = json.loads(completed.stdout)
    assert value["caseCount"] == 40
    assert value["archetypeCount"] == 40
    assert value["contextRetrieval"]["totalRuns"] == 40
    assert value["contextRetrieval"]["measuredRuns"] == 36
    assert value["contextRetrieval"]["measurementScope"] == "ALL_APPLICABLE_CASES"
    assert value["contextRetrieval"]["at5"]["meanPrecision"] is not None
    assert value["contextRetrieval"]["at5"]["meanEstimatedSourceTokens"] < 500


def test_context_metrics_report_recall_precision_and_budget(tmp_path: Path):
    case = next(c for c in load_cases(corpus="v2") if c["id"] == "responsive-table-overflow")
    prepared = prepare_case(case, tmp_path / "project")
    project = tmp_path / "project"
    packet = build_relevant_context_packet(project, request=case["request"], task_goal={"goal": case["request"], "nonGoals": case["protectedScope"]}, baseline=build_project_baseline(project), max_source_refs=5)
    metrics = context_retrieval_metrics(packet, case["expectedRootSources"], k=5)
    assert metrics["recall"] == 1.0
    assert 0 < metrics["precision"] <= 1.0
    assert metrics["estimatedSourceTokens"] >= 0


def test_controller_planned_condition_spoof_is_rejected(tmp_path: Path):
    controller = tmp_path / "controller"
    prepare_all(controller, repetitions=1, corpus="v2", planned_host={"name":"codex-desktop","version":"DESKTOP","model":"MODEL-A"})
    plan = _load(controller / "benchmark-plan.json")
    run = plan["runs"][0]
    result = _synthetic_host_result(run, outcome="NOT_VERIFIED", roots=[])
    result["host"]["model"] = "MODEL-B"
    incoming = tmp_path / "spoof.json"; _save(incoming, result)
    with pytest.raises(ContractViolation) as caught:
        ingest(controller, incoming)
    assert caught.value.code == "BENCHMARK_CONDITION_MISMATCH"


def test_executable_oracle_accepts_equivalent_javascript_behavior(tmp_path: Path):
    case = next(c for c in load_cases(corpus="v2") if c["id"] == "search-debounce")
    project = tmp_path / "project"; prepared = prepare_case(case, project)
    root = project / case["expectedRootSources"][0]
    root.write_text("export const latest=(value)=>String(value);\n", encoding="utf-8")
    row = score_host_observation(prepared["evaluatorManifest"], project, {"outcome":"VERIFIED","rootCauseFiles":case["expectedRootSources"],"regressions":[]})
    assert row["groundTruthSatisfied"] is True
    assert row["oracleResults"][0]["type"] == "NODE_SCRIPT"
    assert row["oracleResults"][0]["status"] == "MEASURED"


def test_executable_oracle_rejects_source_token_gaming(tmp_path: Path):
    case = next(c for c in load_cases(corpus="v2") if c["id"] == "search-debounce")
    project = tmp_path / "project"; prepared = prepare_case(case, project)
    root = project / case["expectedRootSources"][0]
    root.write_text("// PASS new latest\nexport const latest=(_value)=>'stale';\n", encoding="utf-8")
    row = score_host_observation(prepared["evaluatorManifest"], project, {"outcome":"VERIFIED","rootCauseFiles":case["expectedRootSources"],"regressions":[]})
    assert row["groundTruthSatisfied"] is False
    assert row["falseVerified"] is True


def test_attack_suite_reports_strategy_diversity_separately_from_probe_volume():
    completed = subprocess.run([sys.executable, "-B", "scripts/benchmark_attack_suite.py"], cwd=ROOT, text=True, encoding="utf-8", errors="replace", capture_output=True, check=True)
    value = json.loads(completed.stdout)
    assert value["status"] == "PASS"
    assert value["probes"]["strategyFamilies"] >= 12
    assert value["probes"]["totalDeterministicProbes"] == 1200
    assert len(value["probes"]["strategyResults"]) == value["probes"]["strategyFamilies"]


def test_desktop_pack_prebinds_controller_conditions_and_template(tmp_path: Path):
    completed = subprocess.run([sys.executable, "-B", "scripts/desktop_qualification_pack.py", str(tmp_path / "pack"), "--repetitions", "1"], cwd=ROOT, text=True, encoding="utf-8", errors="replace", capture_output=True, check=True)
    value = json.loads(completed.stdout)
    assert value["runCount"] == 24
    queue = json.loads((tmp_path / "pack" / "qualification-queue.json").read_text(encoding="utf-8"))
    first = queue["runs"][0]
    template = json.loads(Path(first["resultTemplate"]).read_text(encoding="utf-8"))
    assert template["schemaVersion"] == "4"
    assert template["conditionDigest"] == first["conditionDigest"]
    assert template["conditions"]["wuqVersion"] == "4.0.0-rc.1"
