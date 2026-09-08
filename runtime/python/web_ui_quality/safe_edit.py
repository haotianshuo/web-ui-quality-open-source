"""Approved, scope-bound Safe Edit for UTF-8 Web presentation files."""

from __future__ import annotations

import copy
import difflib
import json
import os
import re
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO, Callable, Iterator, Mapping, Sequence

from .contracts import (
    ContractViolation,
    build_source_scope_manifest,
    digest_json,
    plan_digest,
    redact_text,
    sha256_hex,
    source_scope_fingerprint,
    validate_productization_plan,
)


DEPENDENCY_FILES = {
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "bun.lock",
    "bun.lockb",
    "requirements.txt",
    "pyproject.toml",
    "poetry.lock",
    "pipfile",
    "pipfile.lock",
    "cargo.toml",
    "cargo.lock",
    "go.mod",
    "go.sum",
}
ALLOWED_SUFFIXES = {".html", ".htm", ".css", ".vue", ".svelte", ".jsx", ".tsx"}
APPROVAL_REF_RE = re.compile(r"^current-conversation:[A-Za-z0-9._:/-]{1,192}$")
TASK_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
R3_CHANGED_CONTENT_RE = re.compile(
    r"(?ix)"
    r"(?:\bfetch\s*\(|\bXMLHttpRequest\b|\baxios\b|\bWebSocket\b|\bEventSource\b|"
    r"\bsendBeacon\s*\(|\blocalStorage\b|\bsessionStorage\b|\bindexedDB\b|"
    r"\bdocument\s*\.\s*cookie\b|\b(?:grant|revoke)Permission\s*\(|"
    r"\b(?:permission|authorization|authentication)\b|"
    r"\b(?:task|order|record|request)\s*\.\s*(?:status|state)\s*=|"
    r"\b(?:transition|setStatus|setState|dispatch|persist|save|delete|remove)\s*\(|"
    r"(?:^|[^A-Za-z0-9_])/(?:api|graphql)/|\b(?:POST|PUT|PATCH|DELETE)\b)"
)
EXTERNAL_ASSET_RE = re.compile(
    r"(?ix)(?:<\s*(?:script|link)[^>]+(?:src|href)\s*=\s*['\"]?\s*(?:https?:)?//|"
    r"@import\b|url\s*\(\s*['\"]?\s*(?:https?:|//|data:))"
)
ROUTE_ATTRIBUTE_RE = re.compile(r"(?ix)\b(?:action|formaction)\s*=|\bhref\s*=\s*['\"]?/(?!/)")
JSX_SAFE_ATTRIBUTE_RE = re.compile(r"(?i)\b(?:className|aria-[A-Za-z-]+|role|title|alt|placeholder|tabIndex|style)\s*=")
JSX_EXECUTABLE_RE = re.compile(
    r"(?x)(?:\b(?:import|export|function|class|const|let|var|if|else|switch|for|while|try|catch|throw|return|await|async)\b|"
    r"=>|\b(?:onClick|onSubmit|onChange|onInput|onKeyDown|onKeyUp|href|to|action|formAction)\s*=|"
    r"\b(?:setState|dispatch|navigate|router|fetch|axios)\b)"
)
_TRUSTED_AUTHORITY = object()


@dataclass(frozen=True, slots=True)
class TrustedApprovalContext:
    """Non-serializable approval binding minted only by trusted host code."""

    task_id: str
    evidence_ref: str
    approved_plan_digest: str
    approved_scope: tuple[str, ...]
    risk_level: str
    _authority: object = field(repr=False, compare=False)


@dataclass(frozen=True, slots=True)
class TrustedApplyReceipt:
    """In-memory proof that this process completed the recorded apply transition."""

    task_id: str
    change_set_digest: str
    execution_receipt_digest: str
    approved_scope: tuple[str, ...]
    project_root_identity: tuple[str, str]
    _authority: object = field(repr=False, compare=False)


@dataclass(frozen=True, slots=True)
class TrustedRollbackApprovalContext:
    """Current-conversation approval bound to one shown rollback preview."""

    task_id: str
    evidence_ref: str
    execution_receipt_digest: str
    rollback_preview_digest: str
    approved_scope: tuple[str, ...]
    _authority: object = field(repr=False, compare=False)


def _normalized_path(raw: str) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise ContractViolation("SOURCE_SCOPE_INVALID", ["$.path: expected non-empty string"])
    normalized = raw.replace("\\", "/")
    pure = PurePosixPath(normalized)
    if pure.is_absolute() or ".." in pure.parts or normalized == "." or not pure.parts:
        raise ContractViolation("SOURCE_SCOPE_ESCAPE", [f"$.path: unsafe relative path {raw!r}"])
    if len(normalized) >= 2 and normalized[1] == ":":
        raise ContractViolation("SOURCE_SCOPE_ESCAPE", [f"$.path: absolute drive path {raw!r}"])
    return pure.as_posix()


def _reject_r3_path(path: str) -> None:
    name = PurePosixPath(path).name.casefold()
    if name in DEPENDENCY_FILES or name.endswith((".lock", ".lockb")):
        raise ContractViolation("R3_REQUIRED", [f"$.changes: dependency file is outside Safe Edit: {path}"])
    suffix = PurePosixPath(path).suffix.casefold()
    if suffix not in ALLOWED_SUFFIXES:
        raise ContractViolation("R3_REQUIRED", [f"$.changes: unsupported non-UI file type: {path}"])


