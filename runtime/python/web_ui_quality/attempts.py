"""Deterministic three-strike limiter for one stable Provider issue key."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Callable

from .contracts import ContractViolation, digest_json


STRATEGY_KINDS = ("root_cause_minimal_fix", "alternative_path", "scope_reduction", "fallback")
STRATEGY_LABELS = {"root_cause_minimal_fix": "ROOT_CAUSE_MINIMAL_FIX", "alternative_path": "ALTERNATIVE_PATH", "scope_reduction": "SCOPE_REDUCTION", "fallback": "FALLBACK"}


def issue_fingerprint(feature_id: str, provider_id: str, target: str, operation: str, root_cause: str) -> str:
    values = [feature_id, provider_id, target.replace("\\", "/"), operation, " ".join(root_cause.split()).casefold()]
    if any(not isinstance(item, str) or not item for item in values):
        raise ContractViolation("ATTEMPT_ISSUE_INVALID", ["$: issue fingerprint fields must be non-empty"])
    return digest_json(values)


@dataclass(frozen=True)
class AttemptPermit:
    issue_key: str
    attempt: int
    strategy_kind: str
    strategy_digest: str


@dataclass(frozen=True)
class AttemptRecord:
    feature_id: str
    provider_id: str
    target: str
    root_cause: str
    permit: AttemptPermit
    evidence_digest: str
    result: str
    remaining_risk: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "issueFingerprint": self.permit.issue_key,
            "attempt": self.permit.attempt,
            "strategy": STRATEGY_LABELS[self.permit.strategy_kind],
            "strategyDigest": self.permit.strategy_digest,
            "provider": self.provider_id,
            "rootCause": self.root_cause,
            "evidenceDigest": self.evidence_digest,
            "result": self.result,
            "remainingRisk": self.remaining_risk,
            "featureId": self.feature_id,
            "target": self.target,
        }


@dataclass
class AttemptLimiter:
    _history: dict[str, list[AttemptRecord]] = field(default_factory=dict)
    _pending: dict[str, AttemptPermit] = field(default_factory=dict)

    def begin(self, issue_key: str, strategy_kind: str, strategy_detail: str) -> AttemptPermit:
        history = self._history.setdefault(issue_key, [])
        if issue_key in self._pending:
            raise ContractViolation("ATTEMPT_PENDING", ["$: prior attempt has no recorded result"])
        attempt = len(history) + 1
        if attempt > 3:
            raise ContractViolation("ATTEMPT_LIMIT_REACHED", ["$: fourth attempt is forbidden"])
        if strategy_kind not in STRATEGY_KINDS or not strategy_detail.strip():
            raise ContractViolation("ATTEMPT_STRATEGY_INVALID", ["$: invalid strategy"])
        if attempt == 1 and strategy_kind != "root_cause_minimal_fix":
            raise ContractViolation("ATTEMPT_STRATEGY_INVALID", ["$: first attempt must be minimal root-cause fix"])
        if attempt == 2 and strategy_kind != "alternative_path":
            raise ContractViolation("ATTEMPT_STRATEGY_INVALID", ["$: second attempt must use an alternative path"])
        if attempt == 3 and strategy_kind not in {"scope_reduction", "fallback"}:
            raise ContractViolation("ATTEMPT_STRATEGY_INVALID", ["$: third attempt must reduce scope or use fallback"])
        strategy_digest = digest_json({"kind": strategy_kind, "detail": " ".join(strategy_detail.split())})
        if any(item.permit.strategy_digest == strategy_digest for item in history):
            raise ContractViolation("ATTEMPT_STRATEGY_REPEATED", ["$: strategy must differ from earlier attempts"])
        permit = AttemptPermit(issue_key, attempt, strategy_kind, strategy_digest)
        self._pending[issue_key] = permit
        return permit

    def record_result(
        self, permit: AttemptPermit, *, feature_id: str, provider_id: str, target: str,
        root_cause: str, evidence_digest: str, result: str, remaining_risk: str,
    ) -> AttemptRecord:
        if self._pending.get(permit.issue_key) != permit:
            raise ContractViolation("ATTEMPT_PERMIT_INVALID", ["$: permit is not pending"])
        if result not in {"PASS", "FAIL", "NOT_VERIFIED"} or remaining_risk not in {"R0", "R1", "R2", "R3"}:
            raise ContractViolation("ATTEMPT_RESULT_INVALID", ["$: result and remaining risk required"])
        if len(evidence_digest) != 64 or any(char not in "0123456789abcdef" for char in evidence_digest):
            raise ContractViolation("ATTEMPT_RESULT_INVALID", ["$.evidenceDigest: sha256 required"])
        expected = issue_fingerprint(feature_id, provider_id, target, "provider_call", root_cause)
        if expected != permit.issue_key:
            raise ContractViolation("ATTEMPT_ISSUE_MISMATCH", ["$: result does not match issue key"])
        record = AttemptRecord(feature_id, provider_id, target, root_cause, permit, evidence_digest, result, remaining_risk)
        self._history[permit.issue_key].append(record)
        del self._pending[permit.issue_key]
        return record

    def record_failure(
        self, permit: AttemptPermit, *, feature_id: str, provider_id: str, target: str,
        root_cause: str, evidence_digest: str, result: str, remaining_risk: str,
    ) -> AttemptRecord:
        if result not in {"FAIL", "NOT_VERIFIED"}:
            raise ContractViolation("ATTEMPT_RESULT_INVALID", ["$: failure result required"])
        return self.record_result(
            permit, feature_id=feature_id, provider_id=provider_id, target=target,
            root_cause=root_cause, evidence_digest=evidence_digest, result=result,
            remaining_risk=remaining_risk,
        )

    def invoke(
        self, *, feature_id: str, provider_id: str, target: str, root_cause: str,
        strategy_kind: str, strategy_detail: str, provider_call: Callable[[], Any],
        evidence_digest: str, remaining_risk: str,
    ) -> Any:
        key = issue_fingerprint(feature_id, provider_id, target, "provider_call", root_cause)
        permit = self.begin(key, strategy_kind, strategy_detail)
        try:
            result = provider_call()
            self.record_result(
                permit, feature_id=feature_id, provider_id=provider_id, target=target,
                root_cause=root_cause, evidence_digest=evidence_digest, result="PASS",
                remaining_risk=remaining_risk,
            )
            return result
        except Exception:
            self.record_failure(
                permit, feature_id=feature_id, provider_id=provider_id, target=target,
                root_cause=root_cause, evidence_digest=evidence_digest,
                result="NOT_VERIFIED", remaining_risk=remaining_risk,
            )
            raise

    def call_allowed(self, issue_key: str) -> bool:
        return len(self._history.get(issue_key, ())) < 3 and issue_key not in self._pending

    def attempt_count(self, issue_key: str) -> int:
        return len(self._history.get(issue_key, ()))

    def records(self, issue_key: str | None = None) -> list[dict[str, Any]]:
        rows = self._history.get(issue_key, ()) if issue_key else [item for values in self._history.values() for item in values]
        return [item.to_dict() for item in rows]
