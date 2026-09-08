"""Deterministic, progressive-enhancement visual-system generator."""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping


_DIRECTIONS: dict[str, dict[str, Any]] = {
    "enterprise-neutral": {
        "name": "Enterprise Neutral", "description": "中性、可靠、适合多数 B2B 后台。",
        "light": {"bg":"oklch(0.975 0.006 250)","surface":"oklch(0.995 0.002 250)","text":"oklch(0.22 0.025 255)","muted":"oklch(0.52 0.025 255)","line":"oklch(0.90 0.015 250)","brand":"oklch(0.57 0.18 255)","brandStrong":"oklch(0.48 0.19 255)","success":"oklch(0.58 0.15 155)","warning":"oklch(0.70 0.16 80)","danger":"oklch(0.58 0.21 28)"},
        "dark": {"bg":"oklch(0.16 0.02 255)","surface":"oklch(0.21 0.02 255)","text":"oklch(0.94 0.01 255)","muted":"oklch(0.72 0.02 255)","line":"oklch(0.32 0.02 255)","brand":"oklch(0.72 0.15 255)","brandStrong":"oklch(0.78 0.13 255)","success":"oklch(0.72 0.13 155)","warning":"oklch(0.78 0.14 80)","danger":"oklch(0.70 0.18 28)"},
        "radius":"12px", "shadow":"0 12px 32px color-mix(in oklab, black 8%, transparent)", "density":"comfortable", "material":"solid-layered",
    },
    "apple-clarity": {
        "name":"Apple-inspired Clarity", "description":"内容优先、克制材质、连续状态变化。",
        "light":{"bg":"oklch(0.985 0.004 250)","surface":"oklch(1 0 0)","text":"oklch(0.18 0.01 250)","muted":"oklch(0.49 0.015 250)","line":"oklch(0.90 0.008 250)","brand":"oklch(0.60 0.19 250)","brandStrong":"oklch(0.50 0.21 250)","success":"oklch(0.62 0.16 150)","warning":"oklch(0.72 0.17 75)","danger":"oklch(0.60 0.22 27)"},
        "dark":{"bg":"oklch(0.12 0.008 250)","surface":"oklch(0.19 0.01 250)","text":"oklch(0.96 0.005 250)","muted":"oklch(0.72 0.012 250)","line":"oklch(0.30 0.01 250)","brand":"oklch(0.72 0.16 250)","brandStrong":"oklch(0.78 0.14 250)","success":"oklch(0.72 0.14 150)","warning":"oklch(0.78 0.15 75)","danger":"oklch(0.72 0.18 27)"},
        "radius":"18px", "shadow":"0 20px 60px color-mix(in oklab, black 10%, transparent)", "density":"comfortable", "material":"controlled-glass",
    },
    "modern-chinese-tech": {
        "name":"Modern Chinese Tech", "description":"清晰层级、强品牌焦点和高效企业组件。",
        "light":{"bg":"oklch(0.972 0.01 220)","surface":"oklch(0.995 0.003 220)","text":"oklch(0.23 0.03 225)","muted":"oklch(0.50 0.035 225)","line":"oklch(0.88 0.025 220)","brand":"oklch(0.62 0.18 210)","brandStrong":"oklch(0.52 0.20 210)","success":"oklch(0.60 0.16 155)","warning":"oklch(0.72 0.17 80)","danger":"oklch(0.59 0.22 25)"},
        "dark":{"bg":"oklch(0.15 0.025 225)","surface":"oklch(0.20 0.025 225)","text":"oklch(0.95 0.01 225)","muted":"oklch(0.72 0.025 225)","line":"oklch(0.31 0.03 225)","brand":"oklch(0.73 0.14 210)","brandStrong":"oklch(0.79 0.12 210)","success":"oklch(0.72 0.13 155)","warning":"oklch(0.79 0.14 80)","danger":"oklch(0.72 0.18 25)"},
        "radius":"10px", "shadow":"0 10px 28px color-mix(in oklab, black 9%, transparent)", "density":"compact", "material":"solid-crisp",
    },
    "warm-professional": {
        "name":"Warm Professional", "description":"适合教育、服务和长期阅读的温和专业风格。",
        "light":{"bg":"oklch(0.975 0.018 85)","surface":"oklch(0.995 0.008 85)","text":"oklch(0.24 0.035 55)","muted":"oklch(0.52 0.035 55)","line":"oklch(0.89 0.03 80)","brand":"oklch(0.58 0.16 45)","brandStrong":"oklch(0.49 0.17 45)","success":"oklch(0.58 0.14 145)","warning":"oklch(0.70 0.16 80)","danger":"oklch(0.58 0.20 28)"},
        "dark":{"bg":"oklch(0.16 0.02 55)","surface":"oklch(0.21 0.025 55)","text":"oklch(0.94 0.015 80)","muted":"oklch(0.72 0.025 70)","line":"oklch(0.32 0.03 55)","brand":"oklch(0.72 0.13 45)","brandStrong":"oklch(0.78 0.12 45)","success":"oklch(0.70 0.12 145)","warning":"oklch(0.77 0.14 80)","danger":"oklch(0.70 0.17 28)"},
        "radius":"16px", "shadow":"0 14px 36px color-mix(in oklab, black 8%, transparent)", "density":"comfortable", "material":"soft-layered",
    },
    "dense-operations": {
        "name":"Dense Operations", "description":"适合专业高频操作、数据比较和键盘工作流。",
        "light":{"bg":"oklch(0.965 0.005 255)","surface":"oklch(0.995 0.002 255)","text":"oklch(0.20 0.02 255)","muted":"oklch(0.48 0.02 255)","line":"oklch(0.86 0.015 255)","brand":"oklch(0.55 0.17 260)","brandStrong":"oklch(0.46 0.18 260)","success":"oklch(0.55 0.15 150)","warning":"oklch(0.68 0.16 75)","danger":"oklch(0.55 0.20 25)"},
        "dark":{"bg":"oklch(0.14 0.02 255)","surface":"oklch(0.19 0.02 255)","text":"oklch(0.94 0.01 255)","muted":"oklch(0.70 0.02 255)","line":"oklch(0.30 0.02 255)","brand":"oklch(0.70 0.14 260)","brandStrong":"oklch(0.76 0.12 260)","success":"oklch(0.69 0.13 150)","warning":"oklch(0.76 0.14 75)","danger":"oklch(0.68 0.17 25)"},
        "radius":"8px", "shadow":"0 8px 22px color-mix(in oklab, black 7%, transparent)", "density":"dense", "material":"solid-crisp",
    },
    "field-friendly": {
        "name":"Field Friendly", "description":"高对比、大触控、单手和弱网提示优先。",
        "light":{"bg":"oklch(0.98 0.008 115)","surface":"oklch(1 0 0)","text":"oklch(0.18 0.025 130)","muted":"oklch(0.44 0.03 130)","line":"oklch(0.84 0.04 120)","brand":"oklch(0.54 0.17 145)","brandStrong":"oklch(0.43 0.18 145)","success":"oklch(0.52 0.16 145)","warning":"oklch(0.67 0.18 75)","danger":"oklch(0.54 0.22 28)"},
        "dark":{"bg":"oklch(0.13 0.02 130)","surface":"oklch(0.19 0.025 130)","text":"oklch(0.96 0.01 120)","muted":"oklch(0.75 0.03 120)","line":"oklch(0.35 0.04 130)","brand":"oklch(0.72 0.15 145)","brandStrong":"oklch(0.80 0.13 145)","success":"oklch(0.72 0.14 145)","warning":"oklch(0.80 0.15 75)","danger":"oklch(0.72 0.19 28)"},
        "radius":"14px", "shadow":"0 10px 30px color-mix(in oklab, black 10%, transparent)", "density":"touch", "material":"high-contrast-solid",
    },
    "ai-workspace": {
        "name":"AI Workspace", "description":"面向生成、工具调用、引用和多版本协作。",
        "light":{"bg":"oklch(0.972 0.012 285)","surface":"oklch(0.995 0.004 285)","text":"oklch(0.21 0.03 285)","muted":"oklch(0.50 0.035 285)","line":"oklch(0.88 0.025 285)","brand":"oklch(0.60 0.21 300)","brandStrong":"oklch(0.51 0.22 300)","success":"oklch(0.60 0.15 155)","warning":"oklch(0.72 0.16 80)","danger":"oklch(0.59 0.21 25)"},
        "dark":{"bg":"oklch(0.14 0.025 285)","surface":"oklch(0.20 0.03 285)","text":"oklch(0.95 0.01 285)","muted":"oklch(0.72 0.03 285)","line":"oklch(0.32 0.035 285)","brand":"oklch(0.74 0.16 300)","brandStrong":"oklch(0.80 0.14 300)","success":"oklch(0.72 0.13 155)","warning":"oklch(0.79 0.14 80)","danger":"oklch(0.72 0.18 25)"},
        "radius":"14px", "shadow":"0 16px 42px color-mix(in oklab, black 9%, transparent)", "density":"comfortable", "material":"layered-glow",
    },
}


