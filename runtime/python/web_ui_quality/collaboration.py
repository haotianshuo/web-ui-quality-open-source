"""Team hand-off exports: SARIF, GitHub summary, and review bundle."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .contracts import digest_json
from .review_workflow import initialize_review

_LEVEL = {"P0": "error", "P1": "error", "P2": "warning", "P3": "note"}


def to_sarif(report: Mapping[str, Any]) -> dict[str, Any]:
    findings = list(report.get("findings", [])) + list(report.get("professionalFindings", []))
    rules: dict[str, Any] = {}
    results: list[dict[str, Any]] = []
    for item in findings:
        rule_id = str(item.get("id") or "WUQ-UNKNOWN")
        rules.setdefault(rule_id, {"id": rule_id, "shortDescription": {"text": str(item.get("title") or rule_id)}, "help": {"text": str(item.get("recommendation") or "Review the generated Web UI Quality report.")}})
        location = None
        evidence = item.get("evidence")
        if isinstance(evidence, list) and evidence and isinstance(evidence[0], Mapping):
            first = evidence[0]; path = first.get("path"); line = first.get("line")
            if path:
                region = {"startLine": max(1, int(line or 1))}
                location = {"physicalLocation": {"artifactLocation": {"uri": str(path)}, "region": region}}
        result = {"ruleId": rule_id, "level": _LEVEL.get(str(item.get("severity")), "warning"), "message": {"text": str(item.get("title") or rule_id)}}
        if location: result["locations"] = [location]
        results.append(result)
    return {"$schema": "https://json.schemastore.org/sarif-2.1.0.json", "version": "2.1.0", "runs": [{"tool": {"driver": {"name": "web-ui-quality", "informationUri": "https://example.invalid/web-ui-quality", "rules": list(rules.values())}}, "results": results}]}


def github_summary(report: Mapping[str, Any]) -> str:
    result = report.get("overallResult") or report.get("verificationReport", {}).get("result", "NOT_VERIFIED")
    score = report.get("scorecard", {}).get("overall", {})
    score_value = score.get("score", "-") if isinstance(score, Mapping) else score
    findings = list(report.get("findings", [])) + list(report.get("professionalFindings", []))
    lines = ["# Web UI Quality", "", f"**Result:** `{result}`  ", f"**Overall score:** `{score_value}`", "", "## Findings", "", "| Severity | Rule | Issue |", "|---|---|---|"]
    for item in findings[:50]:
        title = str(item.get("title") or "").replace("|", "\\|")
        lines.append(f"| {item.get('severity','')} | `{item.get('id','')}` | {title} |")
    lines += ["", "## Artifacts", "", "- Open `workbench/index.html` for before/after, journey, professional engines, and review history.", "- Upload `web-ui-quality.sarif` to GitHub code scanning when enabled."]
    return "\n".join(lines) + "\n"


def export_collaboration_bundle(report: Mapping[str, Any], output_dir: str | Path) -> dict[str, str]:
    out = Path(output_dir); out.mkdir(parents=True, exist_ok=True)
    sarif = to_sarif(report); sarif_path = out / "web-ui-quality.sarif"; sarif_path.write_text(json.dumps(sarif, ensure_ascii=False, indent=2), encoding="utf-8")
    summary_path = out / "github-step-summary.md"; summary_path.write_text(github_summary(report), encoding="utf-8")
    review = initialize_review(str(report.get("reportDigest") or digest_json(report)))
    review_path = out / "review-state.json"; review_path.write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"sarif": sarif_path.name, "githubSummary": summary_path.name, "reviewState": review_path.name}
