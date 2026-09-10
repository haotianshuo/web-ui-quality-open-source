"""Single default product entry for check, focused fix, redesign, and specialist audit."""
from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import parse_qsl, urlencode, urlsplit

from .comparison_gate import evaluate_improvement_claim
from .condition_registry import RunConditions, compare_conditions, normalize_viewports
from .contracts import ContractViolation, digest_json, sha256_hex
from .core import audit_project
from .experience_run import (
    create_experience_run,
    load_experience_run,
    record_phase_artifact,
    seal_after,
    seal_before,
    validate_after_binding,
    write_phase_file,
)
from .fix_workflow import prepare_fix_workflow
from .host_bridge import bridge_request, require_verified_host_write, verify_host_write_receipt, build_repair_scope_revert_plan
from .phase1_host_apply import verify_persisted_host_write_receipt_v3, require_host_write_receipt_v3
from .v3_mainline import build_public_v3_apply_binding, persist_public_v3_apply_binding, load_public_v3_apply_binding, build_v3_revert_plan
from .execution_state import ExecutionState, evidence_state, browser_result_status
from .user_outcome import user_outcome
from .intent_router import route_user_intent
from .control_intent import parse_control_intent
from .task_intent_adapter import normalize_task_intent
from .capability_router import route_capabilities
from .task_goal import create_task_goal, load_task_goal, auto_fix_allowed
from .run_checkpoint import (create_checkpoint, build_run_health, find_latest_compatible_run, find_latest_compatible_checkpoint, find_checkpoint_before, resume_checkpoint)
from .outcome_verification import mutation_verification_plan, combine_repair_verification
from .project_launcher import inspect_project_start
from .release_info import PACKAGE_VERSION
from .smart_acceptance import run_smart_acceptance
from .smart_product_discovery import build_product_discovery, export_product_discovery
from .ui_inventory import run_ui_inventory
from .project_baseline import (
    attach_project_baseline, load_project_baseline, compare_project_baseline, build_project_baseline,
    build_scope_baseline, classify_post_repair_drift,
)
from .systemic_repair import analyze_repair_scope
from .patch_quality import evaluate_patch_quality
from .project_tool_boundary import plan_project_tool_execution, verify_host_tool_results, require_verified_host_tool_result, summarise_host_tool_results
from .verification_budget import select_verification_budget
from .repair_report import build_repair_report
from .task_result import build_task_result
from .context_packet import build_relevant_context_packet
from .risk_tier import classify_risk_tier
from .change_budget import build_change_budget, evaluate_change_budget
from .evidence_graph import build_evidence_graph
from .phase1_shadow import build_shadow_observation
from .browser_request_policy import bind_approved_requests, request_rule_digest, validate_bound_approved_requests

_UI_INVENTORY_REQUEST = re.compile(
    r"(?:ui\s*(?:asset\s*)?inventory|ui\s*资产|资产盘点|全站\s*ui|按钮统计|风格统计|样式统计|统计[^。\n]{0,24}(?:按钮|颜色|字号|圆角|间距))",
    re.IGNORECASE,
)


def _is_ui_inventory_request(request: str | None) -> bool:
    return bool(_UI_INVENTORY_REQUEST.search(request or ""))


_MODE_MAP = {
    "inspect": "CHECK",
    "fix": "FIX_AND_VERIFY",
    "redesign": "DEEP_REDESIGN",
    "specialized-audit": "SPECIALIZED_AUDIT",
    "CHECK": "CHECK",
    "FIX_AND_VERIFY": "FIX_AND_VERIFY",
    "DEEP_REDESIGN": "DEEP_REDESIGN",
    "SPECIALIZED_AUDIT": "SPECIALIZED_AUDIT",
}


def _project_fingerprint(path: Path | None) -> str | None:
    if path is None or not path.is_dir():
        return None
    excluded = {"node_modules", ".git", "dist", "build", ".next", "coverage", "artifacts", "__pycache__"}
    rows: list[dict[str, Any]] = []
    for file in sorted(path.rglob("*")):
        if not file.is_file() or file.is_symlink() or any(part in excluded for part in file.relative_to(path).parts):
            continue
        rel = file.relative_to(path).as_posix()
        try:
            raw = file.read_bytes()
        except OSError:
            continue
        rows.append({"path": rel, "sha256": sha256_hex(raw), "bytes": len(raw)})
        if len(rows) >= 500:
            break
    return digest_json(rows)


def _url_fields(url: str | None) -> dict[str, Any]:
    if not url:
        return {"url": None, "scheme": None, "host": None, "port": None, "route": None, "query": None, "queryPolicy": "exact"}
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ContractViolation("EXPERIENCE_TARGET_INVALID", ["$: URL must be absolute http/https"])
    default_port = 443 if parsed.scheme == "https" else 80
    query = urlencode(sorted(parse_qsl(parsed.query, keep_blank_values=True)), doseq=True)
    normalized = f"{parsed.scheme}://{parsed.hostname.casefold()}:{parsed.port or default_port}{parsed.path or '/'}"
    if query:
        normalized += f"?{query}"
    return {
        "url": normalized,
        "scheme": parsed.scheme.casefold(),
        "host": parsed.hostname.casefold(),
        "port": parsed.port or default_port,
        "route": parsed.path or "/",
        "query": query or None,
        "queryPolicy": "exact",
    }


def _target_identity(target: str | Path, url: str | None) -> tuple[dict[str, Any], Path | None, str | None]:
    raw = str(target)
    parsed = urlsplit(raw)
    if parsed.scheme in {"http", "https"} and parsed.hostname:
        fields = _url_fields(raw)
        return {"kind": "url", **fields}, None, fields["url"]
    project = Path(raw).expanduser().resolve()
    if not project.is_dir():
        raise ContractViolation("EXPERIENCE_TARGET_INVALID", ["$: target must be URL or project directory"])
    fields = _url_fields(url)
    return {"kind": "project", "projectRoot": ".", **fields}, project, fields["url"]


