"""Stable public TaskResult adapter and human rendering primitives.

TaskResult is a convergence layer over existing internal CHECK/REPAIR/
MODERNIZATION result shapes.  It does not replace the Trust Kernel and it does
not create a second execution model; it only exposes one bounded public result.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _strings(values: Any) -> list[str]:
    if isinstance(values, str):
        return [values] if values.strip() else []
    if not isinstance(values, Sequence) or isinstance(values, (bytes, bytearray)):
        return []
    result: list[str] = []
    for value in values:
        text = str(value).strip()
        if text and text not in result:
            result.append(text)
    return result


def _kind(result: Mapping[str, Any]) -> str:
    mode = str(result.get("mode") or "").upper()
    if mode == "FIX_AND_VERIFY" or isinstance(result.get("repairReport"), Mapping):
        return "REPAIR"
    if mode == "DEEP_REDESIGN":
        return "MODERNIZATION"
    return "INSPECTION"


def _raw_status(result: Mapping[str, Any]) -> str:
    verification = _mapping(result.get("repairVerification"))
    report = _mapping(result.get("repairReport"))
    return str(verification.get("status") or report.get("status") or result.get("status") or "NOT_VERIFIED").upper()


def _reason_code(result: Mapping[str, Any], kind: str) -> str:
    """Return one semantic reason for every renderer of the same TaskResult."""
    report = _mapping(result.get("repairReport"))
    for source in (result, report):
        for key in ("reasonCode", "reason_code"):
            value = str(source.get(key) or "").strip().upper()
            if value:
                return value

    raw = _raw_status(result)
    if raw == "VERIFIED":
        return "VERIFIED"
    if raw in {"AUTH_REQUIRED", "AWAITING_HOST_WRITE", "SCOPE_NOT_CONFIRMED", "REVIEW_REQUIRED"}:
        return "MANUAL_DECISION_REQUIRED"

    drift = _mapping(result.get("projectDriftGate"))
    if str(drift.get("status") or "").upper() in {"FAIL", "UNEXPECTED_DRIFT", "DRIFT"}:
        return "DRIFT_DETECTED"

    before = _mapping(result.get("before"))
    preflight = _mapping(before.get("preflight"))
    browser = _mapping(preflight.get("browser"))
    if browser.get("available") is False:
        return "BROWSER_UNAVAILABLE"

    blockers = _strings(preflight.get("blockers"))
    blocker_text = " ".join(blockers).casefold()
    if any(token in blocker_text for token in ("network", "网络", "offline", "离线")):
        return "NETWORK_BLOCKED"
    if any(token in blocker_text for token in ("depend", "依赖", "package", "module")):
        return "DEPENDENCY_MISSING"
    if any(token in blocker_text for token in ("browser", "浏览器", "navigation", "导航", "host policy")):
        return "ENV_BLOCKED"
    if blockers or str(_mapping(result.get("projectStartPlan")).get("status") or "").upper() in {"UNABLE_TO_START", "BLOCKED"}:
        return "INSUFFICIENT_EVIDENCE"

    if raw in {"NOT_VERIFIED", "NOT_VERIFIED_ENVIRONMENT", "PARTIAL", "INDETERMINATE", "POLICY_BLOCKED"}:
        return "ENV_BLOCKED" if raw in {"NOT_VERIFIED_ENVIRONMENT", "POLICY_BLOCKED"} else "INSUFFICIENT_EVIDENCE"
    if raw in {"FAIL", "FAILED", "BLOCKED", "REJECTED", "REGRESSED", "INVALID"}:
        return "FINDINGS_DETECTED" if kind == "INSPECTION" else "TASK_FAILED"
    return "MANUAL_DECISION_REQUIRED"


def _outcome(result: Mapping[str, Any], kind: str) -> str:
    raw = _raw_status(result)
    if raw == "VERIFIED":
        return "VERIFIED"
    if raw in {"REVIEW_REQUIRED", "PRODUCT_UNDERSTANDING_REVIEW_REQUIRED", "AWAITING_HOST_WRITE", "SCOPE_NOT_CONFIRMED"}:
        return "REVIEW_REQUIRED"
    if raw in {
        "NOT_VERIFIED", "NOT_VERIFIED_ENVIRONMENT", "PARTIAL", "INDETERMINATE", "POLICY_BLOCKED",
        "FRAMEWORK_NOT_SUPPORTED", "AUTH_REQUIRED", "RESTRICTED_RENDER", "DATA_NOT_READY",
    }:
        return "NOT_VERIFIED"
    if raw in {"FAIL", "FAILED", "BLOCKED", "REJECTED", "REGRESSED", "INVALID"}:
        # For inspection, a product finding/failing page is still a completed
        # observation task; execution did not necessarily fail.
        return "COMPLETED" if kind == "INSPECTION" else "FAILED"
    if kind == "REPAIR" and raw not in {"PASS", "COMPLETED"}:
        return "NOT_VERIFIED"
    return "COMPLETED"


def _coverage(result: Mapping[str, Any], kind: str) -> dict[str, Any]:
    baseline = _mapping(result.get("projectBaseline"))
    drift = _mapping(result.get("projectDriftGate"))
    scope_baseline = _mapping(result.get("scopeBaseline"))

    global_value = str(drift.get("globalCoverage") or "").upper()
    if global_value not in {"COMPLETE", "PARTIAL", "UNKNOWN", "NOT_APPLICABLE"}:
        completeness = str(baseline.get("completenessStatus") or "").upper()
        global_value = "COMPLETE" if completeness == "COMPLETE" else "PARTIAL" if completeness == "INDETERMINATE" else "UNKNOWN"

    target_status = str(_mapping(baseline.get("targetCoverage")).get("status") or "").upper()
    critical_status = str(_mapping(baseline.get("criticalContextCoverage")).get("status") or "").upper()
    if "targetCoverageComplete" in drift:
        target_status = "COMPLETE" if drift.get("targetCoverageComplete") else "PARTIAL"
    if "criticalContextCoverageComplete" in drift:
        critical_status = "COMPLETE" if drift.get("criticalContextCoverageComplete") else "PARTIAL"
    if not target_status:
        target_status = "COMPLETE" if scope_baseline.get("files") else "NOT_APPLICABLE" if kind != "REPAIR" else "UNKNOWN"
    if not critical_status:
        critical_status = str(_mapping(scope_baseline.get("criticalContextCoverage")).get("status") or "").upper() or ("NOT_APPLICABLE" if kind != "REPAIR" else "UNKNOWN")

    patch_scope = "NOT_APPLICABLE"
    if kind == "REPAIR":
        if target_status == "COMPLETE" and critical_status in {"COMPLETE", "NOT_APPLICABLE"}:
            patch_scope = "COMPLETE"
        elif target_status in {"PARTIAL", "INDETERMINATE"} or critical_status in {"PARTIAL", "INDETERMINATE"}:
            patch_scope = "PARTIAL"
        else:
            patch_scope = "UNKNOWN"

    return {
        "scope": "PATCH" if kind == "REPAIR" else "PROJECT_OBSERVATION",
        "patchScope": patch_scope,
        "globalProject": global_value,
        "target": target_status,
        "criticalContext": critical_status,
        "claimBoundary": (
            "PATCH coverage refers only to the exact sealed repair scope and critical context. "
            "PARTIAL global coverage never proves that unindexed repository files were unchanged."
            if kind == "REPAIR" else
            "Inspection coverage reports the bounded project/evidence surface observed by this execution; it is not a full-repository proof unless globalProject is COMPLETE."
        ),
    }


def _observations(result: Mapping[str, Any], report: Mapping[str, Any]) -> list[str]:
    rows: list[str] = []
    answers = _mapping(report.get("answers"))
    rows += _strings(answers.get("whatWasReproduced"))
    before = _mapping(result.get("before"))
    rows += _strings(before.get("deliveryConclusion"))
    for finding in list(before.get("topFindings") or [])[:5]:
        if isinstance(finding, Mapping):
            text = finding.get("summary") or finding.get("message") or finding.get("title") or finding.get("ruleId")
            if text:
                rows += _strings(str(text))
    if not rows and result.get("status"):
        rows.append(f"Runtime status: {result.get('status')}")
    return rows[:8]


def _hypotheses(result: Mapping[str, Any], report: Mapping[str, Any]) -> list[dict[str, Any]]:
    answers = _mapping(report.get("answers"))
    root = str(answers.get("rootCause") or "").strip()
    if not root:
        return []
    lowered = root.casefold()
    status = "NOT_VERIFIED" if any(token in lowered for token in ("unknown", "remain", "not yet", "unconfirmed", "未确认", "未知")) else "INFERRED"
    return [{"statement": root, "status": status, "evidenceRefs": []}]


def _verification(result: Mapping[str, Any], report: Mapping[str, Any]) -> dict[str, Any]:
    summary = dict(_mapping(report.get("verificationSummary")))
    if not summary:
        drift = _mapping(result.get("projectDriftGate"))
        summary = {
            "overall": _raw_status(result),
            "browser": _browser_surface_status(result),
            "projectTools": str(_mapping(result.get("projectToolGate")).get("status") or "NOT_APPLICABLE"),
            "patchQuality": str(_mapping(result.get("patchQuality")).get("status") or "NOT_APPLICABLE"),
            "projectDrift": str(drift.get("status") or "NOT_APPLICABLE"),
            "hostWrite": "HOST_WRITE_VERIFIED" if isinstance(result.get("hostWriteReceipt"), Mapping) else "NOT_APPLICABLE",
        }
    return {
        "overall": str(summary.get("overall") or _raw_status(result)),
        "browser": str(summary.get("browser") or "NOT_MEASURED"),
        "projectTools": str(summary.get("projectTools") or "NOT_APPLICABLE"),
        "patchQuality": str(summary.get("patchQuality") or "NOT_APPLICABLE"),
        "projectDrift": str(summary.get("projectDrift") or "NOT_APPLICABLE"),
        "hostWrite": str(summary.get("hostWrite") or "NOT_APPLICABLE"),
    }


def _browser_surface_status(result: Mapping[str, Any]) -> str:
    """Project the current Browser lifecycle without trusting a loose status field.

    ``experience_fix`` records the current run's lifecycle after the Browser
    payload has been produced.  A status such as ``BROWSER_PASS`` is therefore
    consumable only when that same result proves execution and measurement.  A
    missing lifecycle deliberately stays ``NOT_MEASURED`` so stale or copied
    Browser fields cannot promote an inspection result.
    """
    lifecycle = _mapping(_mapping(result.get("evidenceLifecycle")).get("browser"))
    if not lifecycle:
        return "NOT_MEASURED"
    if not bool(lifecycle.get("executed")) or not bool(lifecycle.get("measured")):
        return "NOT_MEASURED"
    reported = str(result.get("browserExecutionStatus") or "").upper()
    if reported == "BROWSER_PASS" and bool(lifecycle.get("verified")):
        return "BROWSER_PASS"
    return "BROWSER_NOT_VERIFIED"


def build_task_result(result: Mapping[str, Any], *, request: str | None = None) -> dict[str, Any]:
    """Adapt any public run result into the versioned TaskResult contract."""
    kind = _kind(result)
    report = _mapping(result.get("repairReport"))
    answers = _mapping(report.get("answers"))
    task_goal = _mapping(result.get("taskGoal"))
    raw_status = _raw_status(result)
    outcome = _outcome(result, kind)
    reason_code = _reason_code(result, kind)
    coverage = _coverage(result, kind)
    request_text = str(request or report.get("request") or answers.get("whatYouAsked") or task_goal.get("goal") or "Task request unavailable")
    changes = _strings(answers.get("whatChanged"))
    if kind != "REPAIR" and not changes:
        changes = []
    uncertainties = _strings(answers.get("remainingRiskOrUnknown"))
    verification = _verification(result, report)
    repair_verification = _mapping(result.get("repairVerification"))
    uncertainties += _strings(repair_verification.get("blockers"))
    uncertainties += _strings(repair_verification.get("warnings"))
    change_budget_gate = _mapping(result.get("changeBudgetGate"))
    uncertainties += _strings(change_budget_gate.get("blockers"))
    evidence_graph = _mapping(result.get("evidenceGraph"))
    if evidence_graph.get("requiredMissing"):
        uncertainties.append("EVIDENCE_GRAPH_INCOMPLETE:" + ",".join(_strings(evidence_graph.get("requiredMissing"))))

    claims: list[dict[str, Any]] = []
    if outcome == "VERIFIED":
        claims.append({
            "claim": "Requested repair is verified within the declared coverage.",
            "status": "VERIFIED",
            "evidenceRefs": ["verification", "evidenceGraph:repair-verification"],
        })
    elif kind == "INSPECTION" and outcome == "COMPLETED":
        claims.append({
            "claim": "Inspection completed for the bounded observed surface; findings are not a whole-repository proof.",
            "status": "OBSERVED",
            "evidenceRefs": ["observations", "evidenceGraph:before"],
        })
    else:
        claims.append({
            "claim": "No broader success claim is made beyond the recorded outcome and coverage.",
            "status": "NOT_VERIFIED" if outcome in {"NOT_VERIFIED", "REVIEW_REQUIRED"} else "OBSERVED",
            "evidenceRefs": [],
        })

    execution_id = str(result.get("runId") or _mapping(report.get("taskState")).get("runId") or "unknown-execution")
    task_id = str(result.get("taskId") or "unknown-task")
    protected = _strings(task_goal.get("nonGoals"))
    resumable = bool(_mapping(report.get("taskState")).get("resumable", result.get("checkpoint") is not None))
    browser_status = str(verification.get("browser") or "").upper()
    before_report = _mapping(result.get("before"))
    before_preflight = _mapping(before_report.get("preflight"))
    before_browser = _mapping(before_preflight.get("browser"))
    before_findings = [row for row in list(_mapping(result.get("before")).get("topFindings") or []) if isinstance(row, Mapping)]
    if report.get("nextAction"):
        next_action = str(report.get("nextAction"))
    elif kind == "INSPECTION" and before_preflight.get("authRequired"):
        next_action = "请在目标浏览器中完成登录；登录后继续当前任务，系统会管理验证所需状态，不需要你手工编辑工程文件。"
    elif kind == "INSPECTION" and before_browser.get("available") is False:
        next_action = "源码检查已完成，但真实浏览器验证未完成；恢复可用 Browser 后可以重试或继续当前任务。"
    elif kind == "INSPECTION" and browser_status in {"NOT_MEASURED", "NOT_VERIFIED", "NOT_VERIFIED_ENVIRONMENT", "POLICY_BLOCKED"} and not before_findings:
        next_action = "提供可访问的页面 --url（或先启动本地应用）以复现 UI/交互问题；获得运行证据前不建议修改源码。"
    elif kind == "INSPECTION":
        next_action = "可以基于已记录 Finding 继续修复；若问题依赖真实页面状态，请先补充可访问 URL。"
    else:
        next_action = "审查验证范围和剩余未知项后决定下一步。"

    revert_plan = _mapping(result.get("revertPlan"))
    review = {
        "available": bool(revert_plan),
        "revertScope": str(revert_plan.get("scope")) if revert_plan else None,
        "revertPlanDigest": str(revert_plan.get("planDigest")) if revert_plan else None,
        "hostExecutionRequired": bool(revert_plan.get("hostExecutionRequired")) if revert_plan else False,
        "claimBoundary": str(revert_plan.get("claimBoundary")) if revert_plan else "No repair-scope revert plan is available for this task result.",
    }

    value = {
        "schemaVersion": "1",
        "taskId": task_id,
        "executionId": execution_id,
        "kind": kind,
        "request": request_text,
        "protectedScope": protected,
        "executionStatus": "COMPLETED",
        "outcome": outcome,
        "subjectStatus": raw_status,
        "reasonCode": reason_code,
        "coverage": coverage,
        "observations": _observations(result, report),
        "hypotheses": _hypotheses(result, report),
        "changes": changes,
        "verification": verification,
        "claims": claims,
        "uncertainties": list(dict.fromkeys(uncertainties)),
        "nextAction": next_action,
        "taskState": {
            "resumable": resumable,
            "resumeHint": "继续上次任务" if resumable else None,
        },
        "review": review,
        "claimBoundary": (
            "TaskResult separates execution completion, task outcome, and verification coverage. "
            "VERIFIED never implies whole-repository verification when globalProject is PARTIAL or UNKNOWN."
        ),
        # Beta.2 compatibility aliases.  New consumers should use outcome and the
        # structured TaskResult fields above.
        "repairStatus": raw_status if kind == "REPAIR" else None,
        "repairReport": dict(report) if report else None,
    }
    return value


def human_status_label(kind: str) -> str:
    return {"REPAIR": "Repair", "INSPECTION": "Inspection", "MODERNIZATION": "Modernization"}.get(kind, "Task")


def human_status_explanation(code: str) -> str:
    mapping = {
        "ENV_BLOCKED": "当前环境或宿主策略阻止了所需验证，因此没有宣称成功。",
        "DEPENDENCY_MISSING": "所需依赖尚未就绪，因此没有宣称成功。",
        "BROWSER_UNAVAILABLE": "当前没有可用的 Browser 证据，因此没有宣称成功。",
        "NETWORK_BLOCKED": "当前网络条件阻止了所需操作，因此没有宣称成功。",
        "INSUFFICIENT_EVIDENCE": "现有证据不足以证明任务成功。",
        "MANUAL_DECISION_REQUIRED": "这一步需要当前用户或宿主明确决定，系统没有替你越权。",
        "DRIFT_DETECTED": "发现计划范围外的变化，本次任务不会被标记为 VERIFIED。",
        "FINDINGS_DETECTED": "检查发现了需要处理的问题；发现本身不等于修复完成。",
        "TASK_FAILED": "任务存在确定失败条件，不能声明成功。",
        "NOT_VERIFIED_ENVIRONMENT": "当前环境无法完成所需验证，因此没有宣称成功。",
        "POLICY_BLOCKED": "当前 Host 策略阻止了所需观察；源码不会因此被当作问题修改。",
        "FRAMEWORK_NOT_SUPPORTED": "当前生产生成路径不支持该框架；只读探索结果不能升级为生产 PASS。",
        "UNEXPECTED_DRIFT": "发现计划范围外的项目变化，本次任务不会被标记为 VERIFIED。",
        "REVIEW_REQUIRED": "已有足够证据继续，但存在需要人工确认的风险或选择。",
        "NOT_VERIFIED": "现有证据不足以证明任务成功。",
        "VERIFIED": "任务在下方声明的验证范围内已被验证。",
        "COMPLETED": "任务已完成；该状态不自动表示产品本身无问题。",
        "FAILED": "任务存在确定失败条件，不能声明成功。",
    }
    return mapping.get(str(code or "").upper(), "请结合验证范围和证据摘要理解该状态。")


__all__ = ["build_task_result", "human_status_label", "human_status_explanation"]
