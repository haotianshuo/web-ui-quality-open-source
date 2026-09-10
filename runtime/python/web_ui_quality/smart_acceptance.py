"""v2.3 P0-A smart acceptance orchestration.

This module intentionally implements the v2.3 execution order only through the
P0-A gate.  Later capabilities are reported as NOT_EXECUTED or NOT_APPLICABLE;
they are never implied by a successful runtime check.
"""
from __future__ import annotations

import contextlib
import functools
import json
import threading
from datetime import datetime, timezone
from html import escape
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Sequence
from urllib.parse import urlsplit

from .acceptance_findings import normalize_findings, top_findings
from .task_goal import bind_findings_to_goal
from .business_context import build_context_v2
from .contracts import ContractViolation, digest_json, load_json
from .error_classifier import classify_record
from .user_language import status_label
from .journey import JourneyPolicy, execute_journey, validate_journey
from .playwright_adapter import _context_options, _normalize_viewports, _origin, _safe_url, playwright_capability
from .quick_ui import QUICK_UI_VIEWPORTS, run_quick_ui
from .release_info import PACKAGE_VERSION
from .repair_recipe import build_repair_recipes
from .condition_registry import STANDARD_VIEWPORTS
from .mutation_firewall import BrowserMutationFirewall
from .secure_browser_context import build_credential_map, create_secure_context, split_headers
from .reversible_probe import run_reversible_probe
from .page_health import evaluate_page_health
from .browser_locator import resolve_browser_executable

_DEFAULT_VIEWPORTS: tuple[tuple[int, int], ...] = STANDARD_VIEWPORTS
_CRITICAL_RESOURCE_TYPES = {"document", "script", "stylesheet", "xhr", "fetch", "font"}


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:  # pragma: no cover - noise suppression
        return


@contextlib.contextmanager
def _resolved_target(target: str | Path, *, explicit_url: str | None = None) -> Iterator[dict[str, Any]]:
    raw = str(target)
    parsed = urlsplit(raw)
    if parsed.scheme in {"http", "https"} and parsed.hostname:
        yield {"url": _safe_url(raw, "target"), "projectRoot": None, "source": "url"}
        return
    project = Path(raw).expanduser().resolve()
    if not project.exists() or not project.is_dir():
        raise ContractViolation("SMART_ACCEPTANCE_TARGET_INVALID", ["$: target must be a URL or existing project directory"])
    if explicit_url:
        yield {"url": _safe_url(explicit_url, "url"), "projectRoot": project, "source": "project+url"}
        return
    index = project / "index.html"
    if not index.is_file():
        yield {"url": None, "projectRoot": project, "source": "project-only"}
        return
    handler = functools.partial(_QuietHandler, directory=str(project))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = int(server.server_address[1])
        yield {"url": f"http://localhost:{port}/", "projectRoot": project, "source": "local-static-project"}
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def _environment(url: str | None, explicit: str | None) -> dict[str, str]:
    if explicit:
        value = explicit.strip().lower()
        if value not in {"local", "test", "staging", "production", "unknown"}:
            raise ContractViolation("SMART_ACCEPTANCE_ENVIRONMENT_INVALID", ["$.environment: unsupported"])
        return {"observed": value, "effectivePolicy": "production" if value == "unknown" else value}
    if not url:
        return {"observed": "unknown", "effectivePolicy": "production"}
    host = (urlsplit(url).hostname or "").lower()
    if host in {"localhost", "127.0.0.1", "0.0.0.0", "::1"} or host.endswith(".local"):
        observed = "local"
    elif any(token in host for token in ("staging", "stage", "preview")):
        observed = "staging"
    elif any(token in host for token in ("test", "dev", "sandbox")):
        observed = "test"
    else:
        observed = "unknown"
    return {"observed": observed, "effectivePolicy": "production" if observed == "unknown" else observed}


def _project_coverage(project_root: Path | None) -> dict[str, Any]:
    if project_root is None:
        return {"status": "NOT_APPLICABLE", "discovered": [], "limitations": ["No local source tree was supplied."]}
    discovered: list[dict[str, Any]] = []
    excluded = {"node_modules", ".git", "dist", "build", ".next", "coverage", "reference-output", "__pycache__"}
    for path in project_root.rglob("*"):
        if not path.is_file() or any(part in excluded for part in path.relative_to(project_root).parts):
            continue
        rel = path.relative_to(project_root).as_posix()
        lower = rel.lower()
        kind = None
        if lower.endswith((".html", ".htm")):
            kind = "page"
        elif "/pages/" in f"/{lower}" or "/app/" in f"/{lower}":
            if lower.endswith((".tsx", ".jsx", ".vue", ".svelte", ".js", ".ts")):
                kind = "route-source"
        elif Path(rel).name in {"routes.ts", "routes.js", "router.ts", "router.js"}:
            kind = "route-config"
        if kind:
            discovered.append({"identity": rel, "kind": kind, "state": "DISCOVERED"})
        if len(discovered) >= 200:
            break
    return {
        "status": "AVAILABLE",
        "discovered": discovered,
        "limitations": ["Static discovery does not prove that a page or route was executed."],
    }


