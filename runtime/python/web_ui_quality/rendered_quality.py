"""Rendered-page quality checks that complement static source analysis.

These checks intentionally measure observable usability conditions rather than
claiming subjective beauty.  They inspect geometry, target size, text scale,
contrast, clipping, landmarks, focus affordance, and bounded relational
composition signals in the real browser.  Composition signals remain review
candidates: they are not a universal beauty score or an automatic hard failure.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence


_KEYBOARD_BASELINE_JS = r"""
() => {
  const visible = (el) => {
    const s = getComputedStyle(el); const r = el.getBoundingClientRect();
    return s.display !== 'none' && s.visibility !== 'hidden' && Number(s.opacity || 1) > 0 && r.width > 0 && r.height > 0;
  };
  const interactiveSelector = 'button,a[href],input,select,textarea,[role=button],[role=link],[role=checkbox],[role=switch],[role=tab],[role=combobox],[tabindex]';
  const interactive = [...document.querySelectorAll(interactiveSelector)].filter(visible);
  const enabled = (el) => !el.matches(':disabled') && el.getAttribute('aria-disabled') !== 'true';
  const focusables = interactive.filter(el => enabled(el) && el.tabIndex >= 0);
  const name = (el) => {
    const labelled = el.getAttribute('aria-labelledby');
    if (labelled) {
      const value = labelled.split(/\s+/).map(id => document.getElementById(id)?.textContent || '').join(' ').trim();
      if (value) return value.slice(0, 120);
    }
    return (el.getAttribute('aria-label') || el.getAttribute('title') || el.textContent || el.getAttribute('placeholder') || '')
      .trim().replace(/\s+/g, ' ').slice(0, 120);
  };
  const selector = (el) => {
    if (el.id) return '#'+CSS.escape(el.id);
    const test = el.getAttribute('data-testid'); if (test) return '[data-testid="'+CSS.escape(test)+'"]';
    return el.tagName.toLowerCase() + (el.getAttribute('role') ? '[role='+el.getAttribute('role')+']' : '');
  };
  const paint = (el) => {
    const s = getComputedStyle(el);
    return {
      outlineStyle: s.outlineStyle,
      outlineWidth: parseFloat(s.outlineWidth || '0') || 0,
      outlineColor: s.outlineColor,
      boxShadow: s.boxShadow,
      borderTopColor: s.borderTopColor,
      borderTopWidth: parseFloat(s.borderTopWidth || '0') || 0,
      backgroundColor: s.backgroundColor,
    };
  };
  return {
    interactiveCount: interactive.length,
    enabledInteractiveCount: interactive.filter(enabled).length,
    focusableCount: focusables.length,
    positiveTabIndexCount: focusables.filter(el => el.tabIndex > 0).length,
    scrollX: window.scrollX,
    scrollY: window.scrollY,
    focusables: focusables.slice(0, 60).map((el, index) => ({index, selector: selector(el), name: name(el), role: el.getAttribute('role') || el.tagName.toLowerCase(), tabIndex: el.tabIndex, baseStyle: paint(el)})),
  };
}
"""


_KEYBOARD_FOCUS_JS = r"""
() => {
  const visible = (el) => {
    const s = getComputedStyle(el); const r = el.getBoundingClientRect();
    return s.display !== 'none' && s.visibility !== 'hidden' && Number(s.opacity || 1) > 0 && r.width > 0 && r.height > 0;
  };
  const selector = (el) => {
    if (el.id) return '#'+CSS.escape(el.id);
    const test = el.getAttribute('data-testid'); if (test) return '[data-testid="'+CSS.escape(test)+'"]';
    return el.tagName.toLowerCase() + (el.getAttribute('role') ? '[role='+el.getAttribute('role')+']' : '');
  };
  const name = (el) => (el.getAttribute('aria-label') || el.getAttribute('title') || el.textContent || el.getAttribute('placeholder') || '')
    .trim().replace(/\s+/g, ' ').slice(0, 120);
  const paint = (el) => {
    const s = getComputedStyle(el);
    return {
      outlineStyle: s.outlineStyle,
      outlineWidth: parseFloat(s.outlineWidth || '0') || 0,
      outlineColor: s.outlineColor,
      boxShadow: s.boxShadow,
      borderTopColor: s.borderTopColor,
      borderTopWidth: parseFloat(s.borderTopWidth || '0') || 0,
      backgroundColor: s.backgroundColor,
    };
  };
  const interactiveSelector = 'button,a[href],input,select,textarea,[role=button],[role=link],[role=checkbox],[role=switch],[role=tab],[role=combobox],[tabindex]';
  const focusables = [...document.querySelectorAll(interactiveSelector)].filter(el => visible(el) && !el.matches(':disabled') && el.getAttribute('aria-disabled') !== 'true' && el.tabIndex >= 0);
  const active = document.activeElement;
  const index = focusables.indexOf(active);
  const rect = active && active.getBoundingClientRect ? active.getBoundingClientRect() : null;
  return {
    index,
    focused: Boolean(active && active !== document.body && active !== document.documentElement),
    selector: index >= 0 ? selector(active) : null,
    name: index >= 0 ? name(active) : null,
    role: index >= 0 ? (active.getAttribute('role') || active.tagName.toLowerCase()) : null,
    tabIndex: index >= 0 ? active.tabIndex : null,
    inViewport: Boolean(index >= 0 && rect && rect.right > 0 && rect.bottom > 0 && rect.left < window.innerWidth && rect.top < window.innerHeight),
    focusVisible: Boolean(index >= 0 && active.matches && active.matches(':focus-visible')),
    focusStyle: index >= 0 ? paint(active) : null,
  };
}
"""


_KEYBOARD_SCROLL_SNAPSHOT_JS = r"""
() => {
  window.__wuqKeyboardScrollState = [...document.querySelectorAll('body *')]
    .filter(el => el.scrollWidth > el.clientWidth + 1 || el.scrollHeight > el.clientHeight + 1)
    .map(el => ({el, left: el.scrollLeft, top: el.scrollTop}));
  return window.__wuqKeyboardScrollState.length;
}
"""


_KEYBOARD_SCROLL_RESTORE_JS = r"""
position => {
  document.activeElement?.blur?.();
  for (const row of (window.__wuqKeyboardScrollState || [])) {
    if (!row?.el?.isConnected) continue;
    row.el.scrollLeft = row.left;
    row.el.scrollTop = row.top;
  }
  delete window.__wuqKeyboardScrollState;
  window.scrollTo(position.x, position.y);
}
"""

_RENDERED_QUALITY_JS = r"""
() => {
  const visible = (el) => {
    const s = getComputedStyle(el); const r = el.getBoundingClientRect();
    return s.display !== 'none' && s.visibility !== 'hidden' && Number(s.opacity || 1) > 0 && r.width > 0 && r.height > 0;
  };
  const rgb = (value) => {
    const m = String(value || '').match(/rgba?\(([^)]+)\)/i); if (!m) return null;
    const p = m[1].split(',').map(Number); if (p.length < 3) return null;
    return [p[0], p[1], p[2], p.length > 3 ? p[3] : 1];
  };
  const lum = (c) => {
    const v = c.slice(0,3).map(x => { x/=255; return x <= .03928 ? x/12.92 : Math.pow((x+.055)/1.055,2.4); });
    return .2126*v[0]+.7152*v[1]+.0722*v[2];
  };
  const contrast = (a,b) => { const l1=lum(a), l2=lum(b); return (Math.max(l1,l2)+.05)/(Math.min(l1,l2)+.05); };
  const background = (el) => {
    let cur=el; while(cur){ const c=rgb(getComputedStyle(cur).backgroundColor); if(c && c[3]>.01) return c; cur=cur.parentElement; }
    return [255,255,255,1];
  };
  const selector = (el) => {
    if (el.id) return '#'+CSS.escape(el.id);
    const role=el.getAttribute('role'); const name=el.getAttribute('aria-label') || el.textContent?.trim().slice(0,40);
    return `${el.tagName.toLowerCase()}${role?`[role=${role}]`:''}${name?`:${name}`:''}`;
  };
  const classText = (el) => typeof el.className === 'string' ? el.className : (el.getAttribute('class') || '');
  const compactSelector = (el) => {
    if (el.id) return '#'+CSS.escape(el.id);
    const classes=[...el.classList].slice(0,3);
    if(classes.length) return el.tagName.toLowerCase()+classes.map(value=>'.'+CSS.escape(value)).join('');
    const test=el.getAttribute('data-testid'); if(test) return '[data-testid="'+CSS.escape(test)+'"]';
    return el.tagName.toLowerCase();
  };
  const horizontalScrollOwner = (el) => {
    let current=el.parentElement;
    while(current && current!==document.body){
      const style=getComputedStyle(current);
      if(['auto','scroll'].includes(style.overflowX) && current.scrollWidth>current.clientWidth+1) return compactSelector(current);
      current=current.parentElement;
    }
    return null;
  };
  // The conventional visually-hidden helper intentionally clips its content
  // to keep it available to assistive technology without painting it on screen.
  const intentionallyVisuallyHidden = (el) => el.classList.contains('visually-hidden');
  const intersects = (outer, inner) => inner.right > outer.left && inner.left < outer.right && inner.bottom > outer.top && inner.top < outer.bottom;
  const rounded = value => Number(value.toFixed(3));
  const interactive = [...document.querySelectorAll('button,a[href],input,select,textarea,[role=button],[role=link],[role=checkbox],[role=switch],[tabindex]')].filter(visible);
  const textEls = [...document.querySelectorAll('p,span,b,strong,small,label,li,td,th,a,button,h1,h2,h3,h4,h5,h6')].filter(el => visible(el) && el.textContent.trim());
  const all = [...document.querySelectorAll('body *')].filter(visible);
  const smallTargets=[], tinyText=[], lowContrast=[], clipped=[], overflowViewport=[], brokenImages=[], textFragmentation=[], taskActionCandidates=[];
  const oversizedControls=[], iconTextImbalance=[], inconsistentControlGroups=[];
  const iconElementBoxUnderfill=[], sparseRepeatedComponents=[], shortLabelWrap=[], iconBoxMisalignment=[], adjoiningRoundedCards=[], repeatedRowTextAlignment=[];
  const standaloneControl = (el) => el.tagName !== 'A' || el.getAttribute('role') === 'button' || el.matches('.button,.btn,[class*=button],[class*=btn]');
  for (const el of interactive) {
    const r=el.getBoundingClientRect(), s=getComputedStyle(el), fontSize=parseFloat(s.fontSize||'16');
    const text=(el.getAttribute('aria-label')||el.textContent||el.getAttribute('placeholder')||'').trim();
    if (standaloneControl(el) && (r.width < 44 || r.height < 44) && !['hidden'].includes(el.type)) {
      smallTargets.push({selector:selector(el),styleSelector:compactSelector(el),width:Math.round(r.width),height:Math.round(r.height)});
    }
    if (standaloneControl(el) && text && r.height >= 64 && fontSize <= 16 && r.height/Math.max(fontSize,1) >= 4) {
      oversizedControls.push({selector:selector(el),styleSelector:compactSelector(el),height:Math.round(r.height),fontSize:Number(fontSize.toFixed(1)),ratio:Number((r.height/fontSize).toFixed(2)),text:text.slice(0,60)});
    }
    const icon=el.querySelector('svg,img,i,[class*=icon]');
    if (icon && visible(icon) && text) {
      const ir=icon.getBoundingClientRect(), iconSize=Math.max(ir.width,ir.height), ratio=iconSize/Math.max(fontSize,1);
      if (ratio > 1.8 || ratio < .6) iconTextImbalance.push({selector:selector(el),styleSelector:compactSelector(el),iconPx:Math.round(iconSize),fontSize:Number(fontSize.toFixed(1)),ratio:Number(ratio.toFixed(2)),text:text.slice(0,60)});
    }
  }
  const controlParents=[...new Set(interactive.filter(standaloneControl).map(el=>el.parentElement).filter(Boolean))];
  for (const parent of controlParents.slice(0,300)) {
    const controls=[...parent.children].filter(el=>interactive.includes(el)&&standaloneControl(el));
    if (controls.length < 2) continue;
    const heights=controls.map(el=>el.getBoundingClientRect().height).filter(value=>value>0);
    if (heights.length < 2) continue;
    const minimum=Math.min(...heights), maximum=Math.max(...heights);
    if (maximum-minimum >= 8 && maximum/Math.max(minimum,1) >= 1.2) {
      inconsistentControlGroups.push({selector:selector(parent),styleSelector:compactSelector(parent),count:controls.length,minHeight:Math.round(minimum),maxHeight:Math.round(maximum),difference:Math.round(maximum-minimum)});
    }
  }
  for (const el of textEls.slice(0,1500)) {
    const s=getComputedStyle(el), size=parseFloat(s.fontSize||'16'), fg=rgb(s.color), bg=background(el);
    if (size < 12) tinyText.push({selector:selector(el),styleSelector:compactSelector(el),fontSize:size,text:el.textContent.trim().slice(0,80)});
    if (fg && bg) {
      const ratio=contrast(fg,bg); const bold=parseInt(s.fontWeight||'400',10)>=700;
      const threshold=(size>=24 || (size>=18.66 && bold))?3:4.5;
      if (ratio < threshold) lowContrast.push({selector:selector(el),styleSelector:compactSelector(el),ratio:Number(ratio.toFixed(2)),threshold,fontSize:size});
    }
    const text=el.textContent.trim().replace(/\s+/g,'');
    const cjkCount=(text.match(/[\u3400-\u9fff\uf900-\ufaff]/g)||[]).length;
    const hasTextChild=[...el.children].some(child=>child.textContent.trim());
    const writingMode=String(s.writingMode||'').toLowerCase();
    if (!hasTextChild && cjkCount>=2 && !writingMode.startsWith('vertical')) {
      const r=el.getBoundingClientRect();
      const lineHeight=parseFloat(s.lineHeight)||size*1.35;
      const range=document.createRange();range.selectNodeContents(el);
      const rects=[...range.getClientRects()].filter(box=>box.width>0&&box.height>0);
      const lineTops=[];
      for(const box of rects){if(!lineTops.some(top=>Math.abs(top-box.top)<2)) lineTops.push(box.top);}
      const lineCount=lineTops.length;
      const charactersPerLine=cjkCount/Math.max(lineCount,1);
      if(cjkCount>=4 && r.width<=size*2.4 && r.height>=lineHeight*2.5 && lineCount>=3 && charactersPerLine<=1.7){
        textFragmentation.push({selector:selector(el),styleSelector:compactSelector(el),text:text.slice(0,60),width:rounded(r.width),height:rounded(r.height),fontSize:rounded(size),lineHeight:rounded(lineHeight),lineCount,charactersPerLine:rounded(charactersPerLine),writingMode,evidenceClass:'BROWSER_MEASURED'});
      } else if(cjkCount<=8 && lineCount>=2 && lineCount<=3 && charactersPerLine<=3 && (el.matches('b,strong,h1,h2,h3,h4,h5,h6') || el.closest('button,[role="button"]'))){
        shortLabelWrap.push({selector:selector(el),styleSelector:compactSelector(el),text:text.slice(0,60),width:rounded(r.width),lineCount,charactersPerLine:rounded(charactersPerLine),fontSize:rounded(size),evidenceClass:'DIAGNOSTIC_CANDIDATE'});
      }
    }
  }
  for (const el of all.slice(0,3000)) {
    const r=el.getBoundingClientRect(), s=getComputedStyle(el);
    const outsideViewport=r.right > window.innerWidth + 1 || r.left < -1;
    // Children intentionally revealed through a local horizontal scroller are
    // not page overflow.  The scroller itself is still measured normally.
    if (outsideViewport && !horizontalScrollOwner(el)) overflowViewport.push({selector:selector(el),styleSelector:compactSelector(el),left:Math.round(r.left),right:Math.round(r.right)});
    if (!intentionallyVisuallyHidden(el) && (s.overflowX==='hidden' || s.overflowY==='hidden' || s.overflow==='hidden') && (el.scrollWidth > el.clientWidth + 1 || el.scrollHeight > el.clientHeight + 1) && el.textContent.trim()) clipped.push({selector:selector(el),styleSelector:compactSelector(el),scrollWidth:el.scrollWidth,clientWidth:el.clientWidth,scrollHeight:el.scrollHeight,clientHeight:el.clientHeight});
  }
  for (const image of [...document.images].filter(visible).slice(0,300)) {
    if (image.complete && image.naturalWidth === 0) brokenImages.push({selector:compactSelector(image),alt:(image.getAttribute('alt')||'').trim().slice(0,100),width:rounded(image.getBoundingClientRect().width),height:rounded(image.getBoundingClientRect().height),evidenceClass:'BROWSER_MEASURED'});
  }
  // A touch target and the visible icon surface are different things.  This
  // diagnostic only examines icons inside an explicitly named decorative
  // surface, never every 24px glyph inside a valid 44/48px hit target.
  const explicitIconSurface = /(?:^|[\s_-])(icon-wrap|icon-box|icon-container|icon-badge|mini-icon|message-icon|priority-icon|avatar|thumbnail)(?:[\s_-]|$)/i;
  const iconNodes=[...document.querySelectorAll('svg,img,i,[data-icon],[class*="icon-raster"]')].filter(visible).slice(0,500);
  for (const icon of iconNodes) {
    let container=icon.parentElement;
    for (let depth=0;container && depth<3;depth++,container=container.parentElement) {
      const cr=container.getBoundingClientRect(),cs=getComputedStyle(container);
      if (!explicitIconSurface.test(classText(container)) || cr.width<32 || cr.height<32 || cr.width>96 || cr.height>96) continue;
      const decorated=(cs.backgroundColor!=='rgba(0, 0, 0, 0)'&&cs.backgroundColor!=='transparent')||cs.backgroundImage!=='none'||parseFloat(cs.borderTopWidth||'0')>0||cs.boxShadow!=='none';
      if(!decorated) continue;
      const ir=icon.getBoundingClientRect();
      if (ir.width<=0 || ir.height<=0 || ir.width>cr.width+1 || ir.height>cr.height+1) break;
      const surfaceFillRatio=Math.min(ir.width/cr.width,ir.height/cr.height);
      if (surfaceFillRatio<.55) iconElementBoxUnderfill.push({selector:compactSelector(icon),container:compactSelector(container),iconWidth:rounded(ir.width),iconHeight:rounded(ir.height),containerWidth:rounded(cr.width),containerHeight:rounded(cr.height),surfaceFillRatio:rounded(surfaceFillRatio),threshold:.55,metric:'ELEMENT_BOX_LINEAR_FILL_NOT_VISIBLE_GRAPHIC',evidenceClass:'DIAGNOSTIC_CANDIDATE'});
      const offsetX=(ir.left+ir.width/2)-(cr.left+cr.width/2),offsetY=(ir.top+ir.height/2)-(cr.top+cr.height/2);
      if(Math.abs(offsetX)>Math.max(3,cr.width*.12)||Math.abs(offsetY)>Math.max(3,cr.height*.12)) iconBoxMisalignment.push({selector:compactSelector(icon),container:compactSelector(container),offsetX:rounded(offsetX),offsetY:rounded(offsetY),metric:'BOX_CENTER_OFFSET_NOT_OPTICAL_INK',evidenceClass:'DIAGNOSTIC_CANDIDATE'});
      break;
    }
  }
  // Repetition makes a density observation more useful: one intentionally calm
  // hero is not treated like three structurally identical, tall, sparse cards.
  const componentSelector='article,[class~="card"],[class$="-card"],[class*="-card "],[class*=" card-"],[class*="-item"],[class*="tile"]';
  const componentCandidates=[...document.querySelectorAll(componentSelector)].filter(el=>{
    if(!visible(el)) return false;
    const r=el.getBoundingClientRect(),s=getComputedStyle(el);
    const surface=s.backgroundColor!=='rgba(0, 0, 0, 0)'&&s.backgroundColor!=='transparent'||parseFloat(s.borderTopWidth||'0')>0||parseFloat(s.borderTopLeftRadius||'0')>=6;
    return r.width>=96&&r.height>=56&&surface;
  }).slice(0,240);
  const componentGroups=new Map();
  for(const el of componentCandidates){
    const tokens=[...el.classList].filter(value=>/(card|item|tile|panel|message|priority|summary|quick)/i.test(value)).sort();
    if(!tokens.length) continue;
    const signature=el.tagName.toLowerCase()+':'+tokens.join('.');
    if(!componentGroups.has(signature)) componentGroups.set(signature,[]);
    componentGroups.get(signature).push(el);
  }
  for(const [signature,elements] of componentGroups.entries()){
    // Separate card surfaces need an intentional grouping decision. Flat list
    // rows and horizontally adjacent grid cells are not this observation.
    for(let index=1;index<elements.length;index++){
      const prev=elements[index-1],el=elements[index];if(prev.parentElement!==el.parentElement) continue;
      const a=prev.getBoundingClientRect(),b=el.getBoundingClientRect(),sa=getComputedStyle(prev),sb=getComputedStyle(el);
      const overlap=Math.min(a.right,b.right)-Math.max(a.left,b.left),gap=b.top-a.bottom;
      if(a.height>=72&&b.height>=72&&overlap>=Math.min(a.width,b.width)*.8&&gap>=-.5&&gap<=3&&parseFloat(sa.borderTopLeftRadius)>=6&&parseFloat(sb.borderTopLeftRadius)>=6) adjoiningRoundedCards.push({selector:compactSelector(el),previous:compactSelector(prev),container:compactSelector(el.parentElement),gap:rounded(gap),metric:'ADJACENT_ROUNDED_SURFACE_GAP',evidenceClass:'DIAGNOSTIC_CANDIDATE'});
    }
    if(elements.length<3) continue;
    for(const el of elements){
      const r=el.getBoundingClientRect(),s=getComputedStyle(el);
      const inner={left:r.left+(parseFloat(s.paddingLeft)||0),top:r.top+(parseFloat(s.paddingTop)||0),right:r.right-(parseFloat(s.paddingRight)||0),bottom:r.bottom-(parseFloat(s.paddingBottom)||0)};
      inner.width=Math.max(1,inner.right-inner.left);inner.height=Math.max(1,inner.bottom-inner.top);
      if(inner.height<112) continue;
      const boxes=[];const walker=document.createTreeWalker(el,NodeFilter.SHOW_TEXT);let node;
      while((node=walker.nextNode())&&boxes.length<120){
        if(!node.textContent.trim()||!node.parentElement||!visible(node.parentElement)) continue;
        const range=document.createRange();range.selectNodeContents(node);
        for(const box of range.getClientRects()) if(box.width>0&&box.height>0&&intersects(inner,box)) boxes.push(box);
      }
      for(const child of el.querySelectorAll('img,svg,canvas,video,[data-icon],[class*="icon-raster"],button,input,select,textarea,.pill,.badge,.tag')){
        if(boxes.length>=160) break;if(!visible(child)) continue;const box=child.getBoundingClientRect();if(intersects(inner,box)) boxes.push(box);
      }
      let paintedArea=0;
      for(const box of boxes){const left=Math.max(inner.left,box.left),top=Math.max(inner.top,box.top),right=Math.min(inner.right,box.right),bottom=Math.min(inner.bottom,box.bottom);if(right>left&&bottom>top) paintedArea+=(right-left)*(bottom-top);}
      const paintedAreaRatio=Math.min(1,paintedArea/(inner.width*inner.height));
      if(paintedAreaRatio<.32) sparseRepeatedComponents.push({selector:compactSelector(el),signature,repetitionCount:elements.length,width:rounded(r.width),height:rounded(r.height),innerHeight:rounded(inner.height),paintedAreaRatio:rounded(paintedAreaRatio),threshold:.32,minimumInnerHeight:112,metric:'BOUNDED_DESCENDANT_AREA_RATIO',evidenceClass:'DIAGNOSTIC_CANDIDATE'});
    }
  }
  // Keep task-action discovery passive. A visible control's label and declared
  // destination help a Host choose what to verify, but an inventory never
  // proves that clicking the control is safe or that its promised outcome works.
  const actionRoot=document.querySelector('main,[role="main"]')||document.body;
  const actionContainers='article,li,[role="row"],[role="listitem"],[class~="card"],[class*="-card"],[class*="item"]';
  const actionControls=[...actionRoot.querySelectorAll('button,a[href],[role="button"]')].filter(el=>visible(el)&&!el.disabled&&el.getAttribute('aria-disabled')!=='true').slice(0,240);
  for(const el of actionControls){
    if(el.closest('nav,[role="navigation"]')) continue;
    const container=el.closest(actionContainers);if(!container) continue;
    const label=String(el.getAttribute('aria-label')||el.innerText||el.textContent||'').replace(/\s+/g,' ').trim().slice(0,80);
    if(!label) continue;
    let destinationKind='none',sameOriginTarget=null;
    if(el.tagName==='A'&&el.hasAttribute('href')){destinationKind='href';try{sameOriginTarget=new URL(el.href,location.href).origin===location.origin;}catch{sameOriginTarget=null;}}
    else if(String(el.getAttribute('data-target')||'').trim()) destinationKind='data-target';
    const role=container.getAttribute('role');
    const containerKind=container.tagName==='ARTICLE'?'article':container.tagName==='LI'?'list-item':role==='row'?'row':role==='listitem'?'list-item':container.matches('[class~="card"],[class*="-card"]')?'card':'item';
    taskActionCandidates.push({controlKind:el.tagName.toLowerCase()==='a'?'link':'button',label,dataAction:String(el.getAttribute('data-action')||'').slice(0,50)||null,destinationKind,destinationDeclared:destinationKind!=='none',sameOriginTarget,containerKind,executionStatus:'NOT_EXECUTED'});
    if(taskActionCandidates.length>=40) break;
  }
  const textRuns = (root) => {
    const walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT), runs=[];
    while(walker.nextNode()){
      const node=walker.currentNode, owner=node.parentElement;
      if(!owner||!node.nodeValue.trim()||!visible(owner)) continue;
      const range=document.createRange();range.selectNodeContents(node);
      const rects=[...range.getClientRects()].filter(box=>box.width>0&&box.height>0).map(box=>({x:rounded(box.x),y:rounded(box.y),width:rounded(box.width),height:rounded(box.height),right:rounded(box.right)}));
      if(!rects.length) continue;
      const s=getComputedStyle(owner);
      runs.push({ownerElement:owner,selector:compactSelector(owner),text:node.nodeValue.trim().slice(0,64),fontSize:rounded(parseFloat(s.fontSize)||16),fontWeight:parseInt(s.fontWeight||'400',10)||400,textAlign:s.textAlign,direction:s.direction,writingMode:s.writingMode,rects});
    }
    return runs;
  };
  const meaningfulText = (runs) => runs.map(item=>item.text).join(' ').replace(/\s+/g,' ').trim();
  const decorativeText = (value) => Boolean(value)&&/^[\p{P}\p{S}\s]+$/u.test(value);
  const hasVisualMark = (el) => {
    const visualNodes=[el,...el.querySelectorAll('*')].filter(visible);
    for(const node of visualNodes){
      if(node.matches('svg,img,picture,canvas,video,[role="img"]')) return true;
      const style=getComputedStyle(node);
      if(style.backgroundImage!=='none'||style.maskImage!=='none') return true;
      for(const pseudo of ['::before','::after']){
        const decoration=getComputedStyle(node,pseudo);
        if(decoration.display==='none'||decoration.visibility==='hidden') continue;
        if(decoration.backgroundImage!=='none'||decoration.maskImage!=='none') return true;
        if(decoration.content&&decoration.content!=='none'&&decoration.content!=='normal') return true;
      }
    }
    return false;
  };
  const scopedPath = (root,el) => {
    const parts=[];let current=el;
    while(current&&current!==root){
      let segment=current.tagName.toLowerCase();
      const classes=[...current.classList].slice(0,2);
      if(classes.length) segment+=classes.map(value=>'.'+CSS.escape(value)).join('');
      const siblings=current.parentElement?[...current.parentElement.children].filter(item=>item.tagName===current.tagName):[];
      if(siblings.length>1) segment+=':nth-of-type('+(siblings.indexOf(current)+1)+')';
      parts.unshift(segment);current=current.parentElement;
    }
    return compactSelector(root)+(parts.length?' > '+parts.join(' > '):'');
  };
  const spread = (values) => values.length?Math.max(...values)-Math.min(...values):0;
  const gridTrackCount = (value) => {
    let depth=0,count=0,token=false;
    for(const character of String(value||'')){
      if(character==='(') depth++;
      else if(character===')') depth=Math.max(0,depth-1);
      if(/\s/.test(character)&&depth===0){if(token){count++;token=false;}}
      else token=true;
    }
    return count+(token?1:0);
  };
  const rowContainers=[...all].filter(parent=>{
    if(parent.children.length<2||parent.children.length>20) return false;
    const style=getComputedStyle(parent),display=style.display,orientation=String(parent.getAttribute('aria-orientation')||'').toLowerCase();
    if(orientation==='horizontal') return false;
    if(['flex','inline-flex'].includes(display)&&!String(style.flexDirection||'').startsWith('column')) return false;
    if(['grid','inline-grid'].includes(display)&&(String(style.gridAutoFlow||'').includes('column')||gridTrackCount(style.gridTemplateColumns)>1)) return false;
    return true;
  });
  for(const parent of rowContainers){
    const parentRole=String(parent.getAttribute('role')||'').toLowerCase();
    const semanticList=['ul','ol'].includes(parent.tagName.toLowerCase())||['list','directory','listbox','tree','treegrid'].includes(parentRole);
    const rowInfo=[...parent.children].map((row,index)=>{
      if(!visible(row)) return null;
      const rowStyle=getComputedStyle(row),layoutRow=['grid','inline-grid','flex','inline-flex'].includes(rowStyle.display),rowRole=String(row.getAttribute('role')||'').toLowerCase(),semanticRow=semanticList||rowRole==='listitem';
      if(!(semanticRow||layoutRow)) return null;
      const children=[...row.children].filter(visible);
      if(children.length<2||children.length>8) return null;
      const childInfo=children.map(child=>{
        const runs=textRuns(child),value=meaningfulText(runs),content=Boolean(value)&&!decorativeText(value);
        return {element:child,runs,text:content,visual:hasVisualMark(child)||decorativeText(value),value};
      });
      const leading=childInfo[0],trailing=childInfo[childInfo.length-1];
      const hasEdgeAffordances=Boolean(leading.visual&&!leading.text&&trailing.visual&&!trailing.text);
      if(!(semanticRow||(layoutRow&&hasEdgeAffordances))) return null;
      const textChildren=childInfo.filter(item=>item.text);
      if(!textChildren.length) return null;
      const shape=childInfo.map(item=>item.text?'T':item.visual?'V':'O').join('');
      const runs=textChildren.flatMap(item=>item.runs);
      if(!runs.length) return null;
      const rects=textChildren.map(item=>item.element.getBoundingClientRect());
      const contentBox={left:Math.min(...rects.map(box=>box.left)),right:Math.max(...rects.map(box=>box.right)),top:Math.min(...rects.map(box=>box.top)),bottom:Math.max(...rects.map(box=>box.bottom))};
      const box=row.getBoundingClientRect(),tail=trailing.visual&&!trailing.text?trailing.element:null,tailRect=tail?tail.getBoundingClientRect():null;
      return {element:row,index,children,childInfo,shape,runs,contentBox,tail,tailRect,box,direction:rowStyle.direction,writingMode:rowStyle.writingMode,textAlign:rowStyle.textAlign,display:rowStyle.display,grid:rowStyle.gridTemplateColumns,gap:rowStyle.gap};
    }).filter(Boolean);
    if(rowInfo.length<2) continue;
    const groups=new Map();
    for(const item of rowInfo){
      const key=[item.shape,item.display,item.direction,item.writingMode].join('|');
      if(!groups.has(key)) groups.set(key,[]);
      groups.get(key).push(item);
    }
    for(const rows of groups.values()){
      if(rows.length<2) continue;
      const direction=rows[0].direction,writingMode=String(rows[0].writingMode||'').toLowerCase();
      if(!writingMode.startsWith('horizontal')||rows.some(item=>item.direction!==direction||item.writingMode!==rows[0].writingMode)) continue;
      if(parent.closest('[role="tree"],[role="treegrid"]')) continue;
      if(rows.some(item=>item.element.hasAttribute('aria-level')||item.element.hasAttribute('aria-posinset')||item.element.hasAttribute('data-level'))) continue;
      const parentRect=parent.getBoundingClientRect();
      const rowStarts=rows.map(item=>direction==='rtl'?parentRect.right-item.box.right:item.box.left-parentRect.left);
      const contentInsets=rows.map(item=>direction==='rtl'?item.box.right-item.contentBox.right:item.contentBox.left-item.box.left);
      const rowWidths=rows.map(item=>item.box.width);
      const endGaps=rows.filter(item=>item.tailRect).map(item=>direction==='rtl'?item.tailRect.left-parentRect.left:parentRect.right-item.tailRect.right);
      const maxFont=Math.max(...rows.flatMap(item=>item.runs.map(run=>run.fontSize)));
      const minFont=Math.min(...rows.flatMap(item=>item.runs.map(run=>run.fontSize)));
      const hasRoleHierarchy=rows.some(item=>item.runs.some(run=>run.fontWeight>=600))||maxFont-minFont>=1.5;
      const rowRoles=rows.map(item=>{
        const sorted=[...item.runs].sort((a,b)=>a.rects[0].y-b.rects[0].y);
        if(!hasRoleHierarchy) return {primary_text:sorted[0]};
        const emphasized=sorted.find(run=>run.fontWeight>=600||run.fontSize>=maxFont-0.5);
        const supporting=sorted.find(run=>run!==emphasized&&run.fontWeight<600&&run.fontSize<maxFont-0.5);
        return {emphasized_text:emphasized,supporting_text:supporting};
      });
      const roleNames=hasRoleHierarchy?['emphasized_text','supporting_text']:['primary_text'];
      const roleSpreads={},roleContentSpreads={};
      for(const roleName of roleNames){
        const items=rows.map((item,index)=>{
          const run=rowRoles[index][roleName],fragment=run&&run.rects[0];
          if(!run||!fragment) return null;
          const contentStart=direction==='rtl'?item.contentBox.right:item.contentBox.left;
          const textStart=direction==='rtl'?fragment.right:fragment.x;
          const groupStart=direction==='rtl'?parentRect.right:parentRect.left;
          return {run,fragment,offset:rounded(direction==='rtl'?groupStart-textStart:textStart-groupStart),contentOffset:rounded(direction==='rtl'?contentStart-textStart:textStart-contentStart)};
        });
        const valid=items.filter(Boolean);
        if(valid.length>=2){
          const values=valid.map(item=>item.offset),valueSpread=rounded(spread(values));
          roleSpreads[roleName]=valueSpread;
          roleContentSpreads[roleName]=rounded(spread(valid.map(item=>item.contentOffset)));
        }
      }
      const maxTextSpread=Math.max(0,...Object.values(roleSpreads));
      const rowWidthSpread=rounded(spread(rowWidths));
      const tailEndGapSpread=rounded(spread(endGaps));
      const insetSpread=spread(contentInsets),startSpread=spread(rowStarts);
      const indentationLike=startSpread>=4&&insetSpread<=2.5&&maxTextSpread<=2.5&&rowWidthSpread<=4;
      if(indentationLike) continue;
      const widthMismatch=rowWidthSpread>=Math.max(4,parentRect.width*.01);
      const trailingMismatch=endGaps.length>=2&&tailEndGapSpread>=4;
      const textMismatch=maxTextSpread>=Math.max(2.5,parentRect.width*.005);
      const centered=rows.every(item=>item.textAlign==='center');
      const hasMultipleTextRoles=rows.every(item=>item.runs.length>=2)&&hasRoleHierarchy;
      if(!textMismatch&&!widthMismatch&&!trailingMismatch) continue;
      if(centered&&!hasMultipleTextRoles&&!widthMismatch&&!trailingMismatch) continue;
      const causes=[];
      if(textMismatch) causes.push('SAME_ROLE_TEXT_RANGE_INLINE_START_SPREAD');
      if(widthMismatch) causes.push('REPEATED_ROW_WIDTH_SPREAD');
      if(trailingMismatch) causes.push('TRAILING_VISUAL_INLINE_END_SPREAD');
      const rowEvidence=rows.map((item,index)=>{
        const rowRect={x:rounded(item.box.x),y:rounded(item.box.y),width:rounded(item.box.width),height:rounded(item.box.height),right:rounded(item.box.right)};
        const contentStart=direction==='rtl'?item.contentBox.right:item.contentBox.left;
        const textRoles={};
        for(const roleName of roleNames){
          const run=rowRoles[index][roleName],fragment=run&&run.rects[0];
          if(!run||!fragment) continue;
          const textStart=direction==='rtl'?fragment.right:fragment.x,groupStart=direction==='rtl'?parentRect.right:parentRect.left;
          textRoles[roleName]={selector:scopedPath(parent,run.ownerElement),textBlockSelector:compactSelector(run.ownerElement),text:run.text,fontSize:run.fontSize,fontWeight:run.fontWeight,textAlign:run.textAlign,rangeFragment:fragment,inlineStartPx:rounded(textStart),offsetFromGroupStartPx:rounded(direction==='rtl'?groupStart-textStart:textStart-groupStart),offsetFromContentStartPx:rounded(direction==='rtl'?contentStart-textStart:textStart-contentStart),measurement:'DOM_RANGE_CLIENT_RECT_NOT_GLYPH_BOUNDS'};
        }
        const tail=item.tailRect?{selector:scopedPath(parent,item.tail),rect:{x:rounded(item.tailRect.x),y:rounded(item.tailRect.y),width:rounded(item.tailRect.width),height:rounded(item.tailRect.height),right:rounded(item.tailRect.right)},distanceToGroupInlineEndPx:rounded(direction==='rtl'?item.tailRect.left-parentRect.left:parentRect.right-item.tailRect.right)}:null;
        const contentChildren=item.childInfo.filter(child=>child.text).map(child=>scopedPath(parent,child.element));
        return {rowIndex:item.index+1,rowSelector:scopedPath(parent,item.element),rowRect,rowWidthPx:rounded(item.box.width),gridTemplateColumns:item.grid,gap:item.gap,textAlign:item.textAlign,contentSelectors:contentChildren,contentInlineStartPx:rounded(contentStart),contentWidthPx:rounded(item.contentBox.right-item.contentBox.left),textRoles,trailingVisual:tail};
      });
      const summary=[];
      if(roleSpreads.emphasized_text!==undefined) summary.push('emphasized text range starts vary by '+roleSpreads.emphasized_text+'px');
      if(roleSpreads.supporting_text!==undefined) summary.push('supporting text range starts vary by '+roleSpreads.supporting_text+'px');
      if(widthMismatch) summary.push('row widths vary by '+rowWidthSpread+'px');
      if(trailingMismatch) summary.push('trailing visual end gaps vary by '+tailEndGapSpread+'px');
      repeatedRowTextAlignment.push({selector:compactSelector(parent),styleSelector:compactSelector(parent),rowCount:rows.length,direction,writingMode:rows[0].writingMode,claimBoundary:'Text Range client rectangles describe line layout boxes, not painted glyph bounds; repeated-row grouping is a diagnostic heuristic and requires screenshot review before repair.',evidence:{metric:'REPEATED_ROW_TEXT_AND_TRAILING_ALIGNMENT',causes,summary:summary.join('; '),rowWidthSpreadPx:rowWidthSpread,textRangeStartSpreadPx:roleSpreads,textOffsetWithinContentSpreadPx:roleContentSpreads,trailingVisualGroupEndGapSpreadPx:tailEndGapSpread,rowSelectors:rowEvidence.map(item=>item.rowSelector),rows:rowEvidence}});
    }
  }
  const headings=[...document.querySelectorAll('h1,h2,h3,h4,h5,h6')].filter(visible).map(el=>Number(el.tagName.slice(1)));
  let headingSkips=0; for(let i=1;i<headings.length;i++) if(headings[i]-headings[i-1]>1) headingSkips++;
  const fixed=[...document.querySelectorAll('body *')].filter(el=>{const s=getComputedStyle(el);return visible(el)&&['fixed','sticky'].includes(s.position)}).map(el=>{const r=el.getBoundingClientRect();return {selector:selector(el),top:Math.round(r.top),bottom:Math.round(r.bottom),width:Math.round(r.width),height:Math.round(r.height)}});
  const landmarkCount=document.querySelectorAll('main,nav,header,footer,aside,[role=main],[role=navigation],[role=banner],[role=contentinfo]').length;
  const focusable=interactive.filter(el=>!el.disabled && el.getAttribute('aria-disabled')!=='true').length;
  const primaryActions=[...document.querySelectorAll('button[type=submit],.primary,.btn-primary,.button-primary,[data-variant=primary],[class*=primary]')].filter(visible);
  const pageMarker = document.body?.dataset?.wuqPage || document.documentElement?.dataset?.wuqPage || null;
  const pageEvidence = pageMarker ? {marker: pageMarker, path: location.pathname} : null;
  const stateMarker = document.body?.dataset?.wuqState || document.documentElement?.dataset?.wuqState || null;
  const emptyState = document.querySelector('[data-wuq-empty-state]');
  const stateList = document.querySelector('[data-wuq-state-list]');
  const detailTitle = document.querySelector('[data-wuq-detail-title]');
  const stateEvidence = stateMarker ? {
    marker: stateMarker,
    emptyVisible: Boolean(emptyState && !emptyState.hidden && visible(emptyState)),
    listItemCount: stateList ? [...stateList.querySelectorAll('[role=option]')].filter(visible).length : null,
    detailTitle: detailTitle ? detailTitle.textContent.trim().slice(0, 120) : null,
  } : null;
  return {
    viewport:{width:window.innerWidth,height:window.innerHeight},
    counts:{interactive:interactive.length,textElements:textEls.length,visibleElements:all.length,focusable,landmarks:landmarkCount,headings:headings.length},
    issues:{smallTargets:smallTargets.slice(0,60),tinyText:tinyText.slice(0,60),lowContrast:lowContrast.slice(0,80),textFragmentation:textFragmentation.slice(0,40),clipped:clipped.slice(0,60),overflowViewport:overflowViewport.slice(0,60),brokenImages:brokenImages.slice(0,40),oversizedControls:oversizedControls.slice(0,40),iconTextImbalance:iconTextImbalance.slice(0,40),inconsistentControlGroups:inconsistentControlGroups.slice(0,40),iconElementBoxUnderfill:iconElementBoxUnderfill.slice(0,40),sparseRepeatedComponents:sparseRepeatedComponents.slice(0,40),multiplePrimaryActions:primaryActions.length>2?primaryActions.slice(0,20).map(el=>({selector:selector(el),text:(el.getAttribute('aria-label')||el.textContent||'').trim().slice(0,60)})):[],headingSkips,fixedElements:fixed.slice(0,30)},
    taskActionCandidates:taskActionCandidates.slice(0,40),
    visualReviewCandidates:{shortLabelWrap:shortLabelWrap.slice(0,40),iconBoxMisalignment:iconBoxMisalignment.slice(0,40),adjoiningRoundedCards:adjoiningRoundedCards.slice(0,40),repeatedRowTextAlignment:repeatedRowTextAlignment.slice(0,24)},
    evidence:{url:location.href.split('?')[0],title:document.title,lang:document.documentElement.lang||'',hasMain:!!document.querySelector('main,[role=main]'),h1Count:document.querySelectorAll('h1').length,page:pageMarker,pageEvidence,state:stateMarker,stateEvidence}
  };
}
"""


_ICON_GRAPHIC_ANALYSIS_JS = r"""
async () => {
  const round = value => Number(Number(value || 0).toFixed(3));
  const classText = el => typeof el.className === 'string' ? el.className : (el.getAttribute('class') || '');
  const selector = el => {
    if (el.id) return '#'+CSS.escape(el.id);
    const classes=[...el.classList].slice(0,4);
    return el.tagName.toLowerCase()+classes.map(value=>'.'+CSS.escape(value)).join('');
  };
  const visible = el => {
    const s=getComputedStyle(el),r=el.getBoundingClientRect();
    return s.display!=='none'&&s.visibility!=='hidden'&&Number(s.opacity||1)>0&&r.width>0&&r.height>0;
  };
  const explicitSurface = /(?:^|[\s_-])(icon-wrap|icon-box|icon-container|icon-badge|mini-icon|message-icon|priority-icon|avatar|thumbnail)(?:[\s_-]|$)/i;
  const nearestSurface = el => {
    let current=el.parentElement;
    for(let depth=0;current&&depth<4;depth++,current=current.parentElement){
      if(!explicitSurface.test(classText(current))) continue;
      const s=getComputedStyle(current),r=current.getBoundingClientRect();
      const decorated=s.backgroundColor!=='rgba(0, 0, 0, 0)'&&s.backgroundColor!=='transparent'||s.backgroundImage!=='none'||parseFloat(s.borderTopWidth||'0')>0||s.boxShadow!=='none'||current.classList.contains('mini-icon');
      if(decorated&&r.width>=24&&r.height>=24&&r.width<=112&&r.height<=112) return current;
    }
    return null;
  };
  const urls = value => {
    const out=[]; const re=/url\((?:"([^"]+)"|'([^']+)'|([^)]*))\)/g; let match;
    while((match=re.exec(String(value||'')))!==null) out.push((match[1]||match[2]||match[3]||'').trim());
    return out;
  };
  const positionFraction = token => {
    token=String(token||'50%').trim().toLowerCase();
    if(token==='left'||token==='top') return 0;
    if(token==='right'||token==='bottom') return 1;
    if(token==='center') return .5;
    if(token.endsWith('%')) return Math.max(0,Math.min(1,(parseFloat(token)||0)/100));
    return null;
  };
  const px = token => {
    const value=parseFloat(String(token||''));
    return Number.isFinite(value)?value:null;
  };
  const measureElementGraphic = (el, style, rect) => {
    const svg=el.matches('svg')?el:el.querySelector('svg');
    if(!svg) return null;
    try{
      const box=svg.getBBox(),view=svg.viewBox&&svg.viewBox.baseVal,sr=svg.getBoundingClientRect();
      const vx=view&&view.width?view.x:0,vy=view&&view.height?view.y:0,vw=view&&view.width?view.width:sr.width,vh=view&&view.height?view.height:sr.height;
      const scaleX=sr.width/Math.max(vw,1),scaleY=sr.height/Math.max(vh,1);
      const left=sr.left+(box.x-vx)*scaleX,top=sr.top+(box.y-vy)*scaleY;
      return {sourceType:'inline-svg-geometry',inkBounds:{left:round(left-rect.left),top:round(top-rect.top),right:round(left-rect.left+box.width*scaleX),bottom:round(top-rect.top+box.height*scaleY)},measurement:'SVG_GEOMETRY_BOUNDS_NOT_PERCEPTUAL_CENTER'};
    }catch(_){return null;}
  };
  const imageCache=new Map();
  const readImage=async url=>{
    if(imageCache.has(url)) return imageCache.get(url);
    const promise=(async()=>{
      try{
        const resolved=new URL(url,location.href);
        if(resolved.protocol!=='data:'&&resolved.origin!==location.origin) return {status:'CROSS_ORIGIN_NOT_MEASURED'};
        const image=new Image();
        const loaded=new Promise((resolve,reject)=>{image.onload=resolve;image.onerror=reject;});
        image.src=resolved.href;
        await loaded;
        const width=image.naturalWidth,height=image.naturalHeight;
        if(!width||!height||width*height>4000000) return {status:'PIXEL_BUDGET_EXCEEDED',naturalSize:{width,height}};
        const canvas=document.createElement('canvas');canvas.width=width;canvas.height=height;
        const context=canvas.getContext('2d',{willReadFrequently:true});context.drawImage(image,0,0);
        const data=context.getImageData(0,0,width,height).data;
        let left=width,top=height,right=-1,bottom=-1,ink=0;
        for(let y=0;y<height;y++) for(let x=0;x<width;x++) if(data[(y*width+x)*4+3]>16){ink++;if(x<left)left=x;if(x>right)right=x;if(y<top)top=y;if(y>bottom)bottom=y;}
        return {status:'MEASURED',width,height,data,inkBounds:ink?{left,top,right:right+1,bottom:bottom+1}:null,inkPixels:ink};
      }catch(error){return {status:'PIXEL_READ_UNAVAILABLE',reason:String(error&&error.name||'IMAGE_READ_FAILED')};}
    })();
    imageCache.set(url,promise);return promise;
  };
  const iconNodes=[...document.querySelectorAll('svg,img,i,[data-icon],.icon,[class*="icon-"]')]
    .filter(el=>visible(el)&&!explicitSurface.test(classText(el))&&(el.matches('[data-icon],.icon,[class*="icon-"]')||nearestSurface(el)))
    .slice(0,240);
  const samples=[],visibleMisalignment=[],visibleUnderfill=[],spriteEdgeResidue=[];
  for(const el of iconNodes){
    const rect=el.getBoundingClientRect(),style=getComputedStyle(el),surface=nearestSurface(el),surfaceRect=surface&&surface.getBoundingClientRect();
    const maskUrl=urls(style.maskImage||style.webkitMaskImage)[0]||null;
    const backgroundUrl=urls(style.backgroundImage)[0]||null;
    const imgUrl=el.matches('img')?(el.currentSrc||el.src):null;
    const resourceUrl=maskUrl||backgroundUrl||imgUrl;
    let inkBounds=null,asset=null,crop=null;
    if(resourceUrl){
      const source=await readImage(resourceUrl);
      asset={status:source.status,url:new URL(resourceUrl,location.href).href,path:(()=>{try{const resolved=new URL(resourceUrl,location.href);return resolved.protocol==='data:'?resolved.href:resolved.pathname}catch(_){return resourceUrl}})(),naturalSize:source.width?{width:source.width,height:source.height}:source.naturalSize||null};
      if(source.status==='MEASURED'){
        const maskSize=String(style.maskSize||style.webkitMaskSize||'auto').split(/\s+/),maskPos=String(style.maskPosition||style.webkitMaskPosition||'50% 50%').split(/\s+/);
        const sourceWidth=source.width,sourceHeight=source.height;
        let renderedWidth=rect.width,renderedHeight=rect.height;
        if(maskUrl){
          if(maskSize[0]==='contain'||maskSize[0]==='cover'){
            const fit=maskSize[0]==='contain'?Math.min(rect.width/sourceWidth,rect.height/sourceHeight):Math.max(rect.width/sourceWidth,rect.height/sourceHeight);
            renderedWidth=sourceWidth*fit;renderedHeight=sourceHeight*fit;
          }else{
            const dimension=(token,available,intrinsic)=>token&&token.endsWith('%')?available*(parseFloat(token)||0)/100:token&&token.endsWith('px')?(parseFloat(token)||0):intrinsic;
            renderedWidth=dimension(maskSize[0],rect.width,sourceWidth);
            renderedHeight=dimension(maskSize[1]||maskSize[0],rect.height,sourceHeight);
          }
        }else if(backgroundUrl){
          const bg=String(style.backgroundSize||'auto').split(/\s+/);
          if(bg[0]==='contain'||bg[0]==='cover'){
            const fit=bg[0]==='contain'?Math.min(rect.width/sourceWidth,rect.height/sourceHeight):Math.max(rect.width/sourceWidth,rect.height/sourceHeight);
            renderedWidth=sourceWidth*fit;renderedHeight=sourceHeight*fit;
          }
        }
        const scaleX=renderedWidth/sourceWidth,scaleY=renderedHeight/sourceHeight;
        const posX=positionFraction(maskPos[0]||'50%'),posY=positionFraction(maskPos[1]||'50%');
        const offsetX=posX===null?px(maskPos[0]):(rect.width-renderedWidth)*posX;
        const offsetY=posY===null?px(maskPos[1]):(rect.height-renderedHeight)*posY;
        const sourceLeft=Math.max(0,Math.min(sourceWidth,-(offsetX||0)/Math.max(scaleX,.0001)));
        const sourceTop=Math.max(0,Math.min(sourceHeight,-(offsetY||0)/Math.max(scaleY,.0001)));
        const cropWidth=Math.max(0,Math.min(sourceWidth-sourceLeft,rect.width/Math.max(scaleX,.0001)));
        const cropHeight=Math.max(0,Math.min(sourceHeight-sourceTop,rect.height/Math.max(scaleY,.0001)));
        let l=sourceWidth,t=sourceHeight,r=-1,b=-1,ink=0,edge=0;
        const right=Math.min(sourceWidth,Math.ceil(sourceLeft+cropWidth)),bottom=Math.min(sourceHeight,Math.ceil(sourceTop+cropHeight));
        const edgeX=Math.max(1,Math.ceil(cropWidth*.05)),edgeY=Math.max(1,Math.ceil(cropHeight*.05));
        for(let y=Math.max(0,Math.floor(sourceTop));y<bottom;y++) for(let x=Math.max(0,Math.floor(sourceLeft));x<right;x++){
          if(source.data[(y*sourceWidth+x)*4+3]<=16) continue;
          ink++;if(x<l)l=x;if(x>=r)r=x+1;if(y<t)t=y;if(y>=b)b=y+1;
          if(x<sourceLeft+edgeX||x>=sourceLeft+cropWidth-edgeX||y<sourceTop+edgeY||y>=sourceTop+cropHeight-edgeY)edge++;
        }
        if(ink){inkBounds={left:round(l*scaleX+(offsetX||0)),top:round(t*scaleY+(offsetY||0)),right:round(r*scaleX+(offsetX||0)),bottom:round(b*scaleY+(offsetY||0))};}
        const scaleRatioX=renderedWidth/Math.max(rect.width,1),scaleRatioY=renderedHeight/Math.max(rect.height,1);
        const columns=cropWidth>0?Math.round(sourceWidth/cropWidth):0,rows=cropHeight>0?Math.round(sourceHeight/cropHeight):0;
        const gridLike=Boolean(maskUrl&&scaleRatioX>=1.5&&scaleRatioY>=1.5&&columns>=2&&columns<=8&&rows>=2&&rows<=8&&Math.abs(sourceWidth/cropWidth-columns)<.08&&Math.abs(sourceHeight/cropHeight-rows)<.08);
        const cellColumn=gridLike?Math.min(columns-1,Math.floor((sourceLeft+cropWidth/2)/(sourceWidth/columns))):null;
        const cellRow=gridLike?Math.min(rows-1,Math.floor((sourceTop+cropHeight/2)/(sourceHeight/rows))):null;
        crop={kind:maskUrl?'CSS_MASK_IMAGE':backgroundUrl?'CSS_BACKGROUND_IMAGE': 'IMAGE_ELEMENT',size:maskUrl?style.maskSize:backgroundUrl?style.backgroundSize:null,position:maskUrl?style.maskPosition:backgroundUrl?style.backgroundPosition:null,repeat:maskUrl?style.maskRepeat:backgroundUrl?style.backgroundRepeat:null,renderedSize:{width:round(renderedWidth),height:round(renderedHeight)},elementSize:{width:round(rect.width),height:round(rect.height)},sourceRect:{left:round(sourceLeft),top:round(sourceTop),width:round(cropWidth),height:round(cropHeight)},scaleRatio:{x:round(scaleRatioX),y:round(scaleRatioY)},gridLike,grid:{columns:gridLike?columns:null,rows:gridLike?rows:null,column:cellColumn,row:cellRow},edgeInkPixels:edge,edgeInkRatio:round(ink?edge/ink:0),sourceInkPixels:ink};
        asset.inkBounds=source.inkBounds;
        asset.visibleInkBounds=inkBounds;
      }
    }else{
      const svg=measureElementGraphic(el,style,rect);
      if(svg){inkBounds=svg.inkBounds;asset={status:'MEASURED',url:null,path:null,naturalSize:null,sourceType:svg.sourceType,measurement:svg.measurement,visibleInkBounds:inkBounds};}
    }
    const sample={selector:selector(el),surfaceSelector:surface?selector(surface):null,resource:asset,crop,centers:{surface:surfaceRect?{x:round(surfaceRect.x+surfaceRect.width/2),y:round(surfaceRect.y+surfaceRect.height/2)}:null,elementBox:{x:round(rect.x+rect.width/2),y:round(rect.y+rect.height/2)},visibleGraphicBounds:inkBounds?{x:round(rect.x+(inkBounds.left+inkBounds.right)/2),y:round(rect.y+(inkBounds.top+inkBounds.bottom)/2)}:null},offsets:null,graphicBoundsFill:null,evidenceClass:'BROWSER_MEASURED',visualCenterStatus:'NOT_AUTO_PASSED',sourceOwner:{status:'NOT_CONFIRMED',selector:selector(el),missing:['owning source file and icon() call site require source mapping']}};
    if(inkBounds){
      const graphicCenter={x:rect.x+(inkBounds.left+inkBounds.right)/2,y:rect.y+(inkBounds.top+inkBounds.bottom)/2};
      sample.offsets={visibleBoundsVsElementBox:{x:round(graphicCenter.x-(rect.x+rect.width/2)),y:round(graphicCenter.y-(rect.y+rect.height/2))},visibleBoundsVsSurface:surfaceRect?{x:round(graphicCenter.x-(surfaceRect.x+surfaceRect.width/2)),y:round(graphicCenter.y-(surfaceRect.y+surfaceRect.height/2))}:null};
      if(surfaceRect){
        const width=Math.max(0,Math.min(rect.right,rect.left+inkBounds.right)-Math.max(rect.left,rect.left+inkBounds.left));
        const height=Math.max(0,Math.min(rect.bottom,rect.top+inkBounds.bottom)-Math.max(rect.top,rect.top+inkBounds.top));
        const fill=Math.min(width/Math.max(surfaceRect.width,1),height/Math.max(surfaceRect.height,1));
        sample.graphicBoundsFill={width:round(width),height:round(height),linearRatio:round(fill),metric:'VISIBLE_ALPHA_BOUND_LINEAR_FILL_NOT_AESTHETIC_SCORE'};
        const dx=graphicCenter.x-(surfaceRect.x+surfaceRect.width/2),dy=graphicCenter.y-(surfaceRect.y+surfaceRect.height/2);
        if(Math.abs(dx)>Math.max(2,surfaceRect.width*.10)||Math.abs(dy)>Math.max(2,surfaceRect.height*.10)) visibleMisalignment.push({...sample,ruleId:'RENDER-ICON-VISIBLE-GRAPHIC-OFFSET',metric:'VISIBLE_ALPHA_BOUND_CENTER_NOT_OPTICAL_CENTROID'});
        if(fill<.20) visibleUnderfill.push({...sample,ruleId:'RENDER-ICON-VISIBLE-GRAPHIC-UNDERFILL',metric:'VISIBLE_ALPHA_BOUND_LINEAR_FILL',reviewThreshold:.20});
      }
    }
    if(crop&&crop.gridLike&&crop.edgeInkPixels>=2&&crop.edgeInkRatio>=.02) spriteEdgeResidue.push({...sample,ruleId:'RENDER-ICON-SPRITE-CROP-EDGE-INK',metric:'CSS_MASK_CROP_EDGE_ALPHA',assetUse:{url:asset.url,path:asset.path,selector:selector(el),surfaceSelector:surface?selector(surface):null,crop}});
    samples.push(sample);
  }
  return {status:'MEASURED_CANDIDATES_ONLY',claimBoundary:'Pixel alpha bounds and CSS crop coordinates are measurable evidence, not perceptual centroids or automatic visual acceptance. Ordinary touch-target whitespace and non-symmetric geometry require screenshot review.',counts:{icons:samples.length,pixelMeasured:samples.filter(row=>row.resource&&row.resource.status==='MEASURED').length,visibleGraphicMisalignment:visibleMisalignment.length,visibleGraphicUnderfill:visibleUnderfill.length,spriteEdgeResidue:spriteEdgeResidue.length},samples:samples.slice(0,120),candidates:{visibleGraphicMisalignment:visibleMisalignment.slice(0,40),visibleGraphicUnderfill:visibleUnderfill.slice(0,40),spriteEdgeResidue:spriteEdgeResidue.slice(0,40)}};
}
"""


def _focus_style_changed(focused: Mapping[str, Any], baseline: Mapping[str, Any]) -> bool:
    for key in (
        "outlineStyle", "outlineWidth", "outlineColor", "boxShadow",
        "borderTopColor", "borderTopWidth", "backgroundColor",
    ):
        if focused.get(key) != baseline.get(key):
            return True
    return False


def _has_focus_affordance(focused: Mapping[str, Any], baseline: Mapping[str, Any]) -> bool:
    style = focused.get("focusStyle") if isinstance(focused.get("focusStyle"), Mapping) else {}
    outline_style = str(style.get("outlineStyle") or "").casefold()
    outline_width = float(style.get("outlineWidth") or 0)
    box_shadow = str(style.get("boxShadow") or "").casefold()
    visible_outline = outline_style not in {"", "none", "hidden"} and outline_width > 0
    visible_shadow = box_shadow not in {"", "none"}
    return visible_outline or visible_shadow or _focus_style_changed(style, baseline)


def _keyboard_finding(
    rule_id: str,
    severity: str,
    title: str,
    reason_code: str,
    samples: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "id": rule_id,
        "severity": severity,
        "title": title,
        "count": len(samples),
        "reasonCode": reason_code,
        "samples": [dict(item) for item in samples[:8]],
    }


def _keyboard_sampling_context(baseline: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize the bounded baseline once before applying keyboard rules."""

    focusables = list(baseline.get("focusables") or [])
    focusable_count = int(baseline.get("focusableCount") or len(focusables))
    enabled_count = int(baseline.get("enabledInteractiveCount") or 0)
    interactive_count = int(baseline.get("interactiveCount") or 0)
    positive_count = int(baseline.get("positiveTabIndexCount") or 0)
    coverage_target = min(max(focusable_count, 0), 60)
    sampled_focusables = focusables[:coverage_target] if coverage_target else []
    sampled_indices = {
        int(item.get("index"))
        for item in sampled_focusables
        if isinstance(item, Mapping) and isinstance(item.get("index"), int)
    }
    return {
        "focusables": focusables,
        "focusableCount": focusable_count,
        "enabledCount": enabled_count,
        "interactiveCount": interactive_count,
        "positiveCount": positive_count,
        "coverageTarget": coverage_target,
        "sampledFocusables": sampled_focusables,
        "sampledIndices": sampled_indices,
        "coverageComplete": len(sampled_indices) == coverage_target,
    }