def _root(project_root: str | Path) -> Path:
    try:
        root = Path(project_root).expanduser().resolve(strict=True)
    except FileNotFoundError as error:
        raise ContractViolation("PROJECT_ROOT_INVALID", ["$: project root not found"]) from error
    if not root.is_dir():
        raise ContractViolation("PROJECT_ROOT_INVALID", ["$: project root must be a directory"])
    return root


def _target(root: Path, path: str) -> Path:
    normalized = _normalized_path(path)
    candidate = root.joinpath(*PurePosixPath(normalized).parts)
    try:
        resolved = candidate.resolve(strict=True)
    except FileNotFoundError as error:
        raise ContractViolation("R3_REQUIRED", [f"$.changes: new or missing file is outside Safe Edit: {normalized}"]) from error
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise ContractViolation("SOURCE_SCOPE_ESCAPE", [f"$.path: resolved target leaves project root: {normalized}"]) from error
    if not resolved.is_file():
        raise ContractViolation("SOURCE_SCOPE_INVALID", [f"$.path: expected file: {normalized}"])
    if resolved.stat().st_nlink != 1:
        raise ContractViolation(
            "SOURCE_SCOPE_ESCAPE",
            [f"$.path: hard-linked target has ambiguous ownership: {normalized}"],
        )
    return resolved


def _read_utf8(path: Path, relative: str) -> tuple[str, bytes]:
    raw = path.read_bytes()
    try:
        return raw.decode("utf-8"), raw
    except UnicodeDecodeError as error:
        raise ContractViolation("R3_REQUIRED", [f"$.changes: non-UTF-8 file is outside Safe Edit: {relative}"]) from error


def _ensure_no_sensitive_content(value: str, path: str) -> None:
    _, changed = redact_text(value)
    if changed:
        raise ContractViolation(
            "SENSITIVE_CONTENT_REJECTED",
            [f"$.changes: credential-like assignment detected in {path}; raw value not recorded"],
        )


def _ensure_no_sensitive_value(value: Any, path: str) -> None:
    if isinstance(value, str):
        _ensure_no_sensitive_content(value, path)
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _ensure_no_sensitive_value(item, f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            _ensure_no_sensitive_value(item, f"{path}.{key}")


def _changed_text(before: str, after: str) -> str:
    return "\n".join(
        line[2:]
        for line in difflib.ndiff(before.splitlines(), after.splitlines())
        if line.startswith(("+ ", "- "))
    )


def _script_blocks(value: str) -> list[str]:
    return re.findall(r"(?is)<script\b[^>]*>.*?</script\s*>", value)


def _reject_r3_content(path: str, before: str, after: str) -> None:
    suffix = PurePosixPath(path).suffix.casefold()
    changed = _changed_text(before, after)
    if not changed:
        return
    if R3_CHANGED_CONTENT_RE.search(changed):
        raise ContractViolation("R3_REQUIRED", [f"$.changes: R3 API/permission/data/state/communication impact in {path}"])
    if EXTERNAL_ASSET_RE.search(changed):
        raise ContractViolation("R3_REQUIRED", [f"$.changes: external dependency or communication change in {path}"])
    if suffix == ".css" and re.search(r"(?ix)(?:@import\b|url\s*\()", changed):
        raise ContractViolation("R3_REQUIRED", [f"$.changes: CSS resource loading change in {path}"])
    if suffix in {".html", ".htm", ".vue", ".svelte"}:
        if _script_blocks(before) != _script_blocks(after):
            raise ContractViolation("R3_REQUIRED", [f"$.changes: executable script change is outside Safe Edit: {path}"])
        if ROUTE_ATTRIBUTE_RE.search(changed):
            raise ContractViolation("R3_REQUIRED", [f"$.changes: route or submission target change in {path}"])
    if suffix in {".jsx", ".tsx"}:
        if JSX_EXECUTABLE_RE.search(changed):
            raise ContractViolation("R3_REQUIRED", [f"$.changes: executable React/TypeScript logic change is outside Safe Edit: {path}"])
        meaningful = [line.strip() for line in changed.splitlines() if line.strip()]
        if meaningful and not all(
            line.startswith(("<", "</", "{", "}", "/*", "*", "//"))
            or JSX_SAFE_ATTRIBUTE_RE.search(line)
            or re.fullmatch(r"[A-Za-z0-9 _.,:;!?()（）\-—，。！？、]+", line)
            for line in meaningful
        ):
            raise ContractViolation("R3_REQUIRED", [f"$.changes: JSX/TSX change is not provably presentation-only: {path}"])


def _validated_task_id(value: str) -> str:
    if not isinstance(value, str) or TASK_ID_RE.fullmatch(value) is None:
        raise ContractViolation("CHANGE_SET_INVALID", ["$.taskId: expected stable non-sensitive identifier"])
    _ensure_no_sensitive_content(value, "$.taskId")
    return value


def _validated_evidence_ref(value: str, *, code: str) -> str:
    if not isinstance(value, str) or APPROVAL_REF_RE.fullmatch(value) is None:
        raise ContractViolation(code, ["$: stable current-conversation evidence reference is required"])
    _ensure_no_sensitive_content(value, "$.approvalEvidenceRef")
    return value


def _normalized_scope(value: Any, *, code: str = "CHANGE_SET_SCOPE_MISMATCH") -> list[str]:
    if not isinstance(value, list) or not value or any(not isinstance(item, str) for item in value):
        raise ContractViolation(code, ["$.approvedScope: expected non-empty string array"])
    paths = [_normalized_path(item) for item in value]
    if len(paths) != len(set(paths)):
        raise ContractViolation(code, ["$.approvedScope: duplicate target path"])
    folded: dict[str, str] = {}
    for path in paths:
        key = path.casefold()
        if key in folded and folded[key] != path:
            raise ContractViolation(
                "SOURCE_SCOPE_CASE_COLLISION",
                [f"$.approvedScope: case-fold collision between {folded[key]!r} and {path!r}"],
            )
        folded[key] = path
    return paths


def bind_trusted_current_conversation_approval(
    plan: Mapping[str, Any],
    *,
    evidence_ref: str,
    evidence_resolver: Callable[[str], bool],
    task_id: str = "SAFE-EDIT-001",
) -> TrustedApprovalContext:
    """Removed: Runtime cannot mint current-conversation source-write authority.

    The Codex Host owns source writes.  Runtime produces a Patch Candidate and
    verifies the Host write receipt afterwards; it never holds authority.  The
    signature is retained so existing callers fail loudly instead of silently
    resolving a different name.
    """

    raise ContractViolation("HOST_EDITING_REQUIRED", ["$: Codex Host must apply a shown Patch Candidate; Runtime approval objects are non-authoritative"])


def _patch(path: str, before: str, after: str) -> str:
    return "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
            lineterm="\n",
        )
    )


