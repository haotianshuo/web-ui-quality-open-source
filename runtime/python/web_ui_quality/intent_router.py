"""User-intent routing for the consolidated product surface.

The router deliberately separates *what the user wants* from the internal
execution mode.  Existing compatibility intents (inspect/fix/redesign/
specialized-audit) remain stable while ``taskIntent`` captures the finer
public intent used by the UX layer.  Routing never grants write authority.
"""
from __future__ import annotations

import re
from typing import Any

from .intent_signals import strip_negated_write_clauses


_RULES: tuple[dict[str, Any], ...] = (
    {
        "taskIntent": "VERIFY_ONLY",
        "compatIntent": "inspect",
        "patterns": (
            r"检查(?:刚才|之前|已经).{0,24}(?:改|修改|修复)",
            r"验证(?:刚才|之前|已经).{0,24}(?:改|修改|修复)",
            r"有没有(?:回归|问题)", r"verify(?:\s+only)?", r"regression\s+check",
        ),
        "rationale": "用户要求验证已有修改，而不是发起新的写入。",
        "writeRequested": False,
    },
    {
        "taskIntent": "EXPLAIN",
        "compatIntent": "inspect",
        "patterns": (
            r"别改代码", r"不要改代码", r"不要修改(?:任何)?(?:代码|项目|文件|东西)", r"只告诉我", r"只分析", r"只解释",
            r"read[- ]?only", r"do not (?:edit|change|modify)", r"don't (?:edit|change|modify)",
        ),
        "rationale": "用户明确要求只读解释或诊断。",
        "writeRequested": False,
    },
    {
        "taskIntent": "TRANSFORM",
        "compatIntent": "redesign",
        "patterns": (
            r"重新设计", r"彻底改版", r"重做", r"现代化版本", r"产品升级",
            r"多个设计方向", r"几个设计方向", r"设计方案", r"redesign",
            r"re[- ]?design", r"moderni[sz]e", r"rebuild the (?:product|system)",
        ),
        "rationale": "用户明确要求产品级重设计或多方向探索。",
        "writeRequested": False,
    },
    {
        "taskIntent": "REPAIR_SMALL",
        "compatIntent": "fix",
        "patterns": (
            r"修复", r"修好", r"修一下", r"修掉", r"改一下", r"改好", r"直接改", r"帮我改", r"优化一下",
            r"优化这个页面", r"按照刚才", r"把这些问题", r"帮我处理", r"处理好", r"处理一下", r"帮我改善", r"改善一下", r"改善",
            r"修改", r"调整", r"改成", r"换成", r"更新", r"修正",
            r"implement", r"\bfix\b", r"repair", r"apply the changes", r"make the changes",
            r"\b(?:change|edit|update|adjust|improve|handle)\b",
        ),
        "rationale": "用户要求对已知问题实施受控修复。",
        "writeRequested": True,
    },
    {
        "taskIntent": "SPECIALIZED_AUDIT",
        "compatIntent": "specialized-audit",
        "patterns": (
            r"无障碍", r"accessibility", r"a11y", r"性能", r"performance",
            r"(?:安全|security).{0,16}(?:审计|专项检查|合规检查|audit|review|assessment)",
            r"(?:检查|check|review).{0,24}(?:安全问题|security|安全性)", r"安全审计", r"security\s+audit",
            r"lighthouse", r"完整商业验收", r"全量验收",
            r"专项", r"合规", r"审计", r"responsive", r"响应式", r"断点",
            r"ui\s*asset", r"ui\s*inventory", r"资产盘点", r"按钮统计",
            r"风格统计", r"样式统计", r"全站\s*ui",
        ),
        "rationale": "用户指定了专项领域，但没有请求实施修改。",
        "writeRequested": False,
    },
    {
        "taskIntent": "DIAGNOSE",
        "compatIntent": "inspect",
        "patterns": (
            r"看看", r"检查", r"验收", r"哪里有问题", r"评估", r"审查",
            r"review", r"inspect", r"check", r"evaluate", r"what(?:'s| is) wrong",
        ),
        "rationale": "用户要求只读检查或体验评估。",
        "writeRequested": False,
    },
)


