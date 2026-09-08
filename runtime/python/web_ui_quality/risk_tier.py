"""Deterministic mutation-risk tiers for consolidated Web repair workflows.

Risk tiers are advisory policy inputs, never write authority.  They tell the
Host how much confirmation and verification is required before a source change
can be called safe.  The Trust Kernel remains the final authority for scope,
receipts, drift and verification.
"""
from __future__ import annotations

from pathlib import PurePosixPath
import re
from typing import Any, Iterable

_TIER_ORDER = {"T0": 0, "T1": 1, "T2": 2, "T3": 3, "T4": 4}

_CRITICAL_TERMS = re.compile(
    r"(?:auth|login|logout|permission|role|rbac|payment|checkout|billing|refund|"
    r"delete|remove|destroy|publish|invite|token|session|cookie|权限|登录|支付|"
    r"付款|退款|删除|角色|鉴权|认证|发布|邀请)", re.I,
)
_STATEFUL_TERMS = re.compile(
    r"(?:api|route|router|state|store|query|mutation|submit|save|persist|fetch|"
    r"接口|路由|状态|保存|提交|数据|请求)", re.I,
)
_INTERACTION_TERMS = re.compile(
    r"(?:click|hover|focus|modal|dialog|drawer|tab|accordion|menu|toggle|form|"
    r"点击|弹窗|抽屉|标签切换|菜单交互|表单提交|交互)", re.I,
)
_COSMETIC_TERMS = re.compile(
    r"(?:css|style|spacing|padding|margin|color|font|radius|shadow|alignment|"
    r"错位|间距|颜色|字号|圆角|阴影|对齐|样式)", re.I,
)

_CRITICAL_PATH_PARTS = {
    "auth", "authentication", "authorization", "permissions", "permission",
    "rbac", "billing", "payment", "payments", "checkout", "security",
}
_STATEFUL_PATH_PARTS = {
    "api", "routes", "router", "store", "stores", "state", "services",
    "mutations", "actions", "server", "backend",
}
_CONFIG_NAMES = {
    "package.json", "package-lock.json", "pnpm-lock.yaml", "yarn.lock",
    "vite.config.js", "vite.config.ts", "next.config.js", "next.config.mjs",
    "webpack.config.js", "webpack.config.ts", "tsconfig.json",
}
_STYLE_SUFFIXES = {".css", ".scss", ".sass", ".less", ".styl"}
_COMPONENT_SUFFIXES = {".html", ".jsx", ".tsx", ".vue", ".svelte"}


def _max_tier(left: str, right: str) -> str:
    return left if _TIER_ORDER[left] >= _TIER_ORDER[right] else right


def classify_risk_tier(
    request: str | None,
    *,
    source_scope: Iterable[str] = (),
    systemic: bool = False,
) -> dict[str, Any]:
    """Classify the narrowest defensible risk tier from request and source scope."""
    text = str(request or "")
    # Protected/non-goal clauses such as "不要动登录逻辑" must not raise the
    # mutation tier merely because they name a sensitive area.  Scope paths can
    # still raise the tier if such a file actually enters the patch candidate.
    mutation_text = re.sub(
        r"(?:不要|别|不许|禁止|do\s+not|don't)\s*(?:修改|改|动|碰|touch|change|modify)?[^，。,.；;\n]{0,48}",
        "", text, flags=re.I,
    )
    files = sorted({str(item).replace("\\", "/").lstrip("./") for item in source_scope if str(item).strip()})
    tier = "T0" if files and all(PurePosixPath(path).suffix.casefold() in _STYLE_SUFFIXES for path in files) else "T1"
    reasons: list[str] = []

    if not files and not _COSMETIC_TERMS.search(mutation_text):
        tier = "T1"
        reasons.append("source scope is not yet confirmed")
    if _INTERACTION_TERMS.search(mutation_text):
        tier = _max_tier(tier, "T2")
        reasons.append("request may affect interaction behavior")
    if _STATEFUL_TERMS.search(mutation_text):
        tier = _max_tier(tier, "T3")
        reasons.append("request mentions route/state/data behavior")
    if _CRITICAL_TERMS.search(mutation_text):
        tier = "T4"
        reasons.append("request touches a protected security or data-mutation domain")

    for path in files:
        pure = PurePosixPath(path)
        parts = {part.casefold() for part in pure.parts}
        name = pure.name.casefold()
        suffix = pure.suffix.casefold()
        if parts & _CRITICAL_PATH_PARTS:
            tier = "T4"
            reasons.append(f"protected path in scope: {path}")
        elif parts & _STATEFUL_PATH_PARTS or name in _CONFIG_NAMES:
            tier = _max_tier(tier, "T3")
            reasons.append(f"state/config path in scope: {path}")
        elif suffix in {".js", ".ts"}:
            tier = _max_tier(tier, "T2")
        elif suffix in _COMPONENT_SUFFIXES:
            tier = _max_tier(tier, "T1")

    if systemic:
        tier = _max_tier(tier, "T3")
        reasons.append("systemic repair scope spans a shared root cause")

    policy = {
        "T0": ("COSMETIC", False, "MINIMAL"),
        "T1": ("LAYOUT_COMPONENT", False, "STANDARD"),
        "T2": ("INTERACTION_LOCAL_STATE", False, "STANDARD"),
        "T3": ("ROUTING_STATE_CONFIG", True, "FULL"),
        "T4": ("AUTH_PAYMENT_PERMISSION_DATA", True, "FULL"),
    }[tier]
    label, explicit, verification = policy
    return {
        "schemaVersion": "1",
        "tier": tier,
        "label": label,
        "requiresExplicitUserApproval": explicit,
        "hostWriteStillRequired": True,
        "minimumVerificationProfile": verification,
        "sourceScope": files,
        "reasons": list(dict.fromkeys(reasons)) or ["bounded UI-only scope"],
        "claimBoundary": "Risk tier selects policy strictness; it never grants source-write authority or proves a change safe.",
    }


__all__ = ["classify_risk_tier"]
