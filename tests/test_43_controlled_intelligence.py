from __future__ import annotations

from pathlib import Path

import pytest

from web_ui_quality.adaptive_intelligence import (
    TaskFingerprint,
    TaskGraph,
    build_candidate_arena,
    build_execution_budget,
    build_memory_entry,
    build_traceability_report,
    classify_assumption,
    compare_design_drift,
    complexity_delta,
    consume_budget,
    evaluate_memory_entry,
    propose_replan,
    reproduction_transition,
    route_design_intent,
    select_candidate,
    separate_design_review,
    shadow_supervisor,
    verification_profile,
)
from web_ui_quality.release_info import EXPERIMENTAL_VERSION, experimental_identity
from web_ui_quality.contracts import ContractViolation


def test_experimental_track_keeps_stable_kernel_identity():
    identity = experimental_identity()
    assert EXPERIMENTAL_VERSION == "4.4.0-alpha.18-shadow"
    assert identity["experimentalVersion"] == EXPERIMENTAL_VERSION
    assert identity["kernelVersion"] == "4.2.3"
    assert identity["authorityMode"] == "SHADOW_ADVISORY_ONLY"


def test_doctor_exposes_product_facing_alpha_boundary():
    import json
    import subprocess
    import sys

    root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [sys.executable, "-B", "scripts/run_runtime.py", "doctor", "--compact"],
        cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
    )
    assert completed.returncode == 0, completed.stderr
    value = json.loads(completed.stdout)
    qualification = value["experimentalTrack"]["qualification"]
    assert qualification["runtimeWiring"] == "PASS"
    assert qualification["controlledBenchmark"] == "PASS_SYNTHETIC_ONLY"
    assert qualification["realHostAgentMetrics"] == "NOT_MEASURED"
    assert qualification["enforcement"] == "NOT_ACTIVE"


def test_task_fingerprint_is_stable_and_scope_bound():
    kwargs = dict(project_identity={"repo": "demo", "commit": "abc"}, goal="fix overflow", success_criteria=["no overflow", "tests pass"], protected_scope=["src/App.tsx"])
    first = TaskFingerprint.build(**kwargs)
    second = TaskFingerprint.build(**{**kwargs, "success_criteria": ["tests pass", "no overflow"]})
    assert first.fingerprint_digest == second.fingerprint_digest
    assert TaskFingerprint.from_dict(first.to_dict()).fingerprint_digest == first.fingerprint_digest
    with pytest.raises(ContractViolation):
        TaskFingerprint.build(**{**kwargs, "protected_scope": []})
    with pytest.raises(ContractViolation):
        TaskFingerprint.from_dict({"projectIdentity": "not-an-object", "fingerprintDigest": "bad"})


def test_graph_rejects_ready_or_active_task_with_unverified_dependency():
    graph = TaskGraph()
    graph.add_task("base", goal="baseline")
    with pytest.raises(ContractViolation, match="TASK_DEPENDENCY_BLOCKED"):
        graph.add_task("repair", goal="repair", dependencies=["base"], status="ACTIVE")
    assert "repair" not in graph.nodes


def test_graph_dependencies_and_fail_closed_transitions():
    graph = TaskGraph()
    graph.add_task("one", goal="baseline", scope="src/App.tsx", success_criteria=["sealed"])
    assert graph.nodes["one"]["scope"] == ["src/App.tsx"]
    graph.add_task("two", goal="repair", dependencies=["one"], success_criteria=["verified"])
    assert graph.ready_tasks() == ["one"]
    graph.transition("one", "READY")
    graph.transition("one", "ACTIVE")
    graph.transition("one", "VERIFIED")
    assert graph.ready_tasks() == ["two"]
    with pytest.raises(ContractViolation):
        graph.transition("two", "VERIFIED")
    graph.transition("two", "READY")
    graph.transition("two", "ACTIVE")
    graph.transition("two", "VERIFIED")
    with pytest.raises(ContractViolation):
        graph.transition("two", "ACTIVE")


def test_supervisor_is_shadow_only_and_no_progress_stops():
    graph = TaskGraph(); graph.add_task("one", goal="do one")
    budget = build_execution_budget(risk="LOW")
    rec = shadow_supervisor(graph=graph, budget=budget)
    assert rec["action"] == "START_NEXT_TASK" and rec["writeAuthority"] is False
    stopped = shadow_supervisor(graph=graph, budget=budget, no_progress_rounds=3)
    assert stopped["action"] == "STOP_RECOMMENDED"


