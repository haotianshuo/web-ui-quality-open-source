"""Interaction and state contract generator for enterprise UI patterns."""
from __future__ import annotations

from typing import Any, Mapping, Sequence


_STATE_LIBRARY: dict[str, dict[str, str]] = {
    "loading": {"meaning":"首次或局部数据正在加载", "presentation":"保留页面骨架并显示与最终结构一致的 skeleton", "action":"允许取消非必要请求；不显示虚假进度", "a11y":"使用 aria-busy 与可读状态文本", "persistence":"不清空现有上下文"},
    "initial-empty": {"meaning":"当前业务对象尚不存在", "presentation":"解释为空原因并展示可执行下一步", "action":"新建、导入或返回", "a11y":"标题说明空状态语义", "persistence":"不与筛选无结果混淆"},
    "no-result": {"meaning":"当前搜索或筛选没有匹配结果", "presentation":"显示生效条件和清除入口", "action":"清除或调整筛选", "a11y":"结果区域使用 live region 克制播报", "persistence":"保留用户输入"},
    "validation-error": {"meaning":"输入不满足当前规则", "presentation":"字段就近错误 + 页面摘要定位", "action":"修正后继续", "a11y":"aria-describedby 关联错误", "persistence":"保留全部有效输入"},
    "partial-error": {"meaning":"部分数据或操作失败", "presentation":"保留成功内容并标出失败范围", "action":"局部重试或导出失败项", "a11y":"明确成功与失败数量", "persistence":"避免整页重置"},
    "error": {"meaning":"当前任务无法继续", "presentation":"说明原因、影响和安全返回路径", "action":"重试、返回或联系支持", "a11y":"聚焦错误摘要", "persistence":"尽可能保留上下文"},
    "saving": {"meaning":"变更正在保存", "presentation":"主操作进入处理态并防重复提交", "action":"允许安全取消时提供取消", "a11y":"按钮名称包含处理中", "persistence":"保留草稿"},
    "processing": {"meaning":"长任务正在后台执行", "presentation":"显示阶段、已完成量和可中断性", "action":"查看详情、停止或稍后返回", "a11y":"避免频繁 live 更新", "persistence":"提供任务 ID 和恢复入口"},
    "success": {"meaning":"任务已完成", "presentation":"说明结果、对象和下一步", "action":"继续处理、查看结果或撤销", "a11y":"使用简短状态消息", "persistence":"返回时保留上下文"},
    "permission-denied": {"meaning":"当前角色无权限", "presentation":"解释权限边界而非空白页", "action":"返回可访问区域或申请权限", "a11y":"标题明确无权限", "persistence":"不泄露受限内容"},
    "stale": {"meaning":"数据已被他人更新或超时", "presentation":"对比版本并阻止静默覆盖", "action":"刷新、合并或放弃本地修改", "a11y":"解释冲突对象", "persistence":"保留本地草稿"},
    "offline": {"meaning":"网络不可用", "presentation":"显示离线状态和可用能力", "action":"继续离线草稿或重试同步", "a11y":"状态变化可感知", "persistence":"本地安全保存"},
    "unsaved": {"meaning":"存在未保存修改", "presentation":"导航离开前提示具体影响", "action":"保存、放弃或继续编辑", "a11y":"对话框聚焦和 Escape 语义明确", "persistence":"保存草稿或明确丢弃"},
    "conflict": {"meaning":"多人或多端修改冲突", "presentation":"展示差异而非简单覆盖", "action":"选择版本、合并或重新加载", "a11y":"差异按字段可读", "persistence":"保留双方版本"},
}


def _include_for(model: Mapping[str, Any], pattern: Mapping[str, Any]) -> list[str]:
    required = list(pattern.get("requiredStates", []))
    result = [state for state in required if state in _STATE_LIBRARY]
    task = model.get("taskType"); risk = model.get("risk"); frequency = model.get("frequency")
    for state in ("loading", "error", "success"):
        if state not in result: result.append(state)
    if task == "find-compare" and "no-result" not in result: result.append("no-result")
    if task == "create-edit":
        for state in ("validation-error", "saving", "unsaved"):
            if state not in result: result.append(state)
    if risk in {"high", "regulated"}:
        for state in ("permission-denied", "stale", "conflict"):
            if state not in result: result.append(state)
    if model.get("environment") == "mobile-field":
        for state in ("offline", "processing"):
            if state not in result: result.append(state)
    if frequency in {"continuous", "daily"} and "partial-error" not in result: result.append("partial-error")
    return result


def build_interaction_contract(model: Mapping[str, Any], pattern: Mapping[str, Any]) -> dict[str, Any]:
    states = _include_for(model, pattern)
    state_details = [{"id": state, **_STATE_LIBRARY[state]} for state in states]
    destructive = list(model.get("highRiskActions", []))
    return {
        "primaryTask": model.get("primaryTask") or pattern.get("summary"),
        "primaryInteractions": list(pattern.get("primaryInteractions", [])),
        "stateCoverage": state_details,
        "feedbackContract": {
            "received":"交互后 100ms 内出现按压、选中或处理反馈", "progress":"等待超过 400ms 时展示真实等待状态",
            "result":"成功或失败都说明对象和结果", "recovery":"失败必须提供下一步且保留可恢复数据",
        },
        "navigationMemory": ["筛选", "分页", "选中对象", "滚动位置", "焦点", "未提交草稿"],
        "keyboard": ["Tab 顺序与视觉顺序一致", "Enter/Space 激活控件", "Escape 关闭临时层并返回触发点", "方向键仅用于明确的复合控件"],
        "touch": {"minimumTarget":"44px", "preferredTarget":"48px" if model.get("devicePriority") == "mobile" else "44px", "singleHand":"主要操作位于易达区域"},
        "motion": {"purpose":"只用于状态连续性、层级变化和反馈", "interruptible":True, "reducedMotion":"必须提供无动画退化"},
        "destructiveActions": [{"name": action, "treatment":"与主操作隔离；明确对象、影响、可逆性；逐操作确认"} for action in destructive],
        "acceptanceCriteria": [
            "用户能在首次进入后识别主任务和下一步", "所有适用状态互斥且有恢复动作", "返回后不丢失核心上下文",
            "移动键盘、抽屉和固定操作区不遮挡当前字段", "高风险操作不会因视觉降级而不可发现，也不会与主操作同权重",
        ],
    }
