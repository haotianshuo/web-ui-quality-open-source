"""Project visual-language extraction and DTCG-compatible token mapping."""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence


_VAR = re.compile(r"(--[A-Za-z0-9_-]+)\s*:\s*([^;{}]+)")
_COLOR = re.compile(r"(?i)(#[0-9a-f]{3,8}\b|rgba?\([^)]*\)|hsla?\([^)]*\)|oklch\([^)]*\)|color\([^)]*\))")
_RADIUS = re.compile(r"(?i)border-radius\s*:\s*([^;{}]+)")
_SHADOW = re.compile(r"(?i)box-shadow\s*:\s*([^;{}]+)")
_FONT_FAMILY = re.compile(r"(?i)font-family\s*:\s*([^;{}]+)")
_FONT_SIZE = re.compile(r"(?i)font-size\s*:\s*([^;{}]+)")
_SPACING = re.compile(r"(?i)(?:gap|padding(?:-[a-z]+)?|margin(?:-[a-z]+)?)\s*:\s*([^;{}]+)")
_LENGTH = re.compile(r"(?<![\w-])(-?\d+(?:\.\d+)?(?:px|rem|em))\b", re.I)


def _top(counter: Counter[str], limit: int = 12) -> list[dict[str, Any]]:
    return [{"value": value, "count": count} for value, count in counter.most_common(limit)]


def _type_for(value: str, kind: str) -> str:
    if kind == "color": return "color"
    if kind in {"radius", "spacing", "font-size"}: return "dimension"
    if kind == "shadow": return "shadow"
    if kind == "font-family": return "fontFamily"
    return "string"


def _dtcg_token(value: str, kind: str) -> dict[str, Any]:
    token_type = _type_for(value, kind)
    if token_type == "dimension":
        match = re.fullmatch(r"(-?\d+(?:\.\d+)?)(px|rem|em)", value.strip(), re.I)
        if match:
            return {"$type": "dimension", "$value": {"value": float(match.group(1)), "unit": match.group(2).lower()}}
    if token_type == "fontFamily":
        values = [part.strip().strip("'\"") for part in value.split(",") if part.strip()]
        return {"$type": "fontFamily", "$value": values}
    # DTCG's stable format supports structured colour values, but raw CSS values
    # are preserved as strings when conversion would be lossy.  The extension
    # records the intended semantic type for downstream resolvers.
    return {"$type": token_type if token_type != "color" else "string", "$value": value.strip(), "$extensions": {"org.web-ui-quality.semanticType": token_type}}


def _semantic_aliases(variables: Mapping[str, str], colours: Counter[str]) -> dict[str, str]:
    lowered = {key.casefold(): value for key, value in variables.items()}
    aliases: dict[str, str] = {}
    candidates = {
        "color.background.canvas": ("--background", "--bg", "--page-bg", "--body-bg"),
        "color.background.surface": ("--surface", "--card", "--panel", "--container-bg"),
        "color.text.primary": ("--foreground", "--text", "--text-primary", "--color-text"),
        "color.text.secondary": ("--muted-foreground", "--text-secondary", "--muted", "--color-text-secondary"),
        "color.border.default": ("--border", "--line", "--divider", "--color-border"),
        "color.action.primary": ("--primary", "--brand", "--accent", "--color-primary"),
        "color.status.success": ("--success", "--green", "--color-success"),
        "color.status.warning": ("--warning", "--orange", "--color-warning"),
        "color.status.danger": ("--danger", "--destructive", "--red", "--color-danger"),
    }
    for semantic, keys in candidates.items():
        for key in keys:
            if key in lowered:
                aliases[semantic] = key
                break
    if colours and "color.action.primary" not in aliases:
        aliases["color.action.primary"] = colours.most_common(1)[0][0]
    return aliases


