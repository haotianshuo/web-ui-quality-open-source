from __future__ import annotations

import json
from pathlib import Path

from web_ui_quality.phase1_shadow import adaptive_runtime_status, build_shadow_observation


def _fake_acceptance(*args, **kwargs):
    output = Path(kwargs["output_dir"])
    output.mkdir(parents=True, exist_ok=True)
    report = {
        "status": "PASS",
        "pageHealth": {"pageStatus": "PASS"},
        "journey": {"journeyId": "primary", "status": "PASS", "journey": [], "runs": [{"status": "PASS"}]},
        "findings": [],
        "topFindings": [],
        "deliveryConclusion": "shadow wiring fixture",
        "open": "index.html",
    }
    (output / "smart-acceptance-report.json").write_text(json.dumps(report), encoding="utf-8")
    return report


def test_shadow_status_is_production_wired_but_non_authoritative():
    status = adaptive_runtime_status()
    assert status["mode"] == "SHADOW_ONLY"
    assert status["productionWired"] is True
    assert status["authoritative"] is False
    assert status["mayChangeWriteAuthority"] is False
    assert status["maySetClaimStatus"] is False


def test_shadow_observation_has_no_authority_and_no_raw_request():
    value = build_shadow_observation(
        run_id="r", task_id="t", session_id="s", request="secret user request",
        selected_mode="CHECK", target_kind="url",
        intent_route={"intent": "CHECK", "specialty": "RESPONSIVE", "writeRequested": False, "readOnlyRequired": True},
        control_intent={"action": "CHECK", "profile": "standard", "protectedScope": ["auth"]},
        fixed_result={"status": "PASS", "taskResult": {"status": "PASS"}},
    )
    raw = json.dumps(value, ensure_ascii=False)
    assert "secret user request" not in raw
    assert value["authoritative"] is False
    assert value["invariants"]["mayAuthorizeWrite"] is False
    assert value["invariants"]["maySetClaimStatus"] is False
    assert value["adaptiveObservation"]["mayInfluenceCurrentRun"] is False
    assert value["hostBoundary"]["realCodexHostEnforcement"] == "NOT_MEASURED"


def test_real_experience_run_emits_shadow_artifact_without_changing_result(tmp_path: Path, monkeypatch):
    from web_ui_quality.experience_fix import run_experience_fix

    monkeypatch.setattr("web_ui_quality.experience_fix.run_smart_acceptance", _fake_acceptance)
    artifacts = tmp_path / "artifacts"
    result = run_experience_fix(
        "https://example.test/", artifacts, request="只检查响应式，不要改代码",
        mode="CHECK", task_id="shadow-task", session_id="shadow-session",
    )
    assert result["status"] == "PASS"
    assert "experimentalShadow" not in result
    run_dir = next(artifacts.glob("wuq-*"))
    observations = sorted((run_dir / "experimental" / "phase1-shadow").glob("*-observation.json"))
    assert len(observations) == 1
    shadow = json.loads(observations[0].read_text(encoding="utf-8"))
    assert shadow["mode"] == "SHADOW_ONLY"
    assert shadow["taskBinding"]["taskId"] == "shadow-task"
    assert shadow["fixedWorkflowObservation"]["status"] == "PASS"
    assert shadow["invariants"]["fixedWorkflowAuthoritative"] is True
    assert shadow["invariants"]["mayChangeTaskResult"] is False
    adaptive = shadow["adaptiveControlPlane"]
    assert adaptive["mode"] == "SHADOW_ONLY"
    assert adaptive["observedTaskState"] == "PARTIAL"
    assert adaptive["taskFingerprint"]["fingerprintDigest"]
    assert adaptive["taskGraph"]["nodes"][0]["taskId"] == "shadow-task"
    assert adaptive["supervisor"]["authoritative"] is False
    assert adaptive["authority"]["writeAuthority"] is False
    assert adaptive["authority"]["claimAuthority"] is False
    assert "只检查响应式" not in json.dumps(adaptive, ensure_ascii=False)


def test_shadow_failure_isolated_from_fixed_workflow(tmp_path: Path, monkeypatch):
    from web_ui_quality.experience_fix import run_experience_fix

    monkeypatch.setattr("web_ui_quality.experience_fix.run_smart_acceptance", _fake_acceptance)
    def broken_shadow(**kwargs):
        raise RuntimeError("shadow-only failure")
    monkeypatch.setattr("web_ui_quality.experience_fix.build_shadow_observation", broken_shadow)
    artifacts = tmp_path / "artifacts"
    result = run_experience_fix(
        "https://example.test/", artifacts, request="检查页面",
        mode="CHECK", task_id="shadow-fail-task", session_id="shadow-fail-session",
    )
    assert result["status"] == "PASS"
    run_dir = next(artifacts.glob("wuq-*"))
    shadow_dir = run_dir / "experimental" / "phase1-shadow"
    assert not shadow_dir.exists() or not list(shadow_dir.glob("*-observation.json"))
    errors = sorted(shadow_dir.glob("*-error.json"))
    assert len(errors) == 1
    error = json.loads(errors[0].read_text(encoding="utf-8"))
    assert error["status"] == "SHADOW_OBSERVER_ERROR"
    assert error["authoritative"] is False
    assert "shadow-only failure" not in json.dumps(error, ensure_ascii=False)
    assert "example.test" not in json.dumps(error, ensure_ascii=False)


def test_experience_fix_is_a_real_shadow_caller():
    source = (Path(__file__).resolve().parents[1] / "runtime/python/web_ui_quality/experience_fix.py").read_text(encoding="utf-8")
    assert "from .phase1_shadow import build_shadow_observation" in source
    assert "_emit_phase1_shadow_artifact(" in source
