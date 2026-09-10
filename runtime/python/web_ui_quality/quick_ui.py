"""Screenshot-first UI inspection with a deliberately small output surface."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .contracts import ContractViolation, digest_json
from .error_classifier import classify_record
from .user_language import status_label
from .playwright_adapter import _capture_one, _normalize_viewports, _origin, _safe_url, _viewport_summary
from .release_info import PACKAGE_VERSION
from .repair_recipe import build_repair_recipes
from .condition_registry import STANDARD_VIEWPORTS
from .browser_locator import resolve_browser_executable


QUICK_UI_VIEWPORTS: tuple[tuple[int, int], ...] = STANDARD_VIEWPORTS
_SEVERITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}

_GEOMETRY_RULES: tuple[tuple[str, str, str, str], ...] = (
    ("UI-FIXED-OCCLUSION", "P1", "固定或吸顶元素遮挡了可操作控件", "fixedOcclusions"),
    ("UI-ELEMENT-OVERLAP", "P1", "主要内容块发生明显重叠", "overlaps"),
    ("UI-DIALOG-FIT", "P1", "弹窗或抽屉超出当前视口", "dialogs"),
    ("UI-NAV-OVERFLOW", "P1", "导航在当前宽度发生裁切或溢出", "navigation"),
)

_RECOMMENDATIONS = {
    "RENDER-OVERFLOW": "检查固定宽度、min-width、负边距和未换行内容，让布局在该断点真正重组。",
    "RENDER-CLIPPED-CONTENT": "移除错误的固定高度或 overflow:hidden，并为长文本和动态内容预留伸缩空间。",
    "RENDER-SMALL-TARGET": "将独立按钮和触控控件的可点击区域统一到至少 44px。",
    "RENDER-OVERSIZED-CONTROL": "收敛控件高度、字号和内边距，避免按钮像容器、标签像注释。",
    "RENDER-INCONSISTENT-CONTROL-HEIGHT": "让同一工具栏或表单行中的输入框、按钮和选择器使用同一尺寸令牌。",
    "RENDER-ICON-TEXT-IMBALANCE": "统一图标盒尺寸并与标签字号、间距建立稳定比例。",
    "RENDER-MULTIPLE-PRIMARY-ACTIONS": "每个视图保留一个最强主操作，其余降为次级或文字操作。",
    "UI-FIXED-OCCLUSION": "修正 fixed/sticky 层的占位、z-index 与底部安全区，保证目标始终可点。",
    "UI-ELEMENT-OVERLAP": "定位冲突的定位上下文、网格轨道或负间距，并在当前断点重新排布。",
    "UI-DIALOG-FIT": "给弹窗设置视口内最大尺寸、内部滚动和移动端边距。",
    "UI-NAV-OVERFLOW": "在窄屏切换为折叠菜单、横向滚动标签或更合适的分组，不要硬缩桌面导航。",
    "UI-ALIGNMENT-DRIFT": "收敛页面容器、标题、工具栏和内容区的左边界令牌。",
    "UI-HTTP-FAILURE": "根据真实 HTTP 状态或运行时错误恢复页面访问后，再进行 UI 验证。",
}


def _viewport_label(record: Mapping[str, Any]) -> str:
    viewport = record.get("viewport") or {}
    return f"{int(viewport.get('width') or 0)}x{int(viewport.get('height') or 0)}"


def summarize_top_ui_issues(records: Sequence[Mapping[str, Any]], *, limit: int = 3) -> list[dict[str, Any]]:
    """Merge repeated rendered/geometry evidence and return only the visible Top N."""

    aggregated: dict[str, dict[str, Any]] = {}

    def add(rule_id: str, severity: str, title: str, record: Mapping[str, Any], samples: Sequence[Any]) -> None:
        viewport = _viewport_label(record)
        runtime_boundaries = {"POLICY_BLOCKED", "CONNECTION_REFUSED", "DNS_FAILURE", "TLS_FAILURE", "AUTH_REQUIRED", "NAVIGATION_TIMEOUT", "PAGE_CRASHED", "BROWSER_PROVIDER_MISSING", "UNKNOWN_RUNTIME_FAILURE"}
        user_label = "暂时无法确认" if rule_id in runtime_boundaries else "现在会出错" if severity in {"P0", "P1"} else "用起来别扭" if severity == "P2" else "建议考虑补充"
        issue = aggregated.setdefault(
            rule_id,
            {
                "id": rule_id,
                "severity": severity,
                "userLabel": user_label,
                "title": title,
                "userImpact": "当前运行条件不足以判断页面本身是否有问题。" if user_label == "暂时无法确认" else "可能阻断或显著增加用户完成当前任务的成本。" if severity in {"P0", "P1"} else "会增加理解、扫描或操作成本。",
                "confidence": "high" if severity in {"P0", "P1"} else "medium",
                "count": 0,
                "viewports": [],
                "samples": [],
                "recommendation": _RECOMMENDATIONS.get(rule_id, "回到对应元素的布局与组件样式，修复根因后按相同视口复验。"),
            },
        )
        issue["count"] += max(1, len(samples))
        if viewport not in issue["viewports"]:
            issue["viewports"].append(viewport)
        for sample in samples[:3]:
            if len(issue["samples"]) >= 6:
                break
            issue["samples"].append({"viewport": viewport, "evidence": sample})

    health_titles = {
        "RUNTIME_BROKEN": ("PAGE-RUNTIME-BROKEN", "P0", "页面运行时已经损坏"),
        "AUTH_REQUIRED": ("PAGE-AUTH-REQUIRED", "P0", "当前看到的是认证页面，不是真实业务页面"),
        "RESTRICTED_RENDER": ("PAGE-RESTRICTED-RENDER", "P0", "必要资源被阻止，页面不具代表性"),
        "DATA_NOT_READY": ("PAGE-DATA-NOT-READY", "P0", "页面仍停留在加载或骨架状态"),
        "TASK_FAILED": ("PAGE-TASK-FAILED", "P0", "安全任务探针未完成或未恢复"),
        "NOT_VERIFIED": ("PAGE-NOT-VERIFIED", "P1", "当前条件不足以验证真实页面"),
        "SIMULATED_PREVIEW": ("PAGE-SIMULATED", "P1", "当前证据来自模拟预览，不是真实产品"),
    }
    for record in records:
        page_status = str((record.get("pageHealth") or {}).get("pageStatus") or "")
        if page_status in health_titles:
            rid, severity, title = health_titles[page_status]
            add(rid, severity, title, record, [record.get("pageHealth") or {}])
        http_status = record.get("httpStatus")
        if record.get("status") == "FAIL":
            classified = classify_record(record)
            if classified:
                rule_id = str(classified.get("category") or "UNKNOWN_RUNTIME_FAILURE")
                recommendation = "；".join(str(item) for item in classified.get("recoveryActions", []))
                _RECOMMENDATIONS.setdefault(rule_id, recommendation or "查看原始错误并恢复运行环境后重试。")
                add(rule_id, "P0", str(classified.get("userMessage") or "页面验证失败"), record, [classified])
            elif http_status is None or not 200 <= int(http_status) < 300:
                add("UI-HTTP-FAILURE", "P0", "页面没有返回可用于验收的成功响应", record, [{"httpStatus": http_status, "error": record.get("errorMessage")}])

        for finding in (record.get("renderedQuality") or {}).get("findings", []):
            add(
                str(finding.get("id") or "RENDER-UNKNOWN"),
                str(finding.get("severity") or "P2"),
                str(finding.get("title") or "真实渲染存在 UI 异常"),
                record,
                list(finding.get("samples") or [{}]),
            )

        rows = (record.get("experienceGeometry") or {}).get("viewports") or []
        if not rows:
            continue
        geometry = rows[0]
        for rule_id, severity, title, field in _GEOMETRY_RULES:
            evidence = list(geometry.get(field) or [])
            if field == "dialogs":
                evidence = [item for item in evidence if item.get("offscreen") or item.get("oversized")]
            elif field == "navigation":
                evidence = [item for item in evidence if item.get("overflow")]
            if evidence:
                add(rule_id, severity, title, record, evidence)
        deviation = geometry.get("alignmentDeviationPx")
        if isinstance(deviation, (int, float)) and deviation >= 12:
            add("UI-ALIGNMENT-DRIFT", "P2", "页面主要内容的对齐基线偏差明显", record, [{"alignmentDeviationPx": deviation}])

    issues = list(aggregated.values())
    health_rank = {"PAGE-RUNTIME-BROKEN": 0, "PAGE-AUTH-REQUIRED": 1, "PAGE-RESTRICTED-RENDER": 2, "PAGE-DATA-NOT-READY": 3, "PAGE-TASK-FAILED": 4, "PAGE-NOT-VERIFIED": 5, "PAGE-SIMULATED": 5}
    for issue in issues:
        issue["viewports"].sort(key=lambda value: (not value.startswith("390x"), value))
        severity = str(issue.get("severity") or "P3")
        task_blockage = 5 if str(issue.get("id")) in health_rank and health_rank[str(issue.get("id"))] <= 4 else 4 if severity == "P0" else 3 if severity == "P1" else 1
        viewport_breadth = min(3, len(issue.get("viewports") or []))
        journey_criticality = 5 if str(issue.get("id")) in {"PAGE-TASK-FAILED", "UI-FIXED-OCCLUSION", "UI-DIALOG-FIT", "UI-HTTP-FAILURE"} else 3 if severity in {"P0", "P1"} else 1
        recovery_cost = 5 if severity == "P0" else 4 if severity == "P1" else 2 if severity == "P2" else 1
        evidence_quality = 5 if issue.get("confidence") == "high" else 3 if issue.get("confidence") == "medium" else 1
        regression_risk = 4 if str(issue.get("id")) in {"PAGE-RUNTIME-BROKEN", "PAGE-RESTRICTED-RENDER", "PAGE-TASK-FAILED"} else 3 if severity in {"P0", "P1"} else 1
        score = task_blockage * 30 + journey_criticality * 15 + viewport_breadth * 10 + recovery_cost * 8 + evidence_quality * 6 + regression_risk * 5
        issue["rankingFactors"] = {
            "taskBlockage": task_blockage,
            "severity": severity,
            "viewportBreadth": viewport_breadth,
            "journeyCriticality": journey_criticality,
            "recoveryCost": recovery_cost,
            "confidence": issue.get("confidence"),
            "evidenceQuality": evidence_quality,
            "regressionRisk": regression_risk,
            "score": score,
        }
    issues.sort(
        key=lambda issue: (
            health_rank.get(str(issue["id"]), 20),
            -int((issue.get("rankingFactors") or {}).get("score") or 0),
            _SEVERITY_ORDER.get(str(issue["severity"]), 9),
            -len(issue.get("viewports") or []),
            str(issue["id"]),
        )
    )
    return issues[: max(0, int(limit))]


def _render_html(report: Mapping[str, Any]) -> str:
    status = escape(status_label(report.get("status")))
    issues = list(report.get("topIssues") or [])
    issue_markup = "".join(
        f"""<li><div class="issue-head"><span class="label">{escape(str(item.get('userLabel') or '建议考虑补充'))}</span><strong>{escape(str(item['title']))}</strong></div>
        <p class="impact">{escape(str(item.get('userImpact') or ''))}</p>
        <p><b>建议：</b>{escape(str(item['recommendation']))}</p>
        <small>视口：{escape(', '.join(item['viewports']))} · 证据 {int(item['count'])} 处 · 可信度 {escape(str(item.get('confidence') or 'unknown'))}</small>
        <details><summary>查看技术证据</summary><pre>{escape(json.dumps(item.get('samples') or [], ensure_ascii=False, indent=2))}</pre></details></li>"""
        for item in issues
    ) or "<li class=empty>没有发现高置信度的明显 UI 问题；这不等于已经完成完整商业验收。</li>"
    cards = "".join(
        f"""<figure><div class="shot"><img src="{escape(str(item.get('screenshotRef') or ''))}" alt="{escape(_viewport_label(item))} 视口截图"></div>
        <figcaption><strong>{escape(_viewport_label(item))}</strong><span>{escape(status_label(item.get('status')))}</span></figcaption>
        {f'<a class="full-link" href="{escape(str(item.get("fullPageScreenshotRef")))}">查看整页截图</a>' if item.get('fullPageScreenshotRef') else ''}</figure>"""
        for item in report.get("records", []) if item.get("screenshotRef")
    )
    boundaries = "".join(f"<li>{escape(str(item))}</li>" for item in report.get("notRunByDefault", []))
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Web UI Quality {escape(str(report.get('packageVersion') or ''))} · 页面检查</title><style>
:root{{--bg:#f5f6f8;--card:#fff;--ink:#17191c;--muted:#667085;--line:#e4e7ec;--accent:#166b4f}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.6 system-ui,-apple-system,"Segoe UI",sans-serif}}
main{{max-width:1180px;margin:auto;padding:36px 24px 56px}}header{{display:flex;align-items:flex-end;justify-content:space-between;gap:20px;margin-bottom:24px}}
h1{{font-size:32px;line-height:1.15;margin:0 0 8px}}header p{{margin:0;color:var(--muted)}}.status{{padding:7px 12px;border:1px solid var(--line);border-radius:999px;background:#fff;font-weight:700}}
.panel{{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:22px;margin:18px 0;box-shadow:0 8px 28px rgba(16,24,40,.05)}}h2{{font-size:20px;margin:0 0 14px}}
ol{{margin:0;padding-left:22px}}li{{padding:12px 0 14px}}li+li{{border-top:1px solid var(--line)}}li p{{margin:5px 0;color:#344054}}small{{color:var(--muted)}}
.issue-head{{display:flex;align-items:center;gap:9px}}.label{{font-size:12px;padding:2px 7px;border-radius:6px;background:#fff1f0;color:#b42318}}.impact{{font-weight:650}}
.screens{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px;align-items:start}}figure{{margin:0}}.shot{{overflow:auto;max-height:680px;border:1px solid var(--line);border-radius:12px;background:#eef0f3}}img{{display:block;width:100%;height:auto}}
figcaption{{display:flex;justify-content:space-between;margin-top:8px;color:var(--muted)}}.full-link{{display:inline-block;margin-top:5px;color:var(--accent);font-weight:650}}.empty{{list-style:none;margin-left:-22px;color:var(--muted)}}details{{margin-top:8px}}pre{{white-space:pre-wrap;background:#f7f8fa;padding:12px;border-radius:10px;overflow:auto}}
@media(max-width:900px){{.screens{{grid-template-columns:1fr}}}}@media(max-width:760px){{main{{padding:24px 14px}}header{{align-items:flex-start;flex-direction:column}}h1{{font-size:27px}}.panel{{padding:16px;border-radius:14px}}}}
</style></head><body><main><header><div><p>Web UI Quality {escape(str(report.get('packageVersion') or ''))}</p><h1>真实页面体验检查</h1><p>{escape(str(report.get('url') or ''))}</p></div><div class="status">{status}</div></header>
<section class="panel"><h2>最值得先处理的 {len(issues)} 项</h2><ol>{issue_markup}</ol></section>
<section class="panel"><h2>手机 / 平板 / 桌面真实视口截图</h2><div class="screens">{cards}</div></section>
<section class="panel"><h2>本次未默认执行</h2><ul>{boundaries}</ul></section>
</main></body></html>"""