def _conditions(
    *,
    target: Mapping[str, Any],
    project: Path | None,
    url: str | None,
    viewports: Sequence[Sequence[int]] | None,
    locale: str,
    theme: str,
    browser: str,
    allowed_origins: Iterable[str],
    approved_request_policy: Sequence[Mapping[str, Any]],
    user_role: str | None,
    auth_state: str,
    test_data_state: str,
    readiness_rule: Mapping[str, Any] | None,
    safe_task: Mapping[str, Any] | None,
    feature_flags: Mapping[str, Any] | None,
) -> RunConditions:
    fields = _url_fields(url)
    return RunConditions(
        url=fields["url"],
        route=fields["route"] or target.get("route"),
        source_fingerprint=_project_fingerprint(project),
        scheme=fields["scheme"],
        host=fields["host"],
        port=fields["port"],
        query_policy=fields["queryPolicy"],
        query=fields["query"],
        target_kind=str(target.get("kind") or "unknown"),
        project_root="." if project is not None else None,
        user_role=user_role,
        auth_state=auth_state,
        test_data_state=test_data_state,
        locale=locale,
        theme=theme,
        browser=browser,
        viewports=normalize_viewports(viewports),
        allowed_origins=tuple(sorted(set(str(item) for item in allowed_origins))),
        approved_request_policy=tuple(dict(item) for item in approved_request_policy),
        readiness_rule=dict(readiness_rule or {}),
        safe_task=dict(safe_task or {}),
        feature_flags=dict(feature_flags or {}),
    )


def _result_name(selected: str, has_after: bool) -> str:
    if selected == "FIX_AND_VERIFY":
        return "fix-verify-result.json" if has_after else "fix-plan-result.json"
    return {
        "CHECK": "check-result.json",
        "DEEP_REDESIGN": "redesign-result.json",
        "SPECIALIZED_AUDIT": "audit-result.json",
    }[selected]


