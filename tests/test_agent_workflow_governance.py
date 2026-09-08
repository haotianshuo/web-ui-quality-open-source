from __future__ import annotations

import json
from pathlib import Path

import pytest

from web_ui_quality.assumption_graph import (
    add_assumption,
    load_assumption_graph,
    register_dependent_artifact,
    supersede_assumption,
)
from web_ui_quality.capability_router import route_capabilities
from web_ui_quality.control_intent import parse_control_intent
from web_ui_quality.contracts import ContractViolation
from web_ui_quality.decision_ledger import (
    create_decision,
    load_decision_ledger,
    supersede_decision,
    update_verification_status,
)
from web_ui_quality.experience_run import create_experience_run, seal_before, write_phase_file
from web_ui_quality.outcome_verification import (
    build_outcome_hypothesis,
    classify_mutation_risk,
    evaluate_outcome,
    mutation_verification_plan,
)
from web_ui_quality.run_checkpoint import build_run_health, create_checkpoint, list_checkpoints, resume_checkpoint
from web_ui_quality.task_goal import auto_fix_allowed, create_task_goal, load_task_goal, update_task_goal


def _run(tmp_path: Path, *, task_id: str = "task-1") -> Path:
    root = tmp_path / "artifacts"
    run = create_experience_run(
        root,
        task_id=task_id,
        session_id="session-1",
        mode="CHECK",
        target={"kind": "url", "url": "https://example.test"},
        conditions={"viewport": "390x844"},
    )
    return Path(run["runDir"])


def _sealed_run(tmp_path: Path) -> Path:
    run_dir = _run(tmp_path)
    write_phase_file(run_dir, "before", "observation.json", '{"ok":true}')
    seal_before(run_dir)
    return run_dir


# Checkpoint / resume

def test_checkpoint_create_list_and_digest(tmp_path: Path):
    run_dir = _sealed_run(tmp_path)
    cp = create_checkpoint(run_dir, current_phase="before", active_capabilities=["PageHealth"])
    assert cp["checkpointDigest"]
    assert cp["writeAuthorization"] is False
    rows = list_checkpoints(run_dir)
    assert rows[0]["checkpointId"] == "checkpoint-0001"


def test_checkpoint_tamper_detection(tmp_path: Path):
    run_dir = _sealed_run(tmp_path)
    create_checkpoint(run_dir, current_phase="before")
    path = run_dir / "checkpoints" / "checkpoint-0001.json"
    value = json.loads(path.read_text())
    value["currentPhase"] = "after"
    path.write_text(json.dumps(value))
    with pytest.raises(ContractViolation) as caught:
        list_checkpoints(run_dir)
    assert caught.value.code == "CHECKPOINT_TAMPERED"


def test_resume_uses_sealed_before_as_reference_not_new_evidence(tmp_path: Path):
    run_dir = _sealed_run(tmp_path)
    create_checkpoint(run_dir, current_phase="before")
    resumed = resume_checkpoint(run_dir)
    assert resumed["beforeEvidence"] == "SEALED_REFERENCE_ONLY"
    assert resumed["writeAuthorization"] is False
    assert resumed["writeAuthority"] == "HOST_APPROVAL_REQUIRED"


def test_resume_wrong_task_rejected(tmp_path: Path):
    run_dir = _sealed_run(tmp_path)
    create_checkpoint(run_dir, current_phase="before")
    with pytest.raises(ContractViolation) as caught:
        resume_checkpoint(run_dir, task_id="different-task")
    assert caught.value.code == "CHECKPOINT_TASK_MISMATCH"


def test_missing_checkpoint_rejected(tmp_path: Path):
    run_dir = _sealed_run(tmp_path)
    with pytest.raises(ContractViolation) as caught:
        resume_checkpoint(run_dir)
    assert caught.value.code == "CHECKPOINT_NOT_FOUND"


def test_checkpoint_cannot_smuggle_write_authority(tmp_path: Path):
    run_dir = _sealed_run(tmp_path)
    cp = create_checkpoint(run_dir, current_phase="before", applied_writes=[{"path": "src/App.tsx"}])
    assert cp["writeAuthorization"] is False
    resumed = resume_checkpoint(run_dir)
    assert resumed["writeAuthorization"] is False


# Assumption invalidation graph