def select_direction(model: Mapping[str, Any], pattern_id: str, override: str | None = None) -> str:
    if override:
        if override not in _DIRECTIONS: raise KeyError(override)
        return override
    if pattern_id == "mobile-field" or model.get("environment") == "mobile-field": return "field-friendly"
    if pattern_id == "ai-workspace": return "ai-workspace"
    if model.get("informationDensity") == "high" and model.get("userExpertise") == "expert": return "dense-operations"
    personality = str(model.get("brandPersonality") or "").casefold()
    if any(x in personality for x in ("warm", "温暖", "教育", "service")): return "warm-professional"
    if any(x in personality for x in ("apple", "minimal", "简洁", "premium")): return "apple-clarity"
    if any(x in personality for x in ("科技", "tech", "活力", "modern")): return "modern-chinese-tech"
    return "enterprise-neutral"


def build_visual_system(model: Mapping[str, Any], pattern_id: str, *, override: str | None = None) -> dict[str, Any]:
    direction_id = select_direction(model, pattern_id, override)
    base = deepcopy(_DIRECTIONS[direction_id])
    density = base["density"]
    if model.get("userExpertise") == "novice" and density == "dense": density = "comfortable"
    if model.get("devicePriority") == "mobile": density = "touch"
    control_height = {"dense":"32px","compact":"36px","comfortable":"40px","touch":"48px"}.get(density, "40px")
    space_unit = {"dense":"4px","compact":"4px","comfortable":"4px","touch":"5px"}.get(density, "4px")
    type_scale = {"caption":"12px","body":"14px","bodyStrong":"14px","section":"16px","page":"22px","hero":"30px"}
    line_height = {"caption":1.45,"body":1.55,"section":1.4,"page":1.25,"hero":1.15}
    if density == "touch": type_scale.update({"body":"15px","section":"17px","page":"24px"})
    spacing_scale = {"0":"0","1":space_unit,"2":f"calc({space_unit} * 2)","3":f"calc({space_unit} * 3)","4":f"calc({space_unit} * 4)","5":f"calc({space_unit} * 5)","6":f"calc({space_unit} * 6)","8":f"calc({space_unit} * 8)","10":f"calc({space_unit} * 10)"}
    radius_scale = {"sm":"max(4px, calc("+base["radius"]+" * .55))","md":base["radius"],"lg":"calc("+base["radius"]+" * 1.35)","pill":"999px"}
    elevation = {"0":"none","1":"0 1px 2px color-mix(in oklab, black 6%, transparent)","2":base["shadow"],"3":"0 24px 72px color-mix(in oklab, black 14%, transparent)"}
    chart_palette = [base["light"]["brand"], base["light"]["success"], base["light"]["warning"], "oklch(0.62 0.16 315)", "oklch(0.65 0.14 200)"]
    components = {
        "button":{"height":control_height,"paddingInline":"16px" if density != "dense" else "12px","radius":radius_scale["md"],"fontWeight":650},
        "input":{"height":control_height,"paddingInline":"12px","radius":radius_scale["md"],"focusRing":"0 0 0 3px color-mix(in oklab, var(--wuq-brand) 24%, transparent)"},
        "card":{"padding":"20px" if density == "comfortable" else "14px","radius":radius_scale["lg"],"elevation":elevation["1"]},
        "table":{"rowHeight":"44px" if density == "dense" else "52px" if density == "comfortable" else "56px","headerHeight":"40px","cellPadding":"10px 12px"},
        "dialog":{"maxWidth":"min(720px, calc(100vw - 32px))","maxHeight":"min(88dvh, 860px)","radius":radius_scale["lg"]},
        "sidebar":{"width":"248px","collapsedWidth":"68px","itemHeight":"40px" if density != "touch" else "48px"},
        "toast":{"maxWidth":"min(420px, calc(100vw - 32px))","duration":"4200ms"},
    }
    tokens = {
        "directionId": direction_id, "directionName": base["name"], "description": base["description"],
        "light": base["light"], "dark": base["dark"], "radius": base["radius"], "shadow": base["shadow"],
        "density": density, "material": base["material"], "controlHeight": control_height,
        "spaceUnit": space_unit, "spacingScale": spacing_scale, "radiusScale": radius_scale, "elevation": elevation,
        "typeScale": type_scale, "lineHeight": line_height,
        "motion": {"instant":"0ms","fast":"120ms","standard":"180ms","slow":"260ms","deliberate":"360ms","easing":"cubic-bezier(.2,.8,.2,1)","exitEasing":"cubic-bezier(.4,0,1,1)","reduced":"1ms"},
        "layout": {"contentMax":"1440px","readingMax":"760px","sidebar":"248px","detail":"minmax(320px, 42%)","gutter":"clamp(14px, 2vw, 28px)","safeBottom":"env(safe-area-inset-bottom, 0px)"},
        "focus":{"width":"3px","offset":"2px","style":"solid","colour":"color-mix(in oklab, var(--wuq-brand) 72%, white)"},
        "icons":{"small":"16px","medium":"20px","large":"24px","stroke":"1.75" if density != "dense" else "1.5"},
        "charts":{"palette":chart_palette,"grid":"color-mix(in oklab, var(--wuq-line) 72%, transparent)","positive":base["light"]["success"],"negative":base["light"]["danger"]},
        "components": components,
        "responsive":{"compactContainer":"520px","mediumContainer":"760px","wideContainer":"1080px","strategy":"container-first"},
        "technologyPolicy":{"nativeFirst":True,"progressiveEnhancement":True,"reducedMotionRequired":True,"criticalPathExperimentalFeatures":False},
    }
    tokens["dtcg"] = dtcg_tokens(tokens)
    tokens["css"] = css_variables(tokens)
    return tokens


