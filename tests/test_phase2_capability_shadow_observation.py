from __future__ import annotations

import json
from pathlib import Path

from web_ui_quality.phase1_shadow import build_shadow_observation
from web_ui_quality.phase2_capability_observer import observe_capability_signals
from web_ui_quality.phase2_signal_analysis import summarize_signal_observations
from web_ui_quality.schema_validation import validate_instance

ROOT = Path(__file__).resolve().parents[1]


def _base_result(**updates):
    value = {"status": "NOT_VERIFIED", "taskResult": {"status": "NOT_VERIFIED"}}
    value.update(updates)
    return value


def test_capability_observer_is_non_authoritative_and_has_no_profile_decision():
    observed = observe_capability_signals(
        selected_mode="CHECK",
        intent_route={"writeRequested": False, "readOnlyRequired": True},
        control_intent={"protectedScope": ["auth"]},
        fixed_result=_base_result(),
    )
    assert observed["mode"] == "SHADOW_ONLY"
    assert observed["authoritative"] is False
    assert observed["semanticSignalsUsed"] is False
    assert observed["authorityEffect"] == "NONE"
    assert observed["adaptiveEffect"] == "NONE"
    assert observed["summary"]["profileRecommendation"] == "NOT_EVALUATED_UNTIL_SIGNAL_VALIDITY_GATE"
    assert all(row["authorityEffect"] == "NONE" and row["adaptiveEffect"] == "NONE" for row in observed["mechanicalSignals"] + observed["derivedDeterministicSignals"])


def test_tool_failure_with_success_claim_is_deterministic_negative_signal():
    observed = observe_capability_signals(
        selected_mode="FIX_AND_VERIFY",
        intent_route={"writeRequested": True, "readOnlyRequired": False},
        control_intent={"protectedScope": []},
        fixed_result={
            "status": "VERIFIED",
            "taskResult": {"status": "VERIFIED"},
            "hostWriteReceipt": {"receiptId": "r"},
            "projectToolEvidence": [{"tool": "tests", "status": "FAIL"}],
            "after": {"status": "PASS"},
        },
    )
    rows = {row["code"]: row for row in observed["derivedDeterministicSignals"]}
    assert rows["TOOL_FAILURE_WITH_SUCCESS_CLAIM_CONFLICT"]["polarity"] == "NEGATIVE"
    assert rows["TOOL_FAILURE_WITH_SUCCESS_CLAIM_CONFLICT"]["capabilityEligible"] is True


def test_read_only_with_receipt_is_deterministic_negative_signal():
    observed = observe_capability_signals(
        selected_mode="CHECK",
        intent_route={"writeRequested": False, "readOnlyRequired": True},
        control_intent={"protectedScope": []},
        fixed_result={"status": "PASS", "taskResult": {"status": "PASS"}, "hostWriteReceipt": {"receiptId": "r"}},
    )
    codes = {row["code"] for row in observed["derivedDeterministicSignals"]}
    assert "READ_ONLY_WITH_WRITE_RECEIPT_CONFLICT" in codes


def test_uncertainty_preservation_is_positive_honesty_signal():
    observed = observe_capability_signals(
        selected_mode="FIX_AND_VERIFY",
        intent_route={"writeRequested": True, "readOnlyRequired": False},
        control_intent={"protectedScope": []},
        fixed_result=_base_result(),
    )
    rows = {row["code"]: row for row in observed["derivedDeterministicSignals"]}
    assert rows["UNCERTAINTY_PRESERVED_BY_FIXED_WORKFLOW"]["polarity"] == "POSITIVE"


def test_capability_shadow_schema_validates_nested_observation():
    shadow = build_shadow_observation(
        run_id="r", task_id="t", session_id="s", request="private request",
        selected_mode="CHECK", target_kind="url",
        intent_route={"intent": "CHECK", "specialty": "RESPONSIVE", "writeRequested": False, "readOnlyRequired": True},
        control_intent={"action": "CHECK", "profile": "standard", "protectedScope": []},
        fixed_result=_base_result(),
    )
    schema = json.loads((ROOT / "schemas/capability-shadow-observation-v1.schema.json").read_text(encoding="utf-8"))
    validate_instance(shadow["capabilitySignalObservation"], schema, base_dir=ROOT / "schemas")
    assert "private request" not in json.dumps(shadow, ensure_ascii=False)


def test_offline_summary_does_not_claim_predictive_validity():
    shadow = build_shadow_observation(
        run_id="r", task_id="t", session_id="s", request="x",
        selected_mode="CHECK", target_kind="url",
        intent_route={"intent": "CHECK", "specialty": None, "writeRequested": False, "readOnlyRequired": True},
        control_intent={"action": "CHECK", "profile": "standard", "protectedScope": []},
        fixed_result=_base_result(),
    )
    summary = summarize_signal_observations([shadow])
    assert summary["runCount"] == 1
    assert summary["predictiveValidity"] == "NOT_MEASURED"
    assert summary["profileRecommendation"] == "NOT_EVALUATED_UNTIL_SIGNAL_VALIDITY_GATE"
    assert summary["authorityEffect"] == "NONE"


def test_real_run_persists_capability_signal_observation(tmp_path: Path, monkeypatch):
    import web_ui_quality.experience_fix as ef

    def fake_acceptance(*args, **kwargs):
        output = Path(kwargs["output_dir"])
        output.mkdir(parents=True, exist_ok=True)
        report = {
            "status": "PASS",
            "pageHealth": {"pageStatus": "PASS"},
            "journey": {"journeyId": "primary", "status": "PASS", "journey": [], "runs": [{"status": "PASS"}]},
            "findings": [], "topFindings": [], "deliveryConclusion": "alpha4 capability shadow fixture", "open": "index.html",
        }
        (output / "smart-acceptance-report.json").write_text(json.dumps(report), encoding="utf-8")
        return report

    monkeypatch.setattr(ef, "run_smart_acceptance", fake_acceptance)
    artifacts = tmp_path / "artifacts"
    result = ef.run_experience_fix(
        "https://example.test/", artifacts, request="只检查响应式，不要改代码",
        mode="CHECK", task_id="cso-task", session_id="cso-session",
    )
    assert result["status"] == "PASS"
    run_dir = next(artifacts.glob("wuq-*"))
    observation_path = next((run_dir / "experimental" / "phase1-shadow").glob("*-observation.json"))
    observation = json.loads(observation_path.read_text(encoding="utf-8"))
    signal_observation = observation["capabilitySignalObservation"]
    assert signal_observation["mode"] == "SHADOW_ONLY"
    assert signal_observation["adaptiveEffect"] == "NONE"
    assert signal_observation["summary"]["profileRecommendation"] == "NOT_EVALUATED_UNTIL_SIGNAL_VALIDITY_GATE"
    assert "只检查响应式" not in observation_path.read_text(encoding="utf-8")
