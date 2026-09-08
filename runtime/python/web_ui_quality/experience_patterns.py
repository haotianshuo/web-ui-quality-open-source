"""Evidence-bounded experience patterns for UI modernisation."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, is_dataclass
import re
from typing import Any, Mapping, Sequence

__all__ = ["build_experience_pattern_library", "match_experience_patterns"]


_LIBRARY_VERSION = "2026.07.18"
_TIER_ORDER = {
    "visual_static": 0,
    "rendered_runtime": 1,
    "interaction_probe": 2,
    "telemetry_or_user_context": 3,
}
_PAGE_TYPE_ALIASES = {
    "all": "all",
    "page": "all",
    "landing": "marketing-landing",
    "landing-page": "marketing-landing",
    "marketing": "marketing-landing",
    "marketing-landing": "marketing-landing",
    "campaign": "campaign-landing",
    "campaign-landing": "campaign-landing",
    "product": "ecommerce-product",
    "product-detail": "ecommerce-product",
    "ecommerce": "ecommerce-product",
    "e-commerce": "ecommerce-product",
    "ecommerce-product": "ecommerce-product",
    "commerce-product": "ecommerce-product",
    "dashboard": "dashboard",
    "saas-dashboard": "dashboard",
    "operations-dashboard": "dashboard",
    "crm": "crm",
    "crm-list": "crm",
    "crm-detail": "crm",
    "erp": "erp",
    "admin": "admin",
    "admin-console": "admin",
    "data-list": "data-list",
    "list": "data-list",
    "table": "data-list",
    "catalog": "catalog",
    "search": "search",
    "search-results": "search",
    "form": "form",
    "settings": "form",
    "workflow": "workflow",
    "approval": "workflow",
    "knowledge-base": "knowledge-base",
    "knowledge": "knowledge-base",
    "mobile": "mobile",
    "mobile-page": "mobile",
    "落地页": "marketing-landing",
    "商品详情": "ecommerce-product",
    "仪表盘": "dashboard",
    "crm-页面": "crm",
    "erp-页面": "erp",
    "列表和详情": "data-list",
    "表单和向导": "form",
    "移动页面": "mobile",
}


def _detector(
    detector_id: str,
    signals: Sequence[str],
    operator: str,
    value: Any,
    weight: int,
    observed_message: str,
    verification: str,
) -> dict[str, Any]:
    return {
        "id": detector_id,
        "signals": list(signals),
        "operator": operator,
        "value": value,
        "weight": weight,
        "observedMessage": observed_message,
        "verification": verification,
    }


def _rule(
    *,
    rule_id: str,
    name: str,
    source_family: str,
    scope: str,
    page_types: Sequence[str],
    evidence_tier: str,
    detectors: Sequence[Mapping[str, Any]],
    observed_boundary: str,
    inference_boundary: str,
    must_not_claim: str,
    user_impact: str,
    recommendation: str,
    implementation_hints: Sequence[str],
    anti_patterns: Sequence[str],
    official_sources: Sequence[str],
    required_detector_ids: Sequence[str] = (),
    minimum_evidence_hits: int = 2,
    minimum_match_score: float = 0.4,
) -> dict[str, Any]:
    return {
        "id": rule_id,
        "name": name,
        "sourceFamily": source_family,
        "scope": scope,
        "pageTypes": list(page_types),
        "evidenceTier": evidence_tier,
        "detectors": [dict(item) for item in detectors],
        "minimumEvidenceHits": minimum_evidence_hits,
        "requiredDetectorIds": list(required_detector_ids),
        "minimumMatchScore": minimum_match_score,
        "evidenceBoundary": {
            "observed": observed_boundary,
            "inference": inference_boundary,
            "mustNotClaim": must_not_claim,
        },
        "observedBoundary": observed_boundary,
        "inferenceBoundary": inference_boundary,
        "userImpact": user_impact,
        "recommendation": recommendation,
        "implementationHints": list(implementation_hints),
        "antiPatterns": list(anti_patterns),
        "officialSources": list(official_sources),
        "brandCopyProhibited": True,
    }


_EXPERIENCE_DNA: tuple[dict[str, Any], ...] = (
    {
        "id": "focus-and-breathing-room",
        "name": "焦点与呼吸空间",
        "sourceFamily": "apple",
        "scope": "visual-hierarchy-and-product-story",
        "neutralPrinciples": [
            "一个视区优先回答一个主要问题，并给出清楚的下一步。",
            "留白用于分组、节奏和焦点，不以空白面积本身作为品质指标。",
            "动效只解释状态、反馈、转场或空间关系，并提供减弱动效路径。",
        ],
        "applicationBoundary": "适合营销页、商品叙事和需要降低首屏竞争的页面；数据工作台应保持任务所需密度。",
        "doNotCopy": ["品牌字体与材质", "产品页构图", "特定圆角、玻璃或动画风格"],
        "officialSources": [
            "https://developer.apple.com/design/human-interface-guidelines/layout",
            "https://developer.apple.com/design/human-interface-guidelines/motion",
        ],
        "patternOnly": True,
        "brandCopyProhibited": True,
    },
    {
        "id": "commerce-decision-clarity",
        "name": "商业决策清晰度",
        "sourceFamily": "xiaomi",
        "scope": "commerce-information-and-conversion",
        "neutralPrinciples": [
            "先用少量核心能力建立心智模型，再按主题展开细节。",
            "关键参数与用户收益成对出现，单位、条件和脚注保持可见。",
            "响应式密度随可用空间变化：大屏增加有效信息，小屏保留核心任务。",
        ],
        "applicationBoundary": "适合商品详情、比较和购买决策；不要求采用任何厂商品牌视觉。",
        "doNotCopy": ["品牌配色", "产品摄影风格", "营销口号和页面动效"],
        "officialSources": [
            "https://www.mi.com/global/product/xiaomi-17/",
            "https://dev.mi.com/xiaomihyperos/documentation/detail?pId=2040",
        ],
        "patternOnly": True,
        "brandCopyProhibited": True,
    },
    {
        "id": "enterprise-task-clarity",
        "name": "企业任务清晰度",
        "sourceFamily": "tencent-tdesign+alibaba-ant-design",
        "scope": "enterprise-density-actions-and-feedback",
        "neutralPrinciples": [
            "高密度依靠对齐、分组、稳定列和操作层级，而不是缩小一切。",
            "表格、列表和卡片按比较关系与任务选择，低频操作渐进披露。",
            "反馈强度与紧急度、持续时间和可操作性匹配。",
        ],
        "applicationBoundary": "适合 CRM、ERP、管理后台和工作流；需结合真实角色、权限和任务频率。",
        "doNotCopy": ["组件皮肤", "设计 Token 数值", "品牌图标和默认主题"],
        "officialSources": [
            "https://github.com/Tencent/tdesign",
            "https://ant.design/docs/spec/data-list/",
            "https://ant.design/docs/spec/feedback",
        ],
        "patternOnly": True,
        "brandCopyProhibited": True,
    },
    {
        "id": "data-trust-and-status",
        "name": "数据可信度与状态可解释性",
        "sourceFamily": "stripe",
        "scope": "dashboard-search-status-and-recovery",
        "neutralPrinciples": [
            "Dashboard 同时回答业务走势、异常和下一项行动。",
            "跨对象搜索支持业务标识、字段过滤和可复现查询。",
            "高信任任务把状态、事件时间线、错误原因和恢复动作连在一起。",
        ],
        "applicationBoundary": "适合支付、运营、集成健康和其他高信任数据产品。",
        "doNotCopy": ["Dashboard 版式", "品牌色和图表皮肤", "产品术语"],
        "officialSources": [
            "https://docs.stripe.com/dashboard/basics",
            "https://docs.stripe.com/dashboard/search",
            "https://docs.stripe.com/workbench/overview",
        ],
        "patternOnly": True,
        "brandCopyProhibited": True,
    },
    {
        "id": "rapid-command-efficiency",
        "name": "快速命令效率",
        "sourceFamily": "linear",
        "scope": "power-user-search-filter-and-workflow",
        "neutralPrinciples": [
            "高频操作提供统一命令入口、快捷键和等价鼠标路径。",
            "筛选即时可见、可保存、可分享，并保留在 URL 中。",
            "自动化与撤销减少维护工作，但不隐藏重要副作用。",
        ],
        "applicationBoundary": "适合高频任务和熟练用户；新用户仍需发现性提示和清晰标签。",
        "doNotCopy": ["深色主题", "动效节奏", "特定快捷键或产品信息架构"],
        "officialSources": [
            "https://linear.app/docs/search",
            "https://linear.app/docs/filters",
            "https://linear.app/docs/custom-views",
        ],
        "patternOnly": True,
        "brandCopyProhibited": True,
    },
    {
        "id": "flexible-content-structure",
        "name": "灵活内容结构",
        "sourceFamily": "notion",
        "scope": "composable-content-and-context-preserving-views",
        "neutralPrinciples": [
            "一个数据源可有多个任务视图，每个视图独立保存展示与筛选设置。",
            "轻量查看保留列表上下文，深度工作再进入独立页面。",
            "命令式创建降低工具栏导航，但必须可发现、可取消、可撤销。",
        ],
        "applicationBoundary": "适合知识库、项目数据库和灵活工作台；强约束流程仍需明确状态与权限。",
        "doNotCopy": ["块编辑器外观", "侧栏结构", "品牌图标、字体与交互细节"],
        "officialSources": [
            "https://www.notion.com/help/keyboard-shortcuts",
            "https://www.notion.com/help/views-filters-and-sorts",
        ],
        "patternOnly": True,
        "brandCopyProhibited": True,
    },
)



_PATTERNS: tuple[dict[str, Any], ...] = (
    _rule(
        rule_id="PX-FOCUS-001",
        name="单一首屏焦点",
        source_family="apple",
        scope="visual-hierarchy",
        page_types=("marketing-landing", "campaign-landing", "ecommerce-product"),
        evidence_tier="visual_static",
        detectors=(
            _detector("competing-dominant-regions", ("dominantRegionCount", "aboveFold.dominantRegionCount", "hero.competingRegionCount"), "gte", 3, 2, "首屏存在多个相互竞争的主视觉区域。", "核对首屏主视觉区域数量及其面积、对比度和位置。"),
            _detector("multiple-primary-ctas", ("primaryButtonCountAboveFold", "aboveFold.primaryButtonCount", "hero.primaryCtaCount"), "gte", 2, 2, "首屏出现多个同等权重的主操作。", "核对首屏主按钮数量和视觉权重。"),
            _detector("fragmented-reading-path", ("h1PrimaryCtaPathAligned", "aboveFold.readingPathAligned"), "is_false", True, 1, "标题、主要内容和主操作未形成连续阅读路径。", "检查标题、价值说明和 CTA 是否按阅读顺序连续。"),
            _detector("too-many-major-headings", ("aboveFoldHeadingCount", "hero.majorHeadingCount"), "gte", 3, 1, "首屏存在过多主要标题。", "检查首屏标题层级及是否存在多个同级 H1/H2。"),
        ),
        observed_boundary="只陈述首屏区域、标题和主操作的数量、位置与相对视觉权重。",
        inference_boundary="用户难以判断主要价值与下一步属于体验规律推断，需要行为数据验证程度。",
        must_not_claim="没有眼动、点击或转化数据时，不得断言用户一定忽略了某个区域或转化率会下降。",
        user_impact="用户第一眼难以判断页面最重要的信息和下一步。",
        recommendation="把首屏收敛为一个核心承诺、一个主操作和最多一个低权重详情入口；后续按主题逐段展开。",
        implementation_hints=(
            "建立首屏视觉权重排序并只保留一个 primary CTA。",
            "让 H1、价值说明和 CTA 落在连续阅读路径上。",
            "用间距分组，不用纯装饰空白隐藏必要信息。",
        ),
        anti_patterns=("复制品牌大字大图但继续堆叠卖点。", "用大面积空白代替清晰的信息结构。"),
        official_sources=(
            "https://developer.apple.com/design/human-interface-guidelines/layout",
            "https://www.apple.com/macbook-air/",
        ),
    ),
    _rule(
        rule_id="PX-HIERARCHY-002",
        name="稳定阅读层级与对齐",
        source_family="apple",
        scope="visual-hierarchy-and-alignment",
        page_types=("all",),
        evidence_tier="visual_static",
        detectors=(
            _detector("important-action-outside-reading-origin", ("importantActionInReadingOrigin", "visualHierarchy.primaryActionInReadingOrigin"), "is_false", True, 2, "主要操作未处于页面的优先阅读区域。", "核对主要操作在当前语言阅读顺序中的位置。"),
            _detector("misaligned-modules", ("misalignedModuleCount", "alignment.misalignedModuleCount"), "gte", 2, 2, "多个模块没有共享稳定的对齐线。", "测量相邻模块的起始边、文本基线和内容边界。"),
            _detector("controls-content-not-separated", ("controlContentContrastSeparated", "visualHierarchy.controlContentSeparated"), "is_false", True, 1, "控件层与内容层缺少可辨识的层级差异。", "检查控件与内容是否依靠结构、对比和位置清楚区分。"),
            _detector("heading-level-skips", ("headingLevelSkipCount", "headings.levelSkipCount"), "gte", 1, 1, "标题层级存在跳级或同级权重混乱。", "检查标题语义层级和视觉层级是否一致。"),
        ),
        observed_boundary="只陈述阅读起点、模块对齐、控件分层和标题结构的可见事实。",
        inference_boundary="扫读速度和秩序感属于基于这些事实的推断。",
        must_not_claim="不得把某种材质、阴影或视觉风格本身判定为优质层级。",
        user_impact="页面扫读路径不稳定，用户需要反复寻找重要内容和操作。",
        recommendation="按语言阅读顺序放置重要信息，统一模块对齐线，并用结构和对比区分控件层与内容层。",
        implementation_hints=(
            "聚类 DOMRect 的起始边和文本基线，找出异常对齐。",
            "保持语义标题级别与字号、字重层级一致。",
            "不要只依靠颜色表达控件与内容差异。",
        ),
        anti_patterns=("用玻璃、阴影或渐变假装层级。", "每个卡片使用不同的对齐和标题规则。"),
        official_sources=(
            "https://developer.apple.com/design/human-interface-guidelines/layout",
            "https://developer.apple.com/design/human-interface-guidelines/materials",
        ),
    ),
    _rule(
        rule_id="PX-RESP-DENSITY-007",
        name="跨视口有效密度",
        source_family="xiaomi",
        scope="responsive-density",
        page_types=("all",),
        evidence_tier="rendered_runtime",
        detectors=(
            _detector("low-desktop-occupancy", ("desktopContentOccupancyRatio", "viewports.desktop.contentOccupancyRatio"), "ratio_lt", 0.55, 2, "宽屏有效内容占用率偏低。", "在至少 1200px 宽视口测量内容包围盒与可用内容区比例。"),
            _detector("mobile-horizontal-overflow", ("mobileHorizontalOverflowPx", "viewports.mobile.horizontalOverflowPx"), "gt", 0, 2, "移动视口出现横向溢出。", "在移动视口测量 scrollWidth 与 clientWidth 差值。"),
            _detector("mobile-task-loss", ("mobileCriticalTaskMissing", "viewports.mobile.criticalTaskMissing"), "is_true", True, 2, "移动视图丢失了关键任务能力。", "对比桌面和移动端主任务、主操作与必要信息。"),
            _detector("desktop-mobile-column-stretch", ("desktopSingleNarrowColumn", "viewports.desktop.singleNarrowColumn"), "is_true", True, 1, "宽屏仍使用狭窄的移动单列构图。", "检查宽屏是否能通过增列或主从布局使用空间。"),
        ),
        observed_boundary="必须来自至少两个实际渲染视口的占用、溢出或任务能力事实。",
        inference_boundary="空间浪费或移动任务受阻是由渲染事实推导的用户影响。",
        must_not_claim="没有多视口渲染证据时，不得仅凭 CSS 源码断言响应式体验失败。",
        user_impact="桌面空间被浪费，或移动端出现横向滚动和关键任务缺失。",
        recommendation="大屏通过增列、主从分栏或展开上下文提高有效密度；小屏保留核心任务并折叠次要信息。",
        implementation_hints=(
            "至少测试 390、768/1024、1440 三档视口。",
            "比较断点间组件能力而不只比较元素尺寸。",
            "限制正文行长，避免用无限拉宽填满大屏。",
        ),
        anti_patterns=("所有断点只做等比缩放。", "为了移动简洁而删除关键操作。"),
        official_sources=(
            "https://dev.mi.com/xiaomihyperos/documentation/detail?pId=2040",
            "https://dev.mi.com/xiaomihyperos/documentation/detail?pId=2026",
        ),
    ),
    _rule(
        rule_id="PX-ACTION-HIERARCHY-008",
        name="操作主次与低频收纳",
        source_family="tencent-tdesign",
        scope="action-hierarchy",
        page_types=("all",),
        evidence_tier="visual_static",
        detectors=(
            _detector("multiple-primary-actions", ("primaryButtonCountInTaskRegion", "actions.primaryCountPerTaskRegion"), "gte", 2, 2, "同一任务区域存在多个主按钮。", "按任务区域统计 primary 按钮，而不是按整页统计。"),
            _detector("crowded-mobile-actions", ("visibleMobileActionCount", "actions.mobileVisibleCount"), "gte", 6, 2, "移动端同时外露过多操作。", "检查移动操作区可见动作数量和触控间距。"),
            _detector("danger-same-emphasis", ("dangerActionSameEmphasis", "actions.dangerSameEmphasisAsPrimary"), "is_true", True, 2, "危险操作与主要安全操作使用相同权重。", "比较危险、主要和次要动作的语义与视觉权重。"),
            _detector("unlabelled-unfamiliar-actions", ("unlabeledUnfamiliarActionCount", "actions.unlabeledUnfamiliarCount"), "gte", 1, 1, "存在没有文字说明的陌生操作图标。", "核对非通用图标是否有可见标签或可访问名称。"),
        ),
        observed_boundary="只陈述同一任务区域的按钮数量、标签和视觉权重。",
        inference_boundary="选择犹豫和误操作风险属于基于操作竞争的推断。",
        must_not_claim="不得把按钮颜色本身等同于业务优先级，必须结合语义和位置。",
        user_impact="用户难以判断首要动作，并更容易触发低频或危险操作。",
        recommendation="每个局部任务保留一个主动作，弱化次动作，把低频操作收入“更多”，并让危险动作具有独立语义。",
        implementation_hints=(
            "按容器建立 action group，再判断组内主按钮数量。",
            "移动端优先保留一到两个高频动作。",
            "高频中文按钮使用短而明确的动宾文案。",
        ),
        anti_patterns=("所有按钮都使用品牌主色。", "用一排 icon-only 按钮压缩中文操作。"),
        official_sources=(
            "https://tdesign.tencent.com/qq-miniprogram/components/button",
            "https://tdesign.tencent.com/flutter/components/action-sheet",
        ),
    ),

    _rule(
        rule_id="PX-EMPTY-ACTION-010",
        name="可继续的空状态",
        source_family="tencent-tdesign",
        scope="empty-state-and-recovery",
        page_types=("data-list", "dashboard", "search", "crm", "erp"),
        evidence_tier="visual_static",
        required_detector_ids=("empty-container-present",),
        detectors=(
            _detector("empty-container-present", ("emptyContainerCount", "emptyStates.containerCount"), "gte", 1, 1, "页面存在空数据容器。", "确认容器确实处于首次空、筛选空或错误空状态。"),
            _detector("empty-explanation-missing", ("emptyStateHasExplanation", "emptyStates.hasExplanation"), "is_false", True, 2, "空状态没有说明原因或当前条件。", "检查空状态是否解释首次空、无结果、权限或错误原因。"),
            _detector("empty-recovery-missing", ("emptyStateHasRecoveryAction", "emptyStates.hasRecoveryAction"), "is_false", True, 2, "空状态没有可执行的下一步。", "检查是否提供创建、导入、清除筛选或重试等合适动作。"),
            _detector("filters-hidden-on-no-result", ("noResultShowsActiveFilters", "emptyStates.noResultShowsActiveFilters"), "is_false", True, 1, "无结果状态未显示当前筛选条件。", "在筛选无结果时确认过滤条件仍清楚可见和可清除。"),
        ),
        observed_boundary="必须先观察到真实空容器，再判断解释、条件和恢复动作是否存在。",
        inference_boundary="用户可能误以为故障或不知道如何继续是体验影响推断。",
        must_not_claim="没有确认数据状态时，不得把加载中、权限受限或请求失败统一称为“无数据”。",
        user_impact="用户可能误以为系统故障，并且不知道如何继续任务。",
        recommendation="区分首次空、筛选空、权限空和错误空，说明当前原因，并提供一个最合适的下一步。",
        implementation_hints=(
            "为空状态写入可识别的 state kind。",
            "筛选空保留条件并提供清除筛选。",
            "错误空提供重试，首次空提供创建或导入。",
        ),
        anti_patterns=("所有空态都只显示“暂无数据”。", "在空态放置多个等权主操作。"),
        official_sources=(
            "https://tdesign.tencent.com/qq-miniprogram/components/empty",
            "https://ant.design/docs/spec/data-list/",
        ),
    ),
    _rule(
        rule_id="PX-DATA-MODE-014",
        name="按任务选择数据载体",
        source_family="alibaba-ant-design",
        scope="data-presentation-mode",
        page_types=("data-list", "crm", "erp", "catalog"),
        evidence_tier="visual_static",
        detectors=(
            _detector("comparison-fields-in-cards", ("cardComparableFieldCount", "dataPresentation.cardComparableFieldCount"), "gte", 5, 2, "卡片包含多个需要跨对象比较的字段。", "检查用户是否需要在多个对象间横向比较这些字段。"),
            _detector("long-text-in-table", ("tableLongTextCellRatio", "dataPresentation.tableLongTextCellRatio"), "ratio_gte", 0.3, 2, "表格中较高比例的单元格承载长文本。", "测量长文本单元格占比和行高变化。"),
            _detector("large-images-in-table", ("tableLargeImageCellRatio", "dataPresentation.tableLargeImageCellRatio"), "ratio_gte", 0.25, 1, "表格中较高比例的单元格承载大图。", "测量图片占单元格和行高的比例。"),
            _detector("card-view-for-cross-comparison", ("cardViewRequiresCrossItemComparison", "dataPresentation.crossItemComparisonRequired"), "is_true", True, 2, "当前卡片视图承担跨对象精确比较任务。", "通过任务或交互证据确认用户需要跨项比较。"),
        ),
        observed_boundary="只陈述字段数量、内容类型、行高和当前展示载体。",
        inference_boundary="哪种载体更高效需要结合主要任务和比较关系推断。",
        must_not_claim="不得仅因卡片或表格存在就判定错误；必须至少观察到载体与内容关系不匹配。",
        user_impact="用户难以跨项比较结构化数据，或在表格中阅读不适合矩阵展示的内容。",
        recommendation="结构化多字段比较使用表格，窄容器和快速概览使用列表，强调形象且浏览顺序弱时使用卡片。",
        implementation_hints=(
            "识别字段数据类型、平均文本长度和比较频率。",
            "为有真实价值的场景提供视图切换。",
            "移动端保留关键比较语义，而不是机械卡片化。",
        ),
        anti_patterns=("所有对象一律卡片化。", "把长文和大图强塞进高密度表格。"),
        official_sources=(
            "https://ant.design/docs/spec/data-list/",
            "https://ant.design/docs/spec/research-list/",
        ),
    ),
    _rule(
        rule_id="PX-LIST-WORKBENCH-015",
        name="列表查找与连续处理工作台",
        source_family="alibaba-ant-design",
        scope="data-list-workbench",
        page_types=("data-list", "crm", "erp"),
        evidence_tier="rendered_runtime",
        required_detector_ids=("large-record-set",),
        detectors=(
            _detector("large-record-set", ("recordCount", "list.recordCount", "observed.rows"), "gte", 20, 1, "页面包含需要管理的较大记录集合。", "确认当前列表的实际或总记录数量。"),
            _detector("search-missing", ("hasSearch", "list.hasSearch"), "is_false", True, 2, "列表缺少搜索入口。", "在渲染页面中检查可用且可访问的搜索能力。"),
            _detector("filter-missing", ("hasFilter", "list.hasFilter"), "is_false", True, 2, "列表缺少筛选入口。", "检查筛选是否真实改变结果并显示当前条件。"),
            _detector("sort-missing", ("hasSort", "list.hasSort"), "is_false", True, 1, "列表缺少与任务相关的排序能力。", "检查关键列或排序菜单是否可操作。"),
            _detector("paging-missing", ("hasPaginationOrIncrementalLoad", "list.hasPaginationOrIncrementalLoad"), "is_false", True, 1, "大列表缺少分页或增量加载。", "检查大量数据的加载、位置恢复和性能行为。"),
            _detector("batch-toolbar-always-visible", ("batchToolbarVisibleWithoutSelection", "list.batchToolbarVisibleWithoutSelection"), "is_true", True, 1, "未选择记录时批量操作仍占据主要空间。", "清除选择后检查批量栏是否仍以高权重显示。"),
            _detector("return-context-lost", ("returnContextPreserved", "list.returnContextPreserved"), "is_false", True, 2, "从详情返回后列表上下文没有保留。", "验证返回后的筛选、滚动、选中和焦点状态。"),
        ),
        observed_boundary="匹配必须包含记录规模事实，并观察至少一项查找、处理或返回行为缺失。",
        inference_boundary="处理成本上升是根据任务规模和能力缺口推断。",
        must_not_claim="没有交互验证时，不得仅因 DOM 中找不到特定 class 就断言搜索或筛选不可用。",
        user_impact="用户寻找对象、批量处理和连续核对记录的成本较高。",
        recommendation="为大列表建立搜索、筛选、排序和分页组合，仅在选中后显示批量操作，并保留返回上下文。",
        implementation_hints=(
            "Browser probe 验证搜索、筛选和排序是否改变结果。",
            "记录并恢复 URL、筛选、滚动、选中和焦点。",
            "新建项可置顶并短暂高亮。",
        ),
        anti_patterns=("把所有高级筛选条件永久展开。", "筛选或返回后静默跳到无关位置。"),
        official_sources=(
            "https://ant.design/docs/spec/data-list/",
            "https://ant.design/docs/spec/research-list/",
        ),
        minimum_match_score=0.3,
    ),
    _rule(
        rule_id="PX-FORM-DECOMPOSE-016",
        name="复杂表单分组与进度",
        source_family="alibaba-ant-design",
        scope="form-and-workflow-decomposition",
        page_types=("form", "workflow"),
        evidence_tier="visual_static",
        detectors=(
            _detector("many-required-fields", ("requiredFieldCount", "form.requiredFieldCount"), "gte", 8, 2, "表单包含较多必填字段。", "统计真实可见和渐进披露后的必填字段。"),
            _detector("multiple-semantic-groups", ("semanticGroupCount", "form.semanticGroupCount"), "gte", 3, 1, "字段跨越多个语义分组。", "根据标签、标题和业务关系确认分组。"),
            _detector("long-form-scroll", ("formScrollViewportCount", "form.scrollViewportCount"), "gt", 2, 2, "表单长度超过多个视口。", "在目标视口测量表单主体滚动长度。"),
            _detector("progress-hidden", ("progressVisible", "form.progressVisible"), "is_false", True, 1, "复杂任务没有显示当前进度或剩余部分。", "检查线性流程是否显示已完成、当前和待办部分。"),
        ),
        observed_boundary="只陈述字段数量、语义分组、滚动长度和进度提示。",
        inference_boundary="填写压力、遗漏和错误风险属于基于复杂度的推断。",
        must_not_claim="不得仅按字段数量机械拆步；必须确认字段依赖和任务线性。",
        user_impact="用户难以理解任务范围，容易遗漏字段或在长表单中失去位置。",
        recommendation="按相关性分组；只有在线性依赖明确时才拆为步骤，并持续显示已完成、当前和待办部分。",
        implementation_hints=(
            "先建立字段依赖和语义分组，再决定单页分段或 Steps。",
            "错误摘要可定位并聚焦具体字段。",
            "提交前复核关键值，完成后显示结果和下一步。",
        ),
        anti_patterns=("把短表单强拆成多步。", "步骤条只显示数字而不说明任务。"),
        official_sources=(
            "https://ant.design/docs/spec/research-form/",
            "https://ant.design/components/steps/",
        ),
    ),

    _rule(
        rule_id="PX-FEEDBACK-SEVERITY-017",
        name="反馈强度与任务严重度匹配",
        source_family="alibaba-ant-design",
        scope="status-feedback-and-recovery",
        page_types=("all",),
        evidence_tier="interaction_probe",
        detectors=(
            _detector("critical-failure-in-toast", ("criticalFailureUsesTransientToast", "feedback.criticalFailureUsesTransientToast"), "is_true", True, 2, "关键失败只通过短暂轻提示呈现。", "触发关键失败并记录反馈形态、持续时间和可操作信息。"),
            _detector("minor-success-blocks", ("lightweightSuccessUsesBlockingDialog", "feedback.lightweightSuccessUsesBlockingDialog"), "is_true", True, 2, "轻量成功结果使用阻塞对话框。", "触发轻量成功并检查是否无必要地阻断后续任务。"),
            _detector("operation-exceeds-two-seconds", ("longOperationSeconds", "feedback.operationDurationSeconds"), "gt", 2, 1, "操作持续时间超过两秒。", "测量从提交到稳定结果的真实时长。"),
            _detector("progress-missing", ("longOperationHasProgress", "feedback.longOperationHasProgress"), "is_false", True, 2, "长操作没有进度或持续状态反馈。", "在长操作期间检查加载、阶段或进度反馈。"),
            _detector("cancel-missing", ("longOperationCanCancel", "feedback.longOperationCanCancel"), "is_false", True, 1, "长任务没有取消或安全退出路径。", "确认任务是否足够长且技术上允许取消。"),
        ),
        observed_boundary="必须通过真实操作记录反馈形态、持续时间、状态变化和可用动作。",
        inference_boundary="反馈被错过、打断或降低信任是基于交互事实的推断。",
        must_not_claim="没有触发对应成功、失败和长任务状态时，不得从静态组件名称推断反馈行为。",
        user_impact="重要错误可能被错过，轻量任务被无谓打断，长任务看起来像失去响应。",
        recommendation="轻成功使用非阻塞消息，页面问题使用 Alert，后台结果使用 Notification，关键可操作失败使用 Dialog；长任务显示进度并在可行时允许取消。",
        implementation_hints=(
            "按 severity、scope、duration、actionability 四维选择反馈。",
            "错误说明紧邻修复动作并保持可访问。",
            "异步任务离页后仍应可追踪。",
        ),
        anti_patterns=("所有结果都使用三秒 Toast。", "每次成功都弹出确认对话框。"),
        official_sources=(
            "https://ant.design/docs/spec/feedback",
            "https://ant.design/docs/spec/research-message-and-feedback/",
        ),
        minimum_match_score=0.3,
    ),
    _rule(
        rule_id="PX-DASH-ACTION-019",
        name="从指标到行动的 Dashboard",
        source_family="stripe",
        scope="dashboard-information-and-action",
        page_types=("dashboard",),
        evidence_tier="visual_static",
        required_detector_ids=("known-action-required-items",),
        detectors=(
            _detector("multiple-kpis", ("kpiCount", "dashboard.kpiCount", "observed.metrics"), "gte", 3, 1, "Dashboard 展示多个业务指标。", "统计真正承担业务决策的 KPI，而非装饰数字。"),
            _detector("action-required-absent", ("hasActionRequiredSection", "dashboard.hasActionRequiredSection"), "is_false", True, 2, "Dashboard 没有需处理事项或下一步区域。", "检查异常、待办或建议动作是否在 Dashboard 可见。"),
            _detector("known-action-required-items", ("knownActionRequiredItemCount", "dashboard.knownActionRequiredItemCount", "unresolvedItemCount", "dashboard.unresolvedItemCount"), "gte", 1, 2, "已观察到至少一项需要处理的业务对象。", "确认待办或异常来自真实业务状态，而不是根据版式推测。"),
            _detector("too-many-equal-widgets", ("equalWeightWidgetCount", "dashboard.equalWeightWidgetCount"), "gte", 8, 2, "大量 Widget 使用相同视觉权重。", "比较 Widget 的面积、标题、对比和排序。"),
            _detector("critical-alert-hidden", ("criticalAlertHidden", "dashboard.criticalAlertHidden"), "is_true", True, 2, "关键告警被放在低可见区域。", "核对告警严重度与页面位置、权重是否一致。"),
        ),
        observed_boundary="只陈述 KPI、Widget、告警和行动区域的数量、位置与权重。",
        inference_boundary="用户无法从趋势转向行动属于基于信息结构的推断。",
        must_not_claim="没有业务状态证据时，不得断言 Dashboard 应当存在告警或待办。",
        user_impact="用户看见发生了什么，却不容易识别需要立即处理的事项。",
        recommendation="首屏组合少量关键 KPI、时间范围、趋势和需处理事项，并给出明确下一步；允许按角色有限定制。",
        implementation_hints=(
            "为 KPI 标注时间范围、趋势和数据新鲜度。",
            "把异常与具体对象、原因和下一动作连接。",
            "限制首屏等权 Widget 数量。",
        ),
        anti_patterns=("把所有指标平铺成彩色数字卡。", "用告警色装饰普通指标。"),
        official_sources=(
            "https://docs.stripe.com/dashboard/basics",
            "https://docs.stripe.com/workbench/overview",
        ),
        minimum_match_score=0.3,
    ),
    _rule(
        rule_id="PX-DETAIL-PEEK-026",
        name="保留列表上下文的轻量详情",
        source_family="notion",
        scope="context-preserving-detail",
        page_types=("data-list", "crm", "knowledge-base"),
        evidence_tier="interaction_probe",
        required_detector_ids=("repeated-detail-navigation",),
        detectors=(
            _detector("repeated-detail-navigation", ("detailOpenCountForReview", "navigation.detailOpenCountForReview"), "gte", 3, 2, "用户需要连续打开多条记录进行核对。", "执行连续核对任务并记录详情打开次数。"),
            _detector("brief-review-fields", ("reviewFieldCount", "detail.reviewFieldCount"), "lte", 8, 1, "单条核对只需要少量字段。", "确认完成轻量核对所需的最小字段集合。"),
            _detector("return-context-lost", ("returnContextPreserved", "navigation.returnContextPreserved"), "is_false", True, 2, "从详情返回后列表上下文丢失。", "验证筛选、滚动、选中和焦点是否恢复。"),
            _detector("brief-detail", ("detailContentViewportCount", "detail.contentViewportCount"), "lte", 1, 1, "详情内容可在约一个视口内完成核对。", "在目标视口测量必要详情内容长度。"),
            _detector("contextual-preview-absent", ("hasContextualPreview", "detail.hasContextualPreview"), "is_false", True, 2, "列表没有保留上下文的预览方式。", "检查抽屉、分栏或 Peek 是否可用于轻量核对。"),
        ),
        observed_boundary="必须通过连续核对任务观察导航次数、详情长度和返回状态。",
        inference_boundary="侧栏预览更高效是结合轻量任务与上下文损失后的模式建议。",
        must_not_claim="详情复杂、需分享或超过一屏时，不得强制推荐窄抽屉。",
        user_impact="频繁整页跳转使用户失去列表位置，并增加连续核对成本。",
        recommendation="短查看或轻编辑使用右侧 Peek/Drawer 并保持列表上下文；复杂、可分享或长内容继续使用独立页面。",
        implementation_hints=(
            "预览只包含识别、关键属性、状态、活动和主要动作。",
            "支持上一条、下一条并保持筛选与选中。",
            "抽屉宽度和内部滚动需多视口验证。",
        ),
        anti_patterns=("把完整详情页复制进窄抽屉。", "所有列表点击都强制整页跳转。"),
        official_sources=(
            "https://www.notion.com/help/views-filters-and-sorts",
            "https://knowledge.hubspot.com/records/preview-a-record",
        ),
        minimum_match_score=0.3,
    ),
    _rule(
        rule_id="PX-ZH-SCANNABILITY-044",
        name="中文任务扫读性",
        source_family="alibaba-ant-design+tencent-tdesign",
        scope="zh-localisation-and-scannability",
        page_types=("crm", "erp", "admin", "mobile", "data-list"),
        evidence_tier="visual_static",
        detectors=(
            _detector("long-frequent-labels", ("longChineseHighFrequencyLabelCount", "localization.longHighFrequencyLabelCount"), "gte", 1, 2, "高频中文操作文案过长。", "检查高频按钮是否能用更短且不丢语义的动宾表达。"),
            _detector("wrapped-operational-cells", ("wrappedStatusTimeActionCellCount", "localization.wrappedOperationalCellCount"), "gte", 1, 2, "状态、时间或操作列出现换行。", "在目标列宽与目标字号下检查完整词语是否换行。"),
            _detector("unlabelled-unfamiliar-actions", ("unlabeledUnfamiliarActionCount", "localization.unlabeledUnfamiliarActionCount"), "gte", 1, 1, "陌生操作仅使用图标表达。", "检查图标是否通用，并验证可见标签和可访问名称。"),
            _detector("mixed-terminology", ("mixedTerminologyCount", "localization.mixedTerminologyCount"), "gte", 1, 1, "同一区域存在不必要的中英文术语混用。", "核对英文是否为不可替代的业务或技术标识。"),
            _detector("locale-format-mismatch", ("localeFormattingMismatchCount", "localization.formatMismatchCount"), "gte", 1, 2, "日期、数字或货币格式与当前 locale 不一致。", "用目标 locale 验证日期、数字、单位和货币显示。"),
        ),
        observed_boundary="只陈述文案长度、换行、图标标签、术语和 locale 格式事实。",
        inference_boundary="扫读变慢或误解风险属于语言与布局规律推断。",
        must_not_claim="不得把所有英文都视为问题，也不得为了缩短而损失业务准确性。",
        user_impact="中文用户扫读节奏被打断，状态和操作更容易被误解。",
        recommendation="高频操作使用短而明确的动宾文案；状态、时间和操作词保持完整；陌生或危险动作使用图标加文字；按 locale 统一日期、数字和货币。",
        implementation_hints=(
            "结合操作频率和语义判断文案长度，不设全局硬字符上限。",
            "为状态、时间和操作列设置合理最小宽度与不换行策略。",
            "对 Intl 格式化输出做 locale 测试。",
        ),
        anti_patterns=("为了国际化保留大量无必要英文缩写。", "把中文操作全部压缩成无标签图标。"),
        official_sources=(
            "https://ant.design/docs/spec/data-display-cn/",
            "https://tdesign.tencent.com/flutter/components/input?tab=design",
        ),
    ),
)



def build_experience_pattern_library() -> dict[str, Any]:
    """Return a fresh, JSON-friendly copy of the offline pattern library."""
    return {
        "version": _LIBRARY_VERSION,
        "purpose": "Transferable experience-modernisation rules grounded in official first-party guidance.",
        "brandCopyPolicy": {
            "brandCopyProhibited": True,
            "rule": "只迁移信息组织、任务效率、状态反馈和决策清晰度规律；禁止复制品牌视觉、文案、布局成品或动效签名。",
        },
        "evidenceContract": {
            "observed": "matched 只能由 evidence 中实际存在且满足 detector 的事实产生。",
            "inference": "pageType 与 experienceModel 只用于相关性和候选排序，不能替代观测证据。",
            "lowEvidence": "证据层级不足、信心低或命中数不足时必须进入 candidates，并给出 verificationNeeded。",
        },
        "experienceDNA": deepcopy(list(_EXPERIENCE_DNA)),
        "patterns": deepcopy(list(_PATTERNS)),
    }


def _as_mapping(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        converted = to_dict()
        return dict(converted) if isinstance(converted, Mapping) else {}
    if is_dataclass(value):
        converted = asdict(value)
        return dict(converted) if isinstance(converted, Mapping) else {}
    return {}


def _normalise_key(value: Any) -> str:
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", str(value).casefold())


def _flatten_mapping(value: Mapping[str, Any]) -> dict[str, tuple[Any, str]]:
    flattened: dict[str, tuple[Any, str]] = {}

    def visit(item: Any, path: tuple[str, ...]) -> None:
        if isinstance(item, Mapping):
            for key in sorted(item, key=lambda candidate: str(candidate)):
                visit(item[key], (*path, str(key)))
            return
        if not path:
            return
        dotted = ".".join(path)
        flattened.setdefault(_normalise_key(dotted), (item, dotted))
        flattened.setdefault(_normalise_key(path[-1]), (item, dotted))

    visit(value, ())
    return flattened


def _lookup_signal(
    flattened: Mapping[str, tuple[Any, str]],
    signals: Sequence[str],
) -> tuple[bool, Any, str | None, str | None]:
    for signal in signals:
        found = flattened.get(_normalise_key(signal))
        if found is not None:
            return True, found[0], found[1], signal
    return False, None, None, None


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return float(len(value))
    if isinstance(value, str):
        text = value.strip().replace(",", "")
        if text.endswith("%"):
            try:
                return float(text[:-1]) / 100.0
            except ValueError:
                return None
        try:
            return float(text)
        except ValueError:
            return None
    return None


def _boolean(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in {0, 1}:
        return bool(value)
    if isinstance(value, str):
        text = value.strip().casefold()
        if text in {"true", "yes", "1", "是", "有", "存在"}:
            return True
        if text in {"false", "no", "0", "否", "无", "不存在"}:
            return False
    return None


def _equal(left: Any, right: Any) -> bool:
    left_number = _number(left)
    right_number = _number(right)
    if left_number is not None and right_number is not None:
        return left_number == right_number
    return str(left).strip().casefold() == str(right).strip().casefold()


def _compare(actual: Any, operator: str, expected: Any) -> bool:
    if operator == "is_true":
        return _boolean(actual) is True
    if operator == "is_false":
        return _boolean(actual) is False
    if operator == "eq":
        return _equal(actual, expected)
    actual_number = _number(actual)
    expected_number = _number(expected)
    if actual_number is None or expected_number is None:
        return False
    if operator.startswith("ratio_") and actual_number > 1:
        actual_number /= 100.0
    if operator in {"gte", "ratio_gte"}:
        return actual_number >= expected_number
    if operator == "gt":
        return actual_number > expected_number
    if operator == "lte":
        return actual_number <= expected_number
    if operator in {"lt", "ratio_lt"}:
        return actual_number < expected_number
    return False


def _normalise_tier(value: Any) -> str | None:
    text = str(value).strip().casefold().replace("-", "_").replace(" ", "_")
    aliases = {
        "static": "visual_static",
        "visual": "visual_static",
        "screenshot": "visual_static",
        "dom": "visual_static",
        "runtime": "rendered_runtime",
        "rendered": "rendered_runtime",
        "browser": "rendered_runtime",
        "interaction": "interaction_probe",
        "probe": "interaction_probe",
        "telemetry": "telemetry_or_user_context",
        "user_context": "telemetry_or_user_context",
        "static_source": "visual_static",
        "source_static": "visual_static",
        "screenshot_overlay": "visual_static",
        "local_visual_segmentation": "visual_static",
        "rendered_observation": "rendered_runtime",
        "browser_measured": "rendered_runtime",
        "mixed_rendered_and_static": "rendered_runtime",
        "interaction_observation": "interaction_probe",
    }
    result = aliases.get(text, text)
    return result if result in _TIER_ORDER else None


def _available_tiers(
    evidence: Mapping[str, Any],
    flattened: Mapping[str, tuple[Any, str]],
) -> set[str]:
    tiers: set[str] = set()
    explicit = False
    for key in ("evidenceTier", "evidenceTiers", "evidence_tier", "evidence_tiers", "evidenceMode", "evidenceModes", "sourceType", "sourceTypes"):
        raw = evidence.get(key)
        if raw is None:
            continue
        explicit = True
        values = (
            raw
            if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes, bytearray))
            else (raw,)
        )
        for value in values:
            tier = _normalise_tier(value)
            if tier:
                tiers.add(tier)

    if not explicit and flattened:
        tiers.add("visual_static")

    if "telemetry_or_user_context" in tiers:
        tiers.update({"interaction_probe", "rendered_runtime", "visual_static"})
    elif "interaction_probe" in tiers:
        tiers.update({"rendered_runtime", "visual_static"})
    elif "rendered_runtime" in tiers:
        tiers.add("visual_static")
    return tiers


def _tier_satisfied(required: str, available: set[str]) -> bool:
    if required == "visual_static":
        return "visual_static" in available
    if required == "rendered_runtime":
        return bool({"rendered_runtime", "interaction_probe"} & available)
    return required in available


def _evidence_confidence(evidence: Mapping[str, Any]) -> str:
    raw = evidence.get("confidence", evidence.get("evidenceConfidence", evidence.get("evidence_confidence")))
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        if float(raw) >= 0.8:
            return "high"
        if float(raw) >= 0.5:
            return "medium"
        return "low"
    text = str(raw or "").strip().casefold()
    if text in {"high", "medium", "low"}:
        return text
    return "medium" if evidence else "low"


def _normalise_page_type(value: Any) -> str:
    text = (
        str(value or "unknown")
        .strip()
        .casefold()
        .replace("_", "-")
        .replace(" ", "-")
    )
    return _PAGE_TYPE_ALIASES.get(text, text or "unknown")


def _page_types(page_type: Any, model: Mapping[str, Any]) -> tuple[str, ...]:
    raw_values: list[Any] = []
    if isinstance(page_type, Sequence) and not isinstance(page_type, (str, bytes, bytearray)):
        raw_values.extend(page_type)
    else:
        raw_values.append(page_type)
    for key in ("pageType", "pageTypes", "pageMode", "pageModes"):
        raw = model.get(key)
        if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes, bytearray)):
            raw_values.extend(raw)
        elif raw:
            raw_values.append(raw)

    mode_aliases = {
        "dashboard": "dashboard",
        "列表和详情": "data-list",
        "表单和向导": "form",
        "应用外壳": "admin",
    }
    normalised: list[str] = []
    for raw in raw_values:
        mapped = mode_aliases.get(str(raw).strip().casefold(), raw)
        item = _normalise_page_type(mapped)
        if item != "unknown" and item not in normalised:
            normalised.append(item)
    return tuple(normalised or ("unknown",))


def _page_applicable(rule: Mapping[str, Any], page_types: Sequence[str]) -> bool:
    supported = set(str(item) for item in rule.get("pageTypes", ()))
    return "all" in supported or bool(supported.intersection(page_types))


def _model_relevance(
    rule: Mapping[str, Any],
    model: Mapping[str, Any],
) -> tuple[float, list[str]]:
    """Return a small ranking boost; never use it as matching evidence."""
    boost = 0.0
    reasons: list[str] = []
    density = str(
        model.get("informationDensity") or model.get("information_density") or ""
    ).casefold()
    task = " ".join(
        str(model.get(key) or "")
        for key in ("taskType", "task_type", "primaryTask", "primary_task")
    ).casefold()
    device = str(
        model.get("devicePriority") or model.get("device_priority") or ""
    ).casefold()
    language = str(model.get("locale") or model.get("language") or "").casefold()
    scope = str(rule.get("scope") or "")

    if density == "high" and scope in {
        "data-list-workbench",
        "data-presentation-mode",
        "zh-localisation-and-scannability",
    }:
        boost += 0.03
        reasons.append("体验模型表明信息密度较高")
    if any(word in task for word in ("find", "compare", "查找", "比较", "核对")) and scope in {
        "data-list-workbench",
        "context-preserving-detail",
    }:
        boost += 0.03
        reasons.append("体验模型表明任务需要查找或连续核对")
    if any(word in task for word in ("monitor", "respond", "监控", "异常", "响应")) and scope == "dashboard-information-and-action":
        boost += 0.03
        reasons.append("体验模型表明任务需要监控和响应")
    if device == "mobile" and scope in {"responsive-density", "action-hierarchy"}:
        boost += 0.02
        reasons.append("体验模型表明移动端优先")
    if language.startswith("zh") and scope == "zh-localisation-and-scannability":
        boost += 0.03
        reasons.append("体验模型表明中文 locale")
    return boost, reasons



def _verification_for(
    rule: Mapping[str, Any],
    matched_detectors: Sequence[Mapping[str, Any]],
    tier_ok: bool,
    evidence_confidence: str,
) -> list[str]:
    checks: list[str] = []
    if not tier_ok:
        checks.append(f"需要 {rule['evidenceTier']} 层级证据后才能确认。")
    if evidence_confidence == "low":
        checks.append("现有证据信心较低，需要补充可复现的页面事实。")
    matched_ids = {str(item["detectorId"]) for item in matched_detectors}
    required_ids = {str(item) for item in rule.get("requiredDetectorIds", ())}
    missing_required = sorted(required_ids - matched_ids)
    if missing_required:
        checks.append(
            "必须先验证前置 detector：" + "、".join(missing_required) + "。"
        )
    minimum_hits = int(rule.get("minimumEvidenceHits") or 1)
    if len(matched_ids) < minimum_hits:
        checks.append(
            f"至少需要 {minimum_hits} 个独立 detector 命中；"
            f"当前为 {len(matched_ids)} 个。"
        )
    for detector in rule.get("detectors", ()):
        if detector.get("id") not in matched_ids:
            text = str(detector.get("verification") or "").strip()
            if text and text not in checks:
                checks.append(text)
        if len(checks) >= 5:
            break
    return checks


def _match_rule(
    rule: Mapping[str, Any],
    flattened: Mapping[str, tuple[Any, str]],
    available_tiers: set[str],
    evidence_confidence: str,
    model: Mapping[str, Any],
) -> tuple[dict[str, Any], bool]:
    matched_detectors: list[dict[str, Any]] = []
    total_weight = 0
    matched_weight = 0
    for detector in rule.get("detectors", ()):
        weight = int(detector.get("weight") or 1)
        total_weight += weight
        present, actual, source_path, signal = _lookup_signal(
            flattened,
            detector.get("signals", ()),
        )
        if not present or not _compare(
            actual,
            str(detector.get("operator")),
            detector.get("value"),
        ):
            continue
        matched_weight += weight
        matched_detectors.append(
            {
                "detectorId": detector["id"],
                "signal": signal,
                "sourcePath": source_path,
                "actual": actual,
                "operator": detector["operator"],
                "expected": detector["value"],
                "weight": weight,
                "observed": detector["observedMessage"],
            }
        )

    detector_score = matched_weight / max(1, total_weight)
    boost, context_reasons = _model_relevance(rule, model)
    relevance_score = min(1.0, detector_score + boost)
    tier_ok = _tier_satisfied(str(rule.get("evidenceTier")), available_tiers)
    minimum_hits = int(rule.get("minimumEvidenceHits") or 1)
    minimum_score = float(rule.get("minimumMatchScore") or 0.0)
    required_ids = {str(item) for item in rule.get("requiredDetectorIds", ())}
    matched_ids = {str(item["detectorId"]) for item in matched_detectors}
    required_ok = required_ids.issubset(matched_ids)
    strong_match = (
        tier_ok
        and required_ok
        and evidence_confidence != "low"
        and len(matched_detectors) >= minimum_hits
        and detector_score >= minimum_score
    )
    verification = [] if strong_match else _verification_for(
        rule,
        matched_detectors,
        tier_ok,
        evidence_confidence,
    )
    if strong_match and evidence_confidence == "high" and len(matched_detectors) >= minimum_hits + 1:
        match_confidence = "high"
    elif strong_match:
        match_confidence = "medium"
    else:
        match_confidence = "low"

    result = deepcopy(dict(rule))
    result["match"] = {
        "status": "matched" if strong_match else "candidate",
        "confidence": match_confidence,
        "detectorScore": round(detector_score, 4),
        "relevanceScore": round(relevance_score, 4),
        "matchedDetectors": matched_detectors,
        "observedFacts": [str(item["observed"]) for item in matched_detectors],
        "inference": (
            str(rule.get("userImpact"))
            if strong_match
            else f"若上述事实经验证，可能影响：{rule.get('userImpact')}"
        ),
        "contextReasons": context_reasons,
        "verificationNeeded": verification,
    }
    return result, strong_match


def match_experience_patterns(
    page_type: Any,
    evidence: Mapping[str, Any] | None,
    experience_model: Mapping[str, Any] | Any | None,
) -> dict[str, Any]:
    """Match observations without upgrading page-type inference to fact.

    Evidence may be flat or nested. Page type and experience-model fields only
    affect applicability and ordering. Missing, low-confidence, or lower-tier
    evidence returns relevant rules as candidates with verification requests.
    """
    evidence_map = _as_mapping(evidence)
    model_map = _as_mapping(experience_model)
    flattened = _flatten_mapping(evidence_map)
    available = _available_tiers(evidence_map, flattened)
    confidence = _evidence_confidence(evidence_map)
    normalised_page_types = _page_types(page_type, model_map)

    matched: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    for rule in _PATTERNS:
        if not _page_applicable(rule, normalised_page_types):
            continue
        result, is_match = _match_rule(
            rule,
            flattened,
            available,
            confidence,
            model_map,
        )
        (matched if is_match else candidates).append(result)

    def sort_key(item: Mapping[str, Any]) -> tuple[float, str]:
        match = item.get("match", {})
        return (
            -float(match.get("relevanceScore") or 0.0),
            str(item.get("id") or ""),
        )

    matched.sort(key=sort_key)
    candidates.sort(key=sort_key)
    verification_needed = [
        {
            "patternId": item["id"],
            "requiredEvidenceTier": item["evidenceTier"],
            "checks": list(item["match"]["verificationNeeded"]),
        }
        for item in candidates
        if item["match"].get("verificationNeeded")
    ]
    ordered_tiers = sorted(
        available,
        key=lambda item: (_TIER_ORDER[item], item),
    )
    return {
        "libraryVersion": _LIBRARY_VERSION,
        "pageTypes": list(normalised_page_types),
        "evidenceSummary": {
            "availableTiers": ordered_tiers,
            "confidence": confidence,
            "observedSignalCount": len(flattened),
            "boundary": (
                "只有 detector 命中的 evidence 是 observed；"
                "体验模型与规则中的用户影响保持为 inference。"
            ),
        },
        "matched": matched,
        "candidates": candidates,
        "verificationNeeded": verification_needed,
        "brandCopyProhibited": True,
    }

