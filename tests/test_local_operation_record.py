from __future__ import annotations

import json
from pathlib import Path

import pytest

from web_ui_quality.contracts import ContractViolation, digest_json
from web_ui_quality.experience_fix import _project_fingerprint, run_experience_fix
from web_ui_quality.local_operation_record import (
    check_local_operation_prewrite,
    observe_local_operation,
    record_related_run,
)
from web_ui_quality.phase1_host_apply import verify_persisted_host_write_receipt_v3


def _fake_acceptance(*args, **kwargs):
    output = Path(kwargs["output_dir"])
    is_after = output.name == "after"
    report = {
        "status": "PASS" if is_after else "FAIL",
        "pageHealth": {"pageStatus": "PASS" if is_after else "TASK_FAILED"},
        "journey": {
            "journeyId": "primary",
            "status": "PASS" if is_after else "FAIL",
            "journey": [{"action": "open", "target": "/"}],
            "runs": [{"status": "PASS" if is_after else "FAIL"}],
        },
        "findings": [],
        "topFindings": [],
        "deliveryConclusion": "after observed" if is_after else "before observed",
        "open": "index.html",
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "smart-acceptance-report.json").write_text(json.dumps(report), encoding="utf-8")
    return report


def _prepare_local_run(tmp_path: Path, monkeypatch, *, files=("ui.css",)):
    monkeypatch.setattr("web_ui_quality.experience_fix.run_smart_acceptance", _fake_acceptance)
    project = tmp_path / "project"
    project.mkdir(parents=True)
    (project / "ui.css").write_text(".month-card { display: flex; }\n", encoding="utf-8")
    (project / "other.css").write_text(".nav { color: navy; }\n", encoding="utf-8")
    artifacts = project / ".wuq" / "runs"
    url = "http://example.test/closing.html"
    prepared = run_experience_fix(
        project, artifacts,
        request="修复窄屏月份卡片布局并复验",
        mode="FIX_AND_VERIFY",
        task_id="local-task",
        session_id="local-session",
        url=url,
        files=list(files),
        local_operation=True,
    )
    return project, artifacts, url, prepared, artifacts / prepared["runId"]


def _prewrite(project: Path, run_dir: Path):
    return check_local_operation_prewrite(
        run_dir, project, task_id="local-task", session_id="local-session",
    )


