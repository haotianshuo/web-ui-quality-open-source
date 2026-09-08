"""Human-facing consultation compiled from the bounded 3.1 diagnosis.

This module is a presentation adapter.  It accepts no raw Browser payload and
cannot promote evidence authority or grant project-write approval.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .contracts import digest_json


SUPPORTED_INTENTS: tuple[dict[str, str], ...] = (
    {
        "id": "web-experience",
        "label": "优化网页体验",
        "description": "找出页面最影响理解和操作的地方，并给出改造方向。",
    },
    {
        "id": "crm-saas",
        "label": "优化 CRM / SaaS 系统",
        "description": "改善高频列表、详情、筛选和业务状态流程。",
    },
    {
        "id": "screenshot",
        "label": "分析截图",
        "description": "从页面截图理解视觉层级并提出有边界的候选建议。",
    },
    {
        "id": "mobile",
        "label": "改善移动端体验",
        "description": "检查触控、窄屏重组、草稿和同步反馈。",
    },
    {
        "id": "user-flow",
        "label": "检查用户流程",
        "description": "检查关键任务是否清楚、连续并且可以恢复。",
    },
)


_PAGE_LABELS = {
    "crm": "CRM 客户管理",
    "erp": "ERP 业务系统",
    "saas-dashboard": "运营 Dashboard",
    "landing-page": "产品官网",
    "mobile-workflow": "移动业务流程",
    "unclassified": "当前页面",
}

_INTENT_BY_PAGE = {
    "crm": "crm-saas",
    "erp": "crm-saas",
    "saas-dashboard": "web-experience",
    "landing-page": "web-experience",
    "mobile-workflow": "mobile",
}

_PROBLEM_COPY = {
    "task-clarity": {
        "title": "主要任务和下一步不够清楚",
        "why": "用户需要在多个同等级入口之间判断，容易打断当前任务。",
        "suggestion": "围绕主任务重新组织入口，只突出一个下一步，并保留必要上下文。",
    },
    "responsive": {
        "title": "页面在不同屏幕上不够顺手",
        "why": "桌面结构被直接压缩后，平板和手机上的阅读与操作成本会上升。",
        "suggestion": "分别为桌面、平板和手机重组信息，而不是等比缩小页面。",
    },
    "interaction": {
        "title": "操作反馈和恢复路径不够清楚",
        "why": "用户完成、取消或遇到失败后，可能不知道结果是否保存以及如何继续。",
        "suggestion": "明确展示处理中、成功、失败、返回和恢复状态，并保留已输入内容。",
    },
    "visual": {
        "title": "重要信息没有被优先看见",
        "why": "标题、按钮和信息块的视觉权重接近，用户需要额外扫描才能找到重点。",
        "suggestion": "保留一个主要视觉焦点，降低次要操作权重，并建立稳定的阅读顺序。",
    },
    "component": {
        "title": "相似操作的界面规则不够一致",
        "why": "同类控件表现不一致会增加学习成本，也让状态反馈变得不可预测。",
        "suggestion": "复用项目已有组件并统一命名、状态、焦点和响应式行为。",
    },
}

_DIRECTION_COPY = {
    "responsive-layout": {
        "name": "跨端顺畅版",
        "summary": "让同一任务在桌面、平板和手机上都保持清楚的下一步。",
        "bestFor": "需要跨设备完成同一业务任务的团队",
        "tradeoff": "需要调整中间宽度和移动端的信息布局",
    },
    "visual-hierarchy": {
        "name": "现代简洁版",
        "summary": "减少视觉竞争，让主要任务和关键信息先被看见。",
        "bestFor": "希望新用户更快理解页面的团队",
        "tradeoff": "会降低部分次要信息在首屏的显著程度",
    },
    "interaction-recovery": {
        "name": "高频效率版",
        "summary": "保持筛选、选择、详情和反馈连续，减少反复返回与重新输入。",
        "bestFor": "每天连续处理大量记录的熟练用户",
        "tradeoff": "需要补齐关键状态和恢复行为",
    },
    "component-system": {
        "name": "稳健统一版",
        "summary": "优先统一现有组件与状态，降低迁移范围和后续维护成本。",
        "bestFor": "需要控制改造风险并逐步上线的团队",
        "tradeoff": "视觉变化更克制，结构升级会分阶段完成",
    },
    "task-clarity": {
        "name": "任务优先版",
        "summary": "围绕一个主要任务重组入口、信息和下一步操作。",
        "bestFor": "希望业务人员无需培训即可上手的团队",
        "tradeoff": "需要把低频操作移到次级入口",
    },
}


_STRATEGIC_LENS = {
    "responsive-layout": {"id": "EFFICIENCY_FIRST", "label": "效率优先", "targetUser": "高频、熟练、跨设备操作人员", "coreProblem": "步骤、切换和等待成本过高", "validation": ["任务完成时间", "步骤数", "跨设备成功率"], "knownRisk": "信息密度可能提高，新用户需要更清晰的层级"},
    "interaction-recovery": {"id": "GUIDANCE_AND_ERROR_PREVENTION", "label": "引导与防错优先", "targetUser": "新用户、低频用户和高风险操作人员", "coreProblem": "状态、下一步和恢复路径不清楚", "validation": ["首次完成率", "错误率", "恢复率"], "knownRisk": "额外引导可能拖慢专家用户"},
    "task-clarity": {"id": "GUIDANCE_AND_ERROR_PREVENTION", "label": "引导与防错优先", "targetUser": "新用户、低频用户和高风险操作人员", "coreProblem": "主要任务和下一步不清楚", "validation": ["首次完成率", "求助次数", "错误率"], "knownRisk": "低频操作会被降到次级入口"},
    "visual-hierarchy": {"id": "DECISION_AND_INSIGHT", "label": "决策与洞察优先", "targetUser": "管理者、分析者和负责人", "coreProblem": "异常、趋势和关键信息不够突出", "validation": ["异常发现时间", "下钻成功率", "判断准确性"], "knownRisk": "摘要缺少证据时可能误导"},
    "component-system": {"id": "EFFICIENCY_FIRST", "label": "效率优先", "targetUser": "持续维护和高频使用产品的团队", "coreProblem": "同类组件规则不一致导致学习和维护成本", "validation": ["重复问题数", "组件复用率", "回归缺陷率"], "knownRisk": "视觉变化较克制，收益需要分阶段体现"},
}

# 面向终端用户的结果描述。不要暴露内部设计模型，让用户理解“改变后会怎样”。
_DIRECTION_OUTCOME = {
    "responsive-layout": {
        "headline": "方案 A：让用户在任何设备上都能快速完成任务",
        "effect": "桌面、平板和手机会重新组织信息，用户更容易找到下一步操作。",
        "benefit": "适合经常跨设备工作的团队。",
    },
    "visual-hierarchy": {
        "headline": "方案 B：让重要内容第一眼被看见",
        "effect": "减少视觉干扰，让新用户更快理解页面价值和主要入口。",
        "benefit": "适合希望提升首次访问体验和转化的产品。",
    },
    "interaction-recovery": {
        "headline": "方案 C：让高频操作更快、更放心",
        "effect": "补充加载、成功、失败和恢复反馈，减少用户反复试错。",
        "benefit": "适合 CRM、后台和业务系统。",
    },
    "component-system": {
        "headline": "方案 D：逐步统一产品体验",
        "effect": "统一按钮、表单和状态表现，让整个产品更容易学习。",
        "benefit": "适合大型产品的渐进式升级。",
    },
    "task-clarity": {
        "headline": "方案 A：围绕用户目标重新组织页面",
        "effect": "减少寻找和判断成本，让用户更快完成核心任务。",
        "benefit": "适合业务流程复杂的产品。",
    },
}


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _text(value: Any) -> str:
    return str(value or "").strip()


def _confidence(value: Any) -> str:
    token = _text(value).casefold()
    return token if token in {"low", "medium", "high"} else "low"


def _page_details(diagnosis: Mapping[str, Any]) -> tuple[str, str, str, str]:
    page = _mapping(diagnosis.get("pageUnderstanding"))
    page_type = _mapping(page.get("pageType"))
    primary_task = _mapping(page.get("primaryTask"))
    page_id = _text(page_type.get("id")) or "unclassified"
    label = _PAGE_LABELS.get(page_id, "当前页面")
    task = _text(primary_task.get("value")) or "完成页面的主要任务"
    confidence = _confidence(page_type.get("confidence") or primary_task.get("confidence"))
    return page_id, label, task, confidence


def _select_intent(
    page_id: str,
    context: Mapping[str, Any],
    explicit: str | None,
) -> tuple[str, str]:
    allowed = {item["id"] for item in SUPPORTED_INTENTS}
    requested = _text(explicit or context.get("consultantIntent"))
    if requested in allowed:
        return requested, "user-selected"
    if context.get("screenshot"):
        return "screenshot", "inferred"
    return _INTENT_BY_PAGE.get(page_id, "web-experience"), "inferred"


def _problem_group(item: Mapping[str, Any]) -> str:
    category = _text(item.get("category")).casefold()
    item_id = _text(item.get("id")).casefold()
    if category in {"layout", "responsive"} or "responsive" in item_id or "layout" in item_id:
        return "responsive"
    if category in {"interaction", "accessibility", "layering"}:
        return "interaction"
    if category in {"hierarchy", "typography", "color", "spacing", "visual", "visual-system"}:
        return "visual"
    if category == "component":
        return "component"
    return "task-clarity"


def _component_is_active(item: Mapping[str, Any], component_types: set[str]) -> bool:
    if _text(item.get("category")).casefold() != "component":
        return True
    item_id = _text(item.get("id")).removeprefix("COMPONENT-").casefold()
    return not item_id or item_id in component_types


def _impact(item: Mapping[str, Any], position: int) -> dict[str, str]:
    priority = _text(item.get("priority")).casefold()
    severity = _text(item.get("severity")).upper()
    if priority == "must-fix" or severity == "UX1":
        return {"level": "HIGH", "label": "影响很大"}
    if priority == "should-fix" or severity == "UX2" or position < 2:
        return {"level": "MEDIUM", "label": "值得优先改善"}
    return {"level": "LOW", "label": "可以进一步优化"}


def _problem_rank(item: Mapping[str, Any], group_position: int) -> tuple[int, int, int]:
    return (
        {"must-fix": 0, "should-fix": 1, "candidate": 2}.get(_text(item.get("priority")).casefold(), 3),
        {"UX1": 0, "UX2": 1, "UX3": 2}.get(_text(item.get("severity")).upper(), 3),
        group_position,
    )


def _compile_problems(diagnosis: Mapping[str, Any]) -> list[dict[str, Any]]:
    page = _mapping(diagnosis.get("pageUnderstanding"))
    component_types = {
        _text(item.get("type")).casefold()
        for item in _rows(page.get("componentInventory"))
        if _text(item.get("type"))
    }
    recommendations = [
        item for item in _rows(diagnosis.get("recommendations"))
        if _component_is_active(item, component_types)
    ]
    grouped: dict[str, dict[str, Any]] = {}
    for item in recommendations:
        group = _problem_group(item)
        if group not in grouped:
            grouped[group] = item
    order = ("task-clarity", "responsive", "interaction", "visual", "component")
    selected = [(group, grouped[group]) for group in order if group in grouped][:3]
    if len(selected) < 3:
        for group, item in grouped.items():
            if group not in {name for name, _ in selected}:
                selected.append((group, item))
            if len(selected) == 3:
                break
    selected.sort(key=lambda row: _problem_rank(row[1], order.index(row[0]) if row[0] in order else 9))
    problems: list[dict[str, Any]] = []
    for index, (group, item) in enumerate(selected):
        copy = _PROBLEM_COPY[group]
        verification = [
            _text(value) for value in item.get("verificationNeeded", [])
            if _text(value)
        ] if isinstance(item.get("verificationNeeded"), list) else []
        problems.append(
            {
                "id": f"CONSULTANT-PROBLEM-{index + 1}",
                "title": copy["title"],
                "whyItMatters": copy["why"],
                "suggestion": copy["suggestion"],
                "impact": _impact(item, index),
                "confidence": _confidence(_mapping(item.get("evidence")).get("confidence")),
                "verificationNeeded": verification,
                "sourceFindingIds": [_text(item.get("id"))] if _text(item.get("id")) else [],
                "whyThisAdvice": {
                    "summary": _text(item.get("userProblem")) or copy["why"],
                    "needsConfirmation": _text(item.get("claim")) != "observed-problem",
                },
            }
        )
    return problems


def _option_group(option: Mapping[str, Any]) -> str:
    title = _text(option.get("title")).casefold()
    if "responsive" in title or "layout" in title:
        return "responsive-layout"
    if "visual" in title or "token" in title:
        return "visual-hierarchy"
    if "recover" in title or "journey" in title or "continuous" in title:
        return "interaction-recovery"
    if "component" in title:
        return "component-system"
    return "task-clarity"


def _compile_directions(
    diagnosis: Mapping[str, Any],
    problems: Sequence[Mapping[str, Any]],
    *, direction_count: int = 2,
) -> list[dict[str, Any]]:
    proof = _mapping(diagnosis.get("experienceProof"))
    compilation = _mapping(proof.get("recommendationCompilation"))
    count = 3 if int(direction_count) == 3 else 2
    source_options = _rows(compilation.get("options"))[:3]
    if not source_options:
        return []
    chosen: list[tuple[str, dict[str, Any]]] = []
    used: set[str] = set()
    for option in source_options:
        group = _option_group(option)
        if group in used:
            continue
        used.add(group)
        chosen.append((group, option))
    fallback_groups = (
        "interaction-recovery",
        "visual-hierarchy",
        "component-system",
        "task-clarity",
        "responsive-layout",
    )
    while len(chosen) < count:
        group = next((item for item in fallback_groups if item not in used), None)
        if group is None:
            break
        used.add(group)
        chosen.append((group, source_options[min(len(chosen), len(source_options) - 1)]))
    directions: list[dict[str, Any]] = []
    for index, (group, option) in enumerate(chosen[:count]):
        copy = _DIRECTION_COPY[group]
        problem_changes = [
            _text(item.get("suggestion")) for item in problems
            if _text(item.get("suggestion"))
        ]
        directions.append(
            {
                "id": f"CONSULTANT-DIRECTION-{index + 1}",
                "name": copy["name"],
                "summary": copy["summary"],
                "bestFor": copy["bestFor"],
                "tradeoff": copy["tradeoff"],
                "strategicLens": _STRATEGIC_LENS[group],
                "targetUser": _STRATEGIC_LENS[group]["targetUser"],
                "coreProblem": _STRATEGIC_LENS[group]["coreProblem"],
                "validationMethod": _STRATEGIC_LENS[group]["validation"],
                "knownRisk": _STRATEGIC_LENS[group]["knownRisk"],
                "userScenario": _DIRECTION_OUTCOME[group]["headline"],
                "expectedExperienceChange": _DIRECTION_OUTCOME[group]["effect"],
                "businessValue": _DIRECTION_OUTCOME[group]["benefit"],
                "recommended": index == 0,
                "whyRecommended": (
                    "它最直接回应当前影响最大的体验问题，并保留后续验证和回退空间。"
                    if index == 0 else "它使用相同诊断依据，但采用不同的实施侧重点。"
                ),
                "actionLabel": "选择这个方向",
                "changes": problem_changes[:3],
                "sourceOptionId": _text(option.get("id")),
                "previewStatus": "CONCEPT_PREVIEW",
                "automaticWriteAuthorized": False,
                "technical": {
                    "codeLocations": _rows(option.get("codeLocations")),
                    "acceptanceGates": list(option.get("acceptanceGates") or []),
                    "migrationRisk": _mapping(option.get("migrationRisk")),
                },
            }
        )
    return directions


def _preview_contract(diagnosis: Mapping[str, Any]) -> dict[str, Any]:
    proof = _mapping(diagnosis.get("experienceProof"))
    visual = _mapping(proof.get("visualProof"))
    status = _text(visual.get("status")) or "PLANNED_NOT_CAPTURED"
    verified = status in {"PASS", "PASS_WITH_TOOL_BOUNDARIES"}
    summary = _mapping(diagnosis.get("evidenceSummary"))
    return {
        "mode": "before-after",
        "status": "BROWSER_VERIFIED" if verified else "CONCEPT_PREVIEW",
        "proofStatus": status,
        "authority": _text(visual.get("authority")) or "CANDIDATE_ONLY",
        "viewports": [1440, 768, 390],
        "states": ["ready", "loading", "empty", "error", "success"],
        "toolBoundaries": _mapping(visual.get("toolBoundaries")),
        "referenceScreenshotRole": "REFERENCE_ONLY" if summary.get("screenshot") else "NONE",
        "beforeLabel": "当前体验" if verified else "当前结构示意",
        "afterLabel": "推荐方案" if verified else "推荐结构示意",
        "claimBoundary": (
            "只有可信 Browser 配对可以证明真实 Before/After；当前截图若存在，仅作为参考输入。"
            if not verified else
            "Browser 证明仅覆盖已记录的页面、状态和视口，不代表真实用户结果。"
        ),
        "userOutcomeMeasured": False,
    }


def _technical_appendix(diagnosis: Mapping[str, Any]) -> dict[str, Any]:
    proof = _mapping(diagnosis.get("experienceProof"))
    model = _mapping(proof.get("experienceModel"))
    references: list[str] = []
    verification: list[str] = []
    for entry in _rows(model.get("evidenceLedger")):
        for fact in _rows(entry.get("observedFacts")):
            ref = _text(fact.get("sourceRef"))
            if ref and ref not in references:
                references.append(ref)
        for item in entry.get("verificationNeeded", []) if isinstance(entry.get("verificationNeeded"), list) else []:
            value = _text(item)
            if value and value not in verification:
                verification.append(value)
    return {
        "hiddenByDefault": True,
        "experienceProofDigest": _text(proof.get("experienceProofDigest")),
        "evidenceRefs": references[:20],
        "verificationNeeded": verification[:20],
        "diagnosisRef": "experience-diagnosis.json",
        "proofRef": "experience-proof.json",
    }


def build_experience_consultation(
    diagnosis: Mapping[str, Any],
    *,
    experience_context: Mapping[str, Any] | None = None,
    audience: str | None = None,
    intent: str | None = None,
    direction_count: int = 2,
) -> dict[str, Any]:
    """Compile one plain-language, safely bounded consultation sidecar."""

    context = _mapping(experience_context)
    page_id, page_label, primary_task, confidence = _page_details(diagnosis)
    selected_intent, selection_mode = _select_intent(page_id, context, intent)
    problems = _compile_problems(diagnosis)
    directions = _compile_directions(diagnosis, problems, direction_count=direction_count)
    ready = (
        _text(diagnosis.get("status")) == "DIAGNOSIS_READY"
        and bool(problems)
        and bool(directions)
    )
    if not ready:
        problems = []
        directions = []
    preview = _preview_contract(diagnosis)
    result: dict[str, Any] = {
        "schemaVersion": "3.2",
        "status": "CONSULTATION_READY" if ready else "DISCOVERY_REQUIRED",
        "audience": _text(audience) or "product-manager",
        "supportedIntents": [dict(item) for item in SUPPORTED_INTENTS],
        "selectedIntent": selected_intent,
        "intentSelection": {
            "mode": selection_mode,
            "rationale": f"当前页面更接近{page_label}场景。",
        },
        "opening": (
            "我看了一下：目前最值得先改善的是这三个地方。"
            if ready else
            "我还不能可靠判断这个页面的主要任务，需要你确认一个业务目标。"
        ),
        "businessSummary": {
            "pageType": page_id,
            "pageTypeLabel": page_label,
            "primaryTask": primary_task,
            "plainLanguage": f"我理解这是一个{page_label}页面，主要用来{primary_task}。",
            "confidence": confidence,
            "verificationNeeded": [] if confidence == "high" else ["请确认页面类型和主要任务是否正确。"],
        },
        "topProblems": problems,
        "directions": directions,
        "selectedDirectionId": directions[0]["id"] if directions else None,
        "preview": preview,
        "guidedFlow": {
            "steps": ["understand", "issues", "directions", "preview", "confirm", "apply", "verify"],
            "currentStep": "directions" if ready else "understand",
            "nextAction": "查看推荐效果" if ready else "确认业务目标",
            "apply": {
                "requiresExplicitApproval": True,
                "automaticWriteAuthorized": False,
                "status": "AWAITING_APPROVAL",
            },
        },
        "implementationHandoff": {
            "status": "PREVIEW_ONLY",
            "automaticWriteAuthorized": False,
            "explicitConfirmationRequired": True,
            "userMessage": "当前只生成实施清单，尚未修改任何源码。",
            "confirmLabel": "生成实施清单",
            "applyLabel": "确认后再应用修改",
        },
        "progressiveDisclosure": {
            "defaultSections": ["business-summary", "top-problems", "directions", "preview", "handoff"],
            "hiddenByDefault": ["technicalEvidence", "schema", "componentMapping", "runtimeGeometry"],
            "technicalLabel": "查看技术证据",
        },
        "technicalAppendix": _technical_appendix(diagnosis),
        "clarificationQuestion": None if ready else "这个页面最希望用户完成的事情是什么？",
        "claims": {
            "userOutcomeMetricsMeasured": False,
            "taskTimeMeasured": False,
            "conversionMeasured": False,
            "preferenceMeasured": False,
        },
        "claimBoundary": (
            "这是把现有诊断翻译成产品语言的咨询结果；它不提升证据权威、"
            "不代表真实用户研究，也不授权安装、写入、发布或部署。"
        ),
    }
    result["consultantDigest"] = digest_json(result)
    return result


build_experience_consultant = build_experience_consultation


__all__ = [
    "SUPPORTED_INTENTS",
    "build_experience_consultant",
    "build_experience_consultation",
]