def test_assumption_supersede_invalidates_dependent_decision(tmp_path: Path):
    run_dir = _run(tmp_path)
    asm = add_assumption(run_dir, key="productType", value="marketing-site", source="inference")
    register_dependent_artifact(run_dir, artifact_id="decision-1", artifact_type="DECISION", assumption_ids=[asm["id"]])
    result = supersede_assumption(run_dir, assumption_id=asm["id"], new_value="internal-admin", source="user")
    assert result["invalidated"] == ["decision-1"]


def test_assumption_preserves_raw_evidence(tmp_path: Path):
    run_dir = _run(tmp_path)
    asm = add_assumption(run_dir, key="productType", value="marketing-site", source="inference")
    register_dependent_artifact(run_dir, artifact_id="shot-1", artifact_type="SCREENSHOT", assumption_ids=[asm["id"]])
    result = supersede_assumption(run_dir, assumption_id=asm["id"], new_value="internal-admin", source="user")
    assert result["retained"] == ["shot-1"]


def test_assumption_transitive_invalidation(tmp_path: Path):
    run_dir = _run(tmp_path)
    asm = add_assumption(run_dir, key="productType", value="marketing-site", source="inference")
    register_dependent_artifact(run_dir, artifact_id="finding-1", artifact_type="INTERPRETATION", assumption_ids=[asm["id"]])
    register_dependent_artifact(run_dir, artifact_id="decision-1", artifact_type="DECISION", depends_on=["finding-1"])
    result = supersede_assumption(run_dir, assumption_id=asm["id"], new_value="internal-admin", source="user")
    assert result["invalidated"] == ["decision-1", "finding-1"]


def test_assumption_no_silent_overwrite(tmp_path: Path):
    run_dir = _run(tmp_path)
    add_assumption(run_dir, key="productType", value="marketing-site", source="inference")
    with pytest.raises(ContractViolation) as caught:
        add_assumption(run_dir, key="productType", value="admin", source="user")
    assert caught.value.code == "ASSUMPTION_SILENT_OVERWRITE_FORBIDDEN"


def test_assumption_revalidation_policy(tmp_path: Path):
    run_dir = _run(tmp_path)
    asm = add_assumption(run_dir, key="journey", value="signup", source="user")
    register_dependent_artifact(run_dir, artifact_id="finding-1", artifact_type="INTERPRETATION", assumption_ids=[asm["id"]], invalidation_policy="REVALIDATE")
    result = supersede_assumption(run_dir, assumption_id=asm["id"], new_value="login", source="user")
    assert result["requiresRevalidation"] == ["finding-1"]


# Goal anchor

def test_goal_anchor_create_and_load(tmp_path: Path):
    run_dir = _run(tmp_path)
    created = create_task_goal(run_dir, task_id="task-1", goal="Improve signup completion", success_criteria=["signup completes"], non_goals=["dashboard cleanup"])
    loaded = load_task_goal(run_dir)
    assert loaded["goalDigest"] == created["goalDigest"]


@pytest.mark.parametrize("relevance,allowed", [("DIRECT", True), ("SUPPORTING", False), ("UNRELATED", False)])
def test_goal_relevance_autofix_default(relevance: str, allowed: bool):
    assert auto_fix_allowed(goal_relevance=relevance)["allowed"] is allowed


def test_goal_critical_safety_override():
    result = auto_fix_allowed(goal_relevance="UNRELATED", critical_safety=True)
    assert result == {"allowed": True, "reason": "CRITICAL_SAFETY_OVERRIDE", "goalRelevance": "UNRELATED"}


def test_goal_scope_expansion_recorded(tmp_path: Path):
    run_dir = _run(tmp_path)
    first = create_task_goal(run_dir, task_id="task-1", goal="Fix signup", success_criteria=["signup works"])
    changed = update_task_goal(run_dir, goal="Fix signup and login", reason="user expanded scope")
    assert changed["scopeChanges"][0]["previousDigest"] == first["goalDigest"]
    assert changed["scopeChanges"][0]["newGoal"] == "Fix signup and login"


# Capability routing

def test_login_page_routing():
    result = route_capabilities(page_type="login", profile="standard")
    assert {"PageHealth", "EvidenceIntegrity", "Form", "AuthenticationUX", "Accessibility"} <= set(result["activeCapabilities"])


def test_table_page_routing():
    result = route_capabilities(page_type="table", profile="standard")
    assert {"Table", "DataDensity", "Overflow", "ResponsiveTable"} <= set(result["activeCapabilities"])


def test_simple_component_minimal_avoids_full_inventory():
    result = route_capabilities(page_type="component", profile="minimal")
    active = set(result["activeCapabilities"])
    assert "ComponentQuality" in active
    assert "Conversion" not in active


