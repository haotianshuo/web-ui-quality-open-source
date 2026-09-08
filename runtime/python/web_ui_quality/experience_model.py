"""Business experience modelling for UI modernisation.

This module deliberately separates explicit evidence from derived heuristics.  It
turns business context and observed page facts into a compact experience model
that downstream pattern, visual, interaction, and evaluation engines can use.
Missing evidence lowers confidence instead of being silently invented.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence


_ALLOWED_FREQUENCY = {"continuous", "daily", "weekly", "monthly", "rare", "unknown"}
_ALLOWED_EXPERTISE = {"novice", "mixed", "expert", "unknown"}
_ALLOWED_ENVIRONMENT = {"desktop-office", "mobile-field", "mixed", "public-kiosk", "unknown"}
_ALLOWED_TASK = {"find-compare", "review-confirm", "create-edit", "monitor-respond", "configure", "communicate", "unknown"}
_ALLOWED_RISK = {"low", "medium", "high", "regulated", "unknown"}
_ALLOWED_DENSITY = {"low", "medium", "high", "unknown"}
_ALLOWED_DEVICE = {"desktop", "mobile", "balanced", "unknown"}


def _text(value: Any) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def _list(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple, set)):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _contains(text: str, values: Sequence[str]) -> bool:
    lower = text.casefold()
    return any(value.casefold() in lower for value in values)


def _normalise_frequency(value: str | None) -> str:
    text = (value or "").casefold()
    if _contains(text, ("实时", "持续", "continuous", "always")): return "continuous"
    if _contains(text, ("每天", "每日", "高频", "daily", "frequent")): return "daily"
    if _contains(text, ("每周", "weekly")): return "weekly"
    if _contains(text, ("每月", "monthly")): return "monthly"
    if _contains(text, ("低频", "偶尔", "rare", "occasional")): return "rare"
    return value if value in _ALLOWED_FREQUENCY else "unknown"


def _normalise_expertise(value: str | None) -> str:
    text = (value or "").casefold()
    if _contains(text, ("新手", "普通用户", "文化程度", "不熟悉", "novice", "beginner")): return "novice"
    if _contains(text, ("专业", "专家", "熟练", "expert", "power user")): return "expert"
    if _contains(text, ("混合", "mixed")): return "mixed"
    return value if value in _ALLOWED_EXPERTISE else "unknown"


def _normalise_environment(value: str | None) -> str:
    text = (value or "").casefold()
    if _contains(text, ("混合", "mixed", "办公室和现场", "desktop and mobile")): return "mixed"
    if _contains(text, ("现场", "户外", "单手", "移动", "field", "outdoor")): return "mobile-field"
    if _contains(text, ("办公室", "桌面", "键盘", "desktop", "office")): return "desktop-office"
    if _contains(text, ("公共", "自助机", "kiosk")): return "public-kiosk"
    return value if value in _ALLOWED_ENVIRONMENT else "unknown"


def _normalise_task(value: str | None) -> str:
    text = (value or "").casefold()
    if _contains(text, ("查找", "搜索", "比较", "核对", "find", "compare", "scan")): return "find-compare"
    if _contains(text, ("审核", "确认", "审批", "review", "approve", "confirm")): return "review-confirm"
    if _contains(text, ("新建", "填写", "编辑", "create", "edit", "compose")): return "create-edit"
    if _contains(text, ("监控", "异常", "响应", "monitor", "respond", "alert")): return "monitor-respond"
    if _contains(text, ("设置", "配置", "configure", "setting")): return "configure"
    if _contains(text, ("消息", "沟通", "对话", "communicate", "chat")): return "communicate"
    return value if value in _ALLOWED_TASK else "unknown"


def _normalise_risk(value: str | None, actions: Sequence[str]) -> str:
    text = " ".join([value or "", *actions]).casefold()
    # Keep explicit canonical values intact while still allowing the business
    # context to raise the risk when it names a dangerous operation.  The old
    # fallback treated ``high``/``高`` as arbitrary text and silently downgraded
    # it to ``low``, which removed permission/conflict recovery states downstream.
    if _contains(text, ("监管", "合规", "regulated", "medical", "financial")): return "regulated"
    if _contains(text, ("删除", "发布", "支付", "审批", "授权", "高风险", "高", "delete", "publish", "payment", "approve", "high")): return "high"
    if _contains(text, ("提交", "保存", "修改", "中风险", "中", "medium", "submit", "save")): return "medium"
    if _contains(text, ("低风险", "低", "low")): return "low"
    if text.strip(): return "low"
    return value if value in _ALLOWED_RISK else "unknown"


def _normalise_density(value: str | None, observed: Mapping[str, Any]) -> str:
    text = (value or "").casefold()
    if _contains(text, ("高密度", "大量数据", "dense", "high")): return "high"
    if _contains(text, ("简洁", "低密度", "simple", "low")): return "low"
    rows = int(observed.get("rows") or 0); columns = int(observed.get("columns") or 0); controls = int(observed.get("controls") or 0)
    if rows >= 12 or columns >= 7 or controls >= 16: return "high"
    if rows or columns or controls: return "medium"
    return value if value in _ALLOWED_DENSITY else "unknown"


def _normalise_device(value: str | None, environment: str, mobile_evidence: bool) -> str:
    text = (value or "").casefold()
    if _contains(text, ("移动优先", "mobile first", "mobile")): return "mobile"
    if _contains(text, ("桌面优先", "desktop")): return "desktop"
    if environment == "mobile-field": return "mobile"
    if environment == "desktop-office": return "desktop"
    if mobile_evidence: return "balanced"
    return value if value in _ALLOWED_DEVICE else "unknown"


@dataclass(frozen=True, slots=True)
class ExperienceModel:
    primary_role: str | None
    primary_task: str | None
    success_metric: str | None
    frequency: str
    user_expertise: str
    environment: str
    task_type: str
    risk: str
    information_density: str
    device_priority: str
    accessibility_priority: str
    brand_personality: str
    collaboration_mode: str
    entities: tuple[str, ...]
    operations: tuple[str, ...]
    states: tuple[str, ...]
    pain_points: tuple[str, ...]
    high_risk_actions: tuple[str, ...]
    must_preserve: tuple[str, ...]
    evidence_sources: tuple[str, ...]
    confidence: str
    unresolved_questions: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        raw = asdict(self)
        mapping = {
            "primary_role": "primaryRole", "primary_task": "primaryTask", "success_metric": "successMetric",
            "user_expertise": "userExpertise", "task_type": "taskType", "information_density": "informationDensity",
            "device_priority": "devicePriority", "accessibility_priority": "accessibilityPriority",
            "brand_personality": "brandPersonality", "collaboration_mode": "collaborationMode",
            "pain_points": "painPoints", "high_risk_actions": "highRiskActions", "must_preserve": "mustPreserve",
            "evidence_sources": "evidenceSources", "unresolved_questions": "unresolvedQuestions",
        }
        return {mapping.get(key, key): list(value) if isinstance(value, tuple) else value for key, value in raw.items()}


def build_experience_model(
    business_context: Mapping[str, Any] | None,
    business_model: Mapping[str, Sequence[str]],
    observed_profile: Mapping[str, Any],
    *,
    page_modes: Sequence[str] = (),
) -> ExperienceModel:
    context = business_context or {}
    entities = tuple(dict.fromkeys([*_list(context.get("entities")), *[str(x) for x in business_model.get("entities", []) if str(x).strip()]]))
    operations = tuple(dict.fromkeys([*_list(context.get("operations")), *[str(x) for x in business_model.get("operations", []) if str(x).strip()]]))
    states = tuple(dict.fromkeys([*_list(context.get("states")), *[str(x) for x in business_model.get("states", []) if str(x).strip()]]))
    pain = tuple(_list(context.get("knownPainPoints")) or _list(context.get("painPoints")))
    risk_actions = tuple(_list(context.get("highRiskActions")))
    preserve = tuple(dict.fromkeys([*_list(context.get("mustPreserve")), *[str(x) for x in business_model.get("constraints", []) if str(x).strip()]]))

    primary_role = _text(context.get("primaryRole")) or (str(next(iter(business_model.get("roles", [])), "")).strip() or None)
    primary_task = _text(context.get("primaryTask"))
    success_metric = _text(context.get("successMetric"))
    frequency = _normalise_frequency(_text(context.get("frequency")))
    expertise = _normalise_expertise(_text(context.get("userExpertise")) or _text(context.get("expertise")))
    environment = _normalise_environment(_text(context.get("environment")))
    task_type = _normalise_task(_text(context.get("taskType")) or primary_task or " ".join(operations))
    risk = _normalise_risk(_text(context.get("risk")), risk_actions)
    density = _normalise_density(_text(context.get("informationDensity")), observed_profile)
    device = _normalise_device(_text(context.get("devicePriority")), environment, bool(observed_profile.get("mobileEvidence")))
    accessibility_priority = _text(context.get("accessibilityPriority")) or ("high" if environment in {"public-kiosk", "mobile-field"} or expertise == "novice" else "standard")
    brand_personality = _text(context.get("brandPersonality")) or "professional-neutral"
    collaboration_mode = _text(context.get("collaborationMode")) or "individual-review"

    evidence: list[str] = []
    if context: evidence.append("explicit-business-context")
    if any(business_model.get(key) for key in ("entities", "roles", "operations", "states")): evidence.append("static-page-language")
    if any(int(observed_profile.get(key) or 0) for key in ("tables", "rows", "columns", "forms", "controls", "metrics")): evidence.append("observed-page-structure")
    if page_modes: evidence.append("classified-page-mode")

    unresolved: list[str] = []
    if not primary_role: unresolved.append("主要用户角色未确认")
    if not primary_task: unresolved.append("首要任务未确认")
    if not success_metric: unresolved.append("成功指标未确认")
    if frequency == "unknown": unresolved.append("使用频率未确认")
    if expertise == "unknown": unresolved.append("用户熟练度未确认")
    if environment == "unknown": unresolved.append("使用环境未确认")
    if device == "unknown": unresolved.append("设备优先级未确认")

    explicit_dimensions = sum(1 for value in (primary_role, primary_task, success_metric) if value) + sum(
        1 for value in (frequency, expertise, environment, task_type, risk, density, device) if value != "unknown"
    )
    confidence = "high" if explicit_dimensions >= 8 and len(evidence) >= 3 else "medium" if explicit_dimensions >= 5 else "low"

    return ExperienceModel(
        primary_role=primary_role, primary_task=primary_task, success_metric=success_metric,
        frequency=frequency, user_expertise=expertise, environment=environment, task_type=task_type,
        risk=risk, information_density=density, device_priority=device,
        accessibility_priority=accessibility_priority, brand_personality=brand_personality,
        collaboration_mode=collaboration_mode, entities=entities, operations=operations, states=states,
        pain_points=pain, high_risk_actions=risk_actions, must_preserve=preserve,
        evidence_sources=tuple(evidence), confidence=confidence, unresolved_questions=tuple(unresolved),
    )
