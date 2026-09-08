from __future__ import annotations

from web_ui_quality.adaptive_intelligence import (
    build_authorization_binding,
    build_traceability_report,
    complexity_delta,
    memory_authority_decision,
    qualify_design_finding,
)


def test_missing_real_hunks_are_not_measured_not_pass():
    result = build_traceability_report(goal_digest="goal", hunks=(), enforce=False)
    assert result["status"] == "NOT_MEASURED"
    assert result["reason"] == "PATCH_HUNKS_NOT_AVAILABLE"


def test_changed_existing_files_do_not_count_as_added_architecture():
    result = complexity_delta(changed_files=["a.py", "b.py", "c.py"], goal_size="SMALL")
    assert result["changedFiles"] == 3
    assert result["addedFiles"] == 0
    assert result["status"] == "NORMAL"


def test_subjective_design_finding_can_never_become_verification_input():
    result = qualify_design_finding(
        {"id": "generic-cards"}, subjective=True,
        rule_applicable=True, required_by_task_or_contract=True,
        evidence_class="E6", minimum_required="E1", evidence_fresh=True,
    )
    assert result["verificationEligible"] is False
    assert result["authority"] == "ADVISORY"


def test_objective_design_finding_requires_fresh_sufficient_evidence():
    insufficient = qualify_design_finding(
        {"id": "overflow"}, subjective=False,
        rule_applicable=True, required_by_task_or_contract=True,
        evidence_class="E2", minimum_required="E3", evidence_fresh=True,
    )
    assert insufficient["verificationEligible"] is False
    qualified = qualify_design_finding(
        {"id": "overflow"}, subjective=False,
        rule_applicable=True, required_by_task_or_contract=True,
        evidence_class="E4", minimum_required="E3", evidence_fresh=True,
    )
    assert qualified["verificationEligible"] is True
    assert qualified["authority"] == "VERIFICATION_INPUT"


def test_memory_write_requires_policy_binding_verified_source_redaction_consent_and_encryption():
    denied = memory_authority_decision(
        operation="WRITE", same_project=True, same_tenant=True, policy_permitted=True,
        verified_source=True, redaction_pass=True, consent=True,
        encryption_required=True, encryption_available=False,
    )
    assert denied["allowed"] is False
    assert "MEMORY_WRITE_DENIED_ENCRYPTION_UNAVAILABLE" in denied["reasons"]
    allowed = memory_authority_decision(
        operation="WRITE", same_project=True, same_tenant=True, policy_permitted=True,
        verified_source=True, redaction_pass=True, consent=True,
        encryption_required=True, encryption_available=True,
    )
    assert allowed["allowed"] is True
    assert allowed["persistentWritePerformed"] is False


def test_authorization_binding_is_candidate_only_and_never_write_authority():
    result = build_authorization_binding(
        task_fingerprint="t", selected_candidate_digest="c", plan_digest_value="p",
        source_scope_digest="s", protected_scope_digest="ps", risk_digest="r",
        budget_digest="b", change_intent_digest="ci",
    )
    assert result["authorizationState"] == "CANDIDATE_ONLY"
    assert result["hostApplyRequired"] is True
    assert result["receiptProtocolRequired"] == "V3"
    assert result["writeAuthority"] is False
    assert result["claimAuthority"] is False