def _preflight(quick_report: Mapping[str, Any] | None, *, url: str | None, environment: Mapping[str, str], browser_executable: str | Path | None = None) -> dict[str, Any]:
    capability = playwright_capability(browser_executable)
    if not url:
        return {
            "status": "NOT_VERIFIED", "canContinue": False, "browser": capability,
            "environment": dict(environment), "interactionPolicy": "A0_ONLY",
            "blockers": ["No runnable URL was supplied or safely derived from the project."],
            "warnings": [], "authRequired": False,
            "plainSummary": "已读取项目源码，但没有可安全运行的页面地址；运行时旅程暂时无法确认。",
        }
    if not capability.get("available"):
        return {
            "status": "NOT_VERIFIED", "canContinue": False, "browser": capability,
            "environment": dict(environment), "interactionPolicy": "A0_ONLY",
            "blockers": ["Playwright/Chromium is unavailable."], "warnings": [], "authRequired": False,
            "plainSummary": "当前缺少可用 Browser；源码范围可以读取，但页面操作暂时无法确认。",
        }
    records = list((quick_report or {}).get("records") or [])
    blockers: list[str] = []
    warnings: list[str] = []
    auth_required = False
    for record in records:
        label = str(record.get("label") or "viewport")
        if record.get("status") == "FAIL":
            classified = record.get("failureClassification") or classify_record(record)
            if classified:
                blockers.append(f"{label}: {classified.get('userMessage')}")
                warnings.extend(str(item) for item in classified.get("recoveryActions", []))
            else:
                blockers.append(f"{label}: page did not produce a valid HTTP/render result")
        if record.get("validRender") is False:
            blockers.append(f"{label}: page did not produce representative rendered content")
        critical_blocked = list(record.get("criticalBlockedRequests") or [])
        if critical_blocked:
            origins = sorted({str(item.get("origin")) for item in critical_blocked if item.get("origin")})
            blockers.append(f"{label}: tool blocked critical resources from {', '.join(origins[:5])}")
        if record.get("evidenceStatus") == "NOT_VERIFIED" and not critical_blocked:
            warnings.append(f"{label}: page readiness did not become stable within the bounded window")
        if record.get("pageErrors"):
            warnings.append(f"{label}: page emitted {len(record.get('pageErrors') or [])} runtime error(s)")
        if (record.get("metrics") or {}).get("authWallHint"):
            auth_required = True
    effective = environment.get("effectivePolicy")
    policy = "A0_A1" if effective in {"local", "test", "staging"} else "A0_ONLY"
    if blockers:
        status = "BLOCKED"
        summary = "当前页面不能代表真实产品，已停止关键旅程；请先处理运行环境或允许必要资源。"
    elif auth_required:
        status = "PARTIAL"
        summary = "公开或登录页面已完成基础检查；受保护区域需要任务专属登录后才能继续。"
    else:
        status = "READY"
        summary = "页面可以开始检查；本次只执行当前环境允许的只读或本地 UI 状态操作。"
    return {
        "status": status, "canContinue": not blockers, "browser": capability,
        "environment": dict(environment), "interactionPolicy": policy,
        "blockers": blockers, "warnings": warnings, "authRequired": auth_required,
        "plainSummary": summary,
    }


def _auto_safe_steps(page: Any) -> list[dict[str, Any]]:
    candidate = page.evaluate(
        r"""
        () => {
          const visible = (el) => { const r=el.getBoundingClientRect(); const s=getComputedStyle(el); return r.width>0&&r.height>0&&s.display!=='none'&&s.visibility!=='hidden'; };
          const name = (el) => (el.getAttribute('aria-label') || el.innerText || el.textContent || '').replace(/\s+/g,' ').trim();
          const tab = Array.from(document.querySelectorAll('[role=tab][aria-selected=false]')).find(el => visible(el) && name(el));
          if (tab) return {kind:'tab', name:name(tab)};
          const expandable = Array.from(document.querySelectorAll('button[aria-expanded=false],[role=button][aria-expanded=false]')).find(el => visible(el) && name(el));
          if (expandable) return {kind:'expandable', name:name(expandable), role:expandable.getAttribute('role') || 'button'};
          const summary = Array.from(document.querySelectorAll('details:not([open]) > summary')).find(visible);
          if (summary) return {kind:'details'};
          return null;
        }
        """
    )
    if not candidate:
        return []
    if candidate["kind"] == "tab":
        return [{
            "id": "auto-tab", "action": "click", "risk": "ui-state", "role": "tab", "name": candidate["name"],
            "outcome": {"description": "切换标签后页面状态应改变", "signals": [{"kind": "state_changed", "evidenceRole": "user_visible"}], "minimumSatisfied": 1},
        }]
    if candidate["kind"] == "expandable":
        return [{
            "id": "auto-expand", "action": "click", "risk": "ui-state", "role": candidate.get("role", "button"), "name": candidate["name"],
            "outcome": {"description": "展开控件后 aria-expanded 应变为 true", "signals": [{
                "kind": "attribute_equals", "evidenceRole": "independent", "role": candidate.get("role", "button"), "name": candidate["name"], "attribute": "aria-expanded", "value": "true",
            }], "minimumSatisfied": 1},
        }]
    return [{
        "id": "auto-details", "action": "click", "risk": "ui-state", "selector": "details:not([open]) > summary", "nth": 0,
        "outcome": {"description": "展开详情后页面状态应改变", "signals": [{"kind": "state_changed", "evidenceRole": "user_visible"}], "minimumSatisfied": 1},
    }]


