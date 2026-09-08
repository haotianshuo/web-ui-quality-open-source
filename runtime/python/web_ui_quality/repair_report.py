"""One user-facing repair report over many internal governance artifacts."""
from __future__ import annotations

from typing import Any, Mapping, Sequence


def build_repair_report(
    *,
    request: str,
    status: str,
    reproduced: str,
    root_cause: str,
    changes: Sequence[str],
    verification: Sequence[str],
    risks: Sequence[str],
    unverified: Sequence[str],
    resumable: bool,
    run_id: str,
    authentication: str | None = None,
    verification_summary: Mapping[str, Any] | None = None,
    next_action: str | None = None,
) -> dict[str, Any]:
    """Return the default human-facing answer, not the internal artifact graph."""
    summary = {
        "overall": status,
        "browser": "NOT_MEASURED",
        "projectTools": "NOT_APPLICABLE",
        "patchQuality": "NOT_APPLICABLE",
        "projectDrift": "NOT_APPLICABLE",
        "hostWrite": "NOT_APPLICABLE",
    }
    if verification_summary:
        summary.update({str(k): v for k, v in verification_summary.items() if k in summary})
    if next_action is None:
        next_action = (
            "可以选择“继续上次任务”、重试当前验证或缩小范围后再试。"
            if resumable else "查看剩余风险后决定下一步；必要时重新提交最小范围。"
        )
    return {
        "schemaVersion": "1",
        "status": status,
        "request": request,
        "answers": {
            "whatYouAsked": request,
            "whatWasReproduced": reproduced,
            "rootCause": root_cause,
            "whatChanged": list(changes),
            "howVerified": list(verification),
            "remainingRiskOrUnknown": list(risks) + list(unverified),
        },
        "verificationSummary": summary,
        "nextAction": next_action,
        "authentication": authentication or "anonymous",
        "taskState": {
            "runId": run_id,
            "resumable": bool(resumable),
            "resumeHint": "继续上次任务" if resumable else None,
        },
        "claimBoundary": "The report summarizes sealed evidence and explicit verification results; omitted or unavailable evidence remains unverified.",
    }


__all__ = ["build_repair_report"]
