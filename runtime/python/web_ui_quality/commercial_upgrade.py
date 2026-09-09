"""One productized consultation → implementation → validation → outcome workflow."""
from __future__ import annotations

from html import escape
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .core import audit_project
from .design_intelligence import generate_design_candidates
from .experience_engine import analyze_experience_project, export_experience_analysis
from .design_gallery import build_design_gallery
from .implementation_agent import execute_isolated_transformation
from .outcome_measurement import build_measurement_template, export_outcome_report, measure_outcome
from .product_experience_consultant import build_product_experience_report, export_product_experience_report
from .project_semantics import build_project_semantic_map
from .project_source_ir import build_project_design_ir
from .release_info import release_identity
from .schema_validation import validate_instance
from .smart_product_discovery import (
    apply_cached_product_confirmation,
    build_product_discovery,
    discovery_business_context,
    export_product_discovery,
    load_cached_product_discovery,
)
from .workflow_policy import (
    TrustedWorkflowApproval,
    is_answer_round_action,
    is_diagnosis_only_action,
    model_capability_profile,
    normalize_mode,
    required_scope_for_action,
    validate_confirmation,
)



def _limit_consultation_directions(report: Mapping[str, Any], context: Mapping[str, Any]) -> dict[str, Any]:
    """Limit public redesign choices to the three contracted product directions."""
    result = dict(report)
    directions = [dict(item) for item in result.get("directions", []) if isinstance(item, Mapping)][:3]
    result["directions"] = directions
    valid_ids = {str(item.get("id")) for item in directions}
    if str(result.get("selectedDirectionId")) not in valid_ids:
        result["selectedDirectionId"] = str(directions[0].get("id")) if directions else None
    return result

def _default_journey(product_type: str) -> list[dict[str, Any]]:
    common = [{"id": "page-heading", "action": "assert_visible", "selector": "h1"}]
    if product_type == "crm":
        return common + [
            {"id": "search-account", "action": "fill", "selector": "#search", "value": "Fieldnote"},
            {"id": "result-visible", "action": "assert_visible", "selector": "[data-id=\"fieldnote\"]"},
            {"id": "open-account", "action": "click", "selector": "[data-id=\"fieldnote\"]"},
            {"id": "detail-continuity", "action": "assert_text", "selector": "#detail", "expected": "Fieldnote Labs"},
            {"id": "journey-proof", "action": "screenshot", "filename": "journey-complete.png"},
        ]
    return common + [{"id": "journey-proof", "action": "screenshot", "filename": "journey-complete.png"}]


