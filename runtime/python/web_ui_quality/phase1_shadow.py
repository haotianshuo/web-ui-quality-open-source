"""Phase-1 runtime shadow observer.

This module is deliberately side-effect free.  It can observe the same task and
Fixed Workflow result that production ``run`` sees, but it cannot write project
files, issue authority, mutate claims, or change the Fixed Workflow result.
Persistence of the returned observation is performed by the legacy run layer in
an explicitly non-authoritative experimental artifact directory.
"""
from __future__ import annotations

from typing import Any, Mapping

from .contracts import digest_json
from .release_info import KERNEL_BASE_VERSION, PACKAGE_VERSION
from .phase2_capability_observer import observe_capability_signals
from .adaptive_intelligence import (
    TaskFingerprint,
    TaskGraph,
    build_execution_budget,
    consume_budget,
    complexity_delta,
    build_traceability_report,
    shadow_supervisor,
    verification_profile,
)

ADAPTIVE_RUNTIME_MODE = "SHADOW_ONLY"
SHADOW_SCHEMA_VERSION = "2"


def _observed_task_state(fixed_result: Mapping[str, Any]) -> str:
    """Map the fixed workflow outcome to a conservative Shadow task state."""
    task_result = fixed_result.get("taskResult") if isinstance(fixed_result.get("taskResult"), Mapping) else {}
    outcome = str(task_result.get("outcome") or "").upper()
    raw = str(task_result.get("subjectStatus") or fixed_result.get("status") or "").upper()
    if outcome == "VERIFIED" or raw == "VERIFIED":
        return "VERIFIED"
    if outcome == "FAILED" or raw in {"FAIL", "FAILED", "REJECTED", "BLOCKED", "REGRESSED", "INVALID"}:
        return "FAILED"
    if outcome == "REVIEW_REQUIRED" or raw in {"AWAITING_HOST_WRITE", "SCOPE_NOT_CONFIRMED", "REVIEW_REQUIRED"}:
        return "BLOCKED"
    if outcome == "COMPLETED" or raw in {"PASS", "COMPLETED"}:
        return "PARTIAL"
    return "NOT_VERIFIED"