def _run_journey_matrix(
    url: str,
    *,
    output_dir: Path,
    viewports: Sequence[Sequence[int]],
    locale: str,
    theme: str,
    allow_origins: Iterable[str],
    browser_name: str,
    steps: Sequence[Mapping[str, Any]] | None,
    environment: Mapping[str, str],
    storage_state: str | Path | Mapping[str, Any] | None,
    extra_http_headers: Mapping[str, str] | None,
    ignore_https_errors: bool,
    browser_executable: str | Path | None,
    approved_requests: Sequence[Mapping[str, str]] = (),
) -> dict[str, Any]:
    if environment.get("effectivePolicy") == "production" and steps is None:
        return {"status": "NOT_EXECUTED", "reason": "Automatic A1 interaction is disabled in production/unknown environments.", "runs": [], "journey": []}
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"status": "NOT_VERIFIED", "reason": "Playwright unavailable", "runs": [], "journey": []}
    origins = {_origin(url)}
    for value in allow_origins:
        origins.add(_origin(_safe_url(str(value), "allowOrigins")))
    matrix = _normalize_viewports(viewports)
    all_runs: list[dict[str, Any]] = []
    selected_steps: list[dict[str, Any]] | None = None
    with sync_playwright() as runtime:
        browser_type = getattr(runtime, browser_name, None)
        if browser_type is None:
            return {"status": "NOT_VERIFIED", "reason": "Unsupported browser engine", "runs": [], "journey": []}
        launch_options: dict[str, Any] = {"headless": True}
        decision = resolve_browser_executable(browser_name, explicit=browser_executable)
        if not decision.get("available") and browser_executable is None:
            decision = resolve_browser_executable(browser_name, playwright_browser_type=browser_type)
        if not decision.get("available"):
            return {"status": "NOT_VERIFIED", "reason": decision.get("reason") or "Browser executable unavailable", "runs": [], "journey": []}
        launch_options["executable_path"] = decision["executable"]
        browser = browser_type.launch(**launch_options)
        try:
            for width, height in matrix:
                viewport_id = f"{width}x{height}"
                safe_headers, credential_map = build_credential_map(
                    target_origin=_origin(url), all_primary_origins=(_origin(url),), headers=extra_http_headers
                )
                audit = create_secure_context(
                    browser,
                    context_options=_context_options(
                        viewport=(width, height), locale=locale, theme=theme, storage_state=storage_state,
                        extra_http_headers=safe_headers, ignore_https_errors=ignore_https_errors,
                    ),
                    allowed_origins=origins, credential_headers_by_origin=credential_map, approved_requests=approved_requests,
                    approved_routes={url},
                    authenticated=bool(storage_state is not None or credential_map),
                    allow_websocket=any(str(row.get("method") or "").upper()=="WEBSOCKET" for row in approved_requests),
                )
                context = audit.context
                blocked = audit.blocked_requests
                firewall = audit.firewall
                page = context.new_page()
                try:
                    response = page.goto(url, wait_until="domcontentloaded", timeout=15_000)
                    if response is None or not 200 <= response.status < 300:
                        all_runs.append({"viewport": viewport_id, "status": "NOT_VERIFIED", "reason": "Invalid page response", "steps": []})
                        continue
                    page.wait_for_timeout(350)
                    viewport_out = output_dir / "journeys" / viewport_id
                    viewport_out.mkdir(parents=True, exist_ok=True)
                    critical = [item for item in blocked if item.get("resourceType") in _CRITICAL_RESOURCE_TYPES and item.get("code") == "ORIGIN_NOT_APPROVED"]
                    if critical:
                        all_runs.append({"viewport": viewport_id, "status": "NOT_VERIFIED", "reason": "Critical resources were blocked by the tool.", "blocked": critical, "steps": []})
                        continue
                    if steps is None:
                        probe = run_reversible_probe(page, firewall)
                        run_status = str(probe.get("status"))
                        step_results = [{"id": "auto-reversible-probe", "status": run_status, "outcomeProof": probe, "risk": "ui-state"}]
                        proof_count = 1 if run_status == "PASS_RESTORED" else 0
                        selected_steps = [{"id": "auto-reversible-probe", "action": "click", "risk": "ui-state", "reversible": True}]
                    else:
                        if selected_steps is None:
                            allowed_risks = frozenset({"read-only"}) if environment.get("effectivePolicy") == "production" else frozenset({"read-only", "ui-state"})
                            selected_steps = validate_journey(list(steps), JourneyPolicy(allowed_risks=allowed_risks))
                        step_results = execute_journey(page, selected_steps, output_dir=viewport_out)
                        proof_count = sum(1 for row in step_results if row.get("outcomeProof"))
                        if firewall.mutation_attempted:
                            run_status = "BLOCKED_MUTATION_ATTEMPT"
                        elif any(row.get("status") == "FAIL" for row in step_results):
                            run_status = "FAIL"
                        elif any(row.get("status") == "NOT_VERIFIED" for row in step_results) or proof_count == 0:
                            run_status = "NOT_VERIFIED"
                        else:
                            run_status = "PASS"
                    final_shot = viewport_out / "journey-final.png"
                    final_shot.parent.mkdir(parents=True, exist_ok=True)
                    page.screenshot(path=str(final_shot), full_page=False, animations="disabled")
                    all_runs.append({
                        "viewport": viewport_id, "status": run_status, "steps": step_results,
                        "outcomeProofCount": proof_count,
                        "mutationFirewall": {"status": "BLOCKED_MUTATION_ATTEMPT" if firewall.mutation_attempted or firewall.network_escape_attempted else "PASS", "decisions": firewall.decisions},
                        "networkPolicy": audit.report(),
                        "finalScreenshotRef": str(final_shot.relative_to(output_dir)).replace("\\", "/"),
                    })
                except Exception as error:
                    all_runs.append({"viewport": viewport_id, "status": "NOT_VERIFIED", "reason": f"{type(error).__name__}: {str(error)[:400]}", "steps": []})
                finally:
                    context.close()
        finally:
            browser.close()
    if any(row["status"] in {"FAIL", "FAIL_NOT_RESTORED", "FAIL_NO_STATE_CHANGE", "BLOCKED_MUTATION_ATTEMPT"} for row in all_runs):
        status = "FAIL"
    elif all_runs and all(row["status"] in {"PASS", "PASS_RESTORED"} for row in all_runs):
        status = "PASS_RESTORED" if any(row["status"] == "PASS_RESTORED" for row in all_runs) else "PASS"
    elif any(row["status"] in {"NOT_VERIFIED", "NOT_VERIFIED_NO_SAFE_TARGET"} for row in all_runs):
        status = "NOT_VERIFIED"
    else:
        status = "NOT_EXECUTED"
    return {"status": status, "runs": all_runs, "journey": selected_steps or [], "journeyId": "primary-journey" if selected_steps else None}