def test_full_audit_routing_loads_broad_pipeline():
    result = route_capabilities(page_type="marketing", profile="full")
    assert {"Conversion", "Table", "AuthenticationUX", "ResourceIntegrity"} <= set(result["activeCapabilities"])


def test_mandatory_safety_capability_cannot_be_disabled():
    with pytest.raises(ContractViolation) as caught:
        route_capabilities(profile="minimal", disabled=["EvidenceIntegrity"])
    assert caught.value.code == "MANDATORY_CAPABILITY_DISABLE_FORBIDDEN"


def test_high_risk_escalates_safety_capabilities():
    result = route_capabilities(profile="minimal", page_type="generic", risk="HIGH")
    assert {"Accessibility", "Interaction", "ResourceIntegrity"} <= set(result["activeCapabilities"])


# Decision ledger

def _decision(run_dir: Path):
    return create_decision(
        run_dir,
        issue="Primary Button Height",
        evidence=["design token = 40px", "production = 38px"],
        constraints=["header max height"],
        options=[{"id": "A", "label": "40px"}, {"id": "C", "label": "responsive 40/44", "tradeoffs": "more CSS complexity"}],
        selected_option="C",
        rationale="desktop consistency and mobile touch target",
        rejected_options=["A"],
        expected_outcome=["mobile target improves"],
        risks=["390px header overflow"],
        risk_triggers=["header overflow"],
        verification_plan=["390 screenshot", "click test"],
        related_findings=["F-1"],
        related_patches=["P-1"],
    )


def test_decision_create_and_linkages(tmp_path: Path):
    run_dir = _run(tmp_path)
    dec = _decision(run_dir)
    assert dec["relatedFindings"] == ["F-1"]
    assert dec["relatedPatches"] == ["P-1"]


def test_decision_supersede_preserves_history(tmp_path: Path):
    run_dir = _run(tmp_path)
    first = _decision(run_dir)
    second = supersede_decision(run_dir, first["decisionId"], selectedOption="A", rationale="new constraint")
    ledger = load_decision_ledger(run_dir)
    old = ledger["entries"][0]
    assert old["status"] == "SUPERSEDED"
    assert old["supersededBy"] == second["decisionId"]
    assert second["supersedes"] == first["decisionId"]


def test_decision_verification_status(tmp_path: Path):
    run_dir = _run(tmp_path)
    dec = _decision(run_dir)
    updated = update_verification_status(run_dir, dec["decisionId"], "VERIFIED")
    assert updated["status"] == "VERIFIED"


def test_malformed_decision_ledger_detected(tmp_path: Path):
    run_dir = _run(tmp_path)
    _decision(run_dir)
    path = run_dir / "governance" / "decision-ledger.json"
    path.write_text('{"schemaVersion":"1","entries":{}}')
    with pytest.raises(ContractViolation):
        load_decision_ledger(run_dir)


# Natural language control

@pytest.mark.parametrize(
    "text, expected",
    [
        ("先别改，只看看", {"action": "CHECK", "mutation": "FORBIDDEN"}),
        ("直接修最严重的三个", {"action": "FIX", "scope": "TOP_3"}),
        ("只看当前页", {"action": "CHECK", "scope": "CURRENT"}),
        ("全面检查", {"action": "CHECK", "profile": "full"}),
        ("回到修改按钮之前", {"action": "RESUME", "resumeTarget": "LOOKUP_BY_DESCRIPTION"}),
        ("刚才那个假设错了", {"action": "REVISE_ASSUMPTION", "assumptionRevision": True}),
        ("先停一下", {"action": "CHECKPOINT"}),
        ("继续上次任务", {"action": "RESUME", "resumeTarget": "LATEST_COMPATIBLE"}),
    ],
)
def test_control_intent_examples(text, expected):
    result = parse_control_intent(text)
    for key, value in expected.items():
        assert result[key] == value


def test_control_intent_protected_scope():
    result = parse_control_intent("修一下，但不要动登录页")
    assert "登录页" in result["protectedScope"]
    assert result["mutation"] == "HOST_GATED"


def test_control_intent_ambiguous_mutation_safe_fallback():
    result = parse_control_intent("改得更好看一点")
    assert result["action"] == "NEEDS_EXPLICIT_SCOPE"
    assert result["mutation"] == "FORBIDDEN"
    assert result["safeFallback"] is True


# Outcome + serial verification + run health