def _change_set_digest(value: Mapping[str, Any]) -> str:
    immutable = {
        key: item
        for key, item in value.items()
        if key not in {
            "changeSetDigest",
            "status",
            "verificationResults",
            "executionReceiptDigest",
            "rollbackReceiptDigest",
        }
    }
    return digest_json(immutable)


def _project_root_identity(root: Path) -> dict[str, str]:
    identity = root.stat()
    return {"device": str(identity.st_dev), "inode": str(identity.st_ino)}


def rollback_preview_digest(change_set: Mapping[str, Any]) -> str:
    return digest_json(
        {
            "approvedPlanDigest": change_set.get("approvedPlanDigest"),
            "approvedScope": change_set.get("approvedScope"),
            "rollbackPreview": change_set.get("rollbackPreview"),
            "taskId": change_set.get("taskId"),
        }
    )


def _execution_receipt_digest(change_set: Mapping[str, Any]) -> str:
    return digest_json(
        {
            "approvedScope": change_set.get("approvedScope"),
            "changeSetDigest": change_set.get("changeSetDigest"),
            "projectRootIdentity": change_set.get("projectRootIdentity"),
            "status": "applied",
            "taskId": change_set.get("taskId"),
            "verificationResults": change_set.get("verificationResults"),
        }
    )


def _rollback_receipt_digest(change_set: Mapping[str, Any]) -> str:
    return digest_json(
        {
            "changeSetDigest": change_set.get("changeSetDigest"),
            "executionReceiptDigest": change_set.get("executionReceiptDigest"),
            "rollbackPreviewDigest": change_set.get("rollbackPreviewDigest"),
            "status": "rolled_back",
            "taskId": change_set.get("taskId"),
            "verificationResults": change_set.get("verificationResults"),
        }
    )