def _viewport_class(value: str) -> str:
    try:
        width = int(value.split("x", 1)[0])
    except Exception:
        return "unknown"
    return "mobile" if width <= 480 else "small-desktop" if width < 1200 else "desktop"


def _finding_candidates(
    *,
    url: str | None,
    quick_report: Mapping[str, Any] | None,
    journey_report: Mapping[str, Any],
    preflight: Mapping[str, Any],
) -> list[dict[str, Any]]:
    target = (url or "project").split("?", 1)[0]
    route = urlsplit(url).path if url else "/"
    candidates: list[dict[str, Any]] = []
    for item in (quick_report or {}).get("topIssues", []):
        issue_id = str(item.get("id") or "VISUAL")
        result_label = str(item.get("userLabel") or "用起来别扭")
        runtime_boundary = result_label == "暂时无法确认"
        blocking = not runtime_boundary and (result_label == "现在会出错" or issue_id in {"UI-FIXED-OCCLUSION", "UI-ELEMENT-OVERLAP", "UI-DIALOG-FIT", "UI-NAV-OVERFLOW", "UI-HTTP-FAILURE", "HTTP_SERVER_ERROR"})
        candidates.append({
            "targetIdentity": target, "routeTemplate": route or "/",
            "issueType": "RUNTIME_HEALTH" if runtime_boundary else "RESPONSIVE_BLOCK" if blocking else "VISUAL_FRICTION",
            "semanticTarget": str((item.get("samples") or [{}])[0].get("evidence", {}).get("selector") or item.get("title") or "page layout"),
            "state": "default", "viewportClass": _viewport_class(str((item.get("viewports") or ["unknown"])[0])),
            "expectedOutcomeKey": "content_and_actions_remain_usable",
            "observedOutcomeKey": issue_id.lower().replace("-", "_"),
            "expectedOutcomeSummary": "关键内容和操作在目标尺寸下应保持可读、可达、可命中。",
            "observedOutcomeSummary": str(item.get("title")),
            "evidenceKinds": ["runtime"] if runtime_boundary else ["geometry", "screenshot"],
            "evidenceRefs": [str(record.get("screenshotRef")) for record in (quick_report or {}).get("records", []) if f"{(record.get('viewport') or {}).get('width')}x{(record.get('viewport') or {}).get('height')}" in set(item.get("viewports") or []) and record.get("screenshotRef")] or [f"quick-ui-report.json#{issue_id}"],
            "ruleId": issue_id, "ruleVersion": "2.3-p0a",
            "verificationState": "NOT_VERIFIED" if runtime_boundary else "VERIFIED",
            "resultLabel": result_label if result_label in {"现在会出错", "用起来别扭", "建议考虑补充", "暂时无法确认"} else "用起来别扭",
            "severity": "medium" if runtime_boundary else "high" if blocking else "medium",
            "summary": str(item.get("title") or "页面存在明显体验问题"),
            "impact": "当前证据不足以判断页面本身；不应因此修改源码。" if runtime_boundary else "关键内容或操作可能被遮挡或无法完成。" if blocking else "用户仍可操作，但理解和操作成本明显增加。",
            "recommendation": str(item.get("recommendation") or "在原设计系统内做最小修复并按相同条件复验。"),
        })
    for run in journey_report.get("runs", []):
        for step in run.get("steps", []):
            proof = step.get("outcomeProof") or {}
            if step.get("status") == "FAIL" and proof:
                signals = list(proof.get("signals") or [])
                visible_pass = any(sig.get("evidenceRole") == "user_visible" and sig.get("passed") for sig in signals)
                independent_fail = any(sig.get("evidenceRole") in {"independent", "persistence"} and not sig.get("passed") for sig in signals)
                issue_type = "FALSE_SUCCESS" if visible_pass and independent_fail else "NO_RESPONSE" if any(sig.get("kind") == "state_changed" for sig in signals) else "RESULT_MISMATCH"
                candidates.append({
                    "targetIdentity": target, "routeTemplate": route or "/", "journeyId": "primary-journey", "stepId": step.get("id"),
                    "issueType": issue_type, "semanticTarget": str(step.get("locator") or step.get("step") or "primary action"),
                    "state": "after-action", "viewportClass": _viewport_class(str(run.get("viewport"))),
                    "expectedOutcomeKey": str(proof.get("description") or "promised_outcome"),
                    "observedOutcomeKey": "outcome_not_proved",
                    "expectedOutcomeSummary": str(proof.get("description") or "操作应产生承诺结果"),
                    "observedOutcomeSummary": "操作已执行，但所需结果信号没有达到。",
                    "evidenceKinds": ["interaction", "state", "request"],
                    "evidenceRefs": [f"journeys/{run.get('viewport')}#{step.get('id')}"],
                    "ruleId": f"OUTCOME-{issue_type}", "ruleVersion": "2.3-p0a",
                    "verificationState": "VERIFIED", "resultLabel": "现在会出错", "severity": "high",
                    "summary": "操作后的真实结果没有达到产品承诺。",
                    "impact": "用户可能以为操作已生效，实际任务没有完成。",
                    "recommendation": "先修复触发、反馈或结果状态，再用同一旅程重新验证。",
                })
            elif step.get("status") == "FAIL" and not proof:
                candidates.append({
                    "targetIdentity": target, "routeTemplate": route or "/", "journeyId": "primary-journey", "stepId": step.get("id"),
                    "issueType": "NO_RESPONSE", "semanticTarget": str(step.get("locator") or step.get("step") or "journey step"),
                    "state": "interaction", "viewportClass": _viewport_class(str(run.get("viewport"))),
                    "expectedOutcomeKey": "step_executes", "observedOutcomeKey": "step_execution_failed",
                    "evidenceKinds": ["interaction"], "evidenceRefs": [f"journeys/{run.get('viewport')}#{step.get('id')}"],
                    "ruleId": "JOURNEY-EXECUTION", "ruleVersion": "2.3-p0a",
                    "verificationState": "NOT_VERIFIED", "resultLabel": "暂时无法确认", "severity": "medium",
                    "summary": "关键步骤无法稳定执行。", "impact": "当前证据不足以区分产品问题和定位/环境问题。",
                    "recommendation": "修正定位器或运行条件后重新执行，不把这次失败冒充产品 Bug。",
                })
    for warning in preflight.get("warnings", []):
        if "runtime error" in str(warning):
            candidates.append({
                "targetIdentity": target, "routeTemplate": route or "/", "issueType": "RUNTIME_HEALTH",
                "semanticTarget": "page runtime", "state": "load", "viewportClass": "all",
                "expectedOutcomeKey": "no_blocking_runtime_error", "observedOutcomeKey": "runtime_error_observed",
                "evidenceKinds": ["console", "page-error"], "evidenceRefs": ["quick-ui-report.json#runtime"],
                "ruleId": "RUNTIME-PAGE-ERROR", "ruleVersion": "2.3-p0a",
                "verificationState": "VERIFIED", "resultLabel": "现在会出错", "severity": "high",
                "summary": "页面运行时出现错误。", "impact": "部分操作或状态可能无法可靠完成。",
                "recommendation": "定位错误堆栈对应的组件或状态逻辑，修复后重跑原旅程。",
            })
    return candidates


