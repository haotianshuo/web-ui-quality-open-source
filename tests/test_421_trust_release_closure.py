from __future__ import annotations

import copy
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from web_ui_quality.contracts import ContractViolation, digest_json, hash_file
from web_ui_quality.experience_fix import run_experience_fix
from web_ui_quality.outcome_verification import combine_repair_verification
from web_ui_quality.release_info import PACKAGE_VERSION, KERNEL_VERSION


def _fake_acceptance(*args, **kwargs):
    output = Path(kwargs["output_dir"])
    after = output.name == "after"
    report = {
        "status": "PASS" if after else "FAIL",
        "pageHealth": {"pageStatus": "PASS" if after else "TASK_FAILED"},
        "journey": {
            "journeyId": "primary", "status": "PASS" if after else "FAIL",
            "journey": [{"action": "open", "target": "/"}],
            "runs": [{"status": "PASS" if after else "FAIL"}],
        },
        "findings": [], "topFindings": [],
        "deliveryConclusion": "after improved" if after else "before failed",
        "open": "index.html",
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "smart-acceptance-report.json").write_text(json.dumps(report), encoding="utf-8")
    return report


def _receipt(binding, *, key: bytes):
    now = datetime.now(timezone.utc)
    entries = [
        {
            "entryId": f"entry-{idx}",
            "canonicalPath": row["canonicalPath"],
            "actualOperation": row["operation"],
            "entryResult": "APPLIED",
            "actualBeforeHash": row["expectedBeforeHash"],
            "actualAfterHash": row["intendedAfterHash"],
            "reasonCode": None,
        }
        for idx, row in enumerate(binding["entries"], start=1)
    ]
    value = {
        "schemaVersion": "3", "receiptProtocolVersion": "3.0", "receiptId": "receipt-mainline-v3",
        "pluginVersion": PACKAGE_VERSION, "kernelVersion": KERNEL_VERSION,
        "packageTreeDigest": binding["packageTreeDigest"], "activationId": binding["activationId"],
        "runId": binding["runId"], "sessionId": binding["sessionId"], "taskId": binding["taskId"],
        "nonce": binding["nonce"], "issuedAt": now.isoformat(), "expiresAt": (now + timedelta(minutes=10)).isoformat(),
        "freshnessEpoch": binding["freshnessEpoch"], "baselineDigest": binding["baselineDigest"],
        "targetDigest": binding["targetDigest"], "changeSetDigest": binding["changeSetDigest"],
        "verificationPolicyDigest": binding["verificationPolicyDigest"], "hostIdentity": binding["hostIdentity"],
        "attestationIdentity": binding["attestationIdentity"], "authorizationTicketDigest": binding["authorizationTicketDigest"],
        "actualOperation": "EDIT", "applyResult": "APPLIED", "entries": entries,
        "integrityMechanism": "HMAC_SHA256", "keyId": binding["attestationIdentity"],
    }
    value["receiptDigest"] = digest_json(value)
    value["integrityTag"] = "hmac:" + hmac.new(key, value["receiptDigest"].encode(), hashlib.sha256).hexdigest()
    return value


def _resign_receipt(value, *, key: bytes):
    updated = copy.deepcopy(value)
    updated.pop("integrityTag", None)
    updated.pop("receiptDigest", None)
    updated["receiptDigest"] = digest_json(updated)
    updated["integrityTag"] = "hmac:" + hmac.new(key, updated["receiptDigest"].encode(), hashlib.sha256).hexdigest()
    return updated