def prepare_change_set(
    project_root: str | Path,
    plan: Mapping[str, Any],
    changes: Sequence[Mapping[str, Any]],
    *,
    approval_context: TrustedApprovalContext | None = None,
    task_id: str | None = None,
) -> dict[str, Any]:
    """Prepare a deterministic R1/R2 Change Set without writing any target file."""

    plan_value = copy.deepcopy(dict(plan))
    validate_productization_plan(plan_value)
    _ensure_no_sensitive_value(plan_value, "$.plan")
    risk = plan_value["riskLevel"]
    if risk not in {"R1", "R2"}:
        raise ContractViolation("R3_REQUIRED", ["$.riskLevel: Safe Edit accepts only R1 or R2"])
    actual_plan_digest = plan_digest(plan_value)
    if not isinstance(approval_context, TrustedApprovalContext) or approval_context._authority is not _TRUSTED_AUTHORITY:
        raise ContractViolation("TRUSTED_APPROVAL_REQUIRED", ["$: trusted current-conversation approval context is required"])
    actual_task_id = _validated_task_id(task_id or approval_context.task_id)
    approved_scope = _normalized_scope(plan_value["approvedScope"], code="APPROVAL_MISMATCH")
    if (
        approval_context.task_id != actual_task_id
        or approval_context.approved_plan_digest != actual_plan_digest
        or list(approval_context.approved_scope) != approved_scope
        or approval_context.risk_level != risk
    ):
        raise ContractViolation("APPROVAL_MISMATCH", ["$: trusted approval does not match the executable plan"])
    if not isinstance(changes, Sequence) or isinstance(changes, (str, bytes)) or not changes:
        raise ContractViolation("CHANGE_SET_INVALID", ["$.changes: expected non-empty array"])
    if risk == "R1" and len(changes) != 1:
        raise ContractViolation("CHANGE_SET_INVALID", ["$.changes: R1 requires exactly one file"])

    root = _root(project_root)
    prepared: list[dict[str, Any]] = []
    normalized_changes: list[tuple[Mapping[str, Any], str]] = []
    for index, raw_change in enumerate(changes):
        if not isinstance(raw_change, Mapping):
            raise ContractViolation("CHANGE_SET_INVALID", [f"$.changes[{index}]: expected object"])
        allowed_input_keys = {"path", "targetElement", "description", "afterContent", "delete"}
        extras = sorted(set(raw_change) - allowed_input_keys)
        if extras:
            raise ContractViolation("CHANGE_SET_INVALID", [f"$.changes[{index}]: unexpected fields {extras}"])
        if raw_change.get("delete") is True or raw_change.get("afterContent") is None:
            raise ContractViolation("R3_REQUIRED", [f"$.changes[{index}]: deletion is outside Safe Edit"])
        path = _normalized_path(str(raw_change.get("path", "")))
        normalized_changes.append((raw_change, path))

    paths = [path for _, path in normalized_changes]
    _normalized_scope(paths)
    if set(approved_scope) != set(paths):
        raise ContractViolation("APPROVAL_SCOPE_MISMATCH", ["$.approvedScope: must exactly equal change paths"])
    if risk == "R2" and not plan_value["businessInvariants"]:
        raise ContractViolation("CHANGE_SET_INVALID", ["$.businessInvariants: R2 requires explicit invariants"])

    for index, (raw_change, path) in enumerate(normalized_changes):
        _reject_r3_path(path)
        target = _target(root, path)
        after = raw_change.get("afterContent")
        if not isinstance(after, str):
            raise ContractViolation("CHANGE_SET_INVALID", [f"$.changes[{index}].afterContent: expected string"])
        before, before_bytes = _read_utf8(target, path)
        _ensure_no_sensitive_content(before, path)
        _ensure_no_sensitive_content(after, path)
        _reject_r3_content(path, before, after)
        if before == after:
            raise ContractViolation("CHANGE_SET_INVALID", [f"$.changes[{index}]: content is unchanged"])
        target_element = raw_change.get("targetElement")
        description = raw_change.get("description")
        if not isinstance(target_element, str) or not target_element.strip():
            raise ContractViolation("CHANGE_SET_INVALID", [f"$.changes[{index}].targetElement: required"])
        if not isinstance(description, str) or not description.strip():
            raise ContractViolation("CHANGE_SET_INVALID", [f"$.changes[{index}].description: required"])
        _ensure_no_sensitive_content(target_element, f"$.changes[{index}].targetElement")
        _ensure_no_sensitive_content(description, f"$.changes[{index}].description")
        after_bytes = after.encode("utf-8")
        prepared.append(
            {
                "path": path,
                "targetElement": target_element,
                "description": description,
                "beforeContent": before,
                "afterContent": after,
                "beforeSha256": sha256_hex(before_bytes),
                "afterSha256": sha256_hex(after_bytes),
                "patch": _patch(path, before, after),
            }
        )

    manifest = build_source_scope_manifest(root, paths)
    fingerprint = source_scope_fingerprint(manifest)
    full_patch = "".join(item["patch"] for item in prepared)
    change_set: dict[str, Any] = {
        "schemaVersion": "1",
        "taskId": actual_task_id,
        "riskLevel": risk,
        "status": "prepared",
        "approvalStatus": "approved",
        "approvalSource": "user_current_conversation",
        "approvalEvidenceRef": approval_context.evidence_ref,
        "approvedPlanDigest": actual_plan_digest,
        "approvedScope": list(approved_scope),
        "approvedExclusions": list(plan_value["exclusions"]),
        "projectRootIdentity": _project_root_identity(root),
        "sourceScopeFingerprint": fingerprint,
        "sourceScopeManifest": manifest,
        "plan": plan_value,
        "beforeHashes": {item["path"]: item["beforeSha256"] for item in prepared},
        "afterHashes": {item["path"]: item["afterSha256"] for item in prepared},
        "changes": prepared,
        "patch": full_patch,
        "verificationResults": [],
        "unverifiedItems": [],
        "rollbackPreview": [
            {"path": item["path"], "expectedCurrentSha256": item["afterSha256"], "restoreSha256": item["beforeSha256"], "delete": False}
            for item in prepared
        ],
    }
    change_set["rollbackPreviewDigest"] = rollback_preview_digest(change_set)
    change_set["changeSetDigest"] = _change_set_digest(change_set)
    return change_set


