"""Outcome-driven and serial mutation verification primitives."""
from __future__ import annotations

from typing import Any, Iterable, Mapping

from .contracts import ContractViolation


def build_outcome_hypothesis(*, finding_id: str, expected_outcome: Iterable[str], acceptance_criteria: Iterable[str]) -> dict[str, Any]:
    outcomes = [str(x) for x in expected_outcome if str(x).strip()]
    criteria = [str(x) for x in acceptance_criteria if str(x).strip()]
    if not outcomes or not criteria:
        raise ContractViolation("OUTCOME_HYPOTHESIS_INCOMPLETE", ["$: expectedOutcome and acceptanceCriteria are required before verified improvement"])
    return {"schemaVersion": "1", "findingId": finding_id, "expectedOutcome": outcomes, "acceptanceCriteria": criteria}


def evaluate_outcome(hypothesis: Mapping[str, Any], checks: Mapping[str, bool | None]) -> dict[str, Any]:
    criteria = list(hypothesis.get("acceptanceCriteria") or [])
    rows = [{"criterion": c, "result": "PASS" if checks.get(c) is True else "FAIL" if checks.get(c) is False else "NOT_VERIFIED"} for c in criteria]
    if not rows or any(r["result"] == "FAIL" for r in rows):
        status = "NOT_IMPROVED"
    elif any(r["result"] == "NOT_VERIFIED" for r in rows):
        status = "NOT_VERIFIED"
    else:
        status = "VERIFIED"
    return {"schemaVersion": "1", "findingId": hypothesis.get("findingId"), "status": status, "checks": rows, "claimBoundary": "VERIFIED requires every declared acceptance criterion to PASS."}


def classify_mutation_risk(*, touches_auth: bool = False, touches_navigation: bool = False, files_changed: int = 1, layout_scope: str = "component", explicit: str | None = None) -> str:
    if explicit:
        level = explicit.upper()
        if level not in {"LOW", "MEDIUM", "HIGH"}:
            raise ContractViolation("MUTATION_RISK_INVALID", [f"$: {explicit}"])
        return level
    if touches_auth or touches_navigation or files_changed > 4 or layout_scope in {"shell", "global"}:
        return "HIGH"
    if files_changed > 1 or layout_scope in {"page", "section"}:
        return "MEDIUM"
    return "LOW"


def mutation_verification_plan(mutations: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    rows = []
    serial = False
    for index, mutation in enumerate(mutations, start=1):
        risk = classify_mutation_risk(
            touches_auth=bool(mutation.get("touchesAuth")), touches_navigation=bool(mutation.get("touchesNavigation")),
            files_changed=int(mutation.get("filesChanged", 1)), layout_scope=str(mutation.get("layoutScope", "component")),
            explicit=mutation.get("risk"),
        )
        if risk == "HIGH": serial = True
        rows.append({"sequence": index, "findingId": mutation.get("findingId"), "risk": risk, "verifyBeforeNext": risk == "HIGH"})
    return {"schemaVersion": "1", "strategy": "SERIAL" if serial else "BATCH_WITH_INTEGRATION_VERIFICATION", "mutations": rows, "integrationVerificationRequired": True}


def combine_repair_verification(
    *,
    browser_outcome_status: str,
    project_tool_status: str = "NOT_APPLICABLE",
    patch_quality_status: str = "NOT_APPLICABLE",
    project_drift_status: str = "NOT_APPLICABLE",
    change_budget_status: str = "NOT_APPLICABLE",
    host_write_status: str = "NOT_APPLICABLE",
) -> dict[str, Any]:
    """Produce one user-facing repair decision from independent dimensions.

    Critical project-tool failure outranks visual improvement.  Unverified tool
    evidence prevents VERIFIED.  A deterministic patch-quality risk requires
    review instead of allowing the Browser result to silently certify the patch.
    """
    browser = str(browser_outcome_status or "INCONCLUSIVE")
    tools = str(project_tool_status or "NOT_APPLICABLE")
    quality = str(patch_quality_status or "NOT_APPLICABLE")
    drift = str(project_drift_status or "NOT_APPLICABLE")
    budget = str(change_budget_status or "NOT_APPLICABLE")
    host_write = str(host_write_status or "NOT_APPLICABLE")
    blockers: list[str] = []
    warnings: list[str] = []

    if tools == "FAIL":
        blockers.append("PROJECT_TOOL_FAILED")
    elif tools == "NOT_VERIFIED":
        blockers.append("PROJECT_TOOL_NOT_VERIFIED")

    if browser == "REGRESSED":
        blockers.append("BROWSER_REGRESSION")
    elif browser != "IMPROVEMENT_CLAIM_ALLOWED":
        blockers.append("BROWSER_OUTCOME_NOT_PROVEN")

    if drift == "UNEXPECTED_DRIFT":
        blockers.append("UNEXPECTED_PROJECT_DRIFT")
    elif drift == "NOT_VERIFIED":
        blockers.append("PROJECT_DRIFT_NOT_VERIFIED")

    if quality == "QUALITY_RISK":
        warnings.append("PATCH_QUALITY_RISK")

    if host_write not in {"NOT_APPLICABLE", "VERIFIED_V3"}:
        blockers.append("LEGACY_RECEIPT_NOT_SUFFICIENT_FOR_VERIFIED" if host_write == "LEGACY_HISTORY_ONLY" else "HOST_WRITE_V3_NOT_VERIFIED")

    if budget == "BLOCKED":
        blockers.append("CHANGE_BUDGET_EXCEEDED")
    elif budget == "NOT_VERIFIED":
        blockers.append("CHANGE_BUDGET_NOT_VERIFIED")

    if any(code in blockers for code in {"PROJECT_TOOL_FAILED", "BROWSER_REGRESSION", "UNEXPECTED_PROJECT_DRIFT"}):
        status = "FAIL"
    elif blockers:
        status = "NOT_VERIFIED"
    elif warnings:
        status = "REVIEW_REQUIRED"
    else:
        status = "VERIFIED"

    return {
        "schemaVersion": "1",
        "status": status,
        "dimensions": {
            "browserOutcome": browser,
            "projectTools": tools,
            "patchQuality": quality,
            "projectDrift": drift,
            "changeBudget": budget,
            "hostWrite": host_write,
        },
        "blockers": blockers,
        "warnings": warnings,
        "claimBoundary": "VERIFIED requires a trusted V3 Host receipt for write-backed repair, proven Browser improvement, no failed/unverified required project-tool evidence, no unexpected/unverified project drift, an in-budget patch, and no deterministic patch-quality risk in the bounded evidence scope. Legacy receipts are history-only and can never produce VERIFIED.",
    }


__all__ = ["build_outcome_hypothesis", "evaluate_outcome", "classify_mutation_risk", "mutation_verification_plan", "combine_repair_verification"]
