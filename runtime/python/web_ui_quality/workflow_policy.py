"""Small, versioned policy kernel for the current user-controlled workflow.

The skill explains the workflow in plain language.  This module keeps the
state, evidence labels, confirmation boundary, and model capability fallback
deterministic so a more capable model cannot silently widen the work.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
import hashlib
import json
import os
import re
from typing import Any, Callable, Mapping


EVIDENCE_CLASSES = (
    "SOURCE_CONFIRMED",
    "PAGE_OBSERVED",
    "AI_INFERRED",
    "USER_CONFIRMED",
    "PACKAGE_VERIFIED",
    "RUNTIME_OBSERVED",
    "UNKNOWN",
    "CONFLICTED",
    "NOT_VERIFIED",
    "SYNTHETIC_HYPOTHESIS",
)

WORKFLOW_STATES = (
    "DISCOVERY",
    "AWAITING_USER_CONFIRMATION",
    "DIAGNOSIS",
    "AWAITING_IMPLEMENTATION_APPROVAL",
    "IMPLEMENTATION",
    "VERIFICATION",
)

MODE_NAMES = ("diagnose", "full")
DEFAULT_MODE = "diagnose"

# These actions only move the understanding card forward.  They must never
# open diagnosis, design, Browser validation, or implementation in the same
# call—even when the final deferred answer happens to resolve every question.
# Keeping this list in the policy kernel avoids a mode-specific caller
# accidentally turning a round acknowledgement into a full-upgrade approval.
ANSWER_ROUND_ACTIONS = frozenset({"continue-round", "edit-one"})
DIAGNOSIS_ONLY_ACTIONS = frozenset({"continue-diagnosis"})

_GENERATED_CONFIRMATION_SOURCES = {
    "web-ui-quality-system-understanding",
    "system-understanding-response",
    "explicit-cli-option",
    "agent",
    "model",
    "ai",
}

_WORKFLOW_AUTHORITY = object()
_APPROVAL_REF_RE = re.compile(r"^current-conversation:[A-Za-z0-9._:/-]{1,192}$")


class _NonSerializable:
    """Prevent a host authority object from being smuggled through JSON."""

    def __reduce__(self):  # pragma: no cover - defensive protocol hardening
        raise TypeError(f"{type(self).__name__} is process-local and cannot be serialized")

    def __copy__(self):
        return self

    def __deepcopy__(self, memo):
        return self


@dataclass(frozen=True, slots=True)
class TrustedWorkflowApproval(_NonSerializable):
    """Process-local approval bound to one answer packet and one requested mode.

    A JSON object can describe what a user *may* have said, but it cannot prove
    that the current conversation user said it.  The Codex host creates this
    object after resolving a message reference; runtime stages only accept this
    object as authority.  The private authority sentinel and non-serializable
    methods make an Agent-generated file insufficient by construction.
    """

    evidence_ref: str
    scope: str
    statement: str
    confirmation_digest: str
    requested_mode: str
    _authority: object = field(repr=False, compare=False)


def _canonical_confirmation(value: Mapping[str, Any]) -> str:
    """Canonicalize the packet while excluding only embedded authority.

    Binding just ``answers`` and ``action`` would let a caller alter source,
    confirmation flags, or other packet metadata after the host approved it.
    Preserve every serializable packet field and deliberately omit the
    self-asserted ``approvalReceipt`` field, which is evidence but never
    authority.
    """
    payload = {
        str(key): copy.deepcopy(raw)
        for key, raw in value.items()
        if str(key) not in {"approvalReceipt", "hostApproval", "trustedApproval"}
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def confirmation_digest(value: Mapping[str, Any]) -> str:
    """Return the stable digest used to bind an approval to the shown packet."""
    if not isinstance(value, Mapping):
        return ""
    return hashlib.sha256(_canonical_confirmation(value).encode("utf-8")).hexdigest()


def _validated_approval_ref(value: Any) -> str:
    if not isinstance(value, str) or _APPROVAL_REF_RE.fullmatch(value.strip()) is None:
        raise ValueError("evidence_ref must match current-conversation:<stable-reference>")
    lowered = value.casefold()
    if any(token in lowered for token in ("password=", "token=", "api_key=", "cookie=")):
        raise ValueError("evidence_ref cannot contain sensitive data")
    return value.strip()


def bind_trusted_workflow_approval(
    confirmation: Mapping[str, Any],
    *,
    evidence_ref: str,
    evidence_resolver: Callable[[str], bool],
    scope: str,
    requested_mode: str = DEFAULT_MODE,
    statement: str,
) -> TrustedWorkflowApproval:
    """Mint a process-local approval after the trusted host resolves the user.

    ``evidence_resolver`` belongs to the host, not to project code or the
    model.  A resolver returning anything other than the literal ``True`` is
    rejected.  The packet digest prevents changing answers or mode after the
    user approved the displayed understanding card.
    """
    if not isinstance(confirmation, Mapping):
        raise ValueError("confirmation must be an object")
    reference = _validated_approval_ref(evidence_ref)
    if not callable(evidence_resolver):
        raise ValueError("a trusted host evidence resolver is required")
    try:
        resolved = evidence_resolver(reference)
    except Exception as error:  # pragma: no cover - host callback boundary
        raise ValueError("host evidence could not be resolved safely") from error
    if resolved is not True:
        raise ValueError("host evidence is not verified")
    normalized_scope = str(scope or "").strip().upper()
    if normalized_scope not in {"UNDERSTANDING", "DIAGNOSIS", "FULL", "FULL_UPGRADE"}:
        raise ValueError("scope must be UNDERSTANDING, DIAGNOSIS, FULL, or FULL_UPGRADE")
    normalized_mode = normalize_mode(requested_mode)
    normalized_statement = str(statement or "").strip()
    if len(normalized_statement) < 4:
        raise ValueError("statement must contain an explicit user decision")
    return TrustedWorkflowApproval(
        evidence_ref=reference,
        scope=normalized_scope,
        statement=normalized_statement,
        confirmation_digest=confirmation_digest(confirmation),
        requested_mode=normalized_mode,
        _authority=_WORKFLOW_AUTHORITY,
    )


def require_trusted_workflow_approval(value: TrustedWorkflowApproval | None) -> TrustedWorkflowApproval | None:
    """Validate the non-serializable host binding at every stage boundary."""
    if value is None:
        return None
    if not isinstance(value, TrustedWorkflowApproval) or value._authority is not _WORKFLOW_AUTHORITY:
        raise ValueError("a process-local trusted workflow approval is required")
    return value


def normalize_mode(value: str | None, *, default: str = DEFAULT_MODE) -> str:
    """Return the narrowest supported mode, rejecting silent expansion."""
    candidate = str(value or default).strip().casefold()
    if candidate in {"audit", "consult", "consultation", "review"}:
        return "diagnose"
    if candidate in {"design", "upgrade", "commercial", "commercial-upgrade"}:
        return "full"
    if candidate not in MODE_NAMES:
        raise ValueError(f"unsupported workflow mode: {candidate}")
    return candidate


def is_answer_round_action(value: str | None) -> bool:
    """Return whether an action only records an understanding-card round."""
    return str(value or "").strip().casefold() in ANSWER_ROUND_ACTIONS


def is_diagnosis_only_action(value: str | None) -> bool:
    """Return whether an action may open diagnosis but never full upgrade."""
    return str(value or "").strip().casefold() in DIAGNOSIS_ONLY_ACTIONS


def required_scope_for_action(action: str | None, mode: str | None) -> str:
    """Map a user action to its minimum host approval scope.

    Answer rounds intentionally return ``UNDERSTANDING``; callers still have
    to stop after saving that round.  ``continue-diagnosis`` cannot be used to
    smuggle a full request through a caller that selected ``full``.
    """
    normalized_action = str(action or "").strip().casefold()
    if normalized_action in ANSWER_ROUND_ACTIONS:
        return "UNDERSTANDING"
    if normalized_action in DIAGNOSIS_ONLY_ACTIONS:
        return "DIAGNOSIS"
    return "FULL" if normalize_mode(mode) == "full" else "DIAGNOSIS"


def model_capability_profile(value: str | None = None) -> dict[str, Any]:
    """Choose optional acceleration without making safety model-dependent.

    Host integrations may provide a profile.  Unknown or absent profiles use
    the conservative baseline; all profiles share the same approval semantics.
    """
    candidate = str(value or os.environ.get("WUQ_MODEL_CAPABILITY_PROFILE") or "baseline").strip().casefold()
    if candidate not in {"baseline", "standard", "advanced"}:
        candidate = "baseline"
    return {
        "id": candidate,
        "source": "host-or-default" if value or os.environ.get("WUQ_MODEL_CAPABILITY_PROFILE") else "default",
        "unknownFallsBackTo": "baseline",
        "optionalAcceleration": candidate in {"standard", "advanced"},
        "maySkipApproval": False,
        "mayWriteBeforeApproval": False,
        "contractInvariant": True,
    }


def validate_confirmation(
    confirmation: Mapping[str, Any] | None,
    *,
    approval: TrustedWorkflowApproval | Mapping[str, Any] | None = None,
    required_scope: str = "UNDERSTANDING",
    required_mode: str | None = None,
) -> dict[str, Any]:
    """Validate a response packet against a process-local host approval.

    A mapping supplied by a CLI flag is deliberately *not* authority: it is
    serializable and can be generated by the model.  Only
    :class:`TrustedWorkflowApproval`, minted by ``bind_trusted_workflow_approval``
    after a host evidence resolver confirms the current message, can open a
    workflow stage.
    """
    value = dict(confirmation or {})
    source = str(value.get("source") or "").strip().casefold()
    generated_source = source in _GENERATED_CONFIRMATION_SOURCES
    action = str(value.get("action") or "").strip().casefold()
    if action == "audit-only":
        return {
            "trusted": True,
            "status": "AUDIT_ONLY",
            "reason": "用户选择只查看检测结果；不进入建议或实施。",
            "scope": "AUDIT_ONLY",
        }
    if isinstance(approval, Mapping):
        return {
            "trusted": False,
            "status": "SERIALIZED_APPROVAL_REJECTED",
            "reason": "序列化 JSON 只能作为回答证据；必须由当前 Codex 宿主绑定不可序列化的对话确认对象。",
            "scope": required_scope,
        }
    if not isinstance(approval, TrustedWorkflowApproval) or approval._authority is not _WORKFLOW_AUTHORITY:
        return {
            "trusted": False,
            "status": "SELF_GENERATED_CONFIRMATION_REJECTED" if generated_source else "CURRENT_CONVERSATION_APPROVAL_REQUIRED",
            "reason": "文件由工作台或 Agent 生成，不能代表当前对话中的用户授权。" if generated_source else "需要当前对话中的用户确认；下载的 JSON 本身不能授予权限。",
            "scope": required_scope,
        }
    try:
        require_trusted_workflow_approval(approval)
    except ValueError:
        return {
            "trusted": False,
            "status": "INVALID_APPROVAL_RECEIPT",
            "reason": "确认对象不是由可信宿主绑定的当前对话授权。",
            "scope": required_scope,
        }
    expected_digest = confirmation_digest(value)
    if approval.confirmation_digest != expected_digest:
        return {
            "trusted": False,
            "status": "APPROVAL_PACKET_MISMATCH",
            "reason": "用户确认绑定的回答包已被修改，必须重新确认当前理解卡。",
            "scope": required_scope,
        }
    scope = str(approval.scope or "").strip().upper()
    if scope not in {"UNDERSTANDING", "DIAGNOSIS", "FULL", "FULL_UPGRADE"}:
        return {
            "trusted": False,
            "status": "INVALID_APPROVAL_RECEIPT",
            "reason": "确认范围不受支持。",
            "scope": required_scope,
        }
    if required_scope == "FULL" and scope not in {"FULL", "FULL_UPGRADE"}:
        return {
            "trusted": False,
            "status": "SCOPE_APPROVAL_REQUIRED",
            "reason": "进入完整设计/实施候选需要单独的完整升级确认。",
            "scope": required_scope,
        }
    if required_scope == "DIAGNOSIS" and scope not in {"DIAGNOSIS", "FULL", "FULL_UPGRADE"}:
        return {
            "trusted": False,
            "status": "SCOPE_APPROVAL_REQUIRED",
            "reason": "进入只读诊断需要单独的诊断范围确认。",
            "scope": required_scope,
        }
    if required_mode and normalize_mode(approval.requested_mode) != normalize_mode(required_mode):
        return {
            "trusted": False,
            "status": "APPROVAL_MODE_MISMATCH",
            "reason": "确认收据绑定的工作模式与当前请求不一致，必须重新确认。",
            "scope": required_scope,
        }
    if action in {"continue-with-inference", "continue"}:
        return {
            "trusted": False,
            "status": "EXPLICIT_ANSWERS_REQUIRED",
            "reason": "不能用一个笼统的继续动作替代对高影响未知项的逐项确认。",
            "scope": required_scope,
        }
    if action not in {"confirm-understanding", "confirm", "edit-one", "continue-round", "continue-diagnosis"}:
        return {
            "trusted": False,
            "status": "CONFIRMATION_ACTION_INVALID",
            "reason": "确认动作不受支持。",
            "scope": required_scope,
        }
    return {
        "trusted": True,
        "status": "USER_CONFIRMATION_ACCEPTED",
        "reason": "当前对话用户已确认指定范围；回答文件仅作为证据输入。",
        "scope": scope,
        "receipt": {
            "evidenceRef": approval.evidence_ref,
            "scope": approval.scope,
            "statement": approval.statement,
            "requestedMode": approval.requested_mode,
            "processLocal": True,
        },
        "answerPacketWasGenerated": generated_source,
    }


def confirmation_ledger(
    questions: list[Mapping[str, Any]],
    validation: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Normalize unresolved and conflicting business assumptions for UI/export."""
    trusted = bool(validation.get("trusted"))
    result: list[dict[str, Any]] = []
    for question in questions:
        status = str(question.get("status") or "UNANSWERED")
        if not trusted and status in {"USER_CONFIRMED", "INFERENCE_ACCEPTED"}:
            status = "UNTRUSTED_INPUT"
        evidence = "USER_CONFIRMED" if trusted and status == "USER_CONFIRMED" else (
            "CONFLICTED" if status == "CONFLICTED" else "UNKNOWN"
        )
        result.append({
            "id": question.get("id"),
            "question": question.get("question"),
            "status": status,
            "evidenceType": evidence,
            "currentInference": question.get("currentInference"),
            "answer": question.get("answer"),
            "impact": list(question.get("changes") or []),
            "owner": "current-conversation-user",
        })
    return result
