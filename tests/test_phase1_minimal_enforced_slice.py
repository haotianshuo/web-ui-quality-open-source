from __future__ import annotations

import ast
import hashlib
import hmac
import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from web_ui_quality.contracts import ContractViolation, digest_json, hash_file
from web_ui_quality.phase1_authority import verify_authorization_ticket
from web_ui_quality.phase1_boundaries import authorize_read_path, authorize_write_target
from web_ui_quality.phase1_capabilities import assess_required_channels, resolve_mvhc, verify_capability_snapshot
from web_ui_quality.phase1_claims import evaluate_claim
from web_ui_quality.phase1_deadlock import DeadlockState, observe_round, resource_stop
from web_ui_quality.phase1_evidence import bind_host_observation, model_inferred_evidence, stale_evidence
from web_ui_quality.phase1_host_apply import (build_target_digest, prepare_host_apply_request, verify_host_write_receipt_v2, prepare_host_apply_request_v3, verify_host_write_receipt_v3)
from web_ui_quality.phase1_shadow import adaptive_runtime_status
from web_ui_quality.phase1_task_result import aggregate_task_result
from web_ui_quality.schema_validation import validate_instance

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "runtime" / "python" / "web_ui_quality" / "schemas"
SECRET = b"phase1-test-host-secret-not-shipped"
NOW = datetime(2026, 8, 11, 5, 20, tzinfo=timezone.utc)


def _ts(delta_minutes: int = 0) -> str:
    return (NOW + timedelta(minutes=delta_minutes)).isoformat().replace("+00:00", "Z")


def _sign(digest: str) -> str:
    return "hmac:" + hmac.new(SECRET, digest.encode(), hashlib.sha256).hexdigest()


def _verify(payload, digest_key):
    tag = payload.get("integrityTag")
    return isinstance(tag, str) and hmac.compare_digest(tag, _sign(str(payload.get(digest_key))))


def _assessment(row):
    body = dict(row)
    body["assessmentDigest"] = digest_json(body)
    return body


def _common(channel_id, kind, level="ENFORCED"):
    return {
        "channelId": channel_id,
        "kind": kind,
        "capabilityLevel": level,
        "limitationCodes": [],
        "assessedAt": _ts(),
        "validUntil": _ts(60),
        "assessorId": "fixture-host",
    }


def _snapshot(*, authoritative=True, mutation_level="ENFORCED"):
    rows = []
    for channel in ("fileEditControl", "fileCreateControl", "fileDeleteControl", "fileRenameControl"):
        rows.append(_assessment({
            **_common(channel, "MUTATION", mutation_level),
            "canPrevent": mutation_level == "ENFORCED",
            "canDetect": True,
            "canAttribute": True,
            "canHashBefore": True,
            "canHashAfter": True,
            "canBindReceipt": True,
            "canBlockReplay": mutation_level == "ENFORCED",
            "atomicityLevel": "PER_FILE" if mutation_level == "ENFORCED" else "NONE",
        }))
    rows += [
        _assessment({**_common("fileReadControl", "OBSERVATION"), "canObserve": True, "canAttribute": True, "observationIntegrity": "HOST_ATTESTED", "freshnessBound": "operation", "environmentBinding": True}),
        _assessment({**_common("browserControl", "OBSERVATION"), "canObserve": True, "canAttribute": True, "observationIntegrity": "HOST_ATTESTED", "freshnessBound": "operation", "environmentBinding": True}),
        _assessment({**_common("toolEventTelemetry", "OBSERVATION"), "canObserve": True, "canAttribute": True, "observationIntegrity": "HOST_ATTESTED", "freshnessBound": "operation", "environmentBinding": False}),
        _assessment({**_common("taskIdentity", "IDENTITY"), "authoritativeSource": "host-session", "integrityLevel": "HOST_ATTESTED", "versionBinding": True, "freshnessBound": "session", "sessionBinding": True}),
        _assessment({**_common("claimResultStorage", "PERSISTENCE"), "canPersist": True, "canReadBack": True, "durabilityLevel": "HOST_DURABLE", "integrityLevel": "HOST_ATTESTED"}),
    ]
    payload = {
        "schemaVersion": "1.1",
        "snapshotId": "snap-phase1",
        "hostId": "fixture-host",
        "hostVersion": "1",
        "adapterId": "fixture-adapter",
        "adapterVersion": "1",
        "threatModelVersion": "phase1-core-v1",
        "channelAssessments": rows,
        "issuedAt": _ts(),
        "validUntil": _ts(60),
        "previousSnapshotDigest": None,
        "integrityMechanism": "HMAC_SHA256" if authoritative else "LOCAL_DIGEST_ONLY",
        "keyId": "test-key" if authoritative else None,
    }
    payload["snapshotDigest"] = digest_json(payload)
    payload["integrityTag"] = _sign(payload["snapshotDigest"]) if authoritative else "local-digest"
    return payload


def _trusted_snapshot(*, authoritative=True, mutation_level="ENFORCED"):
    payload = _snapshot(authoritative=authoritative, mutation_level=mutation_level)
    return verify_capability_snapshot(
        payload,
        verifier=(lambda p: _verify(p, "snapshotDigest")) if authoritative else None,
        now=NOW,
    )


def _mvhc():
    return {
        "schemaVersion": "1",
        "requirementSetId": "PHASE1_MVHC_V1",
        "requirements": [
            {"requirementId": "task_identity", "channelId": "taskIdentity", "minimumLevel": "DETECT_ONLY", "purpose": "IDENTITY_REQUIRED"},
            {"requirementId": "baseline_read", "channelId": "fileReadControl", "minimumLevel": "DETECT_ONLY", "purpose": "MEASUREMENT"},
            {"requirementId": "file_edit", "channelId": "fileEditControl", "minimumLevel": "DETECT_ONLY", "purpose": "MEASUREMENT"},
            {"requirementId": "file_create", "channelId": "fileCreateControl", "minimumLevel": "DETECT_ONLY", "purpose": "MEASUREMENT"},
            {"requirementId": "file_delete", "channelId": "fileDeleteControl", "minimumLevel": "DETECT_ONLY", "purpose": "MEASUREMENT"},
            {"requirementId": "file_rename", "channelId": "fileRenameControl", "minimumLevel": "DETECT_ONLY", "purpose": "MEASUREMENT"},
            {"requirementId": "tool_events", "channelId": "toolEventTelemetry", "minimumLevel": "DETECT_ONLY", "purpose": "MEASUREMENT"},
            {"requirementId": "claim_store", "channelId": "claimResultStorage", "minimumLevel": "DETECT_ONLY", "purpose": "INTEGRITY"},
        ],
    }


def _ceiling(task_id="task-1"):
    value = {
        "schemaVersion": "1",
        "ceilingId": "ceil-1",
        "taskId": task_id,
        "allowedWriteRoots": ["src/components"],
        "allowedOperations": ["EDIT"],
        "allowedIntent": ["repair_ui"],
        "forbiddenWriteRoots": ["src/auth", "src/payment"],
        "expiresAt": _ts(60),
    }
    value["ceilingDigest"] = digest_json(value)
    return value


