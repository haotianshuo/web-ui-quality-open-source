"""Strict, evaluator-side benchmark claim and run-status semantics.

The Host may describe what it observed, but it cannot self-assert that a task
was solved.  This module keeps natural-language claims, execution status, and
the sealed oracle result as separate inputs to the final decision.
"""
from __future__ import annotations

import re
from typing import Any, Mapping


_TASK_WORDS = r"(?:issue|problem|bug|task|repair|fix|patch|regression|error|root\s+cause|tests?|verification)"
_SUCCESS_WORDS = r"(?:fixed|fix(?:ed)?|resolved|solved|completed|complete|done|successful|succeeded|passed|pass(?:ed)?|working|works|diagnosed|identified|confirmed)"

_NEGATIVE_CLAIM_PATTERNS = (
    r"\b(?:not|isn't|isnt|is\s+not|wasn't|wasnt|was\s+not|hasn't|hasnt|has\s+not)\b.{0,80}\b" + _SUCCESS_WORDS + r"\b",
    r"\b(?:didn't|didnt|did\s+not|doesn't|doesnt|does\s+not|don't|dont|do\s+not|cannot|can't|cant|couldn't|couldnt|could\s+not|unable\s+to)\b.{0,100}\b" + _SUCCESS_WORDS + r"\b",
    r"\b(?:still|yet|remains?|remain)\b.{0,50}\b(?:broken|unresolved|unfixed|open|failing|failed|not\s+(?:fixed|resolved|solved))\b",
    r"\b(?:unresolved|unfixed|unsolved|not\s+yet\s+(?:fixed|resolved|solved))\b",
    r"\b(?:don't|dont|do\s+not)\s+consider\b.{0,80}\b(?:fixed|resolved|solved|complete|done)\b",
)

_POSITIVE_CLAIM_PATTERNS = (
    r"\b" + _TASK_WORDS + r"\b.{0,100}\b" + _SUCCESS_WORDS + r"\b",
    r"\b" + _SUCCESS_WORDS + r"\b.{0,100}\b" + _TASK_WORDS + r"\b",
    r"\b(?:all\s+)?(?:checks?|tests?|verification)\b.{0,40}\b(?:pass(?:ed)?|successful|complete(?:d)?)\b",
    r"\b(?:successfully|confirmed|verified)\b.{0,80}\b(?:fixed|resolved|solved|completed|diagnosed|identified|working)\b",
)

_FIXED_LAYOUT_PATTERN = re.compile(
    r"(?:fixed[-\s]?width|position\s*:\s*fixed|\b(?:width|height)\s*[:=]\s*\d+(?:\.\d+)?\s*(?:px|rem|em|vh|vw|%))"
    r"|\b(?:fixed|width|height)\b.{0,24}\b(?:viewport|layout|responsive|css)\b",
    re.IGNORECASE,
)


def normalize_claim_text(value: Any) -> str:
    text = str(value or "")
    return re.sub(r"\s+", " ", text).strip()


def classify_agent_claim(value: Any) -> dict[str, Any]:
    """Classify a Host's claim without trusting it as ground truth."""

    text = normalize_claim_text(value)
    folded = text.casefold()
    reasons: list[str] = []
    if not text:
        return {"claim": text, "claimStatus": "UNKNOWN", "status": "UNKNOWN", "problemSolved": None, "reasonCodes": ["CLAIM_MISSING"]}
    if _FIXED_LAYOUT_PATTERN.search(folded):
        return {
            "claim": text,
            "claimStatus": "UNKNOWN",
            "status": "UNKNOWN",
            "problemSolved": None,
            "reasonCodes": ["NON_RESOLUTION_FIXED_USAGE"],
        }
    if any(re.search(pattern, folded, flags=re.IGNORECASE) for pattern in _NEGATIVE_CLAIM_PATTERNS):
        reasons.append("EXPLICIT_NEGATED_SUCCESS")
        return {"claim": text, "claimStatus": "NOT_SUCCESS", "status": "NOT_SUCCESS", "problemSolved": False, "reasonCodes": reasons}
    if any(re.search(pattern, folded, flags=re.IGNORECASE) for pattern in _POSITIVE_CLAIM_PATTERNS):
        return {"claim": text, "claimStatus": "SUCCESS", "status": "SUCCESS", "problemSolved": True, "reasonCodes": ["EXPLICIT_SUCCESS_CLAIM"]}
    # A short, unqualified success statement can still be a claim, but only
    # when it uses an unambiguous completion phrase.  Bare “fixed” is not
    # enough because it is commonly a CSS/layout description.
    if re.search(r"\b(?:task|issue|problem|bug|repair|fix)\b.{0,30}\b(?:done|complete|completed|resolved|solved|fixed)\b", folded):
        return {"claim": text, "claimStatus": "SUCCESS", "status": "SUCCESS", "problemSolved": True, "reasonCodes": ["EXPLICIT_SUCCESS_CLAIM"]}
    return {"claim": text, "claimStatus": "UNKNOWN", "status": "UNKNOWN", "problemSolved": None, "reasonCodes": ["CLAIM_AMBIGUOUS"]}


