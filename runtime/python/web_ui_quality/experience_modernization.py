"""User-experience-led modernization strategy for existing enterprise Web UIs.

This module does not add another scanner. It turns the evidence already produced
by Experience Core into an ordered, explainable delivery strategy. Every item
must connect user impact to a repair, a completion check, and an isolation
boundary so optional capabilities cannot contaminate the primary task.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from .contracts import digest_json


_CATEGORY_WEIGHT = {
    "layout": 18,
    "responsive": 18,
    "interaction": 17,
    "accessibility": 16,
    "performance": 14,
    "layering": 13,
    "visual-system": 11,
    "typography": 10,
    "motion": 8,
    "maintainability": 4,
}
_SEVERITY_WEIGHT = {"UX1": 72, "UX2": 48, "UX3": 24}
_BASE_REQUIRED_STATES = {"loading", "error", "success"}


def _nonempty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def expected_state_ids(model: Mapping[str, Any]) -> set[str]:
    """Return the state IDs required by the same contract as Interaction Core.

    Keeping this small contract shared by the strategy and readiness score avoids
    a plan being marked ready merely because it contains one well-formed state.
    """
    required = set(_BASE_REQUIRED_STATES)
    task = str(model.get("taskType") or "")
    risk = str(model.get("risk") or "")
    environment = str(model.get("environment") or "")
    frequency = str(model.get("frequency") or "")
    if task == "find-compare":
        required.add("no-result")
    if task == "create-edit":
        required.update({"validation-error", "saving", "unsaved"})
    if risk in {"high", "regulated"}:
        required.update({"permission-denied", "stale", "conflict"})
    if environment == "mobile-field":
        required.update({"offline", "processing"})
    if frequency in {"continuous", "daily"}:
        required.add("partial-error")
    return required


def _grounded_task(model: Mapping[str, Any]) -> bool:
    """A task is grounded only when it is explicit and model confidence is usable."""
    return (
        _nonempty_text(model.get("primaryTask"))
        and str(model.get("confidence") or "") in {"medium", "high"}
    )


def _responsive_composition(skeleton: Mapping[str, Any]) -> bool:
    """Require all three responsive compositions; a truthy region list is not enough."""
    composition = skeleton.get("composition")
    if isinstance(composition, Mapping):
        return all(_nonempty_text(composition.get(key)) for key in ("desktop", "tablet", "mobile"))
    return all(_nonempty_text(skeleton.get(key)) for key in ("desktop", "tablet", "mobile"))


def _items(value: Any) -> list[Any]:
    return list(value) if isinstance(value, (list, tuple)) else []


def _priority_score(finding: Mapping[str, Any], model: Mapping[str, Any]) -> int:
    category = str(finding.get("category") or "")
    score = _SEVERITY_WEIGHT.get(str(finding.get("severity") or ""), 18)
    score += _CATEGORY_WEIGHT.get(category, 6)
    if str(model.get("frequency")) in {"continuous", "daily"}:
        score += 7
    if str(model.get("risk")) in {"high", "regulated"} and category in {"interaction", "accessibility", "layering", "responsive"}:
        score += 9
    if str(model.get("devicePriority")) == "mobile" and category in {"responsive", "layout", "interaction", "typography"}:
        score += 8
    return min(100, score)


def _tier(score: int, severity: str) -> tuple[str, str]:
    if severity == "UX1" or score >= 88:
        return "must-fix", "daily-user-impact"
    if severity == "UX2" or score >= 62:
        return "should-fix", "high-user-impact"
    return "later", "maintenance-or-polish"


def _repair_priorities(plan: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    model = plan.get("experienceModel") or {}
    repair = plan.get("uxRepairPlan") or {}
    priorities: list[dict[str, Any]] = []
    for finding in _items(repair.get("findings")):
        if not isinstance(finding, Mapping):
            continue
        severity = str(finding.get("severity") or "UX3")
        score = _priority_score(finding, model)
        delivery, user_value = _tier(score, severity)
        priorities.append({
            "id": str(finding.get("id") or "UX-UNNAMED"),
            "score": score,
            "delivery": delivery,
            "userValue": user_value,
            "category": str(finding.get("category") or "experience"),
            "source": "ux-repair-evidence",
            "evidence": finding.get("evidence"),
            "userImpact": finding.get("userImpact"),
            "action": finding.get("repair"),
            "modernOption": finding.get("modernOption"),
            "fallback": finding.get("fallback"),
            "completionEvidence": _items(finding.get("verification")),
            "isolation": "在所属组件或布局 owner 内修复；失败时回退到现有行为，不改变业务语义。",
        })

    interaction = plan.get("interactionContract") or {}
    pattern = plan.get("selectedPattern") or {}
    baseline = (
        {
            "id": "EXP-TASK-CLARITY", "score": 96, "delivery": "must-fix", "userValue": "daily-user-impact",
            "category": "interaction", "source": "experience-model",
            "evidence": model.get("primaryTask") or pattern.get("summary"),
            "userImpact": "用户进入页面后必须立即知道当前任务、优先信息和下一步。",
            "action": "围绕主任务重排首屏、主操作和状态；隐藏或后置低频高级项。",
            "modernOption": "使用任务优先骨架和渐进披露。", "fallback": "保留现有路由，仅调整层级与标签。",
            "completionEvidence": ["首次进入可识别主任务", "主操作名称对应用户意图", "危险操作与主操作隔离"],
            "isolation": "只调整呈现和任务顺序；业务规则、权限和数据保持不变。",
        },
        {
            "id": "EXP-STATE-RECOVERY", "score": 94, "delivery": "must-fix", "userValue": "daily-user-impact",
            "category": "interaction", "source": "interaction-contract",
            "evidence": f"{len(_items(interaction.get('stateCoverage')))} 个适用状态",
            "userImpact": "加载、无数据、失败、权限和冲突时，用户仍要知道发生了什么以及如何继续。",
            "action": "为每个适用状态实现原因、下一步、上下文保留和可访问反馈。",
            "modernOption": "局部状态边界、可取消请求和非阻塞恢复。", "fallback": "服务端/页面级明确错误与返回路径。",
            "completionEvidence": ["每个适用状态有恢复动作", "失败不清空有效输入", "权限状态不泄露内容"],
            "isolation": "状态失败限制在数据区或任务区，不重置整个应用壳层。",
        },
        {
            "id": "EXP-RESPONSIVE-COMPOSITION", "score": 92, "delivery": "must-fix", "userValue": "daily-user-impact",
            "category": "responsive", "source": "selected-skeleton",
            "evidence": (plan.get("selectedSkeleton") or {}).get("id"),
            "userImpact": "手机、中间宽度和桌面必须保留相同任务能力，而不是把桌面页面缩小。",
            "action": "分别定义三档构图、信息优先级、表格策略、触控区和安全区。",
            "modernOption": "Container Queries 负责组件重组，Media Queries 负责应用壳层。",
            "fallback": "Grid/Flex + 媒体查询 + 局部横向滚动。",
            "completionEvidence": ["320px 无页面级横向滚动", "中间宽度有明确重组", "桌面内容不过度拉伸"],
            "isolation": "组件级适配互不污染；新 CSS 不可用时走基础布局。",
        },
    )
    priorities.sort(key=lambda item: (-int(item["score"]), str(item["id"])))
    for index, item in enumerate(priorities, 1):
        item["rank"] = index
    return {
        "now": [item for item in priorities if item["delivery"] == "must-fix"][:10],
        "next": [item for item in priorities if item["delivery"] == "should-fix"][:10],
        "later": [item for item in priorities if item["delivery"] == "later"][:10],
        # These are universal acceptance gates, not defects.  Keeping them out
        # of now/next/later prevents a clean page from receiving fabricated
        # must-fix findings while preserving the guidance for implementation.
        "acceptanceGates": [
            {**item, "delivery": "acceptance-gate", "rank": index}
            for index, item in enumerate(baseline, 1)
        ],
    }


def _journeys(plan: Mapping[str, Any]) -> list[dict[str, Any]]:
    model = plan.get("experienceModel") or {}
    interaction = plan.get("interactionContract") or {}
    patterns = [item for item in _items(interaction.get("selectedInteractionPatterns")) if isinstance(item, Mapping)]
    states = [item for item in _items(interaction.get("stateCoverage")) if isinstance(item, Mapping)]
    primary_steps = [{
        "intent": item.get("intent"),
        "trigger": item.get("trigger"),
        "feedback": item.get("immediate_feedback"),
        "completion": item.get("completion"),
    } for item in patterns[:4]]
    return [
        {
            "id": "first-success", "type": "first-time", "userIntent": model.get("primaryTask"),
            "steps": primary_steps,
            "completionSignal": "用户完成主任务并理解结果和下一步。",
            "recovery": "任何失败都保留已完成内容并提供返回或重试。",
            "metrics": ["taskCompletionMs", "steps", "errors", "helpRequests"],
        },
        {
            "id": "repeat-efficiency", "type": "repeat-use", "userIntent": model.get("primaryTask"),
            "steps": [{"restore": item} for item in _items(interaction.get("navigationMemory"))],
            "completionSignal": "高频用户无需重复输入即可继续上一任务上下文。",
            "recovery": "恢复失败时清楚说明哪些上下文未恢复。",
            "metrics": ["repeatTaskCompletionMs", "repeatedEntryCount", "contextSwitches"],
        },
        {
            "id": "failure-recovery", "type": "recovery", "userIntent": "从失败、权限、冲突或离线状态安全继续",
            "steps": [{"state": item.get("id"), "meaning": item.get("meaning"), "action": item.get("action"), "persistence": item.get("persistence")} for item in states if item.get("id") not in {"loading", "initial-empty", "success"}],
            "completionSignal": "用户恢复任务或安全退出，且数据、权限和结果边界清晰。",
            "recovery": "无可恢复路径时提供安全返回和支持信息。",
            "metrics": ["recoveryRate", "dataLossCount", "duplicateSubmissionCount"],
        },
    ]


def _state_matrix(plan: Mapping[str, Any]) -> dict[str, Any]:
    model = plan.get("experienceModel") or {}
    interaction = plan.get("interactionContract") or {}
    rows: list[dict[str, Any]] = []
    incomplete: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in _items(interaction.get("stateCoverage")):
        if not isinstance(item, Mapping):
            incomplete.append({"id": "unknown", "missing": ["state object"]})
            continue
        state_id = str(item.get("id") or "unknown")
        required = ("meaning", "presentation", "action", "a11y", "persistence")
        missing = [key for key in required if not item.get(key)]
        if state_id in seen:
            missing.append("unique id")
        seen.add(state_id)
        if missing:
            incomplete.append({"id": state_id, "missing": missing})
        rows.append({
            "id": state_id,
            "reason": item.get("meaning"),
            "presentation": item.get("presentation"),
            "recoveryAction": item.get("action"),
            "contextPersistence": item.get("persistence"),
            "accessibility": item.get("a11y"),
            "completionEvidence": ["状态可被识别", "下一步可执行", "有效上下文被保留"],
        })
    missing_states = sorted(expected_state_ids(model) - seen)
    if missing_states:
        incomplete.append({"id": "__required_states__", "missing": missing_states})
    return {"covered": rows, "incomplete": incomplete, "gateStatus": "PASS" if rows and not incomplete else "FAIL"}


def _capability_centers(plan: Mapping[str, Any]) -> list[dict[str, Any]]:
    model = plan.get("experienceModel") or {}
    skeleton = plan.get("selectedSkeleton") or {}
    repairs = _items((plan.get("uxRepairPlan") or {}).get("findings"))
    layout_debt = any(isinstance(item, Mapping) and item.get("category") in {"layout", "responsive", "layering"} for item in repairs)
    grounded = _grounded_task(model)
    responsive = _responsive_composition(skeleton)
    centers = (
        ("ui-experience-engine", "UI Experience Engine", "PLAN_READY" if grounded else "DISCOVERY_REQUIRED", "任务层级、页面节奏、审美克制和主操作", "人工评审 + 关键旅程"),
        ("layout-intelligence", "Layout Intelligence", "REPAIR_REQUIRED" if layout_debt else "PLAN_READY" if responsive else "DISCOVERY_REQUIRED", "Grid/Flex/容器响应、溢出、遮挡与中间宽度", "三档视口几何证据"),
        ("design-dna", "Design DNA", "CANDIDATE_READY", "项目语言优先的字体、间距、色彩、密度、动效和状态", "Token 映射 + 人工偏好"),
        ("component-intelligence", "Component Intelligence", "MAPPING_REQUIRED", "项目组件优先、行为契约、许可证、依赖与体积", "真实项目组件映射 + 编译"),
        ("visual-studio", "Visual Studio", "CANDIDATE_ONLY", "可序列化 IR、属性、层级、响应预览和 Undo/Redo", "真实浏览器编辑/恢复测试"),
        ("screenshot-intelligence", "Screenshot Intelligence", "OPTIONAL_INPUT", "截图到布局/组件/Token/Design IR 的有界理解", "输入存在时分级证明"),
        ("ux-intelligence", "UX Intelligence", "PLAN_READY" if grounded else "DISCOVERY_REQUIRED", "首次、高频、恢复旅程与用户体感优先级", "任务时间、步骤、错误和恢复率"),
        ("project-experience-library", "Project Experience Library", "CATALOG_AVAILABLE", "可组合页面骨架、组件、状态和交互资产", "代表场景功能预览"),
    )
    return [{
        "id": item[0], "name": item[1], "status": item[2], "owns": item[3], "completionEvidence": item[4],
        "failureIsolation": "该中心失败时返回独立状态并保留主链已有产物；不得伪造成功或自动扩大写入范围。",
    } for item in centers]


def _journeys_complete(journeys: Sequence[Mapping[str, Any]]) -> bool:
    expected = {"first-time", "repeat-use", "recovery"}
    by_type = {str(item.get("type")): item for item in journeys if isinstance(item, Mapping)}
    if set(by_type) != expected:
        return False
    for journey_type in expected:
        item = by_type[journey_type]
        if not _nonempty_text(item.get("userIntent")):
            return False
        steps = _items(item.get("steps"))
        if not steps or not _items(item.get("metrics")):
            return False
        if journey_type == "first-time" and not all(
            isinstance(step, Mapping)
            and all(_nonempty_text(step.get(key)) for key in ("intent", "trigger", "feedback", "completion"))
            for step in steps
        ):
            return False
        if journey_type == "repeat-use" and not all(
            isinstance(step, Mapping) and _nonempty_text(step.get("restore")) for step in steps
        ):
            return False
        if journey_type == "recovery" and not all(
            isinstance(step, Mapping)
            and all(_nonempty_text(step.get(key)) for key in ("state", "meaning", "action", "persistence"))
            for step in steps
        ):
            return False
    return True


def _readiness(
    plan: Mapping[str, Any],
    state_matrix: Mapping[str, Any],
    journeys: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    model = plan.get("experienceModel") or {}
    pattern = plan.get("selectedPattern") or {}
    skeleton = plan.get("selectedSkeleton") or {}
    interaction = plan.get("interactionContract") or {}
    responsive = _responsive_composition(skeleton)
    gates = {
        "primaryTaskGrounded": _grounded_task(model),
        "patternSelected": bool(pattern.get("id")),
        "responsiveComposition": responsive,
        "stateRecoveryComplete": state_matrix.get("gateStatus") == "PASS",
        "criticalJourneysComplete": _journeys_complete(journeys),
        "keyboardAndFocusContract": bool(interaction.get("keyboard")),
    }
    blockers = [name for name, passed in gates.items() if not passed]
    return {
        "status": "PLAN_READY" if not blockers else "DISCOVERY_REQUIRED",
        "hardGates": gates,
        "blockers": blockers,
        "implementationAuthorization": False,
        "meaning": "PLAN_READY 只表示方案可进入受控实施，不代表 Browser、人工或真实用户体验已经验证。",
    }


def build_modernization_strategy(plan: Mapping[str, Any]) -> dict[str, Any]:
    """Build a deterministic, user-value-led strategy from an Experience Core plan."""
    if not isinstance(plan, Mapping):
        raise ValueError("experience plan must be a JSON object")
    if plan.get("schemaVersion") != "3.0":
        raise ValueError("experience plan schemaVersion must be 3.0")
    for key in ("experienceModel", "selectedPattern", "selectedSkeleton", "interactionContract", "uxRepairPlan"):
        if key in plan and plan[key] is not None and not isinstance(plan[key], Mapping):
            raise ValueError(f"experience plan field {key} must be an object")
    state_matrix = _state_matrix(plan)
    journeys = _journeys(plan)
    payload: dict[str, Any] = {
        "schemaVersion": "3.0",
        "positioning": "Enterprise Web UI Experience Modernization Platform",
        "northStar": "让用户更快理解、更少出错、在任何设备和失败状态下都能安全完成主任务。",
        "decisionRule": "用户每天可感知的问题优先，其次是开发效率和维护成本；基础设施保持稳定但不主导产品叙事。",
        "capabilityCenters": _capability_centers(plan),
        "priorityBacklog": _repair_priorities(plan),
        "criticalJourneys": journeys,
        "stateMatrix": state_matrix,
        "investmentPortfolio": {
            "uiUx": 35, "componentEcosystem": 20, "screenshotFigmaDesignIr": 15,
            "visualStudio": 15, "browserExperienceVerification": 10, "infrastructure": 5,
        },
        "verificationLadder": [
            {"level": "static", "status": "AVAILABLE", "proves": "结构、Token、合同和源代码风险", "cannotProve": "真实几何、交互和用户结果"},
            {"level": "browser", "status": "REQUIRED", "proves": "同环境几何、焦点、交互、响应式和视觉回归", "cannotProve": "用户偏好和业务结果"},
            {"level": "expert-review", "status": "REQUIRED", "proves": "层级、审美、状态、内容和任务合理性", "cannotProve": "真实用户群体结果"},
            {"level": "field-user", "status": "REQUIRED_FOR_OUTCOME_CLAIM", "proves": "任务时间、错误率、恢复率、满意度和真实性能", "cannotProve": "未覆盖人群和未来版本"},
        ],
        "deferredInfrastructure": [
            {"name": "Hash / Receipt / Schema", "policy": "maintain-only", "reason": "保留可信、安全和兼容基础，不再作为用户体验核心卖点。"},
        ],
        "readiness": _readiness(plan, state_matrix, journeys),
        "protectedBoundaries": [
            "不自动安装第三方包", "不自动写入目标项目", "不改变业务规则、权限、接口或数据语义",
            "截图、Figma、候选和序列化证据不授予写入或正式通过权威",
        ],
    }
    payload["strategyDigest"] = digest_json(payload)
    return payload


__all__ = ["build_modernization_strategy", "expected_state_ids"]