def _read_boundary(task_id="task-1"):
    value = {
        "schemaVersion": "1",
        "boundaryId": "read-1",
        "taskId": task_id,
        "allowedRoots": ["src"],
        "deniedRoots": ["src/secrets"],
        "sensitiveRoots": [".env"],
    }
    value["boundaryDigest"] = digest_json(value)
    return value


def _ticket(*, baseline_digest, target_digest, ceiling_digest, snapshot_digest):
    value = {
        "schemaVersion": "2",
        "ticketId": "ticket-1",
        "issuer": "fixture-host",
        "authoritySource": "HOST_AUTHORITY",
        "taskId": "task-1",
        "baselineDigest": baseline_digest,
        "targetDigest": target_digest,
        "changeSetDigest": None,
        "writeDelegatedCeilingDigest": ceiling_digest,
        "capabilitySnapshotDigest": snapshot_digest,
        "nonce": "0123456789abcdef",
        "issuedAt": _ts(-1),
        "expiresAt": _ts(30),
        "singleUse": True,
        "concurrencySemantics": "SINGLE_WRITER_SERIALIZED",
        "integrityMechanism": "HMAC_SHA256",
        "keyId": "test-key",
    }
    value["ticketDigest"] = digest_json(value)
    value["integrityTag"] = _sign(value["ticketDigest"])
    return value


def _receipt(*, ticket_digest, path, before_hash, after_hash):
    value = {
        "schemaVersion": "2",
        "receiptId": "receipt-1",
        "taskId": "task-1",
        "authorizationTicketDigest": ticket_digest,
        "changeSetDigest": None,
        "actualOperation": "EDIT",
        "applyResult": "APPLIED",
        "hostActor": "fixture-host",
        "observedAt": _ts(1),
        "concurrencySemantics": "SINGLE_WRITER_SERIALIZED",
        "entries": [{
            "entryId": "entry-1",
            "canonicalPath": path,
            "actualOperation": "EDIT",
            "entryResult": "APPLIED",
            "actualBeforeHash": before_hash,
            "actualAfterHash": after_hash,
            "reasonCode": None,
        }],
        "integrityMechanism": "HMAC_SHA256",
        "keyId": "test-key",
    }
    value["receiptDigest"] = digest_json(value)
    value["integrityTag"] = _sign(value["receiptDigest"])
    return value


def _receipt_v3(request, *, path, before_hash, after_hash, **overrides):
    host = request.to_host_payload()
    value = {
        "schemaVersion": "3",
        "receiptProtocolVersion": host["receiptProtocolVersion"],
        "receiptId": "receipt-v3-1",
        "pluginVersion": host["pluginVersion"],
        "kernelVersion": host["kernelVersion"],
        "packageTreeDigest": host["packageTreeDigest"],
        "activationId": host["activationId"],
        "runId": host["runId"],
        "sessionId": host["sessionId"],
        "taskId": host["taskId"],
        "nonce": host["nonce"],
        "issuedAt": _ts(1),
        "expiresAt": _ts(20),
        "freshnessEpoch": host["freshnessEpoch"],
        "baselineDigest": host["baselineDigest"],
        "targetDigest": host["targetDigest"],
        "changeSetDigest": host["changeSetDigest"],
        "verificationPolicyDigest": host["verificationPolicyDigest"],
        "hostIdentity": host["expectedHostIdentity"],
        "attestationIdentity": host["expectedAttestationIdentity"],
        "authorizationTicketDigest": host["ticketDigest"],
        "actualOperation": "EDIT",
        "applyResult": "APPLIED",
        "entries": [{
            "entryId": "entry-v3-1", "canonicalPath": path, "actualOperation": "EDIT", "entryResult": "APPLIED",
            "actualBeforeHash": before_hash, "actualAfterHash": after_hash, "reasonCode": None,
        }],
        "integrityMechanism": "HMAC_SHA256", "keyId": "test-key",
    }
    value.update(overrides)
    value["receiptDigest"] = digest_json({k:v for k,v in value.items() if k not in {"receiptDigest","integrityTag"}})
    value["integrityTag"] = _sign(value["receiptDigest"])
    return value


class HostReceiptClaimState:
    def __init__(self):
        self.consumed = set()
    def consume(self, receipt_digest, nonce, claim_id):
        key = (receipt_digest, nonce)
        if key in self.consumed:
            return False
        self.consumed.add(key)
        return True


class HostTicketState:
    def __init__(self):
        self.reserved = {}
        self.consumed = set()

    def reserve(self, ticket_digest, nonce):
        if ticket_digest in self.reserved or ticket_digest in self.consumed:
            return ""
        ref = f"reservation:{nonce}"
        self.reserved[ticket_digest] = ref
        return ref

    def consume(self, ticket_digest, reservation_ref):
        if self.reserved.get(ticket_digest) != reservation_ref:
            return False
        self.reserved.pop(ticket_digest)
        self.consumed.add(ticket_digest)
        return True