def prepare_r1_change(
    project_root: str | Path,
    *,
    path: str,
    target_element: str,
    old_text: str,
    new_text: str,
    approval_evidence_ref: str,
    evidence_resolver: Callable[[str], bool],
    description: str,
    task_id: str = "SAFE-R1-001",
) -> dict[str, Any]:
    root = _root(project_root)
    normalized = _normalized_path(path)
    target = _target(root, normalized)
    before, _ = _read_utf8(target, normalized)
    count = before.count(old_text)
    if count != 1:
        raise ContractViolation("R1_TARGET_AMBIGUOUS", [f"$: expected one target occurrence, found {count}"])
    after = before.replace(old_text, new_text, 1)
    plan = {
        "schemaVersion": "1",
        "businessUnderstanding": "用户明确指定的单一展示层修改。",
        "currentFramework": "保留当前组件、Token 和业务逻辑。",
        "productArchetype": "既有 Web 页面",
        "pageModes": ["精准修复"],
        "mainProblems": [description],
        "mustFix": [description],
        "recommendedOptimizations": [],
        "enterpriseDifferences": [],
        "unverifiedItems": [],
        "recommendation": description,
        "selectionReason": "用户明确指定，且影响限定为单一可逆展示目标。",
        "keyTradeoffs": ["只执行最小文本替换，不扩展到共享组件或业务语义。"],
        "rejectedAlternative": "不进行页面重构或依赖变更。",
        "designInterventionLevel": 1,
        "riskLevel": "R1",
        "approvedScope": [normalized],
        "businessInvariants": ["路由、接口、字段语义、权限和状态机不变"],
        "exclusions": ["依赖、删除、新文件和 R3 行为"],
        "verificationPlan": ["beforeHash、完整 diff、afterHash 和目标文本检查"],
        "rollbackPlan": "仅在 afterHash 匹配时恢复 beforeContent。",
    }
    approval = bind_trusted_current_conversation_approval(
        plan,
        evidence_ref=approval_evidence_ref,
        evidence_resolver=evidence_resolver,
        task_id=task_id,
    )
    return prepare_change_set(
        root,
        plan,
        [{"path": normalized, "targetElement": target_element, "description": description, "afterContent": after}],
        approval_context=approval,
        task_id=task_id,
    )


_BASE_CHANGE_SET_FIELDS = {
    "schemaVersion", "taskId", "riskLevel", "status", "approvalStatus", "approvalSource",
    "approvalEvidenceRef", "approvedPlanDigest", "approvedScope", "approvedExclusions",
    "projectRootIdentity", "sourceScopeFingerprint", "sourceScopeManifest", "plan",
    "beforeHashes", "afterHashes", "changes", "patch", "verificationResults",
    "unverifiedItems", "rollbackPreview", "rollbackPreviewDigest", "changeSetDigest",
}
_STATE_CHANGE_SET_FIELDS = {"executionReceiptDigest", "rollbackReceiptDigest"}
_CHANGE_FIELDS = {
    "path", "targetElement", "description", "beforeContent", "afterContent",
    "beforeSha256", "afterSha256", "patch",
}


def _require_sha(value: Any, path: str, *, code: str = "CHANGE_SET_INVALID") -> str:
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        raise ContractViolation(code, [f"{path}: expected lowercase SHA-256"])
    return value


def _expected_verification(change_set: Mapping[str, Any], *, state: str) -> list[dict[str, str]]:
    hash_key = "afterSha256" if state == "applied" else "beforeSha256"
    return [
        {
            "path": item["path"],
            "expectedSha256": item[hash_key],
            "actualSha256": item[hash_key],
            "result": "PASS",
        }
        for item in change_set["changes"]
    ]


