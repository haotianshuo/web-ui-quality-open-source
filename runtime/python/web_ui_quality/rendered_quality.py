"""Rendered-page quality checks that complement static source analysis.

These checks intentionally measure observable usability conditions rather than
claiming subjective beauty.  They inspect geometry, target size, text scale,
contrast, clipping, landmarks, and focus affordance in the real browser.
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
  const interactive = [...document.querySelectorAll('button,a[href],input,select,textarea,[role=button],[role=link],[role=checkbox],[role=switch],[tabindex]')].filter(visible);
  const textEls = [...document.querySelectorAll('p,span,label,li,td,th,a,button,h1,h2,h3,h4,h5,h6')].filter(el => visible(el) && el.textContent.trim());
  const all = [...document.querySelectorAll('body *')].filter(visible);
  const smallTargets=[], tinyText=[], lowContrast=[], clipped=[], overflowViewport=[];
  const oversizedControls=[], iconTextImbalance=[], inconsistentControlGroups=[];
  const standaloneControl = (el) => el.tagName !== 'A' || el.getAttribute('role') === 'button' || el.matches('.button,.btn,[class*=button],[class*=btn]');
  for (const el of interactive) {
    const r=el.getBoundingClientRect(), s=getComputedStyle(el), fontSize=parseFloat(s.fontSize||'16');
    const text=(el.getAttribute('aria-label')||el.textContent||el.getAttribute('placeholder')||'').trim();
    if (standaloneControl(el) && (r.width < 44 || r.height < 44) && !['hidden'].includes(el.type)) {
      smallTargets.push({selector:selector(el),width:Math.round(r.width),height:Math.round(r.height)});
    }
    if (standaloneControl(el) && text && r.height >= 64 && fontSize <= 16 && r.height/Math.max(fontSize,1) >= 4) {
      oversizedControls.push({selector:selector(el),height:Math.round(r.height),fontSize:Number(fontSize.toFixed(1)),ratio:Number((r.height/fontSize).toFixed(2)),text:text.slice(0,60)});
    }
    const icon=el.querySelector('svg,img,i,[class*=icon]');
    if (icon && visible(icon) && text) {
      const ir=icon.getBoundingClientRect(), iconSize=Math.max(ir.width,ir.height), ratio=iconSize/Math.max(fontSize,1);
      if (ratio > 1.8 || ratio < .6) iconTextImbalance.push({selector:selector(el),iconPx:Math.round(iconSize),fontSize:Number(fontSize.toFixed(1)),ratio:Number(ratio.toFixed(2)),text:text.slice(0,60)});
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
      inconsistentControlGroups.push({selector:selector(parent),count:controls.length,minHeight:Math.round(minimum),maxHeight:Math.round(maximum),difference:Math.round(maximum-minimum)});
    }
  }
  for (const el of textEls.slice(0,1500)) {
    const s=getComputedStyle(el), size=parseFloat(s.fontSize||'16'), fg=rgb(s.color), bg=background(el);
    if (size < 12) tinyText.push({selector:selector(el),fontSize:size,text:el.textContent.trim().slice(0,80)});
    if (fg && bg) {
      const ratio=contrast(fg,bg); const bold=parseInt(s.fontWeight||'400',10)>=700;
      const threshold=(size>=24 || (size>=18.66 && bold))?3:4.5;
      if (ratio < threshold) lowContrast.push({selector:selector(el),ratio:Number(ratio.toFixed(2)),threshold,fontSize:size});
    }
  }
  for (const el of all.slice(0,3000)) {
    const r=el.getBoundingClientRect(), s=getComputedStyle(el);
    if (r.right > window.innerWidth + 1 || r.left < -1) overflowViewport.push({selector:selector(el),left:Math.round(r.left),right:Math.round(r.right)});
    if ((s.overflowX==='hidden' || s.overflowY==='hidden' || s.overflow==='hidden') && (el.scrollWidth > el.clientWidth + 1 || el.scrollHeight > el.clientHeight + 1) && el.textContent.trim()) clipped.push({selector:selector(el),scrollWidth:el.scrollWidth,clientWidth:el.clientWidth,scrollHeight:el.scrollHeight,clientHeight:el.clientHeight});
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
    issues:{smallTargets:smallTargets.slice(0,60),tinyText:tinyText.slice(0,60),lowContrast:lowContrast.slice(0,80),clipped:clipped.slice(0,60),overflowViewport:overflowViewport.slice(0,60),oversizedControls:oversizedControls.slice(0,40),iconTextImbalance:iconTextImbalance.slice(0,40),inconsistentControlGroups:inconsistentControlGroups.slice(0,40),multiplePrimaryActions:primaryActions.length>2?primaryActions.slice(0,20).map(el=>({selector:selector(el),text:(el.getAttribute('aria-label')||el.textContent||'').trim().slice(0,60)})):[],headingSkips,fixedElements:fixed.slice(0,30)},
    evidence:{url:location.href.split('?')[0],title:document.title,lang:document.documentElement.lang||'',hasMain:!!document.querySelector('main,[role=main]'),h1Count:document.querySelectorAll('h1').length,page:pageMarker,pageEvidence,state:stateMarker,stateEvidence}
  };
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
                "position => { document.activeElement?.blur?.(); window.scrollTo(position.x, position.y); }",
                {"x": baseline.get("scrollX") or 0, "y": baseline.get("scrollY") or 0},
            )
        except Exception:
            pass
    return _summarize_keyboard_audit(baseline, observations, error=traversal_error, steps_expected=steps)


def inspect_rendered_page(page: Any) -> dict[str, Any]:
    raw = page.evaluate(_RENDERED_QUALITY_JS)
    issues = raw.get("issues", {})
    keyboard_audit = inspect_keyboard_navigation(page)
    raw["keyboardAudit"] = keyboard_audit
    keyboard_findings = list(keyboard_audit.get("findings") or [])
    penalties = {
        "layout": min(35, len(issues.get("overflowViewport", [])) * 8 + len(issues.get("clipped", [])) * 4),
        "readability": min(35, len(issues.get("tinyText", [])) * 2 + len(issues.get("lowContrast", [])) * 3),
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
        ("RENDER-OVERSIZED-CONTROL", "P2", "控件高度与标签字号比例明显失衡", issues.get("oversizedControls", [])),
        ("RENDER-INCONSISTENT-CONTROL-HEIGHT", "P2", "同组控件高度混用，界面节奏不一致", issues.get("inconsistentControlGroups", [])),
        ("RENDER-ICON-TEXT-IMBALANCE", "P2", "控件内图标与文字比例异常", issues.get("iconTextImbalance", [])),
        ("RENDER-MULTIPLE-PRIMARY-ACTIONS", "P2", "同一页面出现过多高强调主操作", issues.get("multiplePrimaryActions", [])),
    ]
    for rule_id, severity, title, evidence in mapping:
        if evidence:
            findings.append({"id": rule_id, "severity": severity, "title": title, "count": len(evidence), "samples": evidence[:8]})
    if int(issues.get("headingSkips", 0)):
        findings.append({"id": "RENDER-HEADING-ORDER", "severity": "P2", "title": "标题层级存在跳级", "count": int(issues["headingSkips"]), "samples": []})
    if not raw.get("evidence", {}).get("hasMain"):
        findings.append({"id": "RENDER-MAIN-LANDMARK", "severity": "P2", "title": "页面缺少 main 主内容地标", "count": 1, "samples": []})
    findings.extend(keyboard_findings)
    status = "FAIL" if any(item["severity"] == "P1" for item in findings) else "PASS_WITH_WARNINGS" if findings else "PASS"
    return {"status": status, "overallScore": overall, "dimensionScores": scores, "findings": findings, "raw": raw}
