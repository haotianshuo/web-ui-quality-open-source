"""File-based review history suitable for Git and pull requests.

The review file is not authorization to modify source. It is a collaboration
record with an append-only hash chain so edited history is detectable.
"""
from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path
from typing import Any, Mapping

from .contracts import ContractViolation, digest_json

_ALLOWED = {"NOT_REVIEWED", "APPROVED", "CHANGES_REQUESTED", "REJECTED"}


def initialize_review(report_digest: str) -> dict[str, Any]:
    if not isinstance(report_digest, str) or len(report_digest) != 64:
        raise ContractViolation("REVIEW_DIGEST_INVALID", ["$.reportDigest: expected SHA-256 hex digest"])
    return {"schemaVersion": "1", "reportDigest": report_digest, "decision": "NOT_REVIEWED", "history": [], "historyDigest": digest_json([])}


def append_review(state: Mapping[str, Any], *, reviewer: str, decision: str, comment: str, timestamp: str | None = None) -> dict[str, Any]:
    decision = str(decision).upper()
    if decision not in _ALLOWED:
        raise ContractViolation("REVIEW_DECISION_INVALID", ["$.decision: unsupported decision"])
    reviewer = str(reviewer).strip(); comment = str(comment).strip()
    if not reviewer:
        raise ContractViolation("REVIEWER_REQUIRED", ["$.reviewer: required"])
    if decision != "NOT_REVIEWED" and not comment:
        raise ContractViolation("REVIEW_COMMENT_REQUIRED", ["$.comment: explain the decision"])
    history = [dict(item) for item in state.get("history", []) if isinstance(item, Mapping)]
    expected = digest_json(history)
    if state.get("historyDigest") not in {None, expected}:
        raise ContractViolation("REVIEW_HISTORY_TAMPERED", ["$.historyDigest: history does not match"])
    at = timestamp or _dt.datetime.now(_dt.timezone.utc).isoformat()
    entry = {"reviewer": reviewer, "decision": decision, "comment": comment, "at": at, "previousHistoryDigest": expected}
    entry["entryDigest"] = digest_json(entry)
    history.append(entry)
    return {"schemaVersion": "1", "reportDigest": state.get("reportDigest"), "decision": decision, "history": history, "historyDigest": digest_json(history)}


def record_review(path: str | Path, *, report_digest: str | None, reviewer: str, decision: str, comment: str) -> dict[str, Any]:
    target = Path(path)
    if target.is_file():
        state = json.loads(target.read_text(encoding="utf-8"))
    else:
        if report_digest is None:
            raise ContractViolation("REVIEW_DIGEST_REQUIRED", ["$: report digest required for a new review file"])
        state = initialize_review(report_digest)
    updated = append_review(state, reviewer=reviewer, decision=decision, comment=comment)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(updated, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return updated