def test_budget_replay_and_exhaustion():
    budget = build_execution_budget(risk="LOW")
    first = consume_budget(budget, "read")
    second = consume_budget(first["budget"], "read", 23)
    assert second["status"] == "PASS"
    blocked = consume_budget(second["budget"], "read")
    assert blocked["status"] == "BLOCKED"


def test_replan_requires_reason_and_is_not_authoritative():
    row = propose_replan(previous_plan_digest="a", new_plan_digest="b", reason="root cause changed", scope_delta=["src/layout.tsx"])
    assert row["status"] == "REPLAN_PROPOSED" and row["requiresAuthorization"] and not row["writeAuthority"]
    with pytest.raises(ContractViolation):
        propose_replan(previous_plan_digest="a", new_plan_digest="b", reason="")


def test_assumption_and_complexity_gates():
    assert classify_assumption("spacing token is unknown")["level"] == "MEDIUM"
    assert classify_assumption("payment semantics unclear", changes_business_behavior=True)["resolution"] == "BLOCK_UNTIL_CLARIFIED"
    assert complexity_delta(added_files=["a", "b", "c"], added_dependencies=["x"], goal_size="SMALL")["status"] == "OVERENGINEERING_RISK"


def test_traceability_and_reproduction_contracts():
    report = build_traceability_report(goal_digest="g", hunks=[{"hunkId": "h1", "category": "DIRECT_FIX", "reason": "fix"}, {"hunkId": "h2", "category": "UNKNOWN"}], enforce=False)
    assert report["status"] == "ADVISORY" and report["untraceableHunks"] == ["h2"]
    assert reproduction_transition("REPORTED", "REPRODUCED") == "REPRODUCED"
    with pytest.raises(ContractViolation):
        reproduction_transition("REPORTED", "VERIFIED")


def test_design_intent_vectors_and_drift():
    intent = route_design_intent(surface_type="dashboard", audience="ops")
    assert intent["surfaceType"] == "DASHBOARD" and intent["guidanceStrength"] == "LOW" and intent["writeAuthority"] is False
    drift = compare_design_drift({"font": "A", "radius": 4}, {"font": "B", "radius": 8}, task_kind="precision_fix")
    assert drift["status"] == "ADVISORY" and drift["driftCount"] == 2
    assert compare_design_drift({"font": "A"}, {"font": "B"}, task_kind="redesign")["status"] == "PASS"


def test_technical_audit_can_fail_but_aesthetic_critique_cannot():
    result = separate_design_review(technical_findings=[{"id": "overflow", "severity": "P1", "status": "FAIL"}], design_critique=[{"id": "too_generic", "severity": "P2"}])
    assert result["status"] == "FAIL" and result["designCritique"][0]["status"] == "ADVISORY"
    advisory = separate_design_review(design_critique=[{"id": "too_many_cards"}])
    assert advisory["status"] == "PASS_WITH_ADVISORY"


def test_memory_binding_and_staleness():
    entry = build_memory_entry(kind="ENGINEERING", payload={"task": "fixed"}, source_digest="src-1")
    assert evaluate_memory_entry(entry, current_source_digest="src-1")["status"] == "TRUSTED"
    assert evaluate_memory_entry(entry, current_source_digest="src-2")["status"] == "HISTORICAL_ONLY"
    tampered = {**entry, "payload": {"task": "changed"}}
    with pytest.raises(ContractViolation, match="MEMORY_ENTRY_TAMPERED"):
        evaluate_memory_entry(tampered, current_source_digest="src-1")
    with pytest.raises(ContractViolation, match="MEMORY_ENTRY_INVALID"):
        evaluate_memory_entry({}, current_source_digest="src-1")


def test_candidate_arena_is_preview_only_and_selection_is_intent():
    arena = build_candidate_arena(task_kind="major_brand", candidates=[{"candidateId": "a"}, {"candidateId": "b"}, {"candidateId": "c"}, {"candidateId": "d"}])
    assert len(arena["candidates"]) == 3 and arena["status"] == "PREVIEW_ONLY"
    selection = select_candidate(arena, "b")
    assert selection["requiresPatchPlan"] and selection["writeAuthority"] is False
    with pytest.raises(ContractViolation, match="CANDIDATE_ARENA_TAMPERED"):
        select_candidate({**arena, "candidates": [{"candidateId": "evil"}]}, "evil")


def test_profiles_cover_harden_and_adapt():
    harden = verification_profile("HARDEN_PROFILE")
    adapt = verification_profile("ADAPT_PROFILE")
    assert "long_text" in harden["cases"] and "375" in adapt["cases"]
    with pytest.raises(ContractViolation):
        verification_profile("UNKNOWN")