def _coverage(
    *,
    project: Mapping[str, Any],
    quick_report: Mapping[str, Any] | None,
    journey_report: Mapping[str, Any],
    source: str,
) -> dict[str, Any]:
    viewports = [f"{row.get('width')}x{row.get('height')}" for row in (quick_report or {}).get("viewports", [])]
    return {
        "targetSource": source,
        "productCoverage": {
            "pages": [{"identity": (quick_report or {}).get("url"), "state": "EXECUTED"}] if quick_report else [],
            "viewports": [{"identity": value, "state": "EXECUTED"} for value in viewports],
            "journeys": [{"identity": "primary-journey", "state": "EXECUTED" if journey_report.get("status") in {"PASS", "FAIL", "NOT_VERIFIED"} else "NOT_EXECUTED", "result": journey_report.get("status")}],
            "sourceObjects": project.get("discovered", []),
        },
        "boundaries": [
            "发现的源码路由不等于已执行路由。",
            "Only the recorded role, state, locale, theme, viewports, and journey are covered.",
            "A PASS does not certify unexecuted pages, roles, data combinations, browsers, or devices.",
        ],
    }


def _status_and_conclusion(preflight: Mapping[str, Any], journey: Mapping[str, Any], findings: Sequence[Mapping[str, Any]]) -> tuple[str, str]:
    if preflight.get("status") == "BLOCKED":
        browser = preflight.get("browser") if isinstance(preflight.get("browser"), Mapping) else {}
        if browser.get("available") is False:
            return "BLOCKED", "源码检查已完成，但真实浏览器验证未完成；恢复可用 Browser 后再继续。"
        return "BLOCKED", "当前环境不能代表真实产品，本次无法形成交付结论。"
    if any(item.get("resultLabel") == "现在会出错" for item in findings):
        return "FAIL", "基于本次已检查范围，暂不建议交付。"
    if journey.get("status") in {"NOT_VERIFIED", "NOT_EXECUTED"}:
        return "NOT_VERIFIED", "已完成页面快检，但关键旅程尚未得到足够证据，暂时无法确认能否交付。"
    if any(item.get("resultLabel") in {"用起来别扭", "建议考虑补充", "暂时无法确认"} for item in findings):
        return "PASS_WITH_WARNINGS", "基于本次已检查范围，未发现已证实的阻断问题，但仍有体验或证据边界需要处理。"
    return "PASS", "基于本次已检查范围，未发现已证实的阻断问题。"