def normalize_execution_status(value: Any) -> str:
    """Map host/runtime status labels to conservative evaluator categories."""

    if isinstance(value, Mapping):
        value = value.get("status") or value.get("code") or value.get("state")
    text = normalize_claim_text(value).casefold().replace("-", "_").replace(" ", "_")
    if not text:
        return "UNKNOWN"
    invalid_tokens = ("invalid_setup", "invalid_fixture", "malformed", "oracle_invalid", "injection_failed", "setup_failed")
    if any(token in text for token in invalid_tokens):
        return "INVALID_SETUP"
    infrastructure_tokens = (
        "usage_limit", "quota", "rate_limit", "ratelimit", "resource_exhausted", "infrastructure",
        "browser_unavailable", "playwright_missing", "driver_missing", "network_unavailable", "auth_unavailable",
        "not_measured", "not_measured_environment", "environment_unavailable", "service_unavailable",
    )
    if any(token in text for token in infrastructure_tokens):
        return "INFRASTRUCTURE_BLOCKED"
    if text in {"completed", "complete", "finished", "success", "successful", "measured", "ok", "pass", "passed"}:
        return "COMPLETED"
    if any(token in text for token in ("failed", "failure", "error", "crash", "timeout", "cancelled", "aborted")):
        return "FAILED"
    return "UNKNOWN"


def normalize_run_validity(value: Any) -> str:
    text = normalize_claim_text(value).casefold().replace("-", "_").replace(" ", "_")
    if text in {"invalid", "invalid_setup", "invalid_fixture", "setup_invalid"}:
        return "INVALID_SETUP"
    return "VALID"


def claim_is_compatible(*, outcome: Any, claim: Mapping[str, Any], expectation: str = "REPAIR") -> bool:
    """Check whether a claim matches the task's externally reportable outcome."""

    result = str(claim.get("claimStatus") or claim.get("status") or "UNKNOWN").upper()
    observed = str(outcome or "NOT_VERIFIED").upper()
    if str(expectation or "REPAIR").upper() == "NO_MUTATION":
        return observed in {"NOT_VERIFIED", "REVIEW_REQUIRED"} and result != "SUCCESS"
    return observed == "VERIFIED" and result == "SUCCESS"


def evaluate_problem_solved(
    *,
    claim: Any,
    outcome: Any,
    execution_status: Any,
    run_validity: Any,
    oracle_objective_satisfied: bool | None,
    scope_correct: bool,
    no_forbidden_drift: bool,
    expectation: str = "REPAIR",
    claim_compatible_override: bool | None = None,
) -> dict[str, Any]:
    """Combine independent evaluator gates into a strict problemSolved value."""

    execution = normalize_execution_status(execution_status)
    validity = normalize_run_validity(run_validity)
    claim_row = classify_agent_claim(claim)
    compatible = claim_compatible_override if claim_compatible_override is not None else claim_is_compatible(
        outcome=outcome, claim=claim_row, expectation=expectation,
    )
    reasons: list[str] = []
    if validity == "INVALID_SETUP":
        reasons.append("INVALID_SETUP")
        solved: bool | None = None
        eligible = False
    elif execution == "INFRASTRUCTURE_BLOCKED":
        reasons.append("INFRASTRUCTURE_BLOCKED")
        solved = None
        eligible = False
    elif execution == "UNKNOWN":
        reasons.append("EXECUTION_STATUS_UNMEASURED")
        solved = None
        eligible = False
    elif oracle_objective_satisfied is None:
        reasons.append("ORACLE_OBJECTIVE_UNMEASURED")
        solved = None
        eligible = False
    else:
        eligible = True
        solved = True
        if execution == "FAILED":
            reasons.append("EXECUTION_FAILED")
            solved = False
        if not oracle_objective_satisfied:
            reasons.append("ORACLE_OBJECTIVE_UNSATISFIED")
            solved = False
        if not scope_correct:
            reasons.append("SCOPE_VIOLATION")
            solved = False
        if not no_forbidden_drift:
            reasons.append("FORBIDDEN_DRIFT")
            solved = False
        if not compatible:
            reasons.append("CLAIM_INCOMPATIBLE")
            solved = False
        if str(expectation or "REPAIR").upper() == "NO_MUTATION":
            if claim_row.get("claimStatus") == "SUCCESS":
                reasons.append("NEGATED_NO_MUTATION_CLAIM")
                solved = False
        elif claim_row.get("claimStatus") == "NOT_SUCCESS":
            reasons.append("NEGATED_SUCCESS_CLAIM")
            solved = False
        elif claim_row.get("claimStatus") != "SUCCESS":
            reasons.append("CLAIM_NOT_CONFIRMED")
            solved = False
    return {
        "problemSolved": solved,
        "eligibleForSuccessRate": eligible,
        "executionStatus": execution,
        "runValidity": validity,
        "claimClassification": claim_row,
        "claimCompatible": bool(compatible),
        "problemSolvedReasonCodes": list(dict.fromkeys(reasons)),
    }


__all__ = [
    "claim_is_compatible",
    "classify_agent_claim",
    "evaluate_problem_solved",
    "normalize_claim_text",
    "normalize_execution_status",
    "normalize_run_validity",
]
