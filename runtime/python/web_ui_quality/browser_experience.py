"""Browser-measured geometry for the Experience Modernization Engine."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .evidence_redaction import redact_structure


_SEMANTIC_DOM_JS = r"""
() => {
  const visible = el => {
    const style=getComputedStyle(el), rect=el.getBoundingClientRect();
    return style.display!=='none'&&style.visibility!=='hidden'&&Number(style.opacity||1)>0&&rect.width>0&&rect.height>0;
  };
  const bounds = el => {
    const r=el.getBoundingClientRect();
    return {x:+r.x.toFixed(1),y:+r.y.toFixed(1),width:+r.width.toFixed(1),height:+r.height.toFixed(1)};
  };
  const name = el => {
    const labelled=el.getAttribute('aria-labelledby');
    if(labelled){
      const value=labelled.split(/\s+/).map(id=>document.getElementById(id)?.textContent||'').join(' ').trim();
      if(value)return value.slice(0,160);
    }
    return (el.getAttribute('aria-label')||el.getAttribute('title')||el.textContent||'').trim().replace(/\s+/g,' ').slice(0,160);
  };
  const selector = el => {
    if(el.id)return '#'+CSS.escape(el.id);
    const test=el.getAttribute('data-testid'); if(test)return '[data-testid="'+CSS.escape(test)+'"]';
    const action=el.getAttribute('data-action'); if(action)return '[data-action="'+CSS.escape(action)+'"]';
    return el.tagName.toLowerCase();
  };
  const states = el => {
    const result={};
    for(const key of ['aria-current','aria-expanded','aria-pressed','aria-selected','aria-checked','aria-invalid','aria-busy','aria-live']){
      if(el.hasAttribute(key))result[key]=el.getAttribute(key);
    }
    if('checked' in el)result.checked=!!el.checked;
    if(el.tagName==='SELECT')result.selectedIndex=el.selectedIndex;
    if(el.matches(':disabled'))result.disabled=true;
    return result;
  };
  const controls=[...document.querySelectorAll('button,a[href],input,select,textarea,[role=button],[role=link],[role=checkbox],[role=combobox],[tabindex]')]
    .filter(visible).slice(0,300).map(el=>({
      selector:selector(el),role:el.getAttribute('role')||el.tagName.toLowerCase(),name:name(el),
      bounds:bounds(el),states:states(el)
    }));
  const headings=[...document.querySelectorAll('h1,h2,h3,h4,[role=heading]')].filter(visible).slice(0,120)
    .map(el=>({selector:selector(el),level:Number(el.getAttribute('aria-level'))||Number(el.tagName.slice(1))||null,text:name(el),bounds:bounds(el)}));
  const landmarks=[...document.querySelectorAll('header,nav,main,aside,footer,[role=banner],[role=navigation],[role=main],[role=complementary],[role=contentinfo]')]
    .filter(visible).slice(0,80).map(el=>({selector:selector(el),role:el.getAttribute('role')||el.tagName.toLowerCase(),name:name(el),bounds:bounds(el)}));
  const dialogs=[...document.querySelectorAll('dialog,[role=dialog],[aria-modal=true]')].filter(visible).slice(0,20)
    .map(el=>({selector:selector(el),name:name(el),states:states(el),bounds:bounds(el)}));
  const liveRegions=[...document.querySelectorAll('[aria-live],[role=status],[role=alert]')].filter(visible).slice(0,40)
    .map(el=>({selector:selector(el),role:el.getAttribute('role'),name:name(el),states:states(el)}));
  const active=document.activeElement;
  return {
    schemaVersion:'3.1',title:document.title,url:location.href.split('?')[0],lang:document.documentElement.lang||null,
    viewport:{width:innerWidth,height:innerHeight,clientWidth:document.documentElement.clientWidth,scrollWidth:document.documentElement.scrollWidth},
    pageState:{htmlDataset:{...document.documentElement.dataset},bodyDataset:{...document.body.dataset}},
    landmarks,headings,controls,dialogs,liveRegions,
    activeElement:active&&active!==document.body?{selector:selector(active),role:active.getAttribute('role')||active.tagName.toLowerCase(),name:name(active)}:null,
    evidenceTier:'browser-measured',
    claimBoundary:'Semantic DOM summary omits input values, raw HTML, cookies, and storage.'
  };
}
"""

_EXPERIENCE_GEOMETRY_JS = r"""
(viewportId) => {
  const visible = el => {
    const s=getComputedStyle(el), r=el.getBoundingClientRect();
    return s.display!=='none'&&s.visibility!=='hidden'&&Number(s.opacity||1)>0&&r.width>0&&r.height>0;
  };
  const rect = el => {
    const r=el.getBoundingClientRect();
    return {x:+r.x.toFixed(1),y:+r.y.toFixed(1),width:+r.width.toFixed(1),height:+r.height.toFixed(1),right:+r.right.toFixed(1),bottom:+r.bottom.toFixed(1)};
  };
  const selector = el => {
    if(el.id)return '#'+CSS.escape(el.id);
    const test=el.getAttribute('data-testid'); if(test)return '[data-testid="'+CSS.escape(test)+'"]';
    const role=el.getAttribute('role'); const label=el.getAttribute('aria-label')||el.textContent?.trim().slice(0,30);
    return el.tagName.toLowerCase()+(role?'[role='+role+']':'')+(label?':'+label:'');
  };
  const effectiveBackground=el=>{let cur=el;while(cur){const value=getComputedStyle(cur).backgroundColor;if(value&&value!=='transparent'&&!/^rgba\(0,\s*0,\s*0,\s*0\)$/.test(value))return value;cur=cur.parentElement;}return 'rgb(255, 255, 255)';};
  const isPrimary=el=>el.matches('.primary,[data-variant=primary],button[type=submit],[aria-current=page]');
  const finite=raw=>{const value=Number(raw);return Number.isFinite(value)?+value.toFixed(2):null;};
  const viewportWidth=Math.round((window.visualViewport&&window.visualViewport.width)||document.documentElement?.clientWidth||window.innerWidth);
  const viewportHeight=Math.round((window.visualViewport&&window.visualViewport.height)||document.documentElement?.clientHeight||window.innerHeight);
  const visualItem=el=>{const s=getComputedStyle(el);return {selector:selector(el),role:el.getAttribute('role')||el.tagName.toLowerCase(),text:(el.getAttribute('aria-label')||el.textContent||'').trim().slice(0,120),fontSizePx:finite(parseFloat(s.fontSize)),fontWeight:s.fontWeight,lineHeightPx:finite(parseFloat(s.lineHeight)),color:s.color,backgroundColor:effectiveBackground(el),bounds:rect(el),visible:true,isPrimary:isPrimary(el),isCta:el.matches('button,a[href],[role=button]')};};
  const elements=[...document.querySelectorAll('body *')].filter(visible).slice(0,2500);
  const interactive=[...document.querySelectorAll('button,a[href],input,select,textarea,[role=button],[tabindex]')].filter(visible);
  const layouts=elements.map(el=>({el,s:getComputedStyle(el)})).filter(x=>['flex','inline-flex','grid','inline-grid'].includes(x.s.display));
  const layoutSystems=layouts.slice(0,120).map(x=>({selector:selector(x.el),display:x.s.display,flexWrap:x.s.flexWrap,gridTemplateColumns:x.s.gridTemplateColumns,gap:x.s.gap,rect:rect(x.el)}));
  const targets=interactive.map(el=>({selector:selector(el),role:el.getAttribute('role')||el.tagName.toLowerCase(),text:(el.getAttribute('aria-label')||el.textContent||'').trim().slice(0,100),clipped:el.scrollWidth>el.clientWidth+1||el.scrollHeight>el.clientHeight+1,...rect(el)}));
  const minimumTargetPx=targets.length?Math.min(...targets.map(x=>Math.min(x.width,x.height))):null;
  let minimumGapPx=null; const buttonGroups=[];
  for(const x of layouts.slice(0,120)){
    const children=[...x.el.children].filter(el=>visible(el)&&el.matches('button,a[href],input,select,[role=button]'));
    if(children.length<2)continue;
    const boxes=children.map(rect).sort((a,b)=>a.x-b.x||a.y-b.y); const gaps=[];
    for(let i=1;i<boxes.length;i++){
      const horizontal=Math.max(0,boxes[i].x-boxes[i-1].right);
      const vertical=Math.max(0,boxes[i].y-boxes[i-1].bottom);
      const gap=horizontal||vertical; if(Number.isFinite(gap))gaps.push(gap);
    }
    if(gaps.length){
      const local=Math.min(...gaps); minimumGapPx=minimumGapPx===null?local:Math.min(minimumGapPx,local);
      buttonGroups.push({selector:selector(x.el),count:children.length,minimumGapPx:+local.toFixed(1),rect:rect(x.el),wrap:x.s.flexWrap});
    }
  }
  const tables=[...document.querySelectorAll('table,[role=grid],[role=table]')].filter(visible).map(el=>{
    const r=rect(el), parent=el.parentElement, ps=parent?getComputedStyle(parent):null;
    return {selector:selector(el),rect:r,scrollWidth:el.scrollWidth,clientWidth:el.clientWidth,columnCount:el.querySelectorAll('tr:first-child th,tr:first-child td').length,localScroll:!!(ps&&['auto','scroll'].includes(ps.overflowX)),viewportOverflow:r.right>viewportWidth+1};
  });
  const dialogs=[...document.querySelectorAll('dialog,[role=dialog],[aria-modal=true],.modal,.drawer,.sheet')].filter(visible).map(el=>{
    const r=rect(el); return {selector:selector(el),rect:r,oversized:r.width>viewportWidth-16||r.height>viewportHeight-16,offscreen:r.x<0||r.y<0||r.right>viewportWidth||r.bottom>viewportHeight};
  });
  const navigation=[...document.querySelectorAll('nav,[role=navigation],header,.sidebar,.sidenav')].filter(visible).map(el=>({selector:selector(el),rect:rect(el),scrollWidth:el.scrollWidth,clientWidth:el.clientWidth,overflow:el.scrollWidth>el.clientWidth+1,expanded:el.getAttribute('aria-expanded')}));
  const fixed=[...document.querySelectorAll('body *')].filter(el=>visible(el)&&['fixed','sticky'].includes(getComputedStyle(el).position));
  const fixedOcclusions=[];
  for(const overlay of fixed.slice(0,40)){
    const a=overlay.getBoundingClientRect();
    for(const target of interactive.slice(0,200)){
      if(overlay===target||overlay.contains(target)||target.contains(overlay))continue;
      const b=target.getBoundingClientRect(); const iw=Math.max(0,Math.min(a.right,b.right)-Math.max(a.left,b.left)); const ih=Math.max(0,Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top));
      if(iw*ih>Math.min(a.width*a.height,b.width*b.height)*.18){fixedOcclusions.push({overlay:selector(overlay),target:selector(target),intersection:+(iw*ih).toFixed(1)});if(fixedOcclusions.length>=30)break;}
    }
    if(fixedOcclusions.length>=30)break;
  }
  const overlapCandidates=[...document.querySelectorAll('main>*,section,article,.card,[role=dialog]')].filter(visible).slice(0,120);
  const overlaps=[];
  for(let i=0;i<overlapCandidates.length;i++)for(let j=i+1;j<overlapCandidates.length;j++){
    const a=overlapCandidates[i],b=overlapCandidates[j]; if(a.contains(b)||b.contains(a))continue;
    const ra=a.getBoundingClientRect(),rb=b.getBoundingClientRect(); const iw=Math.max(0,Math.min(ra.right,rb.right)-Math.max(ra.left,rb.left)); const ih=Math.max(0,Math.min(ra.bottom,rb.bottom)-Math.max(ra.top,rb.top));
    const area=iw*ih,base=Math.min(ra.width*ra.height,rb.width*rb.height);
    if(base>0&&area/base>.18){overlaps.push({a:selector(a),b:selector(b),ratio:+(area/base).toFixed(3)});if(overlaps.length>=30)break;}
  }
  const main=document.querySelector('main,[role=main]')||document.body, mr=main.getBoundingClientRect();
  const structuralContainer=el=>['div','section','article','form','fieldset'].includes(el.tagName.toLowerCase())&&!el.matches('.page-title,.toolbar,[role=region],[role=group]');
  const directAnchors=[...main.children].filter(visible).filter(el=>!structuralContainer(el));
  const nestedAnchors=[...main.querySelectorAll('h1,h2,.page-title,.toolbar')].filter(visible);
  const alignEls=[...new Set([...directAnchors,...nestedAnchors])].slice(0,80);
  const lefts=alignEls.map(el=>el.getBoundingClientRect().left).filter(Number.isFinite);
  const median=lefts.length?[...lefts].sort((a,b)=>a-b)[Math.floor(lefts.length/2)]:0;
  const deviations=lefts.map(x=>Math.abs(x-median)); const alignmentDeviationPx=lefts.length>1?deviations.reduce((a,b)=>a+b,0)/deviations.length:null;
  const primaryActions=[...document.querySelectorAll('.primary,[data-variant=primary],button[type=submit]')].filter(visible);
  const visualElements=[...document.querySelectorAll('h1,h2,h3,p,label,button,a[href],[role=button]')].filter(visible).slice(0,240).map(visualItem);
  const headings=visualElements.filter(item=>['h1','h2','h3','heading'].includes(item.role)).map(item=>({selector:item.selector,text:item.text,fontSize:item.fontSizePx,fontWeight:item.fontWeight,rect:item.bounds}));
  const bodyFont=finite(parseFloat(getComputedStyle(document.body).fontSize||'16'));
  return {
    id:viewportId||String(viewportWidth)+'x'+String(viewportHeight),
    width:viewportWidth,height:viewportHeight,innerWidth,innerHeight,clientWidth:document.documentElement.clientWidth,clientHeight:document.documentElement.clientHeight,scrollWidth:document.documentElement.scrollWidth,
    contentWidth:+mr.width.toFixed(1),contentOccupancy:+(mr.width/Math.max(1,viewportWidth)).toFixed(3),
    minimumGapPx:minimumGapPx===null?null:+minimumGapPx.toFixed(1),minimumTargetPx:minimumTargetPx===null?null:+minimumTargetPx.toFixed(1),
    alignmentDeviationPx:alignmentDeviationPx===null?null:+alignmentDeviationPx.toFixed(1),
    layoutSystems,buttonGroups,buttons:targets.slice(0,200),tables,dialogs,navigation,fixedOcclusions,overlaps,
    visual:{bodyFontPx:bodyFont,primaryActionCount:primaryActions.length,headings,elements:visualElements,salienceOrder:[...headings].sort((a,b)=>(b.fontSize||0)-(a.fontSize||0)).slice(0,5)},
    evidenceTier:'browser-measured',url:location.href.split('?')[0]
  };
}
"""


def inspect_semantic_dom(page: Any) -> dict[str, Any]:
    """Collect a bounded semantic DOM snapshot without form values or raw HTML."""

    return page.evaluate(_SEMANTIC_DOM_JS)


def persist_experience_evidence(
    output_dir: str | Path,
    *,
    label: str,
    viewport: Mapping[str, Any],
    dom_snapshot: Mapping[str, Any],
    geometry: Mapping[str, Any],
) -> dict[str, str]:
    """Persist semantic DOM and geometry sidecars for one trusted capture."""

    width = int(viewport.get("width") or 0)
    height = int(viewport.get("height") or 0)
    if width <= 0 or height <= 0:
        raise ValueError("viewport width and height must be positive")
    safe_label = "".join(char for char in str(label) if char.isalnum() or char in {"-", "_"}) or "page"
    out = Path(output_dir).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    dom_path = out / f"{safe_label}-{width}x{height}.dom.json"
    geometry_path = out / f"{safe_label}-{width}x{height}.geometry.json"
    dom_path.write_text(json.dumps(redact_structure(dict(dom_snapshot)), ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    geometry_path.write_text(json.dumps(redact_structure(dict(geometry)), ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return {"domRef": dom_path.name, "geometryRef": geometry_path.name}


def inspect_experience_geometry(page: Any, *, viewport_id: str | None = None) -> dict[str, Any]:
    """Collect a single current-viewport observation from a Playwright-like page."""
    row = page.evaluate(_EXPERIENCE_GEOMETRY_JS, viewport_id)
    return {
        "schemaVersion": "3.1",
        "status": "MEASURED",
        "viewports": [row],
        "visual": row.get("visual", {}),
        "visualElements": row.get("visual", {}).get("elements", []),
        "evidenceTier": "browser-measured",
        "claimBoundary": "This observation proves only the measured URL, state, role, viewport, and run.",
    }


__all__ = ["inspect_experience_geometry", "inspect_semantic_dom", "persist_experience_evidence"]
