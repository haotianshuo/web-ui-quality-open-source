"""Optional Playwright adapter for isolated, same-condition Browser evidence.

The adapter follows three principles used by mature browser-testing systems:
fresh contexts, resilient page readiness, and evidence that is separate from the
static audit result.  It does not perform destructive actions or submit forms.
"""

from __future__ import annotations

import hashlib
import asyncio
import json
import re
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import urlsplit

from .contracts import ContractViolation, digest_json
from .trusted_evidence import TrustedUIBrowserEvidence, bind_local_browser_evidence
from .journey import JourneyPolicy, execute_journey, validate_journey
from .visual_diff import compare_images
from .rendered_quality import inspect_rendered_page
from .browser_experience import inspect_experience_geometry, inspect_semantic_dom, persist_experience_evidence
from .external_providers import run_axe
from .evidence_redaction import mask_sensitive_dom_for_screenshot, redact_text
from .condition_registry import STANDARD_VIEWPORTS
from .mutation_firewall import BrowserMutationFirewall
from .secure_browser_context import build_credential_map, create_secure_context, split_headers
from .resource_integrity import classify_resource_events
from .readiness import assess_readiness
from .page_health import evaluate_page_health
from .browser_locator import resolve_browser_executable

DEFAULT_VIEWPORTS: tuple[tuple[int, int], ...] = STANDARD_VIEWPORTS
_SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def playwright_capability(browser_executable: str | Path | None = None) -> dict[str, Any]:
    try:
        import playwright  # noqa: F401
        if browser_executable is not None:
            decision = resolve_browser_executable("chromium", explicit=browser_executable)
        else:
            from playwright.async_api import async_playwright

            async def discover() -> dict[str, Any]:
                async with async_playwright() as runtime:
                    return resolve_browser_executable("chromium", playwright_browser_type=runtime.chromium)

            # The capability check is synchronous at the public boundary, but
            # the async Playwright lifecycle lets its initialization task finish
            # before shutdown.  This avoids leaving TargetClosedError warnings on
            # redirected release evidence while preserving the same resolver.
            decision = asyncio.run(discover())
        return {
            "available": bool(decision.get("available")),
            "browser": "chromium" if decision.get("available") else None,
            "executablePresent": bool(decision.get("available")),
            "executable": decision.get("executable"),
            "executableSource": decision.get("source"),
            "reasonCode": "CAPABILITY_AVAILABLE" if decision.get("available") else decision.get("reasonCode") or "BROWSER_EXECUTABLE_NOT_FOUND",
            "resolutionTrace": list(decision.get("resolutionTrace") or []),
            "reason": decision.get("reason"),
        }
    except Exception as error:  # pragma: no cover - environment dependent
        return {
            "available": False,
            "browser": None,
            "reasonCode": "PYTHON_PLAYWRIGHT_PROBE_FAILED",
            "error": type(error).__name__,
        }


def _safe_url(value: str, name: str) -> str:
    if not isinstance(value, str):
        raise ContractViolation("BROWSER_URL_INVALID", [f"$.{name}: expected string"])
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ContractViolation("BROWSER_URL_INVALID", [f"$.{name}: expected safe http(s) URL"])
    return value


def _origin(value: str) -> str:
    parsed = urlsplit(value)
    default_port = 80 if parsed.scheme == "http" else 443
    port = parsed.port
    authority = parsed.hostname if port in {None, default_port} else f"{parsed.hostname}:{port}"
    return f"{parsed.scheme}://{authority}"


def _normalize_viewports(viewports: Sequence[Sequence[int]] | None) -> tuple[tuple[int, int], ...]:
    raw = viewports or DEFAULT_VIEWPORTS
    normalized: list[tuple[int, int]] = []
    for index, item in enumerate(raw):
        if len(item) != 2:
            raise ContractViolation("BROWSER_VIEWPORT_INVALID", [f"$.viewports[{index}]: expected width,height"])
        width, height = int(item[0]), int(item[1])
        if width < 320 or height < 480 or width > 3840 or height > 2160:
            raise ContractViolation("BROWSER_VIEWPORT_INVALID", [f"$.viewports[{index}]: unsupported dimensions"])
        normalized.append((width, height))
    if len(normalized) != len(set(normalized)):
        raise ContractViolation("BROWSER_VIEWPORT_INVALID", ["$.viewports: duplicates are not allowed"])
    return tuple(normalized)


