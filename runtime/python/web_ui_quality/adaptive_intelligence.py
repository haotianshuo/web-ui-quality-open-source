"""4.3 experimental controlled-autonomy contracts.

The module is intentionally pure and side-effect free.  It adds deterministic
planning and design intelligence *around* the 4.2.3 Trust Kernel: no function
in this file writes a project, issues a Host receipt, or promotes a claim.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from .contracts import ContractViolation, digest_json


TASK_STATES = {
    "PENDING", "READY", "ACTIVE", "BLOCKED", "VERIFIED", "PARTIAL",
    "NOT_VERIFIED", "FAILED",
}
TERMINAL_TASK_STATES = {"VERIFIED", "PARTIAL", "NOT_VERIFIED", "FAILED"}
REPRODUCTION_STATES = {
    "REPORTED", "REPRODUCED", "ROOT_CAUSE_SUPPORTED", "PATCHED", "VERIFIED",
    "REPRODUCTION_NOT_AVAILABLE",
}
TRACE_CATEGORIES = {
    "DIRECT_FIX", "REQUIRED_SUPPORT", "REQUIRED_CLEANUP", "TEST_OR_VERIFICATION",
    "UNRELATED_IMPROVEMENT", "STYLE_ONLY", "SPECULATIVE_REFACTOR", "UNKNOWN",
}
SURFACE_TYPES = {
    "MARKETING", "BRAND", "PORTFOLIO", "PRODUCT", "DASHBOARD", "DATA_TABLE",
    "ADMIN", "AUTH", "CHECKOUT", "PUBLIC_SERVICE",
}


def _clean_list(values: Iterable[Any], *, sort: bool = True) -> list[str]:
    if values is None:
        return []
    if isinstance(values, (str, bytes)):
        values = (values,)
    try:
        iterator = iter(values)
    except TypeError as error:
        raise ContractViolation("EXPECTED_LIST", ["value must be an iterable collection"]) from error
    rows: list[str] = []
    seen: set[str] = set()
    for value in iterator:
        item = str(value).strip()
        if item and item not in seen:
            seen.add(item)
            rows.append(item)
    return sorted(rows) if sort else rows


def _digest_body(value: Mapping[str, Any], key: str) -> str:
    return digest_json({k: v for k, v in dict(value).items() if k != key})


@dataclass(frozen=True, slots=True)
class TaskFingerprint:
    """Stable identity preventing cross-goal or cross-scope resume."""

    project_identity: dict[str, Any]
    goal_digest: str
    success_criteria_digest: str
    protected_scope_digest: str
    fingerprint_digest: str
    schema_version: str = "1"

    @classmethod
    def build(
        cls,
        *,
        project_identity: Mapping[str, Any],
        goal: str,
        success_criteria: Iterable[str],
        protected_scope: Iterable[str],
    ) -> "TaskFingerprint":
        project = dict(project_identity)
        if not project or not str(goal).strip():
            raise ContractViolation("TASK_FINGERPRINT_INVALID", ["$: project identity and goal are required"])
        criteria = _clean_list(success_criteria)
        scope = _clean_list(protected_scope)
        if not criteria:
            raise ContractViolation("TASK_FINGERPRINT_INVALID", ["$.successCriteria: at least one criterion required"])
        if not scope:
            raise ContractViolation("TASK_FINGERPRINT_INVALID", ["$.protectedScope: at least one path or scope is required"])
        body = {
            "schemaVersion": "1",
            "projectIdentity": project,
            "goalDigest": digest_json({"goal": str(goal).strip()}),
            "successCriteriaDigest": digest_json({"successCriteria": criteria}),
            "protectedScopeDigest": digest_json({"protectedScope": scope}),
        }
        return cls(
            project_identity=project,
            goal_digest=body["goalDigest"],
            success_criteria_digest=body["successCriteriaDigest"],
            protected_scope_digest=body["protectedScopeDigest"],
            fingerprint_digest=digest_json(body),
            schema_version="1",
        )

    def to_dict(self) -> dict[str, Any]:
        value = {
            "schemaVersion": self.schema_version,
            "projectIdentity": dict(self.project_identity),
            "goalDigest": self.goal_digest,
            "successCriteriaDigest": self.success_criteria_digest,
            "protectedScopeDigest": self.protected_scope_digest,
        }
        value["fingerprintDigest"] = self.fingerprint_digest
        return value

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "TaskFingerprint":
        if not isinstance(value, Mapping):
            raise ContractViolation("TASK_FINGERPRINT_INVALID", ["$: object required"])
        payload = dict(value)
        expected = _digest_body(payload, "fingerprintDigest")
        if payload.get("fingerprintDigest") != expected:
            raise ContractViolation("TASK_FINGERPRINT_TAMPERED", ["$.fingerprintDigest: mismatch"])
        required = ("projectIdentity", "goalDigest", "successCriteriaDigest", "protectedScopeDigest")
        if any(key not in payload for key in required):
            raise ContractViolation("TASK_FINGERPRINT_INVALID", ["$: required identity fields are missing"])
        if not isinstance(payload.get("projectIdentity"), Mapping):
            raise ContractViolation("TASK_FINGERPRINT_INVALID", ["$.projectIdentity: object required"])
        return cls(
            project_identity=dict(payload["projectIdentity"]),
            goal_digest=str(payload["goalDigest"]),
            success_criteria_digest=str(payload["successCriteriaDigest"]),
            protected_scope_digest=str(payload["protectedScopeDigest"]),
            fingerprint_digest=str(payload["fingerprintDigest"]),
            schema_version=str(payload.get("schemaVersion", "1")),
        )


@dataclass(slots=True)
class TaskGraph:
    """Small deterministic DAG with fail-closed transitions."""

    nodes: dict[str, dict[str, Any]] = field(default_factory=dict)

    def add_task(
        self,
        task_id: str,
        *,
        goal: str,
        dependencies: Iterable[str] = (),
        scope: Iterable[str] = (),
        risk: str = "MEDIUM",
        budget: Mapping[str, Any] | None = None,
        expected_evidence: Iterable[str] = (),
        success_criteria: Iterable[str] = (),
        status: str = "PENDING",
    ) -> dict[str, Any]:
        task_id = str(task_id).strip()
        if not task_id or task_id in self.nodes:
            raise ContractViolation("TASK_GRAPH_INVALID", ["$: taskId must be unique and non-empty"])
        if status not in TASK_STATES:
            raise ContractViolation("TASK_STATE_INVALID", [f"$: unsupported state {status}"])
        deps = _clean_list(dependencies)
        if task_id in deps:
            raise ContractViolation("TASK_GRAPH_CYCLE", [f"$: task {task_id} depends on itself"])
        node = {
            "taskId": task_id,
            "goal": str(goal).strip(),
            "dependencies": deps,
            "scope": _clean_list(scope),
            "risk": str(risk).upper(),
            "budget": dict(budget or {}),
            "expectedEvidence": _clean_list(expected_evidence),
            "successCriteria": _clean_list(success_criteria),
            "status": status,
        }
        if not node["goal"]:
            raise ContractViolation("TASK_GRAPH_INVALID", [f"$.nodes[{task_id}].goal: required"])
        self.nodes[task_id] = node
        self._validate_graph()
        if status in {"READY", "ACTIVE"} and not self._dependencies_verified(task_id):
            del self.nodes[task_id]
            raise ContractViolation("TASK_DEPENDENCY_BLOCKED", [f"$: {task_id} dependencies are not VERIFIED"])
        return dict(node)

    def _validate_graph(self) -> None:
        unknown = sorted({dep for node in self.nodes.values() for dep in node["dependencies"] if dep not in self.nodes})
        if unknown:
            # Allow a node to be added before its dependency, but never expose a
            # ready/active graph until all references exist.
            return
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(task_id: str) -> None:
            if task_id in visiting:
                raise ContractViolation("TASK_GRAPH_CYCLE", [f"$: cycle detected at {task_id}"])
            if task_id in visited:
                return
            visiting.add(task_id)
            for dep in self.nodes[task_id]["dependencies"]:
                visit(dep)
            visiting.remove(task_id)
            visited.add(task_id)

        for task_id in self.nodes:
            visit(task_id)

    def _dependencies_verified(self, task_id: str) -> bool:
        node = self.nodes[task_id]
        return all(dep in self.nodes and self.nodes[dep]["status"] == "VERIFIED" for dep in node["dependencies"])

    def ready_tasks(self) -> list[str]:
        self._validate_graph()
        return sorted(
            task_id for task_id, node in self.nodes.items()
            if node["status"] in {"PENDING", "READY"} and self._dependencies_verified(task_id)
        )

    def transition(self, task_id: str, status: str, *, reason: str = "") -> dict[str, Any]:
        if task_id not in self.nodes:
            raise ContractViolation("TASK_NOT_FOUND", [f"$: {task_id}"])
        if status not in TASK_STATES:
            raise ContractViolation("TASK_STATE_INVALID", [f"$: unsupported state {status}"])
        node = self.nodes[task_id]
        current = node["status"]
        if current in TERMINAL_TASK_STATES:
            raise ContractViolation("TASK_TERMINAL_IMMUTABLE", [f"$: {task_id} is already {current}"])
        if status in {"READY", "ACTIVE"} and not self._dependencies_verified(task_id):
            raise ContractViolation("TASK_DEPENDENCY_BLOCKED", [f"$: {task_id} dependencies are not VERIFIED"])
        allowed = {
            "PENDING": {"READY", "BLOCKED"},
            "READY": {"ACTIVE", "BLOCKED"},
            "ACTIVE": TERMINAL_TASK_STATES | {"BLOCKED"},
            "BLOCKED": {"READY", "ACTIVE"},
        }
        if status not in allowed.get(current, set()):
            raise ContractViolation("TASK_TRANSITION_INVALID", [f"$: {current}->{status} is not allowed"])
        if status == "BLOCKED" and not str(reason).strip():
            raise ContractViolation("TASK_BLOCK_REASON_REQUIRED", [f"$: {task_id} requires a reason"])
        node["status"] = status
        if reason:
            node["lastReason"] = str(reason).strip()
        return dict(node)

    def to_dict(self) -> dict[str, Any]:
        body = {"schemaVersion": "1", "nodes": [copy.deepcopy(self.nodes[key]) for key in sorted(self.nodes)]}
        return {**body, "graphDigest": digest_json(body)}


def build_execution_budget(*, risk: str = "MEDIUM", long_task: bool = False) -> dict[str, Any]:
    tier = str(risk).upper()
    base = {
        "LOW": {"read": 24, "context": 8, "tool": 12, "browser": 4, "retry": 1, "replan": 1, "noProgress": 3},
        "MEDIUM": {"read": 40, "context": 12, "tool": 20, "browser": 8, "retry": 2, "replan": 2, "noProgress": 4},
        "HIGH": {"read": 64, "context": 20, "tool": 32, "browser": 16, "retry": 2, "replan": 2, "noProgress": 3},
    }.get(tier, None)
    if base is None:
        raise ContractViolation("EXECUTION_BUDGET_INVALID", [f"$: unsupported risk {risk}"])
    if long_task:
        base = {key: value * 2 if key in {"read", "context", "tool"} else value for key, value in base.items()}
    return {
        "schemaVersion": "1", "risk": tier, "limits": base,
        "used": {key: 0 for key in base},
        "claimBoundary": "Budget controls bounded execution only; it cannot grant write authority or claim status.",
    }


def consume_budget(budget: Mapping[str, Any], kind: str, amount: int = 1) -> dict[str, Any]:
    if kind not in budget.get("limits", {}) or int(amount) < 1:
        raise ContractViolation("EXECUTION_BUDGET_INVALID", [f"$: unknown budget channel {kind!r}"])
    limits = dict(budget["limits"])
    used = dict(budget.get("used") or {})
    next_value = int(used.get(kind, 0)) + int(amount)
    if next_value > int(limits[kind]):
        return {"status": "BLOCKED", "kind": kind, "used": int(used.get(kind, 0)), "limit": int(limits[kind]), "reason": "BUDGET_EXCEEDED", "budgetDigest": digest_json(dict(budget))}
    used[kind] = next_value
    value = {**dict(budget), "used": used}
    return {"status": "PASS", "kind": kind, "used": next_value, "limit": int(limits[kind]), "budget": value, "budgetDigest": digest_json(value)}


def propose_replan(
    *,
    previous_plan_digest: str,
    new_plan_digest: str,
    reason: str,
    scope_delta: Iterable[str] = (),
    risk_delta: Mapping[str, Any] | None = None,
    budget_delta: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if not previous_plan_digest or not new_plan_digest or not str(reason).strip():
        raise ContractViolation("REPLAN_INVALID", ["$: previous/new plan digests and reason are required"])
    body = {
        "schemaVersion": "1", "status": "REPLAN_PROPOSED",
        "previousPlanDigest": previous_plan_digest, "newPlanDigest": new_plan_digest,
        "reason": str(reason).strip(), "scopeDelta": _clean_list(scope_delta),
        "riskDelta": dict(risk_delta or {}), "budgetDelta": dict(budget_delta or {}),
        "requiresAuthorization": bool(scope_delta or risk_delta or budget_delta),
        "writeAuthority": False, "claimAuthority": False,
        "claimBoundary": "Replanning is recorded and advisory; it never silently changes Protected Scope or Write Scope.",
    }
    return {**body, "replanDigest": digest_json(body)}


def classify_assumption(
    description: str,
    *,
    changes_goal: bool = False,
    changes_scope: bool = False,
    changes_business_behavior: bool = False,
    destructive: bool = False,
    security_sensitive: bool = False,
) -> dict[str, Any]:
    if not str(description).strip():
        raise ContractViolation("ASSUMPTION_INVALID", ["$.description: required"])
    high = any((changes_goal, changes_scope, changes_business_behavior, destructive, security_sensitive))
    level = "HIGH" if high else "MEDIUM" if any(word in description.casefold() for word in ("layout", "token", "dependency", "browser")) else "LOW"
    return {
        "schemaVersion": "1", "description": str(description).strip(), "level": level,
        "material": level == "HIGH", "resolution": "BLOCK_UNTIL_CLARIFIED" if level == "HIGH" else "RECORD_AND_PROCEED",
        "claimBoundary": "Only material assumptions block; low-level uncertainty never grants authority.",
    }


def complexity_delta(
    *,
    added_files: Iterable[str] = (),
    changed_files: Iterable[str] = (),
    added_dependencies: Iterable[str] = (),
    added_config: Iterable[str] = (),
    added_public_apis: Iterable[str] = (),
    added_abstractions: Iterable[str] = (),
    added_branches: int = 0,
    changed_lines: int = 0,
    goal_size: str = "NORMAL",
) -> dict[str, Any]:
    counts = {
        "addedFiles": len(_clean_list(added_files)),
        "changedFiles": len(_clean_list(changed_files)),
        "addedDependencies": len(_clean_list(added_dependencies)),
        "addedConfig": len(_clean_list(added_config)),
        "addedPublicApis": len(_clean_list(added_public_apis)),
        "addedAbstractions": len(_clean_list(added_abstractions)),
        "addedBranches": max(0, int(added_branches)),
        "changedLines": max(0, int(changed_lines)),
    }
    # Changed existing files are observed separately and do not count as architectural
    # expansion.  This prevents a surgical patch touching several existing files from
    # being misclassified as "new-file" overengineering.
    score = sum(value for key, value in counts.items() if key != "changedFiles")
    small_goal = str(goal_size).upper() in {"SMALL", "PRECISION_FIX"}
    status = "OVERENGINEERING_RISK" if small_goal and (score >= 8 or counts["addedFiles"] >= 3 or counts["addedDependencies"] > 0) else "NORMAL"
    return {"schemaVersion": "1", **counts, "complexityScore": score, "status": status, "claimBoundary": "Complexity is advisory in Shadow; it never overrides safety or Host authority."}


def build_traceability_report(*, goal_digest: str, hunks: Iterable[Mapping[str, Any]], enforce: bool = False) -> dict[str, Any]:
    rows = []
    for item in hunks:
        category = str(item.get("category") or "UNKNOWN")
        if category not in TRACE_CATEGORIES:
            category = "UNKNOWN"
        rows.append({"hunkId": str(item.get("hunkId") or ""), "category": category, "reason": str(item.get("reason") or "").strip()})
    blockers = [row["hunkId"] for row in rows if row["category"] in {"UNRELATED_IMPROVEMENT", "SPECULATIVE_REFACTOR", "UNKNOWN"}]
    if not rows:
        status = "NOT_MEASURED"
        reason = "PATCH_HUNKS_NOT_AVAILABLE"
    else:
        status = "BLOCKED" if enforce and blockers else "ADVISORY" if blockers or any(row["category"] == "STYLE_ONLY" for row in rows) else "PASS"
        reason = None
    body = {"schemaVersion": "1", "goalDigest": goal_digest, "hunks": rows, "untraceableHunks": blockers, "status": status, "reason": reason, "enforce": bool(enforce), "claimBoundary": "Traceability explains patch relevance; missing real patch hunks remains NOT_MEASURED and never upgrades authority."}
    return {**body, "traceabilityDigest": digest_json(body)}


def reproduction_transition(current: str, target: str) -> str:
    allowed = {
        "REPORTED": {"REPRODUCED", "REPRODUCTION_NOT_AVAILABLE"},
        "REPRODUCED": {"ROOT_CAUSE_SUPPORTED"},
        "ROOT_CAUSE_SUPPORTED": {"PATCHED"},
        "PATCHED": {"VERIFIED"},
        "REPRODUCTION_NOT_AVAILABLE": set(),
        "VERIFIED": set(),
    }
    if target not in REPRODUCTION_STATES or target not in allowed.get(current, set()):
        raise ContractViolation("REPRODUCTION_TRANSITION_INVALID", [f"$: {current}->{target} is not allowed"])
    return target


_SURFACE_ALIASES = {
    "marketing": "MARKETING", "landing": "MARKETING", "brand": "BRAND", "portfolio": "PORTFOLIO",
    "product": "PRODUCT", "saas": "PRODUCT", "dashboard": "DASHBOARD", "table": "DATA_TABLE",
    "data_table": "DATA_TABLE", "admin": "ADMIN", "auth": "AUTH", "login": "AUTH",
    "checkout": "CHECKOUT", "public": "PUBLIC_SERVICE", "public_service": "PUBLIC_SERVICE",
}
_GUIDANCE = {"MARKETING": "HIGH", "BRAND": "HIGH", "PORTFOLIO": "HIGH", "PRODUCT": "MEDIUM", "DASHBOARD": "LOW", "DATA_TABLE": "VERY_LOW", "ADMIN": "LOW", "AUTH": "VERY_LOW", "CHECKOUT": "VERY_LOW", "PUBLIC_SERVICE": "VERY_LOW"}
_DEFAULT_VECTOR = {"MARKETING": (8, 7, 3), "BRAND": (8, 7, 3), "PORTFOLIO": (7, 6, 4), "PRODUCT": (5, 4, 5), "DASHBOARD": (3, 2, 7), "DATA_TABLE": (2, 1, 8), "ADMIN": (3, 2, 7), "AUTH": (2, 1, 5), "CHECKOUT": (2, 1, 5), "PUBLIC_SERVICE": (2, 1, 5)}


def route_design_intent(
    *,
    surface_type: str,
    audience: str = "UNKNOWN",
    design_language: str = "UNKNOWN",
    anti_references: Iterable[str] = (),
    preservation_mode: str = "HIGH",
    variance: int | None = None,
    motion: int | None = None,
    density: int | None = None,
    confidence: str = "MEDIUM",
) -> dict[str, Any]:
    surface = _SURFACE_ALIASES.get(str(surface_type).strip().casefold(), str(surface_type).strip().upper())
    if surface not in SURFACE_TYPES:
        raise ContractViolation("DESIGN_INTENT_INVALID", [f"$.surfaceType: unsupported {surface_type}"])
    defaults = _DEFAULT_VECTOR[surface]
    vector = {"variance": defaults[0] if variance is None else int(variance), "motion": defaults[1] if motion is None else int(motion), "density": defaults[2] if density is None else int(density)}
    if any(value < 0 or value > 10 for value in vector.values()):
        raise ContractViolation("DESIGN_INTENT_INVALID", ["$.designVector: values must be 0..10"])
    body = {
        "schemaVersion": "1", "surfaceType": surface, "audience": str(audience).strip() or "UNKNOWN",
        "designLanguage": str(design_language).strip() or "UNKNOWN", "antiReferences": _clean_list(anti_references),
        "preservationMode": str(preservation_mode).upper(), "designVector": vector,
        "guidanceStrength": _GUIDANCE[surface], "confidence": str(confidence).upper(),
        "guidanceAuthority": "ADVISORY", "writeAuthority": False, "claimAuthority": False,
        "claimBoundary": "Design intent guides direction only; it cannot override protected design scope or Trust Kernel authority.",
    }
    return {**body, "designIntentDigest": digest_json(body)}


def compare_design_drift(before: Mapping[str, Any], after: Mapping[str, Any], *, task_kind: str = "precision_fix") -> dict[str, Any]:
    keys = ("font", "radius", "spacing", "color", "shadow", "density", "motion")
    changed = [key for key in keys if before.get(key) != after.get(key)]
    total = len(keys)
    allowed = str(task_kind).casefold() in {"redesign", "significant_reshape", "design_system"}
    status = "PASS" if not changed or allowed else "ADVISORY"
    body = {"schemaVersion": "1", "taskKind": task_kind, "changedTokens": changed, "driftCount": len(changed), "driftRatio": round(len(changed) / total, 4), "status": status, "claimBoundary": "Design drift is objective comparison data; subjective taste remains advisory."}
    return {**body, "driftDigest": digest_json(body)}


def separate_design_review(*, technical_findings: Iterable[Mapping[str, Any]] = (), design_critique: Iterable[Mapping[str, Any]] = ()) -> dict[str, Any]:
    technical = [dict(item) for item in technical_findings]
    critique = [{**dict(item), "authority": "ADVISORY", "status": "ADVISORY"} for item in design_critique]
    blocking = [item for item in technical if str(item.get("severity", "P3")).upper() in {"P0", "P1"} or str(item.get("status", "")).upper() == "FAIL"]
    body = {"schemaVersion": "1", "technicalAudit": technical, "designCritique": critique, "status": "FAIL" if blocking else "PASS_WITH_ADVISORY" if critique else "PASS", "blockingTechnicalFindings": blocking, "claimBoundary": "Only objective technical findings can affect verification; aesthetic preference cannot fail a task."}
    return {**body, "reviewDigest": digest_json(body)}


def build_memory_entry(*, kind: str, payload: Mapping[str, Any], source_digest: str, design_context_digest: str | None = None) -> dict[str, Any]:
    if not str(source_digest).strip():
        raise ContractViolation("MEMORY_ENTRY_INVALID", ["$.sourceDigest: required"])
    if not str(kind).strip() or not isinstance(payload, Mapping):
        raise ContractViolation("MEMORY_ENTRY_INVALID", ["$.kind and $.payload are required"])
    body = {"schemaVersion": "1", "kind": str(kind).upper(), "payload": dict(payload), "sourceDigest": source_digest, "designContextDigest": design_context_digest, "status": "TRUSTED", "claimBoundary": "Trusted memory is source-bound and never carries write or claim authority."}
    return {**body, "memoryDigest": digest_json(body)}


def evaluate_memory_entry(entry: Mapping[str, Any], *, current_source_digest: str, current_design_context_digest: str | None = None) -> dict[str, Any]:
    if not isinstance(entry, Mapping) or not entry.get("memoryDigest"):
        raise ContractViolation("MEMORY_ENTRY_INVALID", ["$: sealed memory entry required"])
    if entry.get("memoryDigest") != _digest_body(entry, "memoryDigest"):
        raise ContractViolation("MEMORY_ENTRY_TAMPERED", ["$.memoryDigest: mismatch"])
    if not str(current_source_digest).strip():
        raise ContractViolation("MEMORY_ENTRY_INVALID", ["$.currentSourceDigest: required"])
    status = "TRUSTED" if entry.get("sourceDigest") == current_source_digest and (entry.get("designContextDigest") in {None, current_design_context_digest}) else "STALE"
    if status == "STALE" and entry.get("sourceDigest") != current_source_digest:
        status = "HISTORICAL_ONLY"
    return {"status": status, "memoryDigest": entry.get("memoryDigest"), "claimBoundary": "Stale or historical memory cannot satisfy current evidence or authorize changes."}


def candidate_count(task_kind: str) -> int:
    return {"precision_fix": 0, "normal_ui": 1, "significant_redesign": 2, "major_brand": 3}.get(str(task_kind).casefold(), 1)


def build_candidate_arena(*, task_kind: str, candidates: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    limit = candidate_count(task_kind)
    rows = [dict(item) for item in candidates[:limit]]
    body = {"schemaVersion": "1", "taskKind": str(task_kind), "candidateLimit": limit, "candidates": [{**row, "writeAuthority": False, "claimAuthority": False} for row in rows], "selectionRequired": bool(rows), "status": "PREVIEW_ONLY", "claimBoundary": "Candidates are preview-only; user selection and the existing Host/V3 write path remain mandatory."}
    return {**body, "arenaDigest": digest_json(body)}


def select_candidate(arena: Mapping[str, Any], candidate_id: str, *, actor: str = "user") -> dict[str, Any]:
    if not isinstance(arena, Mapping) or not arena.get("arenaDigest"):
        raise ContractViolation("CANDIDATE_ARENA_INVALID", ["$: sealed candidate arena required"])
    if arena.get("arenaDigest") != _digest_body(arena, "arenaDigest"):
        raise ContractViolation("CANDIDATE_ARENA_TAMPERED", ["$.arenaDigest: mismatch"])
    candidates = list(arena.get("candidates") or [])
    selected = next((item for item in candidates if item.get("candidateId") == candidate_id), None)
    if selected is None:
        raise ContractViolation("CANDIDATE_NOT_FOUND", [f"$: {candidate_id}"])
    body = {"schemaVersion": "1", "selectedCandidateId": candidate_id, "selectionActor": actor, "selectedCandidateDigest": digest_json(selected), "requiresPatchPlan": True, "writeAuthority": False, "claimAuthority": False, "claimBoundary": "Selection records intent only; it does not apply a patch."}
    return {**body, "selectionDigest": digest_json(body)}


def verification_profile(name: str) -> dict[str, Any]:
    profiles = {
        "HARDEN_PROFILE": ("loading", "empty", "error", "long_text", "i18n", "network_failure", "disabled", "permission_denied"),
        "ADAPT_PROFILE": ("375", "768", "1024", "1440", "touch", "keyboard", "pointer", "portrait", "landscape"),
    }
    key = str(name).upper()
    if key not in profiles:
        raise ContractViolation("VERIFICATION_PROFILE_INVALID", [f"$: unsupported profile {name}"])
    body = {"schemaVersion": "1", "profile": key, "cases": list(profiles[key]), "mode": "ADVISORY", "claimBoundary": "Coverage profiles expand verification observation only; they never grant write or claim authority."}
    return {**body, "profileDigest": digest_json(body)}


def shadow_supervisor(*, graph: TaskGraph, budget: Mapping[str, Any], current_task_id: str | None = None, no_progress_rounds: int = 0) -> dict[str, Any]:
    ready = graph.ready_tasks()
    limits = budget.get("limits", {})
    no_progress_limit = int(limits.get("noProgress", 0))
    if no_progress_limit and no_progress_rounds >= no_progress_limit:
        action = "STOP_RECOMMENDED"
    elif current_task_id and current_task_id in graph.nodes and graph.nodes[current_task_id]["status"] == "ACTIVE":
        action = "CONTINUE"
    elif ready:
        action = "START_NEXT_TASK"
    elif graph.nodes and all(node["status"] in TERMINAL_TASK_STATES for node in graph.nodes.values()):
        action = "COMPLETE"
    else:
        action = "WAIT_FOR_DEPENDENCY"
    body = {"schemaVersion": "1", "mode": "SHADOW_ONLY", "action": action, "currentTaskId": current_task_id, "nextTaskId": ready[0] if ready else None, "readyTasks": ready, "noProgressRounds": int(no_progress_rounds), "authoritative": False, "writeAuthority": False, "claimAuthority": False, "mayChangeTaskResult": False, "graphDigest": graph.to_dict()["graphDigest"], "budgetDigest": digest_json(dict(budget)), "claimBoundary": "Supervisor output is advisory observation; Fixed Workflow, Host writes, and claims remain authoritative."}
    return {**body, "recommendationDigest": digest_json(body)}


EVIDENCE_LEVELS = {
    "E0": 0,  # opinion
    "E1": 1,  # static source
    "E2": 2,  # static screenshot
    "E3": 3,  # runtime DOM
    "E4": 4,  # interactive browser probe
    "E5": 5,  # project-owned tool/test
    "E6": 6,  # Host-attested mutation evidence
}


def qualify_design_finding(
    finding: Mapping[str, Any],
    *,
    subjective: bool = False,
    rule_applicable: bool = True,
    required_by_task_or_contract: bool = False,
    evidence_class: str = "E0",
    minimum_required: str = "E3",
    evidence_fresh: bool = False,
    valid_waiver: bool = False,
) -> dict[str, Any]:
    """Apply the Phase-0 Design Gate without turning taste into authority."""
    evidence = str(evidence_class).upper()
    minimum = str(minimum_required).upper()
    if evidence not in EVIDENCE_LEVELS or minimum not in EVIDENCE_LEVELS:
        raise ContractViolation("EVIDENCE_CLASS_INVALID", ["$: evidence classes must be E0..E6"])
    eligible = bool(
        not subjective
        and rule_applicable
        and required_by_task_or_contract
        and EVIDENCE_LEVELS[evidence] >= EVIDENCE_LEVELS[minimum]
        and evidence_fresh
        and not valid_waiver
    )
    body = {
        "schemaVersion": "1",
        "finding": dict(finding),
        "subjective": bool(subjective),
        "ruleApplicable": bool(rule_applicable),
        "requiredByTaskOrApprovedContract": bool(required_by_task_or_contract),
        "evidenceClass": evidence,
        "minimumRequired": minimum,
        "evidenceFresh": bool(evidence_fresh),
        "validWaiver": bool(valid_waiver),
        "verificationEligible": eligible,
        "authority": "ADVISORY" if subjective or not eligible else "VERIFICATION_INPUT",
        "writeAuthority": False,
        "claimBoundary": "Subjective design judgment is always advisory; objective findings become verification inputs only after evidence qualification.",
    }
    return {**body, "designGateDigest": digest_json(body)}


def memory_authority_decision(
    *,
    operation: str,
    same_project: bool,
    same_tenant: bool,
    policy_permitted: bool,
    revoked: bool = False,
    expired: bool = False,
    verified_source: bool = False,
    redaction_pass: bool = False,
    encryption_required: bool = False,
    encryption_available: bool = True,
    consent: bool = False,
) -> dict[str, Any]:
    """Machine-readable authority decision for future persistent memory services.

    This function never persists data itself.  It deliberately keeps storage outside
    this module so a model cannot turn a memory suggestion into durable authority.
    """
    op = str(operation).upper()
    if op not in {"READ", "WRITE", "DELETE"}:
        raise ContractViolation("MEMORY_OPERATION_INVALID", ["$: operation must be READ, WRITE, or DELETE"])
    reasons: list[str] = []
    if not same_project: reasons.append("PROJECT_ISOLATION_MISMATCH")
    if not same_tenant: reasons.append("TENANT_ISOLATION_MISMATCH")
    if not policy_permitted: reasons.append("POLICY_DENIED")
    if revoked: reasons.append("MEMORY_REVOKED")
    if expired: reasons.append("MEMORY_EXPIRED")
    if op == "WRITE":
        if not verified_source: reasons.append("SOURCE_NOT_VERIFIED")
        if not redaction_pass: reasons.append("REDACTION_NOT_PASSED")
        if not consent: reasons.append("CONSENT_NOT_ESTABLISHED")
        if encryption_required and not encryption_available:
            reasons.append("MEMORY_WRITE_DENIED_ENCRYPTION_UNAVAILABLE")
    allowed = not reasons
    body = {
        "schemaVersion": "1", "operation": op, "allowed": allowed,
        "reasons": reasons or ["POLICY_REQUIREMENTS_SATISFIED"],
        "persistentWritePerformed": False,
        "writeAuthority": False,
        "claimBoundary": "This decision qualifies memory authority only; persistence requires an external policy-bound memory service and audit receipt.",
    }
    return {**body, "memoryAuthorityDigest": digest_json(body)}


def build_authorization_binding(
    *,
    task_fingerprint: str,
    selected_candidate_digest: str,
    plan_digest_value: str,
    source_scope_digest: str,
    protected_scope_digest: str,
    risk_digest: str,
    budget_digest: str,
    change_intent_digest: str,
) -> dict[str, Any]:
    """Prepare, but never issue, an authorization ticket binding."""
    fields = {
        "taskFingerprint": task_fingerprint,
        "selectedCandidateDigest": selected_candidate_digest,
        "planDigest": plan_digest_value,
        "sourceScopeDigest": source_scope_digest,
        "protectedScopeDigest": protected_scope_digest,
        "riskDigest": risk_digest,
        "budgetDigest": budget_digest,
        "changeIntentDigest": change_intent_digest,
    }
    if any(not str(v).strip() for v in fields.values()):
        raise ContractViolation("AUTHORIZATION_BINDING_INCOMPLETE", ["$: all binding digests are required"])
    body = {
        "schemaVersion": "1", **fields,
        "authorizationState": "CANDIDATE_ONLY",
        "hostApplyRequired": True,
        "receiptProtocolRequired": "V3",
        "writeAuthority": False,
        "claimAuthority": False,
    }
    return {**body, "authorizationTicketDigest": digest_json(body)}


__all__ = [
    "TaskFingerprint", "TaskGraph", "TASK_STATES", "build_execution_budget", "consume_budget",
    "propose_replan", "classify_assumption", "complexity_delta", "build_traceability_report",
    "reproduction_transition", "route_design_intent", "compare_design_drift", "separate_design_review",
    "build_memory_entry", "evaluate_memory_entry", "candidate_count", "build_candidate_arena",
    "select_candidate", "verification_profile", "shadow_supervisor",
    "EVIDENCE_LEVELS", "qualify_design_finding", "memory_authority_decision",
    "build_authorization_binding",
]
