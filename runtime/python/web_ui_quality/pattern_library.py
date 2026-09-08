"""Modern enterprise page-pattern library and deterministic router."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence


@dataclass(frozen=True, slots=True)
class Pattern:
    id: str
    name: str
    category: str
    summary: str
    suitable_tasks: tuple[str, ...]
    page_modes: tuple[str, ...]
    desktop: str
    tablet: str
    mobile: str
    primary_interactions: tuple[str, ...]
    required_states: tuple[str, ...]
    modern_features: tuple[str, ...]
    fallbacks: tuple[str, ...]
    risks: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "name": self.name, "category": self.category, "summary": self.summary,
            "suitableTasks": list(self.suitable_tasks), "pageModes": list(self.page_modes),
            "composition": {"desktop": self.desktop, "tablet": self.tablet, "mobile": self.mobile},
            "primaryInteractions": list(self.primary_interactions), "requiredStates": list(self.required_states),
            "modernFeatures": list(self.modern_features), "fallbacks": list(self.fallbacks), "risks": list(self.risks),
        }


PATTERNS: tuple[Pattern, ...] = (
    Pattern("data-workbench", "搜索与筛选优先的数据主从工作台", "enterprise-data", "高频查找、比较和连续核对记录。",
        ("find-compare", "review-confirm"), ("列表和详情",),
        "稳定筛选栏 + 可调密度列表/表格 + 同页详情面板", "单列列表 + 可展开详情区", "列表与详情使用连续视图切换",
        ("搜索筛选", "键盘移动选中", "详情预览", "批量操作", "返回上下文恢复"),
        ("loading", "initial-empty", "no-result", "partial-error", "selected", "permission-denied", "stale"),
        ("container-queries", "view-transitions", "scroll-state-queries"),
        ("媒体查询退化", "无动画即时切换", "sticky 边框常驻"),
        ("字段过多时需列管理", "详情过长时应升级独立路由")),
    Pattern("review-approval", "审核与审批工作台", "enterprise-workflow", "隔离判断、证据和高风险动作。",
        ("review-confirm",), ("列表和详情", "表单和向导"),
        "队列 + 证据摘要 + 独立审批区", "队列与审批区上下排列", "任务队列与单条审核分屏切换",
        ("领取任务", "证据核对", "通过/退回", "备注", "下一条"),
        ("loading", "queue-empty", "validation-error", "submitting", "success", "conflict", "permission-denied"),
        ("container-queries", "view-transitions", "popover-api"),
        ("媒体查询", "普通 dialog", "内联帮助"),
        ("审批动作必须逐项确认", "需要真实权限和审计链")),
    Pattern("guided-form", "引导式任务表单", "enterprise-form", "为低频、复杂或新手任务提供分组和恢复。",
        ("create-edit", "review-confirm"), ("表单和向导",),
        "章节导航 + 分组表单 + 固定摘要/操作区", "顶部进度 + 单列章节", "单列步骤或分段表单",
        ("渐进披露", "即时校验", "草稿保存", "错误定位", "复核提交"),
        ("loading", "draft", "validation-error", "saving", "save-failed", "success", "unsaved", "session-expired"),
        ("container-queries", "view-transitions", "anchor-positioning"),
        ("媒体查询", "即时切换", "普通定位提示"),
        ("不应机械拆分所有字段", "移动键盘可能遮挡主操作")),
    Pattern("operations-dashboard", "状态—异常—任务驾驶舱", "enterprise-dashboard", "先回答当前情况、异常和下一项工作。",
        ("monitor-respond", "find-compare"), ("Dashboard", "应用外壳"),
        "状态摘要 + 异常队列 + 趋势与任务分区", "两列重排为主次区块", "状态、异常、任务优先，图表折叠为摘要",
        ("时间范围", "异常下钻", "任务领取", "局部刷新", "告警确认"),
        ("loading", "partial-data", "stale", "no-alert", "error", "offline", "success"),
        ("container-queries", "scroll-driven-animation", "scroll-state-queries"),
        ("媒体查询", "无动画", "固定摘要样式"),
        ("避免装饰性 KPI", "颜色必须配合文字和趋势")),
    Pattern("settings-center", "分层设置中心", "enterprise-settings", "组织复杂配置并降低误操作。",
        ("configure",), ("表单和向导", "应用外壳"),
        "分类导航 + 设置详情 + 变更摘要", "顶部分类 + 单列设置", "搜索优先的分类列表与独立详情",
        ("设置搜索", "分组编辑", "即时预览", "恢复默认", "保存摘要"),
        ("loading", "read-only", "unsaved", "saving", "success", "permission-denied", "conflict"),
        ("container-queries", "anchor-positioning", "view-transitions"),
        ("媒体查询", "普通绝对定位", "即时切换"),
        ("高风险设置应独立确认", "默认值必须清楚")),
    Pattern("upload-processing", "上传与处理队列", "enterprise-processing", "支持多文件、长任务和失败恢复。",
        ("create-edit", "monitor-respond"), ("表单和向导", "列表和详情"),
        "上传区 + 队列 + 处理详情", "队列主导，详情下置", "单手上传入口 + 任务卡片",
        ("拖放/选择", "队列管理", "暂停/重试", "错误定位", "结果预览"),
        ("idle", "uploading", "processing", "partial-failure", "paused", "success", "offline"),
        ("container-queries", "view-transitions", "popover-api"),
        ("媒体查询", "即时切换", "内联帮助"),
        ("真实上传必须受授权", "进度不能伪造")),
    Pattern("message-center", "消息与通知中心", "enterprise-communication", "区分待办、提醒、系统消息和已读状态。",
        ("communicate", "monitor-respond"), ("列表和详情", "应用外壳"),
        "消息分组 + 列表 + 内容详情", "列表与内容上下切换", "消息列表到内容的连续切换",
        ("筛选", "已读/未读", "批量处理", "跳转业务对象", "通知设置"),
        ("loading", "initial-empty", "no-result", "unread", "read", "error", "offline"),
        ("container-queries", "view-transitions", "scroll-state-queries"),
        ("媒体查询", "即时切换", "固定分隔线"),
        ("避免所有消息同权重", "跳转需保留来源上下文")),
    Pattern("task-center", "任务队列中心", "enterprise-task", "集中处理待办、优先级、截止时间和进度。",
        ("review-confirm", "monitor-respond"), ("列表和详情", "Dashboard"),
        "优先级摘要 + 队列 + 详情/执行区", "优先级筛选 + 单列队列", "今日任务和下一动作优先",
        ("领取", "排序", "筛选", "执行", "完成/转交"),
        ("loading", "queue-empty", "overdue", "processing", "blocked", "success", "conflict"),
        ("container-queries", "view-transitions", "scroll-state-queries"),
        ("媒体查询", "即时切换", "sticky 常驻样式"),
        ("优先级规则需业务确认", "完成动作需防重复")),
    Pattern("mobile-field", "移动现场作业", "field-operations", "适合强光、单手、扫码和弱网环境。",
        ("review-confirm", "create-edit", "find-compare"), ("列表和详情", "表单和向导"),
        "桌面仅作为管理回看", "大触控单列任务", "步骤化任务卡 + 固定底部操作",
        ("扫码/拍照", "大按钮", "离线草稿", "任务步骤", "确认反馈"),
        ("loading", "offline", "syncing", "draft", "validation-error", "success", "permission-denied"),
        ("container-queries", "view-transitions", "scroll-state-queries"),
        ("媒体查询", "即时切换", "固定底部栏"),
        ("必须验证强光和触摸", "弱网状态需真实后端支持")),
    Pattern("ai-workspace", "AI 协作工作台", "ai-product", "将输入、生成过程、结果、引用和人工控制放在同一任务上下文。",
        ("communicate", "create-edit", "monitor-respond"), ("应用外壳", "列表和详情"),
        "会话/任务列表 + 生成画布 + 证据与控制面板", "主画布 + 可折叠侧栏", "输入—过程—结果单列流",
        ("输入", "流式生成", "停止", "重试", "引用查看", "版本比较", "人工采纳"),
        ("idle", "thinking", "streaming", "tool-running", "partial", "error", "cancelled", "complete"),
        ("container-queries", "view-transitions", "popover-api"),
        ("媒体查询", "即时切换", "内联详情"),
        ("必须区分模型输出与事实", "长任务需可中断和恢复")),
)


def _score(pattern: Pattern, model: Mapping[str, Any], page_modes: Sequence[str], observed: Mapping[str, Any]) -> tuple[int, list[str], list[str]]:
    score = 20; reasons: list[str] = []; penalties: list[str] = []
    task = str(model.get("taskType") or "unknown")
    if task in pattern.suitable_tasks:
        score += 28; reasons.append(f"任务类型 {task} 与模式匹配")
    if any(mode in pattern.page_modes for mode in page_modes):
        score += 24; reasons.append("页面模式与模式库适用范围匹配")
    if "列表和详情" in page_modes and pattern.id == "data-workbench":
        score += 14; reasons.append("列表详情页面默认优先保证查找、比较与上下文恢复")
    if "表单和向导" in page_modes and pattern.id == "guided-form":
        score += 14; reasons.append("表单页面默认优先保证分组、校验与恢复")
    if ("Dashboard" in page_modes or "应用外壳" in page_modes) and pattern.id == "operations-dashboard":
        score += 14; reasons.append("仪表盘默认优先状态、异常与任务")
    environment = str(model.get("environment") or "unknown")
    expertise = str(model.get("userExpertise") or "unknown")
    density = str(model.get("informationDensity") or "unknown")
    device = str(model.get("devicePriority") or "unknown")
    risk = str(model.get("risk") or "unknown")
    frequency = str(model.get("frequency") or "unknown")
    if pattern.id == "mobile-field" and (environment == "mobile-field" or device == "mobile"):
        score += 35; reasons.append("现场或移动优先环境")
    if pattern.id == "data-workbench" and density == "high":
        score += 18; reasons.append("高信息密度需要稳定比较")
    if pattern.id == "guided-form" and expertise == "novice":
        score += 16; reasons.append("新手用户需要明确引导和恢复")
    if pattern.id == "review-approval" and risk in {"high", "regulated"}:
        score += 22; reasons.append("高风险任务需要隔离证据和动作")
    if pattern.id in {"data-workbench", "task-center"} and frequency in {"continuous", "daily"}:
        score += 15; reasons.append("高频任务需要减少跳转")
    if pattern.id == "operations-dashboard" and int(observed.get("metrics") or 0) >= 3:
        score += 18; reasons.append("观察到多个业务指标")
    if pattern.id == "upload-processing" and any(x in " ".join(model.get("operations", [])).casefold() for x in ("上传", "upload", "处理", "process")):
        score += 24; reasons.append("操作语义包含上传或处理")
    if pattern.id == "message-center" and any(x in " ".join(model.get("operations", [])).casefold() for x in ("消息", "通知", "message", "notification")):
        score += 24; reasons.append("操作语义包含消息或通知")
    if pattern.id == "ai-workspace" and any(x in " ".join(model.get("operations", [])).casefold() for x in ("ai", "生成", "对话", "agent")):
        score += 28; reasons.append("观察到 AI 或生成式任务")
    if pattern.id == "data-workbench" and device == "mobile":
        score -= 8; penalties.append("移动优先时必须退化为视图切换")
    if pattern.id == "operations-dashboard" and int(observed.get("metrics") or 0) == 0:
        score -= 18; penalties.append("缺少指标证据")
    if pattern.id == "guided-form" and int(observed.get("controls") or 0) < 3:
        score -= 12; penalties.append("控件数量不足以支持复杂表单")
    return max(0, min(100, score)), reasons, penalties


def route_patterns(model: Mapping[str, Any], page_modes: Sequence[str], observed: Mapping[str, Any], *, limit: int = 4) -> list[dict[str, Any]]:
    ranked: list[dict[str, Any]] = []
    for pattern in PATTERNS:
        score, reasons, penalties = _score(pattern, model, page_modes, observed)
        item = pattern.to_dict(); item.update({"score": score, "reasons": reasons, "penalties": penalties})
        ranked.append(item)
    ranked.sort(key=lambda item: (-item["score"], item["id"]))
    top = ranked[:max(1, limit)]
    gap = top[0]["score"] - (top[1]["score"] if len(top) > 1 else 0)
    confidence = "high" if gap >= 18 and model.get("confidence") == "high" else "medium" if gap >= 7 else "low"
    for index, item in enumerate(top):
        item["status"] = "selected" if index == 0 else "alternative"
        item["confidence"] = confidence if index == 0 else None
    return top


def get_pattern(pattern_id: str) -> Pattern:
    for item in PATTERNS:
        if item.id == pattern_id:
            return item
    raise KeyError(pattern_id)