def _render_html(report: Mapping[str, Any]) -> str:
    top = list(report.get("topFindings") or [])
    cards = "".join(
        f"""<article class=card><div class=tag>{escape(str(item.get('resultLabel')))}</div><h3>{escape(str(item.get('summary')))}</h3>
        <p><b>影响：</b>{escape(str(item.get('impact')))}</p><p><b>最小处理：</b>{escape(str(item.get('recommendation')))}</p>
        <small>{escape(str(item.get('viewportClass')))} · {escape(str(item.get('verificationState')))}</small></article>"""
        for item in top
    ) or "<article class=card><h3>本次没有进入 Top 3 的已证实问题</h3><p>仍请查看覆盖范围和未验证边界。</p></article>"
    shots = "".join(
        f"<figure><img src='{escape(str(row.get('screenshotRef')))}'><figcaption>{escape(str(row.get('label')))} · {escape(str(row.get('status')))}</figcaption></figure>"
        for row in (report.get("runtime") or {}).get("records", []) if row.get("screenshotRef")
    )
    coverage = report.get("coverageSummary") or {}
    return f"""<!doctype html><html lang=zh-CN><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>
<title>Web UI Quality {escape(str(report.get('packageVersion') or ''))} · 智能验收</title><style>
:root{{--bg:#f5f7f8;--card:#fff;--ink:#18201d;--muted:#66736e;--line:#dfe6e2;--accent:#166b4f}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.65 system-ui,-apple-system,'Segoe UI',sans-serif}}
main{{max-width:1180px;margin:auto;padding:34px 22px 60px}}header{{display:flex;justify-content:space-between;gap:24px;align-items:flex-start}}
h1{{margin:0 0 8px;font-size:32px}}.status{{border:1px solid var(--line);background:#fff;border-radius:999px;padding:7px 13px;font-weight:700}}
.panel{{background:#fff;border:1px solid var(--line);border-radius:18px;padding:22px;margin-top:20px;box-shadow:0 8px 28px rgba(20,40,32,.05)}}
.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}}.card{{border:1px solid var(--line);border-radius:14px;padding:16px}}.card h3{{margin:7px 0 8px;font-size:18px}}
.tag{{display:inline-block;background:#eef7f2;color:var(--accent);border-radius:7px;padding:2px 8px;font-size:12px;font-weight:700}}small,.muted{{color:var(--muted)}}
.shots{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}}figure{{margin:0}}img{{width:100%;display:block;border:1px solid var(--line);border-radius:10px}}figcaption{{color:var(--muted);margin-top:6px}}
@media(max-width:800px){{header{{display:block}}.status{{display:inline-block;margin-top:12px}}.grid,.shots{{grid-template-columns:1fr}}}}
</style></head><body><main><header><div><p>Web UI Quality {escape(str(report.get('packageVersion') or ''))}</p><h1>智能验收结果</h1><p>{escape(str(report.get('deliveryConclusion')))}</p></div><div class=status>{escape(status_label(report.get('status')))}</div></header>
<section class=panel><h2>本次检查范围</h2><p>{escape(str((report.get('businessContext') or {}).get('summary')))}</p>
<p class=muted>视口：{escape(', '.join(coverage.get('viewports', [])) or '未执行')} · 旅程：{escape(str(coverage.get('journeyStatus')))}</p>
<p>{escape(str((report.get('preflight') or {}).get('plainSummary')))}</p></section>
<section class=panel><h2>最重要的 {len(top)} 个结果</h2><div class=grid>{cards}</div></section>
<section class=panel><h2>运行证据</h2><div class=shots>{shots}</div></section>
<section class=panel><h2>边界</h2><ul>{''.join(f'<li>{escape(str(x))}</li>' for x in (report.get('coverage') or {}).get('boundaries', []))}</ul></section>
</main></body></html>"""