def _validate_executable(change_set: Mapping[str, Any]) -> None:
    """Validate shape plus every execution-critical cross-field invariant."""

    if not isinstance(change_set, Mapping):
        raise ContractViolation("CHANGE_SET_INVALID", ["$: expected object"])
    missing = sorted(_BASE_CHANGE_SET_FIELDS - set(change_set))
    extras = sorted(set(change_set) - _BASE_CHANGE_SET_FIELDS - _STATE_CHANGE_SET_FIELDS)
    if missing or extras:
        errors = [f"$.{key}: required" for key in missing]
        errors.extend(f"$.{key}: unexpected" for key in extras)
        raise ContractViolation("CHANGE_SET_INVALID", errors)
    if change_set.get("schemaVersion") != "1":
        raise ContractViolation("CHANGE_SET_INVALID", ["$.schemaVersion: expected string '1'"])
    _validated_task_id(change_set.get("taskId"))
    status = change_set.get("status")
    if status not in {"prepared", "applied", "rolled_back"}:
        raise ContractViolation("CHANGE_SET_INVALID", ["$.status: unsupported state"])
    if change_set.get("approvalStatus") != "approved" or change_set.get("approvalSource") != "user_current_conversation":
        raise ContractViolation("CHANGE_SET_INVALID", ["$: approval record shape is invalid"])
    _validated_evidence_ref(change_set.get("approvalEvidenceRef"), code="CHANGE_SET_INVALID")
    if change_set.get("riskLevel") not in {"R1", "R2"}:
        raise ContractViolation("R3_REQUIRED", ["$.riskLevel: Safe Edit accepts only R1 or R2"])
    plan = change_set.get("plan")
    try:
        validate_productization_plan(plan)
    except ContractViolation as error:
        raise ContractViolation("CHANGE_SET_INVALID", ["$.plan: invalid Productization Plan"]) from error
    _ensure_no_sensitive_value(plan, "$.plan")
    if plan.get("riskLevel") != change_set["riskLevel"]:
        raise ContractViolation("CHANGE_SET_SCOPE_MISMATCH", ["$.riskLevel: does not match Plan"])
    approved_scope = _normalized_scope(change_set.get("approvedScope"))
    plan_scope = _normalized_scope(plan.get("approvedScope"))
    if approved_scope != plan_scope:
        raise ContractViolation("CHANGE_SET_SCOPE_MISMATCH", ["$.approvedScope: does not match Plan"])
    if change_set["riskLevel"] == "R1" and len(approved_scope) != 1:
        raise ContractViolation("CHANGE_SET_SCOPE_MISMATCH", ["$.approvedScope: R1 requires one path"])
    exclusions = change_set.get("approvedExclusions")
    if not isinstance(exclusions, list) or exclusions != plan.get("exclusions"):
        raise ContractViolation("CHANGE_SET_SCOPE_MISMATCH", ["$.approvedExclusions: does not match Plan"])
    actual_plan_digest = plan_digest(plan)
    if change_set.get("approvedPlanDigest") != actual_plan_digest:
        raise ContractViolation("APPROVAL_MISMATCH", ["$.approvedPlanDigest: does not match canonical Plan"])
    _require_sha(change_set.get("approvedPlanDigest"), "$.approvedPlanDigest")

    root_identity = change_set.get("projectRootIdentity")
    if (
        not isinstance(root_identity, dict)
        or set(root_identity) != {"device", "inode"}
        or any(not isinstance(root_identity[key], str) or not root_identity[key].isdigit() for key in root_identity)
    ):
        raise ContractViolation("CHANGE_SET_INVALID", ["$.projectRootIdentity: invalid stable identity"])

    changes = change_set.get("changes")
    if not isinstance(changes, list) or not changes:
        raise ContractViolation("CHANGE_SET_INVALID", ["$.changes: expected non-empty array"])
    paths: list[str] = []
    rebuilt_patches: list[str] = []
    rebuilt_before: dict[str, str] = {}
    rebuilt_after: dict[str, str] = {}
    rebuilt_preview: list[dict[str, Any]] = []
    before_sizes: dict[str, int] = {}
    for index, item in enumerate(changes):
        if not isinstance(item, dict) or set(item) != _CHANGE_FIELDS:
            raise ContractViolation("CHANGE_SET_INVALID", [f"$.changes[{index}]: invalid field set"])
        path = _normalized_path(item.get("path"))
        _reject_r3_path(path)
        paths.append(path)
        for key in ("targetElement", "description", "beforeContent", "afterContent"):
            if not isinstance(item.get(key), str):
                raise ContractViolation("CHANGE_SET_INVALID", [f"$.changes[{index}].{key}: expected string"])
        if not item["targetElement"].strip() or not item["description"].strip() or item["beforeContent"] == item["afterContent"]:
            raise ContractViolation("CHANGE_SET_INVALID", [f"$.changes[{index}]: empty metadata or unchanged content"])
        _ensure_no_sensitive_value(item, f"$.changes[{index}]")
        before_bytes = item["beforeContent"].encode("utf-8")
        after_bytes = item["afterContent"].encode("utf-8")
        before_sha = sha256_hex(before_bytes)
        after_sha = sha256_hex(after_bytes)
        if item.get("beforeSha256") != before_sha or item.get("afterSha256") != after_sha:
            raise ContractViolation("CHANGE_SET_HASH_MISMATCH", [f"$.changes[{index}]: content/hash mismatch"])
        expected_patch = _patch(path, item["beforeContent"], item["afterContent"])
        if item.get("patch") != expected_patch:
            raise ContractViolation("CHANGE_SET_PATCH_MISMATCH", [f"$.changes[{index}].patch: content mismatch"])
        rebuilt_patches.append(expected_patch)
        rebuilt_before[path] = before_sha
        rebuilt_after[path] = after_sha
        before_sizes[path] = len(before_bytes)
        rebuilt_preview.append(
            {"path": path, "expectedCurrentSha256": after_sha, "restoreSha256": before_sha, "delete": False}
        )
    _normalized_scope(paths)
    if set(paths) != set(approved_scope) or len(paths) != len(approved_scope):
        raise ContractViolation("CHANGE_SET_SCOPE_MISMATCH", ["$.changes: paths do not exactly match approvedScope"])
    if change_set.get("beforeHashes") != rebuilt_before or change_set.get("afterHashes") != rebuilt_after:
        raise ContractViolation("CHANGE_SET_HASH_MISMATCH", ["$: hash maps do not exactly match changes"])
    if change_set.get("patch") != "".join(rebuilt_patches):
        raise ContractViolation("CHANGE_SET_PATCH_MISMATCH", ["$.patch: does not equal complete ordered patches"])
    if change_set.get("rollbackPreview") != rebuilt_preview:
        raise ContractViolation("CHANGE_SET_ROLLBACK_MISMATCH", ["$.rollbackPreview: does not exactly match changes"])
    expected_preview_digest = rollback_preview_digest(change_set)
    if change_set.get("rollbackPreviewDigest") != expected_preview_digest:
        raise ContractViolation("CHANGE_SET_ROLLBACK_MISMATCH", ["$.rollbackPreviewDigest: preview mismatch"])
    _require_sha(change_set.get("rollbackPreviewDigest"), "$.rollbackPreviewDigest")

    manifest = change_set.get("sourceScopeManifest")
    if not isinstance(manifest, dict) or manifest.get("schemaVersion") != "1" or manifest.get("projectRoot") != ".":
        raise ContractViolation("CHANGE_SET_MANIFEST_MISMATCH", ["$.sourceScopeManifest: invalid header"])
    entries = manifest.get("entries")
    if not isinstance(entries, list) or len(entries) != len(approved_scope):
        raise ContractViolation("CHANGE_SET_MANIFEST_MISMATCH", ["$.sourceScopeManifest.entries: scope mismatch"])
    entry_paths: list[str] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ContractViolation("CHANGE_SET_MANIFEST_MISMATCH", [f"$.sourceScopeManifest.entries[{index}]: expected object"])
        path = _normalized_path(entry.get("path"))
        entry_paths.append(path)
        if entry.get("kind") != "file" or entry.get("sha256") != rebuilt_before.get(path):
            raise ContractViolation("CHANGE_SET_MANIFEST_MISMATCH", [f"$.sourceScopeManifest.entries[{index}]: hash/kind mismatch"])
        if entry.get("size") != before_sizes.get(path):
            raise ContractViolation("CHANGE_SET_MANIFEST_MISMATCH", [f"$.sourceScopeManifest.entries[{index}].size: mismatch"])
        resolved_path = entry.get("resolvedPath")
        if not isinstance(resolved_path, str) or _normalized_path(resolved_path) != resolved_path:
            raise ContractViolation("CHANGE_SET_MANIFEST_MISMATCH", [f"$.sourceScopeManifest.entries[{index}].resolvedPath: invalid"])
        if entry.get("linkType") not in {"regular", "symbolic-link", "junction", "reparse-point", "mixed-reparse"}:
            raise ContractViolation("CHANGE_SET_MANIFEST_MISMATCH", [f"$.sourceScopeManifest.entries[{index}].linkType: invalid"])
    if entry_paths != sorted(approved_scope):
        raise ContractViolation("CHANGE_SET_MANIFEST_MISMATCH", ["$.sourceScopeManifest.entries: paths must equal sorted approvedScope"])
    try:
        fingerprint = source_scope_fingerprint(manifest)
    except ContractViolation as error:
        raise ContractViolation("CHANGE_SET_MANIFEST_MISMATCH", ["$.sourceScopeManifest: invalid fingerprint input"]) from error
    if change_set.get("sourceScopeFingerprint") != fingerprint:
        raise ContractViolation("CHANGE_SET_MANIFEST_MISMATCH", ["$.sourceScopeFingerprint: does not match Manifest"])
    _require_sha(change_set.get("sourceScopeFingerprint"), "$.sourceScopeFingerprint")

    verification = change_set.get("verificationResults")
    unverified = change_set.get("unverifiedItems")
    if not isinstance(verification, list) or not isinstance(unverified, list) or any(not isinstance(item, str) for item in unverified):
        raise ContractViolation("CHANGE_SET_INVALID", ["$: verificationResults/unverifiedItems invalid"])
    if status == "prepared":
        if verification or "executionReceiptDigest" in change_set or "rollbackReceiptDigest" in change_set:
            raise ContractViolation("CHANGE_SET_STATE_INVALID", ["$: prepared state contains execution evidence"])
    elif status == "applied":
        if verification != _expected_verification(change_set, state="applied"):
            raise ContractViolation("CHANGE_SET_STATE_INVALID", ["$.verificationResults: invalid applied evidence"])
        if change_set.get("executionReceiptDigest") != _execution_receipt_digest(change_set):
            raise ContractViolation("CHANGE_SET_STATE_INVALID", ["$.executionReceiptDigest: invalid"])
        _require_sha(change_set.get("executionReceiptDigest"), "$.executionReceiptDigest")
        if "rollbackReceiptDigest" in change_set:
            raise ContractViolation("CHANGE_SET_STATE_INVALID", ["$.rollbackReceiptDigest: premature"])
    else:
        if verification != _expected_verification(change_set, state="rolled_back"):
            raise ContractViolation("CHANGE_SET_STATE_INVALID", ["$.verificationResults: invalid rollback evidence"])
        if change_set.get("executionReceiptDigest") != _execution_receipt_digest(
            {**dict(change_set), "status": "applied", "verificationResults": _expected_verification(change_set, state="applied")}
        ):
            raise ContractViolation("CHANGE_SET_STATE_INVALID", ["$.executionReceiptDigest: invalid prior apply evidence"])
        if change_set.get("rollbackReceiptDigest") != _rollback_receipt_digest(change_set):
            raise ContractViolation("CHANGE_SET_STATE_INVALID", ["$.rollbackReceiptDigest: invalid"])
        _require_sha(change_set.get("rollbackReceiptDigest"), "$.rollbackReceiptDigest")
    _require_sha(change_set.get("changeSetDigest"), "$.changeSetDigest")
    if change_set["changeSetDigest"] != _change_set_digest(change_set):
        raise ContractViolation("CHANGE_SET_TAMPERED", ["$: immutable Change Set content changed after preparation"])




