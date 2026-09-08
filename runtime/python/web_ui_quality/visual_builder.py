"""Dependency-free visual builder for Experience Core and Design IR.

The builder is intentionally local and serialises edits as candidate Design IR.
It supports direct manipulation, responsive previews, undo/redo, token controls,
component insertion, reorder, export, and production-plan inspection.  It does not
modify the source project or execute package installation.
"""
from __future__ import annotations

from copy import deepcopy
import html
import json
from pathlib import Path
from typing import Any, Mapping

from .design_ir import build_document, make_node


def _default_ir(plan: Mapping[str, Any]) -> dict[str, Any]:
    model = plan.get("experienceModel") if isinstance(plan.get("experienceModel"), Mapping) else {}
    skeleton = plan.get("selectedSkeleton") if isinstance(plan.get("selectedSkeleton"), Mapping) else {}
    title = str(model.get("primaryTask") or skeleton.get("name") or "企业体验工作台")
    subtitle = str(skeleton.get("goal") or "通过清晰层级、可恢复交互和响应式布局完成主任务")
    primary = str((model.get("operations") or ["继续处理"])[0] if isinstance(model.get("operations"), list) and model.get("operations") else "继续处理")
    roots = [make_node(
        "page-root", "page", name="Page", style={"layout": "page", "padding": "24px", "background": "var(--canvas-bg)"},
        children=[
            make_node("hero", "section", name="Page header", style={"display": "flex", "direction": "row", "justify": "space-between", "align": "center", "gap": "16px", "padding": "20px"}, children=[
                make_node("hero-copy", "stack", name="Header copy", style={"display": "flex", "direction": "column", "gap": "6px"}, children=[
                    make_node("eyebrow", "text", name="Eyebrow", content="EXPERIENCE CANDIDATE", style={"fontSize": "11px", "fontWeight": 700, "letterSpacing": ".12em", "color": "var(--muted)"}),
                    make_node("title", "text", name="Title", content=title, style={"fontSize": "32px", "fontWeight": 760, "lineHeight": 1.15}),
                    make_node("subtitle", "text", name="Subtitle", content=subtitle, style={"fontSize": "14px", "color": "var(--muted)", "maxWidth": "680px"}),
                ]),
                make_node("primary-action", "button", name="Primary action", content=primary, style={"background": "var(--brand)", "color": "#fff", "padding": "11px 16px", "borderRadius": "12px"}, semantics={"role": "button", "priority": "primary"}),
            ]),
            make_node("toolbar", "section", name="Toolbar", style={"display": "flex", "direction": "row", "justify": "space-between", "align": "center", "gap": "12px", "padding": "12px", "background": "var(--surface)", "border": "1px solid var(--line)", "borderRadius": "14px"}, children=[
                make_node("search", "input", name="Search", content="搜索业务对象", style={"width": "min(360px, 100%)", "padding": "10px 12px", "border": "1px solid var(--line)", "borderRadius": "10px"}, semantics={"role": "searchbox", "label": "搜索"}),
                make_node("result-count", "badge", name="Result count", content="24 条结果", style={"background": "var(--soft)", "padding": "6px 9px", "borderRadius": "999px", "fontSize": "12px"}),
            ]),
            make_node("workspace", "section", name="Workspace", style={"display": "grid", "layout": "split", "gap": "12px", "gridTemplateColumns": "minmax(260px,.8fr) minmax(360px,1.4fr)"}, children=[
                make_node("list-card", "card", name="Object list", style={"padding": "12px", "background": "var(--surface)", "border": "1px solid var(--line)", "borderRadius": "16px"}, children=[
                    make_node("list-title", "text", name="List title", content="待处理对象", style={"fontSize": "15px", "fontWeight": 700}),
                    make_node("list", "list", name="Items", children=[
                        make_node(f"item-{index}", "list-item", name=f"Item {index}", content=f"对象 {index:02d} · 待处理", style={"padding": "12px", "borderRadius": "10px", "background": "var(--soft)" if index == 1 else "transparent"})
                        for index in range(1, 5)
                    ]),
                ]),
                make_node("detail-card", "card", name="Detail", style={"padding": "20px", "background": "var(--surface)", "border": "1px solid var(--line)", "borderRadius": "16px", "minHeight": "340px"}, children=[
                    make_node("status", "badge", name="Status", content="待处理", style={"background": "#fff3d6", "color": "#7a4c00", "padding": "5px 9px", "borderRadius": "999px", "fontSize": "12px"}),
                    make_node("detail-title", "text", name="Detail title", content="对象 01", style={"fontSize": "26px", "fontWeight": 760}),
                    make_node("detail-copy", "text", name="Detail text", content="这里展示真实字段、状态、权限与下一步。预览中的动作不会执行生产副作用。", style={"color": "var(--muted)", "lineHeight": 1.6}),
                    make_node("detail-actions", "stack", name="Actions", style={"display": "flex", "direction": "row", "justify": "flex-end", "gap": "10px", "padding": "24px 0 0"}, children=[
                        make_node("secondary", "button", name="Secondary", content="保存草稿", style={"padding": "10px 14px", "background": "var(--surface)", "border": "1px solid var(--line)", "borderRadius": "10px"}),
                        make_node("confirm", "button", name="Confirm", content=primary, style={"padding": "10px 14px", "background": "var(--brand)", "color": "#fff", "borderRadius": "10px"}),
                    ]),
                ]),
            ]),
        ],
    )]
    return build_document(source_type="experience-plan", source_name="generated-experience", roots=roots, metadata={"experienceDigest": plan.get("experienceDigest")})