def test_phase1_modules_contain_no_target_write_primitive():
    pkg = ROOT / "runtime" / "python" / "web_ui_quality"
    offenders = []
    for path in pkg.glob("phase1_*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr in {"write_text", "write_bytes", "write", "writelines", "truncate"}:
                offenders.append((path.name, node.lineno, func.attr))
            if isinstance(func, ast.Name) and func.id == "open":
                mode = ""
                if len(node.args) > 1 and isinstance(node.args[1], ast.Constant):
                    mode = str(node.args[1].value)
                if any(flag in mode for flag in "wax+"):
                    offenders.append((path.name, node.lineno, f"open:{mode}"))
    assert not offenders


def test_typed_snapshot_is_authoritative_only_with_host_attestation():
    trusted = _trusted_snapshot(authoritative=True)
    assert trusted.authoritative is True
    local = _trusted_snapshot(authoritative=False)
    assert local.authoritative is False
    result = assess_required_channels(
        [{"channelId": "fileEditControl", "minimumLevel": "ENFORCED", "purpose": "WRITE_SAFETY"}], local
    )
    assert result["disposition"] == "BLOCK"
    assert result["weakest"] == "DETECT_ONLY"


def test_mvhc_resolves_to_concrete_channels():
    result = resolve_mvhc(_mvhc(), _trusted_snapshot())
    assert result["status"] == "SATISFIED"
    assert result["trustMode"] == "ENFORCED"


def test_read_boundary_is_independent_of_write_ceiling(tmp_path):
    (tmp_path / "src" / "shared").mkdir(parents=True)
    (tmp_path / "src" / "components").mkdir(parents=True)
    (tmp_path / "src" / "shared" / "util.ts").write_text("export const x=1", encoding="utf-8")
    path = authorize_read_path(tmp_path, _read_boundary(), "src/shared/util.ts")
    assert path.name == "util.ts"
    with pytest.raises(ContractViolation) as caught:
        authorize_write_target(tmp_path, _ceiling(), relative_path="src/shared/util.ts", operation="EDIT", intent="repair_ui", now=NOW)
    assert caught.value.code == "WRITE_OUTSIDE_DELEGATED_CEILING"


def test_secret_read_is_denied(tmp_path):
    (tmp_path / "src" / "secrets").mkdir(parents=True)
    (tmp_path / "src" / "secrets" / "key.txt").write_text("secret", encoding="utf-8")
    with pytest.raises(ContractViolation) as caught:
        authorize_read_path(tmp_path, _read_boundary(), "src/secrets/key.txt")
    assert caught.value.code == "READ_DENIED"


def test_forged_ticket_is_rejected():
    baseline = "a" * 64
    target = "b" * 64
    snap = _trusted_snapshot()
    ticket = _ticket(baseline_digest=baseline, target_digest=target, ceiling_digest="c" * 64, snapshot_digest=snap.snapshot_digest)
    ticket["targetDigest"] = "9" * 64
    with pytest.raises(ContractViolation) as caught:
        verify_authorization_ticket(
            ticket, verifier=lambda p: _verify(p, "ticketDigest"), task_id="task-1", baseline_digest=baseline,
            target_digest=target, write_ceiling_digest="c" * 64, capability_snapshot_digest=snap.snapshot_digest, now=NOW,
        )
    assert caught.value.code == "AUTHORIZATION_TICKET_TAMPERED"


def test_end_to_end_host_apply_receipt_claim_and_task_result(tmp_path):
    target = tmp_path / "src" / "components" / "Button.tsx"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"export const Button=()=>null\n")
    before = hash_file(target)
    intended = b"export const Button=()=> <button>Save</button>\n"
    after = hashlib.sha256(intended).hexdigest()
    baseline_digest = digest_json({"src/components/Button.tsx": before})
    entries = [{"canonicalPath": "src/components/Button.tsx", "operation": "EDIT", "expectedBeforeHash": before, "intendedAfterHash": after}]
    target_digest = build_target_digest(entries)
    ceiling = _ceiling(); snap = _trusted_snapshot()
    ticket = _ticket(baseline_digest=baseline_digest, target_digest=target_digest, ceiling_digest=ceiling["ceilingDigest"], snapshot_digest=snap.snapshot_digest)
    host_state = HostTicketState()
    policy_digest = digest_json({"policy":"phase1-v3-test"}); package_tree = "a"*64
    request = prepare_host_apply_request_v3(
        tmp_path, task_id="task-1", run_id="run-1", session_id="session-1", activation_id="activation-1",
        package_tree_digest=package_tree, baseline_digest=baseline_digest, entries=entries, change_set_digest=target_digest,
        verification_policy_digest=policy_digest, expected_host_identity="fixture-host", expected_attestation_identity="test-key", freshness_epoch=7,
        intent="repair_ui", write_ceiling=ceiling, capability_snapshot=snap, ticket_payload=ticket,
        ticket_verifier=lambda p:_verify(p,"ticketDigest"), reserve_ticket=host_state.reserve, now=NOW,
    )
    target.write_bytes(intended)
    receipt_payload = _receipt_v3(request, path="src/components/Button.tsx", before_hash=before, after_hash=after)
    receipt = verify_host_write_receipt_v3(
        tmp_path, receipt_payload, apply_request=request, receipt_verifier=lambda p:_verify(p,"receiptDigest"), consume_ticket=host_state.consume, now=NOW+timedelta(minutes=2),
    )
    env = "e"*64
    observation = bind_host_observation(
        evidence_id="ev-1", task_id="task-1", subtype="FILE_STATE", source_ref="host:file-state",
        observation_payload={"path":"src/components/Button.tsx","sha256":after}, baseline_digest=baseline_digest,
        environment_fingerprint=env, verifier=lambda e:e["sourceRef"]=="host:file-state", observed_at=_ts(2),
    )
    claim_contract={"claimId":"claim-1","taskId":"task-1","claimRole":"REQUIRED","statement":"Button file matches the approved repair state","verificationContractId":"vc-1","baselineId":"baseline-1","environmentFingerprint":env,"requiredEvidenceTypes":["FILE_STATE"],"requiredChannels":[{"channelId":"fileEditControl","minimumLevel":"ENFORCED","purpose":"WRITE_SAFETY"}]}
    claim_state=HostReceiptClaimState()
    claim=evaluate_claim(
        claim_contract, capability_snapshot=snap, evidence=[observation], predicates=[True], receipts=[receipt], requires_write_receipt=True,
        baseline_digest=baseline_digest, evaluated_at=_ts(3), run_id="run-1", session_id="session-1", activation_id="activation-1",
        target_digest=target_digest, change_set_digest=target_digest, package_tree_digest=package_tree, verification_policy_digest=policy_digest,
        minimum_receipt_epoch=7, consume_receipt=claim_state.consume,
    )
    assert claim["status"] == "VERIFIED"
    task=aggregate_task_result(task_id="task-1",task_contract_digest="f"*64,required_claim_ids=["claim-1"],optional_claim_ids=[],claims=[claim],capability_snapshot_digest=snap.snapshot_digest,environment_fingerprint=env)
    assert task["status"]=="VERIFIED" and task["terminationReason"]=="NONE"
    validate_instance(task,json.loads((SCHEMA_DIR/"task-result-v2.1.schema.json").read_text()),base_dir=SCHEMA_DIR)
    validate_instance(claim,json.loads((SCHEMA_DIR/"claim-v2.schema.json").read_text()),base_dir=SCHEMA_DIR)


def test_ticket_replay_is_blocked_at_host_reservation(tmp_path):
    target = tmp_path / "src" / "components" / "A.tsx"
    target.parent.mkdir(parents=True)
    target.write_text("a", encoding="utf-8")
    before = hash_file(target); after = hashlib.sha256(b"b").hexdigest()
    entries = [{"canonicalPath": "src/components/A.tsx", "operation": "EDIT", "expectedBeforeHash": before, "intendedAfterHash": after}]
    baseline = digest_json({"A": before}); ceiling = _ceiling(); snap = _trusted_snapshot(); td = build_target_digest(entries)
    ticket = _ticket(baseline_digest=baseline, target_digest=td, ceiling_digest=ceiling["ceilingDigest"], snapshot_digest=snap.snapshot_digest)
    state = HostTicketState()
    prepare_host_apply_request(tmp_path, task_id="task-1", baseline_digest=baseline, entries=entries, intent="repair_ui", write_ceiling=ceiling,
                               capability_snapshot=snap, ticket_payload=ticket, ticket_verifier=lambda p:_verify(p,"ticketDigest"), reserve_ticket=state.reserve, now=NOW)
    with pytest.raises(ContractViolation) as caught:
        prepare_host_apply_request(tmp_path, task_id="task-1", baseline_digest=baseline, entries=entries, intent="repair_ui", write_ceiling=ceiling,
                                   capability_snapshot=snap, ticket_payload=ticket, ticket_verifier=lambda p:_verify(p,"ticketDigest"), reserve_ticket=state.reserve, now=NOW)
    assert caught.value.code == "HOST_TICKET_RESERVATION_FAILED"