def _context_options(
    *,
    viewport: tuple[int, int],
    locale: str,
    theme: str,
    storage_state: str | Path | Mapping[str, Any] | None,
    extra_http_headers: Mapping[str, str] | None,
    ignore_https_errors: bool,
) -> dict[str, Any]:
    width, height = viewport
    options: dict[str, Any] = {
        "viewport": {"width": width, "height": height},
        "device_scale_factor": 2 if width <= 480 else 1.5 if width <= 900 else 1,
        "locale": locale,
        "color_scheme": theme,
        "reduced_motion": "reduce",
        "service_workers": "block",
        "accept_downloads": False,
        "ignore_https_errors": ignore_https_errors,
    }
    if width <= 480:
        options["is_mobile"] = True
        options["has_touch"] = True
    elif width <= 900:
        options["has_touch"] = True
    if storage_state is not None:
        options["storage_state"] = str(storage_state) if isinstance(storage_state, Path) else storage_state
    if extra_http_headers:
        safe_headers, _ = split_headers(extra_http_headers)
        if safe_headers:
            options["extra_http_headers"] = safe_headers
    return options


def _capture_one(
    browser: Any,
    *,
    url: str,
    label: str,
    viewport: tuple[int, int],
    output_dir: Path,
    locale: str,
    theme: str,
    allowed_origins: set[str],
    primary_origins: set[str],
    timeout_ms: int,
    approved_requests: Sequence[Mapping[str, str]] = (),
    storage_state: str | Path | Mapping[str, Any] | None = None,
    extra_http_headers: Mapping[str, str] | None = None,
    credential_headers_by_origin: Mapping[str, Mapping[str, str]] | None = None,
    ignore_https_errors: bool = False,
    axe_script: str | Path | None = None,
    persist_dom_sidecars: bool = True,
) -> dict[str, Any]:
    width, height = viewport
    safe_headers, credential_map = build_credential_map(
        target_origin=_origin(url), all_primary_origins=primary_origins, headers=extra_http_headers, explicit_by_origin=credential_headers_by_origin,
    )
    # BrowserMutationFirewall is the single owner of navigation-route
    # canonicalization. Callers pass the raw target URL so a query-bearing
    # route cannot be canonicalized twice and lose its query digest.
    approved_navigation_routes = {url}
    secure = create_secure_context(
        browser,
        context_options=_context_options(
            viewport=viewport, locale=locale, theme=theme, storage_state=storage_state,
            extra_http_headers=safe_headers, ignore_https_errors=ignore_https_errors,
        ),
        allowed_origins=allowed_origins, credential_headers_by_origin=credential_map, credential_origins={_origin(url)} if storage_state is not None else set(credential_map),
        approved_requests=approved_requests, approved_routes=approved_navigation_routes,
        authenticated=bool(storage_state is not None or credential_map),
    )
    context = secure.context
    page = context.new_page()
    console_errors: list[dict[str, str]] = []
    page_errors: list[str] = []
    request_failures: list[dict[str, str]] = []
    blocked_requests = secure.blocked_requests
    firewall = secure.firewall
    page.on(
        "console",
        lambda message: console_errors.append({"type": message.type, "text": redact_text(message.text[:500])})
        if message.type in {"error", "warning"}
        else None,
    )
    page.on("pageerror", lambda error: page_errors.append(redact_text(str(error)[:500])))
    page.on(
        "requestfailed",
        lambda request: request_failures.append(
            {"url": request.url.split("?", 1)[0], "method": request.method, "reason": redact_text(str(request.failure or "failed")[:200]), "resourceType": str(request.resource_type or "unknown"), "origin": _origin(request.url) if urlsplit(request.url).hostname else urlsplit(request.url).scheme}
        ),
    )

    result: dict[str, Any]
    try:
        response = page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        try:
            page.evaluate("document.fonts && document.fonts.ready ? document.fonts.ready : Promise.resolve()")
        except Exception:
            pass
        stability = {"status": "NOT_VERIFIED", "samples": 0}
        last_signature = None
        stable_count = 0
        for sample_index in range(8):
            page.wait_for_timeout(150 if sample_index else 250)
            signature = page.evaluate(
                """() => ({
                    readyState: document.readyState,
                    childCount: document.body ? document.body.getElementsByTagName('*').length : 0,
                    textLength: document.body ? (document.body.innerText || '').length : 0,
                    scrollWidth: document.documentElement ? document.documentElement.scrollWidth : 0,
                    scrollHeight: document.documentElement ? document.documentElement.scrollHeight : 0
                })"""
            )
            stability["samples"] = sample_index + 1
            if signature == last_signature and signature.get("readyState") in {"interactive", "complete"}:
                stable_count += 1
            else:
                stable_count = 0
            last_signature = signature
            if stable_count >= 2:
                stability = {"status": "STABLE", "samples": sample_index + 1, "signature": signature}
                break
        if stability.get("status") != "STABLE":
            stability["signature"] = last_signature
        metrics = page.evaluate(
            r"""
            () => ({
              innerWidth: window.innerWidth,
              innerHeight: window.innerHeight,
              devicePixelRatio: window.devicePixelRatio,
              visualViewportScale: window.visualViewport ? window.visualViewport.scale : 1,
              scrollX: window.scrollX,
              scrollY: window.scrollY,
              bodyScrollWidth: document.body ? document.body.scrollWidth : 0,
              documentScrollWidth: document.documentElement ? document.documentElement.scrollWidth : 0,
              fontsStatus: document.fonts ? document.fonts.status : 'unsupported',
              title: document.title || '',
              h1: document.querySelector('h1')?.textContent?.trim() || '',
              activeElement: document.activeElement?.tagName || '',
              lang: document.documentElement.lang || '',
              readyState: document.readyState,
              bodyTextLength: document.body ? (document.body.innerText || '').trim().length : 0,
              textLength: document.body ? (document.body.innerText || '').trim().length : 0,
              elementCount: document.body ? document.body.getElementsByTagName('*').length : 0,
              mainPresent: Boolean(document.querySelector('main,[role=main],#app,#__next')),
              skeletonCount: document.querySelectorAll('[class*=skeleton i],[aria-busy=true],[data-loading=true]').length,
              loadingHint: /(?:正在加载|加载中|loading\.?\.?)$/i.test((document.body?.innerText || '').trim().slice(-80)),
              authWallHint: Boolean(document.querySelector('input[type=password]')) || /登录|登陆|sign\s*in|log\s*in|验证码|verification code/i.test((document.body?.innerText || '').slice(0,4000))
            })
            """
        )
        rendered_quality = inspect_rendered_page(page)
        experience_geometry = inspect_experience_geometry(page, viewport_id=label)
        sidecar_refs: dict[str, str] = {}
        if persist_dom_sidecars:
            semantic_dom = inspect_semantic_dom(page)
            sidecar_refs = persist_experience_evidence(
                output_dir,
                label=label,
                viewport={"width": width, "height": height},
                dom_snapshot=semantic_dom,
                geometry=experience_geometry,
            )
        axe_result = run_axe(page, axe_script) if axe_script else {"status": "NOT_RUN", "reason": "axe script not supplied"}
        overflow = max(int(metrics["bodyScrollWidth"]), int(metrics["documentScrollWidth"])) > int(metrics["innerWidth"]) + 1
        filename = _SAFE_FILENAME_RE.sub("-", f"{label}-{width}x{height}-viewport.png")
        full_filename = _SAFE_FILENAME_RE.sub("-", f"{label}-{width}x{height}-full-page.png")
        screenshot_path = output_dir / filename
        full_screenshot_path = output_dir / full_filename
        screenshot_masked_nodes = mask_sensitive_dom_for_screenshot(page)
        page.screenshot(path=str(screenshot_path), full_page=False, animations="disabled")
        page.screenshot(path=str(full_screenshot_path), full_page=True, animations="disabled")
        raw = screenshot_path.read_bytes()
        full_raw = full_screenshot_path.read_bytes()
        http_status = response.status if response is not None else None
        http_ok = http_status is not None and 200 <= http_status < 300
        quality_ok = rendered_quality.get("status") == "PASS" and axe_result.get("status") in {"PASS", "NOT_RUN"}
        critical_types = {"document", "script", "stylesheet", "xhr", "fetch", "font", "manifest"}
        critical_blocked = [item for item in blocked_requests if item.get("resourceType") in critical_types and item.get("code") != "NONCRITICAL_TELEMETRY_BLOCKED"]
        critical_failed = [item for item in request_failures if item.get("resourceType") in critical_types and "blockedbyclient" not in str(item.get("reason", "")).lower()]
        page_origin = _origin(page.url) if urlsplit(page.url).hostname else None
        resource_integrity = classify_resource_events([*blocked_requests, *critical_failed], page_origin=page_origin)
        composite_readiness = assess_readiness(
            metrics, http_status=http_status, page_errors=page_errors, console_errors=console_errors,
            core_resource_failures=resource_integrity.get("coreFailures"), timed_out=stability.get("status") != "STABLE",
        )
        valid_render = int(metrics.get("elementCount") or 0) > 0 and (int(metrics.get("bodyTextLength") or 0) > 0 or bool(metrics.get("title")))
        evidence_status = "NOT_VERIFIED" if resource_integrity.get("status") == "BLOCKED" or secure.blocked_websockets or firewall.network_escape_attempted or not valid_render or composite_readiness.get("status") != "READY" else "VERIFIED"
        page_health = evaluate_page_health(
            readiness=composite_readiness, resource_integrity=resource_integrity,
            runtime_errors=page_errors, auth_required=bool(metrics.get("authWallHint")),
            task_status=None, visual_findings=int(rendered_quality.get("findingCount") or 0), browser_executed=True,
        )
        result = {
            "label": label,
            "url": page.url.split("?", 1)[0],
            "viewport": {"width": width, "height": height},
            "httpStatus": http_status,
            "metrics": metrics,
            "horizontalOverflow": overflow,
            "screenshotRef": screenshot_path.name,
            "screenshotSha256": hashlib.sha256(raw).hexdigest(),
            "screenshotBytes": len(raw),
            "fullPageScreenshotRef": full_screenshot_path.name,
            "fullPageScreenshotSha256": hashlib.sha256(full_raw).hexdigest(),
            "fullPageScreenshotBytes": len(full_raw),
            "evidenceRedaction": {"textual": "APPLIED", "screenshotKnownSensitiveNodesMasked": screenshot_masked_nodes, "arbitraryVisualPiiRecognition": "NOT_MEASURED"},
            "console": console_errors,
            "pageErrors": page_errors,
            "requestFailures": request_failures,
            "blockedOrigins": sorted({item.get("origin") for item in blocked_requests if item.get("origin")}),
            "blockedRequests": blocked_requests,
            "criticalBlockedRequests": critical_blocked,
            "criticalRequestFailures": critical_failed,
            "readiness": composite_readiness,
            "stability": stability,
            "resourceIntegrity": resource_integrity,
            "mutationFirewall": {"status": "PASS" if not firewall.mutation_attempted else "BLOCKED_MUTATION_ATTEMPT", "decisions": firewall.decisions},
            "networkPolicy": secure.report(),
            "pageHealth": page_health,
            "validRender": valid_render,
            "evidenceStatus": evidence_status,
            "renderedQuality": rendered_quality,
            "experienceGeometry": experience_geometry,
            "axe": axe_result,
            "status": "FAIL" if not http_ok else "NOT_VERIFIED" if evidence_status == "NOT_VERIFIED" else "PASS" if quality_ok and not critical_failed and not page_errors else "PASS_WITH_WARNINGS",
        }
        result.update(sidecar_refs)
    except Exception as error:
        result = {
            "label": label,
            "url": url.split("?", 1)[0],
            "viewport": {"width": width, "height": height},
            "status": "FAIL",
            "error": type(error).__name__,
            "errorMessage": str(error)[:500],
        }
    finally:
        context.close()
    return result


