"""Static UX repair planning for layout, interaction, and visual debt.

Rules are intentionally conservative.  They surface likely user-facing problems
and propose framework-neutral repair recipes with a fallback and verification
contract.  The engine never edits source files by itself.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .repair_recipe import build_repair_recipes


@dataclass(frozen=True, slots=True)
class UXRepairFinding:
    id: str
    severity: str
    category: str
    file: str | None
    line: int | None
    evidence: str
    user_impact: str
    repair: str
    modern_option: str
    fallback: str
    verification: tuple[str, ...]
    confidence: str = "medium"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["userImpact"] = data.pop("user_impact")
        data["modernOption"] = data.pop("modern_option")
        data["verification"] = list(data["verification"])
        data["evidenceClass"] = "REPAIR_HINT"
        return data


_CSS_BLOCK = re.compile(r"(?is)(?P<selector>[^{}]+)\{(?P<body>[^{}]*)\}")
_DECLARATION = re.compile(r"(?i)(?P<name>--?[a-z][\w-]*)\s*:\s*(?P<value>[^;{}]+)")
_PX_WIDTH = re.compile(r"(?i)\b(?:width|min-width|max-width)\s*:\s*(\d{3,4})px")
_SMALL_FONT = re.compile(r"(?i)\bfont-size\s*:\s*(?:[0-9](?:\.\d+)?|1[01](?:\.\d+)?)px")
_SMALL_TARGET = re.compile(r"(?i)\b(?:height|min-height)\s*:\s*(?:[12]?\d|3[0-9])px")
_COLOR_LITERAL = re.compile(r"(?i)(?:#[0-9a-f]{3,8}\b|rgba?\([^)]*\)|hsla?\([^)]*\)|oklch\([^)]*\))")
_Z_INDEX = re.compile(r"(?i)\bz-index\s*:\s*(\d+)")
_ABSOLUTE = re.compile(r"(?i)\bposition\s*:\s*absolute\b")
_FIXED = re.compile(r"(?i)\bposition\s*:\s*fixed\b")
_TRANSITION_ALL = re.compile(r"(?i)\btransition(?:-property)?\s*:\s*all\b")
_ANIMATION = re.compile(r"(?i)\b(?:animation|transition)\s*:")
_IMPORTANT = re.compile(r"!important\b", re.I)
_HEIGHT_100VH = re.compile(r"(?i)\b(?:height|min-height)\s*:\s*100vh\b")
_BODY_OVERFLOW = re.compile(r"(?is)(?:html|body)[^{]*\{[^}]*overflow\s*:\s*hidden")
_SAFE_AREA = re.compile(r"env\(safe-area-inset-(?:top|right|bottom|left)\)", re.I)
_CONTAINER_QUERY = re.compile(r"@container\b|container-type\s*:", re.I)
_MEDIA_QUERY = re.compile(r"@media\b", re.I)
_FOCUS_VISIBLE = re.compile(r":focus-visible\b", re.I)
_REDUCED_MOTION = re.compile(r"prefers-reduced-motion", re.I)
_BOX_SIZING = re.compile(r"box-sizing\s*:\s*border-box", re.I)


def _line(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _add(result: list[UXRepairFinding], code: str, *, severity: str, category: str, path: str | None, text: str, offset: int | None, evidence: str, impact: str, repair: str, modern: str, fallback: str, verification: Sequence[str], confidence: str = "medium") -> None:
    suffix = 1 + sum(item.id.startswith(code) for item in result)
    result.append(UXRepairFinding(
        code if suffix == 1 else f"{code}-{suffix}", severity, category, path,
        _line(text, offset) if offset is not None else None, evidence[:260], impact, repair, modern, fallback,
        tuple(verification), confidence,
    ))


def analyze_ux_sources(sources: Sequence[Mapping[str, Any]], observed: Mapping[str, Any] | None = None) -> dict[str, Any]:
    observed = observed or {}
    findings: list[UXRepairFinding] = []
    css_text = "\n".join(str(item.get("text") or "") for item in sources if Path(str(item.get("path") or "")).suffix.casefold() == ".css")
    html_sources = [item for item in sources if Path(str(item.get("path") or "")).suffix.casefold() in {".html", ".htm", ".vue", ".svelte"}]

    for source in sources:
        path = str(source.get("path") or "")
        text = str(source.get("text") or "")
        suffix = Path(path).suffix.casefold()
        if suffix == ".css":
            absolute_count = len(_ABSOLUTE.findall(text))
            if absolute_count >= 6:
                match = _ABSOLUTE.search(text)
                _add(findings, "UX-LAYOUT-ABSOLUTE-OVERUSE", severity="UX1", category="layout", path=path, text=text, offset=match.start() if match else 0,
                     evidence=f"检测到 {absolute_count} 处 absolute 定位", impact="内容变化、字体缩放和窄屏时容易错位、遮挡或留白异常。",
                     repair="将页面级排版改为 Grid/Flex；绝对定位只保留给图标、标记和局部装饰。",
                     modern="使用 CSS Grid subgrid、容器查询和逻辑属性组织区域。", fallback="Flex/Grid 基础布局和媒体查询。",
                     verification=("200% 字体缩放无重叠", "390/768/1440 三档无错位", "动态内容变长后布局仍成立"), confidence="high")
            fixed_widths = list(_PX_WIDTH.finditer(text))
            large = [match for match in fixed_widths if int(match.group(1)) >= 720]
            if large:
                _add(findings, "UX-RESPONSIVE-FIXED-WIDTH", severity="UX1", category="responsive", path=path, text=text, offset=large[0].start(),
                     evidence=f"固定宽度 {large[0].group(1)}px", impact="中间宽度和移动端可能出现横向滚动或内容被裁切。",
                     repair="改为 minmax()、clamp()、百分比和 max-inline-size；明确最小可用宽度。",
                     modern="组件级使用 Container Queries 选择列数和详情布局。", fallback="媒体查询改为单列或可滚动数据区。",
                     verification=("320px 不出现页面级横向滚动", "中间宽度有明确重组", "大屏内容不过度拉伸"), confidence="high")
            if _HEIGHT_100VH.search(text):
                match = _HEIGHT_100VH.search(text)
                _add(findings, "UX-MOBILE-100VH", severity="UX2", category="responsive", path=path, text=text, offset=match.start(),
                     evidence=match.group(0), impact="移动浏览器地址栏和软键盘变化时可能遮挡内容或产生跳动。",
                     repair="优先使用 100dvh，并为旧浏览器提供 min-height:100vh 回退。",
                     modern="使用 dvh/svh/lvh 与 safe-area-inset。", fallback="100vh + JS/CSS 变量修正。",
                     verification=("移动地址栏收起/展开无截断", "软键盘打开后当前字段和主操作可见"))
            if _TRANSITION_ALL.search(text):
                match = _TRANSITION_ALL.search(text)
                _add(findings, "UX-MOTION-TRANSITION-ALL", severity="UX2", category="motion", path=path, text=text, offset=match.start(),
                     evidence=match.group(0), impact="无关属性被动画化，可能造成卡顿、布局抖动和不可预测反馈。",
                     repair="只列出 transform、opacity、color、background-color 等必要属性。",
                     modern="View Transitions 只用于明确的视图连续性；布局动画使用 FLIP 或 Motion。", fallback="即时切换或短 opacity 过渡。",
                     verification=("低端设备交互无明显掉帧", "动画可中断", "reduced motion 下关闭"), confidence="high")
            if _ANIMATION.search(text) and not _REDUCED_MOTION.search(css_text):
                match = _ANIMATION.search(text)
                _add(findings, "UX-MOTION-REDUCED-MISSING", severity="UX1", category="accessibility", path=path, text=text, offset=match.start(),
                     evidence="存在动画/过渡但项目 CSS 未检测到 prefers-reduced-motion", impact="对运动敏感用户可能产生不适，且关键操作反馈无法降级。",
                     repair="增加 prefers-reduced-motion: reduce，缩短或移除非必要运动并关闭平滑滚动。",
                     modern="动画合同同时定义 normal、reduced 和 interrupted 三种路径。", fallback="即时状态切换。",
                     verification=("系统减少动态设置生效", "关闭动画后任务仍可理解"), confidence="high")
            z_values = [(int(match.group(1)), match) for match in _Z_INDEX.finditer(text)]
            if z_values and max(value for value, _ in z_values) >= 1000:
                value, match = max(z_values, key=lambda item: item[0])
                _add(findings, "UX-LAYER-ZINDEX-ESCALATION", severity="UX2", category="layering", path=path, text=text, offset=match.start(),
                     evidence=f"z-index: {value}", impact="弹层、固定栏和通知可能互相覆盖，后续维护需要继续抬高层级。",
                     repair="建立有限层级 Token：base、sticky、dropdown、overlay、modal、toast。",
                     modern="使用 top layer 的 dialog/popover，减少手工 z-index。", fallback="集中定义 6 级 z-index 变量。",
                     verification=("Dialog、Popover、Toast 层级正确", "关闭弹层后页面恢复交互"))
            if _FIXED.search(text) and not _SAFE_AREA.search(css_text):
                match = _FIXED.search(text)
                _add(findings, "UX-MOBILE-SAFE-AREA", severity="UX2", category="responsive", path=path, text=text, offset=match.start(),
                     evidence="存在 fixed 区域但未检测到 safe-area-inset", impact="全面屏设备上底部或顶部操作可能贴近系统区域。",
                     repair="固定操作区加入 env(safe-area-inset-*)，并保留内容底部占位。",
                     modern="结合 dvh 和 safe-area 设计移动固定操作。", fallback="增加稳定内边距。",
                     verification=("iOS/Android 安全区内可点击", "内容不会被固定栏遮挡"))
            important_count = len(_IMPORTANT.findall(text))
            if important_count >= 12:
                match = _IMPORTANT.search(text)
                _add(findings, "UX-CSS-IMPORTANT-DEBT", severity="UX2", category="maintainability", path=path, text=text, offset=match.start() if match else 0,
                     evidence=f"检测到 {important_count} 个 !important", impact="主题、状态和响应式覆盖容易失效，组件组合时产生样式污染。",
                     repair="按 cascade layers、组件作用域和语义 Token 重构优先级。",
                     modern="使用 @layer reset, tokens, base, components, utilities。", fallback="降低选择器特异性并限制局部作用域。",
                     verification=("主题和密度切换无覆盖冲突", "组件迁移后样式不泄漏"))
            literal_colors = len(_COLOR_LITERAL.findall(text))
            variables = len(re.findall(r"--[\w-]+\s*:", text))
            if literal_colors >= 24 and variables < max(4, literal_colors // 8):
                first = _COLOR_LITERAL.search(text)
                _add(findings, "UX-VISUAL-TOKEN-DEBT", severity="UX1", category="visual-system", path=path, text=text, offset=first.start() if first else 0,
                     evidence=f"约 {literal_colors} 个颜色字面量、{variables} 个 CSS 变量", impact="同类状态颜色不一致，品牌、深色和高对比模式难以可靠升级。",
                     repair="抽取背景、表面、文字、边界、品牌和状态语义 Token，并映射现有颜色。",
                     modern="输出 W3C DTCG Token JSON 与 CSS 变量别名。", fallback="集中 :root CSS 变量。",
                     verification=("同一语义只使用一个 Token", "深色模式和状态对比通过"))
            small_fonts = list(_SMALL_FONT.finditer(text))
            if small_fonts:
                _add(findings, "UX-TYPOGRAPHY-SMALL-TEXT", severity="UX2", category="typography", path=path, text=text, offset=small_fonts[0].start(),
                     evidence=small_fonts[0].group(0), impact="辅助信息在普通显示器、强光或高龄用户场景中难以阅读。",
                     repair="正文不低于 14px；关键辅助信息不低于 12px，并使用足够行高和对比。",
                     modern="使用 clamp() 建立流体字号，但限制上下界。", fallback="固定可读字号阶梯。",
                     verification=("125%/150% 缩放后无裁切", "移动强光场景可读"))
            if not _BOX_SIZING.search(css_text):
                _add(findings, "UX-LAYOUT-BOX-SIZING", severity="UX3", category="layout", path=path, text=text, offset=0,
                     evidence="未检测到全局 border-box", impact="控件宽高包含边框和内边距时容易超出容器。",
                     repair="增加 *,*::before,*::after{box-sizing:border-box}。",
                     modern="与容器查询和逻辑属性共同建立稳定尺寸模型。", fallback="逐组件设置 border-box。",
                     verification=("表单控件和卡片不超出容器",))
            if _MEDIA_QUERY.search(text) and not _CONTAINER_QUERY.search(css_text):
                _add(findings, "UX-RESPONSIVE-VIEWPORT-ONLY", severity="UX3", category="responsive", path=path, text=text, offset=0,
                     evidence="检测到媒体查询，但未检测到容器查询", impact="同一组件进入侧栏、主区或弹层时可能无法按自身空间重组。",
                     repair="对可复用列表、卡片、详情和工具栏增加 container-type，并以容器宽度控制结构。",
                     modern="Container Queries 作为组件级响应式，媒体查询负责全局壳层。", fallback="保留现有媒体查询。",
                     verification=("同组件在主区和侧栏均成立", "无容器查询浏览器仍可用"))

    html_joined = "\n".join(str(item.get("text") or "") for item in html_sources)
    if html_sources:
        if "<main" not in html_joined.casefold():
            source = html_sources[0]; text = str(source.get("text") or "")
            _add(findings, "UX-SEMANTIC-MAIN-MISSING", severity="UX2", category="accessibility", path=str(source.get("path") or ""), text=text, offset=0,
                 evidence="未检测到 main landmark", impact="键盘和辅助技术用户难以快速跳到主要内容。",
                 repair="为每个页面提供唯一 main，并增加跳过导航链接。", modern="使用语义 HTML 与可见焦点。", fallback="role=main。",
                 verification=("页面只有一个 main", "跳过导航可用"), confidence="high")
        img_count = len(re.findall(r"(?i)<img\b", html_joined))
        missing_dimensions = len(re.findall(r"(?is)<img\b(?![^>]*(?:width\s*=|height\s*=))[^>]*>", html_joined))
        if img_count >= 2 and missing_dimensions:
            source = html_sources[0]; text = str(source.get("text") or "")
            match = re.search(r"(?is)<img\b(?![^>]*(?:width\s*=|height\s*=))[^>]*>", text)
            _add(findings, "UX-LAYOUT-IMAGE-SIZE-MISSING", severity="UX2", category="performance", path=str(source.get("path") or ""), text=text, offset=match.start() if match else 0,
                 evidence=f"{missing_dimensions} 个图片缺少显式尺寸", impact="图片加载后可能造成布局位移，影响阅读和点击准确性。",
                 repair="提供 width/height 或 aspect-ratio，并为非首屏图片使用 lazy loading。",
                 modern="使用 responsive images、aspect-ratio 和 fetchpriority。", fallback="固定占位容器。",
                 verification=("页面加载 CLS 不因图片明显上升", "慢网下布局稳定"))
        controls = int(observed.get("controls") or 0)
        if controls >= 12 and not re.search(r"(?i)<(?:fieldset|section)\b", html_joined):
            source = html_sources[0]; text = str(source.get("text") or "")
            _add(findings, "UX-FORM-GROUPING-MISSING", severity="UX1", category="interaction", path=str(source.get("path") or ""), text=text, offset=0,
                 evidence=f"观察到约 {controls} 个控件，但缺少明确分组结构", impact="用户难以理解任务阶段、错误位置和完成进度。",
                 repair="按用户任务和决策顺序分组；只有存在依赖时才使用步骤器。",
                 modern="使用 container queries 让摘要和分组在中间宽度自动重排。", fallback="fieldset/section + 标题。",
                 verification=("每组有明确标题", "首屏能理解主任务", "错误能定位到组和字段"))
        columns = int(observed.get("columns") or 0)
        if columns >= 6 and "<table" in html_joined.casefold() and not re.search(r"(?i)(overflow-x\s*:\s*auto|data-table-wrapper|table-container)", css_text + html_joined):
            source = html_sources[0]; text = str(source.get("text") or "")
            match = re.search(r"(?i)<table\b", text)
            _add(findings, "UX-TABLE-RESPONSIVE-STRATEGY", severity="UX1", category="responsive", path=str(source.get("path") or ""), text=text, offset=match.start() if match else 0,
                 evidence=f"检测到 {columns} 列表格，未发现明确响应式策略", impact="移动端容易出现压缩、裁切或不可比较的卡片化。",
                 repair="定义列优先级、最小宽度、滚动容器和列表—详情切换；不要机械将每行转卡片。",
                 modern="Container Queries 控制列显示和详情切换。", fallback="局部横向滚动并固定关键列。",
                 verification=("移动端关键字段可见", "表格滚动不带动整页", "比较语义保留"), confidence="high")
        if not _FOCUS_VISIBLE.search(css_text):
            source = html_sources[0]; text = str(source.get("text") or "")
            _add(findings, "UX-FOCUS-VISIBLE-MISSING", severity="UX1", category="accessibility", path=str(source.get("path") or ""), text=text, offset=0,
                 evidence="项目样式未检测到 :focus-visible", impact="键盘用户无法可靠确认当前操作位置。",
                 repair="为所有交互控件建立统一 focus ring Token，并避免仅使用 outline:none。",
                 modern="使用 :focus-visible 区分键盘与指针焦点。", fallback=":focus 明确轮廓。",
                 verification=("只用键盘可完成主任务", "焦点不被 sticky/overlay 遮挡"), confidence="high")

    priority = {"UX1": 0, "UX2": 1, "UX3": 2}
    findings.sort(key=lambda item: (priority.get(item.severity, 9), item.category, item.id))
    quick = [item.to_dict() for item in findings if item.severity in {"UX1", "UX2"} and item.category in {"responsive", "motion", "typography", "accessibility"}][:8]
    structural = [item.to_dict() for item in findings if item.category in {"layout", "visual-system", "interaction", "layering"}][:8]
    score = max(0, 100 - sum({"UX1": 9, "UX2": 5, "UX3": 2}.get(item.severity, 1) for item in findings))
    finding_rows = [item.to_dict() for item in findings]
    return {
        "schemaVersion": "1.1", "score": score, "findingCount": len(findings),
        "findings": finding_rows, "repairRecipes": build_repair_recipes(finding_rows), "quickWins": quick, "structuralRepairs": structural,
        "principles": [
            "先修复会影响任务完成的错位、遮挡、焦点和状态问题，再进行纯装饰优化",
            "组件级响应式优先，页面级媒体查询负责应用壳层",
            "所有现代技术必须有可用回退，不把实验特性放在关键路径",
            "视觉统一通过语义 Token 和组件合同实现，而不是增加选择器特异性",
        ],
    }
