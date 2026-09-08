"""Unified productization workflow across static, browser, visual, and expert engines."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .collaboration import export_collaboration_bundle
from .contracts import digest_json
from .core import audit_project
from .external_providers import run_lighthouse
from .playwright_adapter import compare_pages
from .reporting import generate_html_report
from .visual_review import normalize_visual_review, review_prompt
from .visual_judgment import judge_visual_improvement
from .experience_preview import generate_experience_preview
from .experience_evaluator import evaluate_experience


def _status_score(status: str) -> int:
    return {"PASS": 100, "APPROVED": 100, "PASS_WITH_WARNINGS": 72, "COMPUTED": 60, "NOT_REVIEWED": 45, "NOT_RUN": 35, "NOT_VERIFIED": 25, "CHANGES_REQUESTED": 30, "REJECTED": 0, "FAIL": 0}.get(str(status).upper(), 25)


def _professional_findings(browser: Mapping[str, Any], lighthouse: Mapping[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    after_records = [item for item in browser.get("records", []) if item.get("label") == "after"]
    seen: set[str] = set()
    for record in after_records:
        viewport = record.get("viewport", {})
        for item in record.get("renderedQuality", {}).get("findings", []):
            key = f"{item.get('id')}:{viewport.get('width')}x{viewport.get('height')}"
            if key in seen: continue
            seen.add(key)
            findings.append({"id": item.get("id"), "severity": item.get("severity", "P2"), "title": item.get("title"), "count": item.get("count"), "source": "rendered-browser", "viewport": viewport, "samples": item.get("samples", [])})
        axe = record.get("axe", {})
        for violation in axe.get("violations", []):
            impact = str(violation.get("impact") or "moderate")
            severity = "P1" if impact in {"critical", "serious"} else "P2"
            findings.append({"id": f"AXE-{violation.get('id','UNKNOWN').upper()}", "severity": severity, "title": violation.get("help") or violation.get("description"), "source": "axe-core", "impact": impact, "viewport": viewport, "recommendation": violation.get("helpUrl")})
    scores = lighthouse.get("scores", {}) if isinstance(lighthouse, Mapping) else {}
    for category, score in scores.items():
        if score < 50:
            findings.append({"id": f"LH-{category.upper()}", "severity": "P1", "title": f"Lighthouse {category} score is {score}", "source": "lighthouse"})
        elif score < 80:
            findings.append({"id": f"LH-{category.upper()}", "severity": "P2", "title": f"Lighthouse {category} score is {score}", "source": "lighthouse"})
    return findings


def _apply_maturity_hard_gates(
    weighted: int,
    *,
    browser_status: str,
    overall_result: str,
    blocking_findings: Sequence[Mapping[str, Any]],
) -> tuple[str, dict[str, Any]]:
    """Apply release maturity safety gates before the weighted score.

    The score remains useful for ranking a healthy run, but it cannot turn a
    failed, unverified, or P0/P1-blocked run into ``PILOT_READY``.
    """
    browser_status = str(browser_status or "NOT_VERIFIED").upper()
    overall_result = str(overall_result or "FAIL").upper()
    reasons: list[str] = []
    if any(str(item.get("severity") or "").upper() in {"P0", "P1"} for item in blocking_findings):
        reasons.append("P0_OR_P1_FINDING")
    if browser_status == "FAIL":
        reasons.append("BROWSER_FAIL")
    if overall_result == "FAIL":
        reasons.append("OVERALL_RESULT_FAIL")
    if reasons:
        return "NOT_READY", {"status": "BLOCKED", "cap": "NOT_READY", "reasons": reasons}

    unverified_statuses = {"NOT_VERIFIED", "NOT_RUN", "NOT_MEASURED", "NOT_VERIFIED_ENVIRONMENT"}
    if browser_status in unverified_statuses:
        status = "CONTROLLED_BETA" if weighted >= 55 else "EXPERIMENTAL"
        return status, {"status": "CAPPED", "cap": "CONTROLLED_BETA", "reasons": ["BROWSER_NOT_VERIFIED"]}

    status = "PILOT_READY" if weighted >= 75 else "CONTROLLED_BETA" if weighted >= 55 else "EXPERIMENTAL"
    return status, {"status": "PASS", "cap": None, "reasons": []}


def _scorecard(
    static: Mapping[str, Any],
    browser: Mapping[str, Any],
    lighthouse: Mapping[str, Any],
    visual_review: Mapping[str, Any],
    *,
    overall_result: str = "PASS",
    blocking_findings: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    selected = static.get("experienceCore", {}).get("selectedPattern", {})
    if not selected:
        candidates = static.get("uiProductCapability", {}).get("selectedDirection", {}).get("internalCandidates", [])
        selected = candidates[0] if candidates else {}
    product_score = min(100, max(30, int(selected.get("score", 50))))
    if selected.get("confidence") == "low": product_score = min(product_score, 60)
    browser_score = _status_score(str(browser.get("status", "NOT_VERIFIED")))
    journey = browser.get("journey", [])
    journey_states = [item.get("status") for item in journey if item.get("action") or str(item.get("step", "")).startswith("step")]
    journey_score = round(sum(_status_score(str(x)) for x in journey_states) / len(journey_states)) if journey_states else 35
    after_quality = [item.get("renderedQuality", {}).get("overallScore") for item in browser.get("records", []) if item.get("label") == "after" and item.get("renderedQuality", {}).get("overallScore") is not None]
    rendered_score = round(sum(after_quality) / len(after_quality)) if after_quality else 35
    if visual_review.get("overallScore") is not None:
        visual_score = round((rendered_score + int(visual_review["overallScore"])) / 2)
        visual_status = visual_review.get("status")
    else:
        visual_score = rendered_score
        visual_status = "NOT_REVIEWED"
    engine_statuses = [lighthouse.get("status", "NOT_RUN")]
    axe_statuses = [item.get("axe", {}).get("status", "NOT_RUN") for item in browser.get("records", []) if item.get("label") == "after"]
    engine_statuses.extend(axe_statuses)
    engine_score = round(sum(_status_score(str(x)) for x in engine_statuses) / len(engine_statuses)) if engine_statuses else 35
    weighted = round(product_score*.24 + browser_score*.20 + journey_score*.18 + visual_score*.23 + engine_score*.15)
    maturity, maturity_gate = _apply_maturity_hard_gates(
        weighted,
        browser_status=str(browser.get("status") or "NOT_VERIFIED"),
        overall_result=overall_result,
        blocking_findings=blocking_findings,
    )
    return {
        "productDecision": {"score": product_score, "status": selected.get("confidence", "unknown")},
        "browser": {"score": browser_score, "status": browser.get("status", "NOT_VERIFIED")},
        "journey": {"score": journey_score, "status": "PASS" if journey_score >= 90 else "PASS_WITH_WARNINGS" if journey_score >= 60 else "NOT_VERIFIED"},
        "renderedQuality": {"score": visual_score, "status": visual_status},
        "professionalEngines": {"score": engine_score, "status": "PASS" if engine_score >= 90 else "PASS_WITH_WARNINGS" if engine_score >= 60 else "NOT_VERIFIED"},
        "overall": {"score": weighted, "status": maturity},
        "maturityGate": maturity_gate,
    }


def _experience_metric_pair(browser: Mapping[str, Any], lighthouse: Mapping[str, Any], visual_review: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    before_records = [item for item in browser.get("records", []) if item.get("label") == "before"]
    after_records = [item for item in browser.get("records", []) if item.get("label") == "after"]
    def aggregate(records: list[Mapping[str, Any]]) -> dict[str, Any]:
        quality = [item.get("renderedQuality", {}).get("overallScore") for item in records if item.get("renderedQuality", {}).get("overallScore") is not None]
        issues = sum(len(item.get("renderedQuality", {}).get("findings", [])) for item in records)
        overflow = sum(bool(item.get("horizontalOverflow")) for item in records)
        passes = sum(item.get("status") == "PASS" for item in records)
        axe_scores = []
        for item in records:
            axe = item.get("axe", {})
            if axe.get("status") == "PASS": axe_scores.append(100)
            elif axe.get("status") == "PASS_WITH_WARNINGS": axe_scores.append(70)
            elif axe.get("status") == "FAIL": axe_scores.append(20)
        return {
            "criticalIssues": issues, "horizontalOverflowCount": overflow,
            "mobilePassRate": round(passes / len(records) * 100, 2) if records else None,
            "projectConsistency": round(sum(quality) / len(quality), 2) if quality else None,
            "accessibilityScore": round(sum(axe_scores) / len(axe_scores), 2) if axe_scores else None,
        }
    before, after = aggregate(before_records), aggregate(after_records)
    scores = lighthouse.get("scores", {}) if isinstance(lighthouse, Mapping) else {}
    if scores.get("performance") is not None: after["performanceScore"] = scores.get("performance")
    if visual_review.get("overallScore") is not None: after["visualPreference"] = visual_review.get("overallScore")
    journey = [item for item in browser.get("journey", []) if item.get("action")]
    if journey:
        after["steps"] = len(journey)
        after["errors"] = sum(item.get("status") != "PASS" for item in journey)
        after["stateCoverage"] = round(sum(item.get("status") == "PASS" for item in journey) / len(journey) * 100, 2)
    return before, after


def run_full_audit(
    project_root: str | Path,
    before_url: str,
    after_url: str,
    *,
    output_dir: str | Path,
    business_context: Mapping[str, Any] | None = None,
    project_reference: Mapping[str, Any] | None = None,
    journey_steps: Sequence[Mapping[str, Any]] | None = None,
    viewports: Sequence[Sequence[int]] | None = None,
    storage_state: str | Path | Mapping[str, Any] | None = None,
    extra_http_headers: Mapping[str, str] | None = None,
    allow_origins: Iterable[str] = (),
    approved_action_ids: Iterable[str] = (),
    axe_script: str | Path | None = None,
    run_lighthouse_engine: bool = False,
    lighthouse_executable: str | Path | None = None,
    visual_review: Mapping[str, Any] | None = None,
    browser_name: str = "chromium",
    locale: str = "zh-CN",
    theme: str = "light",
    ignore_https_errors: bool = False,
    trace: bool = True,
    visual_diff: bool = True,
    browser_executable: str | Path | None = None,
) -> dict[str, Any]:
    out = Path(output_dir).expanduser().resolve(); out.mkdir(parents=True, exist_ok=True)
    browser_dir = out / "browser"
    browser, receipt = compare_pages(
        before_url, after_url, output_dir=browser_dir, viewports=viewports, allow_origins=allow_origins,
        browser_name=browser_name, journey_steps=journey_steps, storage_state=storage_state,
        extra_http_headers=extra_http_headers, axe_script=axe_script, approved_action_ids=approved_action_ids,
        locale=locale, theme=theme, ignore_https_errors=ignore_https_errors, trace=trace, visual_diff=visual_diff,
        browser_executable=browser_executable,
    )
    static = audit_project(project_root, project_reference=project_reference, trusted_browser_evidence=receipt, business_context=business_context)
    lighthouse = run_lighthouse(after_url, output_dir=out / "lighthouse", executable=lighthouse_executable) if run_lighthouse_engine else {"status": "NOT_RUN", "reason": "not requested"}
    qualitative = normalize_visual_review(visual_review)
    visual_judgment = judge_visual_improvement(browser, qualitative)
    before_metrics, after_metrics = _experience_metric_pair(browser, lighthouse, qualitative)
    experience_evaluation = evaluate_experience(before_metrics, after_metrics, visual_review=qualitative)
    professional = {"lighthouse": lighthouse, "axe": {"status": "COLLECTED_IN_BROWSER_RECORDS" if axe_script else "NOT_RUN"}, "renderedQuality": {"status": "COLLECTED_IN_BROWSER_RECORDS"}, "visualJudgment": visual_judgment}
    professional_findings = _professional_findings(browser, lighthouse)
    blocking_findings = [
        item for item in list(static.get("findings", [])) + professional_findings
        if str(item.get("severity") or "").upper() in {"P0", "P1"}
    ]
    blocking = bool(blocking_findings)
    overall = "FAIL" if blocking or browser.get("status") == "FAIL" or qualitative.get("status") in {"REJECTED", "CHANGES_REQUESTED"} else "PASS_WITH_WARNINGS" if professional_findings or lighthouse.get("status") in {"NOT_RUN", "PASS_WITH_WARNINGS"} or qualitative.get("status") == "NOT_REVIEWED" else "PASS"
    scorecard = _scorecard(
        static,
        browser,
        lighthouse,
        qualitative,
        overall_result=overall,
        blocking_findings=blocking_findings,
    )
    report = dict(static)
    report.update({
        "schemaVersion": "2.0", "overallResult": overall, "maturity": scorecard["overall"]["status"],
        "browserComparisonReport": browser, "professionalEngines": professional,
        "professionalFindings": professional_findings, "visualReview": qualitative,
        "visualJudgment": visual_judgment,
        "experienceEvaluation": experience_evaluation,
        "visualReviewPrompt": review_prompt({**static, "browserComparisonReport": browser}),
        "scorecard": scorecard,
    })
    report["artifacts"] = {
        "unifiedReport": "unified-report.json",
        "workbench": "workbench/index.html",
        "sarif": "collaboration/web-ui-quality.sarif",
        "githubSummary": "collaboration/github-step-summary.md",
        "reviewState": "collaboration/review-state.json",
        "experiencePreview": "experience-preview/index.html",
    }
    generate_experience_preview(report.get("experienceCore", {}), out / "experience-preview")
    report["reportDigest"] = digest_json({k: v for k, v in report.items() if k != "reportDigest"})
    report_path = out / "unified-report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    generate_html_report(report, output_dir=out / "workbench")
    export_collaboration_bundle(report, out / "collaboration")
    return report