def _build_adaptive_control_plane(
    *,
    task_id: str,
    selected_mode: str,
    target_kind: str,
    control_intent: Mapping[str, Any],
    task_goal: Mapping[str, Any] | None,
    fixed_result: Mapping[str, Any],
) -> dict[str, Any]:
    """Build deterministic 4.3 observations from one real Fixed Workflow run.

    Every value is a digest, count, or generic contract label.  User request
    text, project paths, and patch contents are intentionally not copied into
    the experimental artifact.
    """
    goal = str((task_goal or {}).get("goal") or "Fixed Workflow execution")
    criteria = list((task_goal or {}).get("successCriteria") or ())
    if not criteria:
        criteria = ["fixed workflow result remains authoritative"]
    protected = list(control_intent.get("protectedScope") or ())
    if not protected:
        protected = ["<none-declared>"]
    baseline = fixed_result.get("projectBaseline") if isinstance(fixed_result.get("projectBaseline"), Mapping) else {}
    project_identity = {
        "targetKind": target_kind,
        "sourceDigest": str(baseline.get("baselineDigest") or "NOT_MEASURED"),
    }
    fingerprint = TaskFingerprint.build(
        project_identity=project_identity,
        goal=goal,
        success_criteria=criteria,
        protected_scope=protected,
    )

    risk = "HIGH" if selected_mode == "FIX_AND_VERIFY" else "MEDIUM" if selected_mode in {"DEEP_REDESIGN", "SPECIALIZED_AUDIT"} else "LOW"
    budget = build_execution_budget(risk=risk, long_task=selected_mode in {"DEEP_REDESIGN", "SPECIALIZED_AUDIT"})
    usage = {
        "read": int(bool(fixed_result.get("before") or fixed_result.get("audit"))),
        "context": int(bool(fixed_result.get("contextPacket"))),
        "tool": len(fixed_result.get("projectToolPlans") or ()) if isinstance(fixed_result.get("projectToolPlans"), list) else 0,
        "browser": len(((fixed_result.get("before") or {}).get("runtime") or {}).get("records") or ()) if isinstance(fixed_result.get("before"), Mapping) else 0,
        "retry": 0,
        "replan": 0,
        "noProgress": 0,
    }
    budget_events: list[dict[str, Any]] = []
    for kind, amount in usage.items():
        if not amount:
            continue
        event = consume_budget(budget, kind, amount)
        budget_events.append({key: value for key, value in event.items() if key != "budget"})
        if event.get("status") != "PASS":
            break
        budget = dict(event["budget"])

    graph = TaskGraph()
    task_state = _observed_task_state(fixed_result)
    # Keep the legacy summary node for compatibility, then expose bounded stage
    # observations.  The stage nodes are observational only and never replace the
    # authoritative Fixed Workflow state machine.
    graph.add_task(
        task_id,
        goal="Execute the bounded Fixed Workflow task",
        scope=["<protected-scope-digest>"],
        risk=risk,
        budget={"budgetDigest": digest_json(budget)},
        expected_evidence=["fixedWorkflowObservation", "capabilitySignalObservation"],
        success_criteria=["fixed workflow result remains authoritative"],
        status=task_state,
    )
    stage_specs = [
        ("baseline", bool(baseline), "Observe sealed or measured project baseline"),
        ("diagnose", bool(fixed_result.get("before") or fixed_result.get("audit")), "Observe diagnosis/before evidence"),
        ("plan", bool(fixed_result.get("fixPlan") or fixed_result.get("implementationPlan")), "Observe bounded plan"),
        ("host-apply", bool(fixed_result.get("hostWriteReceipt") or fixed_result.get("writeReceipt")), "Observe Host mutation receipt"),
        ("verify", task_state == "VERIFIED", "Observe final verification"),
    ]
    for stage_name, observed, stage_goal in stage_specs:
        graph.add_task(
            f"{task_id}:{stage_name}", goal=stage_goal, scope=["<protected-scope-digest>"],
            risk=risk, expected_evidence=[stage_name],
            success_criteria=["observation present"],
            status="VERIFIED" if observed else "NOT_VERIFIED",
        )
    supervisor = shadow_supervisor(
        graph=graph,
        budget=budget,
        current_task_id=None,
    )
    fix_plan = fixed_result.get("fixPlan") if isinstance(fixed_result.get("fixPlan"), Mapping) else {}
    changed_files = [str(row.get("path")) for row in fix_plan.get("files", []) if isinstance(row, Mapping) and row.get("path")]
    added_files = [str(row.get("path")) for row in fix_plan.get("files", []) if isinstance(row, Mapping) and row.get("path") and str(row.get("operation") or row.get("action") or "").upper() in {"ADD", "CREATE", "NEW"}]
    complexity = complexity_delta(added_files=added_files, changed_files=changed_files, goal_size="SMALL" if selected_mode == "FIX_AND_VERIFY" else "NORMAL")
    traceability = build_traceability_report(
        goal_digest=fingerprint.goal_digest,
        hunks=(),
        enforce=False,
    )
    return {
        "schemaVersion": "1",
        "mode": "SHADOW_ONLY",
        "taskFingerprint": fingerprint.to_dict(),
        "taskGraph": graph.to_dict(),
        "observedTaskState": task_state,
        "executionBudget": budget,
        "budgetUsage": usage,
        "budgetEvents": budget_events,
        "supervisor": supervisor,
        "complexityDelta": complexity,
        "traceability": traceability,
        "verificationProfiles": [verification_profile("HARDEN_PROFILE"), verification_profile("ADAPT_PROFILE")],
        "authority": {
            "writeAuthority": False,
            "claimAuthority": False,
            "mayChangeTaskResult": False,
            "mayChangeGuidance": False,
            "requiresHostApprovalForMutation": True,
        },
        "claimBoundary": "4.3 control-plane fields are Shadow observations only; the 4.2.3 Fixed Workflow and Host authority remain authoritative.",
    }


