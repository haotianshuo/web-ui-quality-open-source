"""External qualification collection pack for the feature-frozen 4.1 release line.

Offline packaging only. It never grants authority, verifies host attestation, or
activates adaptive behavior. Export is allowlist-based and pseudonymizes task
bindings using a caller-supplied HMAC key that is never written to the pack.
"""
from __future__ import annotations

import hashlib
import hmac
from typing import Any, Iterable, Mapping

from .contracts import digest_json
from .release_info import KERNEL_BASE_VERSION, PACKAGE_VERSION

COLLECTION_VERSION = "4.1-external-qualification-collection-v1"
REDACTION_POLICY_VERSION = "qualification-export-allowlist-v1"


def _token(key: bytes, namespace: str, value: str) -> str:
    if not key:
        raise ValueError("pseudonymization key must not be empty")
    return hmac.new(key, f"WUQ-COLLECT-v1\0{namespace}\0{value}".encode("utf-8"), hashlib.sha256).hexdigest()


def pseudonymize_binding(binding: Mapping[str, Any], key: bytes) -> dict[str, str]:
    out = {}
    for name in ("runId", "taskId", "sessionId"):
        value = str(binding.get(name) or "")
        if not value:
            raise ValueError(f"task binding missing {name}")
        out[name] = f"p_{_token(key, name, value)}"
    return out


def sanitize_shadow_observation(observation: Mapping[str, Any], key: bytes) -> dict[str, Any]:
    binding = observation.get("taskBinding")
    if not isinstance(binding, Mapping):
        raise ValueError("shadow observation missing taskBinding")
    observed_input = observation.get("observedInput") if isinstance(observation.get("observedInput"), Mapping) else {}
    fixed = observation.get("fixedWorkflowObservation") if isinstance(observation.get("fixedWorkflowObservation"), Mapping) else {}
    signal_obs = observation.get("capabilitySignalObservation") if isinstance(observation.get("capabilitySignalObservation"), Mapping) else {}
    safe_signals=[]
    for group in ("mechanicalSignals", "derivedDeterministicSignals"):
        rows = signal_obs.get(group)
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            safe_signals.append({
                "code": str(row.get("code") or "UNKNOWN"),
                "kind": str(row.get("kind") or "UNKNOWN"),
                "polarity": str(row.get("polarity") or "NEUTRAL"),
                "capabilityEligible": bool(row.get("capabilityEligible")),
                "value": row.get("value") if isinstance(row.get("value"), (bool, int, float, type(None))) else str(row.get("value") or "")[:64],
            })
    route = observed_input.get("intentRoute") if isinstance(observed_input.get("intentRoute"), Mapping) else {}
    control = observed_input.get("controlIntent") if isinstance(observed_input.get("controlIntent"), Mapping) else {}
    request_digest = str(observation.get("requestDigest") or "")
    value: dict[str, Any] = {
        "schemaVersion": "1",
        "collectionVersion": COLLECTION_VERSION,
        "packageVersion": PACKAGE_VERSION,
        "kernelBaseVersion": KERNEL_BASE_VERSION,
        "taskBinding": pseudonymize_binding(binding, key),
        "requestToken": f"r_{_token(key, 'requestDigest', request_digest)}" if request_digest else None,
        "observedInput": {
            "selectedMode": observed_input.get("selectedMode"),
            "targetKind": observed_input.get("targetKind"),
            "intentRoute": {
                "intent": route.get("intent"), "specialty": route.get("specialty"),
                "writeRequested": route.get("writeRequested"), "readOnlyRequired": route.get("readOnlyRequired"),
            },
            "controlIntent": {
                "action": control.get("action"), "profile": control.get("profile"),
                "protectedScopeCount": control.get("protectedScopeCount"),
            },
        },
        "fixedWorkflowObservation": {
            "status": fixed.get("status"), "taskResultStatus": fixed.get("taskResultStatus"),
            "writeAuthority": fixed.get("writeAuthority"),
        },
        "signals": sorted(safe_signals, key=lambda r: (r["code"], r["kind"])),
        "sourceObservationDigest": str(observation.get("observationDigest") or digest_json(observation)),
        "pseudonymization": "HMAC-SHA256-CALLER-KEY",
        "redactionPolicyVersion": REDACTION_POLICY_VERSION,
        "authorityEffect": "NONE",
        "adaptiveEffect": "NONE",
        "claimBoundary": "Exported collection rows are privacy-reduced research artifacts only; they cannot grant authority, verify host provenance, or activate adaptive behavior.",
    }
    value["exportRecordDigest"] = digest_json(value)
    return value


