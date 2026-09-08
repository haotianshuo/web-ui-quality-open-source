"""Generate the Experience Modernization Studio around an executable preview.

The studio keeps the primary workflow small: one selected skeleton, the most
relevant alternatives, concrete UX repairs, mapped project tokens, responsive
preview controls, and acceptance evidence.  The full catalog is emitted as a
separate artifact so normal plans do not carry thousands of unused entries.
"""
from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any, Mapping

from .experience_catalog import (
    catalog_metrics,
    component_catalog,
    interaction_catalog,
    page_skeleton_catalog,
    specialised_pattern_catalog,
    state_catalog,
)


def _dump(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def build_library_artifact() -> dict[str, Any]:
    return {
        "schemaVersion": "2.1",
        "metrics": catalog_metrics(),
        "components": component_catalog(),
        "pageSkeletons": page_skeleton_catalog(),
        "interactionPatterns": interaction_catalog(),
        "contextualStates": state_catalog(),
        "specialisedPatterns": specialised_pattern_catalog(),
    }


def generate_experience_studio(
    plan: Mapping[str, Any],
    output_dir: str | Path,
    *,
    preview_relative: str = "../preview/index.html",
    title: str | None = None,
) -> Path:
    out = Path(output_dir).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    library = build_library_artifact()
    _dump(out / "experience-library.json", library)
    generate_library_gallery(out)
    _dump(out / "ux-repair-plan.json", plan.get("uxRepairPlan", {}))
    _dump(out / "project-design-system.json", plan.get("projectDesignSystem", {}))
    _dump(out / "experience-plan.json", plan)

    dtcg = (plan.get("visualSystem") or {}).get("dtcg") or {}
    _dump(out / "visual-tokens.dtcg.json", dtcg)
    project_dtcg = (plan.get("projectDesignSystem") or {}).get("dtcg") or {}
    _dump(out / "project-tokens.dtcg.json", project_dtcg)
    compatibility = str((plan.get("projectDesignSystem") or {}).get("compatibilityCss") or "")
    (out / "compatibility.css").write_text(compatibility, encoding="utf-8")

    selected = plan.get("selectedSkeleton") or {}
    pattern = plan.get("selectedPattern") or {}
    visual = plan.get("visualSystem") or {}
    repairs = plan.get("uxRepairPlan") or {}
    system_map = plan.get("projectDesignSystem") or {}
    interaction = plan.get("interactionContract") or {}
    alternatives = list(plan.get("skeletonAlternatives") or [])[:4]
    components = list((plan.get("library") or {}).get("selectedComponents") or [])
    interactions = list(interaction.get("selectedInteractionPatterns") or [])
    states = list(interaction.get("contextualStates") or [])
    app_title = title or "Web UI Quality · Experience Modernization Studio"

    payload = json.dumps(
        {
            "selectedSkeleton": selected,
            "alternatives": alternatives,
            "repairs": repairs,
            "systemMap": system_map,
            "components": components,
            "interactions": interactions,
            "states": states,
            "acceptance": plan.get("acceptance", {}),
            "quality": plan.get("qualityReadiness", {}),
            "metrics": library["metrics"],
        }, ensure_ascii=False,
    ).replace("</", "<\\/")

    page = f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(app_title)}</title><style>