def _has_positive_write_signal(text: str) -> bool:
    """Ignore a scoped non-goal such as ``不要修改登录逻辑`` when routing."""
    candidate = strip_negated_write_clauses(text)
    patterns = _RULES[3]["patterns"]
    return any(re.search(pattern, candidate, flags=re.IGNORECASE) for pattern in patterns)


def _specialty(text: str, task_intent: str) -> str | None:
    # Specialty is an orthogonal label.  A repair request may be RESPONSIVE,
    # ACCESSIBILITY, PERFORMANCE, SECURITY, or UI_INVENTORY without becoming a
    # read-only specialized audit.  Protected/non-goal clauses are removed
    # before classification so “不要动登录逻辑” cannot relabel an unrelated UI
    # repair as SECURITY.
    specialty_text = re.sub(
        r"(?:不要|别|不许|禁止|do\s+not|don't)\s*(?:修改|改|动|碰|touch|change|modify)?[^，。,.；;\n]{0,48}",
        "", text, flags=re.I,
    )
    groups = (
        ("ACCESSIBILITY", (r"无障碍", r"accessibility", r"a11y")),
        ("PERFORMANCE", (r"性能", r"performance", r"lighthouse")),
        ("SECURITY", (r"安全", r"security", r"auth", r"login", r"permission", r"rbac", r"登录", r"权限", r"角色")),
        ("RESPONSIVE", (r"responsive", r"响应式", r"断点")),
        ("UI_INVENTORY", (r"ui\s*asset", r"ui\s*inventory", r"资产盘点", r"按钮统计", r"风格统计", r"样式统计", r"全站\s*ui")),
    )
    for name, patterns in groups:
        if any(re.search(pattern, specialty_text, flags=re.I) for pattern in patterns):
            return name
    return "GENERAL" if task_intent == "SPECIALIZED_AUDIT" else None


def route_user_intent(text: str | None, *, default: str = "inspect") -> dict[str, Any]:
    """Return the best public task intent without granting write authority."""
    source = str(text or "").strip()
    lowered = source.casefold()
    matches: list[dict[str, Any]] = []
    for rule in _RULES:
        if rule["taskIntent"] == "REPAIR_SMALL" and not _has_positive_write_signal(lowered):
            continue
        hit = [pattern for pattern in rule["patterns"] if re.search(pattern, lowered, flags=re.IGNORECASE)]
        if hit:
            matches.append({**rule, "hits": hit})
    if matches:
        selected = matches[0]
    else:
        compat = default if default in {"inspect", "fix", "redesign", "specialized-audit"} else "inspect"
        selected = {
            "taskIntent": "DIAGNOSE",
            "compatIntent": compat,
            "hits": [],
            "rationale": "没有发现重设计、写入或专项信号，按只读检查处理。",
            "writeRequested": False,
        }
    confidence = "high" if len(selected["hits"]) >= 2 else "medium" if selected["hits"] else "low"
    specialty = _specialty(lowered, str(selected["taskIntent"]))
    return {
        # ``intent`` is kept for existing 4.0 callers.
        "intent": selected["compatIntent"],
        "taskIntent": selected["taskIntent"],
        "specialty": specialty,
        "confidence": confidence,
        "rationale": selected["rationale"],
        "matchedSignals": selected["hits"],
        "writeRequested": bool(selected["writeRequested"]),
        "writeAuthorized": False,
        "productDiscoveryRequired": selected["taskIntent"] == "TRANSFORM",
        "specializedAuditRequired": selected["taskIntent"] == "SPECIALIZED_AUDIT",
        "readOnlyRequired": selected["taskIntent"] in {"DIAGNOSE", "VERIFY_ONLY", "EXPLAIN", "SPECIALIZED_AUDIT"},
        "claimBoundary": "Intent routing selects workflow only; it never carries user approval or Host write authority.",
    }


__all__ = ["route_user_intent"]
