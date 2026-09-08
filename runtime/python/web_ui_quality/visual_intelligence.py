"""Deterministic visual intelligence with explicit evidence authority.

Typography, colour, spacing and hierarchy are analysed from bounded source text
and optional rendered observations. Static findings remain candidates; measured
contrast, geometry and computed type may support high-confidence findings.
"""
from __future__ import annotations

from collections import Counter
from html.parser import HTMLParser
import math
import re
from typing import Any, Mapping, Sequence

from .contracts import digest_json


_COST = {"UX1": 12, "UX2": 7, "UX3": 3}
_SUFFIXES = (".css", ".scss", ".sass", ".less", ".html", ".htm", ".vue", ".svelte", ".jsx", ".tsx")
_BLOCK = re.compile(r"(?is)(?P<selector>[^{}]+)\{(?P<body>[^{}]*)\}")
_DECL = re.compile(r"(?i)(?P<name>-{0,2}[a-z][\w-]*)\s*:\s*(?P<value>[^;{}]+)")
_COLOUR = re.compile(r"(?i)(#[0-9a-f]{3,8}\b|rgba?\([^)]*\)|hsla?\([^)]*\)|oklch\([^)]*\)|color\([^)]*\))")
_PX = re.compile(r"(-?\d+(?:\.\d+)?)px", re.I)
_INTERESTING = {"h1", "h2", "h3", "h4", "h5", "h6", "button", "a"}


def _num(value: Any) -> float | None:
    if isinstance(value, str):
        match = re.search(r"-?\d+(?:\.\d+)?", value)
        value = match.group(0) if match else value
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result == result else None