def test_detect_only_host_cannot_prepare_enforced_write(tmp_path):
    target = tmp_path / "src" / "components" / "A.tsx"; target.parent.mkdir(parents=True); target.write_text("a")
    before=hash_file(target); after=hashlib.sha256(b"b").hexdigest(); entries=[{"canonicalPath":"src/components/A.tsx","operation":"EDIT","expectedBeforeHash":before,"intendedAfterHash":after}]
    baseline=digest_json({"A":before}); ceiling=_ceiling(); snap=_trusted_snapshot(authoritative=True, mutation_level="DETECT_ONLY"); td=build_target_digest(entries)
    ticket=_ticket(baseline_digest=baseline,target_digest=td,ceiling_digest=ceiling["ceilingDigest"],snapshot_digest=snap.snapshot_digest)
    with pytest.raises(ContractViolation) as caught:
        prepare_host_apply_request(tmp_path,task_id="task-1",baseline_digest=baseline,entries=entries,intent="repair_ui",write_ceiling=ceiling,
                                   capability_snapshot=snap,ticket_payload=ticket,ticket_verifier=lambda p:_verify(p,"ticketDigest"),reserve_ticket=HostTicketState().reserve,now=NOW)
    assert caught.value.code == "HOST_WRITE_CHANNEL_NOT_ENFORCED"


def test_model_inferred_evidence_cannot_verify_claim():
    snap = _trusted_snapshot()
    ev = model_inferred_evidence(evidence_id="m1", task_id="task-1", source_ref="model", payload={"guess":True}, baseline_digest="b"*64, environment_fingerprint="e"*64)
    contract={"claimId":"c","taskId":"task-1","claimRole":"REQUIRED","statement":"x","verificationContractId":"v","baselineId":"base","environmentFingerprint":"e"*64,
              "requiredEvidenceTypes":["BROWSER"],"requiredChannels":[{"channelId":"browserControl","minimumLevel":"DETECT_ONLY","purpose":"MEASUREMENT"}]}
    claim=evaluate_claim(contract,capability_snapshot=snap,evidence=[ev],predicates=[True],baseline_digest="b"*64,evaluated_at=_ts())
    assert claim["status"] == "NOT_MEASURED"


def test_stale_evidence_invalidates_claim():
    snap=_trusted_snapshot(); env="e"*64; baseline="b"*64
    obs=bind_host_observation(evidence_id="e1",task_id="task-1",subtype="BROWSER",source_ref="host:browser",observation_payload={"ok":True},baseline_digest=baseline,environment_fingerprint=env,verifier=lambda e:True,observed_at=_ts())
    stale=stale_evidence(obs,reason="AUTHORIZED_WRITE_CHANGED_DEPENDENCY")
    contract={"claimId":"c","taskId":"task-1","claimRole":"REQUIRED","statement":"x","verificationContractId":"v","baselineId":"base","environmentFingerprint":env,
              "requiredEvidenceTypes":["BROWSER"],"requiredChannels":[{"channelId":"browserControl","minimumLevel":"DETECT_ONLY","purpose":"MEASUREMENT"}]}
    claim=evaluate_claim(contract,capability_snapshot=snap,evidence=[stale],predicates=[True],baseline_digest=baseline,evaluated_at=_ts())
    assert claim["status"] == "INVALIDATED"


def test_failed_predicate_is_not_verified():
    snap=_trusted_snapshot(); env="e"*64; baseline="b"*64
    obs=bind_host_observation(evidence_id="e1",task_id="task-1",subtype="BROWSER",source_ref="host:browser",observation_payload={"ok":False},baseline_digest=baseline,environment_fingerprint=env,verifier=lambda e:True,observed_at=_ts())
    contract={"claimId":"c","taskId":"task-1","claimRole":"REQUIRED","statement":"x","verificationContractId":"v","baselineId":"base","environmentFingerprint":env,
              "requiredEvidenceTypes":["BROWSER"],"requiredChannels":[{"channelId":"browserControl","minimumLevel":"DETECT_ONLY","purpose":"MEASUREMENT"}]}
    claim=evaluate_claim(contract,capability_snapshot=snap,evidence=[obs],predicates=[False],baseline_digest=baseline,evaluated_at=_ts())
    assert claim["status"] == "NOT_VERIFIED"


def test_deadlock_uses_obligation_reduction_not_activity_count():
    state=DeadlockState()
    state=observe_round(state,obligations_before=frozenset({"O1","O2"}),obligations_after=frozenset({"O1","O2"}),max_no_progress_rounds=2)
    assert not state.deadlock_detected
    state=observe_round(state,obligations_before=frozenset({"O1","O2"}),obligations_after=frozenset({"O1","O2"}),max_no_progress_rounds=2)
    assert state.deadlock_detected


def test_obligation_reduction_resets_no_progress():
    state=DeadlockState(no_progress_rounds=1)
    state=observe_round(state,obligations_before=frozenset({"O1","O2"}),obligations_after=frozenset({"O1"}),max_no_progress_rounds=2)
    assert state.no_progress_rounds == 0 and not state.deadlock_detected


def test_resource_exhaustion_is_separate_from_deadlock():
    reason, disposition=resource_stop(accepted_progress=True,hard_token_limit_reached=True,telemetry_authoritative=True)
    assert (reason,disposition)==("TOKEN_LIMIT_REACHED","MORE_RESOURCE_REQUIRED")
    reason, disposition=resource_stop(accepted_progress=True,hard_token_limit_reached=True,telemetry_authoritative=False)
    assert (reason,disposition)==("NONE","UNKNOWN")


def test_shadow_mode_cannot_change_authority_or_guidance():
    status=adaptive_runtime_status()
    assert status["mode"]=="SHADOW_ONLY"
    assert status["mayChangeWriteAuthority"] is False
    assert status["mayChangeGuidance"] is False


def test_empty_required_claims_fail_instead_of_vacuous_verified():
    result=aggregate_task_result(task_id="t",task_contract_digest="a"*64,required_claim_ids=[],optional_claim_ids=[],claims=[],capability_snapshot_digest="b"*64,environment_fingerprint="c"*64)
    assert result["status"]=="FAILED"
    assert result["terminationReason"]=="INVALID_TASK_CONTRACT"


