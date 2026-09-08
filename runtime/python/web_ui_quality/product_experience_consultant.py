"""End-to-end AI Product Experience Consultant for Web UI Quality 3.6."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
import hashlib
import html
import json
from pathlib import Path
from typing import Any

from .experience_consultant import build_experience_consultation
from .experience_journey_intelligence import (
    JOURNEY_MODELS,
    analyze_user_journey,
    build_experience_score_report,
    infer_product_type,
)
from .executive_experience_report import build_executive_brief
from .experience_loop import build_measurement_loop
from .consultation_validation import render_validation_html, validate_consultation
from .release_info import PACKAGE_VERSION, release_identity
from .visual_transformation_engine import build_transformation_plan


BUSINESS_MODES = {
    "conversion": "让更多访客理解价值并采取行动",
    "efficiency": "让业务人员更快、更稳地完成任务",
    "mobile": "让移动和现场任务可单手、可恢复地完成",
    "ai-product": "让 AI 输入、生成、审阅和应用更可控",
    "redesign": "在保留业务含义的前提下系统升级体验",
}

INDUSTRY_MODELS = {
    key: {"role": value["roles"][0], "tasks": [item[1] for item in value["stages"]], "goal": value["goal"]}
    for key, value in JOURNEY_MODELS.items()
}


def build_experience_intake(product_type: str | None = None) -> dict[str, Any]:
    """Return a short, non-technical intake for missing product context."""
    resolved = infer_product_type(product_type=product_type)
    return {
        "schemaVersion": "3.6",
        "questions": [
            {
                "id": "businessGoal",
                "question": "这次最希望改善什么？",
                "options": [{"id": key, "label": label} for key, label in BUSINESS_MODES.items()],
                "required": True,
            },
            {
                "id": "primaryTask",
                "question": "用户在这个页面最重要的任务是什么？",
                "options": [],
                "freeText": True,
                "required": True,
            },
            {
                "id": "productType",
                "question": "最接近哪类产品？",
                "options": [
                    {"id": "crm", "label": "CRM / 销售系统"},
                    {"id": "saas", "label": "SaaS / 业务系统"},
                    {"id": "landing", "label": "官网 / 落地页"},
                    {"id": "commerce", "label": "电商"},
                    {"id": "ai-product", "label": "AI 产品"},
                    {"id": "mobile", "label": "移动 / 现场应用"},
                ],
                "required": False,
            },
        ],
        "selectedProductType": resolved,
        "estimatedMinutes": 2,
    }


def build_business_reasoning(product_type: str, findings: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    resolved = infer_product_type(product_type=product_type)
    model = INDUSTRY_MODELS[resolved]
    return {
        "schemaVersion": "3.6",
        "businessContext": {
            "productType": resolved,
            "userRole": model["role"],
            "criticalTasks": model["tasks"],
            "experienceGoal": model["goal"],
        },
        "translatedProblems": [
            {
                "problem": str(item.get("title") or item.get("problem") or "体验问题"),
                "businessImpact": str(item.get("whyItMatters") or f"可能妨碍用户{model['goal']}"),
                "userCost": str(item.get("userCost") or "增加理解、查找、操作或恢复成本"),
                "evidenceStatus": "OBSERVED_OR_INFERRED",
            }
            for item in findings[:3]
        ],
        "claimBoundary": "Business impacts are hypotheses until validated with product data or user research.",
    }


def build_design_reasoning(candidate: Mapping[str, Any], product_type: str) -> dict[str, Any]:
    resolved = infer_product_type(product_type=product_type)
    model = INDUSTRY_MODELS[resolved]
    return {
        "recommended": candidate.get("name"),
        "why": [
            f"贴合{model['role']}完成核心任务的方式",
            f"优先支持“{model['goal']}”",
            "把异常反馈和恢复路径纳入方案，而不只处理静态视觉",
        ],
        "tradeoffs": candidate.get("tradeoff", "需要先实现一个可回滚的关键旅程切片"),
        "measuredOutcome": False,
    }


def build_transformation_report(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schemaVersion": "3.6",
        "before": dict(before),
        "after": dict(after),
        "expectedOutcomes": [
            {"outcome": "更容易找到任务入口", "status": "HYPOTHESIS", "validation": "首次任务测试或导航事件"},
            {"outcome": "更连续地完成关键路径", "status": "HYPOTHESIS", "validation": "任务成功率与上下文切换观察"},
            {"outcome": "遇到错误后更容易恢复", "status": "HYPOTHESIS", "validation": "错误恢复任务与事件"},
        ],
        "claimBoundary": "Expected outcomes are hypotheses; no improvement percentage is generated without a real baseline.",
    }


def _product_name(diagnosis: Mapping[str, Any], context: Mapping[str, Any]) -> str:
    for key in ("productName", "title", "name"):
        if context.get(key):
            return str(context[key])
    page = diagnosis.get("pageUnderstanding") if isinstance(diagnosis.get("pageUnderstanding"), Mapping) else {}
    primary = page.get("primaryTask") if isinstance(page.get("primaryTask"), Mapping) else {}
    return str(primary.get("value") or "当前 Web 产品")


def build_product_experience_report(
    diagnosis: Mapping[str, Any],
    *,
    business_context: Mapping[str, Any] | None = None,
    product_name: str | None = None,
) -> dict[str, Any]:
    """Compile diagnosis, journeys, concepts, handoff, and measurement into one report."""
    context = dict(business_context or {})
    consultation = diagnosis.get("experienceConsultant") if isinstance(diagnosis.get("experienceConsultant"), Mapping) else None
    if not consultation:
        consultation = build_experience_consultation(diagnosis, experience_context=context)
    consultation = dict(consultation)
    page = diagnosis.get("pageUnderstanding") if isinstance(diagnosis.get("pageUnderstanding"), Mapping) else {}
    page_type = page.get("pageType") if isinstance(page.get("pageType"), Mapping) else {}
    product_type = infer_product_type(
        product_type=str(context.get("productType") or ""),
        intent=str(consultation.get("selectedIntent") or context.get("consultantIntent") or ""),
        page_type=str(page_type.get("id") or ""),
    )
    problems = [item for item in consultation.get("topProblems", []) if isinstance(item, Mapping)]
    role = str(context.get("userRole") or context.get("role") or "") or None
    goal = str(context.get("primaryTask") or context.get("task") or "") or None
    journey = analyze_user_journey(product_type, problems, role=role, goal=goal)
    score = build_experience_score_report(journey)
    transformation = build_transformation_plan(consultation, journey, business_context=context)
    measurement = build_measurement_loop(journey, transformation)
    name = product_name or _product_name(diagnosis, context)
    executive = build_executive_brief(name, score, consultation, transformation, measurement)
    status = "DISCOVERY_REQUIRED" if consultation.get("status") == "DISCOVERY_REQUIRED" else "PRODUCT_EXPERIENCE_READY"
    return {
        "schemaVersion": "3.6",
        "generator": release_identity(),
        "status": status,
        "readiness": {
            "consultation": "READY" if status == "PRODUCT_EXPERIENCE_READY" else "DISCOVERY_REQUIRED",
            "implementation": "NOT_RUN",
            "productionBrowserValidation": "NOT_VERIFIED",
            "commercialGA": "NOT_ESTABLISHED",
        },
        "product": {"name": name, "type": product_type},
        "opening": consultation.get("opening"),
        "businessSummary": consultation.get("businessSummary"),
        "topProblems": problems[:3],
        "journey": journey,
        "diagnosticScore": score,
        "transformation": transformation,
        "executiveBrief": executive,
        "measurementLoop": measurement,
        "handoff": {
            "status": "PREVIEW_ONLY",
            "sourceWriteAuthorized": False,
            "explicitConfirmationRequired": True,
            "implementationChecklist": [
                "确认用户角色、核心任务和成功定义",
                "确认推荐方向与一个关键旅程切片",
                "冻结允许修改的源码范围和受保护业务规则",
                "实现默认、加载、空、错误、成功及恢复状态",
                "在 1440、768、390 宽度验证交互和可访问性",
                "记录基线和上线后观察，再决定是否扩展",
            ],
        },
        "technicalEvidence": {
            "diagnosisStatus": diagnosis.get("status"),
            "proofStatus": (diagnosis.get("experienceProof") or {}).get("status") if isinstance(diagnosis.get("experienceProof"), Mapping) else None,
            "progressiveDisclosure": "HIDDEN_BY_DEFAULT",
        },
        "claims": {
            "measuredBusinessOutcome": False,
            "verifiedProductionBeforeAfter": False,
            "diagnosticInferenceUsed": True,
        },
    }


def export_product_experience_report(
    report: Mapping[str, Any],
    output_dir: str | Path,
) -> dict[str, str]:
    out = Path(output_dir).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    artifacts = {
        "report": "product-experience-report.json",
        "journey": "journey-map.json",
        "transformation": "experience-transformation-plan.json",
        "executiveBrief": "executive-brief.json",
        "implementationHandoff": "implementation-handoff.json",
        "measurementPlan": "measurement-plan.json",
        "brief": "product-experience-brief/index.html",
        "validation": "consultation-validation-report.json",
        "validationHtml": "consultation-validation-report.html",
        "manifest": "artifact-manifest.json",
    }
    json_payloads = {
        artifacts["report"]: report,
        artifacts["journey"]: report.get("journey", {}),
        artifacts["transformation"]: report.get("transformation", {}),
        artifacts["executiveBrief"]: report.get("executiveBrief", {}),
        artifacts["implementationHandoff"]: report.get("handoff", {}),
        artifacts["measurementPlan"]: report.get("measurementLoop", {}),
    }
    for relative, payload in json_payloads.items():
        path = out / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    brief_dir = out / "product-experience-brief"
    brief_dir.mkdir(parents=True, exist_ok=True)
    brief_path = brief_dir / "index.html"
    brief_path.write_text(_brief_html(report), encoding="utf-8")

    required = [
        artifacts["report"], artifacts["journey"], artifacts["transformation"],
        artifacts["executiveBrief"], artifacts["implementationHandoff"],
        artifacts["measurementPlan"], artifacts["brief"],
    ]
    validation = validate_consultation(report, required_artifacts=required, output_dir=out)
    (out / artifacts["validation"]).write_text(
        json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (out / artifacts["validationHtml"]).write_text(render_validation_html(validation), encoding="utf-8")

    hashed = required + [artifacts["validation"], artifacts["validationHtml"]]
    manifest = {
        "schemaVersion": "1",
        "generator": release_identity(),
        "validationStatus": validation["status"],
        "artifacts": [
            {
                "path": relative,
                "bytes": (out / relative).stat().st_size,
                "sha256": hashlib.sha256((out / relative).read_bytes()).hexdigest(),
            }
            for relative in hashed
        ],
        "claimBoundary": "Artifact integrity and consultation validation do not establish implementation or production evidence.",
    }
    (out / artifacts["manifest"]).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return artifacts


def _brief_html(report: Mapping[str, Any]) -> str:
    data = json.dumps(report, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    title = html.escape(str((report.get("product") or {}).get("name") or "产品体验方案"))
    return f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} · 产品体验方案</title><style>
:root{{--ink:#16211d;--muted:#66736d;--line:#dce5df;--paper:#f4f7f5;--surface:#fff;--brand:#166b4f;--brand2:#b9e3cf;--warm:#f2dfbd;--danger:#b9483a;--shadow:0 24px 70px rgba(25,54,43,.11);font-family:Inter,"Segoe UI","PingFang SC",sans-serif;color-scheme:light}}*{{box-sizing:border-box}}html{{scroll-behavior:smooth}}body{{margin:0;background:var(--paper);color:var(--ink)}}button{{font:inherit}}button:focus-visible,a:focus-visible{{outline:3px solid #2b8bff;outline-offset:3px}}.shell{{max-width:1240px;margin:auto;padding:18px 22px 72px}}.top{{display:flex;justify-content:space-between;align-items:center;gap:18px;padding:8px 0 22px}}.brand{{display:flex;align-items:center;gap:11px;font-weight:800}}.brand i{{display:grid;place-items:center;width:34px;height:34px;border-radius:11px;background:var(--ink);color:white;font-style:normal}}.status{{font-size:12px;color:var(--muted);background:#e7eee9;border:1px solid var(--line);border-radius:99px;padding:7px 11px}}.hero{{display:grid;grid-template-columns:minmax(0,1.5fr) minmax(300px,.7fr);gap:16px}}.hero-main,.hero-side,.card,.preview,.journey,.metrics,.handoff{{background:var(--surface);border:1px solid var(--line);border-radius:24px;box-shadow:var(--shadow)}}.hero-main{{padding:clamp(24px,5vw,56px);min-height:390px;display:flex;flex-direction:column;justify-content:space-between;background:radial-gradient(circle at 92% 8%,#d2eee0 0 16%,transparent 34%),var(--surface)}}.eyebrow{{letter-spacing:.12em;text-transform:uppercase;color:var(--brand);font-size:12px;font-weight:800}}h1{{font-size:clamp(38px,6vw,72px);line-height:.98;letter-spacing:-.055em;margin:14px 0 20px;max-width:820px}}.lead{{font-size:clamp(17px,2vw,21px);line-height:1.6;color:#3e4c46;max-width:760px}}.hero-foot{{display:flex;flex-wrap:wrap;gap:10px;margin-top:28px}}.pill{{padding:8px 11px;border:1px solid var(--line);border-radius:99px;font-size:12px;background:rgba(255,255,255,.76)}}.hero-side{{padding:24px;display:grid;align-content:start;gap:14px;background:var(--ink);color:white}}.score-label{{font-size:12px;color:#b9c7c0}}.score{{font-size:72px;line-height:1;font-weight:800;letter-spacing:-.06em}}.score small{{font-size:15px;letter-spacing:0;color:#b9c7c0}}.boundary{{padding:13px;border:1px solid #3b4b44;border-radius:14px;color:#cad5d0;font-size:12px;line-height:1.55}}.section-head{{display:flex;justify-content:space-between;align-items:end;gap:16px;margin:54px 0 16px}}h2{{font-size:clamp(26px,4vw,42px);letter-spacing:-.035em;margin:0}}.section-head p{{margin:0;color:var(--muted);max-width:520px;line-height:1.5}}.problems{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}}.card{{padding:24px;box-shadow:none;min-height:230px}}.number{{font-size:12px;font-weight:800;color:var(--brand)}}.card h3{{font-size:21px;margin:28px 0 10px}}.card p{{color:var(--muted);line-height:1.6}}.suggest{{border-top:1px solid var(--line);margin-top:18px;padding-top:14px;font-size:13px;color:var(--ink)}}.direction-tabs{{display:flex;gap:8px;overflow:auto;padding:3px 2px 12px}}.direction-tabs button{{border:1px solid var(--line);background:white;padding:11px 15px;border-radius:99px;white-space:nowrap;cursor:pointer}}.direction-tabs button[aria-selected="true"]{{background:var(--ink);border-color:var(--ink);color:white}}.preview{{padding:16px;overflow:hidden}}.preview-top{{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:4px 4px 14px}}.switches{{display:flex;background:#eef2ef;border-radius:10px;padding:3px}}.switches button{{border:0;background:transparent;padding:7px 11px;border-radius:8px;cursor:pointer}}.switches button.active{{background:white;box-shadow:0 2px 8px #0001}}.viewport{{display:flex;gap:5px}}.viewport button{{width:34px;height:34px;border:1px solid var(--line);background:white;border-radius:9px;cursor:pointer}}.viewport button.active{{border-color:var(--brand);color:var(--brand)}}.stage-wrap{{background:#e9eeeb;border-radius:17px;padding:28px;overflow:auto;min-height:520px}}.stage{{width:100%;max-width:1080px;min-height:455px;margin:auto;background:white;border-radius:16px;box-shadow:0 18px 55px #183c2d1c;transition:max-width .25s;padding:26px}}.concept-head{{display:flex;justify-content:space-between;gap:18px;padding-bottom:20px;border-bottom:1px solid var(--line)}}.concept-head h3{{font-size:28px;margin:0 0 7px}}.concept-head p{{margin:0;color:var(--muted)}}.recommend{{align-self:start;background:var(--brand2);color:#0f5b42;border-radius:99px;padding:7px 10px;font-size:11px;font-weight:800}}.concept-grid{{display:grid;grid-template-columns:.8fr 1.2fr;gap:16px;margin-top:16px}}.journey-mini,.screen{{border:1px solid var(--line);border-radius:15px;padding:16px}}.step{{padding:11px 0;border-bottom:1px solid var(--line)}}.step:last-child{{border:0}}.step b{{display:block;font-size:13px}}.step small{{color:var(--muted)}}.screen{{min-height:280px;background:linear-gradient(160deg,#f8faf8,#edf4ef)}}.screen-bar{{height:12px;width:45%;background:#cbd9d1;border-radius:8px}}.screen-title{{font-size:26px;font-weight:800;margin:28px 0 8px}}.screen-copy{{height:9px;background:#d7e0db;border-radius:6px;width:72%;margin:8px 0}}.screen-actions{{display:flex;gap:9px;margin:26px 0}}.screen-actions i{{height:38px;width:110px;border-radius:10px;background:var(--brand);display:block}}.screen-actions i+ i{{background:white;border:1px solid var(--line)}}.screen-cards{{display:grid;grid-template-columns:repeat(3,1fr);gap:9px}}.screen-cards i{{height:90px;border:1px solid var(--line);background:white;border-radius:12px}}.trade{{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:14px}}.trade div{{background:#f5f7f5;border-radius:14px;padding:14px;font-size:13px;line-height:1.55}}.journey{{padding:26px;box-shadow:none}}.journey-track{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-top:22px}}.journey-step{{position:relative;background:#f4f7f5;border-radius:15px;padding:18px;min-height:150px}}.journey-step.critical{{background:#dcefe5}}.journey-step b{{display:block;margin:7px 0}}.journey-step p{{color:var(--muted);font-size:13px;line-height:1.5}}.metrics{{padding:26px;box-shadow:none}}.metric-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-top:20px}}.metric{{padding:16px;background:#f5f7f5;border-radius:14px}}.metric b{{display:block;font-size:14px}}.metric span{{display:block;color:var(--muted);font-size:12px;margin-top:7px;line-height:1.45}}.metric em{{display:inline-block;margin-top:13px;font-size:10px;font-style:normal;color:#8b5b1d;background:var(--warm);padding:5px 7px;border-radius:99px}}.handoff{{padding:32px;display:grid;grid-template-columns:1fr 1fr;gap:28px;background:var(--ink);color:white}}.handoff p,.handoff li{{color:#bdcac4;line-height:1.6}}.handoff ol{{padding-left:20px}}details{{margin-top:28px;background:#eff3f0;border-radius:15px;padding:16px}}summary{{cursor:pointer;font-weight:700}}pre{{overflow:auto;white-space:pre-wrap;font-size:11px;color:var(--muted)}}@media(max-width:900px){{.hero,.handoff{{grid-template-columns:1fr}}.problems{{grid-template-columns:1fr}}.concept-grid{{grid-template-columns:1fr}}.journey-track,.metric-grid{{grid-template-columns:1fr 1fr}}}}@media(max-width:560px){{.shell{{padding:12px 12px 50px}}.top .status{{display:none}}.hero-main{{min-height:360px}}.stage-wrap{{padding:10px}}.stage{{padding:17px}}.concept-head{{display:block}}.recommend{{display:inline-block;margin-top:10px}}.trade,.journey-track,.metric-grid{{grid-template-columns:1fr}}.screen-cards{{grid-template-columns:1fr}}}}@media(prefers-reduced-motion:reduce){{*{{scroll-behavior:auto!important;transition:none!important}}}}
</style></head><body><div class="shell"><header class="top"><div class="brand"><i>W</i> Web UI Quality</div><div class="status">{PACKAGE_VERSION} · 产品体验咨询</div></header>
<section class="hero"><div class="hero-main"><div><div class="eyebrow">Product experience brief</div><h1 id="productTitle"></h1><p class="lead" id="businessSummary"></p></div><div class="hero-foot" id="heroPills"></div></div><aside class="hero-side"><div class="score-label">诊断优先级分数</div><div class="score" id="score"></div><p id="scoreSummary"></p><div class="boundary">这是基于当前发现的诊断分数，不是转化率、满意度或真实效率提升。没有基线，就不生成虚假的提升百分比。</div></aside></section>
<div class="section-head"><div><div class="eyebrow">Top problems</div><h2>先解决最影响用户的三个地方</h2></div><p>问题按用户影响排序，并直接说明为什么重要、应该怎样改变。</p></div><section class="problems" id="problems"></section>
<div class="section-head"><div><div class="eyebrow">Transformation</div><h2>一个推荐方向，两种备选</h2></div><p>先比较体验结构和取舍，再决定是否进入源码实施。</p></div><div class="direction-tabs" id="directionTabs" role="tablist" aria-label="体验方向"></div>
<section class="preview"><div class="preview-top"><div class="switches"><button id="currentView">当前问题</button><button id="recommendedView" class="active">推荐概念</button></div><div class="viewport" aria-label="预览宽度"><button data-width="1080" class="active" title="桌面">▭</button><button data-width="720" title="平板">▯</button><button data-width="390" title="手机">▯</button></div></div><div class="stage-wrap"><div class="stage" id="stage"></div></div></section>
<div class="section-head"><div><div class="eyebrow">Critical journey</div><h2>围绕完整任务，不只美化一个画面</h2></div></div><section class="journey"><div class="journey-track" id="journey"></div></section>
<div class="section-head"><div><div class="eyebrow">Measurement</div><h2>上线后怎样判断是否真的更好</h2></div></div><section class="metrics"><div class="metric-grid" id="metrics"></div></section>
<div class="section-head"><div><div class="eyebrow">Safe handoff</div><h2>从方案进入可落地实施</h2></div></div><section class="handoff"><div><h3>建议先做一个关键旅程切片</h3><p>选择方案不会自动改源码。确认任务、范围和受保护业务规则后，再实现一个可回滚切片。</p></div><ol id="checklist"></ol></section>
<details><summary>查看技术证据与声明边界</summary><pre id="evidence"></pre></details></div><script>
const DATA={data};const $=id=>document.getElementById(id);const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));let selected=DATA.transformation?.selectedVariantId;let mode='recommended';
function problems(){{const items=DATA.topProblems||[];$('problems').innerHTML=items.length?items.map((p,i)=>`<article class="card"><span class="number">0${{i+1}} · ${{esc(p.impact?.level||'重点')}}</span><h3>${{esc(p.title)}}</h3><p>${{esc(p.whyItMatters)}}</p><div class="suggest"><b>建议：</b>${{esc(p.suggestion)}}</div></article>`).join(''):'<article class="card"><h3>需要补充业务目标</h3><p>告诉我用户最重要的任务，我再给出具体诊断。</p></article>'}}
function tabs(){{const items=DATA.transformation?.variants||[];$('directionTabs').innerHTML=items.map(v=>`<button role="tab" aria-selected="${{v.id===selected}}" data-id="${{esc(v.id)}}">${{v.recommended?'推荐 · ':''}}${{esc(v.name)}}</button>`).join('');$('directionTabs').querySelectorAll('button').forEach(b=>b.onclick=()=>{{selected=b.dataset.id;tabs();renderStage()}})}}
function currentStage(){{const p=DATA.topProblems||[];return `<div class="concept-head"><div><h3>当前体验摩擦</h3><p>基于现有源码或输入形成的候选诊断</p></div><span class="recommend">未验证为生产录屏</span></div><div class="concept-grid"><div class="journey-mini">${{p.map((x,i)=>`<div class="step"><b>${{i+1}}. ${{esc(x.title)}}</b><small>${{esc(x.whyItMatters)}}</small></div>`).join('')}}</div><div class="screen"><div class="screen-bar"></div><div class="screen-title">信息与操作存在竞争</div><div class="screen-copy"></div><div class="screen-copy" style="width:52%"></div><div class="screen-actions"><i></i><i></i></div><div class="screen-cards"><i></i><i></i><i></i></div></div></div>`}}
function conceptStage(v){{if(!v)return currentStage();const steps=v.screenPlan||[];return `<div class="concept-head"><div><h3>${{esc(v.name)}}</h3><p>${{esc(v.outcome)}}</p></div>${{v.recommended?'<span class="recommend">AI 推荐</span>':''}}</div><div class="concept-grid"><div class="journey-mini">${{steps.map(s=>`<div class="step"><b>${{esc(s.stage)}}</b><small>${{esc(s.change)}}</small></div>`).join('')}}</div><div class="screen"><div class="screen-bar"></div><div class="screen-title">${{esc(v.name)}}</div><div class="screen-copy"></div><div class="screen-copy" style="width:52%"></div><div class="screen-actions"><i></i><i></i></div><div class="screen-cards"><i></i><i></i><i></i></div></div></div><div class="trade"><div><b>为什么适合</b><br>${{esc(v.whyRecommended)}}</div><div><b>主要取舍</b><br>${{esc(v.tradeoff)}}</div></div>`}}
function renderStage(){{const v=(DATA.transformation?.variants||[]).find(x=>x.id===selected);$('stage').innerHTML=mode==='current'?currentStage():conceptStage(v)}}
function boot(){{$('productTitle').textContent=DATA.product?.name||'产品体验方案';$('businessSummary').textContent=DATA.businessSummary?.plainLanguage||DATA.opening||'理解当前产品，并给出可验证的升级方向。';$('heroPills').innerHTML=[DATA.product?.type,DATA.status,'源码尚未修改'].filter(Boolean).map(x=>`<span class="pill">${{esc(x)}}</span>`).join('');const s=DATA.diagnosticScore||{{}};$('score').innerHTML=s.experienceScore==null?'—':`${{s.experienceScore}}<small>/100</small>`;$('scoreSummary').textContent=s.summary||'';problems();tabs();renderStage();$('journey').innerHTML=(DATA.journey?.stages||[]).map(s=>`<article class="journey-step ${{s.id===DATA.journey.criticalStageId?'critical':''}}"><span class="number">${{esc(s.status)}}</span><b>${{esc(s.label)}}</b><p>${{esc(s.goal)}}</p></article>`).join('');$('metrics').innerHTML=(DATA.measurementLoop?.metrics||[]).map(m=>`<article class="metric"><b>${{esc(m.label)}}</b><span>${{esc(m.definition)}}</span><em>待建立基线</em></article>`).join('');$('checklist').innerHTML=(DATA.handoff?.implementationChecklist||[]).map(x=>`<li>${{esc(x)}}</li>`).join('');$('evidence').textContent=JSON.stringify({{technicalEvidence:DATA.technicalEvidence,claims:DATA.claims}},null,2);$('currentView').onclick=()=>{{mode='current';$('currentView').classList.add('active');$('recommendedView').classList.remove('active');renderStage()}};$('recommendedView').onclick=()=>{{mode='recommended';$('recommendedView').classList.add('active');$('currentView').classList.remove('active');renderStage()}};document.querySelectorAll('.viewport button').forEach(b=>b.onclick=()=>{{document.querySelectorAll('.viewport button').forEach(x=>x.classList.remove('active'));b.classList.add('active');$('stage').style.maxWidth=b.dataset.width+'px'}})}}boot();
</script></body></html>'''