def test_outcome_requires_declared_acceptance_criteria():
    with pytest.raises(ContractViolation):
        build_outcome_hypothesis(finding_id="F-1", expected_outcome=["CTA visible"], acceptance_criteria=[])


def test_outcome_not_verified_when_any_check_missing():
    h = build_outcome_hypothesis(finding_id="F-1", expected_outcome=["CTA visible"], acceptance_criteria=["visible", "click works"])
    result = evaluate_outcome(h, {"visible": True})
    assert result["status"] == "NOT_VERIFIED"


def test_outcome_verified_only_when_all_checks_pass():
    h = build_outcome_hypothesis(finding_id="F-1", expected_outcome=["CTA visible"], acceptance_criteria=["visible", "click works"])
    result = evaluate_outcome(h, {"visible": True, "click works": True})
    assert result["status"] == "VERIFIED"


def test_high_risk_mutation_is_serial():
    assert classify_mutation_risk(touches_auth=True) == "HIGH"
    plan = mutation_verification_plan([{"findingId": "F-1", "touchesAuth": True}, {"findingId": "F-2"}])
    assert plan["strategy"] == "SERIAL"
    assert plan["mutations"][0]["verifyBeforeNext"] is True


def test_run_health_reports_checkpoint_count(tmp_path: Path):
    run_dir = _sealed_run(tmp_path)
    create_checkpoint(run_dir, current_phase="before")
    health = build_run_health(run_dir, active_capabilities=["PageHealth"])
    assert health["checkpoints"] == 1
    assert health["activeCapabilities"] == ["PageHealth"]


def test_control_intent_extracts_resume_query():
    result = parse_control_intent("回到修改按钮之前")
    assert result["resumeTarget"] == "LOOKUP_BY_DESCRIPTION"
    assert result["resumeQuery"] == "修改按钮"


def test_checkpoint_description_lookup_returns_parent(tmp_path: Path):
    from web_ui_quality.run_checkpoint import find_checkpoint_before
    run_dir = _sealed_run(tmp_path)
    first = create_checkpoint(run_dir, current_phase="before", decisions=[{"issue": "baseline"}])
    create_checkpoint(run_dir, current_phase="before", decisions=[{"issue": "修改按钮", "selectedOption": "44px"}])
    selected = find_checkpoint_before(run_dir, "修改按钮")
    assert selected["checkpointId"] == first["checkpointId"]


def test_experience_fix_pause_creates_checkpoint_without_browser(tmp_path: Path):
    from web_ui_quality.experience_fix import _target_identity, run_experience_fix
    target = "https://example.test/"
    identity, _, _ = _target_identity(target, None)
    run = create_experience_run(
        tmp_path / "artifacts", task_id="task-pause", session_id="session-pause", mode="CHECK",
        target=identity, conditions={"placeholder": True},
    )
    result = run_experience_fix(
        target, tmp_path / "artifacts", request="先停一下", task_id="task-pause", session_id="session-pause",
        existing_run=run["runDir"],
    )
    assert result["status"] == "CHECKPOINTED"
    assert result["writeAuthorization"] is False
    assert result["checkpoint"]["writeAuthorization"] is False


def test_experience_fix_resume_restores_state_without_authority(tmp_path: Path):
    from web_ui_quality.experience_fix import _target_identity, run_experience_fix
    target = "https://example.test/"
    identity, _, _ = _target_identity(target, None)
    run = create_experience_run(
        tmp_path / "artifacts", task_id="task-resume", session_id="session-resume", mode="CHECK",
        target=identity, conditions={"placeholder": True},
    )
    create_checkpoint(run["runDir"], current_phase="before")
    result = run_experience_fix(
        target, tmp_path / "artifacts", request="继续上次任务", task_id="task-resume", session_id="session-resume",
        existing_run=run["runDir"],
    )
    assert result["status"] == "RESUMED"
    assert result["checkpoint"]["writeAuthorization"] is False
    assert result["writeAuthority"] == "HOST_APPROVAL_REQUIRED"


def test_assumption_revision_phrase_stops_for_explicit_old_and_new_values(tmp_path: Path):
    from web_ui_quality.experience_fix import run_experience_fix
    result = run_experience_fix(
        "https://example.test/", tmp_path / "artifacts", request="刚才那个假设错了",
        task_id="task-a", session_id="session-a",
    )
    assert result["status"] == "NEEDS_EXPLICIT_ASSUMPTION_REVISION"
    assert result["requiredFields"] == ["assumptionId", "newValue"]
    assert result["writeAuthorization"] is False