def test_task_status_and_termination_reason_are_separate():
    result=aggregate_task_result(task_id="t",task_contract_digest="a"*64,required_claim_ids=["c"],optional_claim_ids=[],claims=[{"claimId":"c","taskId":"t","status":"NOT_MEASURED","claimDigest":"d"*64}],capability_snapshot_digest="b"*64,environment_fingerprint="c"*64,termination_reason="TIMEOUT")
    assert result["status"]=="BLOCKED"
    assert result["terminationReason"]=="TIMEOUT"

def test_invalid_empty_task_contract_is_serializable_as_failed():
    result=aggregate_task_result(task_id="t",task_contract_digest="a"*64,required_claim_ids=[],optional_claim_ids=[],claims=[],capability_snapshot_digest="b"*64,environment_fingerprint="c"*64)
    schema=json.loads((SCHEMA_DIR/"task-result-v2.1.schema.json").read_text())
    validate_instance(result,schema,base_dir=SCHEMA_DIR)
    forged={**result,"status":"VERIFIED","terminationReason":"NONE"}
    with pytest.raises(Exception):
        validate_instance(forged,schema,base_dir=SCHEMA_DIR)


def test_known_channel_cannot_claim_wrong_capability_kind():
    payload=_snapshot()
    row=next(x for x in payload["channelAssessments"] if x["channelId"]=="fileEditControl")
    row["kind"]="IDENTITY"
    row["assessmentDigest"]=digest_json({k:v for k,v in row.items() if k!="assessmentDigest"})
    payload["snapshotDigest"]=digest_json({k:v for k,v in payload.items() if k not in {"snapshotDigest","integrityTag"}})
    payload["integrityTag"]=_sign(payload["snapshotDigest"])
    with pytest.raises(ContractViolation) as caught:
        verify_capability_snapshot(payload,verifier=lambda p:_verify(p,"snapshotDigest"),now=NOW)
    assert caught.value.code in {"HOST_CAPABILITY_SCHEMA_INVALID","CAPABILITY_KIND_MISMATCH"}


def test_expired_channel_assessment_rejects_snapshot():
    payload=_snapshot()
    row=payload["channelAssessments"][0]
    row["validUntil"]=_ts(-2)
    row["assessmentDigest"]=digest_json({k:v for k,v in row.items() if k!="assessmentDigest"})
    payload["snapshotDigest"]=digest_json({k:v for k,v in payload.items() if k not in {"snapshotDigest","integrityTag"}})
    payload["integrityTag"]=_sign(payload["snapshotDigest"])
    with pytest.raises(ContractViolation) as caught:
        verify_capability_snapshot(payload,verifier=lambda p:_verify(p,"snapshotDigest"),now=NOW)
    assert caught.value.code=="HOST_CAPABILITY_CHANNEL_EXPIRED"


def test_forged_receipt_is_rejected_after_host_write(tmp_path):
    target=tmp_path/"src"/"components"/"A.tsx"; target.parent.mkdir(parents=True); target.write_text("a")
    before=hash_file(target); intended="b"; after=hashlib.sha256(intended.encode()).hexdigest(); baseline=digest_json({"A":before})
    entries=[{"canonicalPath":"src/components/A.tsx","operation":"EDIT","expectedBeforeHash":before,"intendedAfterHash":after}]
    ceiling=_ceiling(); snap=_trusted_snapshot(); ticket=_ticket(baseline_digest=baseline,target_digest=build_target_digest(entries),ceiling_digest=ceiling["ceilingDigest"],snapshot_digest=snap.snapshot_digest); state=HostTicketState()
    req=prepare_host_apply_request(tmp_path,task_id="task-1",baseline_digest=baseline,entries=entries,intent="repair_ui",write_ceiling=ceiling,capability_snapshot=snap,ticket_payload=ticket,ticket_verifier=lambda p:_verify(p,"ticketDigest"),reserve_ticket=state.reserve,now=NOW)
    target.write_text(intended)
    receipt=_receipt(ticket_digest=ticket["ticketDigest"],path="src/components/A.tsx",before_hash=before,after_hash=after)
    receipt["entries"][0]["actualAfterHash"]="9"*64
    with pytest.raises(ContractViolation) as caught:
        verify_host_write_receipt_v2(tmp_path,receipt,apply_request=req,receipt_verifier=lambda p:_verify(p,"receiptDigest"),consume_ticket=state.consume)
    assert caught.value.code in {"HOST_WRITE_RECEIPT_V2_TAMPERED","HOST_WRITE_RECEIPT_V2_ATTESTATION_INVALID"}


def test_required_write_receipt_missing_blocks_verified_claim():
    snap=_trusted_snapshot(); env="e"*64; baseline="b"*64
    obs=bind_host_observation(evidence_id="e1",task_id="task-1",subtype="FILE_STATE",source_ref="host:file",observation_payload={"ok":True},baseline_digest=baseline,environment_fingerprint=env,verifier=lambda e:True,observed_at=_ts())
    contract={"claimId":"c","taskId":"task-1","claimRole":"REQUIRED","statement":"x","verificationContractId":"v","baselineId":"base","environmentFingerprint":env,"requiredEvidenceTypes":["FILE_STATE"],"requiredChannels":[{"channelId":"fileEditControl","minimumLevel":"ENFORCED","purpose":"WRITE_SAFETY"}]}
    claim=evaluate_claim(contract,capability_snapshot=snap,evidence=[obs],predicates=[True],requires_write_receipt=True,baseline_digest=baseline,evaluated_at=_ts())
    assert claim["status"]=="BLOCKED"
    assert "HOST_WRITE_RECEIPT_REQUIRED" in claim["reasonCodes"]


def test_missing_measurement_channel_yields_not_measured_not_failed():
    snap=_trusted_snapshot()
    contract={"claimId":"c","taskId":"task-1","claimRole":"REQUIRED","statement":"x","verificationContractId":"v","baselineId":"base","environmentFingerprint":"e"*64,"requiredEvidenceTypes":["NETWORK"],"requiredChannels":[{"channelId":"networkReadControl","minimumLevel":"DETECT_ONLY","purpose":"MEASUREMENT"}]}
    claim=evaluate_claim(contract,capability_snapshot=snap,evidence=[],predicates=None,baseline_digest="b"*64,evaluated_at=_ts())
    assert claim["status"]=="NOT_MEASURED"
    assert "MEASUREMENT_CAPABILITY_INSUFFICIENT" in claim["reasonCodes"]