def adaptive_runtime_status() -> dict[str, object]:
    return {
        "mode": ADAPTIVE_RUNTIME_MODE,
        "productionWired": True,
        "authoritative": False,
        "mayChangeGuidance": False,
        "mayChangeCheckpointFrequency": False,
        "mayChangeContextBreadth": False,
        "mayChangeExploration": False,
        "mayChangeWriteAuthority": False,
        "maySetClaimStatus": False,
        "claimBoundary": "Fixed Workflow remains authoritative; shadow output is observation-only and cannot alter execution, authority, evidence, claims, or TaskResult.",
    }


def build_shadow_observation(
    *,
    run_id: str,
    task_id: str,
    session_id: str,
    request: str | None,
    selected_mode: str,
    target_kind: str,
    intent_route: Mapping[str, Any],
    control_intent: Mapping[str, Any],
    fixed_result: Mapping[str, Any],
    task_goal: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a non-authoritative observation of one real Fixed Workflow run."""
    fixed_task = fixed_result.get("taskResult") if isinstance(fixed_result.get("taskResult"), Mapping) else {}
    route = {
        "intent": intent_route.get("intent"),
        "specialty": intent_route.get("specialty"),
        "writeRequested": intent_route.get("writeRequested"),
        "readOnlyRequired": intent_route.get("readOnlyRequired"),
    }
    control = {
        "action": control_intent.get("action"),
        "profile": control_intent.get("profile"),
        "protectedScopeCount": len(control_intent.get("protectedScope") or []),
    }
    value: dict[str, Any] = {
        "schemaVersion": SHADOW_SCHEMA_VERSION,
        "producer": "web-ui-quality-phase1-runtime-shadow",
        "packageVersion": PACKAGE_VERSION,
        "kernelBaseVersion": KERNEL_BASE_VERSION,
        "mode": ADAPTIVE_RUNTIME_MODE,
        "authoritative": False,
        "taskBinding": {"runId": run_id, "taskId": task_id, "sessionId": session_id},
        "requestDigest": digest_json({"request": request or ""}),
        "observedInput": {
            "selectedMode": selected_mode,
            "targetKind": target_kind,
            "intentRoute": route,
            "controlIntent": control,
        },
        "fixedWorkflowObservation": {
            "status": fixed_result.get("status"),
            "taskResultStatus": fixed_task.get("status"),
            "writeAuthority": fixed_result.get("writeAuthority") or "LEGACY_FIXED_WORKFLOW",
        },
        "hostBoundary": {
            "realCodexHostEnforcement": "NOT_MEASURED",
            "capabilitySnapshot": "NOT_PROVIDED_TO_SHADOW",
        },
        "capabilitySignalObservation": observe_capability_signals(
            selected_mode=selected_mode,
            intent_route=intent_route,
            control_intent=control_intent,
            fixed_result=fixed_result,
        ),
        "adaptiveControlPlane": _build_adaptive_control_plane(
            task_id=task_id,
            selected_mode=selected_mode,
            target_kind=target_kind,
            control_intent=control_intent,
            task_goal=task_goal,
            fixed_result=fixed_result,
        ),
        "adaptiveObservation": {
            "profileSuggestion": "NOT_EVALUATED_UNTIL_SIGNAL_VALIDITY_GATE",
            "clampSuggestion": "NOT_EVALUATED_UNTIL_SIGNAL_VALIDITY_GATE",
            "mayInfluenceCurrentRun": False,
        },
        "invariants": {
            "fixedWorkflowAuthoritative": True,
            "mayAuthorizeWrite": False,
            "maySetClaimStatus": False,
            "mayChangeTaskResult": False,
            "mayChangeGuidance": False,
            "mayChangeCheckpointFrequency": False,
            "mayChangeContextBreadth": False,
            "mayChangeExploration": False,
        },
    }
    value["observationDigest"] = digest_json(value)
    return value


__all__ = [
    "ADAPTIVE_RUNTIME_MODE",
    "SHADOW_SCHEMA_VERSION",
    "adaptive_runtime_status",
    "build_shadow_observation",
]
