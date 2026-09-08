"""Canonical public task-intent normalization.

The package keeps the historical intent and control routers for compatibility.
This adapter is the small boundary used by a plain user-facing entry point: it
normalizes their outputs, detects contradictory write/read-only requests, and
never grants write authority.
"""
from __future__ import annotations

import re
from typing import Any

from .control_intent import parse_control_intent
from .intent_router import route_user_intent


_FULL_READ_ONLY = re.compile(
    r"(?:不要|别|不许|禁止)\s*(?:修改|改|动|碰)?\s*(?:任何)?\s*(?:代码|项目|文件|东西)"
    r"|(?:do\s+not|don't)\s+(?:edit|change|modify)\s+(?:any\s+)?(?:code|files?|project|anything)"
    r"|read[- ]?only",
    re.IGNORECASE,
)
_WRITE_REQUEST = re.compile(
    r"修复|修好|修一下|修掉|改一下|改好|直接改|帮我改|优化(?:一下|这个|当前|该)|"
    r"\b(?:implement|fix|repair)\b|apply\s+the\s+changes|make\s+the\s+changes",
    re.IGNORECASE,
)


def _public_intent(internal: str) -> str:
    return {
        "DIAGNOSE": "CHECK",
        "SPECIALIZED_AUDIT": "CHECK",
        "VERIFY_ONLY": "VERIFY_ONLY",
        "EXPLAIN": "EXPLAIN",
        "REPAIR_SMALL": "REPAIR",
        "TRANSFORM": "REPAIR",
    }.get(str(internal).upper(), "CHECK")


def normalize_task_intent(text: str | None) -> dict[str, Any]:
    """Return a canonical, fail-closed task intent for ordinary UX surfaces."""
    raw = str(text or "").strip()
    routed = route_user_intent(raw)
    control = parse_control_intent(raw)
    # The compatibility router intentionally prioritizes read-only language;
    # independently inspect the raw request so a contradictory sentence is
    # not silently downgraded to EXPLAIN before this adapter sees it.
    write_requested = bool(
        routed.get("writeRequested")
        or control.get("action") == "FIX"
        or _WRITE_REQUEST.search(raw)
    )
    read_only_requested = bool(_FULL_READ_ONLY.search(raw))
    conflict = write_requested and read_only_requested
    internal_intent = str(routed.get("taskIntent") or "DIAGNOSE")
    public_intent = _public_intent(internal_intent)

    result: dict[str, Any] = {
        "schemaVersion": "1",
        "raw": raw,
        "taskIntent": public_intent,
        "internalTaskIntent": internal_intent,
        "intent": routed.get("intent", "inspect"),
        "specialty": routed.get("specialty"),
        "confidence": routed.get("confidence", "low"),
        "rationale": routed.get("rationale"),
        "matchedSignals": list(routed.get("matchedSignals") or []),
        "writeRequested": write_requested,
        "readOnlyRequired": bool(routed.get("readOnlyRequired") or read_only_requested),
        "writeAuthorized": False,
        "mutation": str(control.get("mutation") or "FORBIDDEN"),
        "protectedScope": list(control.get("protectedScope") or []),
        "requiresHostApproval": bool(control.get("requiresHostApproval")),
        "conflictStatus": "INTENT_CONFLICT" if conflict else "NONE",
        "safeFallback": bool(control.get("safeFallback", True)),
        "claimBoundary": "Normalization selects a workflow only; it never grants Host write authority.",
    }
    if conflict:
        result.update(
            {
                "taskIntent": "REPAIR",
                "readOnlyRequired": True,
                "mutation": "FORBIDDEN",
                "writeAuthorized": False,
                "requiresHostApproval": False,
                "safeFallback": True,
                "conflictReason": "A write request and an explicit whole-task read-only prohibition were both detected.",
            }
        )
    return result


__all__ = ["normalize_task_intent"]
