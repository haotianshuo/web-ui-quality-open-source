"""Read-only whole-site UI asset inventory for real rendered Web projects."""
from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import html
import json
import re
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import urljoin, urlsplit, urlunsplit

from .contracts import ContractViolation
from .design_system_map import build_design_system_map
from .mutation_firewall import BrowserMutationFirewall, origin
from .release_info import PACKAGE_VERSION
from .browser_locator import resolve_browser_executable
from .secure_browser_context import build_credential_map, create_secure_context, split_headers
from .browser_request_policy import navigation_route_key

_EXCLUDED = {"node_modules", ".git", "dist", "build", ".next", ".nuxt", "coverage", "artifacts", "__pycache__"}
_SOURCE_EXTS = {".js", ".jsx", ".ts", ".tsx", ".vue", ".svelte", ".html", ".htm"}
_STATIC_EXTS = {".css", ".js", ".mjs", ".cjs", ".map", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico", ".woff", ".woff2", ".ttf", ".otf", ".pdf", ".zip", ".json", ".xml", ".txt"}
_ROUTE_PATTERNS = (
    re.compile(r"(?:path|route|href)\s*[:=]\s*[\"'](/[^\"'#?]*)[\"']", re.I),
    re.compile(r"<Route\b[^>]*\bpath\s*=\s*[\"'](/[^\"'#?]*)[\"']", re.I),
    re.compile(r"(?:router\.(?:push|replace)|navigate)\(\s*[\"'](/[^\"'#?]*)[\"']", re.I),
)
_DYNAMIC = re.compile(r"^(?:\[\[?\.\.\.[^\]]+\]\]?|\[[^\]]+\]|:[A-Za-z_][\w-]*)$")
_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$", re.I)
_ID = re.compile(r"^(?:\d+|[0-9a-f]{12,})$", re.I)
_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")

_INVENTORY_JS = r"""
(mode) => {
  const maxAll = mode === 'quick' ? 1800 : 3500;
  const maxComponents = mode === 'quick' ? 500 : 900;
  const px=v=>{const n=parseFloat(v||''); return Number.isFinite(n)?+n.toFixed(2):null};
  const compact=v=>String(v||'').trim().replace(/\s+/g,' ').slice(0,180);
  const visible=el=>{const s=getComputedStyle(el),r=el.getBoundingClientRect();return s.display!=='none'&&s.visibility!=='hidden'&&Number(s.opacity||1)>0&&r.width>0&&r.height>0};
  const selector=el=>{if(el.id)return '#'+CSS.escape(el.id);const t=el.getAttribute('data-testid');if(t)return '[data-testid="'+CSS.escape(t)+'"]';const n=el.getAttribute('name');if(n)return el.tagName.toLowerCase()+'[name="'+CSS.escape(n)+'"]';return el.tagName.toLowerCase()+[...el.classList].slice(0,2).map(x=>'.'+CSS.escape(x)).join('')};
  const bounds=el=>{const r=el.getBoundingClientRect();return{x:+r.x.toFixed(1),y:+r.y.toFixed(1),width:+r.width.toFixed(1),height:+r.height.toFixed(1)}};
  const styleOf=el=>{const s=getComputedStyle(el);return{
    width:px(s.width),height:px(s.height),paddingTop:px(s.paddingTop),paddingRight:px(s.paddingRight),paddingBottom:px(s.paddingBottom),paddingLeft:px(s.paddingLeft),
    marginTop:px(s.marginTop),marginRight:px(s.marginRight),marginBottom:px(s.marginBottom),marginLeft:px(s.marginLeft),gap:px(s.gap),rowGap:px(s.rowGap),columnGap:px(s.columnGap),
    fontFamily:compact(s.fontFamily),fontSize:px(s.fontSize),fontWeight:compact(s.fontWeight),lineHeight:px(s.lineHeight),letterSpacing:px(s.letterSpacing),
    color:s.color,backgroundColor:s.backgroundColor,borderTopColor:s.borderTopColor,borderTopWidth:px(s.borderTopWidth),borderTopLeftRadius:px(s.borderTopLeftRadius),
    borderTopRightRadius:px(s.borderTopRightRadius),borderBottomRightRadius:px(s.borderBottomRightRadius),borderBottomLeftRadius:px(s.borderBottomLeftRadius),
    boxShadow:compact(s.boxShadow),opacity:+Number(s.opacity||1).toFixed(3),fill:s.fill,stroke:s.stroke,display:s.display,position:s.position}};
  const base=el=>({selector:selector(el),tag:el.tagName.toLowerCase(),role:el.getAttribute('role')||null,text:compact(el.getAttribute('aria-label')||el.getAttribute('title')||el.textContent||''),disabled:el.matches(':disabled')||el.getAttribute('aria-disabled')==='true',bounds:bounds(el),style:styleOf(el)});
  const all=[...document.querySelectorAll('body *')].filter(visible).slice(0,maxAll);
  const buttonLike=el=>el.matches('button,input[type=button],input[type=submit],input[type=reset],[role=button]')||(el.matches('a[href]')&&/btn|button|primary|secondary|danger|action/i.test(el.className||''));
  const inputLike=el=>el.matches('input:not([type=button]):not([type=submit]):not([type=reset]),textarea,select,[role=combobox]');
  const dialogLike=el=>el.matches('dialog,[role=dialog],[aria-modal=true]')||/(?:^|\s)(?:modal|drawer)(?:\s|$)/i.test(el.className||'');
  const tableLike=el=>el.matches('table,[role=grid]')||/(?:^|\s)(?:table|data-table)(?:\s|$)/i.test(el.className||'');
  const cardLike=el=>/(?:^|\s)(?:card|panel|tile)(?:\s|$)/i.test(el.className||'')||el.getAttribute('data-component')==='card';
  const iconLike=el=>el.matches('svg,i,[role=img]')&&el.getBoundingClientRect().width<=96&&el.getBoundingClientRect().height<=96;
  const typographyRole=el=>buttonLike(el)||inputLike(el)?'control':el.matches('label')?'control-label':/^H[1-6]$/.test(el.tagName)?'heading':el.matches('small,caption,figcaption')?'supporting':'body';
  const list=fn=>all.filter(fn).slice(0,maxComponents).map(base);
  const colors=[],typography=[],radius=[],spacing=[];
  for(const el of all){const s=getComputedStyle(el);colors.push(s.color,s.backgroundColor);if(px(s.borderTopWidth)>0)colors.push(s.borderTopColor);if(px(s.borderRightWidth)>0)colors.push(s.borderRightColor);if(px(s.borderBottomWidth)>0)colors.push(s.borderBottomColor);if(px(s.borderLeftWidth)>0)colors.push(s.borderLeftColor);if(s.fill&&s.fill!=='none')colors.push(s.fill);if(s.stroke&&s.stroke!=='none')colors.push(s.stroke);
    const fs=px(s.fontSize);if(fs!==null)typography.push({fontFamily:compact(s.fontFamily),fontSize:fs,fontWeight:compact(s.fontWeight),lineHeight:px(s.lineHeight),letterSpacing:px(s.letterSpacing),tag:el.tagName.toLowerCase(),semanticRole:typographyRole(el)});
    for(const v of [s.borderTopLeftRadius,s.borderTopRightRadius,s.borderBottomRightRadius,s.borderBottomLeftRadius]){const n=px(v);if(n!==null&&n>0)radius.push(n)}
    for(const v of [s.paddingTop,s.paddingRight,s.paddingBottom,s.paddingLeft,s.marginTop,s.marginRight,s.marginBottom,s.marginLeft,s.gap,s.rowGap,s.columnGap]){const n=px(v);if(n!==null&&n>0)spacing.push(n)}
  }
  const body=compact(document.body?.innerText||'');
  return {title:document.title||'',url:location.href.split('#')[0],links:[...document.querySelectorAll('a[href]')].map(a=>a.href).filter(Boolean).slice(0,500),
    authHint:Boolean(document.querySelector('input[type=password]'))||/登录|登陆|sign\s*in|log\s*in|验证码|verification code/i.test(body.slice(0,1200)),permissionHint:/无权限|没有权限|permission denied|access denied|forbidden|not authorized/i.test(body.slice(0,1500)),
    buttons:list(buttonLike),inputs:mode==='quick'?[]:list(inputLike),cards:mode==='quick'?[]:list(cardLike),dialogs:mode==='quick'?[]:list(dialogLike),tables:mode==='quick'?[]:list(tableLike),icons:mode==='quick'?[]:list(iconLike),colors,typography,radius,spacing};
}
"""

_STYLE_KEYS = {
    "button": ("height", "paddingTop", "paddingRight", "paddingBottom", "paddingLeft", "fontSize", "fontWeight", "color", "backgroundColor", "borderTopColor", "borderTopWidth", "borderTopLeftRadius", "boxShadow", "opacity"),
    "input": ("height", "paddingTop", "paddingRight", "paddingBottom", "paddingLeft", "fontSize", "color", "backgroundColor", "borderTopColor", "borderTopWidth", "borderTopLeftRadius", "boxShadow"),
    "card": ("backgroundColor", "borderTopColor", "borderTopWidth", "borderTopLeftRadius", "boxShadow", "paddingTop", "paddingRight", "paddingBottom", "paddingLeft"),
    "dialog": ("width", "backgroundColor", "borderTopLeftRadius", "boxShadow", "paddingTop", "paddingRight", "paddingBottom", "paddingLeft"),
    "table": ("fontSize", "color", "backgroundColor", "borderTopColor", "borderTopWidth"),
    "icon": ("width", "height", "color", "fill", "stroke"),
}


def _normalize_route(raw: str) -> str | None:
    value = str(raw or "").strip().split("?", 1)[0].split("#", 1)[0]
    if not value.startswith("/") or value.startswith("//"):
        return None
    value = re.sub(r"/+", "/", value).rstrip("/") or "/"
    if value == "/api" or value.startswith("/api/") or Path(value).suffix.casefold() in _STATIC_EXTS or len(value) > 180:
        return None
    return value


def _stable_local_url(raw: str) -> str:
    """Remove ephemeral loopback ports from persisted evidence URLs only."""
    value = str(raw)
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        return value
    if parsed.scheme.casefold() not in {"http", "https"} or parsed.hostname not in {"127.0.0.1", "localhost", "::1"} or port is None:
        return value
    host = parsed.hostname
    if ":" in host:
        host = f"[{host}]"
    return urlunsplit((parsed.scheme, host, parsed.path, parsed.query, parsed.fragment))


def _stabilize_report_urls(value: Any) -> Any:
    """Make local browser evidence deterministic without changing runtime observations."""
    if isinstance(value, Mapping):
        return {key: _stabilize_report_urls(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_stabilize_report_urls(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_stabilize_report_urls(item) for item in value)
    if isinstance(value, str):
        return _stable_local_url(value)
    return value


def _route_template(path: str) -> str:
    normalized = _normalize_route(path) or "/"
    parts = []
    for part in normalized.strip("/").split("/") if normalized != "/" else []:
        parts.append(":param" if _DYNAMIC.match(part) else ":id" if _UUID.match(part) or _ID.match(part) else part)
    return "/" + "/".join(parts) if parts else "/"


def discover_source_routes(project_root: str | Path | None, *, limit: int = 120) -> list[dict[str, Any]]:
    if project_root is None:
        return []
    root = Path(project_root).expanduser().resolve()
    if not root.is_dir():
        return []
    found: dict[str, dict[str, Any]] = {}
    inspected = 0
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.casefold() not in _SOURCE_EXTS:
            continue
        rel = path.relative_to(root)
        if any(part in _EXCLUDED for part in rel.parts):
            continue
        inspected += 1
        if inspected > 1200:
            break
        text = path.read_text(encoding="utf-8", errors="ignore")
        candidates: list[tuple[str, int]] = []
        for pattern in _ROUTE_PATTERNS:
            candidates.extend((m.group(1), text[:m.start(1)].count("\n") + 1) for m in pattern.finditer(text))
        parts = rel.parts
        if "pages" in parts and path.stem not in {"_app", "_document", "_error"}:
            idx = parts.index("pages"); items = list(parts[idx + 1:]); items[-1] = Path(items[-1]).stem
            if items and items[-1] == "index": items = items[:-1]
            candidates.append(("/" + "/".join(items), 1))
        if "app" in parts and path.stem == "page":
            idx = parts.index("app"); items = [x for x in parts[idx + 1:-1] if not (x.startswith("(") and x.endswith(")"))]
            candidates.append(("/" + "/".join(items), 1))
        for route, line in candidates:
            route = _normalize_route(route)
            if route is None: continue
            row = found.setdefault(route, {"path": route, "template": _route_template(route), "sourceEvidence": []})
            if len(row["sourceEvidence"]) < 4: row["sourceEvidence"].append({"file": rel.as_posix(), "line": line})
            if len(found) >= limit: break
        if len(found) >= limit: break
    return [found[k] for k in sorted(found)]


def _rgba_hex(raw: str) -> str | None:
    value = str(raw or "").strip().lower()
    if not value or value in {"transparent", "none", "rgba(0, 0, 0, 0)", "rgba(0,0,0,0)"}: return None
    if re.fullmatch(r"#[0-9a-f]{6}(?:[0-9a-f]{2})?", value): return value.upper()
    m = re.fullmatch(r"rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)(?:\s*,\s*([\d.]+))?\s*\)", value)
    if not m: return None
    rgb = [max(0, min(255, round(float(m.group(i))))) for i in range(1, 4)]; a = float(m.group(4)) if m.group(4) else 1.0
    if a <= 0: return None
    return f"#{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}" if a >= .999 else f"#{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}{round(a*255):02X}"


def _rgb(value: str) -> tuple[int, int, int] | None:
    return tuple(int(value[i:i+2], 16) for i in (1, 3, 5)) if re.fullmatch(r"#[0-9A-F]{6}(?:[0-9A-F]{2})?", value) else None  # type: ignore[return-value]


def _color_distance(a: str, b: str) -> float:
    x, y = _rgb(a), _rgb(b)
    return sum((m-n)**2 for m,n in zip(x,y))**.5 if x and y else 999.0


def _component_style(item: Mapping[str, Any], kind: str) -> dict[str, Any]:
    style = item.get("style") if isinstance(item.get("style"), Mapping) else {}
    return {key: style.get(key) for key in _STYLE_KEYS[kind]}


def _fingerprint(item: Mapping[str, Any], kind: str) -> str:
    return hashlib.sha256(json.dumps(_component_style(item, kind), sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]


def _styles_near(a: Mapping[str, Any], b: Mapping[str, Any], kind: str) -> bool:
    left, right = _component_style(a, kind), _component_style(b, kind)
    colors = {"color", "backgroundColor", "borderTopColor", "fill", "stroke"}
    tol = {"height": 2, "width": 2, "fontSize": 1, "borderTopLeftRadius": 2, "paddingTop": 2, "paddingRight": 2, "paddingBottom": 2, "paddingLeft": 2, "borderTopWidth": .5, "opacity": .05}
    changed = 0
    for key, av in left.items():
        bv = right.get(key)
        if av == bv: continue
        if key in colors:
            ah, bh = _rgba_hex(str(av)), _rgba_hex(str(bv))
            if ah and bh and _color_distance(ah, bh) <= 12: changed += 1; continue
            return False
        if key in tol and isinstance(av, (int, float)) and isinstance(bv, (int, float)) and abs(float(av)-float(bv)) <= tol[key]: changed += 1; continue
        return False
    return 1 <= changed <= 5


def _similar_clusters(reps: Mapping[str, Mapping[str, Any]], counts: Counter[str], kind: str) -> list[dict[str, Any]]:
    keys = list(reps)[:80]; parent = {k:k for k in keys}
    def find(x: str) -> str:
        while parent[x] != x: parent[x] = parent[parent[x]]; x = parent[x]
        return x
    def union(a: str,b: str) -> None:
        a,b=find(a),find(b)
        if a!=b: parent[b]=a
    for i,a in enumerate(keys):
        for b in keys[i+1:]:
            if _styles_near(reps[a], reps[b], kind): union(a,b)
    groups: dict[str,list[str]] = defaultdict(list)
    for k in keys: groups[find(k)].append(k)
    rows=[]
    for vals in groups.values():
        if len(vals)<2: continue
        vals.sort(key=lambda f:(-counts[f],f)); rows.append({"fingerprints":vals,"styleCount":len(vals),"occurrences":sum(counts[v] for v in vals),"suggestedReference":vals[0]})
    return sorted(rows,key=lambda r:(-r["occurrences"],-r["styleCount"]))


def _near_colors(counter: Counter[str]) -> list[dict[str, Any]]:
    keys=[k for k in counter if _rgb(k)]; parent={k:k for k in keys}
    def find(x):
        while parent[x]!=x: parent[x]=parent[parent[x]]; x=parent[x]
        return x
    for i,a in enumerate(keys):
        for b in keys[i+1:]:
            if _color_distance(a,b)<=12:
                ra,rb=find(a),find(b)
                if ra!=rb: parent[rb]=ra
    groups:dict[str,list[str]]=defaultdict(list)
    for k in keys:groups[find(k)].append(k)
    rows=[]
    for vals in groups.values():
        if len(vals)<2:continue
        vals.sort(key=lambda v:(-counter[v],v));rows.append({"colors":[{"value":v,"count":counter[v]} for v in vals],"suggestedReference":vals[0]})
    return sorted(rows,key=lambda r:-sum(x["count"] for x in r["colors"]))


def _canon_text(raw: str) -> str:
    value=re.sub(r"\s+","",str(raw or "").casefold()); aliases={"创建":"新建","新增":"新建","添加":"新建","确认":"确定","提交保存":"保存"}
    return aliases.get(value,value)[:80]


def aggregate_inventory(pages: Sequence[Mapping[str, Any]], *, mode: str) -> dict[str, Any]:
    scanned=[p for p in pages if p.get("status")=="scanned"]
    colors:Counter[str]=Counter(); radii:Counter[float]=Counter(); spacing:Counter[float]=Counter(); sizes:Counter[float]=Counter(); weights:Counter[str]=Counter(); families:Counter[str]=Counter()
    components:dict[str,list[dict[str,Any]]]={k:[] for k in ("button","input","card","dialog","table","icon")}; fields={"button":"buttons","input":"inputs","card":"cards","dialog":"dialogs","table":"tables","icon":"icons"}
    for page in scanned:
        colors.update(x for x in (_rgba_hex(str(v)) for v in page.get("colors",[]) or []) if x); radii.update(page.get("radius",[]) or []); spacing.update(page.get("spacing",[]) or [])
        for t in page.get("typography",[]) or []:
            if isinstance(t,Mapping):
                if t.get("fontSize") is not None:sizes[t["fontSize"]]+=1
                if t.get("fontWeight"):weights[str(t["fontWeight"])]+=1
                if t.get("fontFamily"):families[str(t["fontFamily"])]+=1
        for kind,field in fields.items():
            for raw in page.get(field,[]) or []:
                if not isinstance(raw,Mapping):continue
                item=dict(raw);item["page"]=page.get("path");item["url"]=page.get("url");item["fingerprint"]=_fingerprint(item,kind);components[kind].append(item)
    summaries={}
    for kind,items in components.items():
        counts=Counter(str(x["fingerprint"]) for x in items); reps={}; pages_by=defaultdict(set)
        for x in items: reps.setdefault(str(x["fingerprint"]),x); pages_by[str(x["fingerprint"])].add(str(x.get("page") or ""))
        summaries[kind]={"count":len(items),"styleCount":len(counts),"similarStyleClusters":_similar_clusters(reps,counts,kind),"styles":[{"fingerprint":fp,"count":count,"pageCount":len(pages_by[fp]),"representative":{"page":reps[fp].get("page"),"selector":reps[fp].get("selector"),"text":reps[fp].get("text"),"style":reps[fp].get("style")}} for fp,count in counts.most_common(80)]}
    groups=defaultdict(list)
    for item in components["button"]:
        key=_canon_text(str(item.get("text") or ""))
        if key:groups[key].append(item)
    drift=[]
    for key,items in groups.items():
        fps={str(x["fingerprint"]) for x in items}; pageset=sorted({str(x.get("page")) for x in items if x.get("page")})
        if len(fps)<2 or len(pageset)<2:continue
        drift.append({"id":"button-purpose:"+hashlib.sha256(key.encode()).hexdigest()[:10],"type":"BUTTON_PURPOSE_DRIFT","severity":"High" if len(pageset)>=4 else "Medium","label":f"“{key}”按钮存在 {len(fps)} 套样式","purpose":key,"pageCount":len(pageset),"pages":pageset[:30],"styleCount":len(fps),"occurrences":len(items),"evidence":[{"page":x.get("page"),"selector":x.get("selector"),"fingerprint":x.get("fingerprint"),"style":x.get("style")} for x in items[:20]]})
    common={v for v,c in radii.items() if c>=10}; outliers=[]
    for v,c in radii.items():
        if c<=3 and common:
            near=min(common,key=lambda x:abs(float(x)-float(v)))
            if abs(float(near)-float(v))<=2 and near!=v:outliers.append({"value":v,"count":c,"near":near})
    role_sizes:dict[str,Counter[float]]=defaultdict(Counter)
    for page in scanned:
        for t in page.get("typography",[]) or []:
            if not isinstance(t,Mapping) or t.get("fontSize") is None:continue
            role_sizes[str(t.get("semanticRole") or "unknown")][t["fontSize"]]+=1
    fragments=[]
    for role in sorted(role_sizes):
        scoped=role_sizes[role]; sv=sorted(float(v) for v in scoped)
        for a,b in zip(sv,sv[1:]):
            if 0<b-a<=2 and scoped[a]>=3 and scoped[b]>=3:
                fragments.append({"semanticRole":role,"values":[a,b],"counts":[scoped[a],scoped[b]]})
    cross_role_pairs=[]
    role_by_size:dict[float,set[str]]=defaultdict(set)
    for role,scoped in role_sizes.items():
        for value in scoped:role_by_size[float(value)].add(role)
    for a,b in zip(sorted(role_by_size),sorted(role_by_size)[1:]):
        if 0<b-a<=2 and role_by_size[a]!=role_by_size[b]:
            cross_role_pairs.append({"values":[a,b],"roles":sorted(role_by_size[a]|role_by_size[b]),"roleCounts":[{"semanticRole":role,"counts":[role_sizes[role].get(a,0),role_sizes[role].get(b,0)]} for role in sorted(role_by_size[a]|role_by_size[b])]})
    profiles=[]
    for page in scanned:
        pc=Counter(x for x in (_rgba_hex(str(v)) for v in page.get("colors",[]) or []) if x); pr=Counter(page.get("radius",[]) or []); pf=Counter(t.get("fontSize") for t in page.get("typography",[]) or [] if isinstance(t,Mapping) and t.get("fontSize") is not None); ps=Counter(page.get("spacing",[]) or [])
        profiles.append({"path":page.get("path"),"url":page.get("url"),"dominantColor":pc.most_common(1)[0][0] if pc else None,"dominantRadius":pr.most_common(1)[0][0] if pr else None,"dominantFontSize":pf.most_common(1)[0][0] if pf else None,"dominantSpacing":ps.most_common(1)[0][0] if ps else None,"buttonStyles":len({x["fingerprint"] for x in components["button"] if x.get("page")==page.get("path")})})
    return {"mode":mode,"components":summaries,"colors":{"count":len(colors),"values":[{"value":v,"count":c} for v,c in colors.most_common(120)],"potentialDuplicates":_near_colors(colors)},"typography":{"fontSizeCount":len(sizes),"fontSizes":[{"value":v,"count":c} for v,c in sizes.most_common()],"fontWeights":[{"value":v,"count":c} for v,c in weights.most_common(30)],"fontFamilies":[{"value":v,"count":c} for v,c in families.most_common(30)],"semanticRoleCounts":{role:{"fontSizes":[{"value":v,"count":c} for v,c in role_sizes[role].most_common()]} for role in sorted(role_sizes)},"fragmentationCandidates":fragments[:40],"crossRoleTierPairs":cross_role_pairs[:40]},"radius":{"count":len(radii),"values":[{"value":v,"count":c} for v,c in radii.most_common(100)],"possibleOutliers":sorted(outliers,key=lambda r:(r["count"],float(r["value"])))[:40]},"spacing":{"count":len(spacing),"values":[{"value":v,"count":c} for v,c in spacing.most_common(100)]},"driftCandidates":sorted(drift,key=lambda r:({"High":0,"Medium":1,"Low":2}.get(r["severity"],3),-r["pageCount"]))[:100],"pageProfiles":profiles}


def _design_map(project_root: str | Path | None) -> dict[str, Any] | None:
    if project_root is None:return None
    root=Path(project_root).expanduser().resolve(); sources=[]
    if not root.is_dir():return None
    for path in sorted(root.rglob("*.css")):
        rel=path.relative_to(root)
        if any(part in _EXCLUDED for part in rel.parts):continue
        sources.append({"path":rel.as_posix(),"text":path.read_text(encoding="utf-8",errors="ignore")[:500000]})
        if len(sources)>=200:break
    return build_design_system_map(sources) if sources else None


def _token_compare(inv: Mapping[str, Any], dm: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not dm:return None
    raw=dm.get("inventory") if isinstance(dm.get("inventory"),Mapping) else {}; dc=set()
    for row in raw.get("colors",[]) or []:
        if isinstance(row,Mapping):
            c=_rgba_hex(str(row.get("value") or "")); dc.add(c) if c else None
    for val in (raw.get("variables",{}) if isinstance(raw.get("variables"),Mapping) else {}).values():
        c=_rgba_hex(str(val)); dc.add(c) if c else None
    oc={str(x.get("value")) for x in inv.get("colors",{}).get("values",[]) if isinstance(x,Mapping)}; dr=set()
    for row in raw.get("radii",[]) or []:
        if isinstance(row,Mapping):
            m=re.fullmatch(r"\s*([\d.]+)px\s*",str(row.get("value") or ""),re.I)
            if m:dr.add(float(m.group(1)))
    orad={float(x.get("value")) for x in inv.get("radius",{}).get("values",[]) if isinstance(x,Mapping) and isinstance(x.get("value"),(int,float))}
    return {"cssFiles":dm.get("cssFiles",0),"cssVariableCount":dm.get("cssVariableCount",0),"definedColors":sorted(dc),"observedColorsOutsideDefinedSet":sorted(oc-dc)[:80],"uniqueColorCoveragePercent":round(len(oc&dc)/max(1,len(oc))*100,1),"definedRadiusPx":sorted(dr),"observedRadiusOutsideDefinedSetPx":sorted(orad-dr)[:60],"uniqueRadiusCoveragePercent":round(len(orad&dr)/max(1,len(orad))*100,1),"existingDesignSystemMetrics":dm.get("metrics",{}),"claimBoundary":"Literal CSS token-like definitions vs rendered computed values; semantic token ownership is not proven."}


def _issues(inv: Mapping[str, Any], tc: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    rows=[]
    for d in inv.get("driftCandidates",[]) or []:
        if isinstance(d,Mapping):rows.append({"severity":d.get("severity","Medium"),"type":d.get("type"),"label":d.get("label"),"impact":f"{d.get('pageCount',0)} pages","evidenceRef":d.get("id")})
    comps=inv.get("components",{}) if isinstance(inv.get("components"),Mapping) else {}
    for kind,label,threshold in (("button","Button",6),("input","Input",5),("card","Card",8)):
        data=comps.get(kind,{}) if isinstance(comps.get(kind),Mapping) else {}; count=int(data.get("count") or 0); styles=int(data.get("styleCount") or 0)
        if count>=threshold and styles>=threshold:rows.append({"severity":"High" if kind=="button" and styles>=10 else "Medium","type":"STYLE_FRAGMENTATION","label":f"{label} 存在 {styles} 套真实样式","impact":f"{count} occurrences","evidenceRef":kind})
    dup=inv.get("colors",{}).get("potentialDuplicates",[]) if isinstance(inv.get("colors"),Mapping) else []
    if dup: rows.append({"severity":"Medium","type":"POTENTIAL_DUPLICATE_COLORS","label":f"发现 {len(dup)} 组近似颜色","impact":"computed styles","evidenceRef":"colors.potentialDuplicates"})
    out=inv.get("radius",{}).get("possibleOutliers",[]) if isinstance(inv.get("radius"),Mapping) else []
    if out:rows.append({"severity":"Medium" if len(out)>=4 else "Low","type":"RADIUS_OUTLIERS","label":f"发现 {len(out)} 个低频近似圆角候选","impact":f"{inv.get('radius',{}).get('count',0)} radius values","evidenceRef":"radius.possibleOutliers"})
    fr=inv.get("typography",{}).get("fragmentationCandidates",[]) if isinstance(inv.get("typography"),Mapping) else []
    if fr:rows.append({"severity":"Medium" if len(fr)>=3 else "Low","type":"TYPOGRAPHY_FRAGMENTATION","label":f"发现 {len(fr)} 组相邻字号碎片","impact":f"{inv.get('typography',{}).get('fontSizeCount',0)} font sizes","evidenceRef":"typography.fragmentationCandidates"})
    if tc and int(tc.get("cssVariableCount") or 0)>0 and tc.get("observedColorsOutsideDefinedSet"):rows.append({"severity":"Medium","type":"TOKEN_BYPASS_CANDIDATE","label":f"已有 CSS 变量，但 {len(tc['observedColorsOutsideDefinedSet'])} 个渲染颜色不在提取定义集合中","impact":f"color coverage {tc.get('uniqueColorCoveragePercent',0)}%","evidenceRef":"tokenComparison"})
    return sorted(rows,key=lambda r:({"High":0,"Medium":1,"Low":2}.get(str(r.get("severity")),3),str(r.get("type"))))[:100]


def _summary(report: Mapping[str, Any]) -> dict[str, Any]:
    st=report.get("stats",{}); inv=report.get("inventory",{}); c=inv.get("components",{}) if isinstance(inv,Mapping) else {}
    return {"pagesDiscovered":st.get("pagesDiscovered",0),"pagesScanned":st.get("pagesScanned",0),"pagesFailed":st.get("pagesFailed",0),"buttons":c.get("button",{}).get("count",0),"buttonStyles":c.get("button",{}).get("styleCount",0),"colors":inv.get("colors",{}).get("count",0),"potentialDuplicateColorGroups":len(inv.get("colors",{}).get("potentialDuplicates",[])),"fontSizes":inv.get("typography",{}).get("fontSizeCount",0),"radiusValues":inv.get("radius",{}).get("count",0),"uiDriftCandidates":len(inv.get("driftCandidates",[])),"highPriorityIssues":sum(1 for x in report.get("topIssues",[]) if isinstance(x,Mapping) and x.get("severity")=="High")}


def _render_html(report: Mapping[str, Any]) -> str:
    esc=lambda v:html.escape(str(v)); s=_summary(report); inv=report.get("inventory",{}); comps=inv.get("components",{}); issues=report.get("topIssues",[]); pages=report.get("pages",[])
    cr="".join(f"<tr><td>{esc(k.title())}</td><td>{esc(v.get('count',0))}</td><td>{esc(v.get('styleCount',0))}</td></tr>" for k,v in comps.items() if isinstance(v,Mapping))
    ir="".join(f"<tr><td>{esc(x.get('severity'))}</td><td>{esc(x.get('label'))}</td><td>{esc(x.get('impact'))}</td><td>{esc(x.get('type'))}</td></tr>" for x in issues[:30]) or "<tr><td colspan='4'>未发现达到阈值的 UI 一致性问题。</td></tr>"
    pr="".join(f"<tr><td>{esc(x.get('path'))}</td><td>{esc(x.get('status'))}</td><td>{esc(x.get('httpStatus') or '')}</td><td>{esc(x.get('reason') or '')}</td></tr>" for x in pages[:200])
    return f"""<!doctype html><html lang='zh-CN'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>UI Asset Inventory</title><style>body{{font-family:system-ui;margin:0;background:#f6f7f9;color:#171717}}main{{max-width:1180px;margin:auto;padding:32px}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px}}.card{{background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:18px}}.n{{font-size:28px;font-weight:700}}table{{width:100%;border-collapse:collapse;background:#fff}}th,td{{padding:10px;border-bottom:1px solid #eee;text-align:left;vertical-align:top}}h2{{margin-top:30px}}.notice{{background:#fff;border-left:4px solid #555;padding:12px 16px;margin:16px 0}}</style><main><h1>UI Asset Inventory</h1><p>Web UI Quality {esc(PACKAGE_VERSION)} · READ ONLY · {esc(report.get('mode'))}</p><div class='notice'>不同不等于错误。所有 Drift / Outlier 仅是复核候选，本报告不会修改项目。</div><div class='grid'>{''.join(f"<div class='card'><div class='n'>{esc(v)}</div><div>{label}</div></div>" for label,v in [('扫描页面',s['pagesScanned']),('按钮',s['buttons']),('按钮样式',s['buttonStyles']),('颜色',s['colors']),('字号',s['fontSizes']),('圆角',s['radiusValues']),('UI Drift',s['uiDriftCandidates'])])}</div><h2>组件资产</h2><table><tr><th>类型</th><th>数量</th><th>样式数</th></tr>{cr}</table><h2>问题排名</h2><table><tr><th>等级</th><th>问题</th><th>影响</th><th>类型</th></tr>{ir}</table><h2>页面覆盖</h2><table><tr><th>Route</th><th>状态</th><th>HTTP</th><th>原因</th></tr>{pr}</table></main></html>"""


def _ctx(viewport: tuple[int,int], locale: str, theme: str, storage_state: Any, headers: Mapping[str,str] | None, ignore_https_errors: bool) -> dict[str,Any]:
    w,h=viewport; opts={"viewport":{"width":w,"height":h},"device_scale_factor":2 if w<=480 else 1.5 if w<=900 else 1,"locale":locale,"color_scheme":theme,"reduced_motion":"reduce","service_workers":"block","accept_downloads":False,"ignore_https_errors":ignore_https_errors}
    if w<=480:opts.update({"is_mobile":True,"has_touch":True})
    elif w<=900:opts["has_touch"]=True
    if storage_state is not None:opts["storage_state"]=str(storage_state) if isinstance(storage_state,Path) else storage_state
    if headers: opts["extra_http_headers"]={str(k):str(v) for k,v in headers.items()}
    return opts


def _launch(runtime: Any, name: str, browser_executable: str | Path | None = None) -> Any:
    bt=getattr(runtime,name,None)
    if bt is None:raise ContractViolation("BROWSER_ENGINE_INVALID",[f"$.browser: unsupported {name}"])
    decision=resolve_browser_executable(name,explicit=browser_executable)
    if not decision.get("available") and browser_executable is None:
        decision=resolve_browser_executable(name,playwright_browser_type=bt)
    if not decision.get("available"):
        raise ContractViolation("BROWSER_EXECUTABLE_UNAVAILABLE",[decision.get("reason") or "No usable browser executable was discovered."])
    return bt.launch(headless=True,executable_path=decision["executable"])


def _same_origin_link(raw: str, start: str) -> str | None:
    try:absolute=urljoin(start,raw); p=urlsplit(absolute); b=urlsplit(start)
    except ValueError:return None
    if p.scheme not in {"http","https"} or p.hostname!=b.hostname or (p.port or (443 if p.scheme=="https" else 80))!=(b.port or (443 if b.scheme=="https" else 80)):return None
    path=_normalize_route(p.path or "/")
    return urlunsplit((p.scheme,p.netloc,path,"","")) if path else None


def _scan_page(page: Any, url: str, path: str, mode: str, shots: Path, timeout_ms: int) -> dict[str,Any]:
    try:
        response=page.goto(url,wait_until="domcontentloaded",timeout=timeout_ms)
        try:page.evaluate("document.fonts && document.fonts.ready ? document.fonts.ready : Promise.resolve()")
        except Exception:pass
        page.wait_for_timeout(250); data=page.evaluate(_INVENTORY_JS,mode); status_code=response.status if response else None
        if status_code==401 or data.get("authHint"):status,reason="auth_required","authentication wall detected"
        elif status_code==403 or data.get("permissionHint"):status,reason="permission_denied","permission wall detected"
        elif status_code and status_code>=500:status,reason="broken",f"HTTP {status_code}"
        elif status_code and status_code>=400:status,reason="failed",f"HTTP {status_code}"
        else:status,reason="scanned",None
        shot_ref=shot_sha=None
        if status=="scanned":
            safe=_SAFE_NAME.sub("-",path.strip("/") or "home")[:80]+"-"+hashlib.sha256(path.encode()).hexdigest()[:6]; shot=shots/f"{safe}-desktop.png"; page.screenshot(path=str(shot),full_page=True,animations="disabled"); shot_ref=shot.name; shot_sha=hashlib.sha256(shot.read_bytes()).hexdigest()
        return {"path":path,"url":page.url.split("?",1)[0],"status":status,"reason":reason,"httpStatus":status_code,"title":data.get("title"),"links":data.get("links",[]),"screenshotRef":shot_ref,"screenshotSha256":shot_sha,"buttons":data.get("buttons",[]),"inputs":data.get("inputs",[]),"cards":data.get("cards",[]),"dialogs":data.get("dialogs",[]),"tables":data.get("tables",[]),"icons":data.get("icons",[]),"colors":data.get("colors",[]),"typography":data.get("typography",[]),"radius":data.get("radius",[]),"spacing":data.get("spacing",[])}
    except Exception as e:return {"path":path,"url":url,"status":"failed","reason":f"{type(e).__name__}: {str(e)[:400]}","links":[]}


def run_ui_inventory(start_url: str | None, *, output_dir: str | Path, project_root: str | Path | None = None, routes: Sequence[str] | None = None, mode: str = "full", max_pages: int = 100, viewport: Sequence[int] = (1440,900), locale: str = "zh-CN", theme: str = "light", browser_name: str = "chromium", allow_origins: Iterable[str] = (), timeout_ms: int = 15000, storage_state: str | Path | Mapping[str,Any] | None = None, extra_http_headers: Mapping[str,str] | None = None, ignore_https_errors: bool = False, browser_executable: str | Path | None = None) -> dict[str,Any]:
    if mode not in {"quick","full"}:raise ContractViolation("UI_INVENTORY_MODE_INVALID",["$.mode: quick or full"])
    if not 1<=max_pages<=500:raise ContractViolation("UI_INVENTORY_PAGE_LIMIT_INVALID",["$.maxPages: 1..500"])
    w,h=int(viewport[0]),int(viewport[1])
    if w<320 or h<480 or w>3840 or h>2160:raise ContractViolation("BROWSER_VIEWPORT_INVALID",["$.viewport: unsupported"])
    out=Path(output_dir).expanduser().resolve();out.mkdir(parents=True,exist_ok=True);shots=out/"screenshots";shots.mkdir(exist_ok=True)
    source=discover_source_routes(project_root,limit=max_pages); explicit=[]
    for x in routes or ():
        r=_normalize_route(x)
        if r and r not in explicit:explicit.append(r)
    if not start_url:
        pages=[{"path":x["path"],"template":x["template"],"status":"dynamic" if ":param" in x["template"] else "not_scanned","reason":"No runtime URL supplied"} for x in source]; inv=aggregate_inventory([],mode=mode);dm=_design_map(project_root);tc=_token_compare(inv,dm)
        report={"schemaVersion":"1","producer":"web-ui-quality-ui-inventory","packageVersion":PACKAGE_VERSION,"status":"NOT_VERIFIED","readOnly":True,"mode":mode,"target":{"startUrl":None,"projectRoot":"." if project_root else None},"stats":{"pagesDiscovered":len(pages),"pagesScanned":0,"pagesFailed":0,"pagesSkipped":len(pages)},"sourceRoutes":source,"pages":pages,"inventory":inv,"designSystemMap":dm,"tokenComparison":tc,"limitations":["Runtime URL was not supplied; rendered values are not verified."]}
    else:
        p=urlsplit(start_url)
        if p.scheme not in {"http","https"} or not p.hostname or p.username or p.password:raise ContractViolation("BROWSER_URL_INVALID",["$.startUrl: safe absolute http(s) URL required"])
        approved={origin(start_url)}
        for x in allow_origins:
            ap=urlsplit(str(x))
            if ap.scheme not in {"http","https"} or not ap.hostname:raise ContractViolation("BROWSER_URL_INVALID",[f"$.allowOrigins: invalid {x!r}"])
            approved.add(origin(str(x)))
        authenticated = storage_state is not None
        urls=[]; seen=set()
        def enqueue(url: str, *, preserve_query: bool = False) -> None:
            parsed_url=urlsplit(url)
            path=_normalize_route(parsed_url.path or "/")
            if not path:return
            template=_route_template(path)
            if template in seen:return
            seen.add(template); urls.append(urlunsplit((p.scheme,p.netloc,path,parsed_url.query if preserve_query else "","")))
        # The explicitly requested target URL is an authority input. Preserve
        # its query for authenticated navigation; discovered routes remain
        # path-oriented to avoid silently broadening the crawl surface.
        enqueue(start_url, preserve_query=True)
        if not authenticated:
            for x in source:
                if ":param" not in x["template"]:enqueue(urlunsplit((p.scheme,p.netloc,x["path"],"","")))
        for x in explicit:
            if ":param" not in _route_template(x):enqueue(urlunsplit((p.scheme,p.netloc,x,"","")))
        approved_route_urls=set(urls)
        pages=[];decisions=[];discovered_links=[]
        try:from playwright.sync_api import sync_playwright
        except ImportError as e:raise ContractViolation("PLAYWRIGHT_UNAVAILABLE",["$: install web-ui-quality[browser]"]) from e
        with sync_playwright() as runtime:
            browser=_launch(runtime,browser_name,browser_executable)
            safe_headers, credential_map = build_credential_map(target_origin=origin(start_url), all_primary_origins=(origin(start_url),), headers=extra_http_headers)
            audit=create_secure_context(
                browser,
                context_options=_ctx((w,h),locale,theme,storage_state,safe_headers,ignore_https_errors),
                allowed_origins=approved, credential_headers_by_origin=credential_map,
                approved_routes=approved_route_urls,
                authenticated=authenticated,
            )
            context=audit.context; firewall=audit.firewall; page=context.new_page()
            try:
                i=0
                while i<len(urls) and len(pages)<max_pages:
                    current=urls[i];i+=1;path=_normalize_route(urlsplit(current).path or "/") or "/";row=_scan_page(page,current,path,mode,shots,timeout_ms);pages.append(row)
                    for link in row.get("links",[]) or []:
                        local=_same_origin_link(str(link),start_url)
                        if local and authenticated:
                            if local not in discovered_links:discovered_links.append(local)
                        elif local:enqueue(local)
                decisions=list(firewall.decisions)
            finally:context.close();browser.close()
        known_templates={_route_template(str(x.get("path") or "/")) for x in pages if x.get("status")=="scanned"}; known_paths={str(x.get("path")) for x in pages}
        for x in source:
            if x["path"] not in known_paths and x["template"] not in known_templates and ":param" in x["template"]:pages.append({"path":x["path"],"template":x["template"],"status":"dynamic","reason":"No representative instance discovered."})
        inv=aggregate_inventory(pages,mode=mode);dm=_design_map(project_root);tc=_token_compare(inv,dm);scanned=sum(x.get("status")=="scanned" for x in pages);failed=sum(x.get("status") in {"failed","broken"} for x in pages);skipped=len(pages)-scanned-failed
        inventory_status = "NOT_VERIFIED" if scanned == 0 else "PASS_WITH_WARNINGS" if failed or skipped else "PASS"
        report={"schemaVersion":"1","producer":"web-ui-quality-ui-inventory","packageVersion":PACKAGE_VERSION,"status":inventory_status,"readOnly":True,"mode":mode,"target":{"startUrl":start_url,"projectRoot":"." if project_root else None,"viewport":{"width":w,"height":h}},"stats":{"pagesDiscovered":len(pages),"pagesScanned":scanned,"pagesFailed":failed,"pagesSkipped":skipped},"sourceRoutes":source,"pages":pages,"inventory":inv,"designSystemMap":dm,"tokenComparison":tc,"navigationPolicy":{"authenticated":authenticated,"approvedRoutes":sorted(navigation_route_key(value) for value in approved_route_urls),"discoveredLinksRecordedOnly":discovered_links if authenticated else []},"mutationFirewall":{"status":"BLOCKED_MUTATION_ATTEMPT" if firewall.mutation_attempted or firewall.network_escape_attempted else "PASS","decisions":decisions},"networkPolicy":audit.report(),"limitations":["Only rendered routes/states reachable in the supplied session are proven.","Authenticated inventory visits only the start route and explicitly approved routes; newly discovered links are recorded but not opened.","Hover/focus pseudo-class styles are not asserted unless visible in the measured state.","Different values are review candidates, not automatic errors; no source changes are performed."]}
    report["topIssues"]=_issues(report["inventory"],report.get("tokenComparison"));report["summary"]=_summary(report);report["artifacts"]={"json":"ui-inventory.json","html":"ui-inventory.html","screenshots":"screenshots/"}
    persisted_report = _stabilize_report_urls(report)
    (out/"ui-inventory.json").write_text(json.dumps(persisted_report,ensure_ascii=False,indent=2,sort_keys=True),encoding="utf-8");(out/"ui-inventory.html").write_text(_render_html(persisted_report),encoding="utf-8")
    return report

__all__=["aggregate_inventory","discover_source_routes","run_ui_inventory"]
