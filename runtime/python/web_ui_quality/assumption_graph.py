"""Assumption invalidation graph separating observations from interpretations."""
from __future__ import annotations

from collections import deque
from typing import Any, Iterable, Mapping
import uuid

from .contracts import ContractViolation, digest_json
from .governance_artifacts import now_iso, read_json, write_json_atomic

_ARTIFACT = "governance/assumption-invalidation.json"
_RAW_TYPES = {"RAW_EVIDENCE", "SCREENSHOT", "DOM_OBSERVATION", "ACCESSIBILITY_MEASUREMENT", "COMPUTED_STYLE", "RUNTIME_ERROR", "HTTP_EVIDENCE", "OBSERVATION"}
_POLICIES = {"INVALIDATE", "REVALIDATE", "RETAIN"}


def _empty(run_id: str | None = None) -> dict[str, Any]:
    body = {"schemaVersion": "1", "runId": run_id, "assumptions": [], "artifacts": [], "invalidationLedger": [], "updatedAt": now_iso()}
    return {**body, "graphDigest": digest_json(body)}


def _load(run_dir, *, create: bool = False, run_id: str | None = None) -> dict[str, Any]:
    try:
        value = read_json(run_dir, _ARTIFACT, code="ASSUMPTION_GRAPH_MISSING")
    except ContractViolation:
        if not create:
            raise
        value = _empty(run_id)
        write_json_atomic(run_dir, _ARTIFACT, value, replace=False)
        return value
    body = {k: v for k, v in value.items() if k != "graphDigest"}
    if value.get("graphDigest") != digest_json(body):
        raise ContractViolation("ASSUMPTION_GRAPH_TAMPERED", ["$.graphDigest: mismatch"])
    return value


def _save(run_dir, value: Mapping[str, Any]) -> dict[str, Any]:
    body = {k: v for k, v in dict(value).items() if k != "graphDigest"}
    body["updatedAt"] = now_iso()
    sealed = {**body, "graphDigest": digest_json(body)}
    write_json_atomic(run_dir, _ARTIFACT, sealed)
    return sealed


def add_assumption(run_dir, *, key: str, value: Any, source: str, confidence: float = 1.0, assumption_id: str | None = None, run_id: str | None = None) -> dict[str, Any]:
    graph = _load(run_dir, create=True, run_id=run_id)
    active_same = [a for a in graph["assumptions"] if a.get("key") == key and not a.get("supersededBy")]
    if active_same:
        raise ContractViolation("ASSUMPTION_SILENT_OVERWRITE_FORBIDDEN", [f"$.key: active assumption {key!r} already exists; supersede it explicitly"])
    aid = assumption_id or f"asm-{uuid.uuid4().hex[:12]}"
    if any(a.get("id") == aid for a in graph["assumptions"]):
        raise ContractViolation("ASSUMPTION_ID_EXISTS", [f"$.id: {aid}"])
    item = {"id": aid, "key": key, "value": value, "source": source, "confidence": float(confidence), "createdAt": now_iso(), "supersedes": None, "supersededBy": None}
    graph["assumptions"].append(item)
    _save(run_dir, graph)
    return item


def register_dependent_artifact(run_dir, *, artifact_id: str, artifact_type: str, assumption_ids: Iterable[str] = (), depends_on: Iterable[str] = (), invalidation_policy: str = "INVALIDATE") -> dict[str, Any]:
    graph = _load(run_dir, create=True)
    if invalidation_policy not in _POLICIES:
        raise ContractViolation("INVALIDATION_POLICY_INVALID", [f"$: {invalidation_policy}"])
    if any(a.get("artifactId") == artifact_id for a in graph["artifacts"]):
        raise ContractViolation("DEPENDENT_ARTIFACT_EXISTS", [f"$: {artifact_id}"])
    known_assumptions = {a["id"] for a in graph["assumptions"]}
    unknown = set(assumption_ids) - known_assumptions
    if unknown:
        raise ContractViolation("ASSUMPTION_REFERENCE_INVALID", [f"$: unknown assumptions {sorted(unknown)}"])
    item = {
        "artifactId": artifact_id, "artifactType": artifact_type,
        "assumptionIds": list(assumption_ids), "dependsOn": list(depends_on),
        "invalidationPolicy": invalidation_policy, "status": "VALID", "createdAt": now_iso(),
    }
    graph["artifacts"].append(item)
    _save(run_dir, graph)
    return item


def _affected(graph: Mapping[str, Any], assumption_id: str) -> list[str]:
    artifacts = {a["artifactId"]: a for a in graph.get("artifacts", [])}
    queue = deque(aid for aid, a in artifacts.items() if assumption_id in (a.get("assumptionIds") or []))
    seen: set[str] = set()
    while queue:
        current = queue.popleft()
        if current in seen:
            continue
        seen.add(current)
        for aid, artifact in artifacts.items():
            if current in (artifact.get("dependsOn") or []):
                queue.append(aid)
    return sorted(seen)


def supersede_assumption(run_dir, *, assumption_id: str, new_value: Any, source: str, confidence: float = 1.0) -> dict[str, Any]:
    graph = _load(run_dir)
    index = next((i for i, a in enumerate(graph["assumptions"]) if a.get("id") == assumption_id), None)
    if index is None:
        raise ContractViolation("ASSUMPTION_NOT_FOUND", [f"$: {assumption_id}"])
    old = graph["assumptions"][index]
    if old.get("supersededBy"):
        raise ContractViolation("ASSUMPTION_ALREADY_SUPERSEDED", [f"$: {assumption_id}"])
    new_id = f"asm-{uuid.uuid4().hex[:12]}"
    replacement = {"id": new_id, "key": old["key"], "value": new_value, "source": source, "confidence": float(confidence), "createdAt": now_iso(), "supersedes": assumption_id, "supersededBy": None}
    graph["assumptions"][index] = {**old, "supersededBy": new_id}
    graph["assumptions"].append(replacement)
    affected_ids = _affected(graph, assumption_id)
    invalidated, retained, revalidate = [], [], []
    for artifact in graph["artifacts"]:
        if artifact["artifactId"] not in affected_ids:
            continue
        raw = artifact.get("artifactType") in _RAW_TYPES
        policy = "RETAIN" if raw else artifact.get("invalidationPolicy", "INVALIDATE")
        if policy == "RETAIN":
            artifact["status"] = "VALID"
            retained.append(artifact["artifactId"])
        elif policy == "REVALIDATE":
            artifact["status"] = "REQUIRES_REVALIDATION"
            revalidate.append(artifact["artifactId"])
        else:
            artifact["status"] = "INVALIDATED"
            invalidated.append(artifact["artifactId"])
    result = {
        "event": "ASSUMPTION_SUPERSEDED", "at": now_iso(), "oldAssumptionId": assumption_id,
        "newAssumptionId": new_id, "key": old["key"], "oldValue": old.get("value"), "newValue": new_value,
        "invalidated": sorted(invalidated), "retained": sorted(retained), "requiresRevalidation": sorted(revalidate),
        "reason": "dependent interpretations/decisions cannot survive a changed premise; raw observations are retained",
    }
    graph["invalidationLedger"].append(result)
    _save(run_dir, graph)
    return result


def load_assumption_graph(run_dir) -> dict[str, Any]:
    return _load(run_dir)
