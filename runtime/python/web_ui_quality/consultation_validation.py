"""Honest, dependency-free acceptance checks for product consultation output."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from html import escape
from pathlib import Path
from typing import Any

from .release_info import release_identity


def _check(check_id: str, label: str, passed: bool, detail: str) -> dict[str, Any]:
    return {
        "id": check_id,
        "label": label,
        "status": "PASS" if passed else "FAIL",
        "detail": detail,
    }


def validate_consultation(
    report: Mapping[str, Any],
    *,
    required_artifacts: Sequence[str] = (),
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Validate the consultation contract without implying implementation proof."""
    problems = report.get("topProblems")
    journey = report.get("journey") if isinstance(report.get("journey"), Mapping) else {}
    stages = journey.get("stages") if isinstance(journey.get("stages"), Sequence) else []
    transformation = report.get("transformation") if isinstance(report.get("transformation"), Mapping) else {}
    variants = transformation.get("variants") if isinstance(transformation.get("variants"), Sequence) else []
    handoff = report.get("handoff") if isinstance(report.get("handoff"), Mapping) else {}
    claims = report.get("claims") if isinstance(report.get("claims"), Mapping) else {}
    metrics = (
        report.get("measurementLoop", {}).get("metrics", [])
        if isinstance(report.get("measurementLoop"), Mapping)
        else []
    )
    artifact_root = Path(output_dir).resolve() if output_dir is not None else None
    missing = [
        relative for relative in required_artifacts
        if artifact_root is None or not (artifact_root / relative).is_file()
    ]
    recommended = [item for item in variants if isinstance(item, Mapping) and item.get("recommended") is True]
    metric_claims_clean = all(
        isinstance(item, Mapping) and item.get("baseline") is None and item.get("target") is None
        for item in metrics
    )
    checks = [
        _check("CONSULT-001", "产品问题已收敛", isinstance(problems, Sequence) and len(problems) == 3, "应输出恰好三个按影响排序的问题。"),
        _check("CONSULT-002", "关键旅程完整", len(stages) == 4, "应输出四阶段关键旅程。"),
        _check("CONSULT-003", "方向可决策", 2 <= len(variants) <= 3 and len(recommended) == 1, "应提供一个推荐方向和至少一个真实备选方向；第三个方向仅在形成独立策略时提供。"),
        _check("CONSULT-004", "源码权限边界明确", handoff.get("sourceWriteAuthorized") is False and handoff.get("explicitConfirmationRequired") is True, "咨询产物不得携带源码写入授权。"),
        _check("CONSULT-005", "结果声明诚实", claims.get("measuredBusinessOutcome") is False and claims.get("verifiedProductionBeforeAfter") is False and metric_claims_clean, "未建立基线或生产证据时不得声明业务提升或真实 Before/After。"),
        _check("CONSULT-006", "交付物齐全", not missing, "缺失：" + ", ".join(missing) if missing else "所有声明的咨询交付物均已生成。"),
    ]
    passed = all(item["status"] == "PASS" for item in checks)
    return {
        "schemaVersion": "1",
        "generator": release_identity(),
        "status": "PASS" if passed else "FAIL",
        "scope": "CONSULTATION_OUTPUT_ONLY",
        "checks": checks,
        "readiness": {
            "consultation": "PASS" if passed else "FAIL",
            "implementation": "NOT_RUN",
            "productionBrowserValidation": "NOT_VERIFIED",
            "commercialGA": "NOT_ESTABLISHED",
        },
        "claimBoundary": "This report validates consultation completeness only; it is not source implementation, production Browser, legal, or business-outcome evidence.",
    }


def render_validation_html(validation: Mapping[str, Any]) -> str:
    """Render the acceptance result as a self-contained stakeholder page."""
    rows = "".join(
        "<tr><td>{}</td><td>{}</td><td><span class='{}'>{}</span></td><td>{}</td></tr>".format(
            escape(str(item.get("id", ""))),
            escape(str(item.get("label", ""))),
            "pass" if item.get("status") == "PASS" else "fail",
            escape(str(item.get("status", ""))),
            escape(str(item.get("detail", ""))),
        )
        for item in validation.get("checks", [])
        if isinstance(item, Mapping)
    )
    readiness = validation.get("readiness") if isinstance(validation.get("readiness"), Mapping) else {}
    cards = "".join(
        f"<article><span>{escape(str(key))}</span><b>{escape(str(value))}</b></article>"
        for key, value in readiness.items()
    )
    status = escape(str(validation.get("status", "FAIL")))
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Consultation validation · {status}</title><style>
:root{{--ink:#17211d;--muted:#65716b;--line:#dce5df;--paper:#f4f7f5;--brand:#166b4f;--ok:#dcefe5;--bad:#ffe1dc;font-family:Inter,"Segoe UI","PingFang SC",sans-serif}}*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink)}}main{{max-width:1120px;margin:auto;padding:clamp(22px,5vw,64px) 20px 80px}}header{{background:#17211d;color:white;border-radius:24px;padding:clamp(28px,5vw,54px)}}header p{{color:#bed0c7;max-width:760px;line-height:1.65}}h1{{font-size:clamp(34px,6vw,66px);margin:8px 0;letter-spacing:-.05em}}.status{{display:inline-block;background:#c9f0da;color:#0d513a;border-radius:99px;padding:7px 11px;font-weight:800;font-size:12px}}.cards{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:18px 0}}article{{background:white;border:1px solid var(--line);border-radius:16px;padding:17px}}article span{{display:block;color:var(--muted);font-size:12px;margin-bottom:10px}}article b{{font-size:14px}}section{{background:white;border:1px solid var(--line);border-radius:20px;overflow:auto}}table{{border-collapse:collapse;width:100%;min-width:760px}}th,td{{padding:15px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}}th{{font-size:12px;color:var(--muted)}}td{{font-size:13px;line-height:1.55}}.pass,.fail{{padding:5px 8px;border-radius:99px;font-weight:800;font-size:11px}}.pass{{background:var(--ok);color:#0d513a}}.fail{{background:var(--bad);color:#982f25}}.boundary{{color:var(--muted);font-size:13px;line-height:1.6;margin-top:18px}}@media(max-width:720px){{.cards{{grid-template-columns:1fr 1fr}}}}@media(max-width:460px){{.cards{{grid-template-columns:1fr}}}}
</style></head><body><main><header><span class="status">{status}</span><h1>咨询交付验收</h1><p>这里只验证产品理解、关键旅程、方向决策、交付物和声明边界；不会把尚未执行的源码改造或生产 Browser 验证写成通过。</p></header><div class="cards">{cards}</div><section><table><thead><tr><th>ID</th><th>检查</th><th>结果</th><th>说明</th></tr></thead><tbody>{rows}</tbody></table></section><p class="boundary">{escape(str(validation.get("claimBoundary", "")))}</p></main></body></html>"""