def _keyboard_counts(context: Mapping[str, Any], observations: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    sampled_indices = context["sampledIndices"]
    return {
        "interactive": int(context["interactiveCount"]),
        "enabledInteractive": int(context["enabledCount"]),
        "focusable": int(context["focusableCount"]),
        "stepsAttempted": len(observations),
        "visited": 0,
        "focusAdvance": 0,
        "outOfViewport": 0,
        "focusAffordanceMeasured": 0,
        "focusAffordanceUnmeasured": 0,
        "missingFocusAffordance": 0,
        "positiveTabIndex": int(context["positiveCount"]),
        "sampledFocusable": len(sampled_indices),
        "uniqueVisited": 0,
        "unvisitedSampled": 0,
        "coverageUnmeasured": max(0, int(context["coverageTarget"]) - len(sampled_indices)),
    }


def _keyboard_result_shell(counts: dict[str, int], context: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "evidenceTier": "browser-measured",
        "claimBoundary": "Tab traversal proves only the sampled visible controls in this URL, state, browser, and viewport; it does not prove every route or assistive technology.",
        "status": "NOT_VERIFIED",
        "counts": counts,
        "coverage": {
            "status": "NOT_MEASURED",
            "complete": bool(context["coverageComplete"]),
            "sampled": len(context["sampledIndices"]),
            "target": int(context["coverageTarget"]),
        },
        "samples": [],
        "findings": [],
    }


def _enrich_keyboard_observations(
    observations: Sequence[Mapping[str, Any]],
    sampled_focusables: Sequence[Mapping[str, Any]],
    counts: dict[str, int],
) -> list[dict[str, Any]]:
    baseline_by_index = {
        int(item.get("index")): item.get("baseStyle") or {}
        for item in sampled_focusables
        if isinstance(item, Mapping) and item.get("index") is not None
    }
    enriched: list[dict[str, Any]] = []
    for raw in observations:
        if not isinstance(raw, Mapping):
            continue
        item = dict(raw)
        index = item.get("index")
        if isinstance(index, int) and index >= 0:
            counts["visited"] += 1
            if not bool(item.get("inViewport")):
                counts["outOfViewport"] += 1
            if index not in baseline_by_index:
                counts["focusAffordanceUnmeasured"] += 1
                item["focusAffordance"] = "not_measured"
                enriched.append(item)
                continue
            affordance = _has_focus_affordance(item, baseline_by_index.get(index, {}))
            counts["focusAffordanceMeasured"] += 1
            item["focusAffordance"] = "visible" if affordance else "missing"
            if not affordance:
                counts["missingFocusAffordance"] += 1
        enriched.append(item)
    return enriched


def _finalize_keyboard_coverage(
    enriched: Sequence[Mapping[str, Any]],
    observations: Sequence[Mapping[str, Any]],
    context: Mapping[str, Any],
    counts: dict[str, int],
    steps_expected: int | None,
) -> tuple[list[int], set[int], bool]:
    indices = [
        item.get("index")
        for item in enriched
        if isinstance(item.get("index"), int) and item.get("index") >= 0
    ]
    counts["focusAdvance"] = sum(1 for left, right in zip(indices, indices[1:]) if left != right)
    visited_indices = set(indices)
    counts["uniqueVisited"] = len(visited_indices)
    counts["unvisitedSampled"] = len(context["sampledIndices"] - visited_indices)
    coverage_attempted = (
        steps_expected >= int(context["coverageTarget"])
        if steps_expected is not None
        else len(observations) >= int(context["coverageTarget"])
    )
    return indices, visited_indices, bool(context["coverageComplete"]) and coverage_attempted


def _keyboard_findings(
    indices: Sequence[int],
    visited_indices: set[int],
    enriched: Sequence[Mapping[str, Any]],
    context: Mapping[str, Any],
    counts: Mapping[str, int],
    coverage_measured: bool,
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if not indices:
        findings.append(_keyboard_finding(
            "RENDER-KEYBOARD-UNREACHABLE", "P1", "Tab 没有到达任何可操作控件",
            "TAB_DID_NOT_REACH_CONTROL", enriched,
        ))
    if counts["outOfViewport"]:
        findings.append(_keyboard_finding(
            "RENDER-KEYBOARD-FOCUS-OFFSCREEN", "P1", "键盘焦点移动到了视口外",
            "FOCUS_OUTSIDE_VIEWPORT", [item for item in enriched if not item.get("inViewport")],
        ))
    if coverage_measured and counts["unvisitedSampled"]:
        findings.append(_keyboard_finding(
            "RENDER-KEYBOARD-COVERAGE", "P1", "Tab 没有覆盖所有采样的可操作控件",
            "TAB_SAMPLE_NOT_COVERED",
            [item for item in context["sampledFocusables"] if isinstance(item, Mapping) and item.get("index") not in visited_indices],
        ))
    affordance_measured = counts["focusAffordanceMeasured"]
    if affordance_measured >= 2 and counts["missingFocusAffordance"] * 2 >= affordance_measured:
        findings.append(_keyboard_finding(
            "RENDER-KEYBOARD-FOCUS-AFFORDANCE", "P1", "多数键盘焦点没有可见提示",
            "FOCUS_AFFORDANCE_MISSING", [item for item in enriched if item.get("focusAffordance") == "missing"],
        ))
    if counts["positiveTabIndex"]:
        findings.append(_keyboard_finding(
            "RENDER-KEYBOARD-POSITIVE-TABINDEX", "P2", "存在正 tabindex，键盘顺序可能偏离 DOM 顺序",
            "POSITIVE_TABINDEX", [item for item in context["focusables"] if isinstance(item, Mapping) and int(item.get("tabIndex") or 0) > 0],
        ))
    return findings


def _summarize_keyboard_audit(
    baseline: Mapping[str, Any],
    observations: Sequence[Mapping[str, Any]],
    *,
    error: str | None = None,
    steps_expected: int | None = None,
) -> dict[str, Any]:
    safe_baseline = baseline if isinstance(baseline, Mapping) else {}
    context = _keyboard_sampling_context(safe_baseline)
    counts = _keyboard_counts(context, observations)
    result = _keyboard_result_shell(counts, context)
    if error:
        result["reasonCode"] = "KEYBOARD_AUDIT_RUNTIME_ERROR"
        result["reason"] = str(error)[:300]
        return result
    if context["enabledCount"] == 0:
        result["status"] = "NOT_APPLICABLE"
        result["reasonCode"] = "NO_ENABLED_INTERACTIVE_CONTROLS"
        return result
    if context["focusableCount"] == 0:
        result["status"] = "FAIL"
        result["reasonCode"] = "NO_KEYBOARD_REACHABLE_CONTROLS"
        result["findings"] = [_keyboard_finding(
            "RENDER-KEYBOARD-UNREACHABLE", "P1", "存在可操作元素，但 Tab 无法到达任何控件",
            "NO_KEYBOARD_REACHABLE_CONTROLS", (),
        )]
        return result

    enriched = _enrich_keyboard_observations(observations, context["sampledFocusables"], counts)
    result["samples"] = enriched[:12]
    indices, visited_indices, coverage_measured = _finalize_keyboard_coverage(
        enriched, observations, context, counts, steps_expected,
    )
    result["coverage"] = {
        "status": "MEASURED" if coverage_measured else "NOT_MEASURED",
        "complete": bool(context["coverageComplete"]),
        "sampled": len(context["sampledIndices"]),
        "target": int(context["coverageTarget"]),
        "uniqueVisited": len(visited_indices & context["sampledIndices"]),
        "unvisitedSampled": counts["unvisitedSampled"],
    }
    findings = _keyboard_findings(indices, visited_indices, enriched, context, counts, coverage_measured)
    result["samplingLimit"] = min(int(context["focusableCount"]), 60)
    result["findings"] = findings
    if counts["focusAffordanceUnmeasured"]:
        result["reasonCode"] = "KEYBOARD_SAMPLE_LIMIT_REACHED"
    elif not coverage_measured:
        result["reasonCode"] = "KEYBOARD_COVERAGE_NOT_MEASURED" if context["coverageComplete"] else "KEYBOARD_SAMPLE_LIMIT_REACHED"
    result["status"] = "FAIL" if any(item["severity"] == "P1" for item in findings) else "PASS_WITH_WARNINGS" if findings or counts["focusAffordanceUnmeasured"] or not coverage_measured else "PASS"
    return result


def inspect_keyboard_navigation(page: Any, *, max_steps: int = 60) -> dict[str, Any]:
    """Measure a bounded, read-only Tab traversal in the current browser page."""

    try:
        baseline = page.evaluate(_KEYBOARD_BASELINE_JS)
    except Exception as error:
        return _summarize_keyboard_audit({}, (), error=f"{type(error).__name__}: {error}")
    if not isinstance(baseline, Mapping):
        return _summarize_keyboard_audit({}, (), error="keyboard baseline did not return an object")
    if int(baseline.get("enabledInteractiveCount") or 0) == 0 or int(baseline.get("focusableCount") or 0) == 0:
        return _summarize_keyboard_audit(baseline, ())

    focusable_count = int(baseline.get("focusableCount") or 0)
    steps = min(max(1, min(focusable_count, 60) + 1), max(1, int(max_steps)))
    observations: list[Mapping[str, Any]] = []
    traversal_error: str | None = None
    try:
        page.evaluate(_KEYBOARD_SCROLL_SNAPSHOT_JS)
        page.evaluate("() => { document.activeElement?.blur?.(); window.scrollTo(0, 0); }")
        for _ in range(steps):
            page.keyboard.press("Tab")
            observation = page.evaluate(_KEYBOARD_FOCUS_JS)
            if isinstance(observation, Mapping):
                observations.append(observation)
    except Exception as error:
        traversal_error = f"{type(error).__name__}: {error}"
    finally:
        try:
            page.evaluate(
                _KEYBOARD_SCROLL_RESTORE_JS,
                {"x": baseline.get("scrollX") or 0, "y": baseline.get("scrollY") or 0},
            )
        except Exception:
            pass
    return _summarize_keyboard_audit(baseline, observations, error=traversal_error, steps_expected=steps)


_COMPOSITION_CLAIM_BOUNDARY = (
    "Relational browser heuristics identify review candidates for repeated component density "
    "and explicit icon-surface proportion in this URL, state, and viewport. They do not prove "
    "subjective beauty, business intent, optical centering from DOM boxes or alpha-bounds, or reference fidelity."
)


def _composition_findings(issues: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Map bounded composition observations without promoting them to hard failures."""

    mapping = (
        ("RENDER-SHORT-LABEL-WRAP", "短标题或操作标签被挤换行，需要复核内容与布局分配", issues.get("shortLabelWrap", [])),
        ("RENDER-ICON-BOX-MISALIGNMENT", "图标元素盒中心与装饰底板中心不一致；这本身不证明可见图形居中", issues.get("iconBoxMisalignment", [])),
        ("RENDER-ICON-VISIBLE-GRAPHIC-OFFSET", "可见图形边界中心与底板中心存在偏差，需要查看正常尺寸截图", issues.get("iconVisibleGraphicMisalignment", [])),
        ("RENDER-ICON-VISIBLE-GRAPHIC-UNDERFILL", "可见图形在装饰底板中的占用偏低，需要按组件意图复核", issues.get("iconVisibleGraphicUnderfill", [])),
        ("RENDER-ICON-SPRITE-CROP-EDGE-INK", "实际 CSS 图集裁切在选中单元边缘存在可见像素，需核对原图和裁切位置", issues.get("spriteEdgeResidue", [])),
        ("RENDER-ADJOINING-ROUNDED-CARDS", "相邻圆角卡片几乎贴连，需要复核模块分组与间距", issues.get("adjoiningRoundedCards", [])),
        ("RENDER-REPEATED-ROW-ALIGNMENT", "同组列表行的文字起点或尾部操作位置不一致，需要复核共享布局", issues.get("repeatedRowTextAlignment", [])),
        (
            "RENDER-SPARSE-REPEATED-COMPONENT",
            "重复组件高度较大但内容占用偏低，可能存在无意的大块空白",
            issues.get("sparseRepeatedComponents", []),
        ),
    )
    findings: list[dict[str, Any]] = []
    for rule_id, title, evidence in mapping:
        samples = [dict(item) for item in evidence if isinstance(item, Mapping)]
        if samples:
            findings.append({
                "id": rule_id,
                "severity": "P2",
                "title": title,
                "count": len(samples),
                "samples": samples[:8],
                "evidenceClass": "DIAGNOSTIC_CANDIDATE",
                "confidence": "medium",
                "claimBoundary": _COMPOSITION_CLAIM_BOUNDARY,
            })
    return findings


def _attach_icon_graphic_analysis(page: Any, raw: dict[str, Any]) -> dict[str, Any]:
    """Attach measured graphic bounds and exact applied-asset crop evidence.

    Alpha bounds and crop contacts stay diagnostic candidates; they do not
    establish perceptual centering or an aesthetic pass.
    """

    try:
        result = page.evaluate(_ICON_GRAPHIC_ANALYSIS_JS)
    except Exception as error:
        result = {
            "status": "NOT_MEASURED",
            "reason": f"{type(error).__name__}: {error}",
            "missing": ["same-origin readable icon resource or inline SVG geometry"],
        }
    if not isinstance(result, Mapping):
        result = {"status": "NOT_MEASURED", "reason": "icon analysis returned no object"}
    analysis = dict(result)
    raw["iconGraphicAnalysis"] = analysis
    issues = raw.setdefault("issues", {})
    candidates = analysis.get("candidates") if isinstance(analysis.get("candidates"), Mapping) else {}
    issues["iconVisibleGraphicMisalignment"] = list(candidates.get("visibleGraphicMisalignment") or [])
    issues["iconVisibleGraphicUnderfill"] = list(candidates.get("visibleGraphicUnderfill") or [])
    issues["spriteEdgeResidue"] = list(candidates.get("spriteEdgeResidue") or [])
    return analysis


def _relational_heuristic_findings(issues: Mapping[str, Any]) -> list[dict[str, Any]]:
    mapping = (
        ("RENDER-OVERSIZED-CONTROL", "控件高度与标签字号比例需要复核", issues.get("oversizedControls", [])),
        ("RENDER-INCONSISTENT-CONTROL-HEIGHT", "同组控件高度差异需要复核", issues.get("inconsistentControlGroups", [])),
        ("RENDER-ICON-TEXT-IMBALANCE", "控件内图标与文字比例需要复核", issues.get("iconTextImbalance", [])),
    )
    return [
        {
            "id": rule_id,
            "severity": "P2",
            "title": title,
            "count": len(samples),
            "samples": list(samples)[:8],
            "evidenceClass": "DIAGNOSTIC_CANDIDATE",
            "confidence": "medium",
            "claimBoundary": "Relational browser heuristic only; component role and design intent require independent review before defect admission.",
        }
        for rule_id, title, samples in mapping
        if samples
    ]


def _broken_image_findings(issues: Mapping[str, Any]) -> list[dict[str, Any]]:
    samples = [dict(item) for item in (issues.get("brokenImages") or []) if isinstance(item, Mapping)]
    if not samples:
        return []
    return [{
        "id": "RENDER-BROKEN-IMAGE",
        "severity": "P1",
        "title": "可见图片资源加载失败",
        "count": len(samples),
        "samples": samples[:8],
        "evidenceClass": "BROWSER_MEASURED",
        "confidence": "high",
        "claimBoundary": "The visible image failed in the observed browser state; overall page readiness and business-state representativeness remain separate boundaries.",
    }]


def _text_fragmentation_findings(issues: Mapping[str, Any]) -> list[dict[str, Any]]:
    samples = [dict(item) for item in (issues.get("textFragmentation") or []) if isinstance(item, Mapping)]
    if not samples:
        return []
    return [{
        "id": "RENDER-TEXT-FRAGMENTATION",
        "severity": "P1",
        "title": "横排正文被挤成连续单字换行，已破坏可读性",
        "count": len(samples),
        "samples": samples[:8],
        "evidenceClass": "BROWSER_MEASURED",
        "confidence": "high",
        "claimBoundary": (
            "The finding proves severe CJK line fragmentation only for the observed URL, state, and viewport. "
            "Explicit CSS vertical writing is excluded; design intent and other viewports remain separate claims."
        ),
    }]


def inspect_visual_composition(page: Any) -> dict[str, Any]:
    """Return reference-free composition candidates for a rendered page."""

    raw = page.evaluate(_RENDERED_QUALITY_JS)
    icon_analysis = _attach_icon_graphic_analysis(page, raw)
    findings = _composition_findings({**raw.get("issues", {}), **raw.get("visualReviewCandidates", {})})
    return {
        "status": "PASS_WITH_WARNINGS" if findings else "PASS",
        "evidenceTier": "browser-relational-diagnostic",
        "claimBoundary": _COMPOSITION_CLAIM_BOUNDARY,
        "findings": findings,
        "viewport": raw.get("viewport"),
        "iconGraphicAnalysis": icon_analysis,
    }


def inspect_rendered_page(page: Any) -> dict[str, Any]:
    raw = page.evaluate(_RENDERED_QUALITY_JS)
    _attach_icon_graphic_analysis(page, raw)
    issues = raw.get("issues", {})
    keyboard_audit = inspect_keyboard_navigation(page)
    raw["keyboardAudit"] = keyboard_audit
    keyboard_findings = list(keyboard_audit.get("findings") or [])
    penalties = {
        "layout": min(35, len(issues.get("overflowViewport", [])) * 8 + len(issues.get("clipped", [])) * 4 + len(issues.get("brokenImages", [])) * 8),
        "readability": min(35, len(issues.get("tinyText", [])) * 2 + len(issues.get("lowContrast", [])) * 3 + len(issues.get("textFragmentation", [])) * 10),
        "interaction": min(30, len(issues.get("smallTargets", [])) * 2 + len(issues.get("oversizedControls", [])) + len(keyboard_findings) * 6),
        "consistency": min(25, len(issues.get("inconsistentControlGroups", [])) * 4 + len(issues.get("iconTextImbalance", [])) * 2),
        "hierarchy": min(20, len(issues.get("multiplePrimaryActions", [])) * 2),
        "structure": min(25, int(issues.get("headingSkips", 0)) * 5 + (10 if not raw.get("evidence", {}).get("hasMain") else 0) + (8 if raw.get("evidence", {}).get("h1Count", 0) == 0 else 0)),
    }
    scores = {name: max(0, 100 - value) for name, value in penalties.items()}
    overall = round(sum(scores.values()) / len(scores))
    findings: list[dict[str, Any]] = []
    mapping = [
        ("RENDER-OVERFLOW", "P1", "存在超出视口的可见元素", issues.get("overflowViewport", [])),
        ("RENDER-CLIPPED-CONTENT", "P1", "存在被隐藏溢出裁切的文本内容", issues.get("clipped", [])),
        ("RENDER-LOW-CONTRAST", "P1", "真实渲染文本对比度不足", issues.get("lowContrast", [])),
        ("RENDER-SMALL-TARGET", "P2", "交互目标尺寸偏小", issues.get("smallTargets", [])),
        ("RENDER-TINY-TEXT", "P2", "真实渲染文字小于 12px", issues.get("tinyText", [])),
        ("RENDER-MULTIPLE-PRIMARY-ACTIONS", "P2", "同一页面出现过多高强调主操作", issues.get("multiplePrimaryActions", [])),
    ]
    for rule_id, severity, title, evidence in mapping:
        if evidence:
            findings.append({"id": rule_id, "severity": severity, "title": title, "count": len(evidence), "samples": evidence[:8]})
    findings.extend(_broken_image_findings(issues))
    findings.extend(_text_fragmentation_findings(issues))
    findings.extend(_relational_heuristic_findings(issues))
    findings.extend(_composition_findings({**issues, **raw.get("visualReviewCandidates", {})}))
    if int(issues.get("headingSkips", 0)):
        findings.append({"id": "RENDER-HEADING-ORDER", "severity": "P2", "title": "标题层级存在跳级", "count": int(issues["headingSkips"]), "samples": []})
    if not raw.get("evidence", {}).get("hasMain"):
        findings.append({"id": "RENDER-MAIN-LANDMARK", "severity": "P2", "title": "页面缺少 main 主内容地标", "count": 1, "samples": []})
    findings.extend(keyboard_findings)
    status = "FAIL" if any(item["severity"] == "P1" for item in findings) else "PASS_WITH_WARNINGS" if findings else "PASS"
    return {
        "status": status,
        "overallScore": overall,
        "dimensionScores": scores,
        "findings": findings,
        "compositionClaimBoundary": _COMPOSITION_CLAIM_BOUNDARY,
        "raw": raw,
    }