def test_phase1_rejects_create_operation_even_if_schema_allows_future_operation(tmp_path):
    target=tmp_path/"src"/"components"; target.mkdir(parents=True)
    before="0"*64; after="1"*64; entries=[{"canonicalPath":"src/components/New.tsx","operation":"CREATE","expectedBeforeHash":before,"intendedAfterHash":after}]
    ceiling=_ceiling(); ceiling["allowedOperations"]=["CREATE"]; ceiling["ceilingDigest"]=digest_json({k:v for k,v in ceiling.items() if k!="ceilingDigest"})
    snap=_trusted_snapshot(); baseline="b"*64; td=build_target_digest(entries); ticket=_ticket(baseline_digest=baseline,target_digest=td,ceiling_digest=ceiling["ceilingDigest"],snapshot_digest=snap.snapshot_digest)
    with pytest.raises(ContractViolation) as caught:
        prepare_host_apply_request(tmp_path,task_id="task-1",baseline_digest=baseline,entries=entries,intent="repair_ui",write_ceiling=ceiling,capability_snapshot=snap,ticket_payload=ticket,ticket_verifier=lambda p:_verify(p,"ticketDigest"),reserve_ticket=HostTicketState().reserve,now=NOW)
    assert caught.value.code=="PHASE1_OPERATION_NOT_SUPPORTED"


