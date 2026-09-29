"""Contract for human or vision-model qualitative UI review.

Pixel changes and rendered checks cannot decide whether a design is better.
This contract records an explicit reviewer judgement with per-dimension reasons
and keeps unreviewed evidence separate from accepted visual quality.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from .contracts import ContractViolation

DIMENSIONS = ("task", "hierarchy", "composition", "rhythm", "visual", "interaction", "responsive", "projectFit")
STATUSES = {"NOT_REVIEWED", "APPROVED", "CHANGES_REQUESTED", "REJECTED"}


def review_template() -> dict[str, Any]:
    return {
        "schemaVersion": "1", "reviewerType": "human-or-vision-provider", "status": "NOT_REVIEWED",
        "dimensions": {name: {"score": None, "reason": ""} for name in DIMENSIONS},
        "hardRedLines": [], "strengths": [], "changesRequired": [], "evidenceRefs": [],
    }


def normalize_visual_review(value: Mapping[str, Any] | None) -> dict[str, Any]:
    if value is None:
        return review_template()
    status = str(value.get("status", "NOT_REVIEWED")).upper()
    if status not in STATUSES:
        raise ContractViolation("VISUAL_REVIEW_INVALID", ["$.status: unsupported"])
    raw_dims = value.get("dimensions", {})
    if not isinstance(raw_dims, Mapping):
        raise ContractViolation("VISUAL_REVIEW_INVALID", ["$.dimensions: expected object"])
    dims: dict[str, Any] = {}
    for name in DIMENSIONS:
        raw = raw_dims.get(name, {})
        if not isinstance(raw, Mapping):
            raw = {}
        score = raw.get("score")
        if score is not None:
            score = int(score)
            if not 0 <= score <= 100:
                raise ContractViolation("VISUAL_REVIEW_INVALID", [f"$.dimensions.{name}.score: 0..100"])
        dims[name] = {"score": score, "reason": str(raw.get("reason", "")).strip()}
        if status != "NOT_REVIEWED" and (score is None or not dims[name]["reason"]):
            raise ContractViolation("VISUAL_REVIEW_INVALID", [f"$.dimensions.{name}: reviewed status requires score and reason"])
    def strings(key: str) -> list[str]:
        raw = value.get(key, [])
        return [str(x).strip() for x in raw if str(x).strip()] if isinstance(raw, list) else []
    result = {
        "schemaVersion": "1", "reviewerType": str(value.get("reviewerType", "human-or-vision-provider")),
        "status": status, "dimensions": dims, "hardRedLines": strings("hardRedLines"),
        "strengths": strings("strengths"), "changesRequired": strings("changesRequired"),
        "evidenceRefs": strings("evidenceRefs"),
    }
    scores = [item["score"] for item in dims.values() if item["score"] is not None]
    result["overallScore"] = round(sum(scores) / len(scores)) if scores else None
    if result["hardRedLines"] and status == "APPROVED":
        raise ContractViolation("VISUAL_REVIEW_INVALID", ["$: hard red lines cannot coexist with APPROVED"])
    if result["changesRequired"] and status == "APPROVED":
        raise ContractViolation("VISUAL_REVIEW_INVALID", ["$: unresolved changes cannot coexist with APPROVED"])
    if status != "NOT_REVIEWED" and not result["evidenceRefs"]:
        raise ContractViolation("VISUAL_REVIEW_INVALID", ["$.evidenceRefs: reviewed status requires inspected evidence"])
    return result


def build_visual_review_work(records: Sequence[Mapping[str, Any]], issues: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Give the Host actionable visual work, not a synthetic aesthetic score.

    Reuses the existing human/vision review contract. The runtime measures;
    the Host inspects the screenshots, resolves the candidates, edits only
    authorized source, and records its actual judgement after verification.
    """
    screenshots = [
        {"viewport": dict(record.get("viewport") or {}),
         "viewportRef": record.get("screenshotRef"),
         "fullPageRef": record.get("fullPageScreenshotRef"),
         "pageStatus": (record.get("pageHealth") or {}).get("pageStatus", "NOT_VERIFIED")}
        for record in records if record.get("screenshotRef") or record.get("fullPageScreenshotRef")
    ]
    candidates = [
        {"ruleId": issue.get("id"), "title": issue.get("title"),
         "viewports": list(issue.get("viewports") or []),
         "samples": list(issue.get("samples") or []),
         "repairDirection": issue.get("recommendation"),
         "claimBoundary": issue.get("claimBoundary"),
         "disposition": "NOT_REVIEWED"}
        for issue in issues if issue.get("evidenceClass") == "DIAGNOSTIC_CANDIDATE"
    ]
    return {
        "review": review_template(),
        "screenshots": screenshots,
        "candidates": candidates,
        "checks": [
            {"dimension": "composition", "question": "首屏主任务是否清楚；同组标题、数字、按钮是否对齐；窄屏是否重组而非机械缩小？", "repairDirection": "定位共享布局容器、网格轨道和断点；先调整信息结构，再处理局部间距。"},
            {"dimension": "rhythm", "question": "卡片是否贴连或大而空；组内与组间距离能否清楚表达关系；是否机械长列？", "repairDirection": "在共享容器统一间距与密度；按页面任务选择卡片或紧凑列表，避免逐项补丁和阴影堆叠。"},
            {"dimension": "visual", "question": "图标的可见图形是否大小协调、视觉居中、风格一致；不是仅看盒子居中？", "repairDirection": "区分点击区、装饰底板、SVG viewBox 或位图透明留白；保留足够点击区，修复图形比例或资源裁切。"},
            {"dimension": "visual", "question": "主色、背景、文字与警告/成功色是否分工明确；是否所有元素同时抢眼或层级全靠淡色边线？", "repairDirection": "检查项目已有颜色令牌和语义角色，收敛竞争强调色；对比度合格不能代替整体配色判断。"},
            {"dimension": "projectFit", "question": "图片是否符合产品与内容；清晰度、裁切和风格是否一致；是否仍是简陋占位资产？", "repairDirection": "优先复用合适真实资产。需要照片、插画或有质感的位图时，由 Host 调用可用内置生图工具、落盘并接入页面；不要用临时 SVG/Canvas 冒充。保留合适的矢量图标、品牌标志和原生图表。"},
            {"dimension": "interaction", "question": "主操作、空态、错误和恢复路径是否完整，且视觉修改没有破坏任务？", "repairDirection": "在授权范围实际操作，并验证目标结果；toast、可点击与测试通过都不能证明整个页面已经成熟。"},
        ],
        "workflow": [
            "查看各视口截图及必要全页图；无截图或页面不具代表性时不作视觉通过结论。",
            "逐项判定候选：确认并修复，或结合具体截图说明无需修复；不得仅因 P2 或不妨碍点击而豁免。",
            "从样本的 styleSelector/container 定位共享组件或资源所有者；在授权源码内修复，并检查复用页面。",
            "同条件重新打开修改后页面与关键交互；填写已有视觉评审，分别报告具体问题与页面完成度。",
        ],
        "assetGeneration": {"executor": "Host", "preferredTool": "available built-in image generation", "executed": False, "fallback": "能力不可用时明确保留待处理项；不冒充已经生成或静默切换付费 API。"},
        "claimBoundary": "自动测量用于发现与定位；本清单不是已完成的视觉评审，也不证明图片已经生成。",
    }


def review_prompt(report: Mapping[str, Any]) -> str:
    browser = report.get("browserComparisonReport", {})
    plan = report.get("productizationPlan", {})
    return "\n".join([
        "Review the before/after UI as a product designer. Do not infer unobserved business facts.",
        f"Recommended direction: {plan.get('recommendation', 'unknown')}",
        f"Before: {browser.get('beforeRef', 'NOT_VERIFIED')}",
        f"After: {browser.get('afterRef', 'NOT_VERIFIED')}",
        "Score task, hierarchy, composition, rhythm, visual consistency, interaction credibility, responsive behavior, and project fit from 0-100.",
        "For every dimension provide a short evidence-based reason. List hard red lines separately.",
        "Inspect icon ink and optical centering, color roles/harmony, grouping/spacing, short-label wrapping and asset quality, not just geometry or contrast.",
        "Do not approve while required changes remain. Cite screenshots you actually inspected; technical PASS and functioning clicks are not aesthetic acceptance.",
        "Return JSON matching the visual-review template.",
    ])
