"""Research-backed modern UX catalog used by the Experience Fusion engine.

The catalog intentionally stores design intent and behaviour rather than copied
third-party component code.  Entries are deterministic, framework-neutral, and
include applicability, interaction, responsive, accessibility, recovery, and
measurement contracts so that they can drive real plans rather than act as a
visual inspiration list.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping, Sequence


@dataclass(frozen=True, slots=True)
class ComponentPrimitive:
    id: str
    name: str
    category: str
    purpose: str
    anatomy: tuple[str, ...]
    behaviours: tuple[str, ...]
    states: tuple[str, ...]
    accessibility: tuple[str, ...]
    responsive: tuple[str, ...]
    fallback: str

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        return {key: list(value) if isinstance(value, tuple) else value for key, value in data.items()}


@dataclass(frozen=True, slots=True)
class PageSkeleton:
    id: str
    name: str
    family: str
    goal: str
    composition: tuple[str, ...]
    components: tuple[str, ...]
    interactions: tuple[str, ...]
    states: tuple[str, ...]
    desktop: str
    tablet: str
    mobile: str
    use_when: tuple[str, ...]
    avoid_when: tuple[str, ...]
    acceptance: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        return {key: list(value) if isinstance(value, tuple) else value for key, value in data.items()}


@dataclass(frozen=True, slots=True)
class InteractionPattern:
    id: str
    name: str
    intent: str
    modality: str
    trigger: str
    immediate_feedback: str
    progress: str
    completion: str
    error: str
    recovery: str
    accessibility: str
    telemetry: tuple[str, ...]
    fallback: str
    risk: str

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["telemetry"] = list(self.telemetry)
        return data


@dataclass(frozen=True, slots=True)
class ContextStatePattern:
    id: str
    state: str
    context: str
    meaning: str
    presentation: str
    primary_action: str
    secondary_action: str
    persistence: str
    accessibility: str
    acceptance: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["acceptance"] = list(self.acceptance)
        return data


_COMPONENT_ROWS = (
    ("app-shell", "应用外壳", "layout", "组织全局导航、页面区和跨页状态", ("顶栏", "主导航", "内容区", "全局反馈区"), ("折叠导航", "保持当前路由", "跳过导航"), ("default", "compact", "mobile-drawer")),
    ("page-header", "页面标题区", "navigation", "说明当前对象、任务和主操作", ("标题", "副标题", "面包屑", "主操作", "状态"), ("标题可换行", "操作按优先级收敛", "滚动后压缩"), ("default", "sticky", "compact")),
    ("sidebar", "侧边导航", "navigation", "承载稳定的一级或二级导航", ("品牌区", "分组", "导航项", "折叠触发器", "用户区"), ("图标折叠", "分组展开", "保持选择"), ("expanded", "icon-only", "off-canvas")),
    ("command-palette", "命令面板", "navigation", "为高频用户提供跨页面搜索和操作入口", ("输入", "分组结果", "快捷键", "空结果"), ("Ctrl/Cmd+K", "模糊搜索", "键盘执行"), ("closed", "searching", "empty", "open")),
    ("breadcrumb", "面包屑", "navigation", "展示层级并支持返回上级", ("祖先项", "当前页"), ("超长折叠", "保留当前项"), ("default", "collapsed")),
    ("tabs", "标签页", "navigation", "在同级内容视图间切换", ("标签列表", "标签面板", "数量徽标"), ("方向键切换", "懒加载", "保留面板状态"), ("default", "overflow", "disabled")),
    ("segmented-control", "分段控制", "navigation", "在少量互斥视图间快速切换", ("选项", "选中指示"), ("即时切换", "连续过渡"), ("default", "disabled")),
    ("search-field", "搜索框", "input", "快速定位对象或命令", ("标签", "输入", "清除", "快捷键", "结果计数"), ("防抖", "提交", "清除", "保留输入"), ("idle", "typing", "loading", "no-result")),
    ("filter-bar", "筛选栏", "input", "组合高频筛选并明确生效条件", ("常用筛选", "更多筛选", "已生效标签", "重置"), ("即时或显式应用", "保存视图", "恢复"), ("idle", "dirty", "applied", "empty")),
    ("data-table", "数据表格", "data", "高密度比较结构化记录", ("表头", "行", "排序", "选择", "分页", "列管理"), ("排序", "筛选", "选择", "键盘移动", "虚拟滚动"), ("loading", "empty", "partial", "selected")),
    ("data-grid", "专业数据网格", "data", "处理大规模可编辑和可配置数据", ("冻结列", "编辑单元格", "分组", "汇总", "列设置"), ("键盘编辑", "复制粘贴", "撤销", "批量验证"), ("loading", "editing", "invalid", "saving")),
    ("card-list", "卡片列表", "data", "在低到中密度场景突出对象摘要和下一步", ("标题", "摘要", "状态", "元数据", "主操作"), ("选择", "展开", "滑动操作"), ("loading", "empty", "selected")),
    ("master-detail", "主从详情", "layout", "连续查找并核对对象", ("对象列表", "可调分隔", "详情", "上下文工具栏"), ("选择", "键盘上下项", "恢复滚动", "调整宽度"), ("no-selection", "selected", "loading-detail")),
    ("inspector-drawer", "检查器抽屉", "overlay", "在不离开列表时查看次要详情", ("标题", "摘要", "分区", "操作", "关闭"), ("焦点管理", "历史返回", "宽度适配"), ("closed", "open", "loading")),
    ("dialog", "对话框", "overlay", "处理需要聚焦的短任务或确认", ("标题", "说明", "内容", "主次操作", "关闭"), ("焦点锁定", "Escape", "返回触发点"), ("closed", "open", "submitting", "error")),
    ("popover", "弹出层", "overlay", "提供轻量上下文操作或帮助", ("触发器", "浮层", "箭头", "关闭语义"), ("碰撞翻转", "滚动跟随", "点击外部关闭"), ("closed", "open")),
    ("tooltip", "工具提示", "overlay", "补充简短非关键说明", ("触发器", "提示内容"), ("hover/focus", "延迟", "自动避让"), ("closed", "open")),
    ("form", "表单", "input", "收集和编辑结构化数据", ("分组", "字段", "错误摘要", "操作区"), ("即时校验", "草稿", "提交", "恢复"), ("pristine", "dirty", "invalid", "saving", "saved")),
    ("field", "字段", "input", "提供标签、帮助、输入和错误的完整语义", ("标签", "必填", "输入", "帮助", "错误"), ("输入", "校验", "清除"), ("idle", "focus", "invalid", "disabled", "read-only")),
    ("stepper", "步骤器", "navigation", "表达有依赖的多步骤任务", ("步骤", "状态", "进度", "返回"), ("前进", "返回", "跳转限制", "保存草稿"), ("current", "complete", "error", "disabled")),
    ("file-uploader", "文件上传", "input", "选择、校验并上传一个或多个文件", ("选择区", "文件队列", "进度", "错误", "重试"), ("拖放", "暂停", "取消", "重试", "预览"), ("idle", "uploading", "paused", "failed", "complete")),
    ("progress", "进度反馈", "feedback", "说明真实任务阶段和完成量", ("标签", "数值", "阶段", "取消"), ("确定或不确定进度", "节流更新"), ("idle", "running", "paused", "complete")),
    ("toast", "轻提示", "feedback", "反馈不阻断当前任务的结果", ("图标", "消息", "操作", "关闭"), ("自动消失", "撤销", "队列"), ("info", "success", "warning", "error")),
    ("banner", "页面通知", "feedback", "展示影响页面或任务的重要状态", ("标题", "正文", "操作", "关闭"), ("持久展示", "局部重试"), ("info", "warning", "error")),
    ("empty-state", "空状态", "feedback", "解释为何无内容并给出下一步", ("标题", "说明", "主操作", "次操作"), ("区分首次为空和筛选为空"), ("initial", "filtered", "permission")),
    ("skeleton", "骨架屏", "feedback", "在结构已知时降低首次加载跳动", ("标题占位", "行占位", "媒体占位"), ("与最终结构一致", "避免长时间循环"), ("loading",)),
    ("status-badge", "状态标记", "feedback", "以文字、形状和颜色共同表达状态", ("图标", "文字", "色彩"), ("筛选", "帮助说明"), ("neutral", "success", "warning", "danger")),
    ("timeline", "时间线", "data", "展示事件顺序和历史证据", ("时间", "节点", "内容", "操作者"), ("折叠", "筛选", "定位"), ("loading", "empty", "complete")),
    ("activity-feed", "动态流", "data", "展示跨对象的最新变化", ("事件", "对象", "时间", "操作"), ("加载更多", "过滤", "跳转对象"), ("loading", "empty", "new-items")),
    ("metric-card", "指标卡", "data", "展示一个可行动的状态指标", ("名称", "数值", "趋势", "上下文", "下钻"), ("下钻", "时间范围", "刷新"), ("loading", "stale", "error")),
    ("chart", "图表", "data", "展示趋势、分布或关系", ("标题", "图形", "图例", "轴", "数据表替代"), ("tooltip", "筛选", "缩放", "下钻"), ("loading", "empty", "partial")),
    ("kanban", "看板", "workflow", "按阶段管理有限数量的工作项", ("列", "卡片", "限制", "汇总"), ("拖动", "键盘移动", "批量操作"), ("loading", "empty", "blocked")),
    ("tree", "树形结构", "data", "浏览层级对象或权限", ("节点", "展开", "选择", "层级线"), ("展开", "搜索", "键盘导航", "懒加载"), ("loading", "empty", "selected")),
    ("ai-composer", "AI 输入区", "ai", "组合指令、附件、模式和执行控制", ("输入", "附件", "模式", "发送", "停止"), ("自动扩展", "快捷键", "取消", "草稿"), ("idle", "submitting", "disabled")),
    ("ai-response", "AI 结果区", "ai", "显示流式结果、工具调用和人工采纳", ("内容", "工具状态", "引用", "版本", "采纳"), ("流式", "停止", "重试", "复制", "比较"), ("thinking", "streaming", "partial", "complete", "error")),
    ("citation-panel", "引用与证据面板", "ai", "让用户核对结果依据和来源", ("来源", "片段", "可信度", "跳转"), ("展开", "定位", "过滤"), ("loading", "empty", "available")),
)

_COMPONENT_EXTRAS = {
    "fallback": {
        "app-shell": "普通纵向文档流", "sidebar": "顶部菜单或抽屉", "command-palette": "全局搜索页",
        "popover": "内联区域或 dialog", "tooltip": "可见辅助文字", "master-detail": "独立详情页",
        "data-grid": "分页表格", "chart": "数据表", "kanban": "按状态分组列表", "tree": "缩进列表",
        "ai-response": "普通消息流",
    },
    "accessibility": {
        "default": ("语义元素优先", "名称、角色、状态可被辅助技术识别", "键盘与触控均可完成主任务"),
        "table": ("表头关联", "排序状态可读", "选择数量可读", "保留表格语义"),
        "overlay": ("打开后移动焦点", "关闭后返回触发点", "Escape 语义明确", "背景不可交互"),
        "form": ("标签与输入关联", "错误与字段关联", "错误摘要可定位", "不只靠颜色"),
    },
    "responsive": {
        "default": ("使用容器查询优先", "中间宽度减少并列区域", "移动端主任务优先"),
        "data": ("列优先级", "保留比较语义", "必要时切换列表与详情而非压缩"),
        "overlay": ("宽屏侧边浮层", "窄屏底部或全屏层", "避免超出视口"),
    },
}


def _component_accessibility(component_id: str, category: str) -> tuple[str, ...]:
    if category == "overlay": return _COMPONENT_EXTRAS["accessibility"]["overlay"]
    if category == "input": return _COMPONENT_EXTRAS["accessibility"]["form"]
    if component_id in {"data-table", "data-grid"}: return _COMPONENT_EXTRAS["accessibility"]["table"]
    return _COMPONENT_EXTRAS["accessibility"]["default"]


def _component_responsive(component_id: str, category: str) -> tuple[str, ...]:
    if category == "overlay": return _COMPONENT_EXTRAS["responsive"]["overlay"]
    if category == "data": return _COMPONENT_EXTRAS["responsive"]["data"]
    return _COMPONENT_EXTRAS["responsive"]["default"]


COMPONENTS: tuple[ComponentPrimitive, ...] = tuple(
    ComponentPrimitive(
        row[0], row[1], row[2], row[3], tuple(row[4]), tuple(row[5]), tuple(row[6]),
        _component_accessibility(row[0], row[2]), _component_responsive(row[0], row[2]),
        _COMPONENT_EXTRAS["fallback"].get(row[0], "基础语义 HTML/CSS 实现"),
    )
    for row in _COMPONENT_ROWS
)


_FAMILY_DEFAULTS: dict[str, dict[str, Any]] = {
    "list-detail": {
        "components": ("page-header", "search-field", "filter-bar", "data-table", "master-detail", "status-badge", "toast"),
        "interactions": ("search", "filter", "sort", "open-detail", "return-context"),
        "states": ("loading", "empty-initial", "empty-filtered", "partial-error", "permission-denied", "stale"),
        "desktop": "筛选与对象区稳定可见，详情与列表连续核对", "tablet": "列表与详情上下或可调分栏", "mobile": "列表—详情连续视图切换并恢复位置",
    },
    "form": {
        "components": ("page-header", "form", "field", "stepper", "banner", "toast"),
        "interactions": ("validate", "save-draft", "submit", "undo", "return-context"),
        "states": ("loading", "validation-error", "saving", "save-failed", "unsaved", "success", "conflict"),
        "desktop": "分组表单与摘要并列", "tablet": "单列内容和顶部进度", "mobile": "步骤或分段单列，固定操作不遮挡键盘",
    },
    "dashboard": {
        "components": ("page-header", "filter-bar", "metric-card", "chart", "data-table", "banner"),
        "interactions": ("change-range", "drill-down", "refresh", "acknowledge", "save-view"),
        "states": ("loading", "partial-error", "stale", "empty-initial", "error"),
        "desktop": "状态、异常、趋势和任务分层", "tablet": "两列重排为主次区块", "mobile": "状态、异常和下一动作优先，图表折叠",
    },
    "workflow": {
        "components": ("page-header", "filter-bar", "card-list", "master-detail", "timeline", "dialog"),
        "interactions": ("claim", "review", "approve", "reject", "next-item"),
        "states": ("loading", "empty-initial", "processing", "validation-error", "conflict", "success"),
        "desktop": "队列、证据和决策区并列", "tablet": "队列与决策上下排列", "mobile": "一条任务一个专注视图",
    },
    "settings": {
        "components": ("page-header", "sidebar", "search-field", "form", "field", "banner"),
        "interactions": ("search", "preview", "save", "restore-default", "discard"),
        "states": ("loading", "read-only", "unsaved", "saving", "success", "conflict"),
        "desktop": "分类导航、设置详情和变更摘要", "tablet": "顶部分类和单列设置", "mobile": "搜索优先的分类列表与独立详情",
    },
    "processing": {
        "components": ("page-header", "file-uploader", "progress", "data-table", "inspector-drawer", "toast"),
        "interactions": ("upload", "pause", "resume", "retry", "cancel", "preview"),
        "states": ("idle", "loading", "processing", "partial-success", "error", "offline", "success"),
        "desktop": "上传区、队列和处理详情", "tablet": "队列主导，详情下置", "mobile": "单手上传入口和任务卡片",
    },
    "communication": {
        "components": ("page-header", "search-field", "filter-bar", "card-list", "master-detail", "activity-feed"),
        "interactions": ("search", "filter", "mark-read", "archive", "jump-object"),
        "states": ("loading", "empty-initial", "empty-filtered", "offline", "error"),
        "desktop": "分组、列表与内容详情", "tablet": "列表和内容上下切换", "mobile": "消息列表到内容连续切换",
    },
    "field": {
        "components": ("page-header", "stepper", "form", "field", "file-uploader", "banner", "toast"),
        "interactions": ("scan", "capture", "save-draft", "sync", "submit"),
        "states": ("loading", "offline", "syncing", "validation-error", "saving", "success"),
        "desktop": "管理和回看视图", "tablet": "大触控单列任务", "mobile": "步骤任务卡与安全区内固定操作",
    },
    "ai": {
        "components": ("app-shell", "card-list", "ai-composer", "ai-response", "citation-panel", "inspector-drawer"),
        "interactions": ("compose", "attach", "stream", "stop", "retry", "compare-version", "adopt"),
        "states": ("idle", "loading", "processing", "partial-success", "error", "cancelled", "success"),
        "desktop": "任务列表、生成画布与证据区", "tablet": "主画布和可折叠侧栏", "mobile": "输入—过程—结果单列流",
    },
    "shell": {
        "components": ("app-shell", "sidebar", "command-palette", "page-header", "breadcrumb", "tabs", "toast"),
        "interactions": ("navigate", "command-search", "switch-workspace", "restore-session"),
        "states": ("loading", "permission-denied", "offline", "error"),
        "desktop": "稳定导航和多页工作区", "tablet": "可折叠导航", "mobile": "抽屉导航和单页任务",
    },
}


_SKELETON_VARIANTS: dict[str, tuple[tuple[str, str, str, tuple[str, ...], tuple[str, ...]], ...]] = {
    "list-detail": (
        ("split-inspector", "可调主从检查器", "连续查找、比较和核对对象", ("高频桌面", "字段中高密度"), ("详情需要独立分享链接",)),
        ("route-detail", "独立路由详情", "复杂详情、深层操作和可分享链接", ("详情内容长", "详情有子任务"), ("高频连续核对",)),
        ("drawer-inspector", "抽屉式快速检查", "在列表上下文中完成短详情核对", ("详情较短", "偶发查看"), ("表单复杂",)),
        ("card-priority", "优先字段卡片列表", "帮助低频或移动用户快速识别对象", ("字段少", "视觉识别重要"), ("需要多列横向比较",)),
        ("dense-grid", "高密度专业网格", "服务专家用户的批量比较和编辑", ("高频专家", "大量记录"), ("新手或手机主场景",)),
        ("batch-triage", "批量分诊队列", "快速分类、批量处理和异常优先", ("待办量大", "动作规则稳定"), ("每项需要深度判断",)),
        ("timeline-record", "时间线记录详情", "围绕对象历史和事件证据核对", ("事件顺序重要",), ("纯静态主数据",)),
        ("tree-inspector", "树形对象检查器", "浏览组织、目录或层级资产", ("层级关系稳定",), ("扁平高频批量处理",)),
        ("comparison-matrix", "多对象对比矩阵", "并排比较少量对象的重要字段", ("决策比较", "对象数有限"), ("对象数量巨大",)),
        ("map-list", "地图与列表联动", "结合空间位置和对象状态进行调度", ("空间关系重要",), ("没有可靠位置数据",)),
        ("search-first", "搜索优先对象工作台", "面向已知对象快速定位和处理", ("用户通常知道关键词",), ("需要浏览发现",)),
        ("audit-ledger", "不可变审计台账", "清晰展示变更、操作者和证据", ("审计合规",), ("需要频繁行内编辑",)),
        ("asset-library", "素材与资产库", "预览、筛选和批量管理媒体资产", ("媒体预览重要",), ("纯文本高密度数据",)),
        ("inventory-batch", "库存批次工作台", "批次、库存、位置和异常联动", ("库存对象",), ("无批次语义",)),
        ("crm-pipeline", "客户阶段工作台", "客户列表、阶段、跟进和详情连续处理", ("销售流程",), ("非阶段型对象",)),
        ("service-tickets", "服务工单工作台", "围绕优先级、SLA 和处理记录工作", ("工单服务",), ("无处理闭环",)),
        ("finance-ledger", "财务流水台账", "高密度核对、汇总和异常标记", ("财务专业用户",), ("移动新手",)),
        ("permissions-matrix", "权限矩阵", "角色、资源和权限交叉配置", ("权限配置",), ("权限规则简单",)),
        ("content-review", "内容审核工作台", "内容预览、规则命中和决策并列", ("内容审核",), ("无证据预览",)),
        ("case-file", "案件档案工作台", "围绕对象摘要、证据、历史和任务组织", ("跨模块综合对象",), ("单一短任务",)),
    ),
    "form": (
        ("sectioned", "单页分组表单", "在一页内完成中等复杂度编辑", ("字段可自然分组",), ("步骤强依赖",)),
        ("wizard", "有依赖分步向导", "帮助低频用户完成有顺序的任务", ("步骤依赖",), ("高频专家操作",)),
        ("review-submit", "填写—复核—提交", "在提交前明确摘要和风险", ("提交不可逆或重要",), ("简单低风险保存",)),
        ("autosave-editor", "自动保存编辑器", "支持长时间内容编辑和恢复", ("长内容", "频繁编辑"), ("严格审批提交",)),
        ("inline-edit", "行内快速编辑", "减少简单字段修改的页面跳转", ("字段少", "低风险"), ("复杂联动校验",)),
        ("settings-form", "设置配置表单", "支持即时预览、默认值和变更摘要", ("系统设置",), ("一次性业务提交",)),
        ("bulk-import", "批量导入映射", "上传、字段映射、校验和失败导出", ("批量数据导入",), ("单条编辑",)),
        ("rule-builder", "规则条件构建器", "以条件、动作和优先级组合业务规则", ("规则配置",), ("简单文本设置",)),
        ("survey", "问卷与调查", "分组问题、进度和匿名提示", ("调查收集",), ("专业数据录入",)),
        ("application", "申请与材料提交", "多材料、资格检查和进度保存", ("申请流程",), ("内部高频录入",)),
        ("onboarding", "新用户引导", "逐步建立账号、偏好和初始数据", ("首次使用",), ("重复任务",)),
        ("approval-form", "审批意见表单", "证据、意见和决策在同一上下文", ("审批决定",), ("普通编辑",)),
        ("schedule-builder", "排期与时段构建", "处理日期、资源和冲突", ("排班排期",), ("无时间约束",)),
        ("pricing", "价格与套餐配置", "管理层级价格、折扣和生效范围", ("价格配置",), ("简单数值输入",)),
        ("address", "地址与区域录入", "分级区域、地图和标准化地址", ("地址质量重要",), ("无地理需求",)),
        ("inspection", "检查与巡检表", "检查项、证据、异常和整改", ("巡检",), ("纯信息登记",)),
        ("maintenance", "维护工单表单", "设备、故障、措施和耗材联动", ("维护维修",), ("普通申请",)),
        ("report-builder", "报告构建器", "章节、数据、附件和预览协作", ("结构化报告",), ("短表单",)),
        ("multi-entity", "多对象关联表单", "在一个任务中关联多个业务对象", ("关系复杂",), ("单对象简单录入",)),
        ("mobile-capture", "移动采集表单", "大触控、拍照、扫码、离线草稿", ("现场移动",), ("桌面专业录入",)),
    ),
    "dashboard": (
        ("executive-overview", "经营总览", "少量核心指标、趋势和风险摘要", ("管理层决策",), ("实时操作台",)),
        ("operations-command", "运营指挥台", "状态、异常、任务和资源联动", ("实时运营",), ("只看汇总",)),
        ("exception-first", "异常优先驾驶舱", "先展示需要处理的偏差和下一步", ("异常处理",), ("无明确阈值",)),
        ("analytical", "分析探索面板", "多维筛选、图表联动和下钻", ("分析用户",), ("新手日常任务",)),
        ("service-health", "服务健康监控", "可用性、延迟、错误和事件", ("技术运营",), ("非技术业务汇报",)),
        ("sales", "销售漏斗面板", "阶段、转化、预测和行动清单", ("销售管理",), ("非阶段业务",)),
        ("finance", "财务经营面板", "收入、成本、现金和异常", ("财务管理",), ("实时任务操作",)),
        ("supply-chain", "供应链面板", "库存、交付、风险和节点状态", ("供应链",), ("无跨节点数据",)),
        ("quality", "质量管理面板", "缺陷、趋势、整改和责任区", ("质量管理",), ("无质量指标",)),
        ("workforce", "人员与产能面板", "出勤、负载、产能和风险", ("人员调度",), ("敏感数据无权限",)),
        ("customer-success", "客户成功面板", "健康度、续费风险和跟进任务", ("客户运营",), ("无客户生命周期",)),
        ("project-portfolio", "项目组合面板", "进度、预算、风险和依赖", ("项目群管理",), ("单项目执行",)),
        ("security", "安全态势面板", "告警、资产、风险和处置", ("安全运营",), ("缺少实时事件",)),
        ("compliance", "合规状态面板", "规则覆盖、例外和整改", ("合规管理",), ("无标准映射",)),
        ("learning", "学习运营面板", "参与、完成、效果和提醒", ("教育培训",), ("无学习路径",)),
        ("content", "内容运营面板", "发布、表现、审核和任务", ("内容平台",), ("无内容生命周期",)),
        ("marketing", "营销活动面板", "活动、渠道、转化和预算", ("营销运营",), ("无归因数据",)),
        ("ecommerce", "电商经营面板", "订单、商品、库存和售后", ("零售电商",), ("纯线下流程",)),
        ("logistics", "物流调度面板", "在途、异常、时效和调度", ("物流运营",), ("无实时位置",)),
        ("manufacturing", "制造生产面板", "产量、停机、质量和工单", ("制造现场",), ("无设备数据",)),
        ("energy", "能源使用面板", "消耗、峰值、成本和异常", ("能源管理",), ("数据采样不稳定",)),
        ("asset", "资产健康面板", "资产状态、维护和风险", ("设备资产",), ("资产规模很小",)),
        ("support", "客户支持面板", "工单量、SLA、积压和满意度", ("服务中心",), ("无工单系统",)),
        ("product", "产品使用面板", "活跃、功能采用、路径和问题", ("产品运营",), ("无行为数据",)),
        ("mobile-summary", "移动管理摘要", "关键状态、风险和批准任务", ("移动管理者",), ("复杂分析",)),
        ("wallboard", "大屏态势墙", "远距离展示实时状态和异常", ("监控大屏",), ("交互分析",)),
        ("embedded", "嵌入式对象面板", "在对象详情中展示局部指标", ("对象级分析",), ("全局经营总览",)),
        ("narrative", "叙事汇报面板", "按结论、证据和建议组织数据", ("汇报沟通",), ("实时操作",)),
        ("comparative", "多区域对比面板", "并排比较单位、区域或团队", ("横向比较",), ("单一对象",)),
        ("forecast", "预测与情景面板", "历史、预测、假设和风险区间", ("计划预测",), ("无可靠模型",)),
    ),
    "workflow": (
        ("approval-queue", "审批队列", "证据和决策隔离", ("多条审批",), ("单条偶发审批",)),
        ("triage", "异常分诊", "按风险和影响快速分类", ("异常量大",), ("深度复杂调查",)),
        ("case-management", "案件管理", "对象、证据、历史和任务联动", ("跨阶段案件",), ("简单待办",)),
        ("sla-queue", "SLA 工单队列", "突出超时风险和下一动作", ("服务工单",), ("无 SLA",)),
        ("content-moderation", "内容审核", "预览、规则命中和决策", ("内容平台",), ("纯文本记录",)),
    ),
    "settings": (
        ("category-settings", "分类设置中心", "按稳定分类组织大量配置", ("设置项多",), ("少量设置",)),
        ("search-settings", "搜索优先设置", "通过搜索快速定位配置项", ("设置项多且用户知道名称",), ("探索式设置",)),
        ("policy-settings", "策略与权限设置", "规则、范围和生效影响清晰", ("策略配置",), ("普通偏好",)),
        ("profile-settings", "个人与团队资料", "资料、偏好、通知和安全分区", ("账户中心",), ("系统级配置",)),
        ("integration-settings", "集成连接中心", "连接状态、凭证、范围和日志", ("第三方集成",), ("无外部系统",)),
    ),
    "processing": (
        ("upload-queue", "上传处理队列", "文件、进度和失败恢复", ("多文件处理",), ("单个短上传",)),
        ("import-mapping", "导入映射流程", "字段映射、预览和错误导出", ("数据导入",), ("无结构化数据",)),
        ("media-processing", "媒体处理中心", "转码、预览、版本和失败", ("视频图片",), ("纯文本文件",)),
        ("batch-job", "批处理任务中心", "长任务阶段、日志和结果", ("后台任务",), ("即时请求",)),
        ("sync-center", "同步中心", "来源、差异、冲突和重试", ("多系统同步",), ("单一数据源",)),
    ),
    "communication": (
        ("message-inbox", "业务消息收件箱", "待办、提醒和系统消息分层", ("消息量大",), ("仅即时聊天",)),
        ("notification-feed", "通知动态流", "按时间展示跨对象变化", ("事件提醒",), ("需要深度会话",)),
        ("support-conversation", "服务对话工作台", "对话、客户信息和工单联动", ("客服",), ("纯内部通知",)),
        ("announcement-center", "公告中心", "重要程度、确认和历史", ("组织公告",), ("实时协作",)),
        ("collaboration-feed", "协作动态中心", "评论、提及、任务和文件更新", ("团队协作",), ("无协作对象",)),
    ),
    "field": (
        ("inspection-mobile", "移动巡检", "步骤、证据、异常和同步", ("巡检",), ("办公室录入",)),
        ("delivery-mobile", "配送交付", "路线、到达、签收和异常", ("物流现场",), ("无位置任务",)),
        ("maintenance-mobile", "现场维修", "设备、诊断、措施和耗材", ("维修维护",), ("简单确认",)),
        ("inventory-mobile", "移动盘点", "扫码、数量、差异和同步", ("库存盘点",), ("无条码",)),
        ("sales-visit-mobile", "销售拜访", "客户、签到、记录和下一步", ("外勤销售",), ("纯线上销售",)),
    ),
    "ai": (
        ("chat-research", "研究对话工作台", "会话、检索、引用和结论", ("知识研究",), ("单次短问答",)),
        ("document-copilot", "文档协作工作台", "文档、建议、版本和采纳", ("写作编辑",), ("无文档对象",)),
        ("code-agent", "代码 Agent 工作台", "任务、计划、工具、Diff 和测试", ("编程任务",), ("普通聊天",)),
        ("data-analyst", "数据分析工作台", "数据、问题、代码、图表和解释", ("分析任务",), ("无结构化数据",)),
        ("customer-agent", "客户服务 Agent", "会话、客户上下文、建议和人工接管", ("客服辅助",), ("完全自动无监督",)),
        ("workflow-agent", "流程执行 Agent", "任务步骤、工具调用、审批和恢复", ("长流程自动化",), ("简单问答",)),
        ("creative-studio", "创意生成工作台", "提示、素材、版本和比较", ("图文创作",), ("高精度业务录入",)),
        ("knowledge-curation", "知识整理工作台", "来源、提取、去重、结构化和发布", ("知识管理",), ("即时客服",)),
        ("multi-agent", "多 Agent 协作台", "角色、回合、证据和最终决策", ("复杂决策",), ("单模型简单任务",)),
        ("evaluation-lab", "AI 评测实验室", "样本、输出、评分、差异和回归", ("模型评测",), ("生产日常任务",)),
    ),
    "shell": (
        ("sidebar-shell", "侧边导航应用壳", "稳定多模块企业应用", ("模块多",), ("单页工具",)),
        ("top-nav-shell", "顶部导航应用壳", "模块少且层级浅", ("一级模块少",), ("复杂层级",)),
        ("workspace-shell", "多工作区应用壳", "团队、项目和环境切换", ("多租户多项目",), ("单一空间",)),
        ("command-shell", "命令优先应用壳", "专家高频跨模块操作", ("键盘专家",), ("低频新手",)),
        ("mobile-tab-shell", "移动底部导航壳", "少量稳定一级任务", ("移动应用",), ("模块超过五个",)),
    ),
}


def _skeletons() -> tuple[PageSkeleton, ...]:
    selected: list[PageSkeleton] = []
    # 50 top-level skeletons: 20 list/detail + 20 forms + 10 AI.  Dashboard,
    # workflow, settings, processing, communication, field, and shell remain
    # specialised composition catalogs and are routed independently.
    for family, limit in (("list-detail", 20), ("form", 20), ("ai", 10)):
        defaults = _FAMILY_DEFAULTS[family]
        for variant in _SKELETON_VARIANTS[family][:limit]:
            variant_id, name, goal, use_when, avoid_when = variant
            selected.append(PageSkeleton(
                f"{family}-{variant_id}", name, family, goal,
                (defaults["desktop"], defaults["tablet"], defaults["mobile"]),
                tuple(defaults["components"]), tuple(defaults["interactions"]), tuple(defaults["states"]),
                defaults["desktop"], defaults["tablet"], defaults["mobile"], tuple(use_when), tuple(avoid_when),
                ("主任务入口在首次视图可见", "窄屏不产生非必要横向滚动", "失败后保留用户上下文", "键盘与触控均可完成核心任务"),
            ))
    return tuple(selected)


PAGE_SKELETONS = _skeletons()


def _specialised_catalog(family: str) -> list[dict[str, Any]]:
    defaults = _FAMILY_DEFAULTS[family]
    return [
        {
            "id": f"{family}-{variant[0]}", "name": variant[1], "family": family, "goal": variant[2],
            "components": list(defaults["components"]), "interactions": list(defaults["interactions"]),
            "states": list(defaults["states"]), "composition": {"desktop": defaults["desktop"], "tablet": defaults["tablet"], "mobile": defaults["mobile"]},
            "useWhen": list(variant[3]), "avoidWhen": list(variant[4]),
        }
        for variant in _SKELETON_VARIANTS[family]
    ]


def dashboard_compositions() -> list[dict[str, Any]]: return _specialised_catalog("dashboard")
def form_patterns() -> list[dict[str, Any]]: return _specialised_catalog("form")
def list_detail_patterns() -> list[dict[str, Any]]: return _specialised_catalog("list-detail")
def ai_workspace_patterns() -> list[dict[str, Any]]: return _specialised_catalog("ai")


_INTERACTION_INTENTS: tuple[tuple[str, str, str, str, str, str, str, str], ...] = (
    ("search", "搜索", "输入或快捷键聚焦", "显示输入与匹配计数", "显示真实加载或本地过滤", "展示结果并保留条件", "说明无结果或请求失败", "调整或清除条件"),
    ("filter", "筛选", "选择筛选条件", "标记未应用或即时生效", "显示正在刷新结果", "显示生效标签和数量", "保留条件并说明失败范围", "局部重试或恢复上次结果"),
    ("sort", "排序", "点击列头或选择排序", "立即显示方向", "异步排序时保留当前数据", "更新顺序并播报字段", "恢复原顺序", "重试"),
    ("paginate", "分页/加载更多", "页码、下一页或滚动触发", "锁定重复触发", "显示局部骨架", "追加或替换并保持位置", "保留当前页", "重试当前页"),
    ("row-select", "对象选择", "点击、空格或多选框", "立即高亮并更新计数", "无需等待", "详情或批量操作可用", "不改变原选择", "重新选择"),
    ("bulk-action", "批量操作", "选择对象后触发动作", "显示对象数量和动作范围", "显示真实处理数量", "分别汇总成功失败", "保留失败项", "重试失败项或导出"),
    ("open-detail", "打开详情", "选择对象或 Enter", "保持列表选中", "详情区骨架", "聚焦详情标题", "保留列表和对象", "重新加载详情"),
    ("edit-inline", "行内编辑", "双击、编辑按钮或快捷键", "进入编辑并选中文本", "保存时锁定当前字段", "显示保存状态并退出", "保留原值和输入", "重试或撤销"),
    ("create", "新建对象", "主操作或快捷键", "打开空表单并聚焦首字段", "加载默认值", "保存后定位新对象", "保留草稿", "继续编辑或放弃"),
    ("save-draft", "保存草稿", "显式保存或自动保存", "显示已接收", "低干扰保存状态", "显示最后保存时间", "保留本地草稿", "重试或下载草稿"),
    ("validate", "校验", "离开字段、下一步或提交", "就近反馈", "远程校验显示字段级等待", "通过后继续", "错误摘要和字段定位", "修正后再次校验"),
    ("submit", "提交", "明确主操作", "按钮处理态并防重复", "显示真实阶段", "说明对象和后续状态", "保留输入和错误范围", "修正、重试或保存草稿"),
    ("approve", "批准", "明确决策动作", "显示对象和影响", "防止重复决策", "记录决定并进入下一项", "保留证据和意见", "重试或转交"),
    ("reject", "退回/拒绝", "决策动作并要求理由", "显示影响对象", "提交理由", "记录决定", "保留理由和对象", "重试或取消"),
    ("undo", "撤销", "Toast、快捷键或历史", "立即恢复视觉状态", "必要时同步后端", "说明已恢复", "保持当前状态并解释不可撤销", "打开历史或联系支持"),
    ("retry", "重试", "失败状态中的明确动作", "锁定重复触发", "只重试失败范围", "恢复成功内容", "更新失败原因", "稍后重试或导出"),
    ("upload", "上传", "选择或拖放文件", "立即进入队列并校验", "显示真实字节或阶段", "显示结果预览", "失败项独立保留", "重试、替换或移除"),
    ("pause-resume", "暂停与继续", "队列操作", "立即更新状态", "保留已完成进度", "从安全断点继续", "解释无法暂停或恢复", "重新开始失败项"),
    ("reorder", "重新排序", "拖动或键盘移动", "显示占位和目标位置", "无需后台时即时", "保存顺序并播报", "恢复原顺序", "重试保存"),
    ("expand-collapse", "展开与折叠", "点击或方向键", "图标和 aria-expanded 同步", "懒加载时显示局部进度", "显示内容并保持层级", "保持折叠", "重试加载"),
    ("switch-view", "视图切换", "Tab、分段控制或快捷键", "选中指示立即移动", "懒加载目标视图", "保留各视图状态", "返回原视图", "重试"),
    ("change-range", "时间范围切换", "选择预设或日期", "显示当前范围", "局部刷新图表", "更新所有关联数据", "保留旧数据并标记失败", "重试或恢复范围"),
    ("drill-down", "下钻", "点击指标或图表元素", "突出选择范围", "加载明细", "展示来源与返回路径", "保留上层上下文", "返回或重试"),
    ("stream", "流式生成", "发送请求", "立即显示接收和取消入口", "增量输出、工具和引用状态", "标记完整并提供采纳", "保留部分结果", "继续、重试或切换模型"),
    ("compare-version", "版本比较", "选择两个版本", "显示比较对象", "计算差异", "按区域展示新增删除修改", "保持版本选择", "重试或导出"),
)

_INTERACTION_MODALITIES = {
    "desktop-keyboard": {
        "suffix": "桌面键盘", "accessibility": "提供明确焦点、快捷键提示和可预测 Tab/方向键行为", "fallback": "鼠标与标准表单操作", "risk": "low",
    },
    "touch-mobile": {
        "suffix": "移动触控", "accessibility": "触控目标至少 44px，主操作位于易达区，屏幕阅读顺序清晰", "fallback": "单列布局和原生控件", "risk": "low",
    },
    "async-network": {
        "suffix": "异步网络", "accessibility": "使用 aria-busy 和克制 live region，状态不只依赖动画", "fallback": "手动刷新并保留上次成功内容", "risk": "medium",
    },
    "regulated-high-risk": {
        "suffix": "高风险受控", "accessibility": "明确对象、影响、确认和结果，错误摘要可定位", "fallback": "人工复核和逐项确认", "risk": "high",
    },
}


def _interactions() -> tuple[InteractionPattern, ...]:
    result: list[InteractionPattern] = []
    for intent_id, name, trigger, feedback, progress, completion, error, recovery in _INTERACTION_INTENTS:
        for modality, details in _INTERACTION_MODALITIES.items():
            result.append(InteractionPattern(
                f"{intent_id}-{modality}", f"{name} · {details['suffix']}", intent_id, modality,
                trigger, feedback, progress, completion, error, recovery,
                str(details["accessibility"]),
                ("started", "completed", "failed", "duration_ms", "recovery_used"),
                str(details["fallback"]), str(details["risk"]),
            ))
    return tuple(result)


INTERACTIONS = _interactions()


_BASE_STATES: tuple[tuple[str, str, str, str, str], ...] = (
    ("idle", "尚未开始当前任务", "展示明确主任务和入口", "开始任务", "保持当前筛选和导航"),
    ("loading", "数据正在加载", "使用与最终结构一致的骨架或局部进度", "取消非必要请求", "不清空已有上下文"),
    ("skeleton", "结构已知但内容未返回", "显示稳定布局占位", "等待或返回", "避免布局跳动"),
    ("empty-initial", "尚无业务对象", "解释原因和首次动作", "新建或导入", "不与筛选无结果混淆"),
    ("empty-filtered", "当前条件没有结果", "显示生效条件和清除入口", "清除或调整筛选", "保留用户输入"),
    ("validation-error", "输入不满足规则", "字段就近错误和摘要定位", "修正错误", "保留全部有效输入"),
    ("saving", "变更正在保存", "主操作进入真实处理态", "允许安全取消时取消", "保留草稿并防重复提交"),
    ("save-failed", "保存失败", "解释失败范围和是否已保留", "重试保存", "保留用户输入"),
    ("processing", "长任务正在执行", "显示阶段、完成量和可中断性", "查看、暂停或停止", "提供任务 ID 和恢复入口"),
    ("partial-success", "部分成功、部分失败", "分别展示成功与失败数量", "重试失败项", "保留成功结果和失败项"),
    ("success", "任务完成", "说明对象、结果和下一步", "继续、查看或撤销", "返回时保留上下文"),
    ("error", "任务无法继续", "说明原因、影响和安全路径", "重试或返回", "尽可能保留上下文"),
    ("offline", "网络不可用", "说明可离线能力和限制", "继续草稿或重试", "本地安全保存"),
    ("syncing", "离线内容正在同步", "展示队列和冲突风险", "查看同步详情", "保留本地与服务端版本"),
    ("stale", "数据已过期或被更新", "提示版本差异和时间", "刷新、比较或合并", "不静默覆盖"),
    ("conflict", "多人或多端修改冲突", "按字段展示差异", "选择版本或合并", "保留双方版本"),
    ("permission-denied", "当前角色无权限", "解释边界而不泄露内容", "返回或申请权限", "保留可访问上下文"),
    ("read-only", "当前内容只能查看", "明确原因和可申请路径", "返回或申请编辑", "不显示虚假可编辑控件"),
    ("unsaved", "存在未保存修改", "离开前说明影响", "保存、放弃或继续", "保留草稿"),
    ("cancelled", "任务已取消", "说明已完成部分和清理状态", "重新开始或返回", "保留可复用输入"),
)

_STATE_CONTEXTS: dict[str, dict[str, str]] = {
    "list-detail": {"subject":"记录与详情", "secondary":"返回列表", "layout":"状态覆盖数据区域但保留筛选和选择"},
    "form": {"subject":"表单与草稿", "secondary":"返回上一步", "layout":"状态就近字段并在顶部汇总"},
    "dashboard": {"subject":"指标与数据分区", "secondary":"查看数据时间", "layout":"局部失败不遮挡可用分区"},
    "workflow": {"subject":"任务、证据与决策", "secondary":"返回队列", "layout":"决策区和证据区分别表达状态"},
    "settings": {"subject":"配置与变更", "secondary":"恢复上次保存", "layout":"保留分类和变更摘要"},
    "processing": {"subject":"文件与处理任务", "secondary":"查看队列", "layout":"每项任务独立状态并提供批量汇总"},
    "communication": {"subject":"消息与关联对象", "secondary":"返回收件箱", "layout":"列表和内容分别保留状态"},
    "field": {"subject":"现场步骤与同步", "secondary":"保存离线草稿", "layout":"大触控状态卡和固定安全操作区"},
    "ai": {"subject":"生成内容、工具和引用", "secondary":"保留部分结果", "layout":"区分模型、工具和证据状态"},
    "shell": {"subject":"应用模块与会话", "secondary":"返回可访问模块", "layout":"全局状态不遮挡可用导航"},
}


def _states() -> tuple[ContextStatePattern, ...]:
    result: list[ContextStatePattern] = []
    for state_id, meaning, presentation, action, persistence in _BASE_STATES:
        for context, context_data in _STATE_CONTEXTS.items():
            result.append(ContextStatePattern(
                f"{context}-{state_id}", state_id, context,
                f"{context_data['subject']}：{meaning}",
                f"{context_data['layout']}；{presentation}", action, context_data["secondary"], persistence,
                "状态标题和结果可读；焦点移动符合任务；不只依赖颜色、图标或动画",
                ("用户知道发生了什么", "用户知道下一步", "已输入或已成功内容不会无故丢失", "状态可由键盘和辅助技术理解"),
            ))
    return tuple(result)


CONTEXT_STATES = _states()


_PATTERN_TO_FAMILY = {
    "data-workbench":"list-detail", "review-approval":"workflow", "guided-form":"form",
    "operations-dashboard":"dashboard", "settings-center":"settings", "upload-processing":"processing",
    "message-center":"communication", "task-center":"workflow", "mobile-field":"field", "ai-workspace":"ai",
}


def family_for_pattern(pattern_id: str) -> str:
    return _PATTERN_TO_FAMILY.get(pattern_id, "shell")


def component_catalog() -> list[dict[str, Any]]:
    return [item.to_dict() for item in COMPONENTS]


def page_skeleton_catalog() -> list[dict[str, Any]]:
    return [item.to_dict() for item in PAGE_SKELETONS]


def interaction_catalog() -> list[dict[str, Any]]:
    return [item.to_dict() for item in INTERACTIONS]


def state_catalog() -> list[dict[str, Any]]:
    return [item.to_dict() for item in CONTEXT_STATES]


def specialised_pattern_catalog() -> dict[str, list[dict[str, Any]]]:
    return {
        "dashboards": dashboard_compositions(), "forms": form_patterns(),
        "listDetails": list_detail_patterns(), "aiWorkspaces": ai_workspace_patterns(),
        "workflows": _specialised_catalog("workflow"), "settings": _specialised_catalog("settings"),
        "processing": _specialised_catalog("processing"), "communication": _specialised_catalog("communication"),
        "field": _specialised_catalog("field"), "shells": _specialised_catalog("shell"),
    }


def get_component(component_id: str) -> dict[str, Any]:
    for item in COMPONENTS:
        if item.id == component_id: return item.to_dict()
    raise KeyError(component_id)


def _variant_score(item: Mapping[str, Any], model: Mapping[str, Any], observed: Mapping[str, Any]) -> tuple[int, list[str]]:
    text = " ".join(str(value) for value in (*model.get("painPoints", []), *model.get("operations", []), model.get("primaryTask") or "")).casefold()
    score = 40; reasons: list[str] = []
    variant_id = str(item.get("id") or "")
    density = str(model.get("informationDensity") or "unknown")
    device = str(model.get("devicePriority") or "unknown")
    expertise = str(model.get("userExpertise") or "unknown")
    risk = str(model.get("risk") or "unknown")
    controls = int(observed.get("controls") or 0); columns = int(observed.get("columns") or 0); rows = int(observed.get("rows") or 0)
    if "dense" in variant_id or "grid" in variant_id:
        if density == "high" and expertise == "expert": score += 28; reasons.append("高密度专家任务")
        if device == "mobile": score -= 24
    if any(token in variant_id for token in ("card", "mobile", "field")) and device == "mobile":
        score += 26; reasons.append("移动优先")
    if any(token in variant_id for token in ("wizard", "review-submit", "approval")) and risk in {"high", "regulated"}:
        score += 24; reasons.append("高风险任务需要复核")
    if "inline" in variant_id and controls <= 6 and risk in {"low", "medium"}:
        score += 18; reasons.append("少量低风险字段适合快速编辑")
    if "split" in variant_id and rows >= 6:
        score += 18; reasons.append("多记录连续核对")
    if "route" in variant_id and (columns >= 8 or controls >= 12):
        score += 16; reasons.append("详情或编辑复杂度较高")
    keywords = {
        "upload": ("上传", "upload", "导入"), "inventory": ("库存", "批次", "inventory"),
        "crm": ("客户", "销售", "crm"), "service": ("工单", "售后", "ticket"),
        "finance": ("财务", "金额", "finance"), "permission": ("权限", "角色", "permission"),
        "content": ("内容", "审核", "content"), "inspection": ("巡检", "检查", "inspection"),
        "ai": ("ai", "生成", "agent", "模型"), "code": ("代码", "code", "bug"),
    }
    for key, values in keywords.items():
        if key in variant_id and any(value in text for value in values):
            score += 20; reasons.append(f"任务语义匹配 {key}")
    return max(0, min(100, score)), reasons


def route_skeletons(pattern_id: str, model: Mapping[str, Any], observed: Mapping[str, Any], *, limit: int = 5) -> list[dict[str, Any]]:
    family = family_for_pattern(pattern_id)
    items: list[dict[str, Any]]
    if family == "list-detail": items = list_detail_patterns()
    elif family == "form": items = form_patterns()
    elif family == "ai": items = ai_workspace_patterns()
    else: items = _specialised_catalog(family)
    ranked: list[dict[str, Any]] = []
    for item in items:
        score, reasons = _variant_score(item, model, observed)
        ranked.append({**item, "score": score, "reasons": reasons})
    ranked.sort(key=lambda value: (-int(value["score"]), str(value["id"])))
    return ranked[:max(1, limit)]


def select_interactions(intents: Iterable[str], model: Mapping[str, Any]) -> list[dict[str, Any]]:
    modality = "regulated-high-risk" if model.get("risk") in {"high", "regulated"} else "touch-mobile" if model.get("devicePriority") == "mobile" else "async-network"
    by_id = {item.id: item for item in INTERACTIONS}
    selected: list[dict[str, Any]] = []
    for raw in intents:
        intent = str(raw).strip().casefold().replace("_", "-")
        aliases = {
            "搜索筛选":"search", "搜索":"search", "筛选":"filter", "排序":"sort", "详情预览":"open-detail",
            "草稿保存":"save-draft", "保存":"save-draft", "通过/退回":"approve", "批准":"approve", "退回":"reject",
            "拖放/选择":"upload", "暂停/重试":"pause-resume", "流式生成":"stream", "版本比较":"compare-version",
            "局部刷新":"change-range", "异常下钻":"drill-down", "批量操作":"bulk-action", "即时校验":"validate",
        }
        intent = aliases.get(intent, intent)
        candidate = by_id.get(f"{intent}-{modality}") or by_id.get(f"{intent}-async-network") or by_id.get(f"{intent}-desktop-keyboard")
        if candidate and candidate.id not in {item["id"] for item in selected}:
            selected.append(candidate.to_dict())
    return selected


def contextual_states(pattern_id: str, required_states: Sequence[str]) -> list[dict[str, Any]]:
    family = family_for_pattern(pattern_id)
    index = {(item.context, item.state): item for item in CONTEXT_STATES}
    aliases = {"initial-empty":"empty-initial", "no-result":"empty-filtered", "partial-error":"partial-success", "queue-empty":"empty-initial", "draft":"unsaved", "submitting":"saving", "save-failed":"save-failed", "partial-data":"partial-success", "no-alert":"empty-filtered", "uploading":"processing", "partial-failure":"partial-success", "paused":"cancelled", "unread":"idle", "read":"success", "queue-empty":"empty-initial", "overdue":"stale", "blocked":"error", "thinking":"loading", "streaming":"processing", "tool-running":"processing", "partial":"partial-success", "complete":"success"}
    result: list[dict[str, Any]] = []
    for raw in required_states:
        state = aliases.get(raw, raw)
        item = index.get((family, state))
        if item and item.id not in {entry["id"] for entry in result}:
            result.append(item.to_dict())
    for state in ("loading", "error", "success"):
        item = index[(family, state)]
        if item.id not in {entry["id"] for entry in result}: result.append(item.to_dict())
    return result


def catalog_metrics() -> dict[str, int]:
    specialised = specialised_pattern_catalog()
    return {
        "components": len(COMPONENTS), "pageSkeletons": len(PAGE_SKELETONS),
        "interactions": len(INTERACTIONS), "contextualStates": len(CONTEXT_STATES),
        "dashboardCompositions": len(specialised["dashboards"]), "formPatterns": len(specialised["forms"]),
        "listDetailPatterns": len(specialised["listDetails"]), "aiWorkspacePatterns": len(specialised["aiWorkspaces"]),
    }


def get_skeleton(skeleton_id: str) -> dict[str, Any]:
    """Return one exact page skeleton from either the top-level or specialised catalog."""
    target = str(skeleton_id).strip()
    for item in page_skeleton_catalog():
        if item["id"] == target:
            return item
    for items in specialised_pattern_catalog().values():
        for item in items:
            if item["id"] == target:
                return item
    raise KeyError(f"unknown experience skeleton: {target}")