def run_quick_ui(
    url: str,
    *,
    output_dir: str | Path,
    viewports: Sequence[Sequence[int]] | None = None,
    locale: str = "zh-CN",
    theme: str = "light",
    allow_origins: Iterable[str] = (),
    timeout_ms: int = 15_000,
    browser_name: str = "chromium",
    storage_state: str | Path | Mapping[str, Any] | None = None,
    extra_http_headers: Mapping[str, str] | None = None,
    ignore_https_errors: bool = False,
    browser_executable: str | Path | None = None,
    approved_requests: Sequence[Mapping[str, str]] = (),
) -> dict[str, Any]:
    """Capture one live page at mobile, tablet, and desktop sizes."""

    target = _safe_url(url, "url")
    if theme not in {"light", "dark", "no-preference"}:
        raise ContractViolation("BROWSER_THEME_INVALID", ["$.theme: unsupported"])
    matrix = _normalize_viewports(viewports or QUICK_UI_VIEWPORTS)
    output = Path(output_dir).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    origins = {_origin(target)}
    for value in allow_origins:
        origins.add(_origin(_safe_url(str(value), "allowOrigins")))

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as error:
        raise ContractViolation(
            "PLAYWRIGHT_UNAVAILABLE",
            ["$: quick-ui needs the optional browser dependency; install web-ui-quality[browser]"],
        ) from error

    screenshots_dir = output / "screenshots"
    evidence_dir = output / "evidence"
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    evidence_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
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
            for width, height in matrix:
                label = "mobile" if width <= 480 else "desktop" if width >= 1200 else f"viewport-{width}x{height}"
                records.append(
                    _capture_one(
                        browser,
                        url=target,
                        label=label,
                        viewport=(width, height),
                        output_dir=screenshots_dir,
                        locale=locale,
                        theme=theme,
                        allowed_origins=origins,
                        primary_origins={_origin(target)},
                        timeout_ms=timeout_ms,
                        storage_state=storage_state,
                        extra_http_headers=extra_http_headers,
                        ignore_https_errors=ignore_https_errors,
                        persist_dom_sidecars=False,
                        approved_requests=approved_requests,
                    )
                )
        finally:
            browser.close()

    for record in records:
        if record.get("screenshotRef"):
            record["screenshotRef"] = f"screenshots/{record['screenshotRef']}"
        if record.get("fullPageScreenshotRef"):
            record["fullPageScreenshotRef"] = f"screenshots/{record['fullPageScreenshotRef']}"
        classified = classify_record(record)
        if classified:
            record["failureClassification"] = classified

    top_issues = summarize_top_ui_issues(records, limit=3)
    page_health_rows = [item.get("pageHealth") for item in records if item.get("pageHealth")]
    health_priority = {"RUNTIME_BROKEN": 0, "AUTH_REQUIRED": 1, "RESTRICTED_RENDER": 2, "DATA_NOT_READY": 3, "TASK_FAILED": 4, "NOT_VERIFIED": 5, "SIMULATED_PREVIEW": 5, "VISUAL_FINDINGS": 6, "PASS": 7, "REAL_PAGE_READY": 7}
    page_health = min(page_health_rows, key=lambda row: health_priority.get(str(row.get("pageStatus")), 99)) if page_health_rows else {"pageStatus": "NOT_VERIFIED", "browserExecuted": False, "visualCanOverride": False}
    blocking_health = str(page_health.get("pageStatus")) in {"RUNTIME_BROKEN", "AUTH_REQUIRED", "RESTRICTED_RENDER", "DATA_NOT_READY", "TASK_FAILED"}
    status = "FAIL" if blocking_health or any(item.get("status") == "FAIL" for item in records) else "NOT_VERIFIED" if str(page_health.get("pageStatus")) in {"NOT_VERIFIED", "SIMULATED_PREVIEW"} or any(item.get("status") == "NOT_VERIFIED" for item in records) else "PASS_WITH_WARNINGS" if top_issues or any(item.get("status") == "PASS_WITH_WARNINGS" for item in records) else "PASS"
    report: dict[str, Any] = {
        "schemaVersion": "1",
        "producer": "web-ui-quality-quick-ui",
        "packageVersion": PACKAGE_VERSION,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "url": target.split("?", 1)[0],
        "viewports": [{"width": width, "height": height} for width, height in matrix],
        "viewportNormalization": _viewport_summary(records),
        "pageHealth": page_health,
        "topIssues": top_issues,
        "repairRecipes": build_repair_recipes(top_issues, confirmed_ids=[str(item.get("id")) for item in top_issues]),
        "records": records,
        "scope": "three-viewport viewport-and-full-page screenshot UI geometry, component proportion, responsive composition, runtime health, and representative-render checks",
        "notRunByDefault": ["product discovery", "3 redesign candidates", "security audit", "axe", "Lighthouse", "outcome measurement"],
    }
    report["reportDigest"] = digest_json(report)
    report_json = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    report_html = _render_html(report)
    (evidence_dir / "quick-ui-report.json").write_text(report_json, encoding="utf-8")
    (output / "quick-ui-report.json").write_text(report_json, encoding="utf-8")
    (output / "quick-ui-report.html").write_text(report_html, encoding="utf-8")
    (output / "index.html").write_text(report_html, encoding="utf-8")
    summary_lines = ["# 页面体验检查", "", f"- 状态：{status_label(status)}", f"- 页面：{target.split('?', 1)[0]}", "", "## 最重要的问题"]
    for issue in top_issues:
        summary_lines.append(f"- **{issue.get('userLabel')}：{issue.get('title')}** — {issue.get('recommendation')}")
    summary_lines.extend(["", "## 当前边界", "", "- 未默认执行产品发现、多方案重设计、安全专项、Lighthouse 或用户结果测量。", "- 技术证据位于 `evidence/`，截图位于 `screenshots/`。"])
    (output / "summary.md").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
    report["open"] = "index.html"
    report["summary"] = "summary.md"
    return report


__all__ = ["QUICK_UI_VIEWPORTS", "run_quick_ui", "summarize_top_ui_issues"]
