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
from .intent_signals import extract_scoped_write_scope, has_whole_task_read_only, normalize_signal_text, strip_negated_write_clauses
from .intent_router import route_user_intent

_WRITE_REQUEST = re.compile(
    r"修复|修好|修一下|修掉|改一下|改好|直接改|帮我改|帮我处理|处理(?:好|一下|这个|当前|该)|帮我改善|改善(?:一下|这个|当前|该)|优化(?:一下|这个|当前|该)|"
    r"修改|调整|改成|换成|更新|修正|\b(?:implement|fix|repair|change|edit|update|adjust)\b|"
    r"\b(?:improve|handle)\b|apply\s+the\s+changes|make\s+the\s+changes",
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
    raw = normalize_signal_text(text)
    routed = route_user_intent(raw)
    control = parse_control_intent(raw)
    internal_intent = str(routed.get("taskIntent") or "DIAGNOSE")
    # The compatibility router intentionally prioritizes read-only language;
    # independently inspect the raw request so a contradictory sentence is
    # not silently downgraded to EXPLAIN before this adapter sees it.
    positive_write_text = strip_negated_write_clauses(raw)
    write_requested = bool(
        routed.get("writeRequested")
        or control.get("action") == "FIX"
        or (internal_intent != "VERIFY_ONLY" and _WRITE_REQUEST.search(positive_write_text))
    )
    read_only_requested = has_whole_task_read_only(raw)
    conflict = write_requested and read_only_requested
    public_intent = _public_intent(internal_intent)
    scoped_write = extract_scoped_write_scope(raw)

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
        "scopeIntent": (
            "WRITE_ALLOWED_WITH_SCOPE" if scoped_write and write_requested and not read_only_requested
            else "WRITE_ALLOWED" if write_requested and not read_only_requested
            else "READ_ONLY" if (read_only_requested or routed.get("readOnlyRequired"))
            else "UNSPECIFIED"
        ),
        "allowedWriteScope": scoped_write,
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
                "scopeIntent": "INTENT_CONFLICT",
                "safeFallback": True,
                "conflictReason": "A write request and an explicit whole-task read-only prohibition were both detected.",
            }
        )
    return result


__all__ = ["normalize_task_intent"]
