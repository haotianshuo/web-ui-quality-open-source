"""Current-conversation Host Bridge contracts.

Runtime can request a Host decision and verify post-write hashes, but it cannot
mint, deserialize, or authenticate user authorization.  Actual source writes
belong to the Codex Host.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .contracts import ContractViolation, digest_json, hash_file

_TRUSTED_HOST_WRITE_AUTHORITY = object()


@dataclass(frozen=True, slots=True)
class HostTaskScope:
    """A non-authoritative scope claim for compatibility.

    The object intentionally carries no secret authority.  It may be displayed
    or sent to a Host adapter, but Runtime must never treat it as permission.
    """

    task_id: str
    session_id: str
    mode: str
    finding_ids: tuple[str, ...] = ()
    source_scope: tuple[str, ...] = ()
    exclusions: tuple[str, ...] = (
        "dependencies", "api", "permissions", "persistence", "external-communication", "deployment", "publishing"
    )
    authorization_granted: bool = False

    @property
    def digest(self) -> str:
        return digest_json({
            "taskId": self.task_id, "sessionId": self.session_id, "mode": self.mode,
            "findingIds": self.finding_ids, "sourceScope": self.source_scope,
            "exclusions": self.exclusions, "authorizationGranted": False,
        })


@dataclass(frozen=True, slots=True)
class TrustedHostWriteReceipt:
    """Process-local proof that current project files match a bound receipt."""

    payload: Mapping[str, Any]
    receipt_digest: str
    _authority: object

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": "HOST_WRITE_VERIFIED",
            "receiptDigest": self.receipt_digest,
            **dict(self.payload),
            "authorizationGranted": False,
        }


def bind_narrow_project_local_ui_edit(*, task_id: str, session_id: str, finding_ids: list[str], source_scope: list[str]) -> HostTaskScope:
    """Build a scope claim; despite the legacy name, this never grants authority."""
    if not task_id or not session_id or not finding_ids or not source_scope:
        raise ContractViolation("HOST_SCOPE_INVALID", ["$: task, session, findings, and source scope are required"])
    return HostTaskScope(task_id, session_id, "NARROW_PROJECT_LOCAL_UI_EDIT", tuple(finding_ids), tuple(source_scope))


def require_host_scope(
    value: HostTaskScope | None,
    *,
    mode: str,
    task_id: str,
    source_scope: list[str],
    session_id: str | None = None,
    finding_ids: Sequence[str] = (),
    exclusions: Sequence[str] = (),
) -> HostTaskScope:
    """Refuse Runtime-side authorization.

    Python objects are not a trustworthy proof of a current-conversation Host
    decision.  The Host must perform the write and return a verifiable receipt.
    """
    raise ContractViolation(
        "HOST_EDITING_REQUIRED",
        ["$: Runtime cannot authenticate Host authority; generate a Patch Candidate, let the Host write it, then verify the Host write receipt"],
    )


def bridge_request(action: str, *, task_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    if action not in {
        "submitProductConfirmation", "submitDesignDecision", "submitFixApproval", "submitRecheckRequest",
        "submitPatchCandidate", "submitHostWriteReceipt",
    }:
        raise ContractViolation("HOST_BRIDGE_ACTION_INVALID", [f"$: {action}"])
    return {
        "action": action,
        "taskId": task_id,
        "payload": dict(payload),
        "payloadDigest": digest_json(dict(payload)),
        "delivery": "CURRENT_CONVERSATION_HOST_BRIDGE",
        "jsonExportOptional": True,
        "authorizationGranted": False,
        "fallback": ["生成自然语言摘要", "尝试复制到剪贴板", "提示用户回到当前对话说明选择"],
    }


def verify_host_write_receipt(
    project_root: str | Path,
    receipt: Mapping[str, Any],
    *,
    task_id: str,
    session_id: str,
    finding_ids: Sequence[str],
    source_scope: Sequence[str],
    exclusions: Sequence[str],
    run_id: str,
    baseline: Mapping[str, Any],
    plan_digest: str,
    toolchain_digest: str,
    verification_context_digest: str,
    scope_baseline: Mapping[str, Any] | None = None,
) -> TrustedHostWriteReceipt:
    """Verify files after the Host reports a completed write.

    This proves the current files match the receipt; it does not prove who made
    the change or create authority retroactively.
    """
    root = Path(project_root).expanduser().resolve()
    expected = {
        "runId": run_id,
        "taskId": task_id,
        "sessionId": session_id,
        "findingIds": list(finding_ids),
        "sourceScope": list(source_scope),
        "exclusions": list(exclusions),
        "baselineDigest": baseline.get("baselineDigest"),
        "planDigest": plan_digest,
        "toolchainDigest": toolchain_digest,
        "verificationContextDigest": verification_context_digest,
        "scopeBaselineDigest": (scope_baseline or {}).get("scopeBaselineDigest"),
    }
    mismatches = [key for key, value in expected.items() if receipt.get(key) != value]
    if mismatches:
        raise ContractViolation("HOST_WRITE_RECEIPT_MISMATCH", [f"$.{key}: receipt binding mismatch" for key in mismatches])
    files = receipt.get("files")
    if not isinstance(files, list) or not files:
        raise ContractViolation("HOST_WRITE_RECEIPT_INVALID", ["$.files: non-empty array required"])
    baseline_files = {str(row.get("path")): row for row in baseline.get("files", []) if isinstance(row, Mapping) and row.get("path")}
    scope_files = {str(row.get("path")): row for row in (scope_baseline or {}).get("files", []) if isinstance(row, Mapping) and row.get("path")}
    if scope_baseline:
        body = {k: v for k, v in dict(scope_baseline).items() if k != "scopeBaselineDigest"}
        if digest_json(body) != scope_baseline.get("scopeBaselineDigest"):
            raise ContractViolation("SCOPE_BASELINE_TAMPERED", ["$.scopeBaselineDigest: mismatch"])
        coverage = scope_baseline.get("criticalContextCoverage")
        if baseline.get("completenessStatus") != "COMPLETE":
            if not isinstance(coverage, Mapping) or coverage.get("status") != "COMPLETE":
                raise ContractViolation(
                    "CRITICAL_CONTEXT_INCOMPLETE",
                    ["$: partial global baseline requires complete target-adjacent toolchain/config context before Host write verification"],
                )
        for context_row in scope_baseline.get("criticalContextFiles", []):
            if not isinstance(context_row, Mapping):
                raise ContractViolation("CRITICAL_CONTEXT_INCOMPLETE", ["$.criticalContextFiles: object entries required"])
            context_rel = str(context_row.get("path") or "").replace("\\", "/")
            if context_rel in source_scope:
                continue
            context_path = (root / context_rel).resolve()
            try:
                context_path.relative_to(root)
            except ValueError as error:
                raise ContractViolation("SOURCE_SCOPE_ESCAPE", [f"$.criticalContextFiles: {context_rel!r} escapes project root"]) from error
            if not context_path.is_file() or context_path.is_symlink():
                raise ContractViolation("CRITICAL_CONTEXT_DRIFT", [f"$.criticalContextFiles: {context_rel!r} is missing or no longer a regular file"])
            if hash_file(context_path) != context_row.get("sha256"):
                raise ContractViolation("CRITICAL_CONTEXT_DRIFT", [f"$.criticalContextFiles: {context_rel!r} changed after the patch scope was baselined"])
    if baseline.get("completenessStatus") != "COMPLETE" and not scope_baseline:
        raise ContractViolation("BASELINE_INCOMPLETE", ["$: partial global baseline requires an exact sealed scope baseline before Host write verification"])
    verified: list[dict[str, Any]] = []
    for row in files:
        if not isinstance(row, Mapping):
            raise ContractViolation("HOST_WRITE_RECEIPT_INVALID", ["$.files: object entries required"])
        rel = str(row.get("path") or "").replace("\\", "/")
        if rel not in source_scope:
            raise ContractViolation("HOST_WRITE_RECEIPT_MISMATCH", [f"$.files: {rel!r} outside source scope"])
        path = (root / rel).resolve()
        try:
            path.relative_to(root)
        except ValueError as error:
            raise ContractViolation("SOURCE_SCOPE_ESCAPE", [f"$.files: {rel!r} escapes project root"]) from error
        if not path.is_file() or path.is_symlink():
            raise ContractViolation("HOST_WRITE_RECEIPT_MISMATCH", [f"$.files: regular file missing for {rel!r}"])
        baseline_row = scope_files.get(rel) or baseline_files.get(rel)
        if baseline_row is None:
            raise ContractViolation("HOST_WRITE_RECEIPT_MISMATCH", [f"$.files: {rel!r} was not indexed by the project or scope baseline"])
        before_sha = str(row.get("beforeSha256") or "")
        if before_sha != baseline_row.get("sha256"):
            raise ContractViolation("HOST_WRITE_RECEIPT_MISMATCH", [f"$.files: before hash mismatch for {rel!r}"])
        actual = hash_file(path)
        expected_after = str(row.get("afterSha256") or "")
        if actual != expected_after:
            raise ContractViolation("HOST_WRITE_RECEIPT_MISMATCH", [f"$.files: after hash mismatch for {rel!r}"])
        if before_sha == actual:
            raise ContractViolation("HOST_WRITE_RECEIPT_NO_CHANGE", [f"$.files: no content change recorded for {rel!r}"])
        verified.append({"path": rel, "beforeSha256": before_sha, "afterSha256": actual})
    verified.sort(key=lambda row: row["path"])
    if [row["path"] for row in verified] != sorted(dict.fromkeys(str(item) for item in source_scope)):
        raise ContractViolation("HOST_WRITE_RECEIPT_MISMATCH", ["$.files: receipt paths must exactly match sourceScope"])
    candidate_payload = {"sourceScope": list(source_scope), "files": verified}
    patch_candidate_digest = digest_json(candidate_payload)
    if receipt.get("patchCandidateDigest") != patch_candidate_digest:
        raise ContractViolation("HOST_WRITE_RECEIPT_MISMATCH", ["$.patchCandidateDigest: digest does not match bound before/after hashes"])
    payload = {**expected, "files": verified, "patchCandidateDigest": patch_candidate_digest}
    return TrustedHostWriteReceipt(payload, digest_json(payload), _TRUSTED_HOST_WRITE_AUTHORITY)


def require_verified_host_write(value: TrustedHostWriteReceipt | None) -> TrustedHostWriteReceipt:
    if not isinstance(value, TrustedHostWriteReceipt) or value._authority is not _TRUSTED_HOST_WRITE_AUTHORITY:
        raise ContractViolation("TRUSTED_HOST_WRITE_RECEIPT_REQUIRED", ["$: process-local verified Host write receipt required"])
    return value


def build_repair_scope_revert_plan(value: TrustedHostWriteReceipt) -> dict[str, Any]:
    """Build a non-authoritative, coverage-bounded revert plan.

    The plan only describes how the Host could restore files touched by this
    verified repair. It does not contain prior file bytes, does not mutate the
    project, and never claims to restore unindexed repository state.
    """
    trusted = require_verified_host_write(value)
    files = [
        {
            "path": str(row.get("path")),
            "expectedCurrentSha256": str(row.get("afterSha256")),
            "targetBeforeSha256": str(row.get("beforeSha256")),
        }
        for row in trusted.payload.get("files", [])
        if isinstance(row, Mapping)
    ]
    body = {
        "schemaVersion": "1",
        "kind": "REPAIR_SCOPE_REVERT",
        "runId": trusted.payload.get("runId"),
        "taskId": trusted.payload.get("taskId"),
        "sessionId": trusted.payload.get("sessionId"),
        "scope": "REPAIR_SCOPE",
        "files": files,
        "hostExecutionRequired": True,
        "runtimeMayWrite": False,
        "claimBoundary": "This plan can only restore the exact verified repair scope when the Host can recover the recorded Before content. It is not a whole-repository rollback and carries no write authority.",
    }
    body["planDigest"] = digest_json(body)
    return body


def validate_repair_scope_revert_plan(plan: Mapping[str, Any]) -> dict[str, Any]:
    if plan.get("kind") != "REPAIR_SCOPE_REVERT" or plan.get("scope") != "REPAIR_SCOPE":
        raise ContractViolation("REVERT_PLAN_INVALID", ["$: repair-scope revert plan required"])
    body = {key: value for key, value in dict(plan).items() if key != "planDigest"}
    if digest_json(body) != plan.get("planDigest"):
        raise ContractViolation("REVERT_PLAN_TAMPERED", ["$.planDigest: mismatch"])
    files = plan.get("files")
    if not isinstance(files, list) or not files:
        raise ContractViolation("REVERT_PLAN_INVALID", ["$.files: non-empty repair scope required"])
    seen: set[str] = set()
    for row in files:
        if not isinstance(row, Mapping):
            raise ContractViolation("REVERT_PLAN_INVALID", ["$.files: object entries required"])
        path = str(row.get("path") or "")
        if not path or path in seen:
            raise ContractViolation("REVERT_PLAN_INVALID", ["$.files: unique file paths required"])
        seen.add(path)
        if not row.get("expectedCurrentSha256") or not row.get("targetBeforeSha256"):
            raise ContractViolation("REVERT_PLAN_INVALID", [f"$.files[{path}]: current/before hashes required"])
    return {"status": "VALID", "planDigest": plan.get("planDigest"), "fileCount": len(files), "writeAuthority": "HOST_ONLY"}


__all__ = [
    "HostTaskScope", "TrustedHostWriteReceipt", "bind_narrow_project_local_ui_edit", "require_host_scope",
    "bridge_request", "verify_host_write_receipt", "require_verified_host_write",
    "build_repair_scope_revert_plan", "validate_repair_scope_revert_plan",
]
