#!/usr/bin/env python3
"""Independent acceptance for Web UI Quality 4.0.0-rc.1 Agent Workflow Governance."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import sys

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime" / "python"
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from web_ui_quality.assumption_graph import add_assumption, register_dependent_artifact, supersede_assumption
from web_ui_quality.capability_router import route_capabilities
from web_ui_quality.control_intent import parse_control_intent
from web_ui_quality.decision_ledger import create_decision, supersede_decision, load_decision_ledger
from web_ui_quality.experience_run import create_experience_run, write_phase_file, seal_before
from web_ui_quality.outcome_verification import build_outcome_hypothesis, evaluate_outcome, mutation_verification_plan
from web_ui_quality.run_checkpoint import create_checkpoint, resume_checkpoint
from web_ui_quality.task_goal import create_task_goal, update_task_goal
from web_ui_quality.release_info import PACKAGE_VERSION

EXPECTED_VERSION = "4.3.0"


def main() -> int:
    if PACKAGE_VERSION != EXPECTED_VERSION:
        raise RuntimeError(f"version mismatch: {PACKAGE_VERSION}")
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        run = create_experience_run(
            root / "artifacts", task_id="acceptance-task", session_id="acceptance-session", mode="CHECK",
            target={"kind": "url", "url": "https://example.test/login"}, conditions={"viewport": "390x844"},
        )
        run_dir = Path(run["runDir"])
        goal = create_task_goal(run_dir, task_id="acceptance-task", goal="Improve login completion", success_criteria=["login remains usable"], non_goals=["dashboard redesign"])
        updated_goal = update_task_goal(run_dir, reason="protect login scope", add_non_goals=["billing page"])
        if not updated_goal.get("scopeChanges") or updated_goal.get("goalDigest") == goal.get("goalDigest"):
            raise RuntimeError("Task Goal scope history missing")

        asm = add_assumption(run_dir, key="productType", value="marketing-site", source="inference")
        register_dependent_artifact(run_dir, artifact_id="shot-1", artifact_type="SCREENSHOT", assumption_ids=[asm["id"]])
        register_dependent_artifact(run_dir, artifact_id="finding-1", artifact_type="INTERPRETATION", assumption_ids=[asm["id"]])
        register_dependent_artifact(run_dir, artifact_id="decision-1", artifact_type="DECISION", depends_on=["finding-1"])
        invalidation = supersede_assumption(run_dir, assumption_id=asm["id"], new_value="internal-admin", source="user")
        if "shot-1" not in invalidation["retained"] or set(invalidation["invalidated"]) != {"finding-1", "decision-1"}:
            raise RuntimeError("assumption invalidation boundary failed")

        routing = route_capabilities(page_type="login", profile="standard", risk="HIGH")
        if not {"PageHealth", "EvidenceIntegrity", "AuthenticationUX", "Accessibility"}.issubset(routing["activeCapabilities"]):
            raise RuntimeError("capability routing safety floor failed")

        control_cases = {
            "先别改，只看看": ("CHECK", "FORBIDDEN"),
            "直接修最严重的三个": ("FIX", "HOST_GATED"),
            "全面检查": ("CHECK", "FORBIDDEN"),
            "继续上次任务": ("RESUME", "FORBIDDEN"),
        }
        for text, expected in control_cases.items():
            value = parse_control_intent(text)
            if (value["action"], value["mutation"]) != expected:
                raise RuntimeError(f"control intent mismatch: {text}")
        ambiguous = parse_control_intent("改得更顺眼一些")
        if ambiguous["action"] != "NEEDS_EXPLICIT_SCOPE" or ambiguous["mutation"] != "FORBIDDEN":
            raise RuntimeError("ambiguous mutation did not fail closed")

        dec = create_decision(
            run_dir, issue="Primary Button Height", evidence=["token=40px", "production=38px"], constraints=["header max height"],
            options=[{"id": "A", "label": "40px"}, {"id": "C", "label": "40/44 responsive"}], selected_option="C",
            rationale="desktop consistency; mobile touch target", rejected_options=["A"], expected_outcome=["mobile target improves"],
            risks=["390px overflow"], risk_triggers=["header overflow"], verification_plan=["390/768/1440 screenshots", "click test"],
            related_findings=["F-1"], related_patches=["P-1"],
        )
        successor = supersede_decision(run_dir, dec["decisionId"], selectedOption="A", rationale="new header constraint")
        ledger = load_decision_ledger(run_dir)
        if ledger["entries"][0]["status"] != "SUPERSEDED" or successor["supersedes"] != dec["decisionId"]:
            raise RuntimeError("decision supersession history failed")

        hypothesis = build_outcome_hypothesis(finding_id="F-1", expected_outcome=["primary CTA remains visible"], acceptance_criteria=["visible", "click works", "390 no overflow"])
        if evaluate_outcome(hypothesis, {"visible": True, "click works": True})["status"] != "NOT_VERIFIED":
            raise RuntimeError("missing acceptance check incorrectly verified")
        if evaluate_outcome(hypothesis, {"visible": True, "click works": True, "390 no overflow": True})["status"] != "VERIFIED":
            raise RuntimeError("complete outcome verification failed")
        serial = mutation_verification_plan([{"findingId": "F-1", "risk": "HIGH"}, {"findingId": "F-2", "risk": "LOW"}])
        if serial["strategy"] != "SERIAL" or serial["mutations"][0]["verifyBeforeNext"] is not True:
            raise RuntimeError("high-risk serial mutation policy failed")

        write_phase_file(run_dir, "before", "browser-observation.json", '{"status":"observed"}')
        seal_before(run_dir)
        cp = create_checkpoint(run_dir, current_phase="before", task_goal=updated_goal, active_capabilities=routing["activeCapabilities"])
        resumed = resume_checkpoint(run_dir, cp["checkpointId"], task_id="acceptance-task")
        if resumed["beforeEvidence"] != "SEALED_REFERENCE_ONLY" or resumed["writeAuthorization"] is not False:
            raise RuntimeError("checkpoint resume crossed evidence/write boundary")

    print(json.dumps({
        "status": "PASS",
        "version": EXPECTED_VERSION,
        "goalAnchor": "PASS",
        "assumptionInvalidation": "PASS",
        "capabilityRouting": "PASS",
        "decisionLedger": "PASS",
        "controlIntent": "PASS",
        "outcomeVerification": "PASS",
        "serialMutationVerification": "PASS",
        "checkpointResume": "PASS",
        "hostWriteBoundary": "PRESERVED",
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