def _dimension(value: str) -> dict[str, Any]:
    import re
    match = re.fullmatch(r"(-?\d+(?:\.\d+)?)(px|rem|em|ms)", value.strip())
    if not match: return {"$type":"string","$value":value}
    unit = match.group(2)
    token_type = "duration" if unit == "ms" else "dimension"
    return {"$type":token_type,"$value":{"value":float(match.group(1)),"unit":unit}}


def dtcg_tokens(system: Mapping[str, Any]) -> dict[str, Any]:
    light = system["light"]; dark = system["dark"]
    return {
        "$description":"Web UI Quality generated visual system; review and map to project tokens before production.",
        "color": {
            "light": {key:{"$type":"string","$value":value,"$extensions":{"org.web-ui-quality.semanticType":"color"}} for key,value in light.items()},
            "dark": {key:{"$type":"string","$value":value,"$extensions":{"org.web-ui-quality.semanticType":"color"}} for key,value in dark.items()},
        },
        "spacing": {key:_dimension(value) for key,value in system["spacingScale"].items()},
        "radius": {key:{"$type":"string","$value":value} for key,value in system["radiusScale"].items()},
        "typography": {"fontSize":{key:_dimension(value) for key,value in system["typeScale"].items()}},
        "motion": {key:_dimension(value) if str(value).endswith("ms") else {"$type":"cubicBezier","$value":[0.2,0.8,0.2,1]} for key,value in system["motion"].items() if key not in {"exitEasing"}},
    }