def _adapter_manifest() -> dict[str, Any]:
    return {
        "schemaVersion": "2.2",
        "builtInEditor": {
            "type": "dependency-free",
            "status": "ENABLED",
            "capabilities": ["drag-reorder", "keyboard-reorder-controls", "click-to-insert", "text-edit", "style-edit", "undo-redo", "responsive-preview", "json-html-export"],
            "accessibilityContract": {
                "dragAlternative": "Click to insert plus Move Up / Move Down controls",
                "keyboard": "Undo/redo shortcuts and standard button/input navigation",
                "requiredVerification": ["non-drag reorder", "visible focus", "selection after delete", "390px editor access"],
            },
        },
        "optionalAdapters": [
            {"id": "puck", "license": "MIT", "framework": "react", "strategy": "map Design IR nodes to user-owned React components", "status": "ADAPTER_CONTRACT_ONLY"},
            {"id": "grapesjs", "license": "BSD-3-Clause", "framework": "html-multi", "strategy": "map Design IR to GrapesJS Component Manager blocks", "status": "ADAPTER_CONTRACT_ONLY"},
            {"id": "craftjs", "license": "MIT", "framework": "react", "strategy": "map Design IR to project-defined Craft.js nodes", "status": "ADAPTER_CONTRACT_ONLY"},
        ],
        "policy": ["No third-party editor is silently downloaded", "Adapters require explicit dependency and license approval", "Built-in editor remains available offline"],
    }