:root{{--bg:#f4f6f8;--surface:#fff;--surface2:#f8fafc;--text:#17202a;--muted:#667085;--line:#dfe5ec;--brand:#2563eb;--brand2:#1d4ed8;--good:#0f8a5f;--warn:#b76e00;--bad:#c43d4b;--radius:14px;--shadow:0 16px 50px rgba(31,41,55,.10);font-family:Inter,"Segoe UI","PingFang SC",sans-serif;color-scheme:light}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text)}}button,select{{font:inherit}}button{{cursor:pointer}}.app{{min-height:100vh;display:grid;grid-template-rows:auto 1fr}}header{{height:64px;padding:0 18px;display:flex;align-items:center;justify-content:space-between;background:rgba(255,255,255,.92);border-bottom:1px solid var(--line);backdrop-filter:blur(16px);position:sticky;top:0;z-index:20}}.brand{{display:flex;gap:11px;align-items:center}}.mark{{width:32px;height:32px;border-radius:10px;background:linear-gradient(145deg,var(--brand),#74a5ff);box-shadow:inset 0 1px rgba(255,255,255,.5)}}h1{{font-size:17px;margin:0}}.subtitle{{font-size:12px;color:var(--muted);margin-top:2px}}.toolbar{{display:flex;gap:8px;align-items:center}}button,select{{min-height:36px;border:1px solid var(--line);border-radius:10px;background:var(--surface);padding:0 11px;color:var(--text)}}button.primary{{background:var(--brand);border-color:var(--brand);color:#fff}}.layout{{min-height:0;display:grid;grid-template-columns:270px minmax(480px,1fr) 360px}}nav,.inspector{{background:var(--surface);overflow:auto}}nav{{border-right:1px solid var(--line);padding:16px}}.inspector{{border-left:1px solid var(--line)}}.section-title{{font-size:11px;font-weight:750;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin:18px 8px 8px}}.tab{{width:100%;display:flex;align-items:center;gap:10px;text-align:left;border:0;background:transparent;margin:2px 0}}.tab.active{{background:#eef4ff;color:var(--brand2);font-weight:700}}.count{{margin-left:auto;border-radius:999px;background:var(--surface2);padding:2px 7px;font-size:11px}}.summary{{padding:13px;border:1px solid var(--line);background:var(--surface2);border-radius:12px}}.summary b{{display:block;margin-bottom:5px}}main{{padding:16px;overflow:auto}}.canvas-shell{{height:calc(100vh - 98px);display:grid;grid-template-rows:auto minmax(0,1fr);background:#dfe5ec;border:1px solid #cdd6e0;border-radius:16px;overflow:hidden;box-shadow:var(--shadow)}}.canvas-bar{{display:flex;gap:8px;align-items:center;padding:8px;background:#f8fafc;border-bottom:1px solid #ccd5df}}.canvas-bar .spacer{{flex:1}}.viewport{{display:grid;place-items:center;overflow:auto;padding:16px}}iframe{{display:block;border:0;background:#fff;width:100%;height:100%;min-height:640px;border-radius:9px;box-shadow:0 12px 38px rgba(31,41,55,.16);transition:width .2s ease}}.inspector-head{{padding:16px;border-bottom:1px solid var(--line);position:sticky;top:0;background:var(--surface);z-index:4}}.panel{{display:none;padding:16px}}.panel.active{{display:block}}.metric-grid{{display:grid;grid-template-columns:1fr 1fr;gap:8px}}.metric{{padding:10px;border-radius:11px;background:var(--surface2);border:1px solid var(--line)}}.metric b{{display:block;font-size:20px}}.item{{padding:11px 0;border-bottom:1px solid var(--line)}}.item:last-child{{border:0}}.item h3{{font-size:14px;margin:0 0 5px}}.item p,.item li{{font-size:12px;line-height:1.55;color:var(--muted)}}.item ul{{margin:6px 0;padding-left:18px}}.badge{{display:inline-flex;border-radius:999px;padding:3px 7px;font-size:11px;background:#edf2f7;color:var(--muted)}}.badge.good{{background:#e7f6ef;color:var(--good)}}.badge.warn{{background:#fff4df;color:var(--warn)}}.repair{{border-left:3px solid var(--line);padding-left:10px}}.repair.P1{{border-color:var(--bad)}}.repair.P2{{border-color:var(--warn)}}.empty{{padding:22px;text-align:center;color:var(--muted)}}@media(max-width:1200px){{.layout{{grid-template-columns:220px minmax(400px,1fr) 310px}}}}@media(max-width:920px){{.layout{{grid-template-columns:1fr}}nav{{display:none}}.inspector{{border:0}}main{{min-height:720px}}.canvas-shell{{height:680px}}}}@media(prefers-reduced-motion:reduce){{*{{scroll-behavior:auto!important;transition-duration:.01ms!important}}}}
</style></head><body><div class="app"><header><div class="brand"><span class="mark"></span><div><h1>{html.escape(app_title)}</h1><div class="subtitle">{html.escape(str(pattern.get('name') or '页面体验方案'))} · {html.escape(str(selected.get('name') or '推荐骨架'))}</div></div></div><div class="toolbar"><select id="viewportSelect" aria-label="预览宽度"><option value="1440">桌面 1440</option><option value="1024">中屏 1024</option><option value="768">平板 768</option><option value="390">手机 390</option></select><button id="themeBtn">切换主题</button><button id="densityBtn">切换密度</button><button class="primary" id="openBtn">独立打开预览</button></div></header><div class="layout"><nav><div class="summary"><b>{html.escape(str(selected.get('name') or '推荐页面骨架'))}</b><span class="badge good">{html.escape(str(selected.get('score', '—')))} 分</span><p>{html.escape(str(selected.get('goal') or ''))}</p></div><div class="section-title">评审区域</div><button class="tab active" data-panel="overview">总览<span class="count">1</span></button><button class="tab" data-panel="repairs">错位与体验修复<span class="count">{int(repairs.get('findingCount') or 0)}</span></button><button class="tab" data-panel="alternatives">页面骨架<span class="count">{1+len(alternatives)}</span></button><button class="tab" data-panel="components">组件与交互<span class="count">{len(components)+len(interactions)}</span></button><button class="tab" data-panel="states">状态与恢复<span class="count">{len(states)}</span></button><button class="tab" data-panel="tokens">项目设计系统<span class="count">{int(system_map.get('cssVariableCount') or 0)}</span></button><button class="tab" data-panel="acceptance">验收<span class="count">4</span></button><div class="section-title">资产</div><div class="summary"><b>Experience Library</b><p>完整目录单独写入 <code>experience-library.json</code>，避免污染主任务上下文。</p><p><a href="library.html" target="_blank">打开可搜索资产库 →</a></p></div></nav><main><div class="canvas-shell"><div class="canvas-bar"><span class="badge">实时可交互预览</span><span id="viewportLabel">1440px</span><span class="spacer"></span><span class="badge">渐进增强 + 可退化</span></div><div class="viewport"><iframe id="preview" title="Experience preview" src="{html.escape(preview_relative)}"></iframe></div></div></main><aside class="inspector"><div class="inspector-head"><b>体验方案检查器</b><div class="subtitle">方案、修复、组件和验收保持同一上下文</div></div><section class="panel active" id="overview"></section><section class="panel" id="repairs"></section><section class="panel" id="alternatives"></section><section class="panel" id="components"></section><section class="panel" id="states"></section><section class="panel" id="tokens"></section><section class="panel" id="acceptance"></section></aside></div></div><script>
const DATA={payload};const frame=document.getElementById('preview');const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));
function item(title,body,badge=''){{return `<article class="item"><h3>${{esc(title)}} ${{badge?`<span class="badge">${{esc(badge)}}</span>`:''}}</h3>${{body}}</article>`}}
function list(values){{return `<ul>${{(values||[]).map(v=>`<li>${{esc(v)}}</li>`).join('')}}</ul>`}}
const selected=DATA.selectedSkeleton||{{}};document.getElementById('overview').innerHTML=`<div class="metric-grid"><div class="metric"><span>实施准备度</span><b>${{esc(DATA.quality.score??'—')}}</b><small>${{esc(DATA.quality.status||'待评审')}}</small></div><div class="metric"><span>UX 基线</span><b>${{esc(DATA.repairs.score??'—')}}</b><small>静态体验分</small></div><div class="metric"><span>组件资产</span><b>${{DATA.metrics.components}}</b><small>可组合原语</small></div><div class="metric"><span>交互模式</span><b>${{DATA.metrics.interactions}}</b><small>完整合同</small></div></div>${{item(selected.name||'推荐骨架',`<p>${{esc(selected.goal||'')}}</p>${{list(selected.reasons)}}`)}}${{item('桌面 / 中屏 / 移动',list([selected.composition?.desktop||selected.desktop,selected.composition?.tablet||selected.tablet,selected.composition?.mobile||selected.mobile]))}}`;
const repairItems=[...(DATA.repairs.quickWins||[]),...(DATA.repairs.structuralRepairs||[])];document.getElementById('repairs').innerHTML=repairItems.length?repairItems.map(r=>`<article class="item repair ${{esc(r.severity||'')}}"><h3>${{esc(r.title||r.id)}} <span class="badge">${{esc(r.severity||'')}}</span></h3><p>${{esc(r.problem||r.message||'')}}</p>${{(r.repair||r.recommendation)?`<p><b>修复：</b>${{esc(r.repair||r.recommendation)}}</p>`:''}}${{r.fallback?`<p><b>退化：</b>${{esc(r.fallback)}}</p>`:''}}</article>`).join(''):'<div class="empty">未发现高置信静态错位问题；仍需 Browser 三档视口验收。</div>';
document.getElementById('alternatives').innerHTML=[selected,...DATA.alternatives].map((s,i)=>item(s.name||s.id,`<p>${{esc(s.goal||'')}}</p>${{list(s.reasons||s.useWhen)}}`,i===0?'当前推荐':`${{s.score??'—'}} 分`)).join('');
document.getElementById('components').innerHTML=(DATA.components||[]).map(c=>item(c.name||c.id,`<p>${{esc(c.purpose||'')}}</p>${{list([...(c.behaviours||[]),...(c.responsive||[]).slice(0,1)])}}`,c.category||'component')).join('')+(DATA.interactions||[]).map(x=>item(x.name||x.id,`<p><b>反馈：</b>${{esc(x.immediate_feedback||'')}}</p><p><b>失败恢复：</b>${{esc(x.recovery||'')}}</p>`,x.modality||'interaction')).join('');
document.getElementById('states').innerHTML=(DATA.states||[]).map(s=>item(s.state||s.id,`<p>${{esc(s.presentation||s.meaning||'')}}</p><p><b>下一步：</b>${{esc(s.primary_action||'')}}</p><p><b>数据：</b>${{esc(s.persistence||'')}}</p>`,s.context||'state')).join('');
const metrics=DATA.systemMap.metrics||{{}};document.getElementById('tokens').innerHTML=`<div class="metric-grid"><div class="metric"><span>Token 复用</span><b>${{Math.round(metrics.tokenReuseRatio||0)}}%</b></div><div class="metric"><span>颜色语义化</span><b>${{Math.round(metrics.colourTokenRatio||0)}}%</b></div><div class="metric"><span>间距一致性</span><b>${{Math.round(metrics.spacingGridCoherence||0)}}%</b></div><div class="metric"><span>综合一致性</span><b>${{Math.round(metrics.consistencyScore||0)}}%</b></div></div>${{item('兼容策略',list(DATA.systemMap.recommendations||[]))}}`;
const acceptance=DATA.acceptance||{{}};document.getElementById('acceptance').innerHTML=Object.entries(acceptance).map(([k,v])=>item(k,list(v))).join('');
document.querySelectorAll('.tab').forEach(btn=>btn.onclick=()=>{{document.querySelectorAll('.tab').forEach(x=>x.classList.remove('active'));document.querySelectorAll('.panel').forEach(x=>x.classList.remove('active'));btn.classList.add('active');document.getElementById(btn.dataset.panel).classList.add('active')}});
const widths={{1440:'100%',1024:'1024px',768:'768px',390:'390px'}};document.getElementById('viewportSelect').onchange=e=>{{frame.style.width=widths[e.target.value];document.getElementById('viewportLabel').textContent=e.target.value+'px'}};let dark=false;document.getElementById('themeBtn').onclick=()=>{{dark=!dark;frame.contentWindow?.postMessage({{type:'wuq:set-theme',value:dark?'dark':'light'}},'*')}};const densities=['comfortable','dense','touch'];let di=0;document.getElementById('densityBtn').onclick=()=>{{di=(di+1)%densities.length;frame.contentWindow?.postMessage({{type:'wuq:set-density',value:densities[di]}},'*')}};document.getElementById('openBtn').onclick=()=>window.open(frame.src,'_blank','noopener');
</script></body></html>'''
    page = _postprocess_studio_html(page)
    path = out / "index.html"
    path.write_text(page, encoding="utf-8")
    return path


def _postprocess_studio_html(page: str) -> str:
    """Keep the Studio navigable on narrow screens and expose tab semantics."""
    css = """
/* WUQ Studio mobile navigation and keyboard contract. */
button:focus-visible,select:focus-visible,a:focus-visible{outline:3px solid #7c8cff;outline-offset:2px}
@media(max-width:920px){
  html,body{max-width:100vw;overflow-x:hidden}
  header{height:auto;min-height:64px;padding:8px;align-items:flex-start;flex-wrap:wrap;gap:8px}
  .brand{min-width:0;flex:1 1 180px;overflow:hidden}.brand>div{min-width:0}.brand h1{font-size:14px}.brand .subtitle{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .toolbar{min-width:0;max-width:100%;flex:1 1 100%;overflow-x:auto;overflow-y:hidden;flex-wrap:nowrap;padding-bottom:2px}.toolbar>*{flex:0 0 auto}
  #mobileNavToggle{display:inline-flex!important}
  nav{display:none!important;position:absolute;inset:0 auto auto 0;width:min(300px,86vw);max-height:calc(100dvh - 120px);z-index:30;box-shadow:18px 0 40px rgba(31,41,55,.18)}
  nav.open{display:block!important}
  .layout{position:relative;width:100%;min-width:0}.layout>main,.inspector{width:100%;min-width:0}
  main{padding:8px}.canvas-shell{width:100%;max-width:100%;height:min(680px,calc(100dvh - 128px))}.viewport{width:100%;min-width:0;justify-items:center}
}
@media(max-width:560px){.brand{flex-basis:100%}.brand .subtitle{display:none}.canvas-bar{font-size:11px;overflow-x:auto;white-space:nowrap}}
@media(min-width:921px){#mobileNavToggle{display:none!important}}
"""
    page = page.replace("</style>", css + "</style>", 1)
    script = r"""
(function(){
  const nav=document.querySelector('nav'),header=document.querySelector('header'),toolbar=document.querySelector('.toolbar');
  if(nav&&toolbar&&!document.getElementById('mobileNavToggle')){
    const button=document.createElement('button');button.id='mobileNavToggle';button.type='button';button.textContent='导航';button.setAttribute('aria-controls','studio-nav');button.setAttribute('aria-expanded','false');nav.id='studio-nav';
    toolbar.insertBefore(button,toolbar.firstChild);button.addEventListener('click',function(){const open=nav.classList.toggle('open');button.setAttribute('aria-expanded',String(open));if(open)nav.querySelector('button')?.focus()});
    nav.addEventListener('click',function(event){if(event.target.closest('.tab')){nav.classList.remove('open');button.setAttribute('aria-expanded','false')}});
  }
  document.querySelectorAll('.tab').forEach(function(tab,index){
    const panel=tab.getAttribute('data-panel');tab.setAttribute('role','tab');tab.setAttribute('aria-controls',panel||'');tab.setAttribute('aria-selected',tab.classList.contains('active')?'true':'false');tab.id=tab.id||'studio-tab-'+index;
    const target=panel&&document.getElementById(panel);if(target){target.setAttribute('role','tabpanel');target.setAttribute('aria-labelledby',tab.id)}
    tab.addEventListener('click',function(){document.querySelectorAll('.tab').forEach(function(other){other.setAttribute('aria-selected',other.classList.contains('active')?'true':'false')})});
  });
  const select=document.getElementById('viewportSelect');
  if(select){const frame=document.getElementById('preview');const widths={1440:'1440px',1024:'1024px',768:'768px',390:'390px'};select.addEventListener('change',function(){if(frame)frame.style.width=widths[this.value]||'100%'});select.dispatchEvent(new Event('change'))}
})();
"""
    return page.replace("</script></body></html>", "</script><script>" + script + "</script></body></html>", 1)


def generate_library_gallery(output_dir: str | Path) -> Path:
    """Create a searchable, dependency-free browser for all Experience assets."""
    out = Path(output_dir).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    data = build_library_artifact()
    _dump(out / "experience-library.json", data)
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    page = f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Experience Fusion Library</title><style>
:root{{--bg:#f5f7fa;--surface:#fff;--text:#17202a;--muted:#667085;--line:#dde4ec;--brand:#2563eb;font-family:Inter,"Segoe UI","PingFang SC",sans-serif}}*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text)}}header{{position:sticky;top:0;z-index:5;background:rgba(255,255,255,.94);backdrop-filter:blur(14px);border-bottom:1px solid var(--line);padding:18px clamp(18px,4vw,52px)}}h1{{margin:0 0 4px;font-size:22px}}p{{color:var(--muted)}}.controls{{display:grid;grid-template-columns:minmax(220px,1fr) 180px 180px;gap:10px;margin-top:14px}}input,select{{min-height:42px;border:1px solid var(--line);border-radius:10px;background:#fff;padding:0 12px;font:inherit}}main{{padding:24px clamp(18px,4vw,52px)}}.metrics{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:18px}}.metric,.card{{background:var(--surface);border:1px solid var(--line);border-radius:14px}}.metric{{padding:14px}}.metric b{{display:block;font-size:23px}}.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px}}.card{{padding:15px;display:grid;gap:9px}}.card h2{{font-size:16px;margin:0}}.tag{{display:inline-flex;width:max-content;padding:3px 7px;border-radius:999px;background:#edf3ff;color:#1d4ed8;font-size:11px}}.row{{display:flex;gap:7px;flex-wrap:wrap}}.card ul{{margin:0;padding-left:17px;color:var(--muted);font-size:12px;line-height:1.5}}.empty{{padding:60px;text-align:center;color:var(--muted)}}@media(max-width:760px){{.controls{{grid-template-columns:1fr}}.metrics{{grid-template-columns:repeat(2,1fr)}}}}
</style></head><body><header><h1>Experience Fusion Library</h1><p>50 页面骨架、100 交互合同、200 场景状态与专项企业构图。资产保存设计意图、行为、恢复和验收，不复制第三方组件代码。</p><div class="controls"><input id="search" type="search" placeholder="搜索名称、任务、组件、状态…"><select id="type"><option value="skeleton">页面骨架</option><option value="component">组件原语</option><option value="interaction">交互模式</option><option value="state">状态模式</option><option value="dashboard">Dashboard 构图</option></select><select id="family"><option value="">全部场景</option></select></div></header><main><div class="metrics" id="metrics"></div><div class="grid" id="grid"></div></main><script>
const DATA={payload};const $=id=>document.getElementById(id);const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));const metrics=DATA.metrics;$('metrics').innerHTML=[['页面骨架',metrics.pageSkeletons],['交互合同',metrics.interactions],['场景状态',metrics.contextualStates],['组件原语',metrics.components]].map(x=>`<div class="metric"><span>${{x[0]}}</span><b>${{x[1]}}</b></div>`).join('');
const types={{skeleton:DATA.pageSkeletons,component:DATA.components,interaction:DATA.interactionPatterns,state:DATA.contextualStates,dashboard:DATA.specialisedPatterns.dashboards}};function family(item){{return item.family||item.category||item.context||item.modality||'general'}}function resetFamilies(){{const values=[...new Set(types[$('type').value].map(family))].sort();$('family').innerHTML='<option value="">全部场景</option>'+values.map(v=>`<option>${{esc(v)}}</option>`).join('')}}function describe(item){{const lists=[item.use_when||item.useWhen,item.behaviours,item.telemetry,item.acceptance,item.states,item.interactions].filter(Boolean).flat().slice(0,5);return `<article class="card"><div class="row"><span class="tag">${{esc(family(item))}}</span><span class="tag">${{esc(item.id)}}</span></div><h2>${{esc(item.name||item.state||item.id)}}</h2><p>${{esc(item.goal||item.purpose||item.meaning||item.intent||'')}}</p>${{lists.length?`<ul>${{lists.map(v=>`<li>${{esc(v)}}</li>`).join('')}}</ul>`:''}}</article>`}}function render(){{const q=$('search').value.trim().toLowerCase(),f=$('family').value;const items=types[$('type').value].filter(item=>(!f||family(item)===f)&&(!q||JSON.stringify(item).toLowerCase().includes(q)));$('grid').innerHTML=items.length?items.map(describe).join(''):'<div class="empty">没有匹配资产</div>'}}$('type').onchange=()=>{{resetFamilies();render()}};$('family').onchange=render;$('search').oninput=render;resetFamilies();render();
</script></body></html>'''
    page = page.replace('<input id="search"', '<input id="search" aria-label="搜索资产"')
    page = page.replace('<select id="type">', '<select id="type" aria-label="资产类型"')
    page = page.replace('<select id="family">', '<select id="family" aria-label="业务场景"')
    path = out / "library.html"
    path.write_text(page, encoding="utf-8")
    return path