def run_smart_acceptance(
    target: str | Path,
    *,
    output_dir: str | Path,
    url: str | None = None,
    project_root: str | Path | None = None,
    business_context: Mapping[str, Any] | None = None,
    journey_steps: Sequence[Mapping[str, Any]] | None = None,
    viewports: Sequence[Sequence[int]] | None = None,
    locale: str = "zh-CN",
    theme: str = "light",
    allow_origins: Iterable[str] = (),
    environment: str | None = None,
    browser_name: str = "chromium",
    storage_state: str | Path | Mapping[str, Any] | None = None,
    extra_http_headers: Mapping[str, str] | None = None,
    ignore_https_errors: bool = False,
    browser_executable: str | Path | None = None,
    task_goal: Mapping[str, Any] | None = None,
    approved_requests: Sequence[Mapping[str, str]] = (),
) -> dict[str, Any]:
    output = Path(output_dir).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    matrix = tuple(viewports or _DEFAULT_VIEWPORTS)
    with _resolved_target(project_root or target, explicit_url=url) as resolved:
        actual_url = resolved.get("url")
        actual_project = resolved.get("projectRoot")
        environment_info = _environment(actual_url, environment)
        viewport_summary = [f"{width}x{height}" for width, height in matrix]
        settings_summary = {
            "schemaVersion": "1",
            "url": actual_url,
            "urlSource": resolved.get("source"),
            "viewports": viewport_summary,
            "locale": locale,
            "theme": theme,
            "browser": browser_name,
            "checkDepth": "页面健康 + Top 3 + 一次安全旅程",
            "riskLevel": "LOW_READ_ONLY",
            "verificationStrategy": "三视口 Browser 证据 + 页面健康 + Outcome Proof",
            "defaultsApplied": {
                "viewports": viewports is None,
                "locale": locale == "zh-CN",
                "theme": theme == "light",
                "browser": browser_name == "chromium",
                "environment": environment is None,
            },
            "editable": ["url", "viewports", "locale", "theme", "browser", "journey"],
            "plainSummary": (
                "已使用安全默认设置："
                f"视口={', '.join(viewport_summary)}；"
                "检查深度=页面健康+Top 3+一次安全旅程；"
                "风险等级=低；验证策略=三视口 Browser 证据+Outcome Proof。"
            ),
            "claimBoundary": "设置摘要只说明本次计划的安全默认值；它不代表页面已执行或验证通过。",
        }
        quick_report: dict[str, Any] | None = None
        if actual_url:
            try:
                quick_report = run_quick_ui(
                    actual_url, output_dir=output, viewports=matrix, locale=locale, theme=theme,
                    allow_origins=allow_origins, browser_name=browser_name, storage_state=storage_state,
                    extra_http_headers=extra_http_headers, ignore_https_errors=ignore_https_errors, browser_executable=browser_executable, approved_requests=approved_requests,
                )
            except ContractViolation as error:
                quick_report = {"status": "NOT_VERIFIED", "records": [], "viewports": [{"width": w, "height": h} for w, h in matrix], "error": error.as_dict(), "url": actual_url}
        project_map = _project_coverage(actual_project)
        first_record = ((quick_report or {}).get("records") or [{}])[0]
        metrics = first_record.get("metrics") or {}
        inferred: dict[str, Any] = {}
        visible_title = str(metrics.get("h1") or metrics.get("title") or "").strip()
        if visible_title:
            inferred["coreObject"] = visible_title
        context = build_context_v2(
            business_context, reason="smart_acceptance_initial",
            default_environment=environment_info.get("observed"), inferred=inferred,
        )
        preflight = _preflight(quick_report, url=actual_url, environment=environment_info, browser_executable=browser_executable)
        if actual_url and preflight.get("canContinue") and not preflight.get("authRequired"):
            journey_report = _run_journey_matrix(
                actual_url, output_dir=output, viewports=matrix, locale=locale, theme=theme,
                allow_origins=allow_origins, browser_name=browser_name, steps=journey_steps,
                environment=environment_info, storage_state=storage_state,
                extra_http_headers=extra_http_headers, ignore_https_errors=ignore_https_errors, browser_executable=browser_executable, approved_requests=approved_requests,
            )
        else:
            journey_report = {"status": "NOT_VERIFIED" if preflight.get("status") != "PARTIAL" else "NOT_EXECUTED", "reason": "Preflight or authentication boundary prevented safe journey execution.", "runs": [], "journey": []}
        candidates = _finding_candidates(url=actual_url, quick_report=quick_report, journey_report=journey_report, preflight=preflight)
        normalized = normalize_findings(candidates, context_version=context["contextVersion"])
        findings = normalized["findings"]
        if task_goal is not None:
            findings = bind_findings_to_goal(findings, task_goal)
        top = top_findings(findings, limit=3)
        status, conclusion = _status_and_conclusion(preflight, journey_report, findings)
        coverage = _coverage(project=project_map, quick_report=quick_report, journey_report=journey_report, source=str(resolved.get("source")))
        representative = (((quick_report or {}).get("records") or [{}])[0])
        page_health = evaluate_page_health(
            readiness=representative.get("readiness"), resource_integrity=representative.get("resourceIntegrity"),
            runtime_errors=list(representative.get("pageErrors") or []),
            auth_required=bool((representative.get("metrics") or {}).get("authWallHint")),
            task_status=str(journey_report.get("status") or "NOT_VERIFIED"),
            visual_findings=len(findings), browser_executed=bool((quick_report or {}).get("records")),
        )
        if page_health.get("pageStatus") in {"RUNTIME_BROKEN", "AUTH_REQUIRED", "RESTRICTED_RENDER", "DATA_NOT_READY", "TASK_FAILED"}:
            status = "FAIL" if page_health.get("pageStatus") != "AUTH_REQUIRED" else "PARTIAL"
            conclusion = "页面健康状态优先于视觉结果；当前不能把整洁截图判定为产品通过。"
        report: dict[str, Any] = {
            "schemaVersion": "2.3-p0a",
            "producer": "web-ui-quality-smart-acceptance",
            "packageVersion": PACKAGE_VERSION,
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "status": status,
            "deliveryConclusion": conclusion,
            "target": {"url": actual_url, "projectRoot": "." if actual_project else None, "source": resolved.get("source")},
            "businessContext": context,
            "preflight": preflight,
            "pageHealth": page_health,
            "runtime": quick_report,
            "journey": journey_report,
            "findings": findings,
            "topFindings": top,
            "repairRecipes": build_repair_recipes(top, confirmed_ids=[str(item.get("findingId") or item.get("id") or item.get("ruleId") or item.get("fingerprint")) for item in top]),
            "normalization": {"errors": normalized["normalizationErrors"], "digest": normalized["digest"]},
            "coverage": coverage,
            "coverageSummary": {
                "viewports": [f"{w}x{h}" for w, h in matrix],
                "viewportNormalization": (quick_report or {}).get("viewportNormalization") or {"status": "NOT_VERIFIED", "records": []},
                "journeyStatus": journey_report.get("status"),
                "executedJourneys": 1 if journey_report.get("journey") else 0,
                "unverifiedAreas": ["authenticated roles"] if preflight.get("authRequired") else [],
                "settingsSummary": settings_summary,
            },
            "phaseCapabilities": {
                "P0-0": "AVAILABLE", "P0-0.5": "AVAILABLE", "P0-A": "AVAILABLE",
                "P0-B-R": "NOT_EXECUTED", "P0-B-S": "NOT_EXECUTED",
                "P1-R": "NOT_APPLICABLE_TO_THIS_RELEASE", "P1-S": "NOT_APPLICABLE_TO_THIS_RELEASE",
                "P2": "NOT_APPLICABLE_TO_THIS_RELEASE", "P3": "NOT_APPLICABLE_TO_THIS_RELEASE",
            },
            "claimBoundary": "本结果仅适用于本次记录的目标、环境、业务上下文、视口与已执行旅程；它不是发布认证。" if locale.lower().startswith("zh") else "This result applies only to the recorded target, environment, context, viewports, and executed journey. It is not a release certification.",
        }
        report["reportDigest"] = digest_json(report)
        report_json = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
        report_html = _render_html(report)
        evidence_dir = output / "evidence"
        evidence_dir.mkdir(parents=True, exist_ok=True)
        (evidence_dir / "smart-acceptance-report.json").write_text(report_json, encoding="utf-8")
        (output / "smart-acceptance-report.json").write_text(report_json, encoding="utf-8")
        (output / "smart-acceptance-report.html").write_text(report_html, encoding="utf-8")
        (output / "index.html").write_text(report_html, encoding="utf-8")
        summary = [
            "# 智能验收结果", "", f"- 状态：{status_label(status)}", f"- 结论：{conclusion}",
        ]
        if top:
            summary.extend(["", f"## 最重要的 {len(top)} 个结果"] )
            for item in top:
                summary.append(f"- **{item.get('resultLabel')}：{item.get('summary')}** — {item.get('recommendation')}")
        else:
            summary.extend(["", "## 本次没有可排序的问题", "", "- 当前证据没有形成可验证的 Top 问题；请结合页面可运行性与覆盖边界解读结果。"] )
        summary.extend(["", "## 业务理解边界", "", f"- {context.get('summary')}", "", "技术证据位于 `evidence/`。"] )
        if (output / "screenshots").is_dir() and any((output / "screenshots").iterdir()):
            summary.append("真实页面截图位于 `screenshots/`。")
        (output / "summary.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
        report["open"] = "index.html"
        report["summary"] = "summary.md"
        return report


__all__ = ["run_smart_acceptance"]