def _postprocess_builder_html(page: str) -> str:
    """Harden the dependency-free builder shell after template generation.

    The builder is emitted as one self-contained document for offline use.  Keeping
    the hardening layer here makes the large HTML template easier to review while
    ensuring that editor-only affordances never leak into exported HTML.
    """
    css = """
/* WUQ builder hardening: keyboard-visible focus, labelled controls and mobile shell. */
.sr-only{position:absolute!important;width:1px!important;height:1px!important;padding:0!important;margin:-1px!important;overflow:hidden!important;clip:rect(0,0,0,0)!important;white-space:nowrap!important;border:0!important}
button:focus-visible,input:focus-visible,select:focus-visible,textarea:focus-visible,.node:focus-visible{outline:3px solid #7c8cff!important;outline-offset:2px}
.node[tabindex="0"]{cursor:pointer}
.brand h1{font-size:14px;margin:0}
@media(max-width:900px){
  body{overflow:auto}
  .top{height:56px;min-height:56px;overflow:hidden;padding:0 8px;gap:8px}
  .brand{min-width:0;flex:0 0 160px;overflow:hidden}
  .brand>div:last-child{min-width:0;overflow:hidden;white-space:nowrap}
  .tools{min-width:0;flex:1 1 auto;overflow-x:auto;overflow-y:hidden;flex-wrap:nowrap;padding-bottom:2px;scrollbar-width:thin}
  .layout{grid-template-columns:1fr!important;overflow:visible}
  .left{max-height:42vh;border-right:0;border-bottom:1px solid var(--line)}
  .left .panel-head{position:static}
  .center{min-height:52vh;padding:12px}
  .stage-wrap{min-width:390px}
  .right{top:56px;width:min(300px,100vw);max-width:100vw}
  .statusbar{left:12px;bottom:12px}
  .toast{left:12px;right:12px;max-width:none}
}
@media(max-width:560px){
  .brand{flex-basis:42px}
  .brand>div:last-child{display:none}
  .left{max-height:34vh}
}
"""
    page = page.replace("</style>", css + "</style>", 1)
    replacements = {
        '<select id="viewport">': '<select id="viewport" aria-label="预览宽度">',
        '<input id="paletteSearch" class="search" placeholder="搜索组件">': '<input id="paletteSearch" class="search" aria-label="搜索组件" placeholder="搜索组件">',
        '<button id="inspectorToggle">属性</button>': '<button id="inspectorToggle" aria-controls="right" aria-expanded="false">属性</button>',
        '<aside class="right" id="right">': '<aside class="right" id="right" aria-label="元素属性">',
        '<div class="statusbar" id="status">就绪</div>': '<div class="statusbar" id="status" role="status" aria-live="polite" aria-atomic="true">就绪</div>',
        '<div class="toast" id="toast"></div>': '<div class="toast" id="toast" role="status" aria-live="polite" aria-atomic="true"></div>',
        '<b>Design Intelligence Visual Builder</b>': '<h1>Design Intelligence Visual Builder</h1>',
    }
    for old, new in replacements.items():
        page = page.replace(old, new)

    # Append the hardening layer inside the same script block so the generated
    # document remains valid when hosts or validators extract its inline JS.
    patch = r"""
(function(){
  const wuqPersist=()=>{try{localStorage.setItem(storageKey,JSON.stringify(state))}catch(_){}};
  commit=function(label){history.push(clone(state));if(history.length>80)history.shift();future=[];$('status').textContent=label};
  const wuqOriginalRender=render;
  render=function(){wuqOriginalRender();wuqPersist()};

  const wuqStyleText=function(style){
    const aliases={direction:'flex-direction',justify:'justify-content',align:'align-items'};
    const parts=Object.entries(style||{}).filter(([k,v])=>v!==''&&v!=null&&k!=='layout').map(([k,v])=>`${aliases[k]||k.replace(/[A-Z]/g,m=>'-'+m.toLowerCase())}:${v}`);
    if(style?.layout==='split'&&!style?.gridTemplateColumns)parts.push('display:grid','grid-template-columns:1fr 1fr');
    return parts.join(';');
  };
  const wuqIsContainer=node=>!!node&&['page','frame','section','stack','card','list'].includes(node.type);
  const wuqEditorAttrs=(node,style)=>{
    const editor=window.__wuqExporting?'':` draggable="true" data-id="${esc(node.id)}"`;
    const interactive=['button','input','list-item'].includes(node.type);
    const focus=window.__wuqExporting||interactive?'':` tabindex="0" aria-label="${esc('选择 '+(node.name||node.type))}"`;
    return `${editor}${focus} style="${esc(style)}"`;
  };
  const wuqNodeLabel=node=>window.__wuqExporting?'':`<span class="node-label">${esc(node.type)} · ${esc(node.name)}</span>`;
  nodeHtml=function(node){
    const base=wuqStyleText(node.style),label=wuqNodeLabel(node),kids=(node.children||[]).map(nodeHtml).join('');
    const attrs=wuqEditorAttrs(node,base);
    if(node.type==='text')return `<div class="node" ${attrs}>${esc(node.content||'')}${label}</div>`;
    if(node.type==='button')return `<button type="button" class="node render-button" ${attrs}>${esc(node.content||'')}${label}</button>`;
    if(node.type==='input'){
      const name=esc(node.semantics?.label||node.name||'输入');
      return `<label class="node" ${attrs}><input class="render-input" aria-label="${name}" placeholder="${esc(node.content||'输入')}">${label}</label>`;
    }
    if(node.type==='badge')return `<span class="node" ${attrs}>${esc(node.content||'')}${label}</span>`;
    if(node.type==='divider')return `<div class="node" ${attrs}>${label}</div>`;
    if(node.type==='image')return `<div class="node" ${attrs} role="img" aria-label="${esc(node.semantics?.alt||node.name||'图片')}"><span style="display:grid;place-items:center;height:100%;color:var(--muted)">${esc(node.content||'')}</span>${label}</div>`;
    if(node.type==='list-item'){
      const style=wuqStyleText({...node.style,textAlign:'left',background:'transparent'});
      return `<button type="button" class="node" ${wuqEditorAttrs(node,style)}>${esc(node.content||'')}${label}</button>`;
    }
    return `<div class="node" ${attrs}>${label}${kids||'<div style="min-height:28px;color:var(--muted);font-size:11px">空容器：拖入组件</div>'}</div>`;
  };

  bindCanvas=function(){
    document.querySelectorAll('.node').forEach(el=>{
      const target=find(el.dataset.id)[0];
      if(el.dataset.id===selected)el.classList.add('selected');
      el.onclick=e=>{
        e.stopPropagation();
        if(['INPUT','TEXTAREA','SELECT'].includes(e.target.tagName)){selected=el.dataset.id;return}
        e.preventDefault();selected=el.dataset.id;render();
      };
      el.onkeydown=e=>{if((e.key==='Enter'||e.key===' ')&&e.target===el){e.preventDefault();selected=el.dataset.id;render()}};
      el.ondragstart=e=>{if(window.__wuqExporting)return;e.dataTransfer.setData('text/node-id',el.dataset.id);el.classList.add('dragging')};
      el.ondragend=()=>el.classList.remove('dragging');
      el.ondragover=e=>{if(!wuqIsContainer(target))return;e.preventDefault();el.classList.add('drop-target')};
      el.ondragleave=()=>el.classList.remove('drop-target');
      el.ondrop=e=>{
        e.preventDefault();e.stopPropagation();el.classList.remove('drop-target');
        if(!wuqIsContainer(target)){toast('只能将组件放入区块、卡片或列表容器');return}
        const id=e.dataTransfer.getData('text/node-id'),type=e.dataTransfer.getData('text/component-type');
        if(type){commit('添加组件');insertNode(el.dataset.id,defaultNode(type));render();return}
        if(id&&id!==el.dataset.id){const [moving]=find(id);if(moving){let child=moving;let cycle=false;walk(moving.children||[],n=>{if(n.id===target.id)cycle=true});if(cycle){toast('不能把父级放入自己的子级');return}commit('移动组件');removeNode(id);insertNode(el.dataset.id,moving);render()}}
      };
    });
    $('canvas').ondragover=e=>e.preventDefault();
    $('canvas').ondrop=e=>{e.preventDefault();const type=e.dataTransfer.getData('text/component-type');if(type){commit('添加根组件');insertNode(null,defaultNode(type));render()}};
  };

  const wuqExportHtml=function(){
    const old=window.__wuqExporting;window.__wuqExporting=true;
    const body=(state.roots||[]).map(nodeHtml).join('');window.__wuqExporting=old;
    const css=':root{--canvas-bg:#f7f8fb;--surface:#fff;--text:#17202a;--muted:#667085;--line:#dbe2ea;--soft:#eef3f9;--brand:#2563eb}*{box-sizing:border-box}body{margin:0;color:var(--text);font-family:Inter,"Segoe UI","PingFang SC",sans-serif}.node{position:relative;min-height:18px}.render-input{display:block;width:100%;min-height:40px}.sr-only{position:absolute!important;width:1px!important;height:1px!important;padding:0!important;margin:-1px!important;overflow:hidden!important;clip:rect(0,0,0,0)!important;white-space:nowrap!important;border:0!important}button,input{font:inherit}@media(max-width:720px){[style*="grid-template-columns"]{grid-template-columns:1fr!important}}';
    download('visual-builder-export.html',`<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>WUQ Experience Export</title><style>${css}</style></head><body>${body}</body></html>`,'text/html');
  };
  exportHtml=wuqExportHtml;$('exportHtml').onclick=wuqExportHtml;

  const inspector=$('inspector'),toggle=$('inspectorToggle'),right=$('right');
  toggle.addEventListener('click',()=>{toggle.setAttribute('aria-expanded',right.classList.contains('open')?'true':'false')});
  document.addEventListener('keydown',e=>{if(e.key==='Escape'&&right.classList.contains('open')){right.classList.remove('open');toggle.setAttribute('aria-expanded','false');toggle.focus()}});
  const wuqLabelFields=()=>{
    inspector.querySelectorAll('.field').forEach((field,index)=>{const label=field.querySelector('label'),control=field.querySelector('input,select,textarea');if(!label||!control)return;const id=control.id||`wuq-inspector-${index}-${(control.dataset.key||'field').replace(/[^a-z0-9_-]/gi,'-')}`;control.id=id;label.htmlFor=id});
    document.querySelectorAll('#treeHost button').forEach(btn=>{btn.setAttribute('role','treeitem');btn.setAttribute('aria-selected',btn.classList.contains('active')?'true':'false')});
    document.querySelectorAll('.candidate').forEach(btn=>btn.setAttribute('aria-pressed',btn.classList.contains('active')?'true':'false'));
  };
  if(window.MutationObserver)new MutationObserver(wuqLabelFields).observe(inspector,{childList:true,subtree:true});
  render();
  wuqLabelFields();
})();
"""
    return page.replace("</script></body></html>", f"\n{patch}</script></body></html>", 1)