def test_read_symlink_alias_into_sensitive_root_is_denied(tmp_path):
    safe = tmp_path / "src" / "safe"
    secrets = tmp_path / "src" / "secrets"
    safe.mkdir(parents=True)
    secrets.mkdir(parents=True)
    (secrets / "token.txt").write_text("SECRET", encoding="utf-8")
    try:
        (safe / "alias").symlink_to(secrets, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is unavailable on this host")
    with pytest.raises(ContractViolation) as caught:
        authorize_read_path(tmp_path, _read_boundary(), "src/safe/alias/token.txt")
    assert caught.value.code == "READ_RESOLVED_TARGET_DENIED"


def test_write_symlink_alias_into_forbidden_root_is_denied(tmp_path):
    components = tmp_path / "src" / "components"
    auth = tmp_path / "src" / "auth"
    components.mkdir(parents=True)
    auth.mkdir(parents=True)
    (auth / "token.ts").write_text("secret", encoding="utf-8")
    try:
        (components / "alias").symlink_to(auth, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is unavailable on this host")
    with pytest.raises(ContractViolation) as caught:
        authorize_write_target(
            tmp_path, _ceiling(), relative_path="src/components/alias/token.ts",
            operation="EDIT", intent="repair_ui", now=NOW,
        )
    assert caught.value.code == "WRITE_ALIAS_NOT_ALLOWED"


@pytest.mark.skipif(os.name != "nt", reason="native Windows junction/reparse qualification")
def test_native_windows_junction_alias_into_forbidden_root_is_denied(tmp_path):
    components = tmp_path / "src" / "components"
    auth = tmp_path / "src" / "auth"
    components.mkdir(parents=True)
    auth.mkdir(parents=True)
    (auth / "token.ts").write_text("secret", encoding="utf-8")
    alias = components / "junction-alias"
    # Do not use cmd.exe /S here. /S changes quote processing around the /C
    # command string and has produced invalid-path failures before mklink ran.
    # Run mklink from the link parent with relative names so the qualification
    # is independent of quoting the temporary absolute path (which may contain
    # spaces or non-ASCII characters on a real Windows workstation).
    created = subprocess.run(
        "cmd.exe /d /c mklink /J junction-alias ..\\auth",
        cwd=components,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    assert created.returncode == 0, created.stderr or created.stdout
    if hasattr(os.path, "isjunction"):
        assert os.path.isjunction(alias)
    with pytest.raises(ContractViolation) as caught:
        authorize_write_target(
            tmp_path,
            _ceiling(),
            relative_path="src/components/junction-alias/token.ts",
            operation="EDIT",
            intent="repair_ui",
            now=NOW,
        )
    assert caught.value.code == "WRITE_ALIAS_NOT_ALLOWED"


def test_windows_junction_fixture_does_not_use_cmd_s_quote_rewrite():
    source = Path(__file__).read_text(encoding="utf-8")
    junction_block = source[source.index("def test_native_windows_junction_alias_into_forbidden_root_is_denied"):source.index("def test_write_hardlink_alias_is_conservatively_denied")]
    assert '"/s"' not in junction_block.casefold()
    assert "cwd=components" in junction_block
    assert "mklink /J junction-alias ..\\\\auth" in junction_block


def test_write_hardlink_alias_is_conservatively_denied(tmp_path):
    components = tmp_path / "src" / "components"
    components.mkdir(parents=True)
    first = components / "A.tsx"
    second = components / "B.tsx"
    first.write_text("a", encoding="utf-8")
    try:
        second.hardlink_to(first)
    except (OSError, NotImplementedError):
        pytest.skip("hardlink creation is unavailable on this host")
    with pytest.raises(ContractViolation) as caught:
        authorize_write_target(
            tmp_path, _ceiling(), relative_path="src/components/A.tsx",
            operation="EDIT", intent="repair_ui", now=NOW,
        )
    assert caught.value.code == "WRITE_HARDLINK_NOT_ALLOWED"


def test_task_result_not_verified_precedes_partial():
    claims = [
        {"claimId":"a","taskId":"task-1","status":"VERIFIED","claimDigest":"a"*64},
        {"claimId":"b","taskId":"task-1","status":"NOT_VERIFIED","claimDigest":"b"*64},
    ]
    result = aggregate_task_result(
        task_id="task-1", task_contract_digest="f"*64,
        required_claim_ids=["a","b"], optional_claim_ids=[], claims=claims,
        capability_snapshot_digest="c"*64, environment_fingerprint="e"*64,
    )
    assert result["status"] == "NOT_VERIFIED"
    assert result["terminationReason"] == "NONE"


def test_task_result_invalidated_precedes_partial():
    claims = [
        {"claimId":"a","taskId":"task-1","status":"VERIFIED","claimDigest":"a"*64},
        {"claimId":"b","taskId":"task-1","status":"INVALIDATED","claimDigest":"b"*64},
    ]
    result = aggregate_task_result(
        task_id="task-1", task_contract_digest="f"*64,
        required_claim_ids=["a","b"], optional_claim_ids=[], claims=claims,
        capability_snapshot_digest="c"*64, environment_fingerprint="e"*64,
    )
    assert result["status"] == "BLOCKED"
    assert result["terminationReason"] == "REQUIRED_CLAIM_INVALIDATED"


def test_mutation_epoch_invalidates_old_observation():
    snap = _trusted_snapshot(); env = "e"*64; baseline = "b"*64
    obs = bind_host_observation(
        evidence_id="epoch-old", task_id="task-1", subtype="BROWSER", source_ref="host:browser",
        observation_payload={"ok":True}, baseline_digest=baseline, environment_fingerprint=env,
        verifier=lambda e: True, state_epoch=12, observed_at="2000-01-01T00:00:00Z",
    )
    contract={"claimId":"c","taskId":"task-1","claimRole":"REQUIRED","statement":"x","verificationContractId":"v","baselineId":"base","environmentFingerprint":env,
              "requiredEvidenceTypes":["BROWSER"],"requiredChannels":[{"channelId":"browserControl","minimumLevel":"DETECT_ONLY","purpose":"MEASUREMENT"}]}
    claim=evaluate_claim(contract,capability_snapshot=snap,evidence=[obs],predicates=[True],baseline_digest=baseline,evaluated_at=_ts(),minimum_state_epoch=13)
    assert claim["status"] == "INVALIDATED"
    assert "EVIDENCE_STATE_EPOCH_STALE" in claim["reasonCodes"]


def test_old_wall_clock_observation_can_be_fresh_at_current_epoch():
    snap = _trusted_snapshot(); env = "e"*64; baseline = "b"*64
    obs = bind_host_observation(
        evidence_id="epoch-current", task_id="task-1", subtype="BROWSER", source_ref="host:browser",
        observation_payload={"ok":True}, baseline_digest=baseline, environment_fingerprint=env,
        verifier=lambda e: True, state_epoch=13, observed_at="2000-01-01T00:00:00Z",
    )
    contract={"claimId":"c","taskId":"task-1","claimRole":"REQUIRED","statement":"x","verificationContractId":"v","baselineId":"base","environmentFingerprint":env,
              "requiredEvidenceTypes":["BROWSER"],"requiredChannels":[{"channelId":"browserControl","minimumLevel":"DETECT_ONLY","purpose":"MEASUREMENT"}]}
    claim=evaluate_claim(contract,capability_snapshot=snap,evidence=[obs],predicates=[True],baseline_digest=baseline,evaluated_at=_ts(),minimum_state_epoch=13)
    assert claim["status"] == "VERIFIED"


def test_phase1_read_boundary_schema_rejects_unimplemented_budget_fields():
    boundary = _read_boundary()
    boundary.pop("boundaryDigest")
    boundary["maxReadBytes"] = 1
    boundary["boundaryDigest"] = digest_json(boundary)
    with pytest.raises(ContractViolation) as caught:
        authorize_read_path(Path.cwd(), boundary, "README.md")
    assert caught.value.code == "READ_BOUNDARY_SCHEMA_INVALID"


def test_receipt_rejects_alias_introduced_after_authorization(tmp_path):
    target = tmp_path / "src" / "components" / "A.tsx"
    forbidden = tmp_path / "src" / "auth" / "A.tsx"
    target.parent.mkdir(parents=True)
    forbidden.parent.mkdir(parents=True)
    target.write_text("a", encoding="utf-8")
    intended = "b"
    before = hash_file(target)
    after = hashlib.sha256(intended.encode()).hexdigest()
    entries = [{"canonicalPath":"src/components/A.tsx","operation":"EDIT","expectedBeforeHash":before,"intendedAfterHash":after}]
    baseline = digest_json({"A":before}); ceiling = _ceiling(); snap = _trusted_snapshot(); td = build_target_digest(entries)
    ticket = _ticket(baseline_digest=baseline,target_digest=td,ceiling_digest=ceiling["ceilingDigest"],snapshot_digest=snap.snapshot_digest)
    state = HostTicketState()
    request = prepare_host_apply_request(
        tmp_path,task_id="task-1",baseline_digest=baseline,entries=entries,intent="repair_ui",
        write_ceiling=ceiling,capability_snapshot=snap,ticket_payload=ticket,
        ticket_verifier=lambda p:_verify(p,"ticketDigest"),reserve_ticket=state.reserve,now=NOW,
    )
    forbidden.write_text(intended, encoding="utf-8")
    target.unlink()
    try:
        target.symlink_to(forbidden)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is unavailable on this host")
    receipt_payload = _receipt(ticket_digest=ticket["ticketDigest"],path="src/components/A.tsx",before_hash=before,after_hash=after)
    with pytest.raises(ContractViolation) as caught:
        verify_host_write_receipt_v2(
            tmp_path,receipt_payload,apply_request=request,
            receipt_verifier=lambda p:_verify(p,"receiptDigest"),consume_ticket=state.consume,
        )
    assert caught.value.code == "HOST_WRITE_RECEIPT_V2_PATH_ALIAS_OR_ESCAPE"


def _make_v3_claim_fixture(tmp_path):
    target=tmp_path/"src"/"components"/"Secure.tsx"; target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes(b"before\n")
    before=hash_file(target); after_bytes=b"after\n"; after=hashlib.sha256(after_bytes).hexdigest()
    baseline=digest_json({"src/components/Secure.tsx":before})
    entries=[{"canonicalPath":"src/components/Secure.tsx","operation":"EDIT","expectedBeforeHash":before,"intendedAfterHash":after}]
    target_digest=build_target_digest(entries); ceiling=_ceiling(); snap=_trusted_snapshot()
    ticket=_ticket(baseline_digest=baseline,target_digest=target_digest,ceiling_digest=ceiling["ceilingDigest"],snapshot_digest=snap.snapshot_digest)
    ticket_state=HostTicketState(); policy=digest_json({"policy":"v3-security"}); package_tree="c"*64
    request=prepare_host_apply_request_v3(
        tmp_path,task_id="task-1",run_id="run-1",session_id="session-1",activation_id="activation-1",package_tree_digest=package_tree,
        baseline_digest=baseline,entries=entries,change_set_digest=target_digest,verification_policy_digest=policy,
        expected_host_identity="fixture-host",expected_attestation_identity="test-key",freshness_epoch=9,intent="repair_ui",write_ceiling=ceiling,
        capability_snapshot=snap,ticket_payload=ticket,ticket_verifier=lambda p:_verify(p,"ticketDigest"),reserve_ticket=ticket_state.reserve,now=NOW,
    )
    target.write_bytes(after_bytes)
    payload=_receipt_v3(request,path="src/components/Secure.tsx",before_hash=before,after_hash=after)
    receipt=verify_host_write_receipt_v3(tmp_path,payload,apply_request=request,receipt_verifier=lambda p:_verify(p,"receiptDigest"),consume_ticket=ticket_state.consume,now=NOW+timedelta(minutes=2))
    env="e"*64
    def observation(task_id="task-1",baseline_digest=baseline):
        return bind_host_observation(evidence_id=f"ev-{task_id}",task_id=task_id,subtype="FILE_STATE",source_ref="host:file-state",observation_payload={"sha256":after},baseline_digest=baseline_digest,environment_fingerprint=env,verifier=lambda e:True,observed_at=_ts(2))
    def contract(task_id="task-1",claim_id="claim-secure"):
        return {"claimId":claim_id,"taskId":task_id,"claimRole":"REQUIRED","statement":"secure write","verificationContractId":"vc-secure","baselineId":"baseline-secure","environmentFingerprint":env,"requiredEvidenceTypes":["FILE_STATE"],"requiredChannels":[{"channelId":"fileEditControl","minimumLevel":"ENFORCED","purpose":"WRITE_SAFETY"}]}
    common={"capability_snapshot":snap,"predicates":[True],"receipts":[receipt],"requires_write_receipt":True,"evaluated_at":_ts(3),"run_id":"run-1","session_id":"session-1","activation_id":"activation-1","target_digest":target_digest,"change_set_digest":target_digest,"package_tree_digest":package_tree,"verification_policy_digest":policy,"minimum_receipt_epoch":9}
    return {"target":target,"before":before,"after":after,"baseline":baseline,"target_digest":target_digest,"receipt":receipt,"snap":snap,"observation":observation,"contract":contract,"common":common}


def test_v3_receipt_from_task_a_cannot_verify_task_b(tmp_path):
    f=_make_v3_claim_fixture(tmp_path); state=HostReceiptClaimState(); kwargs=dict(f["common"]); kwargs.update(evidence=[f["observation"]("task-2")],baseline_digest=f["baseline"],consume_receipt=state.consume)
    claim=evaluate_claim(f["contract"]("task-2"),**kwargs)
    assert claim["status"]=="BLOCKED" and "HOST_WRITE_RECEIPT_TASK_MISMATCH" in claim["reasonCodes"]


def test_v3_receipt_cross_session_is_rejected(tmp_path):
    f=_make_v3_claim_fixture(tmp_path); state=HostReceiptClaimState(); kwargs=dict(f["common"]); kwargs.update(evidence=[f["observation"]()],baseline_digest=f["baseline"],session_id="session-2",consume_receipt=state.consume)
    claim=evaluate_claim(f["contract"](),**kwargs)
    assert claim["status"]=="BLOCKED" and "HOST_WRITE_RECEIPT_SESSION_MISMATCH" in claim["reasonCodes"]


def test_v3_receipt_wrong_baseline_is_rejected(tmp_path):
    f=_make_v3_claim_fixture(tmp_path); wrong="d"*64; state=HostReceiptClaimState(); kwargs=dict(f["common"]); kwargs.update(evidence=[f["observation"](baseline_digest=wrong)],baseline_digest=wrong,consume_receipt=state.consume)
    claim=evaluate_claim(f["contract"](),**kwargs)
    assert claim["status"]=="BLOCKED" and "HOST_WRITE_RECEIPT_BASELINE_MISMATCH" in claim["reasonCodes"]


def test_v3_receipt_wrong_target_is_rejected(tmp_path):
    f=_make_v3_claim_fixture(tmp_path); state=HostReceiptClaimState(); kwargs=dict(f["common"]); kwargs.update(evidence=[f["observation"]()],baseline_digest=f["baseline"],target_digest="d"*64,consume_receipt=state.consume)
    claim=evaluate_claim(f["contract"](),**kwargs)
    assert claim["status"]=="BLOCKED" and "HOST_WRITE_RECEIPT_TARGET_MISMATCH" in claim["reasonCodes"]


def test_v3_receipt_expired_at_claim_time_is_rejected(tmp_path):
    f=_make_v3_claim_fixture(tmp_path); state=HostReceiptClaimState(); kwargs=dict(f["common"]); kwargs.update(evidence=[f["observation"]()],baseline_digest=f["baseline"],evaluated_at=_ts(25),consume_receipt=state.consume)
    claim=evaluate_claim(f["contract"](),**kwargs)
    assert claim["status"]=="BLOCKED" and "HOST_WRITE_RECEIPT_EXPIRED" in claim["reasonCodes"]


def test_v3_receipt_replay_is_rejected(tmp_path):
    f=_make_v3_claim_fixture(tmp_path); state=HostReceiptClaimState(); kwargs=dict(f["common"]); kwargs.update(evidence=[f["observation"]()],baseline_digest=f["baseline"],consume_receipt=state.consume)
    first=evaluate_claim(f["contract"](),**kwargs); second=evaluate_claim(f["contract"](),**kwargs)
    assert first["status"]=="VERIFIED"
    assert second["status"]=="BLOCKED" and "HOST_WRITE_RECEIPT_REPLAYED" in second["reasonCodes"]


def test_v3_receipt_post_receipt_drift_is_rejected(tmp_path):
    f=_make_v3_claim_fixture(tmp_path); f["target"].write_bytes(b"tampered-after-receipt\n")
    state=HostReceiptClaimState(); kwargs=dict(f["common"]); kwargs.update(evidence=[f["observation"]()],baseline_digest=f["baseline"],consume_receipt=state.consume)
    claim=evaluate_claim(f["contract"](),**kwargs)
    assert claim["status"]=="BLOCKED" and "HOST_WRITE_RECEIPT_POST_APPLY_DRIFT" in claim["reasonCodes"]


def test_v2_receipt_is_history_only_for_420_verified_claim(tmp_path):
    target=tmp_path/"src"/"components"/"Legacy.tsx"; target.parent.mkdir(parents=True); target.write_bytes(b"a")
    before=hash_file(target); after_bytes=b"b"; after=hashlib.sha256(after_bytes).hexdigest(); baseline=digest_json({"legacy":before})
    entries=[{"canonicalPath":"src/components/Legacy.tsx","operation":"EDIT","expectedBeforeHash":before,"intendedAfterHash":after}]
    ceiling=_ceiling(); snap=_trusted_snapshot(); td=build_target_digest(entries); ticket=_ticket(baseline_digest=baseline,target_digest=td,ceiling_digest=ceiling["ceilingDigest"],snapshot_digest=snap.snapshot_digest); state=HostTicketState()
    req=prepare_host_apply_request(tmp_path,task_id="task-1",baseline_digest=baseline,entries=entries,intent="repair_ui",write_ceiling=ceiling,capability_snapshot=snap,ticket_payload=ticket,ticket_verifier=lambda p:_verify(p,"ticketDigest"),reserve_ticket=state.reserve,now=NOW)
    target.write_bytes(after_bytes); rp=_receipt(ticket_digest=ticket["ticketDigest"],path="src/components/Legacy.tsx",before_hash=before,after_hash=after)
    legacy=verify_host_write_receipt_v2(tmp_path,rp,apply_request=req,receipt_verifier=lambda p:_verify(p,"receiptDigest"),consume_ticket=state.consume)
    env="e"*64; obs=bind_host_observation(evidence_id="legacy-ev",task_id="task-1",subtype="FILE_STATE",source_ref="host:file",observation_payload={"sha256":after},baseline_digest=baseline,environment_fingerprint=env,verifier=lambda e:True,observed_at=_ts(2))
    contract={"claimId":"legacy-claim","taskId":"task-1","claimRole":"REQUIRED","statement":"legacy","verificationContractId":"vc","baselineId":"b","environmentFingerprint":env,"requiredEvidenceTypes":["FILE_STATE"],"requiredChannels":[{"channelId":"fileEditControl","minimumLevel":"ENFORCED","purpose":"WRITE_SAFETY"}]}
    claim=evaluate_claim(contract,capability_snapshot=snap,evidence=[obs],predicates=[True],receipts=[legacy],requires_write_receipt=True,baseline_digest=baseline,evaluated_at=_ts(3))
    assert claim["status"]=="BLOCKED" and "LEGACY_RECEIPT_NOT_SUFFICIENT_FOR_VERIFIED" in claim["reasonCodes"]