def _emit_phase1_shadow_artifact(
    run_dir: Path,
    *,
    run_id: str,
    task_id: str,
    session_id: str,
    request: str | None,
    selected_mode: str,
    target_kind: str,
    intent_route: Mapping[str, Any],
    control_intent: Mapping[str, Any],
    fixed_result: Mapping[str, Any],
    task_goal: Mapping[str, Any] | None = None,
) -> None:
    """Persist best-effort non-authoritative shadow evidence outside sealed phases.

    Shadow failures are intentionally isolated from the Fixed Workflow.  These
    artifacts are diagnostics only and are never consumed by the 4.0 Trust
    Kernel, Claim Authority, write authorization, or TaskResult aggregation.
    """
    try:
        payload = build_shadow_observation(
            run_id=run_id, task_id=task_id, session_id=session_id, request=request,
            selected_mode=selected_mode, target_kind=target_kind,
            intent_route=intent_route, control_intent=control_intent,
            fixed_result=fixed_result, task_goal=task_goal,
        )
        shadow_dir = run_dir / "experimental" / "phase1-shadow"
        shadow_dir.mkdir(parents=True, exist_ok=True)
        existing = sorted(shadow_dir.glob("*-observation.json"))
        sequence = len(existing) + 1
        target = shadow_dir / f"{sequence:04d}-observation.json"
        raw = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        with target.open("x", encoding="utf-8") as handle:
            handle.write(raw)
    except Exception:
        # Shadow must never change the authoritative run result or availability.
        # Persist a redacted diagnostic marker so a missing observation can be
        # distinguished from an observer failure without leaking user input,
        # paths, or exception text into the artifact.
        try:
            shadow_dir = run_dir / "experimental" / "phase1-shadow"
            shadow_dir.mkdir(parents=True, exist_ok=True)
            sequence = len(list(shadow_dir.glob("*.json"))) + 1
            failure = {
                "schemaVersion": "1",
                "producer": "web-ui-quality-phase1-runtime-shadow",
                "mode": "SHADOW_ONLY",
                "status": "SHADOW_OBSERVER_ERROR",
                "authoritative": False,
                "taskBinding": {"runId": run_id, "taskId": task_id, "sessionId": session_id},
                "errorType": "OBSERVER_BUILD_FAILED",
                "claimBoundary": "The Shadow observer failed in isolation; the Fixed Workflow result remains authoritative.",
            }
            target = shadow_dir / f"{sequence:04d}-error.json"
            with target.open("x", encoding="utf-8") as handle:
                handle.write(json.dumps(failure, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
        except Exception:
            pass
        return


def run_experience_fix(
    target: str | Path,
    artifacts_root: str | Path,
    *,
    request: str | None = None,
    mode: str | None = None,
    task_id: str,
    session_id: str,
    url: str | None = None,
    existing_run: str | Path | None = None,
    after_url: str | None = None,
    files: Iterable[str] = (),
    business_context: Mapping[str, Any] | None = None,
    viewports: Sequence[Sequence[int]] | None = None,
    locale: str = "zh-CN",
    theme: str = "light",
    browser: str = "chromium",
    allowed_origins: Iterable[str] = (),
    approved_requests: Sequence[Mapping[str, str]] = (),
    environment: str | None = None,
    user_role: str | None = None,
    auth_state: str = "anonymous",
    test_data_state: str = "unspecified",
    readiness_rule: Mapping[str, Any] | None = None,
    safe_task: Mapping[str, Any] | None = None,
    feature_flags: Mapping[str, Any] | None = None,
    browser_executable: str | Path | None = None,
    storage_state: str | Path | Mapping[str, Any] | None = None,
    host_write_receipt: Mapping[str, Any] | None = None,
    host_patch_candidate: Mapping[str, Any] | None = None,
    host_receipt_hmac_key: bytes | str | None = None,
    host_tool_results: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    canonical_intent = normalize_task_intent(request)
    if canonical_intent["conflictStatus"] == "INTENT_CONFLICT":
        raise ContractViolation(
            "INTENT_CONFLICT",
            ["$: write request conflicts with an explicit whole-task read-only prohibition"],
        )
    control = parse_control_intent(request)
    routed = route_user_intent(request)
    control_mode = {"CHECK": "CHECK", "FIX": "FIX_AND_VERIFY"}.get(control.get("action"))
    requested_mode = _MODE_MAP.get(mode or control_mode or routed["intent"])
    # A clean inspection is never allowed to enter the repair workflow merely
    # because a stale/ambient mode says FIX_AND_VERIFY.  An explicit repair
    # request is already rejected above when it conflicts with whole-task
    # read-only language; this branch covers the read-only-only case.
    if canonical_intent["readOnlyRequired"] and not canonical_intent["writeRequested"] and requested_mode == "FIX_AND_VERIFY":
        selected = "CHECK"
    else:
        selected = requested_mode
    if selected is None:
        raise ContractViolation("EXPERIENCE_MODE_INVALID", [f"$: unsupported mode {mode!r}"])
    execution = ExecutionState()
    target_identity, project, actual_url = _target_identity(target, url)
    artifacts = Path(artifacts_root).expanduser().resolve()
    existing_meta: Mapping[str, Any] | None = load_experience_run(existing_run) if existing_run else None
    run_id = str(existing_meta.get("runId")) if existing_meta is not None else f"wuq-{uuid.uuid4().hex[:16]}"
    if existing_meta is not None:
        stored_policy = list((existing_meta.get("conditions") or {}).get("approved_request_policy") or [])
        bound_approved_requests = validate_bound_approved_requests(
            stored_policy, task_id=task_id, run_id=run_id, session_id=session_id,
        ) if stored_policy else ()
        if approved_requests and request_rule_digest(approved_requests) != request_rule_digest(bound_approved_requests):
            raise ContractViolation("BROWSER_REQUEST_POLICY_CHANGED", ["$: Before/After Browser request approval rules differ; start a new run instead of weakening comparability"])
    else:
        bound_approved_requests = bind_approved_requests(
            approved_requests, task_id=task_id, run_id=run_id, session_id=session_id,
        ) if approved_requests else ()
    conditions = _conditions(
        target=target_identity, project=project, url=actual_url, viewports=viewports,
        locale=locale, theme=theme, browser=browser, allowed_origins=allowed_origins,
        approved_request_policy=bound_approved_requests,
        user_role=user_role, auth_state=auth_state, test_data_state=test_data_state,
        readiness_rule=readiness_rule, safe_task=safe_task, feature_flags=feature_flags,
    )
    matrix = [(item.width, item.height) for item in conditions.viewports]
    execution.advance("PREFLIGHT", status="PASS", input_ref="request", output_ref="target+conditions")

    # Natural-language workflow controls are resolved before any Browser or source
    # workflow starts. They restore/checkpoint state only; they never authorize a
    # project write.
    if control.get("action") in {"CHECKPOINT", "RESUME", "REVISE_ASSUMPTION"}:
        if control.get("action") == "REVISE_ASSUMPTION":
            state = None
            if existing_run:
                try:
                    from .assumption_graph import load_assumption_graph
                    state = load_assumption_graph(existing_run)
                except ContractViolation:
                    state = None
            return {
                "schemaVersion": "2", "producer": "web-ui-quality-experience-fix", "packageVersion": PACKAGE_VERSION,
                "status": "NEEDS_EXPLICIT_ASSUMPTION_REVISION", "controlIntent": control,
                "requiredFields": ["assumptionId", "newValue"], "assumptionState": state,
                "writeAuthorization": False, "writeAuthority": "HOST_APPROVAL_REQUIRED",
                "claimBoundary": "An assumption is never silently overwritten; identify the old assumption and new value explicitly.",
            }

        if existing_run:
            control_run_dir = Path(existing_run).expanduser().resolve()
            control_run = load_experience_run(control_run_dir)
            if control_run.get("taskId") != task_id or control_run.get("targetDigest") != digest_json(target_identity):
                raise ContractViolation("CHECKPOINT_RUN_MISMATCH", ["$: current task/target does not match the selected run"])
        else:
            explicit_mode = _MODE_MAP.get(mode) if mode else None
            if control.get("action") == "CHECKPOINT":
                control_run_dir = find_latest_compatible_run(
                    artifacts, task_id=task_id, target_identity=target_identity, mode=explicit_mode,
                )
            else:
                control_run_dir, _ = find_latest_compatible_checkpoint(
                    artifacts, task_id=task_id, target_identity=target_identity, mode=explicit_mode,
                )
            control_run = load_experience_run(control_run_dir)

        if control.get("action") == "CHECKPOINT":
            phase_order = ("report", "compare", "after", "before")
            current_phase = next((name for name in phase_order if control_run.get("phases", {}).get(name, {}).get("status") == "SEALED"), "before")
            try:
                current_goal = load_task_goal(control_run_dir)
            except ContractViolation:
                current_goal = {}
            cp = create_checkpoint(control_run_dir, current_phase=current_phase, task_goal=current_goal)
            return {
                "schemaVersion": "2", "producer": "web-ui-quality-experience-fix", "packageVersion": PACKAGE_VERSION,
                "status": "CHECKPOINTED", "controlIntent": control, "runId": control_run["runId"],
                "runDir": ".", "checkpoint": cp,
                "runHealth": build_run_health(control_run_dir),
                "writeAuthorization": False, "writeAuthority": "HOST_APPROVAL_REQUIRED",
            }

        if control.get("resumeTarget") == "LOOKUP_BY_DESCRIPTION":
            query = control.get("resumeQuery")
            selected_checkpoint = find_checkpoint_before(control_run_dir, str(query or ""))
            resumed = resume_checkpoint(control_run_dir, selected_checkpoint["checkpointId"], task_id=task_id)
        else:
            resumed = resume_checkpoint(control_run_dir, "latest", task_id=task_id)
        return {
            "schemaVersion": "2", "producer": "web-ui-quality-experience-fix", "packageVersion": PACKAGE_VERSION,
            "status": "RESUMED", "controlIntent": control, "runId": control_run["runId"],
            "runDir": ".", "checkpoint": resumed,
            "runHealth": build_run_health(control_run_dir, active_capabilities=resumed.get("activeCapabilities", [])),
            "writeAuthorization": False, "writeAuthority": "HOST_APPROVAL_REQUIRED",
            "claimBoundary": resumed.get("resumeClaimBoundary"),
        }

    if existing_run:
        run = dict(existing_meta or load_experience_run(existing_run))
        run_dir = Path(run["runDir"])
        if run["taskId"] != task_id or run["sessionId"] != session_id or run.get("mode") != selected:
            raise ContractViolation("BASELINE_IDENTITY_MISMATCH", ["$: current task, session, or mode differs from immutable run"])
    else:
        run = create_experience_run(
            artifacts, task_id=task_id, session_id=session_id, mode=selected,
            target=target_identity, conditions=conditions.to_dict(), run_id=run_id,
        )
        run_dir = Path(run["runDir"])

    # Every run has an explicit goal anchor. Existing runs retain their original
    # anchor; scope changes must use task_goal.update_task_goal rather than being
    # inferred silently from later model output.
    try:
        task_goal = load_task_goal(run_dir)
    except ContractViolation as error:
        if error.code != "TASK_GOAL_MISSING":
            raise
        protected = [str(x) for x in control.get("protectedScope", [])]
        task_goal = create_task_goal(
            run_dir, task_id=task_id,
            goal=(request or {
                "CHECK": "Evaluate the requested Web UI experience without mutation",
                "FIX_AND_VERIFY": "Fix and verify the requested Web UI problem within Host-approved scope",
                "DEEP_REDESIGN": "Develop isolated redesign directions without modifying the source project",
                "SPECIALIZED_AUDIT": "Run the requested specialized Web UI audit",
            }[selected]),
            success_criteria=[
                "requested scope is addressed without silent scope expansion",
                "any PASS or improvement claim is backed by current evidence",
            ],
            non_goals=protected,
        )

    profile = control.get("profile") or ("full" if selected == "SPECIALIZED_AUDIT" else "standard")
    capability_routing = route_capabilities(
        task=selected, profile=profile, route=actual_url, risk="MEDIUM" if selected == "FIX_AND_VERIFY" else "LOW",
        intent=control.get("action"),
    )
    initial_risk_tier = classify_risk_tier(request, source_scope=files) if selected == "FIX_AND_VERIFY" else None
    initial_change_budget = (
        build_change_budget(request, risk_tier=initial_risk_tier["tier"], explicit_files=files)
        if initial_risk_tier is not None else None
    )

    project_baseline = None
    if project is not None:
        baseline_path = run_dir / "before" / "project-baseline.json"
        current_state = load_experience_run(run_dir)
        if current_state.get("phases", {}).get("before", {}).get("status") != "SEALED" and not baseline_path.exists():
            project_baseline = attach_project_baseline(run_dir, project, target_files=files)
        elif baseline_path.is_file():
            if current_state.get("phases", {}).get("before", {}).get("status") == "SEALED":
                project_baseline = load_project_baseline(run_dir)
            else:
                project_baseline = json.loads(baseline_path.read_text(encoding="utf-8"))

    start_plan = inspect_project_start(project, supplied_url=actual_url) if project is not None else {
        "status": "USE_SUPPLIED_URL", "url": actual_url, "writes": 0, "installAttempts": 0,
    }
    common = {
        "schemaVersion": "2",
        "producer": "web-ui-quality-experience-fix",
        "packageVersion": PACKAGE_VERSION,
        "runId": run["runId"],
        "taskId": task_id,
        "sessionId": session_id,
        "mode": selected,
        "intentRoute": routed,
        "controlIntent": control,
        "taskGoal": task_goal,
        "capabilityRouting": capability_routing,
        "activeCapabilities": capability_routing["activeCapabilities"],
        "riskTier": initial_risk_tier,
        "changeBudget": initial_change_budget,
        "runDir": ".",
        "sourceProjectChanged": False,
        "projectStartPlan": start_plan,
        "projectBaseline": ({
            "baselineDigest": project_baseline.get("baselineDigest"),
            "fileCount": project_baseline.get("fileCount"),
            "frameworks": (project_baseline.get("metadata") or {}).get("frameworks", []),
            "packageManager": (project_baseline.get("metadata") or {}).get("packageManager"),
            "completenessStatus": project_baseline.get("completenessStatus"),
            "targetCoverage": dict(project_baseline.get("targetCoverage") or {}),
            "criticalContextCoverage": dict(project_baseline.get("criticalContextCoverage") or {}),
        } if isinstance(project_baseline, Mapping) else None),
    }

    execution.advance("PLAN", status="PASS", input_ref="target+conditions", output_ref="bounded-work-plan")

    if selected == "CHECK":
        report = run_smart_acceptance(
            target, output_dir=run_dir / "before", url=actual_url,
            business_context=business_context, viewports=matrix, locale=locale, theme=theme,
            allow_origins=allowed_origins, environment=environment, browser_name=browser, browser_executable=browser_executable, storage_state=storage_state, task_goal=task_goal, approved_requests=bound_approved_requests,
        )
        manifest = seal_before(run_dir)
        result = {**common, "status": report.get("status"), "pageHealth": report.get("pageHealth"), "before": report, "baselineManifest": manifest, "open": report.get("open")}

    elif selected == "FIX_AND_VERIFY":
        current_run = load_experience_run(run_dir)
        if current_run["phases"]["before"]["status"] != "SEALED":
            before_report = run_smart_acceptance(
                target, output_dir=run_dir / "before", url=actual_url,
                business_context=business_context, viewports=matrix, locale=locale, theme=theme,
                allow_origins=allowed_origins, environment=environment, browser_name=browser, browser_executable=browser_executable, storage_state=storage_state, task_goal=task_goal, approved_requests=bound_approved_requests,
            )
            seal_before(run_dir)
        else:
            before_report_path = run_dir / "before" / "smart-acceptance-report.json"
            before_report = json.loads(before_report_path.read_text(encoding="utf-8")) if before_report_path.is_file() else None

        if after_url:
            stored_run = load_experience_run(run_dir)
            stored_conditions = dict(stored_run.get("conditions") or {})
            stored_target = dict(stored_run.get("target") or {})
            after_target, after_project, normalized_after_url = _target_identity(target, after_url)
            after_conditions = _conditions(
                target=after_target, project=after_project, url=normalized_after_url, viewports=viewports,
                locale=locale, theme=theme, browser=browser, allowed_origins=allowed_origins,
                approved_request_policy=bound_approved_requests,
                user_role=user_role, auth_state=auth_state, test_data_state=test_data_state,
                readiness_rule=readiness_rule, safe_task=safe_task, feature_flags=feature_flags,
            ).to_dict()
            condition_check = compare_conditions(stored_conditions, after_conditions, allowed_differences=("source_fingerprint",))
            target_match = digest_json(stored_target) == digest_json(after_target)
            if not target_match:
                raise ContractViolation("TARGET_IDENTITY_MISMATCH", ["$: actual After URL/project identity differs from sealed Before target"])
            if not condition_check["match"]:
                details = [f"$.conditions.{key}: Before={value['before']!r}, After={value['after']!r}" for key, value in condition_check["mismatches"].items()]
                raise ContractViolation("CONDITIONS_MISMATCH", details or ["$: After conditions differ from Before"])
            validate_after_binding(
                run_dir, task_id=task_id, session_id=session_id, mode=selected,
                target=stored_target, conditions=stored_conditions,
                baseline_digest=stored_run.get("baselineDigest"),
            )
            trusted_host_receipt = None
            trusted_v3_receipt = None
            legacy_receipt_used = False
            host_write_status = "NOT_APPLICABLE"
            trusted_tool_results = []
            tool_gate = {"schemaVersion": "1", "status": "NOT_APPLICABLE", "results": [], "passCount": 0, "failCount": 0, "notVerifiedCount": 0}
            prior_result: Mapping[str, Any] = {}
            if project is not None:
                plan_result_path = run_dir / "report" / "fix-plan-result.json"
                if not plan_result_path.is_file():
                    raise ContractViolation("HOST_WRITE_RECEIPT_BINDING_MISSING", ["$: persisted fix-plan-result.json is required before After verification"])
                try:
                    prior_result = json.loads(plan_result_path.read_text(encoding="utf-8"))
                except (OSError, UnicodeError, json.JSONDecodeError) as error:
                    raise ContractViolation("HOST_WRITE_RECEIPT_BINDING_MISSING", ["$: persisted fix plan is unreadable"]) from error
                binding = prior_result.get("hostReceiptBinding")
                if not isinstance(binding, Mapping):
                    raise ContractViolation("HOST_WRITE_RECEIPT_BINDING_MISSING", ["$: fix plan has no Host receipt binding"])
                if not isinstance(host_write_receipt, Mapping):
                    raise ContractViolation("HOST_WRITE_RECEIPT_REQUIRED", ["$: After verification requires the Host write receipt for this run"])
                if str(host_write_receipt.get("schemaVersion") or "") == "3":
                    v3_binding = load_public_v3_apply_binding(run_dir)
                    trusted_v3_receipt = verify_persisted_host_write_receipt_v3(
                        project, host_write_receipt, binding=v3_binding, hmac_key=host_receipt_hmac_key,
                    )
                    require_host_write_receipt_v3(trusted_v3_receipt)
                    host_write_status = "VERIFIED_V3"
                else:
                    # Legacy receipts remain readable for migration/history and can
                    # support failure diagnosis, but they can never upgrade a 4.2.3
                    # repair result to VERIFIED.
                    trusted_host_receipt = verify_host_write_receipt(
                        project, host_write_receipt,
                        task_id=task_id, session_id=session_id,
                        finding_ids=list(binding.get("findingIds") or []),
                        source_scope=list(binding.get("sourceScope") or []),
                        exclusions=list(binding.get("exclusions") or []),
                        run_id=str(binding.get("runId") or ""),
                        baseline=project_baseline or {},
                        plan_digest=str(binding.get("planDigest") or ""),
                        toolchain_digest=str(binding.get("toolchainDigest") or ""),
                        verification_context_digest=str(binding.get("verificationContextDigest") or ""),
                        scope_baseline=prior_result.get("scopeBaseline") if isinstance(prior_result.get("scopeBaseline"), Mapping) else None,
                    )
                    require_verified_host_write(trusted_host_receipt)
                    legacy_receipt_used = True
                    host_write_status = "LEGACY_HISTORY_ONLY"
                prior_tool_plans = [item for item in prior_result.get("projectToolPlans", []) if isinstance(item, Mapping)]
                trusted_tool_results = verify_host_tool_results(project, prior_tool_plans, host_tool_results) if prior_tool_plans else []
                for item in trusted_tool_results:
                    require_verified_host_tool_result(item)
                tool_gate = summarise_host_tool_results(trusted_tool_results)
            after_report = run_smart_acceptance(
                after_project or target, output_dir=run_dir / "after", url=normalized_after_url,
                business_context=business_context, viewports=matrix, locale=locale, theme=theme,
                allow_origins=allowed_origins, environment=environment, browser_name=browser, browser_executable=browser_executable, storage_state=storage_state, task_goal=task_goal, approved_requests=bound_approved_requests,
            )
            after_manifest = seal_after(run_dir)
            safe_task_match = stored_conditions.get("safe_task") == after_conditions.get("safe_task")
            gate = evaluate_improvement_claim(
                before_report, after_report,
                condition_match=bool(condition_check["match"]), target_match=target_match, safe_task_match=safe_task_match,
                browser_viewports=matrix,
            )
            comparison = {
                **gate,
                "baselineDigest": load_experience_run(run_dir).get("baselineDigest"),
                "conditionsDigest": stored_run.get("conditionsDigest"),
                "conditionComparison": condition_check,
                "sourceLineage": {
                    "baselineFingerprint": stored_conditions.get("source_fingerprint"),
                    "afterFingerprint": after_conditions.get("source_fingerprint"),
                    "changeExpected": True,
                },
                "beforeHealth": gate.get("beforeHealth") or (before_report or {}).get("pageHealth"),
                "afterHealth": gate.get("afterHealth") or after_report.get("pageHealth"),
                "observedBeforeHealth": (before_report or {}).get("pageHealth"),
                "observedAfterHealth": after_report.get("pageHealth"),
            }
            if trusted_v3_receipt is not None:
                verified_files = [str(row.get("canonicalPath")) for row in trusted_v3_receipt.to_dict().get("entries", []) if isinstance(row, Mapping)]
            elif trusted_host_receipt is not None:
                verified_files = [row["path"] for row in trusted_host_receipt.payload.get("files", [])]
            else:
                verified_files = list(files)
            baseline_drift = compare_project_baseline(project_baseline, project, target_files=verified_files) if isinstance(project_baseline, Mapping) and project is not None else None
            drift_gate = classify_post_repair_drift(baseline_drift, expected_write_paths=verified_files)
            quality_baseline = prior_result.get("scopeBaseline") if isinstance(prior_result.get("scopeBaseline"), Mapping) else project_baseline
            patch_quality = evaluate_patch_quality(project, quality_baseline, source_scope=verified_files) if isinstance(quality_baseline, Mapping) and project is not None and verified_files else None
            prior_risk_tier = prior_result.get("riskTier") if isinstance(prior_result.get("riskTier"), Mapping) else classify_risk_tier(request, source_scope=verified_files)
            prior_change_budget = prior_result.get("changeBudget") if isinstance(prior_result.get("changeBudget"), Mapping) else build_change_budget(request, risk_tier=str(prior_risk_tier.get("tier") or "T1"), explicit_files=list((prior_result.get("hostReceiptBinding") or {}).get("sourceScope", [])) if isinstance(prior_result.get("hostReceiptBinding"), Mapping) else verified_files)
            change_budget_gate = evaluate_change_budget(prior_change_budget, changed_files=verified_files)
            final_verification = combine_repair_verification(
                browser_outcome_status=gate["status"],
                project_tool_status=str(tool_gate.get("status") or "NOT_APPLICABLE"),
                patch_quality_status=str((patch_quality or {}).get("status") or "NOT_APPLICABLE"),
                project_drift_status=str(drift_gate.get("status") or "NOT_VERIFIED"),
                change_budget_status=str(change_budget_gate.get("status") or "NOT_VERIFIED"),
                host_write_status=host_write_status,
            )
            comparison = {**comparison, "repairVerification": final_verification}
            write_phase_file(run_dir, "compare", "comparison.json", json.dumps(comparison, ensure_ascii=False, indent=2, sort_keys=True))
            record_phase_artifact(run_dir, "compare", comparison)
            tool_lines = [f"{row.get('tool')}: {row.get('status')}" for row in tool_gate.get("results", [])]
            verification_lines = [
                f"Browser/Before-After: {gate['status']}",
                *(tool_lines or ["Project tools: NOT_APPLICABLE"]),
                *([f"Patch quality: {patch_quality.get('status')}"] if patch_quality else []),
                f"Change budget: {change_budget_gate.get('status')}",
                f"Project drift: {drift_gate.get('status')}",
                f"Overall repair verification: {final_verification['status']}",
            ]
            if final_verification["status"] == "VERIFIED":
                next_action = "修复已通过当前证据链验证；如需继续，可直接描述下一个问题。"
            elif final_verification["status"] == "FAIL":
                next_action = "先处理失败的类型检查/测试或 Browser 回归；可以选择“重试”当前验证、“缩小范围”后再试，或说“继续上次任务”，不要把当前结果当成已修复。"
            elif final_verification["status"] == "REVIEW_REQUIRED":
                next_action = "Browser 结果可用，但补丁存在质量风险；先审查技术债信号，再决定是否接受。"
            else:
                next_action = "当前证据不足以宣称修复完成；可以选择“重试”、 “缩小范围”或说“继续上次任务”补齐缺失证据后再验证。"
            repair_report = build_repair_report(
                request=request or "Verify the requested repair", status=final_verification["status"],
                reproduced=str((before_report or {}).get("deliveryConclusion") or "Before evidence recorded"),
                root_cause="Use the recorded finding/source mapping and decision ledger; no unsupported root cause is promoted.",
                changes=verified_files,
                verification=verification_lines,
                risks=[str(item) for item in final_verification.get("warnings", [])],
                unverified=[str(item) for item in final_verification.get("blockers", [])],
                resumable=True, run_id=run["runId"], authentication=auth_state,
                verification_summary={
                    "overall": final_verification["status"],
                    "browser": gate["status"],
                    "projectTools": str(tool_gate.get("status") or "NOT_APPLICABLE"),
                    "patchQuality": str((patch_quality or {}).get("status") or "NOT_APPLICABLE"),
                    "projectDrift": str(drift_gate.get("status") or "NOT_VERIFIED"),
                    "hostWrite": "HOST_WRITE_V3_VERIFIED" if trusted_v3_receipt is not None else "LEGACY_HISTORY_ONLY" if legacy_receipt_used else "NOT_APPLICABLE",
                },
                next_action=next_action,
            )
            result = {**common, "status": final_verification["status"], "before": before_report,
                      "scopeBaseline": prior_result.get("scopeBaseline") if isinstance(prior_result.get("scopeBaseline"), Mapping) else None,
                      "after": after_report, "afterManifest": after_manifest, "comparison": comparison,
                      "repairVerification": final_verification, "baselineDrift": baseline_drift, "projectDriftGate": drift_gate, "patchQuality": patch_quality,
                      "riskTier": prior_risk_tier, "changeBudget": prior_change_budget, "changeBudgetGate": change_budget_gate,
                      "hostWriteReceipt": trusted_v3_receipt.to_dict() if trusted_v3_receipt is not None else trusted_host_receipt.to_dict() if trusted_host_receipt is not None else None,
                      "hostWriteProtocol": "V3" if trusted_v3_receipt is not None else "LEGACY_HISTORY_ONLY" if legacy_receipt_used else "NONE",
                      "projectToolEvidence": [item.to_dict() for item in (trusted_tool_results if project is not None else [])],
                      "projectToolGate": tool_gate,
                      "repairReport": repair_report,
                      "revertPlan": build_v3_revert_plan(trusted_v3_receipt.to_dict()) if trusted_v3_receipt is not None else build_repair_scope_revert_plan(trusted_host_receipt) if trusted_host_receipt is not None else None,
                      "open": after_report.get("open")}
        else:
            if project is None:
                raise ContractViolation("PROJECT_ROOT_REQUIRED", ["$: focused source fix requires a local project"])
            evidence_path = run_dir / "before" / "smart-acceptance-report.json"
            evidence_report = before_report
            if evidence_report is None and evidence_path.is_file():
                evidence_report = json.loads(evidence_path.read_text(encoding="utf-8"))
            finding_ids: list[str] = []
            excluded_by_goal: list[dict[str, Any]] = []
            for item in (evidence_report or {}).get("topFindings", []):
                if not isinstance(item, Mapping):
                    continue
                decision = auto_fix_allowed(
                    goal_relevance=str(item.get("goalRelevance") or "UNRELATED"),
                    critical_safety=str(item.get("severity") or "").casefold() == "critical",
                )
                fid = str(item.get("findingId") or item.get("fingerprint") or item.get("ruleId") or item.get("id"))
                if decision["allowed"]:
                    finding_ids.append(fid)
                else:
                    excluded_by_goal.append({"findingId": fid, **decision})
            plan = prepare_fix_workflow(
                project, run_dir / "report", files=files,
                evidence=evidence_path if finding_ids else None,
                goal="修复当前任务已确认的最重要体验问题",
                request=request,
            )
            serial_plan = mutation_verification_plan([
                {"findingId": fid or f"scope-{index}", "filesChanged": 1, "layoutScope": "component", "risk": "MEDIUM"}
                for index, fid in enumerate(finding_ids or [None], start=1)
            ])
            finding_rows = [item for item in (evidence_report or {}).get("topFindings", []) if isinstance(item, Mapping)]
            systemic_scope = analyze_repair_scope(finding_rows)
            baseline_drift = compare_project_baseline(project_baseline, project, target_files=files) if isinstance(project_baseline, Mapping) else None
            patch_quality = evaluate_patch_quality(project, project_baseline, source_scope=files) if isinstance(project_baseline, Mapping) and list(files) else None
            plan_risk_tier = plan.get("riskTier") if isinstance(plan.get("riskTier"), Mapping) else classify_risk_tier(request, source_scope=[item.get("path") for item in plan.get("files", []) if isinstance(item, Mapping)], systemic=systemic_scope.get("repairScope") == "SYSTEMIC_ROOT_CAUSE")
            verification_risk = "HIGH" if str(plan_risk_tier.get("tier")) in {"T3", "T4"} or systemic_scope.get("repairScope") == "SYSTEMIC_ROOT_CAUSE" else "MEDIUM" if str(plan_risk_tier.get("tier")) in {"T1", "T2"} else "LOW"
            budget = select_verification_budget(
                risk=verification_risk,
                affected_surfaces=max(len(finding_rows), 1), changed_files=max(len(list(files)), 1),
                systemic=systemic_scope.get("repairScope") == "SYSTEMIC_ROOT_CAUSE",
            )
            tool_plans = []
            if plan.get("scopeConfirmed"):
                for tool in ((project_baseline or {}).get("metadata") or {}).get("localTools", []):
                    try:
                        defaults = {"tsc": ["--noEmit"], "vue-tsc": ["--noEmit"], "vitest": ["run"]}.get(str(tool), [])
                        tool_plans.append(plan_project_tool_execution(
                            project, str(tool), args=defaults,
                            run_id=str(run["runId"]), task_id=task_id, session_id=session_id,
                        ))
                    except ContractViolation:
                        continue
            source_scope = [item["path"] for item in plan["files"]]
            scope_baseline = build_scope_baseline(project, project_baseline or {}, source_scope=source_scope)
            toolchain_digest = digest_json(tool_plans)
            verification_context_digest = digest_json({
                "targetDigest": run.get("targetDigest"),
                "conditionsDigest": run.get("conditionsDigest"),
                "verificationBudget": budget,
                "sourceScope": source_scope,
            })
            binding_finding_ids = finding_ids or [f"scope-{index:04d}" for index, _ in enumerate(source_scope, start=1)]
            receipt_binding = {
                "runId": run["runId"],
                "taskId": task_id,
                "sessionId": session_id,
                "findingIds": binding_finding_ids,
                "sourceScope": source_scope,
                "exclusions": plan["willNotDo"],
                "baselineDigest": (project_baseline or {}).get("baselineDigest"),
                "planDigest": plan["planDigest"],
                "toolchainDigest": toolchain_digest,
                "verificationContextDigest": verification_context_digest,
                "scopeBaselineDigest": scope_baseline["scopeBaselineDigest"],
            }
            v3_apply_binding = None
            if host_patch_candidate is not None:
                v3_apply_binding = build_public_v3_apply_binding(
                    candidate=host_patch_candidate, run_id=str(run["runId"]), task_id=task_id, session_id=session_id,
                    baseline_digest=str((project_baseline or {}).get("baselineDigest") or ""), plan_digest=str(plan["planDigest"]),
                    source_scope=source_scope, exclusions=plan["willNotDo"], scope_baseline=scope_baseline,
                    change_budget=plan.get("changeBudget") if isinstance(plan.get("changeBudget"), Mapping) else None,
                )
                persist_public_v3_apply_binding(run_dir, v3_apply_binding)
            bridge = bridge_request(
                plan["hostBridgeAction"], task_id=task_id,
                payload={
                    **receipt_binding,
                    "mode": "NARROW_PROJECT_LOCAL_UI_EDIT",
                    "runtimeWriteAuthority": False,
                    "receiptContract": "host-write-receipt-v3.schema.json",
                    "legacyReceiptPolicy": "HISTORY_ONLY_CANNOT_VERIFY",
                    "patchCandidateRequiredBeforeApply": True,
                    "hostApplyBindingV3": v3_apply_binding,
                },
            )
            plan_budget_gate = plan.get("changeBudgetGate") if isinstance(plan.get("changeBudgetGate"), Mapping) else {"status": "NOT_VERIFIED", "blockers": ["CHANGE_BUDGET_MISSING"]}
            scope_confirmed = bool(plan.get("scopeConfirmed")) and str(plan_budget_gate.get("status")) == "PASS"
            repair_report = build_repair_report(
                request=request or "Repair the confirmed Web UI problem", status="NOT_VERIFIED",
                reproduced=str((before_report or {}).get("deliveryConclusion") or "Before evidence recorded"),
                root_cause=(f"Shared root cause candidate: {systemic_scope['systemicCandidates'][0]['rootSource']}"
                            if systemic_scope.get("systemicCandidates") else
                            "Root cause remains bounded to the confirmed finding/source scope" if scope_confirmed else
                            "Root cause/source ownership is not yet confirmed; no patch scope was inferred."),
                changes=[f"Patch candidate limited to {item['path']}" for item in plan.get("files", [])],
                verification=[f"Verification budget: {budget['profile']} / {budget['strategy']}",
                              "Project-owned tools require Host approval before execution"],
                risks=[row.get("code") for row in (patch_quality or {}).get("risks", [])],
                unverified=["No source write has occurred yet; Runtime cannot self-authorize writes"],
                resumable=True, run_id=run["runId"], authentication=auth_state,
                verification_summary={
                    "overall": "AWAITING_HOST_WRITE" if scope_confirmed else "SCOPE_NOT_CONFIRMED",
                    "browser": "BEFORE_RECORDED",
                    "projectTools": "HOST_RESULTS_REQUIRED" if tool_plans else "NOT_APPLICABLE",
                    "patchQuality": str((patch_quality or {}).get("status") or "NOT_APPLICABLE"),
                    "projectDrift": "NOT_APPLICABLE",
                    "hostWrite": "HOST_RECEIPT_REQUIRED" if scope_confirmed else "NOT_STARTED",
                },
                next_action=("审查 Patch Candidate；由 Host 应用后，把 Host write receipt 和列出的 project-tool result 带回同一 run 完成验证。"
                             if scope_confirmed else str(plan.get("nextAction") or "先补齐 Finding 到 Source 的映射；不要猜测修改文件。")),
            )
            result = {**common, "status": plan["status"], "before": before_report, "fixPlan": plan, "hostBridge": bridge,
                      "goalScope": {"eligibleFindingIds": finding_ids, "excluded": excluded_by_goal},
                      "systemicRepair": systemic_scope, "baselineDrift": baseline_drift, "patchQuality": patch_quality,
                      "riskTier": plan_risk_tier, "changeBudget": plan.get("changeBudget"), "changeBudgetGate": plan_budget_gate,
                      "projectToolPlans": tool_plans, "verificationBudget": budget, "repairReport": repair_report,
                      "scopeBaseline": scope_baseline, "hostReceiptBinding": receipt_binding,
                      "hostApplyBindingV3": v3_apply_binding,
                      "mutationVerificationPlan": serial_plan, "userConfirmationRequired": not scope_confirmed, "open": plan.get("open")}

    elif selected == "DEEP_REDESIGN":
        if project is None:
            raise ContractViolation("PROJECT_ROOT_REQUIRED", ["$: redesign requires a local project"])
        discovery = build_product_discovery(project, business_context=business_context)
        artifacts_map = export_product_discovery(discovery, run_dir / "before" / "system-understanding")
        seal_before(run_dir)
        bridge = bridge_request(
            "submitProductConfirmation", task_id=task_id,
            payload={"runId": run["runId"], "status": discovery.get("status"), "questions": discovery.get("questions"), "nextStage": "NEW_HOST_TASK_REQUIRED"},
        )
        result = {**common, "status": "PRODUCT_UNDERSTANDING_REVIEW_REQUIRED", "productDiscovery": discovery, "artifacts": artifacts_map, "hostBridge": bridge, "hardStop": True, "open": "before/system-understanding/index.html"}

    else:
        if _is_ui_inventory_request(request):
            inventory_dir = run_dir / "before" / "ui-inventory"
            inventory_viewport = next((vp for vp in reversed(matrix) if vp[0] >= 1200), (1440, 900))
            inventory = run_ui_inventory(
                actual_url, output_dir=inventory_dir, project_root=project, mode="full", max_pages=100,
                viewport=inventory_viewport, locale=locale, theme=theme, browser_name=browser,
                allow_origins=allowed_origins, storage_state=storage_state, browser_executable=browser_executable,
            )
            manifest = seal_before(run_dir)
            result = {
                **common, "status": inventory.get("status"), "auditType": "UI_ASSET_INVENTORY",
                "uiInventory": inventory, "baselineManifest": manifest,
                "open": "before/ui-inventory/ui-inventory.html",
            }
        else:
            if project is None:
                raise ContractViolation("PROJECT_ROOT_REQUIRED", ["$: specialist source audit requires a local project"])
            audit = audit_project(project, business_context=business_context, include_security=True)
            write_phase_file(run_dir, "before", "specialized-audit.json", json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True))
            manifest = seal_before(run_dir)
            result = {**common, "status": audit.get("status"), "audit": audit, "baselineManifest": manifest, "open": "before/specialized-audit.json"}

    # Product Evidence Foundation: build one bounded context plan and one public
    # TaskResult over the existing internal mode-specific result.  Neither object
    # grants authority or changes the Trust Kernel.
    if project is not None:
        context_scope: list[str] = [str(item) for item in files]
        fix_plan = result.get("fixPlan") if isinstance(result.get("fixPlan"), Mapping) else {}
        for row in fix_plan.get("files", []) if isinstance(fix_plan, Mapping) else []:
            if isinstance(row, Mapping) and row.get("path"):
                context_scope.append(str(row.get("path")))
        host_receipt_row = result.get("hostWriteReceipt") if isinstance(result.get("hostWriteReceipt"), Mapping) else {}
        for row in host_receipt_row.get("files", []) if isinstance(host_receipt_row, Mapping) else []:
            if isinstance(row, Mapping) and row.get("path"):
                context_scope.append(str(row.get("path")))
        evidence_for_context = result.get("before") if isinstance(result.get("before"), Mapping) else result.get("audit") if isinstance(result.get("audit"), Mapping) else {}
        result["contextPacket"] = build_relevant_context_packet(
            project,
            request=request or str(task_goal.get("goal") or ""),
            task_goal=task_goal,
            baseline=project_baseline,
            evidence=evidence_for_context if isinstance(evidence_for_context, Mapping) else {},
            explicit_source_scope=context_scope,
        )
    if selected == "FIX_AND_VERIFY" and after_url:
        execution.advance("HOST_APPLY", status="PASS" if host_write_status == "VERIFIED_V3" else "DEGRADED", input_ref="host-apply-binding-v3", output_ref="host-write-receipt", evidence_refs=["hostWriteReceipt"] if result.get("hostWriteReceipt") else [], failure_class=None if host_write_status == "VERIFIED_V3" else "DEGRADED_CONTINUE")
    else:
        execution.advance("HOST_APPLY", status="NOT_APPLICABLE" if selected != "FIX_AND_VERIFY" else "AWAITING_HOST", input_ref="bounded-work-plan", output_ref=None, failure_class=None if selected != "FIX_AND_VERIFY" else "USER_ACTION_REQUIRED")
    browser_requested = selected in {"CHECK", "FIX_AND_VERIFY"}
    browser_payload = result.get("after") if isinstance(result.get("after"), Mapping) else result.get("before") if isinstance(result.get("before"), Mapping) else None
    browser_runtime = browser_payload.get("runtime") if isinstance(browser_payload, Mapping) and isinstance(browser_payload.get("runtime"), Mapping) else {}
    browser_attempted = bool(browser_requested and isinstance(browser_payload, Mapping) and ("runtime" in browser_payload or "preflight" in browser_payload))
    browser_executed = bool(browser_attempted and list(browser_runtime.get("records") or []))
    comparison_status = str((result.get("comparison") or {}).get("status") or "") if isinstance(result.get("comparison"), Mapping) else ""
    browser_verified = comparison_status == "IMPROVEMENT_CLAIM_ALLOWED" or (selected == "CHECK" and str(result.get("status") or "").upper() in {"PASS", "COMPLETED"})
    browser_measured = browser_executed and str((browser_payload or {}).get("status") or "").upper() not in {"NOT_MEASURED", "NOT_RUN", "NOT_EXECUTED"}
    result["evidenceLifecycle"] = {"browser": evidence_state(requested=browser_requested, attempted=browser_attempted, executed=browser_executed, measured=browser_measured, verified=browser_verified if browser_measured else False)}
    result["browserExecutionStatus"] = browser_result_status(browser_executed=browser_executed, browser_measured=browser_measured, browser_verified=browser_verified if browser_measured else False)
    execution.advance("VERIFY", status=str(result.get("status") or "NOT_VERIFIED"), input_ref="evidence", output_ref="verification")
    result["evidenceGraph"] = build_evidence_graph(result)
    result["taskResult"] = build_task_result(result, request=request)
    result["userOutcome"] = user_outcome(result["taskResult"])
    execution.advance("REPORT", status=str(result["taskResult"].get("outcome") or result.get("status") or "NOT_VERIFIED"), input_ref="verification", output_ref="taskResult")
    result["executionState"] = {"stage": execution.stage, "history": list(execution.history or [])}

    _emit_phase1_shadow_artifact(
        run_dir, run_id=str(run["runId"]), task_id=task_id, session_id=session_id,
        request=request, selected_mode=selected, target_kind=str(target_identity.get("kind") or "unknown"),
        intent_route=routed, control_intent=control, fixed_result=result,
        task_goal=task_goal,
    )

    result_name = _result_name(selected, bool(after_url))
    try:
        write_phase_file(run_dir, "report", result_name, json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True, default=str))
        if not (selected == "FIX_AND_VERIFY" and not after_url):
            record_phase_artifact(run_dir, "report", {"result": result_name, "status": result.get("status")})
    except ContractViolation as error:
        # A previous phase-specific result is immutable; do not overwrite it.
        if error.code not in {"BEFORE_EVIDENCE_IMMUTABLE", "EXPERIENCE_PHASE_SEALED"}:
            raise

    checkpoint = create_checkpoint(
        run_dir, current_phase="final", task_goal=task_goal,
        active_capabilities=capability_routing["activeCapabilities"],
        findings=list((result.get("before") or {}).get("topFindings", []) if isinstance(result.get("before"), Mapping) else []),
        verified_writes=list((result.get("hostWriteReceipt") or {}).get("files", []) if isinstance(result.get("hostWriteReceipt"), Mapping) else []),
        claim_boundary="Evidence First; No Evidence, No PASS; Runtime cannot self-authorize writes.",
    )
    result["checkpoint"] = {k: checkpoint[k] for k in ("checkpointId", "sequence", "checkpointDigest", "createdAt", "writeAuthorization")}
    result["runHealth"] = build_run_health(run_dir, active_capabilities=capability_routing["activeCapabilities"])
    return result


__all__ = ["run_experience_fix"]