def css_variables(system: Mapping[str, Any]) -> str:
    light = system["light"]; dark = system["dark"]; ts = system["typeScale"]; motion = system["motion"]
    vars_light = "\n".join(f"  --wuq-{k}: {v};" for k, v in light.items())
    vars_dark = "\n".join(f"  --wuq-{k}: {v};" for k, v in dark.items())
    spacing = "\n".join(f"  --wuq-space-{k}: {v};" for k,v in system["spacingScale"].items())
    radii = "\n".join(f"  --wuq-radius-{k}: {v};" for k,v in system["radiusScale"].items())
    elevations = "\n".join(f"  --wuq-elevation-{k}: {v};" for k,v in system["elevation"].items())
    components = system["components"]
    return f"""@layer wuq.tokens, wuq.base, wuq.components, wuq.utilities;
@layer wuq.tokens {{
:root {{
{vars_light}
{spacing}
{radii}
{elevations}
  --wuq-radius: {system['radius']};
  --wuq-shadow: {system['shadow']};
  --wuq-control-height: {system['controlHeight']};
  --wuq-space: {system['spaceUnit']};
  --wuq-font-caption: {ts['caption']};
  --wuq-font-body: {ts['body']};
  --wuq-font-section: {ts['section']};
  --wuq-font-page: {ts['page']};
  --wuq-line-body: {system['lineHeight']['body']};
  --wuq-motion-fast: {motion['fast']};
  --wuq-motion-standard: {motion['standard']};
  --wuq-motion-slow: {motion['slow']};
  --wuq-motion-easing: {motion['easing']};
  --wuq-focus-ring: {components['input']['focusRing']};
  --wuq-table-row-height: {components['table']['rowHeight']};
  --wuq-dialog-max-height: {components['dialog']['maxHeight']};
  color-scheme: light dark;
}}
[data-theme='dark'] {{
{vars_dark}
}}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme='light']) {{
{vars_dark}
}} }}
}}
@layer wuq.base {{
*,*::before,*::after {{ box-sizing:border-box; }}
:where(html) {{ text-size-adjust:100%; }}
:where(body) {{ margin:0; font-size:var(--wuq-font-body); line-height:var(--wuq-line-body); background:var(--wuq-bg); color:var(--wuq-text); }}
:where(button,input,select,textarea) {{ font:inherit; }}
:where(button,[href],input,select,textarea,[tabindex]:not([tabindex='-1'])):focus-visible {{ outline:3px solid color-mix(in oklab,var(--wuq-brand) 72%,white); outline-offset:2px; }}
}}
@media (prefers-reduced-motion: reduce) {{ *,*::before,*::after {{ animation-duration: 1ms !important; animation-iteration-count:1 !important; transition-duration: 1ms !important; scroll-behavior: auto !important; }} }}
@supports (field-sizing: content) {{ textarea,input:not([type='checkbox']):not([type='radio']) {{ field-sizing:content; }} }}
"""

def direction_catalog() -> list[dict[str, Any]]:
    return [{"id": key, "name": value["name"], "description": value["description"], "density": value["density"], "material": value["material"]} for key, value in _DIRECTIONS.items()]