def build_host_attestation_request(export_record: Mapping[str, Any], *, host_id: str, host_version: str, created_at: str) -> dict[str, Any]:
    value: dict[str, Any] = {
        "schemaVersion": "1", "collectionVersion": COLLECTION_VERSION,
        "packageVersion": PACKAGE_VERSION, "kernelBaseVersion": KERNEL_BASE_VERSION,
        "taskBinding": dict(export_record["taskBinding"]),
        "exportRecordDigest": str(export_record.get("exportRecordDigest") or ""),
        "hostId": host_id, "hostVersion": host_version,
        "verificationStatus": "REQUESTED_NOT_VERIFIED", "integrityMechanism": "HOST_PROVIDER_REQUIRED",
        "attestationEvidenceDigest": None, "verifierId": None, "integrityTag": None,
        "createdAt": created_at, "authorityEffect": "NONE", "adaptiveEffect": "NONE",
        "claimBoundary": "This request is not host attestation. Only an external HostGovernanceProvider can return verifiable provenance; WUQ collection tooling does not self-upgrade it to HOST_ATTESTED.",
    }
    value["attestationRequestDigest"] = digest_json(value)
    return value


def build_label_request(export_record: Mapping[str, Any], *, requested_source: str, split: str, created_at: str) -> dict[str, Any]:
    source = requested_source.upper()
    if source not in {"EXTERNAL_ORACLE", "HOST_ACCEPTANCE", "HUMAN_BLIND_REVIEW"}:
        raise ValueError("label request source must be independent confirmatory source")
    split = split.upper()
    if split not in {"DEVELOPMENT", "HOLDOUT", "EXTERNAL"}:
        raise ValueError("unknown split")
    value: dict[str, Any] = {
        "schemaVersion": "1", "collectionVersion": COLLECTION_VERSION,
        "packageVersion": PACKAGE_VERSION, "kernelBaseVersion": KERNEL_BASE_VERSION,
        "taskBinding": dict(export_record["taskBinding"]),
        "exportRecordDigest": str(export_record.get("exportRecordDigest") or ""),
        "requestedLabelSource": source, "split": split,
        "outcome": None, "independence": "UNASSESSED", "evaluatorPseudonym": None,
        "evidenceDigest": None, "blindingStatus": "REQUESTED", "createdAt": created_at,
        "authorityEffect": "NONE", "adaptiveEffect": "NONE",
        "claimBoundary": "This is an annotation request, not a label. Filled labels remain research evidence and never alter the original Fixed Workflow result.",
    }
    value["labelRequestDigest"] = digest_json(value)
    return value


def build_collection_manifest(records: Iterable[Mapping[str, Any]], *, created_at: str) -> dict[str, Any]:
    rows=list(records)
    digests=[str(r.get("exportRecordDigest") or "") for r in rows]
    if len(digests) != len(set(digests)):
        raise ValueError("duplicate export record digest")
    value: dict[str, Any] = {
        "schemaVersion": "1", "collectionVersion": COLLECTION_VERSION,
        "packageVersion": PACKAGE_VERSION, "kernelBaseVersion": KERNEL_BASE_VERSION,
        "recordCount": len(rows), "exportRecordDigests": sorted(digests),
        "pseudonymization": "HMAC-SHA256-CALLER-KEY", "keyIncludedInPack": False,
        "redactionPolicyVersion": REDACTION_POLICY_VERSION,
        "hostAttestationStatus": "REQUESTS_ONLY_NOT_VERIFIED",
        "labelStatus": "REQUESTS_ONLY_NOT_LABELS",
        "realWorldPredictiveValidity": "NOT_MEASURED",
        "adaptiveGuidance": "NOT_ACTIVE", "realCodexHostEnforcement": "NOT_MEASURED",
        "createdAt": created_at, "authorityEffect": "NONE", "adaptiveEffect": "NONE",
        "claimBoundary": "Collection completeness does not imply host attestation, label independence, predictive validity, or permission to activate adaptive guidance.",
    }
    value["collectionDigest"] = digest_json(value)
    return value

__all__ = ["COLLECTION_VERSION", "REDACTION_POLICY_VERSION", "pseudonymize_binding", "sanitize_shadow_observation", "build_host_attestation_request", "build_label_request", "build_collection_manifest"]
