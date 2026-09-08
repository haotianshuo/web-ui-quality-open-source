"""Build a compact dependency graph for repair evidence and success claims.

The graph is derived from already-trusted Runtime objects.  It does not make a
weak artifact trustworthy; it makes the dependency chain inspectable and lets
callers see exactly which evidence a final claim depends on.
"""
from __future__ import annotations

from typing import Any, Mapping
from .contracts import digest_json


def _node(node_id: str, kind: str, value: Any, *, required: bool, status: str | None = None) -> dict[str, Any]:
    present = value is not None and value != {} and value != []
    if status is None:
        status = "PRESENT" if present else "MISSING"
    digest = digest_json(value) if present else None
    return {
        "id": node_id,
        "kind": kind,
        "required": bool(required),
        "status": str(status),
        "digest": digest,
    }


def build_evidence_graph(result: Mapping[str, Any]) -> dict[str, Any]:
    mode = str(result.get("mode") or "CHECK").upper()
    repair = mode == "FIX_AND_VERIFY" or isinstance(result.get("repairReport"), Mapping)
    has_after = isinstance(result.get("after"), Mapping)
    final_claim = str((result.get("repairVerification") or {}).get("status") if isinstance(result.get("repairVerification"), Mapping) else result.get("status") or "NOT_VERIFIED").upper()

    nodes = [
        _node("task-goal", "POLICY", result.get("taskGoal"), required=True),
        _node("project-baseline", "BASELINE", result.get("projectBaseline"), required=repair),
        _node("before", "OBSERVATION", result.get("before"), required=True),
        _node("scope-baseline", "BASELINE", result.get("scopeBaseline"), required=repair),
        _node("risk-tier", "POLICY", result.get("riskTier"), required=repair),
        _node("change-budget", "POLICY", result.get("changeBudget"), required=repair),
        _node("fix-plan", "PLAN", result.get("fixPlan"), required=repair and not has_after),
        _node("host-write-receipt", "MUTATION_RECEIPT", result.get("hostWriteReceipt"), required=repair and has_after),
        _node("after", "OBSERVATION", result.get("after"), required=repair and has_after),
        _node("project-tools", "VERIFICATION", result.get("projectToolGate"), required=False),
        _node("patch-quality", "VERIFICATION", result.get("patchQuality"), required=repair and has_after),
        _node("project-drift", "VERIFICATION", result.get("projectDriftGate"), required=repair and has_after),
        _node("comparison", "VERIFICATION", result.get("comparison"), required=repair and has_after),
        _node("repair-verification", "CLAIM_GATE", result.get("repairVerification"), required=repair and has_after, status=final_claim if has_after else None),
    ]
    required_missing = [node["id"] for node in nodes if node["required"] and node["status"] == "MISSING"]

    edges: list[dict[str, str]] = []
    present = {node["id"] for node in nodes if node["status"] != "MISSING"}
    def link(source: str, target: str) -> None:
        if source in present and target in present:
            edges.append({"from": source, "to": target})

    for source in ("task-goal", "project-baseline", "before", "risk-tier", "change-budget"):
        link(source, "fix-plan")
    for source in ("fix-plan", "scope-baseline"):
        link(source, "host-write-receipt")
    for source in ("host-write-receipt", "after"):
        link(source, "comparison")
    for source in ("comparison", "project-tools", "patch-quality", "project-drift", "host-write-receipt"):
        link(source, "repair-verification")

    if required_missing:
        graph_status = "INCOMPLETE"
    elif repair and has_after and final_claim == "VERIFIED":
        graph_status = "COMPLETE_VERIFIED_CHAIN"
    elif repair:
        graph_status = "COMPLETE_PENDING_OR_NONVERIFIED_CHAIN"
    else:
        graph_status = "COMPLETE_OBSERVATION_CHAIN"
    graph = {
        "schemaVersion": "1",
        "status": graph_status,
        "mode": mode,
        "nodes": nodes,
        "edges": edges,
        "requiredMissing": required_missing,
        "finalClaim": final_claim,
        "claimBoundary": "Graph completeness proves evidence dependencies are present; only the underlying Trust Kernel gates can authorize VERIFIED.",
    }
    graph["graphDigest"] = digest_json(graph)
    return graph


__all__ = ["build_evidence_graph"]