def _release_html(report: Mapping[str, Any]) -> str:
    decision = report.get("decision") if isinstance(report.get("decision"), Mapping) else {}
    recommended = decision.get("recommended") if isinstance(decision.get("recommended"), Mapping) else {}
    gates = report.get("gates") if isinstance(report.get("gates"), Mapping) else {}
    cards = "".join(
        f"<article><span>{escape(str(name))}</span><b>{escape(str(value.get('status') if isinstance(value, Mapping) else value))}</b><small>{escape(str(value.get('artifact', '') if isinstance(value, Mapping) else ''))}</small></article>"
        for name, value in gates.items()
    )
    status = escape(str(report.get("status")))
    artifacts = "".join(f"<li>{escape(str(item))}</li>" for item in report.get("artifacts", []))
    alternatives = "".join(f"<article><span>备选方向</span><b>{escape(str(item.get('name')))}</b><small>{escape(str(item.get('tradeoff') or '需要负责人确认'))}</small></article>" for item in decision.get("alternatives", []) if isinstance(item, Mapping))
    risks = "".join(f"<li>{escape(str(item))}</li>" for item in decision.get("risks", []))
    ui = report.get("ui") if isinstance(report.get("ui"), Mapping) else {}
    if ui.get("status") == "RENDERED":
        ui_action = '<a class="open" href="design-gallery/index.html">进入设计决策工作台 →</a>'
    else:
        ui_action = (
            '<p>设计决策工作台当前未启动。需要视觉比较时运行 '
            f'<code>{escape(str(ui.get("command") or "web-ui-quality design-ui <upgrade-output>"))}</code>。</p>'
        )
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>体验升级决策摘要 · {status}</title><style>
:root{{--ink:#16211d;--muted:#65726c;--line:#d9e4de;--paper:#f3f7f5;--brand:#145f46;font-family:Inter,"Segoe UI","PingFang SC",sans-serif}}*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink)}}main{{max-width:1120px;margin:auto;padding:34px 20px 80px}}header{{padding:clamp(30px,6vw,58px);border-radius:26px;background:radial-gradient(circle at 90% 0,#2b806260,transparent 35%),var(--ink);color:white}}h1{{font-size:clamp(38px,7vw,70px);margin:10px 0;letter-spacing:-.05em}}header p{{max-width:780px;color:#bdd0c7;line-height:1.6}}.status{{display:inline-block;background:#cdf1dc;color:#0d5039;border-radius:99px;padding:7px 10px;font-weight:800;font-size:12px}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px;margin:20px 0}}article,section,details{{background:white;border:1px solid var(--line);border-radius:18px;padding:20px}}article span,article small{{display:block;color:var(--muted);font-size:12px;line-height:1.5}}article b{{display:block;font-size:18px;margin:10px 0}}section{{margin:20px 0}}section h2{{margin-top:0}}li{{margin:9px 0;color:var(--muted);line-height:1.55}}.open{{display:inline-block;margin-top:18px;padding:13px 16px;border-radius:12px;background:#dff3e9;color:#0d5039;text-decoration:none;font-weight:800}}.recommend{{border:2px solid #7fc9a8}}details summary{{cursor:pointer;font-weight:800}}details .grid{{margin-bottom:0}}
</style></head><body><main><header><span class="status">{escape(str(decision.get('status') or status))}</span><h1>现在只需要决定一个方向</h1><p>{escape(str(decision.get('question') or '哪套体验方向最适合产品下一阶段？'))}</p>{ui_action}</header><section><h2>系统推荐</h2><div class="grid"><article class="recommend"><span>{escape(str(recommended.get('id') or '待确认'))}</span><b>{escape(str(recommended.get('name') or '尚未形成推荐'))}</b><small>{escape(str(recommended.get('why') or '请先完成视觉评审。'))}</small></article><article><span>适合</span><b>{escape(str(recommended.get('fit') or '当前核心用户任务'))}</b><small>推荐来自产品诊断和浏览器证据，最终决定仍由负责人做出。</small></article><article><span>需要接受</span><b>明确取舍</b><small>{escape(str(recommended.get('tradeoff') or '仍需确认品牌与实施偏好'))}</small></article></div></section><section><h2>其他可选方向</h2><div class="grid">{alternatives}</div></section><section><h2>不会擅自做什么</h2><ul>{risks}</ul></section><details><summary>查看技术验证与完整交付物</summary><div class="grid">{cards}</div><ul>{artifacts}</ul></details></main></body></html>"""


def refresh_commercial_ui_state(
    upgrade_output: str | Path,
    ui_state: Mapping[str, Any],
) -> dict[str, Any] | None:
    """Record an on-demand UI render in the existing release evidence."""
    root = Path(upgrade_output).expanduser().resolve()
    report_path = root / "commercial-release-report.json"
    if not report_path.is_file():
        return None
    value = json.loads(report_path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        return None
    report = dict(value)
    state = dict(ui_state)
    report["ui"] = state
    decision = dict(report.get("decision")) if isinstance(report.get("decision"), Mapping) else {}
    decision["ui"] = state
    decision["nextActions"] = ["打开设计决策工作台", "切换角色与设备比较", "确认方向并下载决策", "交给 Codex 定稿并复验"]
    report["decision"] = decision
    gates = dict(report.get("gates")) if isinstance(report.get("gates"), Mapping) else {}
    design_gate = dict(gates.get("designGallery")) if isinstance(gates.get("designGallery"), Mapping) else {}
    design_gate["artifact"] = "design-gallery/index.html"
    design_gate["ui"] = state.get("status")
    gates["designGallery"] = design_gate
    report["gates"] = gates
    artifacts = list(report.get("artifacts")) if isinstance(report.get("artifacts"), list) else []
    for artifact in ("design-gallery/index.html", "design-gallery/executive-decision-brief.md"):
        if artifact not in artifacts:
            insert_at = artifacts.index("design-gallery/design-review.json") if "design-gallery/design-review.json" in artifacts else len(artifacts)
            artifacts.insert(insert_at, artifact)
    report["artifacts"] = artifacts
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (root / "commercial-release-report.html").write_text(_release_html(report), encoding="utf-8")
    return report


def _diagnosis_html(report: Mapping[str, Any]) -> str:
    product = report.get("product") if isinstance(report.get("product"), Mapping) else {}
    consultation = report.get("consultation") if isinstance(report.get("consultation"), Mapping) else {}
    problems = consultation.get("topProblems") if isinstance(consultation.get("topProblems"), list) else []
    directions = consultation.get("directions") if isinstance(consultation.get("directions"), list) else []
    problem_html = "".join(
        f"<article><span>{escape(str(item.get('impact', {}).get('label') if isinstance(item.get('impact'), Mapping) else '待确认'))}</span>"
        f"<b>{escape(str(item.get('title') or '未命名问题'))}</b><p>{escape(str(item.get('whyItMatters') or '需要结合真实业务确认。'))}</p></article>"
        for item in problems if isinstance(item, Mapping)
    )
    direction_html = "".join(
        f"<article><span>{escape(str(item.get('id') or '方向'))}</span><b>{escape(str(item.get('name') or '未命名方向'))}</b>"
        f"<p>{escape(str(item.get('summary') or item.get('whyRecommended') or '等待进一步确认。'))}</p></article>"
        for item in directions if isinstance(item, Mapping)
    )
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>只读产品诊断 · {escape(str(product.get('name') or 'Web 产品'))}</title><style>
:root{{--ink:#16211d;--muted:#65726c;--line:#d9e4de;--paper:#f3f7f5;--brand:#145f46;font-family:Inter,"Segoe UI","PingFang SC",sans-serif}}*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink)}}main{{max-width:1100px;margin:auto;padding:32px 18px 70px}}header,section,article{{background:white;border:1px solid var(--line);border-radius:20px;padding:22px}}header{{background:var(--ink);color:white;padding:clamp(28px,6vw,60px)}}h1{{font-size:clamp(36px,7vw,68px);line-height:1;letter-spacing:-.05em;margin:12px 0}}header p{{max-width:800px;color:#c5d7cf;line-height:1.65}}section{{margin-top:16px}}h2{{margin-top:0}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px}}article span{{display:block;color:var(--muted);font-size:12px}}article b{{display:block;margin:9px 0;font-size:18px}}article p{{color:var(--muted);line-height:1.6}}.notice{{padding:14px;background:#edf7f0;border-radius:14px;color:#176044;line-height:1.6}}a{{color:#176044;font-weight:800}}</style></head><body><main><header><span>Web UI Quality {escape(str(report.get('generator', {}).get('version', '')))} · 只读诊断</span><h1>先把问题说清楚</h1><p>{escape(str(consultation.get('opening') or '已完成系统理解与产品体验诊断。'))}</p></header><section><h2>我理解的系统</h2><p>{escape(str((consultation.get('businessSummary') or {}).get('plainLanguage') if isinstance(consultation.get('businessSummary'), Mapping) else '请查看系统理解卡。'))}</p><p class="notice">这份结果只描述证据支持的产品问题，不包含代码修改、生产权限证明或真实用户效果承诺。</p></section><section><h2>最值得先讨论的三个问题</h2><div class="grid">{problem_html or '<p>当前没有足够证据形成稳定的 Top 3；请先补充业务信息。</p>'}</div></section><section><h2>推荐与备选方向（尚未实施）</h2><div class="grid">{direction_html or '<p>方向仍待确认。</p>'}</div></section><section><h2>下一步</h2><p>如果你确认诊断方向，再明确要求“生成隔离设计候选”，系统才会进入重型设计流程。</p><a href="../system-understanding/index.html">返回系统理解与证据 →</a></section></main></body></html>"""


def _run_diagnosis_only(
    project: Path,
    output: Path,
    *,
    context: Mapping[str, Any],
    product_name: str | None,
    target_framework: str | None,
    discovery: Mapping[str, Any],
    security_audit: bool,
    model_profile: Mapping[str, Any],
) -> dict[str, Any]:
    """Run the default, bounded path: understand → diagnose → stop."""
    consultation_dir = output / "consultation"
    audit = audit_project(project, business_context=context, include_security=security_audit)
    if audit.get("status") == "NOT_APPLICABLE":
        result = {
            "schemaVersion": "2", "generator": release_identity(), "mode": "diagnose",
            "status": "NOT_APPLICABLE", "reason": "AUDIT_SCOPE_EMPTY", "sourceProjectChanged": False,
        }
        (output / "commercial-release-report.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (output / "commercial-release-report.html").write_text(_diagnosis_html(result), encoding="utf-8")
        return result
    core = audit.get("experienceCore") if isinstance(audit.get("experienceCore"), Mapping) else {}
    productization = audit.get("productizationPlan") if isinstance(audit.get("productizationPlan"), Mapping) else {}
    model = dict(core.get("experienceModel") or {}) if isinstance(core.get("experienceModel"), Mapping) else dict(context)
    model.update({key: value for key, value in context.items() if value not in (None, "")})
    diagnosis = analyze_experience_project(
        project,
        model,
        page_modes=productization.get("pageModes", []),
        framework=target_framework,
    )
    technical = export_experience_analysis(diagnosis, consultation_dir / "technical-analysis", title=product_name)
    consultation = _limit_consultation_directions(
        build_product_experience_report(diagnosis, business_context=context, product_name=product_name), context
    )
    schema_dir = Path(__file__).resolve().parent / "schemas"
    validate_instance(consultation, json.loads((schema_dir / "product-experience-report.schema.json").read_text(encoding="utf-8")), base_dir=schema_dir)
    consultation_artifacts = export_product_experience_report(consultation, consultation_dir)
    report = {
        "schemaVersion": "2", "generator": release_identity(), "mode": "diagnose",
        "status": "PRODUCT_DIAGNOSIS_READY", "product": consultation.get("product"),
        "consultation": consultation,
        "decision": {
            "status": "DIAGNOSIS_ONLY",
            "question": "是否需要在确认诊断后生成隔离设计候选？",
            "recommended": (consultation.get("directions") or [None])[0] if isinstance(consultation.get("directions"), list) else None,
        },
        "gates": {
            "productDiscovery": {"status": discovery.get("status"), "workflowState": discovery.get("workflowState"), "artifact": "system-understanding/index.html"},
            "consultation": {"status": "PASS", "artifact": f"consultation/{consultation_artifacts['report']}"},
            "securityAudit": {"status": "OPT_IN" if not security_audit else "RUN", "included": security_audit},
            "design": {"status": "NOT_RUN", "reason": "DESIGN_REQUIRES_EXPLICIT_REQUEST"},
            "implementation": {"status": "NOT_RUN", "reason": "SOURCE_READ_ONLY"},
            "browserValidation": {"status": "NOT_RUN", "reason": "DEEP_MODE_NOT_REQUESTED"},
            "outcomeMeasurement": {"status": "NOT_RUN", "reason": "BASELINE_NOT_REQUESTED"},
        },
        "artifacts": [
            "system-understanding/index.html", "system-understanding/system-understanding.json",
            "system-understanding/execution-brief.json", "system-understanding/test-plan.json",
            "system-understanding/scan-cache.json", f"consultation/{consultation_artifacts['report']}",
            "consultation/product-experience-brief/index.html",
        ],
        "workflowState": "AWAITING_IMPLEMENTATION_APPROVAL",
        "sourceProjectChanged": False,
        "patchIntegrationAuthorized": False,
        "securityAudit": "RUN" if security_audit else "OPT_IN_ONLY",
        "modelCapabilityProfile": dict(model_profile),
        "scanStats": discovery.get("scanStats", {}),
        "technicalAnalysis": technical,
        "claimBoundary": "只读诊断不是生产验证、用户研究、代码修改授权或安全审计结论；未知项和未验证环境保持显式标记。",
    }
    (output / "commercial-release-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output / "commercial-release-report.html").write_text(_diagnosis_html(report), encoding="utf-8")
    return report


def run_commercial_upgrade(
    project_root: str | Path,
    output_dir: str | Path,
    *,
    business_context: Mapping[str, Any] | None = None,
    product_name: str | None = None,
    product_type: str | None = None,
    target_framework: str | None = None,
    browser_executable: str | Path | None = None,
    browser_single_process: bool = False,
    journey: Sequence[Mapping[str, Any]] | None = None,
    baseline_events: str | Path | None = None,
    after_events: str | Path | None = None,
    outcome_provider: str = "generic",
    outcome_config: Mapping[str, Any] | None = None,
    screenshot_paths: Sequence[str | Path] = (),
    multimodal_overlay: Mapping[str, Any] | None = None,
    product_confirmation: Mapping[str, Any] | None = None,
    product_discovery: Mapping[str, Any] | None = None,
    approval_receipt: TrustedWorkflowApproval | Mapping[str, Any] | None = None,
    mode: str = "full",
    security_audit: bool = False,
    model_profile: str | None = None,
    design_ui: bool = False,
) -> dict[str, Any]:
    project = Path(project_root).expanduser().resolve()
    output = Path(output_dir).expanduser().resolve()
    if output.exists() and any(output.iterdir()):
        children = {item.name for item in output.iterdir()}
        resumable = children <= {"system-understanding"} and bool(product_confirmation)
        if not resumable:
            raise ValueError("commercial upgrade output directory must be new, empty, or a product-understanding output being resumed with confirmation")
    output.mkdir(parents=True, exist_ok=True)
    mode = normalize_mode(mode, default="full")
    capability_profile = model_capability_profile(model_profile)
    context = dict(business_context or {})
    if product_name:
        context["productName"] = product_name
    if product_type:
        context["productType"] = product_type

    if product_discovery is not None:
        discovery = dict(product_discovery)
    else:
        cached = load_cached_product_discovery(
            project,
            output,
            business_context=context,
            screenshot_paths=screenshot_paths,
            multimodal_overlay=multimodal_overlay,
        ) if output.exists() else None
        if cached is not None and product_confirmation:
            discovery = apply_cached_product_confirmation(
                cached,
                product_confirmation,
                approval_receipt=approval_receipt,
                model_profile=capability_profile["id"],
            )
        elif cached is not None:
            discovery = dict(cached)
        else:
            discovery = dict(build_product_discovery(
                project,
                business_context=context,
                screenshot_paths=screenshot_paths,
                multimodal_overlay=multimodal_overlay,
                confirmation=product_confirmation,
                approval_receipt=approval_receipt,
                model_profile=capability_profile["id"],
            ))
    requested_action = str((product_confirmation or {}).get("action") or "").strip().casefold()
    required_gate_scope = required_scope_for_action(requested_action, mode)
    validation = validate_confirmation(
        product_confirmation,
        approval=approval_receipt,
        required_scope=required_gate_scope,
        required_mode=mode,
    ) if product_confirmation else {"trusted": False, "status": "CURRENT_CONVERSATION_APPROVAL_REQUIRED"}
    answer_round_only = is_answer_round_action(requested_action)
    diagnosis_only = is_diagnosis_only_action(requested_action)
    if not validation.get("trusted") or discovery.get("status") != "PRODUCT_UNDERSTANDING_READY":
        export_product_discovery(discovery, output / "system-understanding")
        return {
            "schemaVersion": "2", "generator": release_identity(), "mode": mode,
            "status": validation.get("status") if not validation.get("trusted") else discovery.get("status"),
            "product": discovery.get("product"), "gates": {"productDiscovery": {"status": discovery.get("status")}},
            "sourceProjectChanged": False, "patchIntegrationAuthorized": False,
            "modelCapabilityProfile": capability_profile,
            "claimBoundary": "未获得当前对话用户确认，未进入建议或实施。",
        }
    if answer_round_only:
        # Saving a round is intentionally a hard stop.  A caller requesting
        # `mode=full` must submit a new packet and a fresh FULL approval after
        # the complete understanding card has been reviewed.
        discovery_artifacts = export_product_discovery(discovery, output / "system-understanding")
        result = {
            "schemaVersion": "2", "generator": release_identity(), "mode": mode,
            "status": "PRODUCT_UNDERSTANDING_ROUND_SAVED",
            "product": discovery.get("product"),
            "gates": {
                "productDiscovery": {
                    "status": discovery.get("status"),
                    "workflowState": "AWAITING_USER_CONFIRMATION",
                    "artifact": f"system-understanding/{discovery_artifacts['workbench']}",
                },
                "diagnosis": {"status": "NOT_RUN", "reason": "NEW_SCOPE_CONFIRMATION_REQUIRED"},
                "design": {"status": "NOT_RUN", "reason": "NEW_SCOPE_CONFIRMATION_REQUIRED"},
                "implementation": {"status": "NOT_RUN", "reason": "SOURCE_READ_ONLY"},
            },
            "sourceProjectChanged": False,
            "patchIntegrationAuthorized": False,
            "nextAction": "重新提交 confirm-understanding，并明确只读诊断或完整升级范围。",
            "modelCapabilityProfile": capability_profile,
            "scanStats": discovery.get("scanStats", {}),
            "claimBoundary": "本轮回答只更新系统理解证据；它不是诊断或完整升级授权。",
        }
        (output / "commercial-release-report.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        return result
    if diagnosis_only and mode == "full":
        export_product_discovery(discovery, output / "system-understanding")
        return {
            "schemaVersion": "2", "generator": release_identity(), "mode": mode,
            "status": "DIAGNOSIS_SCOPE_REQUIRED",
            "product": discovery.get("product"),
            "gates": {"productDiscovery": {"status": discovery.get("status")}, "design": {"status": "NOT_RUN"}, "implementation": {"status": "NOT_RUN"}},
            "sourceProjectChanged": False, "patchIntegrationAuthorized": False,
            "nextAction": "继续诊断不能打开完整升级；请重新提交完整升级确认。",
            "modelCapabilityProfile": capability_profile,
            "claimBoundary": "诊断范围确认不会授予完整升级或实施权限。",
        }
    discovery_artifacts = export_product_discovery(discovery, output / "system-understanding")
    inferred_context = discovery_business_context(discovery)
    for key, value in inferred_context.items():
        if value in (None, "", []):
            continue
        if isinstance(value, list):
            existing = context.get(key)
            context[key] = list(dict.fromkeys((list(existing) if isinstance(existing, list) else []) + value))
        elif not context.get(key):
            context[key] = value
    effective_product_name = product_name or str(context.get("productName") or "").strip() or None

    if mode == "diagnose":
        return _run_diagnosis_only(
            project,
            output,
            context=context,
            product_name=effective_product_name,
            target_framework=target_framework,
            discovery=discovery,
            security_audit=security_audit,
            model_profile=capability_profile,
        )

    consultation_dir = output / "consultation"
    audit = audit_project(project, business_context=context, include_security=security_audit)
    if audit.get("status") == "NOT_APPLICABLE":
        result = {"schemaVersion": "1", "generator": release_identity(), "status": "NOT_APPLICABLE", "reason": "AUDIT_SCOPE_EMPTY"}
        (output / "commercial-release-report.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return result
    core = audit.get("experienceCore") if isinstance(audit.get("experienceCore"), Mapping) else {}
    productization = audit.get("productizationPlan") if isinstance(audit.get("productizationPlan"), Mapping) else {}
    model = dict(core.get("experienceModel") or {}) if isinstance(core.get("experienceModel"), Mapping) else dict(context)
    model.update({key: value for key, value in context.items() if value not in (None, "")})
    diagnosis = analyze_experience_project(
        project,
        model,
        page_modes=productization.get("pageModes", []),
        framework=target_framework,
    )
    technical = export_experience_analysis(diagnosis, consultation_dir / "technical-analysis", title=effective_product_name)
    consultation = _limit_consultation_directions(
        build_product_experience_report(diagnosis, business_context=context, product_name=effective_product_name), context
    )
    schema_dir = Path(__file__).resolve().parent / "schemas"
    validate_instance(consultation, json.loads((schema_dir / "product-experience-report.schema.json").read_text(encoding="utf-8")), base_dir=schema_dir)
    consultation_artifacts = export_product_experience_report(consultation, consultation_dir)

    design_ir = build_project_design_ir(project, audit_report=audit)
    candidate_count = 3
    design_candidates = generate_design_candidates(core or model, design_ir=design_ir, count=candidate_count)
    semantic_map = build_project_semantic_map(project)
    design_context = {
        "designIr": design_ir,
        "designCandidates": design_candidates,
        "semanticMap": semantic_map,
        "designSystem": semantic_map.get("designSystem", {}),
    }
    implementation_dir = output / "implementation"
    implementation = execute_isolated_transformation(project, implementation_dir, consultation, design_context=design_context)
    validation_dir = output / "validation"
    effective_journey = list(journey) if journey is not None else _default_journey(str(consultation.get("product", {}).get("type") or "saas"))
    design_review = build_design_gallery(
        implementation_dir / "generated-preview" / "before",
        implementation,
        validation_dir,
        output / "design-gallery",
        browser_executable=browser_executable,
        journey=effective_journey,
        single_process=browser_single_process,
        product_discovery=discovery,
        render_ui=design_ui,
    ) if implementation.get("status") == "IMPLEMENTED_IN_ISOLATED_COPY" else {
        "status": "NOT_RUN", "reason": "implementation did not produce runnable design candidates"
    }
    selected_validation_path = validation_dir / "production-validation-report.json"
    validation = json.loads(selected_validation_path.read_text(encoding="utf-8")) if selected_validation_path.is_file() else {
        "status": "NOT_RUN", "reason": "no Browser-accepted design candidate was selected"
    }

    outcome_dir = output / "outcome"
    if baseline_events and after_events:
        outcome = measure_outcome(
            baseline_events,
            after_events,
            provider=outcome_provider,
            config=outcome_config,
        )
    else:
        outcome = build_measurement_template()
    outcome_artifacts = export_outcome_report(outcome, outcome_dir)

    implementation_pass = implementation.get("status") == "IMPLEMENTED_IN_ISOLATED_COPY"
    browser_pass = validation.get("status") == "PASS"
    design_pass = design_review.get("status") == "DESIGN_GALLERY_PASS"
    measurement_ready = outcome.get("status") in {"PASS", "BASELINE_REQUIRED"}
    status = "COMMERCIAL_WORKFLOW_PASS" if implementation_pass and design_pass and browser_pass and measurement_ready else "COMMERCIAL_WORKFLOW_NOT_VERIFIED"
    design_ui_state = design_review.get("ui") if isinstance(design_review.get("ui"), Mapping) else {
        "requested": bool(design_ui),
        "status": "NOT_AVAILABLE",
        "artifact": None,
        "brief": None,
        "command": "web-ui-quality design-ui <upgrade-output>",
    }
    artifacts = [
        f"system-understanding/{discovery_artifacts['workbench']}",
        f"system-understanding/{discovery_artifacts['understanding']}",
        f"system-understanding/{discovery_artifacts['executionBrief']}",
        f"system-understanding/{discovery_artifacts['testPlan']}",
        f"system-understanding/{discovery_artifacts['scanCache']}",
        "consultation/product-experience-report.json",
        "consultation/product-experience-brief/index.html",
        "implementation/implementation-plan.json",
        "implementation/design-intelligence/project-semantic-map.json",
        "implementation/design-intelligence/project-design-ir.json",
        "implementation/design-intelligence/project-design-candidates.json",
        "implementation/design-intelligence/project-design-system-map.json",
        "implementation/source-change.patch",
        "implementation/generated-preview/before/",
        "implementation/generated-preview/after/",
        "implementation/generated-preview/variants/",
        "design-gallery/design-review.json",
        "validation/production-validation-report.json",
        "validation/production-validation-report.html",
        "outcome/outcome-measurement-report.json",
        "outcome/outcome-measurement-report.html",
    ]
    if design_ui and design_ui_state.get("status") == "RENDERED":
        artifacts[artifacts.index("design-gallery/design-review.json"):artifacts.index("design-gallery/design-review.json")] = [
            "design-gallery/index.html",
            "design-gallery/executive-decision-brief.md",
        ]
    review_variants = [item for item in design_review.get("variants", []) if isinstance(item, Mapping)]
    recommended_variant = next((item for item in review_variants if item.get("id") == design_review.get("selectedVariantId")), None)
    recipe = recommended_variant.get("recipe") if isinstance(recommended_variant, Mapping) and isinstance(recommended_variant.get("recipe"), Mapping) else {}
    decision = {
        "status": "READY_FOR_HUMAN_DECISION" if design_pass and browser_pass else "EVIDENCE_REQUIRED",
        "question": "这些真实作品中，哪一种体验方向最符合产品接下来的业务阶段？",
        "recommended": {
            "id": recommended_variant.get("id") if recommended_variant else None,
            "name": recommended_variant.get("name") if recommended_variant else None,
            "why": recipe.get("promise") or "产品诊断优先、Browser 证据门禁后形成的推荐。",
            "fit": recommended_variant.get("outcome") if recommended_variant else None,
            "tradeoff": recommended_variant.get("tradeoff") if recommended_variant else None,
        },
        "alternatives": [
            {"id": item.get("id"), "name": item.get("name"), "tradeoff": item.get("tradeoff")}
            for item in review_variants if item.get("id") != design_review.get("selectedVariantId")
        ],
        "evidence": {"candidateCount": len(review_variants), "viewportCount": 3, "browserStatus": validation.get("status")},
        "ui": dict(design_ui_state),
        "risks": [
            "原项目没有被修改；只有负责人确认后才生成可集成补丁。",
            "当前结果不等于已授权上线，也不代表生产环境已经验证。",
            "视觉和旅程证据不构成业务指标因果提升的承诺。",
        ],
        "nextActions": (
            ["打开设计决策工作台", "切换角色与设备比较", "确认方向并下载决策", "交给 Codex 定稿并复验"]
            if design_ui_state.get("status") == "RENDERED"
            else ["按需运行 design-ui", "切换角色与设备比较", "确认方向并下载决策", "交给 Codex 定稿并复验"]
        ),
    }
    release = {
        "schemaVersion": "2",
        "generator": release_identity(),
        "mode": "full",
        "status": status,
        "product": consultation.get("product"),
        "decision": decision,
        "gates": {
            "productDiscovery": {
                "status": discovery.get("status"),
                "confidence": discovery.get("confidence", {}).get("percent"),
                "unansweredQuestions": discovery.get("questionPolicy", {}).get("unanswered"),
                "artifact": "system-understanding/index.html",
            },
            "consultation": {"status": "PASS", "artifact": f"consultation/{consultation_artifacts['report']}"},
            "projectDesignIntelligence": {
                "status": design_candidates.get("status"),
                "semanticStatus": semantic_map.get("status"),
                "groundedRoleCount": semantic_map.get("coverage", {}).get("groundedRoleCount"),
                "artifact": "implementation/design-intelligence/project-design-candidates.json",
            },
            "implementation": {"status": "PASS" if implementation_pass else "FAIL", "artifact": "implementation/implementation-plan.json"},
            "designGallery": {
                "status": design_review.get("status"),
                "selectedVariantId": design_review.get("selectedVariantId"),
                "artifact": "design-gallery/index.html" if design_ui_state.get("status") == "RENDERED" else "design-gallery/design-review.json",
                "ui": design_ui_state.get("status"),
            },
            "browserValidation": {"status": validation.get("status"), "artifact": "validation/production-validation-report.json"},
            "outcomeMeasurement": {"status": outcome.get("status"), "decision": outcome.get("decision"), "artifact": f"outcome/{outcome_artifacts['report']}"},
            "securityAudit": {"status": "RUN" if security_audit else "OPT_IN_ONLY", "included": security_audit},
        },
        "sourceProjectChanged": False,
        "patchIntegrationAuthorized": False,
        "selectedVariantId": design_review.get("selectedVariantId"),
        "ui": design_ui_state,
        "artifacts": artifacts,
        "technicalAnalysis": technical,
        "workflowState": "AWAITING_IMPLEMENTATION_APPROVAL",
        "securityAudit": "RUN" if security_audit else "OPT_IN_ONLY",
        "modelCapabilityProfile": capability_profile,
        "scanStats": discovery.get("scanStats", {}),
        "claimBoundary": "Workflow PASS proves an isolated implementation and local/staging Browser acceptance. It does not authorize integration, production mutation, causal business claims, security hardening, or legal distribution terms.",
    }
    report_path = output / "commercial-release-report.json"
    report_path.write_text(json.dumps(release, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output / "commercial-release-report.html").write_text(_release_html(release), encoding="utf-8")
    return release
