"""Evidence-aware user-journey analysis for product experience consultations.

The module turns UI findings into a small, business-readable journey.  It does
not claim measured outcome improvements: scores are diagnostic heuristics and
missing evidence is represented explicitly.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


JOURNEY_MODELS: dict[str, dict[str, Any]] = {
    "crm": {
        "roles": ["销售人员", "销售经理"],
        "goal": "找到正确客户并推进下一步",
        "stages": [
            ("discover", "发现客户", "快速定位值得处理的客户"),
            ("evaluate", "判断机会", "理解价值、状态与风险"),
            ("follow-up", "跟进沟通", "记录进展并获得明确反馈"),
            ("advance", "推进成交", "安全完成关键业务动作"),
        ],
    },
    "saas": {
        "roles": ["业务用户", "管理员"],
        "goal": "以较低学习成本完成核心任务",
        "stages": [
            ("orient", "理解当前状态", "知道自己在哪里以及下一步是什么"),
            ("find", "找到功能", "快速定位主要入口和相关对象"),
            ("complete", "完成任务", "在连续上下文中完成操作"),
            ("confirm", "确认结果", "获得清晰反馈并能恢复异常"),
        ],
    },
    "landing": {
        "roles": ["访客", "潜在客户"],
        "goal": "理解价值、建立信任并采取行动",
        "stages": [
            ("understand", "理解价值", "快速判断产品是否适合自己"),
            ("trust", "建立信任", "获得可信证据并消除主要顾虑"),
            ("compare", "比较方案", "理解差异、成本和适用场景"),
            ("act", "开始行动", "顺畅进入注册、咨询或购买"),
        ],
    },
    "commerce": {
        "roles": ["消费者", "复购用户"],
        "goal": "找到合适商品并放心完成购买",
        "stages": [
            ("discover", "发现商品", "通过分类、推荐或搜索缩小范围"),
            ("evaluate", "评估商品", "理解价格、规格、库存与信任信息"),
            ("decide", "形成决策", "比较选择并确认适配性"),
            ("checkout", "完成购买", "低摩擦且可恢复地完成结算"),
        ],
    },
    "ai-product": {
        "roles": ["知识工作者", "AI 功能使用者"],
        "goal": "清楚表达意图并获得可控、可信的结果",
        "stages": [
            ("frame", "表达意图", "理解能力边界并提供必要输入"),
            ("generate", "等待生成", "看见进度、可取消并理解系统状态"),
            ("review", "审阅结果", "判断来源、质量与可用性"),
            ("refine", "调整与交付", "低成本迭代并安全应用结果"),
        ],
    },
    "mobile": {
        "roles": ["移动用户", "现场工作人员"],
        "goal": "在有限屏幕和不稳定环境中完成主要任务",
        "stages": [
            ("arrive", "进入任务", "快速回到需要处理的对象"),
            ("capture", "查看或录入", "用单手完成关键信息处理"),
            ("validate", "确认信息", "在提交前发现遗漏与错误"),
            ("sync", "提交与同步", "在弱网和冲突下保持可恢复"),
        ],
    },
}

_PRODUCT_ALIASES = {
    "crm-saas": "crm", "crm": "crm", "sales": "crm",
    "landing": "landing", "marketing": "landing", "website": "landing",
    "commerce": "commerce", "ecommerce": "commerce", "shop": "commerce",
    "ai": "ai-product", "ai-product": "ai-product", "assistant": "ai-product",
    "mobile": "mobile", "field": "mobile", "user-flow": "saas",
    "web-experience": "saas", "screenshot": "saas", "dashboard": "saas",
}

_STAGE_KEYWORDS = {
    "discover": ("搜索", "查找", "入口", "导航", "筛选", "find", "search", "navigation"),
    "orient": ("层级", "当前", "状态", "标题", "定位", "hierarchy", "orientation"),
    "find": ("入口", "导航", "菜单", "搜索", "find", "search", "discover"),
    "understand": ("价值", "文案", "理解", "标题", "value", "copy", "message"),
    "trust": ("信任", "证据", "评价", "安全", "trust", "proof"),
    "compare": ("对比", "方案", "价格", "compare", "pricing"),
    "evaluate": ("详情", "信息", "字段", "比较", "detail", "information"),
    "decide": ("选择", "规格", "库存", "decision", "option"),
    "frame": ("输入", "提示", "意图", "prompt", "input"),
    "generate": ("加载", "等待", "进度", "取消", "loading", "progress"),
    "review": ("结果", "来源", "准确", "review", "result", "source"),
    "capture": ("表单", "输入", "触控", "键盘", "form", "input", "touch"),
    "validate": ("校验", "错误", "必填", "validation", "error"),
    "complete": ("操作", "流程", "表单", "按钮", "action", "workflow", "form"),
    "follow-up": ("跟进", "记录", "消息", "note", "follow"),
    "advance": ("提交", "确认", "审批", "submit", "approve"),
    "act": ("注册", "购买", "咨询", "行动", "signup", "buy", "cta"),
    "checkout": ("支付", "地址", "订单", "checkout", "payment", "order"),
    "confirm": ("反馈", "成功", "失败", "恢复", "feedback", "success", "recovery"),
    "refine": ("编辑", "重试", "应用", "edit", "retry", "apply"),
    "sync": ("离线", "同步", "冲突", "重试", "offline", "sync", "conflict"),
    "arrive": ("首页", "返回", "恢复", "home", "resume"),
}


def infer_product_type(*, product_type: str | None = None, intent: str | None = None, page_type: str | None = None) -> str:
    """Resolve a supported journey family without inventing a narrow industry."""
    # Explicit product context wins.  When it is absent, source-grounded page
    # classification must win over the consultant's broad default intent
    # (``web-experience`` maps to SaaS and previously swallowed landing pages).
    for raw in (product_type, page_type, intent):
        value = str(raw or "").strip().casefold()
        if not value:
            continue
        if value in JOURNEY_MODELS:
            return value
        if value in _PRODUCT_ALIASES:
            return _PRODUCT_ALIASES[value]
        for alias, target in _PRODUCT_ALIASES.items():
            if alias in value:
                return target
    return "saas"


def _finding_text(finding: Mapping[str, Any]) -> str:
    parts = [finding.get(key) for key in ("title", "whyItMatters", "suggestion", "description", "problem")]
    return " ".join(str(value) for value in parts if value).casefold()


def _finding_id(finding: Mapping[str, Any], index: int) -> str:
    return str(finding.get("id") or finding.get("findingId") or f"problem-{index + 1}")


def _severity(finding: Mapping[str, Any]) -> str:
    impact = finding.get("impact") if isinstance(finding.get("impact"), Mapping) else {}
    value = str(impact.get("level") or finding.get("severity") or "MEDIUM").upper()
    return value if value in {"P0", "P1", "P2", "P3", "HIGH", "MEDIUM", "LOW"} else "MEDIUM"


def _best_stage(text: str, stage_ids: Sequence[str]) -> str:
    ranked = []
    for index, stage_id in enumerate(stage_ids):
        hits = sum(1 for keyword in _STAGE_KEYWORDS.get(stage_id, ()) if keyword in text)
        ranked.append((hits, -index, stage_id))
    hits, _, stage_id = max(ranked)
    return stage_id if hits else stage_ids[0]


def analyze_user_journey(
    product_type: str,
    findings: Sequence[Mapping[str, Any]],
    *,
    role: str | None = None,
    goal: str | None = None,
) -> dict[str, Any]:
    """Link observed problems to a four-stage user journey."""
    resolved = infer_product_type(product_type=product_type)
    model = JOURNEY_MODELS[resolved]
    clean_findings = [item for item in findings if isinstance(item, Mapping)][:12]
    assignments: dict[str, list[Mapping[str, Any]]] = {stage[0]: [] for stage in model["stages"]}
    stage_ids = list(assignments)
    for finding in clean_findings:
        assignments[_best_stage(_finding_text(finding), stage_ids)].append(finding)

    stages = []
    for stage_id, label, stage_goal in model["stages"]:
        linked = assignments[stage_id]
        stages.append({
            "id": stage_id,
            "label": label,
            "goal": stage_goal,
            "frictions": [str(item.get("title") or item.get("problem") or "待确认的体验问题") for item in linked],
            "linkedFindingIds": [_finding_id(item, clean_findings.index(item)) for item in linked],
            "opportunity": str(linked[0].get("suggestion")) if linked and linked[0].get("suggestion") else "保留现有业务含义，减少该阶段的理解、操作或恢复成本",
            "status": "FRICTION_FOUND" if linked else "NO_DIRECT_FINDING",
        })

    weighted = {"P0": 5, "P1": 4, "HIGH": 4, "P2": 2, "MEDIUM": 2, "P3": 1, "LOW": 1}
    critical = max(
        stages,
        key=lambda stage: sum(weighted[_severity(item)] for item in assignments[stage["id"]]),
    )
    coverage = round(sum(bool(stage["linkedFindingIds"]) for stage in stages) / len(stages), 2)
    confidence = "high" if len(clean_findings) >= 3 and coverage >= .5 else "medium" if clean_findings else "low"
    return {
        "schemaVersion": "3.6",
        "productType": resolved,
        "persona": [role] if role else list(model["roles"]),
        "primaryGoal": goal or model["goal"],
        "journey": [stage["label"] for stage in stages],
        "stages": stages,
        "frictionPoints": [
            {
                "id": _finding_id(item, index),
                "friction": str(item.get("title") or item.get("problem") or "体验问题"),
                "severity": _severity(item),
                "businessRisk": str(item.get("whyItMatters") or "可能增加任务完成、理解或恢复成本"),
            }
            for index, item in enumerate(clean_findings[:3])
        ],
        "linkedFindings": [dict(item) for item in clean_findings],
        "criticalStageId": critical["id"],
        "recommendedFocus": f"优先改善“{critical['label']}”阶段，并验证它是否降低真实用户完成核心任务的阻力",
        "evidence": {
            "findingCount": len(clean_findings),
            "stageCoverage": coverage,
            "confidence": confidence,
            "claimBoundary": "Journey links are diagnostic inferences, not measured user behavior.",
        },
    }


def build_experience_score_report(journey: Mapping[str, Any], score: int | None = None) -> dict[str, Any]:
    """Build an explainable diagnostic score or request a real baseline."""
    findings = [item for item in journey.get("linkedFindings", []) if isinstance(item, Mapping)]
    if score is None and not findings:
        return {
            "experienceScore": None,
            "status": "BASELINE_REQUIRED",
            "summary": "现有证据不足，暂不生成会造成误解的体验分数。",
            "topIssues": [],
            "nextAction": "先完成一次基线任务观察或页面审计",
            "method": {"type": "diagnostic-heuristic", "measuredOutcome": False},
            "journey": dict(journey),
        }
    if score is None:
        penalty = {"P0": 18, "P1": 12, "HIGH": 12, "P2": 7, "MEDIUM": 7, "P3": 3, "LOW": 3}
        raw = 100 - sum(penalty[_severity(item)] for item in findings[:6])
        score = max(20, min(96, raw))
    score = max(0, min(100, int(score)))
    top = [str(item.get("title") or item.get("problem") or "体验问题") for item in findings[:3]]
    return {
        "experienceScore": score,
        "status": "DIAGNOSTIC_ONLY",
        "summary": "该分数用于整理当前诊断优先级，不代表转化率、效率或用户满意度。",
        "topIssues": top,
        "nextAction": "查看推荐方案，并建立可测量的真实基线",
        "method": {
            "type": "diagnostic-heuristic",
            "measuredOutcome": False,
            "formula": "100 minus severity-weighted observed findings",
            "findingCount": len(findings),
        },
        "journey": dict(journey),
    }