def compare_pages(
    before_url: str,
    after_url: str,
    *,
    output_dir: str | Path,
    viewports: Sequence[Sequence[int]] | None = None,
    locale: str = "zh-CN",
    theme: str = "light",
    allow_origins: Iterable[str] = (),
    timeout_ms: int = 15_000,
    browser_name: str = "chromium",
    journey_steps: Sequence[Mapping[str, Any]] | None = None,
    allow_submit: bool = False,
    trace: bool = True,
    visual_diff: bool = True,
    storage_state: str | Path | Mapping[str, Any] | None = None,
    extra_http_headers: Mapping[str, str] | None = None,
    credential_headers_by_origin: Mapping[str, Mapping[str, str]] | None = None,
    approved_requests: Sequence[Mapping[str, str]] = (),
    ignore_https_errors: bool = False,
    axe_script: str | Path | None = None,
    approved_action_ids: Iterable[str] = (),
    browser_executable: str | Path | None = None,
) -> tuple[dict[str, Any], TrustedUIBrowserEvidence]:
    """Capture before/after pages in fresh isolated contexts under equal settings."""

    before = _safe_url(before_url, "beforeUrl")
    after = _safe_url(after_url, "afterUrl")
    if theme not in {"light", "dark", "no-preference"}:
        raise ContractViolation("BROWSER_THEME_INVALID", ["$.theme: unsupported"])
    target_dir = Path(output_dir).expanduser().resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    matrix = _normalize_viewports(viewports)
    primary_origins = {_origin(before), _origin(after)}
    origins = set(primary_origins)
    for value in allow_origins:
        origins.add(_origin(_safe_url(str(value), "allowOrigins")))
    _, sensitive_headers = split_headers(extra_http_headers)
    if sensitive_headers and len(primary_origins) > 1 and not credential_headers_by_origin:
        raise ContractViolation("BROWSER_CREDENTIAL_SCOPE_AMBIGUOUS", ["$: sensitive headers cannot be shared across different before/after origins"])
    if storage_state is not None and len(primary_origins) > 1:
        raise ContractViolation("BROWSER_STORAGE_STATE_MULTI_ORIGIN_UNSAFE", ["$: one storageState cannot be shared across different before/after origins in 4.2.3"])

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as error:
        raise ContractViolation(
            "PLAYWRIGHT_UNAVAILABLE",
            ["$: install the optional browser dependency with `pip install web-ui-quality[browser]`"],
        ) from error

    records: list[dict[str, Any]] = []
    validated_journey = validate_journey(journey_steps, JourneyPolicy(allow_submit=allow_submit, approved_action_ids=frozenset(str(x) for x in approved_action_ids))) if journey_steps else None
    journey_results: list[dict[str, str]] = []
    trace_ref: str | None = None
    warnings: list[str] = []
    if trace and (storage_state is not None or sensitive_headers or credential_headers_by_origin):
        trace = False
        warnings.append("TRACE_DISABLED_FOR_AUTHENTICATED_OR_CREDENTIALLED_CONTEXT")
    with sync_playwright() as runtime:
        browser_type = getattr(runtime, browser_name, None)
        if browser_type is None:
            raise ContractViolation("BROWSER_ENGINE_INVALID", ["$.browserName: unsupported"])
        launch_options: dict[str, Any] = {"headless": True}
        decision = resolve_browser_executable(browser_name, explicit=browser_executable)
        if not decision.get("available") and browser_executable is None:
            decision = resolve_browser_executable(browser_name, playwright_browser_type=browser_type)
        if not decision.get("available"):
            raise ContractViolation("BROWSER_EXECUTABLE_UNAVAILABLE", [decision.get("reason") or "No usable browser executable was discovered."])
        launch_options["executable_path"] = decision["executable"]
        browser = browser_type.launch(**launch_options)
        try:
            for viewport in matrix:
                records.append(
                    _capture_one(
                        browser,
                        url=before,
                        label="before",
                        viewport=viewport,
                        output_dir=target_dir,
                        locale=locale,
                        theme=theme,
                        allowed_origins=origins, primary_origins=primary_origins,
                        timeout_ms=timeout_ms, approved_requests=approved_requests, storage_state=storage_state, extra_http_headers=extra_http_headers,
                        credential_headers_by_origin=credential_headers_by_origin, ignore_https_errors=ignore_https_errors, axe_script=axe_script,
                    )
                )
                records.append(
                    _capture_one(
                        browser,
                        url=after,
                        label="after",
                        viewport=viewport,
                        output_dir=target_dir,
                        locale=locale,
                        theme=theme,
                        allowed_origins=origins, primary_origins=primary_origins,
                        timeout_ms=timeout_ms, approved_requests=approved_requests, storage_state=storage_state, extra_http_headers=extra_http_headers,
                        credential_headers_by_origin=credential_headers_by_origin, ignore_https_errors=ignore_https_errors, axe_script=axe_script,
                    )
                )
            if validated_journey:
                for journey_index, viewport in enumerate(matrix):
                    width, height = viewport
                    viewport_id = f"{width}x{height}"
                    safe_headers, journey_credentials = build_credential_map(
                        target_origin=_origin(after), all_primary_origins=primary_origins, headers=extra_http_headers, explicit_by_origin=credential_headers_by_origin,
                    )
                    secure_journey = create_secure_context(
                        browser, context_options=_context_options(viewport=viewport, locale=locale, theme=theme, storage_state=storage_state, extra_http_headers=safe_headers, ignore_https_errors=ignore_https_errors),
                        allowed_origins=origins, credential_headers_by_origin=journey_credentials, credential_origins={_origin(after)} if storage_state is not None else set(journey_credentials),
                        approved_requests=approved_requests,
                        approved_routes={after},
                        authenticated=bool(storage_state is not None or journey_credentials),
                    )
                    context = secure_journey.context
                    journey_blocked_requests = secure_journey.blocked_requests
                    journey_firewall = secure_journey.firewall
                    page = context.new_page()
                    trace_started = False
                    try:
                        if trace and journey_index == 0:
                            context.tracing.start(screenshots=True, snapshots=True, sources=False)
                            trace_started = True
                        response = page.goto(after, wait_until="domcontentloaded", timeout=timeout_ms)
                        if response is None or not 200 <= response.status < 300:
                            raise RuntimeError(f"journey page returned HTTP {response.status if response is not None else 'none'}")
                        viewport_output = target_dir / "journey" / viewport_id
                        viewport_results = execute_journey(page, validated_journey, output_dir=viewport_output, timeout_ms=timeout_ms)
                        for item in viewport_results:
                            item["id"] = f"{item.get('id', 'step')}@{viewport_id}"
                            item["step"] = f"{item.get('step', '关键旅程')} [{viewport_id}]"
                            if item.get("failureScreenshotRef"):
                                item["failureScreenshotRef"] = f"journey/{viewport_id}/{item['failureScreenshotRef']}"
                        if journey_firewall.mutation_attempted or journey_firewall.network_escape_attempted or secure_journey.blocked_websockets:
                            viewport_results.append({
                                "id": f"browser-firewall@{viewport_id}", "step": f"Browser Firewall [{viewport_id}]",
                                "action": "network-guard", "status": "FAIL", "reason": "BLOCKED_BROWSER_POLICY_ATTEMPT",
                                "durationMs": 0, "locatorStrategy": "network", "url": after.split("?", 1)[0],
                                "networkPolicy": secure_journey.report(),
                            })
                        journey_results.extend(viewport_results)
                        if journey_blocked_requests:
                            kinds = sorted({str(item.get("code")) for item in journey_blocked_requests})
                            warnings.append(f"journey {viewport_id} requests blocked: {', '.join(kinds)}")
                    except Exception as error:
                        journey_results.append({
                            "id": f"journey-bootstrap@{viewport_id}",
                            "step": f"关键旅程初始化 [{viewport_id}]",
                            "action": "goto",
                            "status": "FAIL",
                            "reason": f"{type(error).__name__}: {str(error)[:400]}",
                            "durationMs": 0,
                            "locatorStrategy": "navigation",
                            "url": after.split("?", 1)[0],
                        })
                    finally:
                        if trace_started:
                            try:
                                trace_path = target_dir / "journey-trace.zip"
                                context.tracing.stop(path=str(trace_path))
                                trace_ref = trace_path.name
                            except Exception:
                                warnings.append("journey trace could not be finalized")
                        context.close()
        finally:
            browser.close()

    failures = [item for item in records if item["status"] == "FAIL"]
    equal_condition_pairs = True
    for viewport in matrix:
        pair = [item for item in records if item["viewport"] == {"width": viewport[0], "height": viewport[1]}]
        if len(pair) != 2 or any(item["status"] not in {"PASS", "PASS_WITH_WARNINGS"} for item in pair):
            equal_condition_pairs = False
            continue
        before_metrics, after_metrics = pair[0]["metrics"], pair[1]["metrics"]
        keys = ("innerWidth", "innerHeight", "devicePixelRatio", "visualViewportScale")
        if any(before_metrics[key] != after_metrics[key] for key in keys):
            equal_condition_pairs = False
        for item in pair:
            if item["horizontalOverflow"]:
                warnings.append(f"{item['label']} {viewport[0]}x{viewport[1]} horizontal overflow")
            if item["console"] or item["pageErrors"] or item["requestFailures"]:
                warnings.append(f"{item['label']} {viewport[0]}x{viewport[1]} runtime warnings")
            if item["blockedOrigins"]:
                warnings.append(f"{item['label']} {viewport[0]}x{viewport[1]} external origins blocked")
            if item.get("renderedQuality", {}).get("status") in {"FAIL", "PASS_WITH_WARNINGS"}:
                warnings.append(f"{item['label']} {viewport[0]}x{viewport[1]} rendered quality findings")
            if item.get("axe", {}).get("status") in {"FAIL", "PASS_WITH_WARNINGS"}:
                warnings.append(f"{item['label']} {viewport[0]}x{viewport[1]} accessibility findings")
    if failures or not equal_condition_pairs:
        status = "FAIL"
    elif warnings:
        status = "PASS_WITH_WARNINGS"
    else:
        status = "PASS"

    first_before = next((item for item in records if item.get("label") == "before" and item.get("status") in {"PASS", "PASS_WITH_WARNINGS"}), None)
    first_after = next((item for item in records if item.get("label") == "after" and item.get("status") in {"PASS", "PASS_WITH_WARNINGS"}), None)
    before_ref = first_before["screenshotRef"] if first_before else "NOT_VERIFIED"
    after_ref = first_after["screenshotRef"] if first_after else "NOT_VERIFIED"
    journey = [
        {
            "step": "页面在隔离 Browser Context 中完成加载",
            "status": "FAIL" if failures else "PASS",
            "reason": "所有代表视口均执行独立导航与截图。" if not failures else "至少一个页面或视口加载失败。",
        },
        {
            "step": "before/after 条件一致",
            "status": "PASS" if equal_condition_pairs else "FAIL",
            "reason": "CSS viewport、DPR 与 visualViewport scale 已逐对核验。",
        },
        {
            "step": "关键内容无明显横向溢出",
            "status": "PASS" if not any(item.get("horizontalOverflow") for item in records) else "PASS_WITH_WARNINGS",
            "reason": "通过 document/body scrollWidth 与 innerWidth 比较。",
        },
    ]
    if journey_results:
        journey.extend(journey_results)
        if any(item["status"] == "FAIL" for item in journey_results):
            status = "FAIL"
    visual_results: list[dict[str, Any]] = []
    if visual_diff:
        for width, height in matrix:
            before_path = target_dir / f"before-{width}x{height}.png"
            after_path = target_dir / f"after-{width}x{height}.png"
            if before_path.exists() and after_path.exists():
                result = compare_images(before_path, after_path, diff_path=target_dir / f"diff-{width}x{height}.png")
                result["viewport"] = {"width": width, "height": height}
                visual_results.append(result)
    payload = {
        "schemaVersion": "1",
        "producer": "web-ui-quality-playwright",
        "browser": browser_name,
        "authentication": {"storageStateSupplied": storage_state is not None, "extraHeadersSupplied": bool(extra_http_headers), "credentialValuesRecorded": False},
        "browserExecuted": bool(records),
        "requestedViewports": [{"width": width, "height": height} for width, height in matrix],
        "observedViewports": [{"width": width, "height": height} for width, height in sorted({((item.get("viewport") or {}).get("width"), (item.get("viewport") or {}).get("height")) for item in records if (item.get("viewport") or {}).get("width") and (item.get("viewport") or {}).get("height")})],
        "status": status,
        "beforeUrl": before.split("?", 1)[0],
        "afterUrl": after.split("?", 1)[0],
        "targetUrl": after.split("?", 1)[0],
        "beforeRef": before_ref,
        "afterRef": after_ref,
        "conditions": [
            f"fresh isolated {browser_name} context per page and viewport",
            "deviceScaleFactor=1",
            f"locale={locale}",
            f"theme={theme}",
            "reducedMotion=reduce",
            "serviceWorkers=block",
            "authenticated storage state reused only when explicitly supplied",
            "no persistent browser profile or downloads",
        ],
        "viewports": [{"width": width, "height": height} for width, height in matrix],
        "records": records,
        "journey": journey,
        "traceRef": trace_ref,
        "visualDiff": visual_results,
        "step10": [],
        "warnings": sorted(set(warnings)),
        "outputDirectory": target_dir.name,
    }
    payload["evidenceDigest"] = digest_json(payload)
    report_path = target_dir / "browser-comparison-report.json"
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    receipt = bind_local_browser_evidence(payload, evidence_ref=f"local-playwright:{payload['evidenceDigest']}")
    return payload, receipt
