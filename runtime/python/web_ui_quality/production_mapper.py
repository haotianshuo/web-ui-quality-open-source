"""Map Experience Core and Design IR to a reviewable production implementation plan.

The mapper never edits the project.  It discovers the current stack and local
components, recommends permissively licensed components, and emits generated
scaffolds in a separate output directory for human review and Safe Edit later.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import html
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping

from .component_registry import build_install_plan, detect_framework, recommend_components
from .design_ir import walk_nodes
from .scope_policy import collect_project_sources

_SUPPORTED_FRAMEWORKS = {"react", "vue", "svelte", "html"}
_EXTENSIONS = {"react": ".tsx", "vue": ".vue", "svelte": ".svelte", "html": ".html"}
_COMPONENT_NAME = re.compile(r"(?:export\s+(?:default\s+)?(?:function|const|class)\s+|class\s+)([A-Z][A-Za-z0-9_]*)")
_IMPORT = re.compile(r"(?:from\s+|require\()['\"]([^'\"]+)['\"]")

_COMPONENT_ROLE_MAP = {
    "page-header": "navigation", "search-field": "input", "filter-bar": "form",
    "data-table": "data-grid", "master-detail": "drawer", "status-badge": "badge",
    "toast": "toast", "stepper": "tabs", "form-section": "form", "summary-card": "card",
    "upload-zone": "upload", "message-list": "list", "task-board": "list",
    "ai-response": "card", "source-panel": "tabs", "command-bar": "command-menu",
    "approval-panel": "form", "settings-nav": "navigation", "chart-panel": "chart",
}


def _read_text(path: Path, max_bytes: int = 512_000) -> str | None:
    try:
        if path.stat().st_size > max_bytes:
            return None
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None


def discover_local_components(project_root: str | Path) -> dict[str, Any]:
    root = Path(project_root).expanduser().resolve()
    items: list[dict[str, Any]] = []
    imports: set[str] = set()
    paths, _skipped, scope_hygiene = collect_project_sources(
        root, suffixes={".js", ".jsx", ".ts", ".tsx", ".vue", ".svelte", ".html"},
        max_files=500, max_file_bytes=512_000, max_total_bytes=20 * 1024 * 1024,
    )
    for path in paths:
        text = _read_text(path)
        if text is None:
            continue
        relative = str(path.relative_to(root)).replace("\\", "/")
        for package in _IMPORT.findall(text):
            if not package.startswith("."):
                imports.add(package.split("/")[0] if not package.startswith("@") else "/".join(package.split("/")[:2]))
        names = set(_COMPONENT_NAME.findall(text))
        if path.suffix.casefold() in {".vue", ".svelte"}:
            names.add(path.stem)
        if path.suffix.casefold() == ".html" and ("data-component" in text or "<template" in text):
            names.add(path.stem)
        for name in sorted(names):
            items.append({
                "name": name, "path": relative,
                "frameworkHint": "vue" if path.suffix == ".vue" else "svelte" if path.suffix == ".svelte" else "react" if path.suffix in {".jsx", ".tsx"} else "html",
                "qualitySignals": {
                    "hasProps": "props" in text or "defineProps" in text,
                    "hasAria": "aria-" in text or "role=" in text,
                    "hasTests": any((path.parent / f"{path.stem}{suffix}").is_file() for suffix in (".test.tsx", ".test.ts", ".spec.ts", ".spec.js")),
                    "hasStory": any((path.parent / f"{path.stem}{suffix}").is_file() for suffix in (".stories.tsx", ".stories.ts", ".stories.js")),
                },
            })
    return {"components": items, "externalImports": sorted(imports), "scopeHygiene": scope_hygiene}


def _requested_components(plan: Mapping[str, Any], design_ir: Mapping[str, Any] | None) -> list[str]:
    requested: list[str] = []
    skeleton = plan.get("selectedSkeleton") if isinstance(plan.get("selectedSkeleton"), Mapping) else {}
    for raw in skeleton.get("components", []) if isinstance(skeleton.get("components"), list) else []:
        requested.append(_COMPONENT_ROLE_MAP.get(str(raw), str(raw)))
    if design_ir:
        for node in walk_nodes(design_ir):
            kind = str(node.get("type") or "")
            if kind in {"button", "input", "select", "dialog", "drawer", "popover", "tooltip", "tabs", "table"}:
                requested.append("data-grid" if kind == "table" else kind)
    return list(dict.fromkeys(requested or ["navigation", "button", "input", "card", "form"]))


def _local_match(component: str, local: Mapping[str, Any]) -> dict[str, Any] | None:
    terms = {
        "navigation": ("nav", "sidebar", "menu"), "input": ("input", "field", "search"),
        "button": ("button", "action"), "form": ("form", "wizard"), "data-grid": ("table", "grid", "list"),
        "dialog": ("dialog", "modal"), "drawer": ("drawer", "sheet"), "card": ("card", "panel"),
        "toast": ("toast", "notice", "message"), "tabs": ("tabs", "tab"), "upload": ("upload", "dropzone"),
    }.get(component, (component.replace("-", ""),))
    ranked = []
    for item in local.get("components", []) if isinstance(local.get("components"), list) else []:
        haystack = f"{item.get('name','')} {item.get('path','')}".casefold().replace("-", "").replace("_", "")
        score = sum(1 for term in terms if term.replace("-", "") in haystack)
        if score:
            signals = item.get("qualitySignals") or {}
            score += int(bool(signals.get("hasAria"))) + int(bool(signals.get("hasTests"))) + int(bool(signals.get("hasStory")))
            ranked.append((score, item))
    ranked.sort(key=lambda entry: (-entry[0], str(entry[1].get("path"))))
    return deepcopy(ranked[0][1]) if ranked else None


def build_production_plan(
    project_root: str | Path,
    experience_plan: Mapping[str, Any],
    *,
    design_ir: Mapping[str, Any] | None = None,
    target_framework: str | None = None,
) -> dict[str, Any]:
    stack = detect_framework(project_root)
    detected_framework = str(stack["framework"])
    framework = target_framework or detected_framework
    supported = framework in _SUPPORTED_FRAMEWORKS
    local = discover_local_components(project_root)
    requested = _requested_components(experience_plan, design_ir)
    recommendations = recommend_components(requested, framework=framework, existing_imports=local.get("externalImports", []))
    mappings: list[dict[str, Any]] = []
    for rec in recommendations["recommendations"]:
        component = rec["component"]
        local_item = _local_match(component, local)
        mappings.append({
            "role": component,
            "strategy": "reuse-local" if local_item else "adopt-or-generate",
            "localComponent": local_item,
            "recommendedSource": rec.get("recommended"),
            "alternatives": rec.get("alternatives", []),
            "requiredContract": rec.get("requiredContract", []),
            "bindingStatus": "CANDIDATE_ONLY",
        })
    install = build_install_plan(recommendations, stack.get("packageManager"))
    plan = {
        "schemaVersion": "2.2", "status": "REVIEW_REQUIRED" if supported else "FRAMEWORK_NOT_SUPPORTED",
        "project": {"root": ".", **stack},
        "detectedFramework": detected_framework,
        "frameworkSupport": {"supported": supported, "supportedTargets": sorted(_SUPPORTED_FRAMEWORKS), "explicitTargetOverride": target_framework is not None},
        "experienceDigest": experience_plan.get("experienceDigest"),
        "targetFramework": framework,
        "localInventory": local,
        "requestedRoles": requested,
        "componentMappings": mappings,
        "installPlan": install,
        "implementationPhases": [
            {"id": "tokens", "goal": "Map generated semantic tokens to project tokens", "writeAuthority": False},
            {"id": "shell", "goal": "Implement page shell and responsive composition in generated output", "writeAuthority": False},
            {"id": "components", "goal": "Bind local or approved permissive components to each role", "writeAuthority": False},
            {"id": "data", "goal": "Bind real fields, API calls, permission states and telemetry", "writeAuthority": False},
            {"id": "verification", "goal": "Run Browser journeys, visual review and task metrics before Safe Edit", "writeAuthority": False},
        ],
        "qualityGates": [
            "No new component package is installed without explicit approval",
            "Existing project component is preferred when it meets interaction and accessibility contracts",
            "Generated scaffold must compile before any project patch is prepared",
            "Data, API, permission and destructive actions remain unbound until reviewed",
            "Desktop, tablet and mobile states must pass before production application",
        ],
        "limitations": ([f"Framework {framework} is not supported for production scaffold generation; no HTML fallback is claimed."] if not supported else []) + [
            "Component matching is heuristic and does not prove semantic equivalence.",
            "Generated files are scaffolds in a separate output directory, not automatic project edits.",
            "Business data bindings require project-specific review.",
        ],
    }
    plan["planDigest"] = sha256(json.dumps(plan, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return plan


def _page_model(plan: Mapping[str, Any]) -> dict[str, Any]:
    skeleton = plan.get("selectedSkeleton") if isinstance(plan.get("selectedSkeleton"), Mapping) else {}
    model = plan.get("experienceModel") if isinstance(plan.get("experienceModel"), Mapping) else {}
    title = str(model.get("primaryTask") or skeleton.get("name") or "企业体验工作台")
    components = list(skeleton.get("components", [])) if isinstance(skeleton.get("components"), list) else []
    return {
        "title": title,
        "subtitle": str(skeleton.get("goal") or "基于 Experience Core 生成的生产候选界面"),
        "components": components,
        "states": list(skeleton.get("states", [])) if isinstance(skeleton.get("states"), list) else [],
        "primaryAction": str((model.get("operations") or ["继续处理"])[0] if isinstance(model.get("operations"), list) and model.get("operations") else "继续处理"),
    }


def generate_production_scaffold(
    production_plan: Mapping[str, Any],
    experience_plan: Mapping[str, Any],
    output_dir: str | Path,
) -> dict[str, Any]:
    out = Path(output_dir).expanduser().resolve(); out.mkdir(parents=True, exist_ok=True)
    framework = str(production_plan.get("targetFramework") or "")
    if production_plan.get("status") == "FRAMEWORK_NOT_SUPPORTED" or framework not in _SUPPORTED_FRAMEWORKS:
        return {"status": "NOT_SUPPORTED", "framework": framework or None, "reason": "FRAMEWORK_NOT_SUPPORTED", "supportedTargets": sorted(_SUPPORTED_FRAMEWORKS)}
    model = _page_model(experience_plan)
    visual = experience_plan.get("visualSystem") if isinstance(experience_plan.get("visualSystem"), Mapping) else {}
    css = str(visual.get("css") or _fallback_css())
    (out / "experience-tokens.css").write_text(css + "\n" + _scaffold_css(), encoding="utf-8")
    component = _render_framework(framework, model)
    suffix = _EXTENSIONS.get(framework, ".html")
    file_name = f"GeneratedExperience{suffix}" if framework != "html" else "generated-experience.html"
    component_path = out / file_name
    component_path.write_text(component, encoding="utf-8")
    plan_path = out / "production-plan.json"
    plan_path.write_text(json.dumps(production_plan, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    readme = out / "README.md"
    readme.write_text(_readme(framework, file_name, production_plan), encoding="utf-8")
    return {"status": "SCAFFOLD_READY", "framework": framework, "component": component_path.name, "css": "experience-tokens.css", "plan": "production-plan.json", "readme": "README.md"}


def _render_framework(framework: str, model: Mapping[str, Any]) -> str:
    title = json.dumps(str(model["title"]), ensure_ascii=False)
    subtitle = json.dumps(str(model["subtitle"]), ensure_ascii=False)
    action = json.dumps(str(model["primaryAction"]), ensure_ascii=False)
    if framework == "react":
        return f'''import React, {{ useState }} from "react";\nimport "./experience-tokens.css";\n\nexport default function GeneratedExperience() {{\n  const [query, setQuery] = useState("");\n  const [selected, setSelected] = useState("A-1024");\n  const rows = ["A-1024", "B-2048", "C-4096"].filter(x => x.toLowerCase().includes(query.toLowerCase()));\n  return <main className="wuq-page"><header className="wuq-header"><div><p className="wuq-eyebrow">Experience Candidate</p><h1>{{{title}}}</h1><p>{{{subtitle}}}</p></div><button className="wuq-primary">{{{action}}}</button></header><section className="wuq-toolbar"><label>搜索<input value={{query}} onChange={{e=>setQuery(e.target.value)}} placeholder="搜索业务对象" /></label><span>{{rows.length}} 条结果</span></section><section className="wuq-split"><div className="wuq-list">{{rows.map(row=><button key={{row}} onClick={{()=>setSelected(row)}} className={{selected===row?"active":""}}><b>{{row}}</b><span>待处理 · 刚刚更新</span></button>)}}</div><article className="wuq-detail"><span className="wuq-badge">待处理</span><h2>{{selected}}</h2><p>这里绑定真实字段、权限和状态。生成文件不会自动执行生产副作用。</p><div className="wuq-actions"><button>保存草稿</button><button className="wuq-primary">{{{action}}}</button></div></article></section></main>;\n}}\n'''
    if framework == "vue":
        return f'''<script setup>\nimport {{ computed, ref }} from 'vue'\nimport './experience-tokens.css'\nconst title={title}; const subtitle={subtitle}; const primaryAction={action};\nconst query=ref(''); const selected=ref('A-1024'); const all=['A-1024','B-2048','C-4096']; const rows=computed(()=>all.filter(x=>x.toLowerCase().includes(query.value.toLowerCase())))\n</script>\n<template><main class="wuq-page"><header class="wuq-header"><div><p class="wuq-eyebrow">Experience Candidate</p><h1>{{{{ title }}}}</h1><p>{{{{ subtitle }}}}</p></div><button class="wuq-primary">{{{{ primaryAction }}}}</button></header><section class="wuq-toolbar"><label>搜索<input v-model="query" placeholder="搜索业务对象"></label><span>{{{{ rows.length }}}} 条结果</span></section><section class="wuq-split"><div class="wuq-list"><button v-for="row in rows" :key="row" @click="selected=row" :class="{{ active: selected===row }}"><b>{{{{ row }}}}</b><span>待处理 · 刚刚更新</span></button></div><article class="wuq-detail"><span class="wuq-badge">待处理</span><h2>{{{{ selected }}}}</h2><p>这里绑定真实字段、权限和状态。生成文件不会自动执行生产副作用。</p><div class="wuq-actions"><button>保存草稿</button><button class="wuq-primary">{{{{ primaryAction }}}}</button></div></article></section></main></template>\n'''
    if framework == "svelte":
        return f'''<script>\nimport './experience-tokens.css'; let query=''; let selected='A-1024'; const all=['A-1024','B-2048','C-4096']; $: rows=all.filter(x=>x.toLowerCase().includes(query.toLowerCase()));\n</script>\n<main class="wuq-page"><header class="wuq-header"><div><p class="wuq-eyebrow">Experience Candidate</p><h1>{{{title}}}</h1><p>{{{subtitle}}}</p></div><button class="wuq-primary">{{{action}}}</button></header><section class="wuq-toolbar"><label>搜索<input bind:value={{query}} placeholder="搜索业务对象"></label><span>{{rows.length}} 条结果</span></section><section class="wuq-split"><div class="wuq-list">{{#each rows as row}}<button on:click={{()=>selected=row}} class:active={{selected===row}}><b>{{row}}</b><span>待处理 · 刚刚更新</span></button>{{/each}}</div><article class="wuq-detail"><span class="wuq-badge">待处理</span><h2>{{selected}}</h2><p>这里绑定真实字段、权限和状态。生成文件不会自动执行生产副作用。</p><div class="wuq-actions"><button>保存草稿</button><button class="wuq-primary">{{{action}}}</button></div></article></section></main>\n'''
    safe_title = html.escape(str(model["title"]))
    safe_subtitle = html.escape(str(model["subtitle"]))
    safe_action = html.escape(str(model["primaryAction"]))
    return f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{safe_title}</title><link rel="stylesheet" href="experience-tokens.css"></head><body><main class="wuq-page"><header class="wuq-header"><div><p class="wuq-eyebrow">Experience Candidate</p><h1>{safe_title}</h1><p>{safe_subtitle}</p></div><button class="wuq-primary">{safe_action}</button></header><section class="wuq-toolbar"><label>搜索<input id="query" placeholder="搜索业务对象"></label><span id="count">3 条结果</span></section><section class="wuq-split"><div class="wuq-list" id="list"></div><article class="wuq-detail"><span class="wuq-badge">待处理</span><h2 id="selected">A-1024</h2><p>这里绑定真实字段、权限和状态。生成文件不会自动执行生产副作用。</p><div class="wuq-actions"><button>保存草稿</button><button class="wuq-primary">{safe_action}</button></div></article></section></main><script>const all=['A-1024','B-2048','C-4096'],q=document.getElementById('query'),list=document.getElementById('list'),selected=document.getElementById('selected'),count=document.getElementById('count');function render(){{const rows=all.filter(x=>x.toLowerCase().includes(q.value.toLowerCase()));count.textContent=rows.length+' 条结果';list.innerHTML=rows.map(x=>`<button data-id="${{x}}"><b>${{x}}</b><span>待处理 · 刚刚更新</span></button>`).join('');list.querySelectorAll('button').forEach(b=>b.onclick=()=>{{selected.textContent=b.dataset.id;list.querySelectorAll('button').forEach(x=>x.classList.toggle('active',x===b))}})}}q.oninput=render;render();</script></body></html>'''


def _fallback_css() -> str:
    return ":root{--wuq-bg:#f6f7f9;--wuq-surface:#fff;--wuq-text:#17202a;--wuq-muted:#667085;--wuq-line:#dfe5ec;--wuq-brand:#2563eb;--wuq-radius:12px}"


def _scaffold_css() -> str:
    return '''\n*{box-sizing:border-box}body{margin:0;background:var(--wuq-bg,#f6f7f9);color:var(--wuq-text,#17202a);font-family:Inter,"Segoe UI","PingFang SC",sans-serif}.wuq-page{max-width:1280px;margin:auto;padding:clamp(16px,3vw,36px)}.wuq-header,.wuq-toolbar,.wuq-actions{display:flex;align-items:center;justify-content:space-between;gap:16px}.wuq-header{margin-bottom:20px}.wuq-header h1{margin:3px 0;font-size:clamp(24px,3vw,38px);letter-spacing:-.03em}.wuq-header p{margin:0;color:var(--wuq-muted,#667085)}.wuq-eyebrow{text-transform:uppercase;letter-spacing:.12em;font-size:11px}.wuq-primary,button,input{min-height:40px;border-radius:var(--wuq-radius,12px);font:inherit}.wuq-primary{border:0;background:var(--wuq-brand,#2563eb);color:#fff;padding:0 16px;font-weight:700}.wuq-toolbar{padding:12px 14px;border:1px solid var(--wuq-line,#dfe5ec);background:var(--wuq-surface,#fff);border-radius:var(--wuq-radius,12px);margin-bottom:12px}.wuq-toolbar label{display:flex;align-items:center;gap:10px}.wuq-toolbar input{border:1px solid var(--wuq-line,#dfe5ec);padding:0 12px;min-width:min(340px,55vw)}.wuq-split{display:grid;grid-template-columns:minmax(260px,.8fr) minmax(360px,1.4fr);gap:12px;container-type:inline-size}.wuq-list,.wuq-detail{border:1px solid var(--wuq-line,#dfe5ec);background:var(--wuq-surface,#fff);border-radius:var(--wuq-radius,12px);padding:12px}.wuq-list{display:grid;align-content:start;gap:8px}.wuq-list button{display:grid;text-align:left;border:1px solid transparent;background:transparent;padding:12px;color:inherit}.wuq-list button span{color:var(--wuq-muted,#667085);font-size:12px}.wuq-list button:hover,.wuq-list button.active{border-color:color-mix(in oklab,var(--wuq-brand,#2563eb) 40%,transparent);background:color-mix(in oklab,var(--wuq-brand,#2563eb) 8%,transparent)}.wuq-detail{min-height:320px}.wuq-detail h2{font-size:28px}.wuq-badge{display:inline-flex;padding:4px 8px;border-radius:999px;background:#fff3d6;color:#7a4c00;font-size:12px}.wuq-actions{justify-content:flex-end;margin-top:36px}.wuq-actions button{padding:0 14px;border:1px solid var(--wuq-line,#dfe5ec);background:var(--wuq-surface,#fff)}@container(max-width:720px){.wuq-split{grid-template-columns:1fr}.wuq-detail{min-height:260px}}@media(max-width:640px){.wuq-header{align-items:flex-start;flex-direction:column}.wuq-header>.wuq-primary{width:100%}.wuq-toolbar{align-items:stretch;flex-direction:column}.wuq-toolbar label{display:grid}.wuq-toolbar input{min-width:0;width:100%}.wuq-page{padding-bottom:calc(88px + env(safe-area-inset-bottom))}.wuq-actions{position:sticky;bottom:0;padding:12px 0 calc(12px + env(safe-area-inset-bottom));background:var(--wuq-surface,#fff)}}@media(prefers-reduced-motion:no-preference){button{transition:background-color .16s,border-color .16s,transform .16s}button:active{transform:translateY(1px)}}'''


def _readme(framework: str, file_name: str, plan: Mapping[str, Any]) -> str:
    return f'''# Generated Experience Scaffold\n\nFramework: `{framework}`  \nEntry file: `{file_name}`\n\nThis scaffold is generated outside the source project and has **no write authority**.\n\n## Before integration\n\n1. Review `production-plan.json` and component licenses.\n2. Prefer mapped local components over new dependencies.\n3. Bind real API, permissions, validation, and telemetry.\n4. Compile the scaffold in an isolated branch.\n5. Run desktop/tablet/mobile Browser journeys and visual review.\n6. Only then prepare a trusted Safe Edit change set.\n\nSuggested dependency command: `{(plan.get('installPlan') or {}).get('suggestedCommand') or 'none'}`\n'''
