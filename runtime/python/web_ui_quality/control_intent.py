"""Conservative natural-language control layer.

The parser maps user language to constrained intent. It never grants project
write authority; FIX remains a request that must pass Host Write Boundary.
"""
from __future__ import annotations

import re
from typing import Any

from .intent_signals import (
    extract_scoped_protected_scope,
    extract_scoped_write_scope,
    has_whole_task_read_only,
    strip_negated_write_clauses,
)


def parse_control_intent(text: str | None) -> dict[str, Any]:
    raw = str(text or "").strip()
    low = raw.casefold()
    base = {
        "schemaVersion": "1", "raw": raw, "action": "UNKNOWN", "mutation": "FORBIDDEN",
        "scope": None, "profile": None, "reportDepth": None, "resumeTarget": None, "resumeQuery": None,
        "assumptionRevision": False, "protectedScope": [], "confidence": "LOW",
        "scopeIntent": "UNSPECIFIED", "allowedWriteScope": [],
        "requiresHostApproval": False, "safeFallback": True,
    }
    if not raw:
        return base

    read_only_requested = has_whole_task_read_only(low)
    # Only direct optimization language counts as a mutation request. Phrases
    # such as “告诉我应该怎么优化” remain read-only because the optimization
    # verb is not used as an imperative action.
    verification_requested = bool(re.search(
        r"(验证(?:刚才|之前|已经)?|有没有(?:回归|问题)|verify|regression\s+check)",
        low,
    ))
    positive_write_text = strip_negated_write_clauses(raw)
    fix_requested = not verification_requested and bool(re.search(
        r"(直接修|修一下|修复|修掉|帮我修|帮我优化|优化(?:一下|这个|当前|该)|帮我处理|处理(?:好|一下|这个|当前|该)|帮我改善|改善(?:一下|这个|当前|该)|修改|调整|改成|换成|更新|修正|\bfix\b|repair|\b(?:change|edit|update|adjust|improve|handle)\b)",
        positive_write_text.casefold(),
    ))
    scoped_write = extract_scoped_write_scope(raw)
    if read_only_requested:
        return {**base, "action": "CHECK", "mutation": "FORBIDDEN", "scopeIntent": "READ_ONLY", "confidence": "HIGH", "safeFallback": False}
    if re.search(r"(先停一下|暂停|pause|checkpoint)", low):
        return {**base, "action": "CHECKPOINT", "mutation": "FORBIDDEN", "confidence": "HIGH", "safeFallback": False}
    if re.search(r"(继续上次任务|继续上一次|resume latest|continue last)", low):
        return {**base, "action": "RESUME", "resumeTarget": "LATEST_COMPATIBLE", "confidence": "HIGH", "safeFallback": False}
    match = re.search(r"回到(.+?)之前", raw)
    if match:
        return {**base, "action": "RESUME", "resumeTarget": "LOOKUP_BY_DESCRIPTION", "resumeQuery": match.group(1).strip(), "confidence": "MEDIUM", "safeFallback": False}
    if re.search(r"(rollback to|go back to)", low):
        return {**base, "action": "RESUME", "resumeTarget": "LOOKUP_BY_DESCRIPTION", "confidence": "MEDIUM", "safeFallback": False}
    if re.search(r"(刚才那个假设错了|假设.*错|assumption.*wrong|revise assumption)", low):
        return {**base, "action": "REVISE_ASSUMPTION", "assumptionRevision": True, "confidence": "HIGH", "safeFallback": False}

    result = dict(base)
    matched = False
    if re.search(r"(全面检查|完整检查|full audit|check everything)", low):
        result.update({"action": "CHECK", "profile": "full", "confidence": "HIGH", "safeFallback": False}); matched = True
    if re.search(r"(只看这个页面|只看当前页|current page only|this page only)", low):
        result.update({"scope": "CURRENT", "confidence": "HIGH", "safeFallback": False}); matched = True
    if re.search(r"(修.*最严重.*三|最严重的?三个|top\s*3|three most severe)", low):
        result.update({"action": "FIX", "mutation": "HOST_GATED", "scope": "TOP_3", "requiresHostApproval": True, "confidence": "HIGH", "safeFallback": False}); matched = True
    elif fix_requested:
        result.update({
            "action": "FIX", "mutation": "HOST_GATED", "requiresHostApproval": True,
            "scopeIntent": "WRITE_ALLOWED_WITH_SCOPE" if scoped_write else "WRITE_ALLOWED",
            "allowedWriteScope": scoped_write, "confidence": "MEDIUM", "safeFallback": False,
        }); matched = True
    if re.search(r"(简单点|简洁|concise|brief)", low):
        result["reportDepth"] = "concise"; matched = True
    if re.search(r"(详细一点|详细点|detailed|in detail)", low):
        result["reportDepth"] = "detailed"; matched = True
    protected = re.findall(r"(?:不要动|不要碰|不要改|不要修改|别动|别碰|别改|别修改|do\s+not\s+touch|don't\s+touch)([^，。,.!！;；]+)", raw, flags=re.IGNORECASE)
    if protected:
        result["protectedScope"] = [x.strip() for x in protected if x.strip()]
        result["safeFallback"] = False
        matched = True
    for value in extract_scoped_protected_scope(raw):
        if value not in result["protectedScope"]:
            result["protectedScope"].append(value)
        result["safeFallback"] = False
        matched = True
    if matched:
        if result["action"] == "UNKNOWN":
            result["action"] = "CHECK"
        return result
    return {**base, "action": "NEEDS_EXPLICIT_SCOPE" if any(x in low for x in ("改", "修", "change", "fix")) else "UNKNOWN"}