def check_plan_stale(project_root: str | Path, change_set: Mapping[str, Any]) -> None:
    _validate_executable(change_set)
    try:
        root = _root(project_root)
        if _project_root_identity(root) != change_set["projectRootIdentity"]:
            raise ContractViolation("PLAN_STALE", ["$: project root identity changed"])
        paths = list(change_set["approvedScope"])
        current = build_source_scope_manifest(root, paths)
        for path in paths:
            _target(root, path)
    except (OSError, ContractViolation) as error:
        if isinstance(error, ContractViolation) and error.code == "PLAN_STALE":
            raise
        raise ContractViolation("PLAN_STALE", ["$: approved path, target, or project root changed"]) from error
    if source_scope_fingerprint(current) != change_set["sourceScopeFingerprint"]:
        raise ContractViolation("PLAN_STALE", ["$: approved source scope or real target changed before execution"])




def apply_change_set(
    project_root: str | Path,
    change_set: Mapping[str, Any],
    *,
    approval_context: TrustedApprovalContext | None = None,
) -> tuple[dict[str, Any], TrustedApplyReceipt]:
    """Removed write path; actual project modification belongs to the Codex Host.

    Runtime emits a Patch Candidate and later verifies the Host write receipt.
    No Runtime code path writes target project files.
    """

    raise ContractViolation("HOST_EDITING_REQUIRED", ["$: Runtime does not write target project files; Host must apply the Patch Candidate and return file hashes"])