def _prepare_public_v3(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("web_ui_quality.experience_fix.run_smart_acceptance", _fake_acceptance)
    project = tmp_path / "project"; project.mkdir()
    source = project / "index.tsx"; source.write_text("export const App=()=> <main>before</main>\n", encoding="utf-8")
    artifacts = tmp_path / "artifacts"
    first = run_experience_fix(
        project, artifacts, request="修复移动端按钮布局", mode="FIX_AND_VERIFY",
        task_id="task-mainline", session_id="session-mainline", url="http://example.test/", files=["index.tsx"],
    )
    run_dir = artifacts / first["runId"]
    before_hash = hash_file(source)
    after_bytes = b"export const App=()=> <main>after</main>\n"
    after_hash = hashlib.sha256(after_bytes).hexdigest()
    candidate = {
        "runId": first["runId"], "taskId": "task-mainline", "sessionId": "session-mainline",
        "hostIdentity": "fixture-host", "attestationIdentity": "fixture-key",
        "entries": [{"canonicalPath": "index.tsx", "operation": "EDIT", "expectedBeforeHash": before_hash, "intendedAfterHash": after_hash}],
    }
    prepared = run_experience_fix(
        project, artifacts, request="修复移动端按钮布局", mode="FIX_AND_VERIFY",
        task_id="task-mainline", session_id="session-mainline", url="http://example.test/", files=["index.tsx"],
        existing_run=run_dir, host_patch_candidate=candidate,
    )
    source.write_bytes(after_bytes)
    key = b"fixture-host-secret-outside-project"
    return project, artifacts, run_dir, prepared["hostApplyBindingV3"], _receipt(prepared["hostApplyBindingV3"], key=key), key


def test_public_repair_mainline_can_verify_only_with_v3(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("web_ui_quality.experience_fix.run_smart_acceptance", _fake_acceptance)
    project = tmp_path / "project"; project.mkdir()
    source = project / "index.tsx"; source.write_text("export const App=()=> <main>before</main>\n", encoding="utf-8")
    artifacts = tmp_path / "artifacts"

    first = run_experience_fix(
        project, artifacts, request="修复移动端按钮布局", mode="FIX_AND_VERIFY",
        task_id="task-mainline", session_id="session-mainline", url="http://example.test/", files=["index.tsx"],
    )
    run_dir = artifacts / first["runId"]
    before_hash = hash_file(source)
    after_bytes = b"export const App=()=> <main>after</main>\n"
    after_hash = hashlib.sha256(after_bytes).hexdigest()
    candidate = {
        "runId": first["runId"], "taskId": "task-mainline", "sessionId": "session-mainline",
        "hostIdentity": "fixture-host", "attestationIdentity": "fixture-key",
        "entries": [{"canonicalPath": "index.tsx", "operation": "EDIT", "expectedBeforeHash": before_hash, "intendedAfterHash": after_hash}],
    }
    prepared = run_experience_fix(
        project, artifacts, request="修复移动端按钮布局", mode="FIX_AND_VERIFY",
        task_id="task-mainline", session_id="session-mainline", url="http://example.test/", files=["index.tsx"],
        existing_run=run_dir, host_patch_candidate=candidate,
    )
    binding = prepared["hostApplyBindingV3"]
    assert binding and binding["writeAuthorized"] is False
    assert (run_dir / "report" / "host-apply-binding-v3.json").is_file()

    source.write_bytes(after_bytes)
    key = b"fixture-host-secret-outside-project"
    receipt = _receipt(binding, key=key)
    final = run_experience_fix(
        project, artifacts, request="修复移动端按钮布局", mode="FIX_AND_VERIFY",
        task_id="task-mainline", session_id="session-mainline", url="http://example.test/", files=["index.tsx"],
        existing_run=run_dir, after_url="http://example.test/", host_write_receipt=receipt, host_receipt_hmac_key=key,
    )
    assert final["hostWriteProtocol"] == "V3"
    assert final["repairVerification"]["dimensions"]["hostWrite"] == "VERIFIED_V3"
    assert final["status"] == "VERIFIED"
    assert final["taskResult"]["outcome"] == "VERIFIED"
    assert final["evidenceGraph"]["requiredMissing"] == []
    assert final["evidenceGraph"]["status"] == "COMPLETE_VERIFIED_CHAIN"
    assert final["userOutcome"]["result"] == "已完成并验证"
    assert final["executionState"]["stage"] == "REPORT"
    assert [row["to"] for row in final["executionState"]["history"]] == ["PREFLIGHT", "PLAN", "HOST_APPLY", "VERIFY", "REPORT"]


def test_legacy_receipt_is_never_enough_for_verified():
    result = combine_repair_verification(
        browser_outcome_status="IMPROVEMENT_CLAIM_ALLOWED", project_tool_status="NOT_APPLICABLE",
        patch_quality_status="PASS", project_drift_status="PASS", change_budget_status="PASS",
        host_write_status="LEGACY_HISTORY_ONLY",
    )
    assert result["status"] == "NOT_VERIFIED"
    assert "LEGACY_RECEIPT_NOT_SUFFICIENT_FOR_VERIFIED" in result["blockers"]


@pytest.mark.parametrize(
    ("case", "expected_code"),
    [
        ("expired", "HOST_WRITE_RECEIPT_V3_EXPIRED"),
        ("nonce", "HOST_WRITE_RECEIPT_V3_BINDING_MISMATCH"),
        ("host", "HOST_WRITE_RECEIPT_V3_BINDING_MISMATCH"),
        ("files", "HOST_WRITE_RECEIPT_V3_BINDING_MISMATCH"),
        ("hash", "HOST_WRITE_RECEIPT_V3_BINDING_MISMATCH"),
        ("hmac", "HOST_WRITE_RECEIPT_V3_ATTESTATION_INVALID"),
    ],
)
def test_public_v3_negative_binding_cases_block_verified(monkeypatch, tmp_path: Path, case: str, expected_code: str):
    project, artifacts, run_dir, binding, receipt, key = _prepare_public_v3(monkeypatch, tmp_path)
    broken = copy.deepcopy(receipt)
    if case == "expired":
        old = datetime.now(timezone.utc) - timedelta(minutes=30)
        broken["issuedAt"] = old.isoformat()
        broken["expiresAt"] = (old + timedelta(minutes=5)).isoformat()
        broken = _resign_receipt(broken, key=key)
    elif case == "nonce":
        broken["nonce"] = "abcdef0123456789"
        broken = _resign_receipt(broken, key=key)
    elif case == "host":
        broken["hostIdentity"] = "wrong-host"
        broken = _resign_receipt(broken, key=key)
    elif case == "files":
        broken["entries"][0]["canonicalPath"] = "other.tsx"
        broken = _resign_receipt(broken, key=key)
    elif case == "hash":
        broken["entries"][0]["actualAfterHash"] = "0" * 64
        broken = _resign_receipt(broken, key=key)
    elif case == "hmac":
        broken["integrityTag"] = "hmac:" + "0" * 64

    with pytest.raises(ContractViolation) as caught:
        run_experience_fix(
            project, artifacts, request="修复移动端按钮布局", mode="FIX_AND_VERIFY",
            task_id="task-mainline", session_id="session-mainline", url="http://example.test/", files=["index.tsx"],
            existing_run=run_dir, after_url="http://example.test/", host_write_receipt=broken, host_receipt_hmac_key=key,
        )
    assert caught.value.code == expected_code
