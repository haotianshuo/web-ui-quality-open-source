"""Task Goal Anchor: explicit scope control for long-running agent work."""
from __future__ import annotations

from typing import Any, Iterable, Mapping

from .contracts import ContractViolation, digest_json
from .governance_artifacts import now_iso, read_json, write_json_atomic

_RELEVANCE = {"DIRECT", "SUPPORTING", "UNRELATED"}
_ARTIFACT = "governance/task-goal.json"


def create_task_goal(run_dir, *, task_id: str, goal: str, success_criteria: Iterable[str], non_goals: Iterable[str] = ()) -> dict[str, Any]:
    if not task_id or not str(goal).strip():
        raise ContractViolation("TASK_GOAL_INVALID", ["$: taskId and goal are required"])
    criteria = [str(x).strip() for x in success_criteria if str(x).strip()]
    if not criteria:
        raise ContractViolation("TASK_GOAL_INVALID", ["$.successCriteria: at least one criterion required"])
    body = {
        "schemaVersion": "1",
        "taskId": task_id,
        "goal": str(goal).strip(),
        "successCriteria": criteria,
        "nonGoals": [str(x).strip() for x in non_goals if str(x).strip()],
        "scopeChanges": [],
        "createdAt": now_iso(),
        "updatedAt": None,
    }
    value = {**body, "goalDigest": digest_json(body)}
    write_json_atomic(run_dir, _ARTIFACT, value, replace=False)
    return value


def load_task_goal(run_dir) -> dict[str, Any]:
    value = read_json(run_dir, _ARTIFACT, code="TASK_GOAL_MISSING")
    body = {k: v for k, v in value.items() if k != "goalDigest"}
    if value.get("goalDigest") != digest_json(body):
        raise ContractViolation("TASK_GOAL_TAMPERED", ["$.goalDigest: mismatch"])
    return value


def update_task_goal(run_dir, *, goal: str | None = None, add_non_goals: Iterable[str] = (), reason: str, actor: str = "user") -> dict[str, Any]:
    current = load_task_goal(run_dir)
    if not str(reason).strip():
        raise ContractViolation("TASK_GOAL_SCOPE_CHANGE_INVALID", ["$.reason: required"])
    previous_digest = current["goalDigest"]
    new_goal = str(goal).strip() if goal is not None else current["goal"]
    non_goals = list(current.get("nonGoals") or [])
    for item in add_non_goals:
        clean = str(item).strip()
        if clean and clean not in non_goals:
            non_goals.append(clean)
    change = {
        "at": now_iso(), "actor": actor, "reason": str(reason).strip(),
        "previousGoal": current["goal"], "newGoal": new_goal,
        "previousDigest": previous_digest,
    }
    body = {k: v for k, v in current.items() if k != "goalDigest"}
    body.update({"goal": new_goal, "nonGoals": non_goals, "updatedAt": change["at"]})
    body["scopeChanges"] = [*(current.get("scopeChanges") or []), change]
    value = {**body, "goalDigest": digest_json(body)}
    write_json_atomic(run_dir, _ARTIFACT, value)
    return value


def finding_goal_relevance(finding: Mapping[str, Any], goal: Mapping[str, Any]) -> str:
    explicit = finding.get("goalRelevance")
    if explicit in _RELEVANCE:
        return str(explicit)
    related = {str(x).casefold() for x in finding.get("goalTags", []) if str(x).strip()}
    goal_tags = {str(x).casefold() for x in goal.get("tags", []) if str(x).strip()}
    if related and goal_tags and related & goal_tags:
        return "DIRECT"
    return "UNRELATED"


def auto_fix_allowed(*, goal_relevance: str, critical_safety: bool = False, allow_supporting: bool = False) -> dict[str, Any]:
    if goal_relevance not in _RELEVANCE:
        raise ContractViolation("GOAL_RELEVANCE_INVALID", [f"$: {goal_relevance!r}"])
    if critical_safety:
        return {"allowed": True, "reason": "CRITICAL_SAFETY_OVERRIDE", "goalRelevance": goal_relevance}
    if goal_relevance == "DIRECT":
        return {"allowed": True, "reason": "DIRECT_TO_GOAL", "goalRelevance": goal_relevance}
    if goal_relevance == "SUPPORTING" and allow_supporting:
        return {"allowed": True, "reason": "SUPPORTING_EXPLICITLY_ALLOWED", "goalRelevance": goal_relevance}
    return {"allowed": False, "reason": "OUTSIDE_AUTO_FIX_SCOPE", "goalRelevance": goal_relevance}


def classify_finding_for_goal(finding: Mapping[str, Any], goal: Mapping[str, Any]) -> str:
    """Bind an observed finding to the current Task Goal without expanding scope."""
    haystack = " ".join(str(finding.get(key) or "") for key in ("routeTemplate", "semanticTarget", "summary", "impact", "recommendation")).casefold()
    for item in goal.get("nonGoals", []) or []:
        token = str(item).strip().casefold()
        if token and token in haystack:
            return "UNRELATED"
    if str(finding.get("issueType") or "") == "COMPLETENESS_SUGGESTION":
        return "SUPPORTING"
    return "DIRECT"


def bind_findings_to_goal(findings: Iterable[Mapping[str, Any]], goal: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [{**dict(item), "goalRelevance": classify_finding_for_goal(item, goal)} for item in findings]