def bind_trusted_rollback_approval(
    applied_change_set: Mapping[str, Any],
    apply_receipt: TrustedApplyReceipt | None,
    *,
    evidence_ref: str,
    evidence_resolver: Callable[[str], bool],
) -> TrustedRollbackApprovalContext:
    receipt = _require_apply_receipt(apply_receipt)
    _validate_executable(applied_change_set)
    if applied_change_set.get("status") != "applied":
        raise ContractViolation("CHANGE_SET_STATE_INVALID", ["$: rollback approval requires applied state"])
    _match_apply_receipt(applied_change_set, receipt)
    reference = _validated_evidence_ref(evidence_ref, code="TRUSTED_ROLLBACK_APPROVAL_REQUIRED")
    if not callable(evidence_resolver):
        raise ContractViolation("TRUSTED_ROLLBACK_APPROVAL_REQUIRED", ["$: trusted host evidence resolver is required"])
    try:
        resolved = evidence_resolver(reference)
    except Exception as error:
        raise ContractViolation("TRUSTED_ROLLBACK_APPROVAL_REQUIRED", ["$: rollback evidence could not be resolved safely"]) from error
    if resolved is not True:
        raise ContractViolation("TRUSTED_ROLLBACK_APPROVAL_REQUIRED", ["$: rollback evidence is not verified by trusted host"])
    return TrustedRollbackApprovalContext(
        task_id=applied_change_set["taskId"],
        evidence_ref=reference,
        execution_receipt_digest=applied_change_set["executionReceiptDigest"],
        rollback_preview_digest=applied_change_set["rollbackPreviewDigest"],
        approved_scope=tuple(applied_change_set["approvedScope"]),
        _authority=_TRUSTED_AUTHORITY,
    )










def rollback_change_set(
    project_root: str | Path,
    applied_change_set: Mapping[str, Any],
    *,
    apply_receipt: TrustedApplyReceipt | None = None,
    rollback_approval_context: TrustedRollbackApprovalContext | None = None,
) -> dict[str, Any]:
    """Removed write path; the Codex Host owns reverse-patch execution.

    Runtime emits a reverse Patch Candidate only.
    """

    raise ContractViolation("HOST_EDITING_REQUIRED", ["$: Runtime does not roll back target project files; Host must apply the reverse Patch Candidate"])



def read_enterprise_differences(project_root: str | Path) -> dict[str, Any]:
    """Read the minimal accepted-differences config without auto-migration or writes."""

    root = _root(project_root)
    path = root / ".ui-audit.json"
    if not path.exists():
        return {"status": "missing", "readOnly": True, "schemaVersion": "1", "acceptedDifferences": []}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ContractViolation("UI_AUDIT_CONFIG_INVALID", ["$: .ui-audit.json is not valid UTF-8 JSON"]) from error
    if not isinstance(value, dict) or value.get("schemaVersion") != "1":
        return {"status": "unknown_version", "readOnly": True, "acceptedDifferences": []}
    items = value.get("acceptedDifferences", [])
    if not isinstance(items, list):
        raise ContractViolation("UI_AUDIT_CONFIG_INVALID", ["$.acceptedDifferences: expected array"])
    normalized: list[dict[str, str]] = []
    required = {"id", "scope", "category", "reason"}
    for index, item in enumerate(items):
        if not isinstance(item, dict) or set(item) != required or any(not isinstance(item[key], str) or not item[key].strip() for key in required):
            raise ContractViolation("UI_AUDIT_CONFIG_INVALID", [f"$.acceptedDifferences[{index}]: invalid minimal record"])
        normalized.append({key: item[key] for key in ("id", "scope", "category", "reason")})
    return {"status": "valid", "readOnly": True, "schemaVersion": "1", "acceptedDifferences": normalized}