def _flag(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    lowered = str(value).strip().casefold()
    if lowered in {"true", "yes", "primary", "visible"}:
        return True
    if lowered in {"false", "no", "secondary", "hidden"}:
        return False
    return None


def _maps(value: Any) -> list[Mapping[str, Any]]:
    return [item for item in value if isinstance(item, Mapping)] if isinstance(value, (list, tuple)) else []


def _first(row: Mapping[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = _num(row.get(key))
        if value is not None:
            return value
    return None


class _SemanticHTML(HTMLParser):
    """Collect visible-order heading and action candidates without a DOM dependency."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.items: list[dict[str, Any]] = []
        self._stack: list[dict[str, Any]] = []
        self._order = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {name.casefold(): value or "" for name, value in attrs}
        role = values.get("role", "").casefold()
        if tag.casefold() not in _INTERESTING and role not in {"button", "link", "heading"}:
            return
        self._order += 1
        classes = values.get("class", "")
        self._stack.append({
            "tag": tag.casefold(), "role": role or tag.casefold(), "text": "",
            "id": values.get("id") or None, "class": classes, "order": self._order,
            "href": values.get("href") or None,
            "isPrimary": bool(re.search(r"(?i)(?:^|[\s_-])(?:primary|cta|main-action)(?:$|[\s_-])", classes)),
        })

    def handle_data(self, data: str) -> None:
        if self._stack:
            self._stack[-1]["text"] += data

    def handle_endtag(self, tag: str) -> None:
        if not self._stack:
            return
        for index in range(len(self._stack) - 1, -1, -1):
            if self._stack[index]["tag"] == tag.casefold():
                item = self._stack.pop(index)
                item["text"] = " ".join(str(item["text"]).split())[:160]
                self.items.append(item)
                return

    def close(self) -> None:
        super().close()
        while self._stack:
            item = self._stack.pop()
            item["text"] = " ".join(str(item["text"]).split())[:160]
            self.items.append(item)


def _semantic_items(text: str) -> list[dict[str, Any]]:
    parser = _SemanticHTML()
    try:
        parser.feed(text)
        parser.close()
    except Exception:
        return []
    return sorted(parser.items, key=lambda item: item["order"])


def _parse_colour(value: Any) -> tuple[float, float, float, float] | None:
    text = str(value or "").strip().casefold()
    if text.startswith("#"):
        raw = text[1:]
        if len(raw) in {3, 4}:
            raw = "".join(char * 2 for char in raw)
        if len(raw) not in {6, 8} or not re.fullmatch(r"[0-9a-f]+", raw):
            return None
        channels = [int(raw[index:index + 2], 16) / 255 for index in (0, 2, 4)]
        alpha = int(raw[6:8], 16) / 255 if len(raw) == 8 else 1.0
        return channels[0], channels[1], channels[2], alpha
    match = re.match(r"rgba?\(([^)]+)\)", text)
    if not match:
        return None
    parts = [part.strip() for part in re.split(r"[,/]", match.group(1))]
    if len(parts) < 3:
        return None
    values = []
    for part in parts[:3]:
        number = _num(part)
        if number is None:
            return None
        values.append(max(0.0, min(1.0, number / 100 if "%" in part else number / 255)))
    alpha = _num(parts[3]) if len(parts) > 3 else 1.0
    return values[0], values[1], values[2], max(0.0, min(1.0, alpha or 0.0))


def _luminance(colour: tuple[float, float, float, float]) -> float:
    channels = [value / 12.92 if value <= .03928 else ((value + .055) / 1.055) ** 2.4 for value in colour[:3]]
    return .2126 * channels[0] + .7152 * channels[1] + .0722 * channels[2]


def _contrast(foreground: Any, background: Any) -> float | None:
    fg = _parse_colour(foreground)
    bg = _parse_colour(background)
    if not fg or not bg or fg[3] < .99 or bg[3] < .99:
        return None
    a, b = _luminance(fg), _luminance(bg)
    return round((max(a, b) + .05) / (min(a, b) + .05), 2)


def _source_profile(text: str) -> dict[str, Any]:
    sizes: list[float] = []
    weights: list[int] = []
    line_heights: list[float] = []
    spacing: list[float] = []
    colours: Counter[str] = Counter()
    variables = len(re.findall(r"--[\w-]+\s*:", text))
    selector_type: dict[str, dict[str, Any]] = {}
    primary_selectors: list[str] = []
    for block in _BLOCK.finditer(text):
        selector = " ".join(block.group("selector").split())[:160]
        declarations = {
            item.group("name").casefold(): item.group("value").strip()
            for item in _DECL.finditer(block.group("body"))
        }
        if "font-size" in declarations:
            value = _num(declarations["font-size"])
            if value is not None and "px" in declarations["font-size"].casefold():
                sizes.append(value)
        if "font-weight" in declarations:
            value = _num(declarations["font-weight"])
            if value is not None:
                weights.append(int(value))
        if "line-height" in declarations:
            value = _num(declarations["line-height"])
            if value is not None:
                line_heights.append(value)
        for name, value in declarations.items():
            if name in {"gap", "row-gap", "column-gap", "padding", "padding-inline", "padding-block", "margin", "margin-inline", "margin-block"}:
                spacing.extend(float(number) for number in _PX.findall(value) if 0 < float(number) <= 160)
            colours.update(match.group(0).casefold() for match in _COLOUR.finditer(value))
        lower = selector.casefold()
        if re.search(r"(?:^|[\s.#_-])(?:primary|cta|main-action)(?:$|[\s.#_:-])", lower):
            primary_selectors.append(selector)
        if re.search(r"(^|,|\s)h1(?:\b|[.#:\[])", lower):
            selector_type["h1"] = {"selector": selector, "fontSizePx": _num(declarations.get("font-size"))}
        if re.search(r"(^|,|\s)(?:body|p)(?:\b|[.#:\[])", lower):
            selector_type.setdefault("body", {"selector": selector, "fontSizePx": _num(declarations.get("font-size"))})
    semantic = _semantic_items(text)
    headings = [item for item in semantic if item["tag"].startswith("h")]
    actions = [item for item in semantic if item["tag"] in {"button", "a"} or item["role"] in {"button", "link"}]
    unique_spacing = sorted(set(spacing))
    return {
        "fontSizesPx": sorted(set(sizes)),
        "fontWeights": sorted(set(weights)),
        "lineHeights": sorted(set(line_heights)),
        "colourLiterals": [{"value": value, "count": count} for value, count in colours.most_common(24)],
        "colourLiteralCount": sum(colours.values()),
        "cssVariableCount": variables,
        "spacingValuesPx": unique_spacing,
        "offGridSpacingPx": [value for value in unique_spacing if value % 4 != 0],
        "selectorType": selector_type,
        "primarySelectors": primary_selectors,
        "headings": headings[:40],
        "actions": actions[:80],
    }



def _has_rendered_authority(observed: Mapping[str, Any]) -> bool:
    raw = observed.get("evidenceTier") or observed.get("evidenceMode")
    value = str(raw or "").strip().casefold().replace("_", "-")
    return value in {"browser-measured", "rendered-observation", "mixed-rendered-and-static"}


def _rendered_elements(observed: Mapping[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for key in ("visualElements", "renderedElements", "elements"):
        for item in _maps(observed.get(key)):
            result.append({**dict(item), "viewport": item.get("viewport")})
    raw_viewports = observed.get("viewports")
    rows = raw_viewports.values() if isinstance(raw_viewports, Mapping) else raw_viewports if isinstance(raw_viewports, (list, tuple)) else []
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            continue
        viewport = row.get("id") or row.get("name") or row.get("width") or f"viewport-{index + 1}"
        for key in ("visualElements", "renderedElements", "elements"):
            for item in _maps(row.get(key)):
                result.append({**dict(item), "viewport": item.get("viewport") or viewport})
    return result


def _contrast_observations(observed: Mapping[str, Any], elements: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    result = [dict(item) for item in _maps(observed.get("contrastObservations"))]
    for item in elements:
        ratio = _first(item, "contrastRatio", "contrast")
        if ratio is None:
            ratio = _contrast(item.get("color") or item.get("foreground"), item.get("backgroundColor") or item.get("background"))
        if ratio is not None:
            result.append({
                "selector": item.get("selector") or item.get("id"),
                "text": str(item.get("text") or "")[:100],
                "ratio": ratio,
                "fontSizePx": _first(item, "fontSizePx", "fontSize"),
                "fontWeight": _first(item, "fontWeight"),
                "isPrimary": _flag(item.get("isPrimary")) is True,
                "viewport": item.get("viewport"),
            })
    unique: dict[tuple[Any, ...], dict[str, Any]] = {}
    for item in result:
        key = (item.get("viewport"), item.get("selector"), item.get("text"), _first(item, "ratio", "contrastRatio"))
        unique[key] = item
    return list(unique.values())


def _bounds(item: Mapping[str, Any]) -> tuple[float | None, float | None, float | None, float | None]:
    raw = item.get("bounds") if isinstance(item.get("bounds"), Mapping) else item.get("rect") if isinstance(item.get("rect"), Mapping) else item
    return _first(raw, "x", "left"), _first(raw, "y", "top"), _first(raw, "width"), _first(raw, "height")


def _element_role(item: Mapping[str, Any]) -> str:
    return str(item.get("role") or item.get("tag") or item.get("type") or "unknown").strip().casefold()


def _is_cta(item: Mapping[str, Any]) -> bool:
    if _flag(item.get("isPrimary")) is True or _flag(item.get("isCta")) is True:
        return True
    role = _element_role(item)
    text = " ".join(str(item.get(key) or "") for key in ("class", "name", "id", "text")).casefold()
    return role in {"button", "link", "a"} and bool(re.search(r"\b(?:primary|cta|start|buy|submit|save|create)\b|开始|购买|提交|保存|新建", text))


def _salience(item: Mapping[str, Any], index: int) -> dict[str, Any]:
    role = _element_role(item)
    x, y, width, height = _bounds(item)
    size = _first(item, "fontSizePx", "fontSize") or 16
    weight = _first(item, "fontWeight") or 400
    ratio = _first(item, "contrastRatio", "contrast")
    if ratio is None:
        ratio = _contrast(item.get("color") or item.get("foreground"), item.get("backgroundColor") or item.get("background"))
    area = max(0.0, (width or 0) * (height or 0))
    role_bonus = {"h1": 28, "heading-1": 28, "h2": 16, "heading-2": 16, "button": 12, "link": 5, "a": 5}.get(role, 0)
    if _is_cta(item):
        role_bonus += 20
    if _flag(item.get("decorative")) is True:
        role_bonus -= 30
    top_bonus = max(0.0, 10 - (y or 0) / 100)
    score = min(100.0, size * 1.1 + weight / 55 + min(12, math.log1p(area) * 1.1) + min(15, (ratio or 1) * 2) + role_bonus + top_bonus)
    return {
        "id": item.get("id") or item.get("selector") or f"element-{index + 1}",
        "selector": item.get("selector"),
        "text": str(item.get("text") or item.get("name") or "")[:120],
        "role": role,
        "score": round(score, 2),
        "fontSizePx": size,
        "fontWeight": weight,
        "contrastRatio": ratio,
        "bounds": {"x": x, "y": y, "width": width, "height": height},
        "isCta": _is_cta(item),
        "isPrimary": _flag(item.get("isPrimary")) is True,
        "viewport": item.get("viewport"),
        "evidenceMode": "rendered-observation",
    }


def _focal_sequence(elements: Sequence[Mapping[str, Any]], source: Mapping[str, Any]) -> list[dict[str, Any]]:
    rendered = [_salience(item, index) for index, item in enumerate(elements) if _flag(item.get("visible")) is not False]
    if rendered:
        return sorted(rendered, key=lambda item: (-item["score"], str(item["id"])))[:5]
    candidates = list(source["headings"]) + list(source["actions"])
    static = []
    for item in candidates:
        role = item["tag"]
        score = 75 if role == "h1" else 58 if role == "h2" else 48 if item.get("isPrimary") else 34
        static.append({
            "id": item.get("id") or f"{role}-{item['order']}", "selector": None,
            "text": item.get("text"), "role": role, "score": score,
            "isCta": role in {"button", "a"}, "isPrimary": bool(item.get("isPrimary")),
            "evidenceMode": "static-source", "confidence": "low",
        })
    return sorted(static, key=lambda item: (-item["score"], str(item["id"])))[:5]


def _finding(
    code: str, severity: str, category: str, title: str, explanation: str,
    impact: str, evidence: Any, recommendation: str, verification: Sequence[str],
    confidence: str, evidence_mode: str,
) -> dict[str, Any]:
    return {
        "id": code, "severity": severity, "category": category, "title": title,
        "userExplanation": explanation, "userImpact": impact, "evidence": evidence,
        "recommendation": recommendation,
        "verification": list(verification), "confidence": confidence,
        "evidenceMode": evidence_mode,
    }


def _dimension_status(findings: Sequence[Mapping[str, Any]], category: str, rendered: bool) -> dict[str, Any]:
    items = [item for item in findings if item.get("category") == category]
    if any(item.get("severity") == "UX1" and item.get("evidenceMode") == "rendered-observation" for item in items):
        status = "FAIL"
    elif items:
        status = "CANDIDATE" if not rendered else "PASS_WITH_WARNINGS"
    else:
        status = "PASS" if rendered else "NOT_VERIFIED"
    return {"status": status, "findingCount": len(items), "measured": rendered}


def analyze_visual_intelligence(
    sources: Sequence[Mapping[str, Any]],
    observed: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Analyse typography, colour, spacing, hierarchy and CTA emphasis."""

    observed = observed or {}
    rendered_observed = observed if _has_rendered_authority(observed) else {}
    text = "\n".join(
        str(item.get("text") or "")
        for item in sources
        if str(item.get("path") or "").casefold().endswith(_SUFFIXES)
    )
    source = _source_profile(text)
    elements = _rendered_elements(rendered_observed)
    contrast_rows = _contrast_observations(rendered_observed, elements)
    focal = _focal_sequence(elements, source)
    findings: list[dict[str, Any]] = []
    rendered = bool(elements or contrast_rows)

    small_source = [value for value in source["fontSizesPx"] if value < 12]
    if small_source:
        findings.append(_finding(
            "VISUAL-TYPOGRAPHY-SMALL-SOURCE", "UX2", "typography", "页面包含过小的文字规格",
            "源码中存在小于 12px 的字号，辅助信息在普通显示器、强光或高龄场景下容易变得吃力。",
            "用户会跳过说明、状态或错误信息，增加理解和操作风险。",
            {"fontSizesPx": small_source}, "把重要辅助文字提升到可读字号，并同步检查行高和对比度。",
            ("125%/200% 缩放无裁切", "关键说明在移动强光环境可读"), "medium", "static-source",
        ))
    if len(source["fontSizesPx"]) >= 9 or len(source["fontWeights"]) >= 7:
        findings.append(_finding(
            "VISUAL-TYPOGRAPHY-TOO-MANY-STYLES", "UX2", "typography", "字体层级过多，阅读节奏不稳定",
            "页面使用了过多字号或字重，相近内容看起来像不同层级。",
            "用户难以快速判断标题、正文、说明和状态之间的关系。",
            {"fontSizesPx": source["fontSizesPx"], "fontWeights": source["fontWeights"]},
            "收敛为少量语义化文字角色，并让字号、字重、行高共同表达层级。",
            ("同类内容使用同一文字角色", "只看文字层级即可理解页面结构"), "medium", "static-source",
        ))
    h1 = source["selectorType"].get("h1", {}).get("fontSizePx")
    body = source["selectorType"].get("body", {}).get("fontSizePx")
    if h1 and body and h1 / max(1, body) < 1.3:
        findings.append(_finding(
            "VISUAL-TYPOGRAPHY-FLAT-HIERARCHY", "UX1", "typography", "页面标题与正文缺少清晰层级",
            "主标题和正文的字号过于接近，用户第一眼无法确认当前页面和核心任务。",
            "扫读速度下降，主任务和重要状态容易被普通内容淹没。",
            {"h1FontSizePx": h1, "bodyFontSizePx": body, "ratio": round(h1 / body, 2)},
            "扩大标题与正文的层级差，同时保持克制的字重和行长。",
            ("首次进入可识别页面任务", "标题、章节和正文形成稳定三级层次"), "medium", "static-source",
        ))

    for index, item in enumerate(elements):
        size = _first(item, "fontSizePx", "fontSize")
        line_height = _first(item, "lineHeightPx", "lineHeight")
        text_value = str(item.get("text") or "")
        if size is not None and size < 12 and text_value.strip():
            findings.append(_finding(
                f"VISUAL-TINY-TEXT-{index + 1}", "UX2", "typography", "真实渲染文字过小",
                "这段文字在当前视口小于 12px，正常观看距离下难以稳定阅读。",
                "用户可能忽略状态、说明或下一步，尤其影响移动和低视力场景。",
                {"selector": item.get("selector"), "text": text_value[:100], "fontSizePx": size, "viewport": item.get("viewport")},
                "提升字号并检查文字容器是否仍有足够空间。",
                ("渲染字号不低于项目可读下限", "放大后不裁切"), "high", "rendered-observation",
            ))
        if size and line_height and line_height / size < 1.22 and len(text_value) >= 40:
            findings.append(_finding(
                f"VISUAL-LINE-HEIGHT-{index + 1}", "UX2", "typography", "长文本行距造成阅读压力",
                "长文本的行距过紧，连续阅读时行与行之间难以区分。",
                "用户更容易串行、漏读和疲劳。",
                {"selector": item.get("selector"), "fontSizePx": size, "lineHeightPx": line_height, "ratio": round(line_height / size, 2)},
                "按正文角色提高行高，并控制阅读行长。",
                ("连续三行文本容易跟读", "200% 缩放后不重叠"), "high", "rendered-observation",
            ))

    low_contrast = []
    cta_contrast = []
    for item in contrast_rows:
        ratio = _first(item, "ratio", "contrastRatio")
        size = _first(item, "fontSizePx", "fontSize") or 16
        weight = _first(item, "fontWeight") or 400
        threshold = 3.0 if size >= 24 or (size >= 18.66 and weight >= 700) else 4.5
        if ratio is not None and ratio < threshold:
            row = {**item, "ratio": ratio, "threshold": threshold}
            low_contrast.append(row)
            if _flag(item.get("isPrimary")) is True:
                cta_contrast.append(row)
    if low_contrast:
        findings.append(_finding(
            "VISUAL-COLOR-LOW-CONTRAST", "UX1", "color", "文字与背景对比度不足",
            "部分真实渲染文字与背景过于接近，信息存在但不容易被看见。",
            "用户可能漏读状态、说明或操作标签，低视力和强光环境风险更高。",
            {"count": len(low_contrast), "examples": low_contrast[:10]},
            "调整语义文字/背景 token，并在最终合成背景上重新测量。",
            ("普通文字达到 4.5:1", "大号粗体达到 3:1", "状态不只依赖颜色"), "high", "rendered-observation",
        ))
    if cta_contrast:
        findings.append(_finding(
            "VISUAL-CTA-CONTRAST", "UX1", "hierarchy", "主操作视觉强调不足",
            "主 CTA 的文字与表面对比不足，最重要的下一步没有形成可靠焦点。",
            "用户需要额外寻找操作，或误以为按钮不可用。",
            {"examples": cta_contrast[:6]}, "提高主 CTA 的文字、表面和边界对比，并保持单一主操作。",
            ("主 CTA 标签清晰", "禁用与可用状态可区分", "焦点样式可见"), "high", "rendered-observation",
        ))

    if source["colourLiteralCount"] >= 24 and source["cssVariableCount"] < max(4, source["colourLiteralCount"] // 8):
        findings.append(_finding(
            "VISUAL-COLOR-SYSTEM-FRAGMENTED", "UX2", "color", "颜色规则分散，状态和层级难以保持一致",
            "页面使用了大量颜色字面量，却缺少稳定语义 token。",
            "相同状态可能看起来不同，主色、状态色和 CTA 之间容易互相竞争。",
            {"colourLiteralCount": source["colourLiteralCount"], "cssVariableCount": source["cssVariableCount"]},
            "把颜色收敛为背景、表面、文字、边界、品牌和状态语义 token。",
            ("同一语义使用同一 token", "浅色/深色和高对比模式均可读"), "medium", "static-source",
        ))

    spacing = source["spacingValuesPx"]
    off_grid = source["offGridSpacingPx"]
    if len(spacing) >= 9 and len(off_grid) / len(spacing) >= .35:
        findings.append(_finding(
            "VISUAL-SPACING-RHYTHM", "UX2", "spacing", "页面间距缺少稳定节奏",
            "相近模块使用了过多不同间距，内容的亲疏关系不清楚。",
            "用户需要额外判断哪些内容属于同一任务，页面也显得零散。",
            {"spacingValuesPx": spacing[:30], "offGridRatio": round(len(off_grid) / len(spacing), 3)},
            "把组件内部、模块之间和页面分区收敛到递进的语义间距。",
            ("同类组件使用同一间距角色", "只看间距即可理解分组"), "medium", "static-source",
        ))
    observed_spacing = rendered_observed.get("spacingObservations")
    if isinstance(observed_spacing, Mapping):
        inconsistent = _first(observed_spacing, "inconsistentPairCount", "outlierCount") or 0
        minimum = _first(observed_spacing, "minimumGapPx", "minGapPx")
        if inconsistent > 0 or (minimum is not None and minimum < 8):
            findings.append(_finding(
                "VISUAL-SPACING-OBSERVED", "UX2", "spacing", "真实页面的分组间距不稳定",
                "相邻区域的间隔忽大忽小，或操作之间过于拥挤。",
                "用户更难扫读和判断分组，触控时也更容易误操作。",
                dict(observed_spacing), "用少量语义间距校准同级关系，并优先解决小于 8px 的拥挤操作。",
                ("主要分组节奏一致", "操作之间有清晰触控间隔"), "high", "rendered-observation",
            ))

    primary_source = [item for item in source["actions"] if item.get("isPrimary")]
    primary_rendered = [item for item in elements if _flag(item.get("isPrimary")) is True]
    primary_count = len(primary_rendered) if elements else len(primary_source) + len(source["primarySelectors"])
    if primary_count >= 2:
        findings.append(_finding(
            "VISUAL-CTA-COMPETITION", "UX1" if elements else "UX2", "hierarchy", "多个主操作争夺第一视觉焦点",
            "页面同时把多个动作表现为最高优先级，用户无法快速判断下一步。",
            "决策时间增加，用户可能选择低价值或高风险动作。",
            {"primaryCount": primary_count, "sourceSelectors": source["primarySelectors"][:8]},
            "每个任务上下文只保留一个主 CTA，其余动作降为次要、文字或更多菜单。",
            ("首次进入 3 秒内可指出主操作", "危险操作不与主 CTA 同权重"),
            "high" if elements else "medium", "rendered-observation" if elements else "static-source",
        ))

    first_focus = focal[0] if focal else None
    second_focus = focal[1] if len(focal) > 1 else None
    if first_focus and first_focus["evidenceMode"] == "rendered-observation":
        if first_focus["role"] in {"nav", "navigation", "decorative", "image"} and not first_focus["isCta"]:
            findings.append(_finding(
                "VISUAL-HIERARCHY-FIRST-FOCUS", "UX1", "hierarchy", "用户第一眼看到的不是主任务",
                "导航或装饰元素比页面任务和主操作更醒目。",
                "用户进入页面后需要先过滤无关视觉噪声，才能理解该做什么。",
                {"firstFocus": first_focus, "secondFocus": second_focus},
                "降低非任务元素的面积、对比或强调，把标题、状态或主 CTA 提升为第一焦点。",
                ("第一焦点对应主任务", "第二焦点提供证据或下一步"), "high", "rendered-observation",
            ))
        if second_focus and first_focus.get("isCta") and second_focus.get("isCta") and abs(first_focus["score"] - second_focus["score"]) <= 8:
            findings.append(_finding(
                "VISUAL-HIERARCHY-CTA-TIE", "UX1", "hierarchy", "两个 CTA 的视觉权重几乎相同",
                "第一和第二焦点都是操作，而且强调程度接近。",
                "用户需要停下来比较按钮，而不是自然进入主路径。",
                {"firstFocus": first_focus, "secondFocus": second_focus},
                "明确一个主 CTA，并让第二动作在颜色、尺寸或位置上降级。",
                ("主次操作可在不读文案时区分",), "high", "rendered-observation",
            ))

    page_type = str(observed.get("pageType") or "").casefold()
    if not page_type and any(token in text.casefold() for token in ("landing", "hero", "pricing", "start free", "免费试用")):
        page_type = "landing"
    cta_candidates = [item for item in focal if item.get("isCta")]
    if page_type in {"landing", "marketing", "marketing-landing"} and not cta_candidates and not source["actions"]:
        findings.append(_finding(
            "VISUAL-LANDING-CTA-MISSING", "UX1", "hierarchy", "Landing 首屏缺少明确行动入口",
            "页面说明了内容，但没有给用户一个清楚的下一步。",
            "访问者理解价值后仍不知道如何开始、购买或进一步了解。",
            {"pageType": page_type}, "为核心价值配置一个具体、可验证且唯一的主 CTA。",
            ("首屏主 CTA 可见", "CTA 文案说明结果而非泛化动作"), "medium", "static-source",
        ))

    unique = {item["id"]: item for item in findings}
    findings = sorted(unique.values(), key=lambda item: ({"UX1": 0, "UX2": 1, "UX3": 2}.get(item["severity"], 9), item["id"]))
    rendered_findings = [item for item in findings if item["evidenceMode"] == "rendered-observation"]
    status = (
        "FAIL" if any(item["severity"] == "UX1" and item["evidenceMode"] == "rendered-observation" for item in findings)
        else "PASS_WITH_WARNINGS" if findings else "PASS" if rendered else "NOT_VERIFIED"
    )
    hierarchy = {
        "focalSequence": focal,
        "firstFocus": first_focus,
        "secondFocus": second_focus,
        "ctaHierarchy": {
            "candidateCount": len(cta_candidates),
            "primaryCount": primary_count,
            "primary": [item for item in cta_candidates if item.get("isPrimary")][:3],
            "secondary": [item for item in cta_candidates if not item.get("isPrimary")][:5],
        },
    }
    result: dict[str, Any] = {
        "schemaVersion": "3.1", "status": status,
        "analysisStatus": "MEASURED" if rendered else "CANDIDATE_ONLY",
        "model": {
            "typography": {
                "fontSizesPx": source["fontSizesPx"], "fontWeights": source["fontWeights"],
                "lineHeights": source["lineHeights"], "observedTextCount": len(elements),
            },
            "color": {
                "literals": source["colourLiterals"], "literalCount": source["colourLiteralCount"],
                "cssVariableCount": source["cssVariableCount"],
                "contrastObservationCount": len(contrast_rows), "lowContrastCount": len(low_contrast),
            },
            "spacing": {
                "valuesPx": spacing, "offGridValuesPx": off_grid,
                "renderedObservation": dict(observed_spacing) if isinstance(observed_spacing, Mapping) else None,
            },
            "visualHierarchy": hierarchy,
        },
        "dimensions": {
            category: _dimension_status(findings, category, rendered)
            for category in ("typography", "color", "spacing", "hierarchy")
        },
        "findings": findings,
        "evidenceSummary": {
            "sourceFiles": len(sources), "renderedElementCount": len(elements),
            "contrastObservationCount": len(contrast_rows),
            "renderedFindingCount": len(rendered_findings),
            "staticCandidateCount": len(findings) - len(rendered_findings),
        },
        "score": max(0, 100 - sum(_COST.get(item["severity"], 1) for item in findings)),
        "claimBoundary": "源码中的字体、颜色、间距和 CTA 规则只形成候选；第一/第二视觉焦点与对比度只有在 rendered-observation 下才是当前渲染证据。",
    }
    result["digest"] = digest_json(result)
    return result


__all__ = ["analyze_visual_intelligence"]

