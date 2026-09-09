"""Generate the plain-language WUQ 3.2 Experience Consultant surface."""
from __future__ import annotations

import html
import json
from pathlib import Path
import shutil
from typing import Any, Mapping


def _escape(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def _problem_cards(consultation: Mapping[str, Any]) -> str:
    cards: list[str] = []
    for index, problem in enumerate(consultation.get("topProblems", []), start=1):
        if not isinstance(problem, Mapping):
            continue
        impact = problem.get("impact") if isinstance(problem.get("impact"), Mapping) else {}
        cards.append(
            '<article class="problem-card">'
            f'<div class="problem-meta"><span>问题 {index}</span><span class="impact">{_escape(impact.get("label"))}</span></div>'
            f'<h3>{_escape(problem.get("title"))}</h3>'
            f'<p>{_escape(problem.get("whyItMatters"))}</p>'
            f'<div class="suggestion"><b>建议</b><span>{_escape(problem.get("suggestion"))}</span></div>'
            "</article>"
        )
    return "".join(cards)


def _direction_cards(consultation: Mapping[str, Any]) -> str:
    cards: list[str] = []
    for index, direction in enumerate(consultation.get("directions", [])):
        if not isinstance(direction, Mapping):
            continue
        recommended = bool(direction.get("recommended"))
        selected_class = "selected" if recommended else ""
        recommendation_badge = (
            '<span class="recommended">AI 推荐</span>'
            if recommended
            else '<span class="alternative">备选方向</span>'
        )
        button_class = "primary" if recommended else ""
        aria_pressed = "true" if recommended else "false"
        button_label = "已选择" if recommended else _escape(direction.get("actionLabel"))
        cards.append(
            f'<article class="direction-card {selected_class}" data-direction="{_escape(direction.get("id"))}">'
            f'<div class="direction-top"><span class="direction-number">{chr(65 + index)}</span>'
            f'{recommendation_badge}</div>'
            f'<h3>{_escape(direction.get("userScenario") or direction.get("name"))}</h3>'
            f'<p>{_escape(direction.get("expectedExperienceChange") or direction.get("summary"))}</p>'
            f'<dl><dt>价值</dt><dd>{_escape(direction.get("businessValue"))}</dd>'
            f'<dt>适合</dt><dd>{_escape(direction.get("bestFor"))}</dd>'
            f'<dt>取舍</dt><dd>{_escape(direction.get("tradeoff"))}</dd></dl>'
            f'<button type="button" class="choose-direction {button_class}" '
            f'data-choose-direction="{_escape(direction.get("id"))}" aria-pressed="{aria_pressed}">'
            f'{button_label}</button></article>'
        )
    return "".join(cards)


def _intent_buttons(consultation: Mapping[str, Any]) -> str:
    selected = str(consultation.get("selectedIntent") or "")
    buttons = []
    for item in consultation.get("supportedIntents", []):
        if not isinstance(item, Mapping):
            continue
        is_selected = str(item.get("id") or "") == selected
        buttons.append(
            f'<button type="button" data-intent="{_escape(item.get("id"))}" aria-pressed="{"true" if is_selected else "false"}">'
            f'<b>{_escape(item.get("label"))}</b><span>{_escape(item.get("description"))}</span></button>'
        )
    return "".join(buttons)


def _reference_surface(reference_name: str | None) -> str:
    if reference_name:
        return (
            '<figure class="reference-shot">'
            f'<img src="{_escape(reference_name)}" alt="用户提供的页面参考截图">'
            '<figcaption>参考截图（未验证为 Before 状态）</figcaption></figure>'
        )
    return """
<div class="legacy-surface" aria-label="当前结构示意">
  <div class="legacy-head"><h4>客户列表</h4><div><button>新增</button><button>导出</button></div></div>
  <div class="legacy-tools"><input aria-label="旧版搜索" placeholder="搜索"><button>筛选</button><button>排序</button><button>批量</button><button>更多</button></div>
  <div class="legacy-table"><b>客户　状态　负责人　等级　地区　来源　更新时间　操作</b>
    <p>北辰物流　待跟进　陈晨　A　华东　转介绍　今天　详情</p>
    <p>远航科技　正常　林岚　B　华南　官网　昨天　详情</p>
    <p>青禾制造　待跟进　周敏　A　华北　活动　本周　详情</p>
  </div>
</div>"""


def _after_surface() -> str:
    return """
<div class="after-workspace" id="afterWorkspace" data-direction-style="balanced">
  <div class="workbench-head"><div><small>客户工作台</small><h4>查找并连续处理客户</h4></div><button class="primary" type="button" id="newCustomer">新建客户</button></div>
  <div class="workbench-filter" role="group" aria-label="客户筛选">
    <input id="customerSearch" type="search" aria-label="搜索客户" placeholder="搜索名称、ID 或负责人">
    <button type="button" data-filter="all" aria-pressed="true">全部</button>
    <button type="button" data-filter="follow" aria-pressed="false">待跟进</button>
  </div>
  <div class="filter-feedback" id="filterFeedback" role="status" aria-live="polite">显示全部客户</div>
  <div class="workbench-grid" id="workbenchGrid">
    <section class="customer-list" aria-label="客户列表">
      <button type="button" class="customer selected" data-record="beichen" aria-pressed="true"><span><b>北辰物流</b><small>KH-2401 · 华东</small></span><em>待跟进</em></button>
      <button type="button" class="customer" data-record="yuanhang" aria-pressed="false"><span><b>远航科技</b><small>KH-2398 · 华南</small></span><em>正常</em></button>
      <button type="button" class="customer" data-record="qinghe" aria-pressed="false"><span><b>青禾制造</b><small>KH-2386 · 华北</small></span><em>待跟进</em></button>
    </section>
    <aside class="customer-detail" aria-labelledby="detailName">
      <button type="button" class="detail-back" id="detailBack">← 返回列表</button>
      <span class="status-chip" id="detailStatus">待跟进</span><h5 id="detailName">北辰物流</h5>
      <dl><dt>负责人</dt><dd id="detailOwner">陈晨</dd><dt>下一步</dt><dd id="detailNext">确认合同条款</dd><dt>最近活动</dt><dd id="detailUpdated">今天 10:24</dd></dl>
      <div class="detail-actions"><button type="button" id="addNote">记录活动</button><button type="button" class="primary" id="completeTask">标记已完成</button></div>
    </aside>
  </div>
  <div class="preview-state" id="previewState" hidden><h5 id="stateTitle"></h5><p id="stateBody"></p><button type="button" id="stateAction">返回正常状态</button></div>
</div>"""


def _technical_content(consultation: Mapping[str, Any]) -> str:
    preview = consultation.get("preview") if isinstance(consultation.get("preview"), Mapping) else {}
    appendix = consultation.get("technicalAppendix") if isinstance(consultation.get("technicalAppendix"), Mapping) else {}
    refs = appendix.get("evidenceRefs") if isinstance(appendix.get("evidenceRefs"), list) else []
    checks = appendix.get("verificationNeeded") if isinstance(appendix.get("verificationNeeded"), list) else []
    return (
        '<div class="tech-grid">'
        f'<article><span>预览证明状态</span><b>{_escape(preview.get("proofStatus"))}</b></article>'
        f'<article><span>当前权威边界</span><b>{_escape(preview.get("authority"))}</b></article></div>'
        f'<p>{_escape(preview.get("claimBoundary"))}</p>'
        '<h4>仍需确认</h4><ul>'
        + ("".join(f'<li>{_escape(item)}</li>' for item in checks[:8]) or "<li>根据真实项目状态继续验证。</li>")
        + '</ul><h4>来源引用</h4><ul class="code-list">'
        + ("".join(f'<li><code>{_escape(item)}</code></li>' for item in refs[:8]) or "<li>当前没有可公开的细节引用。</li>")
        + "</ul>"
    )


_TEMPLATE = r'''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__ · WUQ Experience Consultant</title>
<style>
:root{--bg:#f3f5f8;--surface:#fff;--text:#172133;--muted:#687386;--line:#dfe4eb;--brand:#2f5de5;--brand-soft:#edf2ff;--good:#167453;--warn:#9a5b00;--shadow:0 16px 44px rgba(31,47,76,.09);--radius:18px;--preview-width:100%}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--bg);color:var(--text);font:15px/1.55 Inter,"Segoe UI","PingFang SC",system-ui,sans-serif}button,input{font:inherit}button{min-height:44px;border:1px solid var(--line);border-radius:11px;background:var(--surface);color:var(--text);padding:0 14px;cursor:pointer}button:hover{border-color:#9eafe4}button:focus-visible,input:focus-visible,summary:focus-visible{outline:3px solid rgba(47,93,229,.3);outline-offset:2px}.primary{background:var(--brand);border-color:var(--brand);color:#fff}.appbar{position:sticky;top:0;z-index:20;display:flex;align-items:center;justify-content:space-between;gap:16px;padding:12px 24px;border-bottom:1px solid rgba(223,228,235,.9);background:rgba(255,255,255,.92);backdrop-filter:blur(18px)}.brand{display:flex;align-items:center;gap:11px}.mark{width:36px;height:36px;border-radius:12px;display:grid;place-items:center;background:linear-gradient(135deg,#2f5de5,#6e8fff);color:#fff;font-weight:800}.brand b,.brand small{display:block}.brand small{color:var(--muted)}main{max-width:1240px;margin:auto;padding:30px 24px 70px;display:grid;gap:24px}.hero{display:grid;grid-template-columns:1.2fr .8fr;gap:24px;padding:32px;border-radius:26px;background:linear-gradient(135deg,#fff 45%,#edf2ff);border:1px solid var(--line);box-shadow:var(--shadow)}.eyebrow{color:var(--brand);font-size:12px;font-weight:800;letter-spacing:.08em}.hero h1{font-size:clamp(30px,4vw,52px);line-height:1.08;margin:10px 0 14px}.hero p{max-width:720px;color:var(--muted);font-size:17px}.understanding{align-self:stretch;padding:20px;border-radius:18px;background:rgba(255,255,255,.78);border:1px solid rgba(223,228,235,.9)}.understanding span,.understanding small{display:block;color:var(--muted)}.understanding b{display:block;font-size:20px;margin:7px 0}.section-head{display:flex;align-items:end;justify-content:space-between;gap:16px}.section-head h2{margin:0;font-size:26px}.section-head p{margin:4px 0 0;color:var(--muted)}.problem-grid,.direction-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}.problem-card,.direction-card,.preview-card,.handoff,.technical{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);box-shadow:0 2px 10px rgba(31,47,76,.03)}.problem-card{padding:20px}.problem-meta,.direction-top{display:flex;align-items:center;justify-content:space-between;gap:10px;color:var(--muted);font-size:12px}.impact,.recommended{border-radius:999px;padding:4px 8px;background:#fff4d8;color:#7b4b00;font-weight:700}.problem-card h3,.direction-card h3{font-size:19px;margin:15px 0 8px}.problem-card p,.direction-card p{color:var(--muted)}.suggestion{display:grid;gap:4px;margin-top:18px;padding-top:14px;border-top:1px solid var(--line)}.direction-card{padding:20px;display:flex;flex-direction:column;min-height:330px}.direction-card.selected{border-color:var(--brand);box-shadow:0 0 0 3px rgba(47,93,229,.09),var(--shadow)}.direction-number{display:grid;place-items:center;width:30px;height:30px;border-radius:10px;background:var(--brand-soft);color:var(--brand);font-weight:800}.alternative{color:var(--muted)}.direction-card dl{display:grid;grid-template-columns:42px 1fr;gap:8px;margin:10px 0 20px}.direction-card dt{color:var(--muted)}.direction-card dd{margin:0}.direction-card .choose-direction{margin-top:auto;width:100%}.selected-summary{display:grid;grid-template-columns:1fr auto;align-items:center;gap:14px;padding:15px 18px;border-radius:14px;background:var(--brand-soft);color:#203d9f}.preview-card{padding:18px}.preview-toolbar{display:flex;justify-content:space-between;gap:16px;align-items:center;flex-wrap:wrap;margin-bottom:14px}.segmented{display:flex;gap:5px;padding:4px;border-radius:13px;background:#eef1f5}.segmented button{min-height:38px;border:0;background:transparent}.segmented button[aria-pressed="true"]{background:#fff;color:var(--brand);box-shadow:0 2px 8px rgba(31,47,76,.08)}.preview-frame{width:min(100%,var(--preview-width));margin:auto;border:1px solid var(--line);border-radius:18px;background:#f8fafc;padding:12px;transition:width .2s ease}.preview-panes{display:grid;grid-template-columns:1fr;gap:12px}.preview-pane{display:none;min-width:0}.preview-frame[data-preview-mode="before"] .before-pane,.preview-frame[data-preview-mode="after"] .after-pane{display:block}.preview-frame[data-preview-mode="compare"] .preview-panes{grid-template-columns:1fr 1fr}.preview-frame[data-preview-mode="compare"] .preview-pane{display:block}.pane-label{display:flex;justify-content:space-between;align-items:center;margin:0 2px 7px;color:var(--muted);font-size:13px}.legacy-surface,.after-workspace,.reference-shot{min-height:470px;padding:18px;border:1px solid var(--line);border-radius:14px;background:#fff}.legacy-head,.workbench-head{display:flex;justify-content:space-between;gap:12px;align-items:center}.legacy-tools,.workbench-filter{display:flex;gap:6px;margin:18px 0;flex-wrap:wrap}.legacy-tools input,.workbench-filter input{min-width:200px;flex:1;min-height:44px;border:1px solid var(--line);border-radius:10px;padding:8px 10px}.legacy-table{min-width:680px;padding:12px;border:1px solid var(--line);border-radius:8px;color:#596273}.before-pane{overflow:auto}.reference-shot{margin:0}.reference-shot img{display:block;max-width:100%;height:auto;margin:auto}.reference-shot figcaption{text-align:center;color:var(--muted);padding:10px}.workbench-head h4,.legacy-head h4{font-size:20px;margin:3px 0}.workbench-head small{color:var(--muted)}.workbench-filter button[aria-pressed="true"]{background:var(--brand-soft);border-color:#9eafe4;color:#2449bd}.filter-feedback{color:var(--muted);font-size:13px;margin:-10px 0 12px}.workbench-grid{display:grid;grid-template-columns:minmax(250px,.9fr) minmax(280px,1.1fr);gap:12px}.customer-list,.customer-detail{border:1px solid var(--line);border-radius:13px;overflow:hidden}.customer{width:100%;display:flex;justify-content:space-between;align-items:center;text-align:left;border:0;border-bottom:1px solid var(--line);border-radius:0;padding:14px}.customer span b,.customer span small{display:block}.customer span small{color:var(--muted)}.customer em{font-style:normal;font-size:12px;border-radius:999px;padding:4px 8px;background:#f5f0e4;color:#7b5514}.customer.selected{background:var(--brand-soft);box-shadow:inset 3px 0 var(--brand)}.customer-detail{padding:17px}.customer-detail h5{font-size:21px;margin:8px 0}.customer-detail dl{display:grid;grid-template-columns:75px 1fr;gap:10px}.customer-detail dt{color:var(--muted)}.customer-detail dd{margin:0;font-weight:650}.status-chip{display:inline-flex;border-radius:999px;padding:4px 8px;background:#fff4d8;color:#7b4b00;font-size:12px}.detail-actions{display:flex;justify-content:flex-end;gap:8px;margin-top:18px}.detail-back{display:none}.preview-state{min-height:320px;place-content:center;text-align:center}.preview-state:not([hidden]){display:grid}.preview-state h5{font-size:22px;margin:0}.after-workspace[data-direction-style="efficiency"]{--brand:#176f59}.after-workspace[data-direction-style="incremental"]{--brand:#536078}.state-controls{display:flex;gap:6px;flex-wrap:wrap;margin-top:12px}.state-controls button[aria-pressed="true"]{background:var(--brand-soft);border-color:#9eafe4;color:#2449bd}.handoff{padding:24px;display:grid;grid-template-columns:1fr auto;gap:18px;align-items:center}.handoff h2{margin:0}.handoff p{margin:6px 0 0;color:var(--muted)}.handoff-result{margin-top:14px;padding:15px;border-radius:13px;background:#eef8f3;color:#1f5e48}.handoff-result[hidden]{display:none}.technical{padding:0 20px}.technical summary{cursor:pointer;padding:18px 0;font-weight:750}.technical-body{padding:0 0 20px}.tech-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}.tech-grid article{padding:12px;border-radius:12px;background:#f7f8fa}.tech-grid span,.tech-grid b{display:block}.tech-grid span{color:var(--muted)}.code-list{word-break:break-word}.intent-switcher{margin-top:18px}.intent-grid{display:grid;grid-template-columns:repeat(5,1fr);gap:8px;padding:10px 0}.intent-grid button{height:auto;min-height:92px;text-align:left;padding:12px}.intent-grid button b,.intent-grid button span{display:block}.intent-grid button span{font-size:12px;color:var(--muted);margin-top:5px}.intent-grid button[aria-pressed="true"]{border-color:var(--brand);background:var(--brand-soft)}dialog{width:min(620px,calc(100vw - 28px));max-height:calc(100vh - 28px);border:0;border-radius:20px;padding:0;box-shadow:0 28px 80px rgba(18,30,55,.25)}dialog::backdrop{background:rgba(18,30,55,.46)}.dialog-body{padding:24px}.dialog-body h2{margin-top:0}.dialog-actions{display:flex;justify-content:flex-end;gap:8px;padding:14px 24px;border-top:1px solid var(--line)}.toast{position:fixed;right:18px;bottom:18px;z-index:50;max-width:360px;padding:12px 15px;border-radius:12px;background:#172133;color:#fff;opacity:0;transform:translateY(14px);pointer-events:none;transition:.2s}.toast.show{opacity:1;transform:none}
.segmented button{min-height:44px}[hidden]{display:none!important}
</style>
<style id="viewport-accuracy">
@media(max-width:900px){main{padding:22px 16px 60px}.hero{grid-template-columns:1fr}.problem-grid,.direction-grid{grid-template-columns:1fr 1fr}.intent-grid{grid-template-columns:1fr 1fr}.preview-frame[data-preview-mode="compare"] .preview-panes{grid-template-columns:1fr}}
@media(max-width:720px){.appbar{padding:10px 14px}.brand small{display:none}.problem-grid,.direction-grid{grid-template-columns:1fr}.section-head{align-items:flex-start;flex-direction:column}.selected-summary,.handoff{grid-template-columns:1fr}.preview-toolbar{align-items:flex-start;flex-direction:column}.segmented{width:100%;overflow:auto}.segmented button{flex:1;white-space:nowrap}.preview-card{padding:10px}.preview-frame{padding:8px}.workbench-grid{grid-template-columns:1fr}.workbench-grid .customer-detail{display:none}.workbench-grid.show-detail .customer-list{display:none}.workbench-grid.show-detail .customer-detail{display:block}.detail-back{display:inline-flex}.intent-grid{grid-template-columns:1fr}.tech-grid{grid-template-columns:1fr}}
@media(max-width:430px){main{padding:18px 10px 50px}.hero{padding:22px}.hero h1{font-size:32px}.problem-card,.direction-card{padding:17px}.workbench-head{align-items:flex-start;flex-direction:column}.workbench-head .primary{width:100%}.workbench-filter{display:grid}.legacy-surface,.after-workspace,.reference-shot{padding:12px}.dialog-actions{display:grid}.dialog-actions button{width:100%}}
@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important;transition:none!important}}
</style>
</head>
<body>
<header class="appbar"><div class="brand"><div class="mark" aria-hidden="true">W</div><div><b>WUQ</b><small>AI 产品体验顾问</small></div></div><button type="button" id="techJump">查看技术证据</button></header>
<main id="consultant-main">
  <section class="hero"><div><div class="eyebrow">AI EXPERIENCE CONSULTANT</div><h1>__OPENING__</h1><p>我会先解释最重要的问题，再推荐一个方向。你不需要理解底层分析术语。</p></div><aside class="understanding"><span>我理解的页面</span><b>__PAGE_LABEL__</b><small>主要任务</small><b>__PRIMARY_TASK__</b><small>__CONFIDENCE__</small></aside></section>
  <section id="problems"><div class="section-head"><div><h2>影响最大的三个地方</h2><p>按用户任务影响排序，不展示冗长问题清单。</p></div></div><div class="problem-grid">__PROBLEMS__</div></section>
  <section id="directions"><div class="section-head"><div><h2>我建议先选这个方向</h2><p>一个默认推荐，另外两个方向写清适用场景和取舍。</p></div></div><div class="direction-grid">__DIRECTIONS__</div><div class="selected-summary" aria-live="polite"><div><b id="selectedName">__SELECTED_NAME__</b><span id="selectedReason">__SELECTED_REASON__</span></div><button type="button" class="primary" id="viewPreview">查看推荐效果</button></div></section>
  <section id="preview"><div class="section-head"><div><h2>看看改变，而不只是读报告</h2><p>没有可信配对时会明确标注“结构示意”；结构预览不代表真实用户结果。</p></div></div><div class="preview-card"><div class="preview-toolbar"><div class="segmented" role="group" aria-label="预览模式"><button type="button" data-preview="before" aria-pressed="false">__BEFORE_LABEL__</button><button type="button" data-preview="after" aria-pressed="true">__AFTER_LABEL__</button><button type="button" data-preview="compare" aria-pressed="false">并排比较</button></div><div class="segmented" role="group" aria-label="预览宽度"><button type="button" data-width="1440" aria-pressed="true">桌面</button><button type="button" data-width="768" aria-pressed="false">平板</button><button type="button" data-width="390" aria-pressed="false">移动</button></div></div><div class="preview-frame" id="previewFrame" data-preview-mode="after"><div class="preview-panes"><article class="preview-pane before-pane"><div class="pane-label"><b>__BEFORE_LABEL__</b><span>__REFERENCE_BOUNDARY__</span></div>__REFERENCE_SURFACE__</article><article class="preview-pane after-pane"><div class="pane-label"><b>__AFTER_LABEL__</b><span id="directionPreviewLabel">__SELECTED_NAME__</span></div>__AFTER_SURFACE__</article></div></div><div class="state-controls" role="group" aria-label="查看关键状态"><button type="button" data-state="ready" aria-pressed="true">正常</button><button type="button" data-state="loading" aria-pressed="false">加载</button><button type="button" data-state="empty" aria-pressed="false">空态</button><button type="button" data-state="error" aria-pressed="false">错误与恢复</button><button type="button" data-state="success" aria-pressed="false">完成反馈</button></div></div></section>
  <section class="handoff"><div><h2>准备好后，生成实施清单</h2><p>先确认影响范围和回退方式。生成清单不等于授权修改源码。</p><div class="handoff-result" id="handoffResult" role="status" aria-live="polite" tabindex="-1" hidden><b>实施清单已准备</b><div id="handoffDirection"></div><p>尚未修改任何源码；应用修改仍需当前对话中的明确确认。</p></div></div><button type="button" class="primary" id="prepareHandoff">生成实施清单</button></section>
  <details id="technicalEvidence" class="technical"><summary>为什么这样建议 / 查看技术证据</summary><div class="technical-body">__TECHNICAL__</div></details>
  <details class="technical intent-switcher"><summary>重新选择改善目标</summary><div class="intent-grid">__INTENTS__</div><p id="intentStatus" role="status" aria-live="polite">当前结果仍按已分析的页面生成。</p></details>
</main>
<dialog id="handoffDialog" role="dialog" aria-labelledby="handoffTitle"><div class="dialog-body"><div class="eyebrow">SAFE HANDOFF</div><h2 id="handoffTitle">确认实施范围</h2><p>将为 <b id="dialogDirection">__SELECTED_NAME__</b> 生成一份有界实施清单。</p><ul id="dialogChanges"></ul><p><b>当前不会修改文件、安装依赖、发布或部署。</b></p></div><div class="dialog-actions"><button type="button" id="cancelHandoff">返回继续比较</button><button type="button" class="primary" id="confirmHandoff">确认生成清单</button></div></dialog>
<div class="toast" id="toast" role="status" aria-live="polite"></div>
<script>
const CONSULTATION=__PAYLOAD__;
const $=id=>document.getElementById(id);let selectedId=CONSULTATION.selectedDirectionId;let handoffOpener=null;
const directions=new Map(CONSULTATION.directions.map(item=>[item.id,item]));
function toast(message){const el=$('toast');el.textContent=message;el.classList.add('show');clearTimeout(toast.timer);toast.timer=setTimeout(()=>el.classList.remove('show'),2200)}
function selectDirection(id,focus=false,announce=true){const item=directions.get(id);if(!item)return;selectedId=id;document.querySelectorAll('[data-direction]').forEach(card=>card.classList.toggle('selected',card.dataset.direction===id));document.querySelectorAll('[data-choose-direction]').forEach(button=>{const active=button.dataset.chooseDirection===id;button.setAttribute('aria-pressed',String(active));button.textContent=active?'已选择':'选择这个方向'});$('selectedName').textContent=item.name;$('selectedReason').textContent=item.whyRecommended;$('directionPreviewLabel').textContent=item.name;$('afterWorkspace').dataset.directionStyle=id.endsWith('2')?'efficiency':id.endsWith('3')?'incremental':'balanced';if(focus)$('selectedName').scrollIntoView({block:'nearest'});if(announce)toast('已选择 '+item.name)}
document.querySelectorAll('[data-choose-direction]').forEach(button=>button.addEventListener('click',()=>selectDirection(button.dataset.chooseDirection,true)));
function setPreviewMode(mode){$('previewFrame').dataset.previewMode=mode;document.querySelectorAll('[data-preview]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.preview===mode)))}
document.querySelectorAll('[data-preview]').forEach(button=>button.addEventListener('click',()=>setPreviewMode(button.dataset.preview)));
document.querySelectorAll('[data-width]').forEach(button=>button.addEventListener('click',()=>{document.querySelectorAll('[data-width]').forEach(item=>item.setAttribute('aria-pressed','false'));button.setAttribute('aria-pressed','true');document.documentElement.style.setProperty('--preview-width',Math.min(Number(button.dataset.width),1160)+'px');toast('已切换到 '+button.textContent+'预览')}));
$('viewPreview').onclick=()=>{$('preview').scrollIntoView({behavior:'smooth'});setPreviewMode('after')};
const records={beichen:{name:'北辰物流',status:'待跟进',owner:'陈晨',next:'确认合同条款',updated:'今天 10:24'},yuanhang:{name:'远航科技',status:'正常',owner:'林岚',next:'安排季度回访',updated:'昨天 16:08'},qinghe:{name:'青禾制造',status:'待跟进',owner:'周敏',next:'补充联系人信息',updated:'本周一'}};
let selectedRecord='beichen';function selectRecord(id){const item=records[id];if(!item)return;selectedRecord=id;document.querySelectorAll('[data-record]').forEach(button=>{const active=button.dataset.record===id;button.classList.toggle('selected',active);button.setAttribute('aria-pressed',String(active))});$('detailName').textContent=item.name;$('detailStatus').textContent=item.status;$('detailOwner').textContent=item.owner;$('detailNext').textContent=item.next;$('detailUpdated').textContent=item.updated;$('workbenchGrid').classList.add('show-detail');toast('已打开 '+item.name+'，筛选状态已保留')}
document.querySelectorAll('[data-record]').forEach(button=>button.onclick=()=>selectRecord(button.dataset.record));$('detailBack').onclick=()=>{$('workbenchGrid').classList.remove('show-detail');const trigger=document.querySelector('[data-record="'+selectedRecord+'"]');if(trigger)trigger.focus()};
function applyFilter(value){document.querySelectorAll('[data-filter]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.filter===value)));document.querySelectorAll('[data-record]').forEach(button=>{const show=value==='all'||records[button.dataset.record].status==='待跟进';button.hidden=!show});$('filterFeedback').textContent=value==='follow'?'已应用：待跟进':'显示全部客户'}
document.querySelectorAll('[data-filter]').forEach(button=>button.onclick=()=>applyFilter(button.dataset.filter));$('customerSearch').oninput=e=>{const query=e.target.value.trim();document.querySelectorAll('[data-record]').forEach(button=>button.hidden=query&&!records[button.dataset.record].name.includes(query));$('filterFeedback').textContent=query?'搜索结果已更新':'显示全部客户'};
$('newCustomer').onclick=()=>toast('新建流程会先保存草稿，再进入确认。');$('addNote').onclick=()=>toast('活动记录已在预览中打开，尚未写入数据。');$('completeTask').onclick=()=>{$('detailStatus').textContent='已完成';toast('完成状态已反馈；真实操作仍需业务权限。')};
const stateCopy={loading:['正在理解页面','保留页面骨架，完成后自动显示结果。'],empty:['当前没有匹配结果','可以清除筛选或重新确认业务目标。'],error:['这一部分暂时不可用','已保留选择和输入，可以安全重试。'],success:['任务已完成','结果已保存，可以继续下一项。']};
function setState(state){document.querySelectorAll('[data-state]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.state===state)));const host=$('afterWorkspace'),panel=$('previewState');if(state==='ready'){host.querySelector('.workbench-head').hidden=false;host.querySelector('.workbench-filter').hidden=false;$('filterFeedback').hidden=false;$('workbenchGrid').hidden=false;panel.hidden=true}else{const copy=stateCopy[state];host.querySelector('.workbench-head').hidden=true;host.querySelector('.workbench-filter').hidden=true;$('filterFeedback').hidden=true;$('workbenchGrid').hidden=true;panel.hidden=false;$('stateTitle').textContent=copy[0];$('stateBody').textContent=copy[1]}}
document.querySelectorAll('[data-state]').forEach(button=>button.onclick=()=>setState(button.dataset.state));$('stateAction').onclick=()=>{setState('ready');document.querySelector('[data-state="ready"]').focus()};
$('prepareHandoff').onclick=e=>{handoffOpener=e.currentTarget;const item=directions.get(selectedId);$('dialogDirection').textContent=item.name;$('dialogChanges').replaceChildren(...item.changes.map(change=>{const li=document.createElement('li');li.textContent=change;return li}));$('handoffDialog').showModal()};
function closeHandoff(){ $('handoffDialog').close();if(handoffOpener)handoffOpener.focus() }
$('cancelHandoff').onclick=closeHandoff;$('handoffDialog').addEventListener('cancel',event=>{event.preventDefault();closeHandoff()});
$('confirmHandoff').onclick=()=>{const item=directions.get(selectedId);$('handoffDirection').textContent='已选择：'+item.name;$('handoffResult').hidden=false;$('handoffDialog').close();$('handoffResult').focus();toast('实施清单已生成，尚未修改任何源码')};
// Native Escape closes the dialog through the cancel handler and restores focus.
$('techJump').onclick=()=>{$('technicalEvidence').open=true;$('technicalEvidence').scrollIntoView({behavior:'smooth'});$('technicalEvidence').querySelector('summary').focus()};
document.querySelectorAll('[data-intent]').forEach(button=>button.onclick=()=>{$('intentStatus').textContent='已选择“'+button.querySelector('b').textContent+'”。重新分析需要提供对应页面或截图；当前结果已保留。'});
selectDirection(selectedId,false,false);
</script>
</body></html>'''


def generate_consultant_preview(
    consultation: Mapping[str, Any],
    diagnosis: Mapping[str, Any],
    output_dir: str | Path,
    *,
    title: str | None = None,
    reference_screenshot: str | Path | None = None,
) -> Path:
    """Write one dependency-free, safely bounded consultation review surface."""

    out = Path(output_dir).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    reference_name = None
    if reference_screenshot:
        source = Path(reference_screenshot).expanduser().resolve(strict=True)
        reference_name = "reference" + source.suffix.casefold()
        shutil.copyfile(source, out / reference_name)

    business = consultation.get("businessSummary") if isinstance(consultation.get("businessSummary"), Mapping) else {}
    preview = consultation.get("preview") if isinstance(consultation.get("preview"), Mapping) else {}
    directions = [item for item in consultation.get("directions", []) if isinstance(item, Mapping)]
    selected = next((item for item in directions if item.get("recommended")), directions[0] if directions else {})
    confidence = {"high": "判断把握：较高", "medium": "判断把握：中等，建议确认主任务", "low": "判断把握：较低，需要补充业务目标"}.get(str(business.get("confidence")), "需要确认业务目标")
    replacements = {
        "__TITLE__": _escape(title or business.get("pageTypeLabel") or "产品体验建议"),
        "__OPENING__": _escape(consultation.get("opening")),
        "__PAGE_LABEL__": _escape(business.get("pageTypeLabel")),
        "__PRIMARY_TASK__": _escape(business.get("primaryTask")),
        "__CONFIDENCE__": _escape(confidence),
        "__PROBLEMS__": _problem_cards(consultation),
        "__DIRECTIONS__": _direction_cards(consultation),
        "__SELECTED_NAME__": _escape(selected.get("name")),
        "__SELECTED_REASON__": _escape(selected.get("whyRecommended")),
        "__BEFORE_LABEL__": _escape(preview.get("beforeLabel")),
        "__AFTER_LABEL__": _escape(preview.get("afterLabel")),
        "__REFERENCE_BOUNDARY__": _escape("参考输入" if reference_name else "概念结构，不是实测截图"),
        "__REFERENCE_SURFACE__": _reference_surface(reference_name),
        "__AFTER_SURFACE__": _after_surface(),
        "__TECHNICAL__": _technical_content(consultation),
        "__INTENTS__": _intent_buttons(consultation),
        "__PAYLOAD__": _json(consultation),
    }
    page = _TEMPLATE
    for key, value in replacements.items():
        page = page.replace(key, value)
    path = out / "index.html"
    path.write_text(page, encoding="utf-8")
    return path


__all__ = ["generate_consultant_preview"]