def build_design_system_map(sources: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    variables: dict[str, str] = {}
    colours: Counter[str] = Counter(); radii: Counter[str] = Counter(); shadows: Counter[str] = Counter()
    fonts: Counter[str] = Counter(); font_sizes: Counter[str] = Counter(); spacings: Counter[str] = Counter()
    css_files = 0; total_declarations = 0; variable_uses = 0
    for source in sources:
        path = str(source.get("path") or "")
        if Path(path).suffix.casefold() != ".css": continue
        css_files += 1; text = str(source.get("text") or "")
        for name, value in _VAR.findall(text): variables[name] = value.strip()
        colours.update(value.strip() for value in _COLOR.findall(text))
        radii.update(value.strip() for value in _RADIUS.findall(text))
        shadows.update(value.strip() for value in _SHADOW.findall(text) if value.strip().casefold() != "none")
        fonts.update(value.strip() for value in _FONT_FAMILY.findall(text))
        font_sizes.update(value.strip() for value in _FONT_SIZE.findall(text))
        for value in _SPACING.findall(text):
            spacings.update(match.group(0) for match in _LENGTH.finditer(value))
        total_declarations += len(re.findall(r"(?m)[\w-]+\s*:\s*[^;{}]+", text))
        variable_uses += len(re.findall(r"var\(--[\w-]+", text))

    aliases = _semantic_aliases(variables, colours)
    hard_coded_colours = sum(colours.values())
    token_reuse_ratio = round(variable_uses / max(1, total_declarations) * 100, 1)
    colour_token_ratio = round(len(variables) / max(1, len(variables) + hard_coded_colours) * 100, 1)
    spacing_values = [float(match.group(1)) for value in spacings for match in [re.match(r"(-?\d+(?:\.\d+)?)", value)] if match]
    coherent_spacing = 100.0
    if spacing_values:
        near_grid = sum(abs(value / 4 - round(value / 4)) < 0.1 for value in spacing_values)
        coherent_spacing = round(near_grid / len(spacing_values) * 100, 1)
    consistency = round(token_reuse_ratio * 0.35 + colour_token_ratio * 0.35 + coherent_spacing * 0.30)

    dtcg: dict[str, Any] = {
        "$description": "Web UI Quality extracted project token map. Review before production use.",
        "project": {
            "raw": {
                "cssVariables": {name.removeprefix("--").replace("-", "."): _dtcg_token(value, "string") for name, value in sorted(variables.items())},
                "colors": {f"color-{index+1}": _dtcg_token(item["value"], "color") for index, item in enumerate(_top(colours, 16))},
                "radius": {f"radius-{index+1}": _dtcg_token(item["value"], "radius") for index, item in enumerate(_top(radii, 8))},
                "spacing": {f"space-{index+1}": _dtcg_token(item["value"], "spacing") for index, item in enumerate(_top(spacings, 12))},
                "fontSize": {f"size-{index+1}": _dtcg_token(item["value"], "font-size") for index, item in enumerate(_top(font_sizes, 10))},
                "fontFamily": {f"family-{index+1}": _dtcg_token(item["value"], "font-family") for index, item in enumerate(_top(fonts, 6))},
            }
        },
    }
    compatibility_lines = [":root {"]
    semantic_defaults = {
        "color.background.canvas": "oklch(0.975 0.006 250)", "color.background.surface": "oklch(0.995 0.002 250)",
        "color.text.primary": "oklch(0.22 0.025 255)", "color.text.secondary": "oklch(0.52 0.025 255)",
        "color.border.default": "oklch(0.90 0.015 250)", "color.action.primary": "oklch(0.57 0.18 255)",
        "color.status.success": "oklch(0.58 0.15 155)", "color.status.warning": "oklch(0.70 0.16 80)",
        "color.status.danger": "oklch(0.58 0.21 28)",
    }
    for semantic, fallback in semantic_defaults.items():
        alias = aliases.get(semantic)
        css_name = "--wuq-" + semantic.replace(".", "-")
        compatibility_lines.append(f"  {css_name}: {'var(' + alias + ', ' + fallback + ')' if alias and alias.startswith('--') else alias or fallback};")
    compatibility_lines.append("}")

    return {
        "schemaVersion": "1.0", "cssFiles": css_files, "cssVariableCount": len(variables),
        "metrics": {"tokenReuseRatio": token_reuse_ratio, "colourTokenRatio": colour_token_ratio, "spacingGridCoherence": coherent_spacing, "consistencyScore": consistency},
        "semanticAliases": aliases,
        "inventory": {"variables": dict(sorted(variables.items())), "colors": _top(colours, 16), "radii": _top(radii, 8), "shadows": _top(shadows, 8), "fontFamilies": _top(fonts, 6), "fontSizes": _top(font_sizes, 10), "spacing": _top(spacings, 12)},
        "dtcg": dtcg, "compatibilityCss": "\n".join(compatibility_lines) + "\n",
        "recommendations": [
            "优先将现有变量映射为背景、表面、文字、边界、操作和状态语义 Token",
            "保留项目已有品牌语言，只有对比、状态或一致性不足时才替换具体数值",
            "设计 Token 与组件结构解耦，避免通过高特异性 CSS 覆盖第三方组件",
            "导出的 DTCG Token 需要设计与前端共同复核后再成为生产单一事实源",
        ],
    }
