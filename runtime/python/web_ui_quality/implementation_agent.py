"""Source-native, multi-direction implementation in an isolated design workspace."""
from __future__ import annotations

from collections.abc import Mapping
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
from typing import Any

from .contracts import ContractViolation
from .project_semantics import build_project_semantic_map, selectors_for_role, write_project_design_context
from .release_info import PACKAGE_VERSION, release_identity


SKIP_DIRS = {
    ".git", ".hg", ".svn", ".idea", ".vscode", ".pytest_cache", ".mypy_cache",
    ".next", ".nuxt", ".svelte-kit", ".venv", "venv", "__pycache__", "node_modules",
    "coverage", "dist", "build", "target", "vendor", "output", "reference-output",
}
MAX_FILES = 5_000
MAX_FILE_BYTES = 25 * 1024 * 1024
MAX_TOTAL_BYTES = 250 * 1024 * 1024
STYLE_MARKER = f"wuq-design-work-{PACKAGE_VERSION}"
SCRIPT_MARKER = f"wuq-design-runtime-{PACKAGE_VERSION}"


PALETTES = {
    "crm": ("#176b52", "#0d4737", "#dff3e9", "#f3f7f5"),
    "saas": ("#2563d9", "#173f91", "#e5edff", "#f5f7fc"),
    "landing": ("#c55231", "#82301e", "#ffeadf", "#fbf7f3"),
    "commerce": ("#b54a32", "#772d21", "#ffe7dc", "#fcf7f4"),
    "ai-product": ("#684bd2", "#47318f", "#eee9ff", "#f7f5fc"),
    "mobile": ("#18747a", "#104f53", "#dcf3f3", "#f3f9f9"),
}