def generate_visual_builder(
    experience_plan: Mapping[str, Any],
    output_dir: str | Path,
    *,
    design_ir: Mapping[str, Any] | None = None,
    candidates: Mapping[str, Any] | None = None,
    production_plan: Mapping[str, Any] | None = None,
    title: str | None = None,
) -> Path:
    out = Path(output_dir).expanduser().resolve(); out.mkdir(parents=True, exist_ok=True)
    ir = deepcopy(dict(design_ir)) if design_ir else _default_ir(experience_plan)
    payload = {
        "schemaVersion": "2.2", "title": title or "Web UI Quality Visual Builder",
        "experience": dict(experience_plan), "designIr": ir,
        "candidates": dict(candidates or {}), "production": dict(production_plan or {}),
        "adapters": _adapter_manifest(),
    }
    for name, value in (("builder-state.json", payload), ("design-ir.json", ir), ("editor-adapters.json", payload["adapters"])):
        (out / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    page = _html_page(payload)
    path = out / "index.html"; path.write_text(page, encoding="utf-8")
    return path


def _html_page(payload: Mapping[str, Any]) -> str:
    data = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    title = html.escape(str(payload.get("title") or "Visual Builder"))
    page = f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title><style>
:root{{--bg:#eef1f5;--panel:#fff;--text:#17202a;--muted:#667085;--line:#dbe2ea;--brand:#2563eb;--canvas:#f8fafc;--danger:#d92d20;font-family:Inter,"Segoe UI","PingFang SC",sans-serif;color-scheme:light}}*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);overflow:hidden}}button,input,select,textarea{{font:inherit}}button{{cursor:pointer}}.app{{height:100dvh;display:grid;grid-template-rows:56px 1fr}}.top{{display:flex;align-items:center;justify-content:space-between;padding:0 14px;background:#111827;color:#fff;border-bottom:1px solid #2b3545;gap:10px}}.brand{{display:flex;align-items:center;gap:10px;min-width:240px}}.logo{{display:grid;place-items:center;width:30px;height:30px;border-radius:9px;background:linear-gradient(135deg,#6d5dfc,#2dd4bf);font-weight:800}}.brand b{{font-size:14px}}.brand small{{display:block;color:#aab4c4}}.tools{{display:flex;align-items:center;gap:7px;flex-wrap:wrap}}.top button,.top select{{height:34px;border:1px solid #465268;border-radius:8px;background:#202a3a;color:#fff;padding:0 10px}}.top button:hover{{background:#2a3547}}.top .primary{{background:#356df3;border-color:#4f7df3}}.layout{{min-height:0;display:grid;grid-template-columns:248px minmax(0,1fr) 300px}}.left,.right{{background:var(--panel);overflow:auto}}.left{{border-right:1px solid var(--line)}}.right{{border-left:1px solid var(--line)}}.panel-head{{position:sticky;top:0;z-index:2;background:rgba(255,255,255,.95);backdrop-filter:blur(12px);padding:14px;border-bottom:1px solid var(--line)}}.panel-head b{{font-size:13px}}.panel-head p{{margin:4px 0 0;color:var(--muted);font-size:11px}}.search{{width:100%;height:36px;border:1px solid var(--line);border-radius:9px;padding:0 10px;margin-top:10px}}.palette{{display:grid;grid-template-columns:1fr 1fr;gap:8px;padding:12px}}.palette button{{min-height:58px;border:1px solid var(--line);border-radius:10px;background:#fff;text-align:left;padding:9px;color:var(--text)}}.palette button:hover{{border-color:#9bb7ff;background:#f5f8ff}}.palette span{{display:block;font-weight:700;font-size:12px}}.palette small{{color:var(--muted);font-size:10px}}.library-section{{border-top:1px solid var(--line);padding:12px}}.library-section h3{{margin:0 0 9px;font-size:12px}}.candidate{{display:block;width:100%;padding:9px;border:1px solid var(--line);background:#fff;border-radius:9px;margin-bottom:7px;text-align:left}}.candidate.active{{border-color:var(--brand);box-shadow:0 0 0 2px #dbe7ff}}.center{{min-width:0;overflow:auto;background:radial-gradient(circle at 1px 1px,#cdd5df 1px,transparent 0);background-size:20px 20px;padding:30px}}.stage-wrap{{min-width:max-content;display:grid;justify-content:center}}.stage{{width:1180px;min-height:720px;background:var(--canvas);box-shadow:0 24px 80px rgba(20,30,50,.18);border-radius:12px;overflow:auto;transition:width .2s}}.stage.dark{{--canvas-bg:#111827;--surface:#1f2937;--text:#f8fafc;--muted:#a7b0bf;--line:#374151;--soft:#2a3648;--brand:#7c8cff;color-scheme:dark}}.canvas{{min-height:100%;padding:1px;color:var(--text,#17202a);background:var(--canvas-bg,#f7f8fb)}}.node{{position:relative;min-height:18px;outline:1px solid transparent}}.node:hover{{outline-color:#9bb7ff}}.node.selected{{outline:2px solid var(--brand)!important;outline-offset:2px}}.node.dragging{{opacity:.4}}.drop-target{{box-shadow:inset 0 0 0 2px #2dd4bf}}.node-label{{display:none;position:absolute;left:0;top:-20px;background:#2563eb;color:#fff;padding:3px 6px;border-radius:5px;font-size:9px;z-index:20;white-space:nowrap}}.node.selected>.node-label{{display:block}}.render-text{{white-space:pre-wrap}}.render-input{{display:block;width:100%;min-height:40px}}.render-button{{border:0;font-weight:700}}.render-list{{display:grid;gap:6px}}.inspector{{padding:12px}}.empty{{padding:28px 10px;text-align:center;color:var(--muted);font-size:12px}}.field{{display:grid;gap:5px;margin-bottom:11px}}.field label{{font-size:11px;color:var(--muted)}}.field input,.field select,.field textarea{{width:100%;border:1px solid var(--line);border-radius:8px;padding:8px;background:#fff;color:var(--text)}}.field textarea{{min-height:78px;resize:vertical}}.field-row{{display:grid;grid-template-columns:1fr 1fr;gap:8px}}.actions{{display:grid;grid-template-columns:1fr 1fr;gap:7px;margin:12px 0}}.actions button{{height:36px;border:1px solid var(--line);background:#fff;border-radius:8px}}.actions .danger{{color:var(--danger)}}.tree{{font-size:11px;border-top:1px solid var(--line);padding-top:12px}}.tree button{{display:block;width:100%;border:0;background:transparent;text-align:left;padding:5px;border-radius:6px;color:inherit}}.tree button.active{{background:#eaf0ff;color:#1d4ed8}}.statusbar{{position:fixed;left:260px;bottom:12px;background:#111827;color:#fff;border-radius:8px;padding:7px 10px;font-size:10px;box-shadow:0 8px 24px rgba(0,0,0,.22);pointer-events:none}}.toast{{position:fixed;right:316px;bottom:18px;background:#111827;color:#fff;padding:10px 13px;border-radius:9px;opacity:0;transform:translateY(8px);transition:.2s;z-index:50}}.toast.show{{opacity:1;transform:none}}@media(max-width:900px){{.layout{{grid-template-columns:210px minmax(0,1fr)}}.right{{position:fixed;right:0;top:56px;bottom:0;width:300px;transform:translateX(100%);transition:.2s;z-index:10;box-shadow:-20px 0 50px rgba(0,0,0,.15)}}.right.open{{transform:none}}.brand small{{display:none}}}}@media(prefers-reduced-motion:reduce){{*{{scroll-behavior:auto!important;transition:none!important;animation:none!important}}}}
</style></head><body><div class="app"><header class="top"><div class="brand"><span class="logo">W</span><div><b>Design Intelligence Visual Builder</b><small>候选设计可编辑；不直接修改项目</small></div></div><div class="tools"><button id="undo" title="撤销 Ctrl+Z">撤销</button><button id="redo" title="重做 Ctrl+Shift+Z">重做</button><select id="viewport"><option value="1180">桌面 1180</option><option value="900">小桌面 900</option><option value="768">平板 768</option><option value="390">手机 390</option></select><button id="theme">深色</button><button id="grid">网格</button><button id="inspectorToggle">属性</button><button id="exportJson">导出 JSON</button><button id="exportHtml" class="primary">导出 HTML</button></div></header><div class="layout"><aside class="left"><div class="panel-head"><b>组件与设计候选</b><p>拖入或点击添加，组件保持独立状态</p><input id="paletteSearch" class="search" placeholder="搜索组件"></div><div class="palette" id="palette"></div><div class="library-section"><h3>审美候选</h3><div id="candidates"></div></div><div class="library-section"><h3>生产映射</h3><div id="productionSummary" class="empty">尚未生成生产映射</div></div></aside><main class="center" id="center"><div class="stage-wrap"><div class="stage" id="stage"><div class="canvas" id="canvas"></div></div></div></main><aside class="right" id="right"><div class="panel-head"><b>元素属性</b><p>修改会进入本地撤销栈和候选 Design IR</p></div><div class="inspector" id="inspector"><div class="empty">选择一个元素开始编辑</div></div></aside></div></div><div class="statusbar" id="status">就绪</div><div class="toast" id="toast"></div><script>
const BOOT={data};const TYPES=[['section','区块','布局容器'],['stack','堆栈','纵向或横向组织'],['card','卡片','信息表面'],['text','文字','标题或说明'],['button','按钮','主次操作'],['input','输入框','表单输入'],['badge','标签','状态信息'],['divider','分割线','内容分组'],['list-item','列表项','可选择对象'],['image','图片','带替代文本的媒体']];
const $=id=>document.getElementById(id),clone=v=>JSON.parse(JSON.stringify(v)),uid=()=>`node-${{Date.now().toString(36)}}-${{Math.random().toString(36).slice(2,7)}}`,esc=v=>String(v??'').replace(/[&<>"]/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}}[c]));let state=clone(BOOT.designIr),selected=null,history=[],future=[],grid=true;const storageKey='wuq-builder-'+(BOOT.experience.experienceDigest||'local');
function toast(msg){{const t=$('toast');t.textContent=msg;t.classList.add('show');setTimeout(()=>t.classList.remove('show'),1600)}}function commit(label){{history.push(clone(state));if(history.length>80)history.shift();future=[];$('status').textContent=label;localStorage.setItem(storageKey,JSON.stringify(state));}}function undo(){{if(!history.length)return;future.push(clone(state));state=history.pop();selected=null;render();toast('已撤销')}}function redo(){{if(!future.length)return;history.push(clone(state));state=future.pop();selected=null;render();toast('已重做')}}
function walk(nodes,fn,parent=null){{for(const node of nodes||[]){{if(fn(node,parent)===false)return false;if(walk(node.children||[],fn,node)===false)return false}}}}function find(id){{let found=null,parent=null;walk(state.roots,(n,p)=>{{if(n.id===id){{found=n;parent=p;return false}}}});return [found,parent]}}function childrenOf(parent){{return parent?parent.children:state.roots}}function removeNode(id){{const [node,parent]=find(id);if(!node)return;const arr=childrenOf(parent),i=arr.findIndex(x=>x.id===id);if(i>=0)arr.splice(i,1)}}function insertNode(parentId,node,index=null){{const [parent]=parentId?find(parentId):[null];const arr=childrenOf(parent);if(index==null)arr.push(node);else arr.splice(index,0,node)}}
function defaultNode(type){{const base={{id:uid(),type,name:type,style:{{}},semantics:{{}},bindings:{{}},children:[]}};if(type==='text')Object.assign(base,{{name:'Text',content:'可编辑文字',style:{{fontSize:'16px',fontWeight:650}}}});if(type==='button')Object.assign(base,{{name:'Button',content:'操作按钮',style:{{padding:'10px 14px',background:'var(--brand)',color:'#fff',borderRadius:'10px'}},semantics:{{role:'button'}}}});if(type==='input')Object.assign(base,{{name:'Input',content:'输入内容',style:{{padding:'10px 12px',border:'1px solid var(--line)',borderRadius:'10px'}},semantics:{{role:'textbox',label:'输入内容'}}}});if(type==='badge')Object.assign(base,{{name:'Badge',content:'状态',style:{{padding:'5px 8px',background:'var(--soft)',borderRadius:'999px',fontSize:'12px'}}}});if(type==='card')Object.assign(base,{{name:'Card',style:{{padding:'16px',background:'var(--surface)',border:'1px solid var(--line)',borderRadius:'16px'}},children:[defaultNode('text')]}});if(type==='section'||type==='stack')Object.assign(base,{{name:type==='section'?'Section':'Stack',style:{{display:'flex',direction:'column',gap:'12px',padding:'16px'}},children:[]}});if(type==='divider')Object.assign(base,{{name:'Divider',style:{{height:'1px',background:'var(--line)'}}}});if(type==='list-item')Object.assign(base,{{name:'List item',content:'列表对象 · 状态',style:{{padding:'12px',border:'1px solid var(--line)',borderRadius:'10px'}}}});if(type==='image')Object.assign(base,{{name:'Image',content:'图片区域',style:{{height:'180px',background:'linear-gradient(135deg,#dbeafe,#ddd6fe)',borderRadius:'14px'}},semantics:{{alt:'描述图片内容'}}}});return base}}
function styleText(style){{return Object.entries(style||{{}}).filter(([k,v])=>v!==''&&v!=null&&!['layout','gridTemplateColumns'].includes(k)).map(([k,v])=>`${{k.replace(/[A-Z]/g,m=>'-'+m.toLowerCase())}}:${{v}}`).join(';')}}function nodeHtml(node){{const s=styleText(node.style),attrs=`draggable="true" data-id="${{esc(node.id)}}" style="${{esc(s)}}"`;const label=`<span class="node-label">${{esc(node.type)}} · ${{esc(node.name)}}</span>`;const kids=(node.children||[]).map(nodeHtml).join('');if(node.type==='text')return `<div class="node" ${{attrs}}><span class="render-text">${{esc(node.content)}}</span>${{label}}</div>`;if(node.type==='button')return `<button class="node render-button" ${{attrs}}>${{esc(node.content)}}${{label}}</button>`;if(node.type==='input')return `<label class="node" ${{attrs}}><span class="sr-only">${{esc(node.semantics?.label||node.name)}}</span><input class="render-input" placeholder="${{esc(node.content||'输入')}}">${{label}}</label>`;if(node.type==='badge')return `<span class="node" ${{attrs}}>${{esc(node.content)}}${{label}}</span>`;if(node.type==='divider')return `<div class="node" ${{attrs}}>${{label}}</div>`;if(node.type==='image')return `<div class="node" ${{attrs}} role="img" aria-label="${{esc(node.semantics?.alt||node.name)}}"><span style="display:grid;place-items:center;height:100%;color:var(--muted)">${{esc(node.content)}}</span>${{label}}</div>`;if(node.type==='list-item')return `<button class="node" ${{attrs}} style="${{esc(s)}};text-align:left;background:transparent">${{esc(node.content)}}${{label}}</button>`;const extra=node.style?.layout==='split'||node.style?.gridTemplateColumns?`grid-template-columns:${{node.style.gridTemplateColumns||'1fr 1fr'}};display:grid`:'';return `<div class="node" ${{attrs}} style="${{esc(s)}};${{extra}}">${{label}}${{kids||'<div style="min-height:28px;color:var(--muted);font-size:11px">空容器：拖入组件</div>'}}</div>`}}
function render(){{$('canvas').innerHTML=(state.roots||[]).map(nodeHtml).join('');bindCanvas();renderTree();renderInspector();$('status').textContent=`${{countNodes()}} 个元素 · ${{history.length}} 次可撤销`;}}function countNodes(){{let n=0;walk(state.roots,()=>n++);return n}}function bindCanvas(){{document.querySelectorAll('.node').forEach(el=>{{if(el.dataset.id===selected)el.classList.add('selected');el.onclick=e=>{{e.preventDefault();e.stopPropagation();selected=el.dataset.id;render()}};el.ondragstart=e=>{{e.dataTransfer.setData('text/node-id',el.dataset.id);el.classList.add('dragging')}};el.ondragend=()=>el.classList.remove('dragging');el.ondragover=e=>{{e.preventDefault();el.classList.add('drop-target')}};el.ondragleave=()=>el.classList.remove('drop-target');el.ondrop=e=>{{e.preventDefault();e.stopPropagation();el.classList.remove('drop-target');const id=e.dataTransfer.getData('text/node-id'),type=e.dataTransfer.getData('text/component-type');commit(type?'添加组件':'移动组件');if(type)insertNode(el.dataset.id,defaultNode(type));else if(id&&id!==el.dataset.id){{const [moving]=find(id);if(moving){{removeNode(id);insertNode(el.dataset.id,moving)}}}}render()}}}});$('canvas').ondragover=e=>e.preventDefault();$('canvas').ondrop=e=>{{e.preventDefault();const type=e.dataTransfer.getData('text/component-type');if(type){{commit('添加根组件');insertNode(null,defaultNode(type));render()}}}}}}
function renderPalette(){{const q=$('paletteSearch').value.toLowerCase();$('palette').innerHTML=TYPES.filter(x=>x.join(' ').toLowerCase().includes(q)).map(([type,name,desc])=>`<button draggable="true" data-type="${{type}}"><span>${{name}}</span><small>${{desc}}</small></button>`).join('');$('palette').querySelectorAll('button').forEach(btn=>{{btn.ondragstart=e=>e.dataTransfer.setData('text/component-type',btn.dataset.type);btn.onclick=()=>{{commit('添加组件');const parent=selected&&['section','stack','card','page','frame'].includes(find(selected)[0]?.type)?selected:null;insertNode(parent,defaultNode(btn.dataset.type));render()}}}})}}
function renderCandidates(){{const items=BOOT.candidates?.candidates||[];$('candidates').innerHTML=items.length?items.map((c,i)=>`<button class="candidate ${{i===0?'active':''}}" data-id="${{c.id}}"><b>${{esc(c.name)}}</b><small>${{esc(c.designDNA?.composition||'')}}</small></button>`).join(''):'<div class="empty">未生成审美候选</div>';$('candidates').querySelectorAll('button').forEach(btn=>btn.onclick=()=>{{document.querySelectorAll('.candidate').forEach(x=>x.classList.remove('active'));btn.classList.add('active');const c=items.find(x=>x.id===btn.dataset.id);applyCandidate(c);toast('已应用候选 '+c.name)}})}}function applyCandidate(c){{if(!c)return;commit('应用审美候选');const dna=c.designDNA||{{}};const root=state.roots?.[0];if(root){{root.style=root.style||{{}};root.style.variants={{candidate:c.id,composition:dna.composition,surface:dna.surface,motion:dna.motion,density:dna.density}}}};const hue={{'spatial-clarity':'#2563eb','vibrant-tech':'#0ea5e9','kinetic-operations':'#4f46e5','tactile-field':'#15803d','warm-service':'#c2410c','luminous-ai':'#7c3aed','monochrome-focus':'#111827'}}[c.archetype]||'#2563eb';$('stage').style.setProperty('--brand',hue);render()}}
function renderProduction(){{const p=BOOT.production,m=p?.componentMappings||[];$('productionSummary').className='';$('productionSummary').innerHTML=m.length?`<p style="font-size:11px;color:var(--muted)">框架：<b>${{esc(p.targetFramework)}}</b> · ${{m.length}} 个角色</p>${{m.slice(0,6).map(x=>`<div style="font-size:10px;margin:5px 0"><b>${{esc(x.role)}}</b> → ${{esc(x.localComponent?.name||x.recommendedSource?.name||'生成原生组件')}}</div>`).join('')}}`:'<div class="empty">尚未生成生产映射</div>'}}
function renderTree(){{const tree=[];function add(nodes,d=0){{for(const n of nodes||[]){{tree.push(`<button class="${{n.id===selected?'active':''}}" data-id="${{n.id}}" style="padding-left:${{6+d*12}}px">${{esc(n.name)}} <small>${{esc(n.type)}}</small></button>`);add(n.children,d+1)}}}}add(state.roots);const host=$('treeHost');if(host)host.innerHTML=tree.join('');document.querySelectorAll('#treeHost button').forEach(b=>b.onclick=()=>{{selected=b.dataset.id;render()}})}}
function field(label,key,value,type='text',options=[]){{if(type==='select')return `<div class="field"><label>${{label}}</label><select data-key="${{key}}">${{options.map(x=>`<option ${{String(x)===String(value)?'selected':''}}>${{x}}</option>`).join('')}}</select></div>`;return `<div class="field"><label>${{label}}</label>${{type==='textarea'?`<textarea data-key="${{key}}">${{esc(value||'')}}</textarea>`:`<input data-key="${{key}}" type="${{type}}" value="${{esc(value||'')}}">`}}</div>`}}
function renderInspector(){{const host=$('inspector'),[node,parent]=selected?find(selected):[null,null];if(!node){{host.innerHTML='<div class="empty">选择一个元素开始编辑</div><div class="tree" id="treeHost"></div>';renderTree();return}}const st=node.style||{{}};host.innerHTML=`${{field('名称','name',node.name)}}${{['text','button','badge','list-item','image','input'].includes(node.type)?field('内容','content',node.content||'','textarea'):''}}<div class="field-row">${{field('布局方向','style.direction',st.direction||'column','select',['column','row'])}}${{field('间距','style.gap',st.gap||'')}}</div><div class="field-row">${{field('内边距','style.padding',st.padding||'')}}${{field('圆角','style.borderRadius',st.borderRadius||'')}}</div><div class="field-row">${{field('背景','style.background',st.background||'')}}${{field('文字色','style.color',st.color||'')}}</div><div class="field-row">${{field('宽度','style.width',st.width||'')}}${{field('高度','style.height',st.height||'')}}</div>${{field('对齐','style.justify',st.justify||'','select',['','flex-start','center','space-between','flex-end'])}}<div class="actions"><button id="duplicate">复制</button><button id="moveUp">上移</button><button id="moveDown">下移</button><button id="delete" class="danger">删除</button></div><div class="tree" id="treeHost"></div>`;host.querySelectorAll('[data-key]').forEach(el=>el.onchange=()=>{{commit('修改属性');setValue(node,el.dataset.key,el.value);render()}});$('duplicate').onclick=()=>{{commit('复制元素');const copy=clone(node);function ids(n){{n.id=uid();(n.children||[]).forEach(ids)}}ids(copy);const arr=childrenOf(parent),i=arr.findIndex(x=>x.id===node.id);arr.splice(i+1,0,copy);selected=copy.id;render()}};$('delete').onclick=()=>{{commit('删除元素');removeNode(node.id);selected=null;render()}};$('moveUp').onclick=()=>move(-1);$('moveDown').onclick=()=>move(1);renderTree()}}function setValue(obj,path,value){{const keys=path.split('.');let cur=obj;for(let i=0;i<keys.length-1;i++)cur=cur[keys[i]]||(cur[keys[i]]={{}});cur[keys.at(-1)]=value}}function move(delta){{const [node,parent]=find(selected),arr=childrenOf(parent),i=arr.findIndex(x=>x.id===selected),n=i+delta;if(n<0||n>=arr.length)return;commit('移动元素');[arr[i],arr[n]]=[arr[n],arr[i]];render()}}
function cleanForExport(){{const out=clone(state);out.metadata={{...(out.metadata||{{}}),editedAt:new Date().toISOString(),editor:'WUQ Visual Builder 2.2.1',productionAuthority:false}};return out}}function download(name,text,type='application/json'){{const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([text],{{type}}));a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),500)}}function exportHtml(){{const body=(state.roots||[]).map(nodeHtml).join('');const css=`:root{{--canvas-bg:#f7f8fb;--surface:#fff;--text:#17202a;--muted:#667085;--line:#dbe2ea;--soft:#eef3f9;--brand:#2563eb}}*{{box-sizing:border-box}}body{{margin:0;color:var(--text);font-family:Inter,"Segoe UI","PingFang SC",sans-serif}}.node{{position:relative}}button,input{{font:inherit}}@media(max-width:720px){{[style*="grid-template-columns"]{{grid-template-columns:1fr!important}}}}`;download('visual-builder-export.html',`<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>${{css}}</style></head><body>${{body}}</body></html>`,'text/html')}}
$('undo').onclick=undo;$('redo').onclick=redo;$('viewport').onchange=e=>$('stage').style.width=e.target.value+'px';$('theme').onclick=()=>{{$('stage').classList.toggle('dark');$('theme').textContent=$('stage').classList.contains('dark')?'浅色':'深色'}};$('grid').onclick=()=>{{grid=!grid;$('center').style.background=grid?'radial-gradient(circle at 1px 1px,#cdd5df 1px,transparent 0)':'#e7ebf0';$('center').style.backgroundSize='20px 20px'}};$('inspectorToggle').onclick=()=>$('right').classList.toggle('open');$('exportJson').onclick=()=>download('design-ir-edited.json',JSON.stringify(cleanForExport(),null,2));$('exportHtml').onclick=exportHtml;$('paletteSearch').oninput=renderPalette;window.onkeydown=e=>{{if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='z'){{e.preventDefault();e.shiftKey?redo():undo()}}if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='s'){{e.preventDefault();$('exportJson').click()}}}};try{{const saved=localStorage.getItem(storageKey);if(saved)state=JSON.parse(saved)}}catch{{}}renderPalette();renderCandidates();renderProduction();render();
 </script></body></html>'''
    return _postprocess_builder_html(page)