def test_project_fingerprint_ignores_root_run_evidence_but_tracks_project_files(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    css = project / "ui.css"
    config = project / "package.json"
    css.write_text(".month-card { display: flex; }\n", encoding="utf-8")
    config.write_text('{"name":"sample","version":"1"}\n', encoding="utf-8")
    runtime_report = project / ".wuq" / "runs" / "run-1" / "report.json"
    runtime_report.parent.mkdir(parents=True)
    runtime_report.write_text('{"status":"before"}\n', encoding="utf-8")

    baseline = _project_fingerprint(project)
    runtime_report.write_text('{"status":"after","screenshots":3}\n', encoding="utf-8")
    assert _project_fingerprint(project) == baseline

    css.write_text(".month-card { display: grid; }\n", encoding="utf-8")
    assert _project_fingerprint(project) != baseline
    css.write_text(".month-card { display: flex; }\n", encoding="utf-8")
    assert _project_fingerprint(project) == baseline

    config.write_text('{"name":"sample","version":"2"}\n', encoding="utf-8")
    assert _project_fingerprint(project) != baseline
    config.write_text('{"name":"sample","version":"1"}\n', encoding="utf-8")

    nested_runtime_named_dir = project / "src" / ".wuq" / "config.json"
    nested_runtime_named_dir.parent.mkdir(parents=True)
    nested_runtime_named_dir.write_text('{"tracked":true}\n', encoding="utf-8")
    assert _project_fingerprint(project) != baseline


def test_explicit_scope_local_edit_and_same_condition_after_remain_not_v3(tmp_path: Path, monkeypatch):
    project, artifacts, url, prepared, run_dir = _prepare_local_run(tmp_path, monkeypatch)
    assert prepared["fixPlan"]["scopeSource"] == "explicit-host-scope"
    assert [row["path"] for row in prepared["fixPlan"]["files"]] == ["ui.css"]
    assert prepared["localOperationPrep"]["approvedSourceScope"] == ["ui.css"]
    assert prepared["hostApplyBindingV3"] is None
    assert prepared["fixPlan"]["writeAuthorized"] is False

    prewrite = _prewrite(project, run_dir)
    assert prewrite["status"] == "READY_FOR_HOST_APPLY"
    (project / "ui.css").write_text(".month-card { display: grid; min-width: 0; }\n", encoding="utf-8")
    final = run_experience_fix(
        project, artifacts,
        request="修复窄屏月份卡片布局并复验",
        mode="FIX_AND_VERIFY",
        task_id="local-task",
        session_id="local-session",
        url=url,
        existing_run=run_dir,
        after_url=url,
        local_operation=True,
    )

    record = final["localOperationRecord"]
    assert record["recordType"] == "WEB_UI_QUALITY_LOCAL_OPERATION_RECORD_V1"
    assert record["recordStatus"] == "LOCAL_OBSERVATION_COMPLETE"
    assert record["approvedSourceScope"] == ["ui.css"]
    assert record["observedChangedFiles"] == ["ui.css"]
    assert record["files"][0]["beforeSha256"] != record["files"][0]["afterSha256"]
    assert ".month-card { display: flex; }" in record["files"][0]["unifiedDiff"]
    assert ".month-card { display: grid; min-width: 0; }" in record["files"][0]["unifiedDiff"]
    assert record["sameConditionAfter"]["conditionsMatch"] is True
    assert record["sameConditionAfter"]["viewports"]
    assert record["independentHostAttestation"] == "NOT_PROVIDED"
    assert final["hostWriteReceipt"] is None
    assert final["hostWriteProtocol"] == "LOCAL_OPERATION_RECORD_V1"
    assert final["repairVerification"]["status"] == "NOT_VERIFIED"
    assert "INDEPENDENT_HOST_ATTESTATION_NOT_AVAILABLE" in final["repairVerification"]["blockers"]
    assert final["taskResult"]["outcome"] == "NOT_VERIFIED"
    assert final["taskResult"]["verification"]["hostWrite"] == "LOCAL_OPERATION_RECORD_ONLY"
    schema_path = Path(__file__).resolve().parents[1] / "schemas" / "task-result.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    from web_ui_quality.schema_validation import validate_instance

    validate_instance(final["taskResult"], schema, base_dir=schema_path.parent)
    assert final["taskResult"]["localOperation"]["recordType"] == "WEB_UI_QUALITY_LOCAL_OPERATION_RECORD_V1"
    assert final["taskResult"]["localOperation"]["independentHostAttestation"] == "NOT_PROVIDED"
    assert final["evidenceGraph"]["requiredMissing"] == []
    assert final["evidenceGraph"]["status"] == "COMPLETE_PENDING_OR_NONVERIFIED_CHAIN"
    assert (run_dir / "report" / "local-operation-record.json").is_file()


def test_local_after_requires_the_explicit_prewrite_check(tmp_path: Path, monkeypatch):
    project, artifacts, url, _prepared, run_dir = _prepare_local_run(tmp_path, monkeypatch)
    (project / "ui.css").write_text(".month-card { display: grid; }\n", encoding="utf-8")
    with pytest.raises(ContractViolation) as caught:
        run_experience_fix(
            project, artifacts,
            request="修复窄屏月份卡片布局并复验",
            mode="FIX_AND_VERIFY",
            task_id="local-task",
            session_id="local-session",
            url=url,
            existing_run=run_dir,
            after_url=url,
            local_operation=True,
        )
    assert caught.value.code == "LOCAL_OPERATION_PREWRITE_CHECK_REQUIRED"


def test_prewrite_check_rejects_file_drift_before_host_edit(tmp_path: Path, monkeypatch):
    project, _artifacts, _url, _prepared, run_dir = _prepare_local_run(tmp_path, monkeypatch)
    (project / "ui.css").write_text(".month-card { display: grid; }\n", encoding="utf-8")
    with pytest.raises(ContractViolation) as caught:
        _prewrite(project, run_dir)
    assert caught.value.code == "LOCAL_OPERATION_FILE_DRIFT"


def test_after_rejects_changes_outside_the_approved_scope(tmp_path: Path, monkeypatch):
    project, _artifacts, _url, _prepared, run_dir = _prepare_local_run(tmp_path, monkeypatch)
    _prewrite(project, run_dir)
    (project / "ui.css").write_text(".month-card { display: grid; }\n", encoding="utf-8")
    (project / "other.css").write_text(".nav { color: red; }\n", encoding="utf-8")
    with pytest.raises(ContractViolation) as caught:
        observe_local_operation(run_dir, project, task_id="local-task", session_id="local-session")
    assert caught.value.code == "LOCAL_OPERATION_SCOPE_EXCEEDED"
    assert "other.css" in str(caught.value)


def test_local_prep_and_prewrite_records_cannot_be_mixed_across_runs(tmp_path: Path, monkeypatch):
    project_a, _artifacts_a, _url_a, _prepared_a, run_a = _prepare_local_run(tmp_path / "a", monkeypatch)
    _prewrite(project_a, run_a)
    project_b, _artifacts_b, _url_b, _prepared_b, run_b = _prepare_local_run(tmp_path / "b", monkeypatch)
    for name in ("local-operation-prep.json", "local-operation-prewrite-check.json"):
        source = run_a / "report" / name
        target = run_b / "report" / name
        target.write_bytes(source.read_bytes())
    with pytest.raises(ContractViolation) as caught:
        observe_local_operation(run_b, project_b, task_id="local-task", session_id="local-session")
    assert caught.value.code == "LOCAL_OPERATION_RUN_MISMATCH"


def test_local_preparation_requires_a_sealed_before(tmp_path: Path):
    from web_ui_quality.experience_run import create_experience_run
    from web_ui_quality.local_operation_record import prepare_local_operation

    project = tmp_path / "project"
    project.mkdir()
    (project / "ui.css").write_text(".month-card {}\n", encoding="utf-8")
    run = create_experience_run(
        tmp_path / "runs", task_id="t", session_id="s", mode="FIX_AND_VERIFY",
        target={"kind": "project", "route": "/closing.html"}, conditions={"route": "/closing.html"},
    )
    with pytest.raises(ContractViolation) as caught:
        prepare_local_operation(
            run["runDir"], project, task_id="t", session_id="s",
            plan={"scopeConfirmed": True, "files": [{"path": "ui.css"}]},
            receipt_binding={"sourceScope": ["ui.css"]}, scope_baseline={"files": [{"path": "ui.css"}]},
        )
    assert caught.value.code == "LOCAL_OPERATION_BEFORE_REQUIRED"


def test_local_record_is_rejected_by_the_v3_receipt_validator(tmp_path: Path):
    local_record = {
        "schemaVersion": "1",
        "recordType": "WEB_UI_QUALITY_LOCAL_OPERATION_RECORD_V1",
        "recordStatus": "LOCAL_OBSERVATION_COMPLETE",
        "independentHostAttestation": "NOT_PROVIDED",
    }
    with pytest.raises(ContractViolation) as caught:
        verify_persisted_host_write_receipt_v3(
            tmp_path, local_record, binding={}, hmac_key=b"not-a-production-key",
        )
    assert caught.value.code == "HOST_WRITE_RECEIPT_V3_SCHEMA_INVALID"


def test_public_run_cli_selects_the_exact_local_continuation(tmp_path: Path, monkeypatch, capsys):
    from web_ui_quality import __main__ as cli
    from web_ui_quality.experience_fix import _target_identity
    from web_ui_quality.experience_run import create_experience_run

    project = tmp_path / "project"
    project.mkdir()
    url = "http://example.test/closing.html"
    target, _, _ = _target_identity(project, url)
    task_id = f"cli-task-{digest_json({'target': str(project.resolve())})[:16]}"
    artifacts = project / ".wuq" / "runs"
    run = create_experience_run(
        artifacts, task_id=task_id, session_id="exact-session", mode="FIX_AND_VERIFY",
        target=target, conditions={"route": "/closing.html"},
    )
    received = {}

    def fake_run(*args, **kwargs):
        received.update(kwargs)
        return {"status": "LOCAL_OPERATION_READY_FOR_HOST_APPLY"}

    monkeypatch.setattr(cli, "run_experience_fix", fake_run)
    code = cli.main([
        "run", str(project), "continue bounded local operation",
        "--url", url, "--continue-run", run["runId"],
        "--local-operation", "--local-operation-prewrite-check", "--compact",
    ])
    capsys.readouterr()
    assert code == 0
    assert Path(received["existing_run"]) == Path(run["runDir"])
    assert received["session_id"] == "exact-session"
    assert received["local_operation"] is True
    assert received["local_operation_prewrite_check"] is True
    assert received["after_url"] is None


def test_related_run_preserves_discovery_and_rejects_wrong_target(tmp_path: Path):
    from web_ui_quality.experience_run import create_experience_run, seal_before, write_phase_file

    artifacts = tmp_path / "runs"
    conditions = {"route": "/closing.html", "viewports": [{"width": 390, "height": 844}]}
    discovery = create_experience_run(
        artifacts, task_id="t", session_id="s1", mode="FIX_AND_VERIFY",
        target={"kind": "project", "route": "/closing.html"}, conditions=conditions,
    )
    discovery_dir = Path(discovery["runDir"])
    write_phase_file(discovery_dir, "before", "report.json", "{}")
    seal_before(discovery_dir)
    repair = create_experience_run(
        artifacts, task_id="t", session_id="s2", mode="FIX_AND_VERIFY",
        target={"kind": "project", "route": "/closing.html"}, conditions=conditions,
    )
    link = record_related_run(
        repair["runDir"], discovery_dir, task_id="t", target_digest=discovery["targetDigest"],
        reason="preserve immutable discovery",
    )
    assert link["discoveryRunId"] == discovery["runId"]
    assert link["repairRunId"] == repair["runId"]
    assert (discovery_dir / "before" / ".sealed").is_file()
    wrong = create_experience_run(
        artifacts, task_id="t", session_id="s3", mode="FIX_AND_VERIFY",
        target={"kind": "project", "route": "/other.html"}, conditions={"route": "/other.html"},
    )
    with pytest.raises(ContractViolation) as caught:
        record_related_run(
            wrong["runDir"], discovery_dir, task_id="t", target_digest=wrong["targetDigest"],
            reason="wrong target must stop",
        )
    assert caught.value.code == "RELATED_RUN_MISMATCH"

def test_public_prewrite_check_ignores_its_own_wuq_run_artifacts(tmp_path: Path, monkeypatch):
    project, artifacts, url, _prepared, run_dir = _prepare_local_run(tmp_path, monkeypatch)
    continued = run_experience_fix(
        project, artifacts,
        request="修复窄屏月份卡片布局并复验",
        mode="FIX_AND_VERIFY",
        task_id="local-task",
        session_id="local-session",
        url=url,
        existing_run=run_dir,
        local_operation=True,
        local_operation_prewrite_check=True,
    )
    assert continued["status"] == "LOCAL_OPERATION_READY_FOR_HOST_APPLY"
    assert continued["localOperationPrewriteCheck"]["status"] == "READY_FOR_HOST_APPLY"
    assert continued["writeAuthorization"] is False