RECIPES = (
    {
        "id": "operations-workspace",
        "label": "高效工作台",
        "promise": "把列表、上下文和下一步行动组织成稳定的高密度工作区。",
        "signature": "persistent-navigation + split-workspace + compact-objects",
    },
    {
        "id": "guided-flow",
        "label": "引导式流程",
        "promise": "用横向导航、清晰分组和渐进披露降低第一次使用的理解成本。",
        "signature": "top-navigation + staged-cards + guided-actions",
    },
    {
        "id": "calm-focus",
        "label": "沉静聚焦",
        "promise": "用克制的视觉层级、宽松留白和单一主行动提升决策清晰度。",
        "signature": "compact-rail + focused-detail + calm-hierarchy",
    },
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _slug(value: Any, fallback: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(value or "").casefold()).strip("-")
    return slug[:64] or fallback


def _project_files(root: Path) -> list[Path]:
    files: list[Path] = []
    total = 0
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if any(part in SKIP_DIRS or part.startswith(".wuq-") for part in relative.parts):
            continue
        if path.is_symlink() or not path.is_file():
            continue
        size = path.stat().st_size
        if size > MAX_FILE_BYTES:
            raise ContractViolation("IMPLEMENTATION_SCOPE_TOO_LARGE", [f"{relative.as_posix()}: file exceeds {MAX_FILE_BYTES} bytes"])
        total += size
        if total > MAX_TOTAL_BYTES:
            raise ContractViolation("IMPLEMENTATION_SCOPE_TOO_LARGE", [f"$: project exceeds {MAX_TOTAL_BYTES} copied bytes"])
        files.append(path)
        if len(files) > MAX_FILES:
            raise ContractViolation("IMPLEMENTATION_SCOPE_TOO_LARGE", [f"$: project exceeds {MAX_FILES} files"])
    if not files:
        raise ContractViolation("IMPLEMENTATION_SCOPE_EMPTY", ["$: no bounded project files found"])
    return files


def _copy_files(root: Path, files: list[Path], destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=False)
    for source in files:
        target = destination / source.relative_to(root)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def _safe_css_value(value: Any, fallback: str) -> str:
    token = str(value or "").strip()
    return token if token and not any(character in token for character in ";{}") else fallback


def _design_token(design_context: Mapping[str, Any], semantic: str, fallback: str) -> str:
    semantic_map = design_context.get("semanticMap") if isinstance(design_context.get("semanticMap"), Mapping) else {}
    design_system = semantic_map.get("designSystem") if isinstance(semantic_map.get("designSystem"), Mapping) else {}
    aliases = design_system.get("semanticAliases") if isinstance(design_system.get("semanticAliases"), Mapping) else {}
    value = str(aliases.get(semantic) or "")
    if value.startswith("--"):
        return f"var({value},{fallback})"
    return _safe_css_value(value, fallback)


def _base_css(
    product_type: str,
    recipe: Mapping[str, Any],
    direction: Mapping[str, Any],
    design_context: Mapping[str, Any],
) -> str:
    brand, strong, soft, paper = PALETTES.get(product_type, PALETTES["saas"])
    recipe_id = str(recipe["id"])
    direction_name = str(direction.get("name") or recipe["label"])
    semantic_map = design_context.get("semanticMap") if isinstance(design_context.get("semanticMap"), Mapping) else {}
    navigation = selectors_for_role(semantic_map, "navigation", (".nav",))
    brand = _design_token(design_context, "color.action.primary", brand)
    paper = _design_token(design_context, "color.background.canvas", paper)
    surface = _design_token(design_context, "color.background.surface", "#fff")
    ink = _design_token(design_context, "color.text.primary", "#17211d")
    muted = _design_token(design_context, "color.text.secondary", "#64716b")
    line = _design_token(design_context, "color.border.default", "#d8e2dc")
    concept = recipe.get("designConcept") if isinstance(recipe.get("designConcept"), Mapping) else {}
    concept_id = str(concept.get("archetype") or "project-grounded")
    return f"""/* {STYLE_MARKER} · {recipe_id} · {direction_name}. Isolated candidate only. */
/* Project-grounded design concept: {concept_id}. */
:root {{
  --wuq-brand:{brand};--wuq-brand-strong:{strong};--wuq-brand-soft:{soft};--wuq-paper:{paper};
  --wuq-surface:{surface};--wuq-ink:{ink};--wuq-muted:{muted};--wuq-line:{line};--wuq-focus:#2478ff;
  --wuq-r-sm:10px;--wuq-r-md:16px;--wuq-r-lg:24px;--wuq-shadow:0 18px 55px rgba(24,49,39,.10);
  color-scheme:light;
}}
html {{ scroll-behavior:smooth; }}
body {{ background:var(--wuq-paper);color:var(--wuq-ink);text-rendering:optimizeLegibility;-webkit-font-smoothing:antialiased; }}
:where(main,section,article,aside,nav,header,footer,div) {{ min-inline-size:0; }}
:where(button,input,select,textarea,a[href]) {{ font:inherit;touch-action:manipulation; }}
:where(button,input:not([type="checkbox"]):not([type="radio"]),select) {{ min-block-size:44px; }}
:where(button,[role="button"]) {{ min-inline-size:44px!important;flex-shrink:0; }}
{navigation} a {{ min-block-size:44px;min-inline-size:44px;display:flex;align-items:center; }}
:where(button,[role="button"],input,select,textarea,a[href]):focus-visible {{ outline:3px solid var(--wuq-focus)!important;outline-offset:3px; }}
:where(button,.button,[role="button"]) {{ border-radius:var(--wuq-r-sm); }}
:where(.primary,button.primary,[data-primary]) {{ background:var(--wuq-brand)!important;border-color:var(--wuq-brand)!important;color:#fff!important;box-shadow:0 8px 22px color-mix(in srgb,var(--wuq-brand) 24%,transparent); }}
:where(.primary,button.primary,[data-primary]):hover {{ background:var(--wuq-brand-strong)!important; }}
:where(h1,h2,h3) {{ text-wrap:balance;letter-spacing:-.03em; }}
:where(p,small,.muted) {{ text-wrap:pretty; }}
table {{ inline-size:100%;border-collapse:separate;border-spacing:0; }}
:where(th,td) {{ padding-block:12px; }}
thead th {{ position:sticky;inset-block-start:0;z-index:1;background:var(--wuq-paper); }}
[data-wuq-scroll-region] {{ overflow:auto;overscroll-behavior:contain; }}
"""


def _recipe_css(recipe_id: str, design_context: Mapping[str, Any]) -> str:
    semantic_map = design_context.get("semanticMap") if isinstance(design_context.get("semanticMap"), Mapping) else {}
    shell = selectors_for_role(semantic_map, "shell", (".app",))
    navigation = selectors_for_role(semantic_map, "navigation", (".nav",))
    page_head = selectors_for_role(semantic_map, "pageHeader", (".page-head",))
    toolbar = selectors_for_role(semantic_map, "toolbar", (".toolbar",))
    workspace = selectors_for_role(semantic_map, "workspace", (".workspace",))
    collection = selectors_for_role(semantic_map, "collection", (".list-panel",))
    detail = selectors_for_role(semantic_map, "detail", (".detail",))
    item = selectors_for_role(semantic_map, "item", (".account",))
    facts = selectors_for_role(semantic_map, "facts", (".facts",))
    fact = selectors_for_role(semantic_map, "fact", (".fact",))
    actions = selectors_for_role(semantic_map, "actions", (".actions",))
    if recipe_id == "guided-flow":
        return f"""
/* A materially different top-navigation and staged-card composition. */
{shell} {{ display:block!important;min-height:100vh; }}
{navigation} {{ position:sticky!important;inset-block-start:0;z-index:20;height:auto!important;min-height:68px;padding:10px clamp(16px,3vw,34px)!important;display:flex!important;flex-direction:row!important;align-items:center!important;gap:18px;background:color-mix(in srgb,var(--wuq-surface) 94%,transparent)!important;color:var(--wuq-ink)!important;border-bottom:1px solid var(--wuq-line);backdrop-filter:blur(18px); }}
.logo {{ margin:0!important;flex:0 0 auto;box-shadow:inset 0 0 0 1px color-mix(in srgb,var(--wuq-brand) 22%,transparent); }}
{navigation} nav {{ display:flex!important;grid-auto-flow:column;gap:4px;overflow:auto; }}
{navigation} a {{ color:var(--wuq-muted)!important;white-space:nowrap; }}
{navigation} a.active,{navigation} a:hover {{ background:var(--wuq-brand-soft)!important;color:var(--wuq-brand-strong)!important; }}
.profile {{ margin:0 0 0 auto!important;color:var(--wuq-ink)!important; }}
.profile span {{ color:var(--wuq-muted)!important; }}
main {{ max-width:1240px;margin-inline:auto;padding:clamp(22px,4vw,52px)!important; }}
{page_head} {{ padding:26px 28px;border:1px solid var(--wuq-line);border-radius:var(--wuq-r-lg);background:linear-gradient(135deg,var(--wuq-surface) 0%,var(--wuq-brand-soft) 150%);box-shadow:0 14px 42px rgba(35,62,51,.07); }}
{page_head} h1 {{ font-size:clamp(34px,4vw,52px)!important; }}
{toolbar} {{ padding:16px 18px;margin-block:18px 14px!important;border:1px solid var(--wuq-line);border-radius:var(--wuq-r-md);background:var(--wuq-surface); }}
{workspace} {{ grid-template-columns:minmax(0,.9fr) minmax(0,1.1fr)!important;gap:18px!important; }}
{collection},{detail} {{ border:0!important;border-radius:var(--wuq-r-lg)!important;box-shadow:0 16px 50px rgba(28,52,42,.09); }}
{item} {{ margin:8px 10px;padding:13px!important;border:1px solid transparent!important;border-radius:14px;background:var(--wuq-surface); }}
{item}:hover,{item}[aria-selected="true"] {{ border-color:color-mix(in srgb,var(--wuq-brand) 28%,var(--wuq-line))!important;background:var(--wuq-brand-soft)!important; }}
{detail} {{ padding:clamp(24px,3vw,38px)!important; }}
{facts} {{ gap:12px!important; }}{fact} {{ border:1px solid var(--wuq-line);background:color-mix(in srgb,var(--wuq-surface) 94%,var(--wuq-paper))!important; }}
{actions} {{ padding-top:18px;border-top:1px solid var(--wuq-line); }}
@media(max-width:760px){{{navigation}{{overflow:auto}}.profile{{display:none!important}}{page_head}{{padding:20px}}{workspace}{{grid-template-columns:1fr!important}}{detail}{{min-height:420px}}}}
"""
    if recipe_id == "calm-focus":
        return f"""
/* A compact rail and calm, detail-first decision surface. */
body {{ background:#f7f7f4!important; }}
{shell} {{ grid-template-columns:92px minmax(0,1fr)!important; }}
{navigation} {{ padding:24px 12px!important;background:var(--wuq-surface)!important;color:var(--wuq-ink)!important;border-right:1px solid var(--wuq-line); }}
.logo {{ margin-inline:auto!important;margin-bottom:34px!important; }}
{navigation} nav {{ gap:8px!important; }}
{navigation} a {{ padding:12px 5px!important;text-align:center;color:var(--wuq-muted)!important;font-size:11px; }}
{navigation} a.active,{navigation} a:hover {{ background:var(--wuq-brand-soft)!important;color:var(--wuq-brand-strong)!important; }}
.profile {{ padding:8px 0!important;justify-content:center;color:var(--wuq-ink)!important; }}.profile span{{display:none!important}}
main {{ inline-size:min(100%,1260px);margin-inline:auto;padding:clamp(28px,5vw,66px)!important; }}
{page_head} {{ align-items:center!important; }}{page_head} h1{{font-size:clamp(40px,5vw,64px)!important;font-weight:720;letter-spacing:-.055em!important}}{page_head} p{{text-transform:uppercase;letter-spacing:.12em;font-weight:700}}
{toolbar} {{ margin-block:34px 18px!important;align-items:center!important; }}{toolbar} label{{max-width:520px}}
{workspace} {{ grid-template-columns:minmax(300px,.7fr) minmax(520px,1.3fr)!important;gap:22px!important;min-height:640px; }}
{collection},{detail} {{ border:1px solid var(--wuq-line)!important;border-radius:26px!important;background:var(--wuq-surface);box-shadow:none; }}
.list-head {{ padding:18px 20px!important; }}{item}{{padding:18px!important;background:transparent!important}}{item}[aria-selected="true"]{{background:var(--wuq-brand-soft)!important;box-shadow:inset 3px 0 0 var(--wuq-brand)}}
{detail} {{ padding:clamp(28px,4vw,48px)!important; }}{detail} h2{{font-size:clamp(30px,3vw,42px)!important}}{facts}{{margin-block:34px!important}}{fact}{{padding:18px!important;background:color-mix(in srgb,var(--wuq-surface) 86%,var(--wuq-paper))!important}}.timeline{{padding-top:28px!important}}{actions}{{margin-top:34px!important}}
@media(max-width:900px){{{workspace}{{grid-template-columns:1fr!important}}{shell}{{grid-template-columns:72px minmax(0,1fr)!important}}main{{padding:24px!important}}}}
@media(max-width:560px){{{shell}{{display:block!important}}{navigation}{{position:static!important;height:auto!important;flex-direction:row!important;overflow:auto}}.logo{{margin:0 8px 0 0!important}}{navigation} nav{{display:flex!important}}{navigation} a{{font-size:12px;white-space:nowrap}}{workspace}{{display:block!important}}{detail}.mobile-open{{display:block!important;position:fixed!important;inset:0;z-index:30;border-radius:0!important;overflow:auto}}}}
"""
    return f"""
/* A persistent, efficient split workspace for repeated operational work. */
{shell} {{ grid-template-columns:204px minmax(0,1fr)!important; }}
{navigation} {{ background:#10251d!important;padding:22px 14px!important; }}
{navigation} a {{ border-radius:12px!important; }}{navigation} a.active{{background:#24513f!important}}
main {{ max-width:1480px;margin-inline:auto;padding:clamp(24px,3vw,42px)!important; }}
{page_head} h1 {{ font-size:clamp(36px,4vw,50px)!important; }}
{toolbar} {{ margin-block:24px 14px!important; }}
{workspace} {{ grid-template-columns:minmax(330px,.78fr) minmax(500px,1.22fr)!important;gap:14px!important; }}
{collection},{detail} {{ border:1px solid var(--wuq-line)!important;border-radius:18px!important;background:var(--wuq-surface);box-shadow:0 10px 38px rgba(28,54,43,.06); }}
.list-head {{ position:sticky;top:0;z-index:2;background:#fff;padding:15px 16px!important; }}
{item} {{ min-height:66px;padding:12px 14px!important; }}{item}[aria-selected="true"]{{background:var(--wuq-brand-soft)!important;box-shadow:inset 3px 0 0 var(--wuq-brand)}}
{detail} {{ padding:clamp(24px,3vw,36px)!important; }}{facts}{{gap:10px!important}}{fact}{{background:color-mix(in srgb,var(--wuq-surface) 88%,var(--wuq-paper))!important}}{actions}{{position:sticky;bottom:0;padding-block:16px;background:linear-gradient(transparent,var(--wuq-surface) 24%)}}
@media(max-width:900px){{{shell}{{grid-template-columns:72px minmax(0,1fr)!important}}{workspace}{{grid-template-columns:1fr!important}}{navigation} a{{font-size:0}}{navigation} a::first-letter{{font-size:15px}}}}
@media(max-width:560px){{{shell}{{display:block!important}}{navigation}{{position:static!important;height:auto!important;flex-direction:row!important;overflow:auto}}.logo{{margin:0 8px 0 0!important}}{navigation} nav{{display:flex!important}}{navigation} a{{font-size:12px;white-space:nowrap}}{workspace}{{display:block!important}}{detail}.mobile-open{{display:block!important;position:fixed!important;inset:0;z-index:30;border-radius:0!important;overflow:auto}}}}
"""


def _responsive_css(design_context: Mapping[str, Any]) -> str:
    semantic_map = design_context.get("semanticMap") if isinstance(design_context.get("semanticMap"), Mapping) else {}
    page_head = selectors_for_role(semantic_map, "pageHeader", (".page-head",))
    toolbar = selectors_for_role(semantic_map, "toolbar", (".toolbar",))
    detail = selectors_for_role(semantic_map, "detail", (".detail",))
    return f"""
@media(max-width:900px){{:where({page_head},{toolbar}){{align-items:stretch;flex-wrap:wrap}}:where({page_head},{toolbar})>*{{min-inline-size:0}}}}
@media(max-width:560px){{:where(main,.content,.shell){{padding-inline:14px!important}}:where(.filters,.actions,.button-row){{flex-wrap:wrap}}:where(.filters,.actions,.button-row)>button{{flex:1 1 auto}}h1{{font-size:clamp(28px,10vw,42px)!important}}{detail}.mobile-open{{display:block!important;position:fixed!important;inset:0!important;z-index:40!important;overflow:auto!important;border-radius:0!important}}}}
@media(prefers-reduced-motion:reduce){{*,*::before,*::after{{scroll-behavior:auto!important;transition-duration:.01ms!important;animation-duration:.01ms!important}}}}
"""


def _stylesheet(product_type: str, recipe: Mapping[str, Any], direction: Mapping[str, Any], design_context: Mapping[str, Any]) -> str:
    return _base_css(product_type, recipe, direction, design_context) + _recipe_css(str(recipe["id"]), design_context) + _responsive_css(design_context)


def _enhancement_script(recipe: Mapping[str, Any], direction: Mapping[str, Any], design_context: Mapping[str, Any]) -> str:
    semantic_map = design_context.get("semanticMap") if isinstance(design_context.get("semanticMap"), Mapping) else {}
    semantic_selectors = {
        role: selectors_for_role(semantic_map, role, ())
        for role in ("shell", "navigation", "pageHeader", "toolbar", "workspace", "collection", "detail", "facts", "fact", "item", "actions", "profile", "status")
    }
    return f"""/* {SCRIPT_MARKER}: semantic recovery and design-candidate identity. */
(() => {{
  const root=document.documentElement;
  root.dataset.wuqRelease={json.dumps(PACKAGE_VERSION)};
  root.dataset.wuqVariant={json.dumps(recipe['id'])};
  root.dataset.wuqDesignSource='project-semantics';
  const semanticSelectors={json.dumps(semantic_selectors, ensure_ascii=False)};
  Object.entries(semanticSelectors).forEach(([role,selector])=>{{try{{document.querySelectorAll(selector).forEach(node=>{{if(!node.dataset.wuqRole)node.dataset.wuqRole=role}})}}catch(_error){{}}}});
  const workspace=document.querySelector(semanticSelectors.workspace);
  if(workspace){{
    if({json.dumps(str(recipe['id']))}==='guided-flow'){{[...workspace.children].forEach((node,index)=>{{node.dataset.wuqStage=String(index+1)}});workspace.dataset.wuqDisclosure='staged'}}
    if({json.dumps(str(recipe['id']))}==='operations-workspace')workspace.dataset.wuqDensity='compact';
    if({json.dumps(str(recipe['id']))}==='calm-focus')workspace.dataset.wuqAttention='detail-first';
  }}
  document.querySelectorAll('input[type="search"]').forEach((input)=>{{if(!input.getAttribute('aria-label')){{const label=input.closest('label')?.textContent?.trim();input.setAttribute('aria-label',label||input.getAttribute('placeholder')||'Search')}}}});
  document.querySelectorAll('[id*="toast" i],[class*="toast" i],[id*="status" i]').forEach((node)=>{{if(!node.getAttribute('role'))node.setAttribute('role','status');if(!node.getAttribute('aria-live'))node.setAttribute('aria-live','polite')}});
  document.querySelectorAll('[id*="empty" i],[class*="empty" i]').forEach((node)=>{{if(!node.getAttribute('role'))node.setAttribute('role','status')}});
  document.querySelectorAll('table').forEach((table)=>{{const parent=table.parentElement;if(parent){{parent.dataset.wuqScrollRegion='';if(!parent.hasAttribute('tabindex'))parent.tabIndex=0}}}});
  window.__WUQ_TRANSFORMATION__=Object.freeze({{version:{json.dumps(PACKAGE_VERSION)},variant:{json.dumps(recipe['id'])},direction:{json.dumps(str(direction.get('id') or 'unknown'))},status:'IMPLEMENTED_IN_ISOLATED_COPY'}});
}})();
"""


def _inject_html(path: Path, root: Path) -> bool:
    source = path.read_text(encoding="utf-8")
    if STYLE_MARKER in source or SCRIPT_MARKER in source:
        return False
    css_relative = os.path.relpath(root / "wuq-experience.css", path.parent).replace(os.sep, "/")
    js_relative = os.path.relpath(root / "wuq-experience.js", path.parent).replace(os.sep, "/")
    head = f'  <link rel="stylesheet" href="{css_relative}" data-wuq-asset="{STYLE_MARKER}">\n'
    script = f'  <script src="{js_relative}" data-wuq-asset="{SCRIPT_MARKER}"></script>\n'
    lowered = source.casefold()
    head_index = lowered.rfind("</head>")
    body_index = lowered.rfind("</body>")
    if head_index < 0 or body_index < 0:
        return False
    source = source[:head_index] + head + source[head_index:]
    body_index = source.casefold().rfind("</body>")
    path.write_text(source[:body_index] + script + source[body_index:], encoding="utf-8")
    return True


def _framework(root: Path) -> str | None:
    package = root / "package.json"
    text = package.read_text(encoding="utf-8", errors="ignore").casefold() if package.is_file() else ""
    if "next" in text or any((root / item).is_file() for item in ("src/app/layout.tsx", "app/layout.tsx")):
        return "next"
    if "react" in text or any((root / item).is_file() for item in ("src/main.tsx", "src/main.jsx", "src/App.tsx", "src/App.jsx")):
        return "react"
    if "vue" in text or any((root / item).is_file() for item in ("src/main.ts", "src/main.js")) and any(root.rglob("*.vue")):
        return "vue"
    return None


def _framework_entry(root: Path, framework: str | None) -> Path | None:
    candidates = {
        "next": (
            "src/app/layout.tsx", "src/app/layout.jsx", "src/app/layout.js", "app/layout.tsx", "app/layout.jsx", "app/layout.js",
            "src/pages/_app.tsx", "src/pages/_app.jsx", "src/pages/_app.ts", "src/pages/_app.js",
            "pages/_app.tsx", "pages/_app.jsx", "pages/_app.ts", "pages/_app.js",
        ),
        "react": ("src/main.tsx", "src/main.jsx", "src/App.tsx", "src/App.jsx", "src/main.ts", "src/main.js"),
        "vue": ("src/main.ts", "src/main.js"),
    }.get(framework or "", ())
    return next((root / item for item in candidates if (root / item).is_file()), None)


def _insert_imports(source: str, imports: list[str]) -> str:
    """Keep JavaScript directive prologues such as ``use client`` first."""
    if not imports:
        return source
    lines = source.splitlines(keepends=True)
    index = 0
    while index < len(lines) and (not lines[index].strip() or lines[index].lstrip().startswith(("//", "/*", "*"))):
        index += 1
    directive_end = index
    directive = re.compile(r"^[\"'][^\"']+[\"'];?$")
    while directive_end < len(lines) and directive.fullmatch(lines[directive_end].strip()):
        directive_end += 1
    insertion = directive_end if directive_end > index else index
    block = "".join(value + "\n" for value in imports)
    return "".join(lines[:insertion]) + block + "".join(lines[insertion:])


def _inject_framework(
    root: Path,
    css: str,
    recipe: Mapping[str, Any],
    direction: Mapping[str, Any],
    design_context: Mapping[str, Any],
) -> tuple[list[str], str]:
    framework = _framework(root)
    entry = _framework_entry(root, framework)
    if entry is None:
        return [], "FRAMEWORK_NOT_SUPPORTED"
    design_dir = entry.parent / "wuq-experience"
    design_dir.mkdir(exist_ok=True)
    css_path = design_dir / "experience-layer.css"
    runtime_path = design_dir / "experience-runtime.js"
    tokens_path = design_dir / "design-tokens.json"
    semantic_path = design_dir / "project-semantic-map.json"
    css_path.write_text(css, encoding="utf-8")
    runtime_path.write_text(_enhancement_script(recipe, direction, design_context), encoding="utf-8")
    semantic_map = design_context.get("semanticMap") if isinstance(design_context.get("semanticMap"), Mapping) else {}
    semantic_path.write_text(json.dumps(semantic_map, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tokens_path.write_text(json.dumps({
        "version": PACKAGE_VERSION,
        "recipe": recipe["id"],
        "signature": recipe["signature"],
        "designConcept": recipe.get("designConcept"),
        "semanticAliases": (semantic_map.get("designSystem") or {}).get("semanticAliases", {}) if isinstance(semantic_map.get("designSystem"), Mapping) else {},
        "ownership": "project-local-candidate",
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    relative_import = "./wuq-experience/experience-layer.css"
    runtime_import = "./wuq-experience/experience-runtime.js"
    source = entry.read_text(encoding="utf-8")
    imports = []
    if relative_import not in source:
        imports.append(f'import "{relative_import}";')
    if runtime_import not in source:
        imports.append(f'import "{runtime_import}";')
    if imports:
        entry.write_text(_insert_imports(source, imports), encoding="utf-8")
    changed = [
        entry.relative_to(root).as_posix(), css_path.relative_to(root).as_posix(),
        runtime_path.relative_to(root).as_posix(), tokens_path.relative_to(root).as_posix(), semantic_path.relative_to(root).as_posix(),
    ]
    if framework == "next":
        router = "PAGES_ROUTER" if "/pages/" in f"/{entry.relative_to(root).as_posix()}" else "APP_ROUTER"
        return changed, f"NEXT_{router}_SOURCE_NATIVE_STYLE"
    return changed, f"{framework.upper()}_SOURCE_NATIVE_STYLE"


def _implement(
    root: Path,
    product_type: str,
    recipe: Mapping[str, Any],
    direction: Mapping[str, Any],
    design_context: Mapping[str, Any],
) -> tuple[list[str], str]:
    css = _stylesheet(product_type, recipe, direction, design_context)
    if _framework(root):
        return _inject_framework(root, css, recipe, direction, design_context)
    html_files = [path for path in sorted(root.rglob("*.html")) if not any(part in SKIP_DIRS for part in path.relative_to(root).parts)]
    if html_files:
        (root / "wuq-experience.css").write_text(css, encoding="utf-8")
        (root / "wuq-experience.js").write_text(_enhancement_script(recipe, direction, design_context), encoding="utf-8")
        semantic_map = design_context.get("semanticMap") if isinstance(design_context.get("semanticMap"), Mapping) else {}
        (root / "wuq-project-map.json").write_text(json.dumps(semantic_map, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        changed = {"wuq-experience.css", "wuq-experience.js", "wuq-project-map.json"}
        for path in html_files[:50]:
            if _inject_html(path, root):
                changed.add(path.relative_to(root).as_posix())
        return sorted(changed), "STATIC_HTML_DESIGN_RECONSTRUCTION"
    return _inject_framework(root, css, recipe, direction, design_context)


def _diff_file(relative: str, before: Path, after: Path) -> str:
    before_path = before / relative
    after_path = after / relative
    old = before_path.read_text(encoding="utf-8").splitlines(keepends=True) if before_path.is_file() else []
    new = after_path.read_text(encoding="utf-8").splitlines(keepends=True) if after_path.is_file() else []
    return "".join(difflib.unified_diff(old, new, fromfile=f"a/{relative}" if old else "/dev/null", tofile=f"b/{relative}"))


def execute_isolated_transformation(
    project_root: str | Path,
    output_dir: str | Path,
    report: Mapping[str, Any],
    *,
    design_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Create exactly three materially distinct candidates and promote one to the compatibility After path."""
    project = Path(project_root).expanduser().resolve()
    output = Path(output_dir).expanduser().resolve()
    if not project.is_dir():
        raise ContractViolation("IMPLEMENTATION_PROJECT_INVALID", ["$: project root must be a directory"])
    if output == project or project in output.parents:
        raise ContractViolation("IMPLEMENTATION_OUTPUT_INVALID", ["$: output must be outside the target project"])
    if output.exists() and any(output.iterdir()):
        raise ContractViolation("IMPLEMENTATION_OUTPUT_NOT_EMPTY", ["$: output directory must be new or empty"])
    output.mkdir(parents=True, exist_ok=True)
    grounded_context = dict(design_context or {})
    if not isinstance(grounded_context.get("semanticMap"), Mapping):
        grounded_context["semanticMap"] = build_project_semantic_map(project)
    semantic_map = grounded_context["semanticMap"]
    if not isinstance(grounded_context.get("designSystem"), Mapping) and isinstance(semantic_map.get("designSystem"), Mapping):
        grounded_context["designSystem"] = semantic_map["designSystem"]
    design_artifacts = write_project_design_context(grounded_context, output / "design-intelligence")
    preview = output / "generated-preview"
    before = preview / "before"
    variants_root = preview / "variants"
    source_files = _project_files(project)
    _copy_files(project, source_files, before)
    variants_root.mkdir(parents=True)

    product = report.get("product") if isinstance(report.get("product"), Mapping) else {}
    product_type = str(product.get("type") or "saas")
    transformation = report.get("transformation") if isinstance(report.get("transformation"), Mapping) else {}
    design_candidates_value = grounded_context.get("designCandidates") if isinstance(grounded_context.get("designCandidates"), Mapping) else {}
    design_candidates = [item for item in design_candidates_value.get("candidates", []) if isinstance(item, Mapping)][:3]
    candidate_count = 3
    source_variants = [item for item in transformation.get("variants", []) if isinstance(item, Mapping)][:candidate_count]
    if not source_variants:
        source_variants = [{"id": f"direction-{index + 1}", "name": recipe["label"], "recommended": index == 0} for index, recipe in enumerate(RECIPES[:candidate_count])]
    while len(source_variants) < candidate_count:
        source_variants.append({"id": f"direction-{len(source_variants) + 1}", "name": RECIPES[len(source_variants)]["label"], "recommended": False})

    candidate_records: list[dict[str, Any]] = []
    for index, direction in enumerate(source_variants[:candidate_count]):
        concept = dict(design_candidates[index]) if index < len(design_candidates) else {}
        recipe = {**RECIPES[index], "designConcept": concept}
        direction_id = str(direction.get("id") or f"direction-{index + 1}")
        path_id = _slug(direction_id, f"direction-{index + 1}")
        root = variants_root / path_id
        _copy_files(project, source_files, root)
        changed, mode = _implement(root, product_type, recipe, direction, grounded_context)
        candidate_records.append({
            "id": direction_id,
            "pathId": path_id,
            "name": str(direction.get("name") or recipe["label"]),
            "recommendedByDiagnosis": bool(direction.get("recommended", index == 0)),
            "diagnosticFit": int((direction.get("fit") or {}).get("diagnosticFit", 100 if index == 0 else 78)) if isinstance(direction.get("fit"), Mapping) else (100 if index == 0 else 78),
            "recipe": dict(recipe),
            "designConcept": concept,
            "projectSemanticCoverage": semantic_map.get("coverage"),
            "mode": mode,
            "root": f"generated-preview/variants/{path_id}",
            "changedFiles": changed,
            "status": "IMPLEMENTED" if changed else "FRAMEWORK_NOT_SUPPORTED",
            "outcome": direction.get("outcome"),
            "tradeoff": direction.get("tradeoff"),
        })

    implemented = [item for item in candidate_records if item["status"] == "IMPLEMENTED"]
    if not implemented:
        result = {
            "schemaVersion": "1", "generator": release_identity(), "status": "FRAMEWORK_NOT_SUPPORTED",
            "mode": "FRAMEWORK_NOT_SUPPORTED", "sourceProjectChanged": False, "isolatedCopyChanged": False,
            "variants": candidate_records, "reason": "No safe HTML, React, Next.js, or Vue entry point was found.",
        }
        (output / "implementation-plan.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return result

    requested = transformation.get("selectedVariantId")
    selected = next((item for item in implemented if item["id"] == requested), implemented[0])
    selected_root = variants_root / selected["pathId"]
    after = preview / "after"
    shutil.copytree(selected_root, after)
    changed = list(selected["changedFiles"])

    patch_text = "".join(_diff_file(relative, before, after) for relative in sorted(changed))
    patch_path = output / "source-change.patch"
    patch_path.write_text(patch_text, encoding="utf-8")
    change_records = []
    for relative in sorted(changed):
        old, new = before / relative, after / relative
        change_records.append({
            "path": relative, "operation": "modify" if old.is_file() else "add",
            "beforeSha256": _sha256(old) if old.is_file() else None, "afterSha256": _sha256(new), "bytes": new.stat().st_size,
        })
    manifest = {
        "schemaVersion": "1", "generator": release_identity(), "status": "IMPLEMENTED_IN_ISOLATED_COPY",
        "mode": selected["mode"], "projectFileCount": len(source_files), "selectedVariantId": selected["id"],
        "changes": change_records, "patch": {"path": patch_path.name, "sha256": _sha256(patch_path), "bytes": patch_path.stat().st_size},
    }
    (output / "change-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output / "variant-manifest.json").write_text(json.dumps({
        "schemaVersion": "1", "generator": release_identity(), "status": "DESIGN_CANDIDATES_READY",
        "selectedVariantId": selected["id"], "variants": candidate_records,
    }, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    rollback = {
        "schemaVersion": "1", "strategy": "discard-isolated-workspace", "originalProjectChanged": False,
        "restoreSource": "generated-preview/before", "removeCandidate": "generated-preview/after",
        "removeAllVariants": "generated-preview/variants", "patchApplicationRequiresExplicitApproval": True,
    }
    (output / "rollback-manifest.json").write_text(json.dumps(rollback, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    plan = {
        "schemaVersion": "1", "generator": release_identity(), "status": "IMPLEMENTED_IN_ISOLATED_COPY",
        "mode": selected["mode"], "product": product, "selectedVariantId": selected["id"],
        "selectedDirection": {"id": selected["id"], "name": selected["name"], "outcome": selected.get("outcome"), "tradeoff": selected.get("tradeoff")},
        "sourceProjectChanged": False, "isolatedCopyChanged": True, "before": "generated-preview/before", "after": "generated-preview/after",
        "variantManifest": "variant-manifest.json", "variants": candidate_records, "patch": "source-change.patch",
        "designIntelligence": {key: f"design-intelligence/{value}" for key, value in design_artifacts.items()},
        "projectSemanticCoverage": semantic_map.get("coverage"),
        "changeManifest": "change-manifest.json", "rollbackManifest": "rollback-manifest.json", "changedFiles": sorted(changed),
        "acceptance": [
            "Three source-backed design candidates are independently runnable", "Candidates differ in composition, density, hierarchy, and navigation",
            "Original target source remains byte-for-byte untouched", "Selected After has a complete patch and rollback boundary",
            "Every candidate must pass Browser validation before presentation",
        ],
    }
    (output / "implementation-plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return plan


def _apply_decision_preferences(after: Path, preferences: Mapping[str, Any]) -> list[str]:
    density = str(preferences.get("density") or "preserve")
    brand = str(preferences.get("brand") or "preserve")
    if density not in {"preserve", "compact", "comfortable"}:
        raise ContractViolation("DESIGN_DECISION_INVALID", ["$.preferences.density: unsupported value"])
    if brand not in {"preserve", "refine", "explore"}:
        raise ContractViolation("DESIGN_DECISION_INVALID", ["$.preferences.brand: unsupported value"])
    css_paths = [after / "wuq-experience.css", *sorted(after.rglob("wuq-experience/experience-layer.css"))]
    runtime_paths = [after / "wuq-experience.js", *sorted(after.rglob("wuq-experience/experience-runtime.js"))]
    changed: list[str] = []
    density_css = {
        "preserve": "",
        "compact": "\n/* User decision: compact density. */\n[data-wuq-decision-density=\"compact\"] [data-wuq-role=\"item\"],[data-wuq-decision-density=\"compact\"] [data-wuq-role=\"fact\"]{padding-block:8px!important}\n",
        "comfortable": "\n/* User decision: comfortable density. */\n[data-wuq-decision-density=\"comfortable\"] [data-wuq-role=\"item\"],[data-wuq-decision-density=\"comfortable\"] [data-wuq-role=\"fact\"]{padding-block:18px!important}\n",
    }[density]
    for path in css_paths:
        if path.is_file() and density_css and "User decision:" not in path.read_text(encoding="utf-8"):
            path.write_text(path.read_text(encoding="utf-8") + density_css, encoding="utf-8")
            changed.append(path.relative_to(after).as_posix())
    decision_runtime = f"\n;(()=>{{document.documentElement.dataset.wuqDecisionDensity={json.dumps(density)};document.documentElement.dataset.wuqDecisionBrand={json.dumps(brand)}}})();\n"
    for path in runtime_paths:
        if path.is_file() and "wuqDecisionDensity" not in path.read_text(encoding="utf-8"):
            path.write_text(path.read_text(encoding="utf-8") + decision_runtime, encoding="utf-8")
            changed.append(path.relative_to(after).as_posix())
    return changed


def finalize_design_selection(
    upgrade_output: str | Path,
    decision: str | Path | Mapping[str, Any],
) -> dict[str, Any]:
    """Promote a gallery choice inside the isolated output and rebuild its patch."""
    root = Path(upgrade_output).expanduser().resolve()
    implementation = root / "implementation" if (root / "implementation").is_dir() else root
    before = implementation / "generated-preview" / "before"
    variants_root = implementation / "generated-preview" / "variants"
    after = implementation / "generated-preview" / "after"
    if not before.is_dir() or not variants_root.is_dir():
        raise ContractViolation("DESIGN_DECISION_OUTPUT_INVALID", ["$: expected a WUQ isolated upgrade output"])
    if isinstance(decision, Mapping):
        payload = dict(decision)
    else:
        payload_value = json.loads(Path(decision).expanduser().read_text(encoding="utf-8"))
        if not isinstance(payload_value, Mapping):
            raise ContractViolation("DESIGN_DECISION_INVALID", ["$: expected a JSON object"])
        payload = dict(payload_value)
    selected_id = str(payload.get("selectedVariantId") or "")
    manifest_path = implementation / "variant-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    variants = [item for item in manifest.get("variants", []) if isinstance(item, Mapping)]
    selected = next((dict(item) for item in variants if str(item.get("id")) == selected_id and item.get("status") == "IMPLEMENTED"), None)
    if selected is None:
        raise ContractViolation("DESIGN_DECISION_INVALID", ["$.selectedVariantId: candidate does not exist or is not implemented"])
    selected_root = implementation / str(selected["root"])
    if not selected_root.is_dir() or selected_root.parent != variants_root:
        raise ContractViolation("DESIGN_DECISION_OUTPUT_INVALID", ["$: selected candidate root is outside the isolated variants directory"])
    if after.is_dir():
        shutil.rmtree(after)
    shutil.copytree(selected_root, after)
    preferences = payload.get("preferences") if isinstance(payload.get("preferences"), Mapping) else {}
    preference_changes = _apply_decision_preferences(after, preferences)
    changed = sorted(set(str(value) for value in selected.get("changedFiles", [])) | set(preference_changes))
    patch_path = implementation / "source-change.patch"
    patch_path.write_text("".join(_diff_file(relative, before, after) for relative in changed), encoding="utf-8")
    change_records = []
    for relative in changed:
        old, new = before / relative, after / relative
        if not new.is_file():
            continue
        change_records.append({
            "path": relative,
            "operation": "modify" if old.is_file() else "add",
            "beforeSha256": _sha256(old) if old.is_file() else None,
            "afterSha256": _sha256(new),
            "bytes": new.stat().st_size,
        })
    change_manifest_path = implementation / "change-manifest.json"
    change_manifest = json.loads(change_manifest_path.read_text(encoding="utf-8")) if change_manifest_path.is_file() else {}
    change_manifest.update({
        "generator": release_identity(),
        "status": "IMPLEMENTED_IN_ISOLATED_COPY",
        "selectedVariantId": selected_id,
        "mode": selected.get("mode"),
        "changes": change_records,
        "patch": {"path": patch_path.name, "sha256": _sha256(patch_path), "bytes": patch_path.stat().st_size},
    })
    change_manifest_path.write_text(json.dumps(change_manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest["selectedVariantId"] = selected_id
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    plan_path = implementation / "implementation-plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan.update({
        "selectedVariantId": selected_id,
        "selectedDirection": {"id": selected_id, "name": selected.get("name"), "outcome": selected.get("outcome"), "tradeoff": selected.get("tradeoff")},
        "mode": selected.get("mode"),
        "changedFiles": changed,
        "selectionStatus": "HUMAN_DECISION_FINALIZED",
    })
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    receipt = {
        "schemaVersion": "1",
        "generator": release_identity(),
        "status": "DESIGN_SELECTION_FINALIZED",
        "selectedVariantId": selected_id,
        "preferences": dict(preferences),
        "notes": payload.get("notes") if isinstance(payload.get("notes"), Mapping) else {},
        "patch": "source-change.patch",
        "sourceProjectChanged": False,
        "browserRevalidationRequiredAfterPreferenceChange": bool(preference_changes),
    }
    (implementation / "design-decision-receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt
