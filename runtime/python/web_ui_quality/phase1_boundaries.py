"""Separate Phase-1 read and write boundaries.

Phase 1 deliberately applies policy to both the declared project-relative path
and the resolved physical target. Read authorization never expands write
authority. Write targets reject filesystem aliases (symlink/junction/reparse
components and multi-link files) in the Minimal Trust Contract Slice.
"""
from __future__ import annotations

import json
import os
import stat as statmod
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from .contracts import ContractViolation, digest_json
from .schema_validation import SchemaValidationError, validate_instance


def _schema(name: str) -> dict[str, Any]:
    return json.loads((Path(__file__).with_name("schemas") / name).read_text(encoding="utf-8"))


def _body_digest(value: Mapping[str, Any], digest_key: str) -> str:
    return digest_json({k: v for k, v in dict(value).items() if k != digest_key})


def _norm_rel(value: str) -> str:
    raw = value.replace("\\", "/").strip()
    path = PurePosixPath(raw)
    if not raw or path.is_absolute() or any(part in {"..", ""} for part in path.parts):
        raise ContractViolation("BOUNDARY_PATH_INVALID", [f"$: invalid project-relative path {value!r}"])
    return path.as_posix()


def _under(path: str, roots: list[str]) -> bool:
    normalized = PurePosixPath(path)
    for root in roots:
        r = PurePosixPath(_norm_rel(root.rstrip("/") or "."))
        if r.as_posix() == ".":
            return True
        try:
            normalized.relative_to(r)
            return True
        except ValueError:
            continue
    return False


def _physical_under(target: Path, project_root: Path, roots: list[str]) -> bool:
    """Return True when a resolved physical target is below any resolved policy root."""
    for root_value in roots:
        rel = _norm_rel(root_value.rstrip("/") or ".")
        policy_root = project_root if rel == "." else (project_root / rel)
        physical_root = policy_root.resolve(strict=False)
        try:
            physical_root.relative_to(project_root)
        except ValueError:
            # A policy root that itself resolves outside the project can never
            # authorize a project-contained target.
            continue
        try:
            target.relative_to(physical_root)
            return True
        except ValueError:
            continue
    return False


def _is_junction(path: Path) -> bool:
    checker = getattr(path, "is_junction", None)
    if checker is None:
        return False
    try:
        return bool(checker())
    except OSError:
        return False


def _is_reparse_point(path: Path) -> bool:
    """Best-effort Windows reparse-point detection beyond symlink/junction APIs."""
    if os.name != "nt":
        return False
    try:
        attrs = int(getattr(path.lstat(), "st_file_attributes", 0))
    except OSError:
        return False
    mask = int(getattr(statmod, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    return bool(attrs & mask)


def _alias_components(project_root: Path, rel: str) -> list[str]:
    """List declared path components that are symlink/junction aliases."""
    current = project_root
    aliases: list[str] = []
    for part in PurePosixPath(rel).parts:
        current = current / part
        try:
            if current.is_symlink() or _is_junction(current) or _is_reparse_point(current):
                aliases.append(current.relative_to(project_root).as_posix())
        except (OSError, ValueError):
            # Permission/race ambiguity is handled by later precondition checks.
            continue
    return aliases


def _physical_identity(path: Path) -> tuple[int, int]:
    stat = path.stat()
    return int(stat.st_dev), int(stat.st_ino)


def validate_read_boundary(boundary: Mapping[str, Any]) -> dict[str, Any]:
    value = dict(boundary)
    try:
        validate_instance(value, _schema("read-authorization-boundary-v1.schema.json"), base_dir=Path(__file__).with_name("schemas"))
    except SchemaValidationError as error:
        raise ContractViolation("READ_BOUNDARY_SCHEMA_INVALID", [f"$: {error}"]) from error
    if value.get("boundaryDigest") != _body_digest(value, "boundaryDigest"):
        raise ContractViolation("READ_BOUNDARY_TAMPERED", ["$.boundaryDigest: mismatch"])
    return value


def validate_write_ceiling(ceiling: Mapping[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    value = dict(ceiling)
    try:
        validate_instance(value, _schema("write-delegated-ceiling-v1.schema.json"), base_dir=Path(__file__).with_name("schemas"))
    except SchemaValidationError as error:
        raise ContractViolation("WRITE_CEILING_SCHEMA_INVALID", [f"$: {error}"]) from error
    if value.get("ceilingDigest") != _body_digest(value, "ceilingDigest"):
        raise ContractViolation("WRITE_CEILING_TAMPERED", ["$.ceilingDigest: mismatch"])
    expiry = datetime.fromisoformat(str(value["expiresAt"]).replace("Z", "+00:00"))
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    if expiry <= current:
        raise ContractViolation("WRITE_CEILING_EXPIRED", ["$.expiresAt: expired"])
    return value


def authorize_read_path(project_root: str | Path, boundary: Mapping[str, Any], relative_path: str) -> Path:
    """Authorize a read only if declared *and physical* classifications agree."""
    policy = validate_read_boundary(boundary)
    rel = _norm_rel(relative_path)
    allowed = list(policy["allowedRoots"])
    denied = list(policy.get("deniedRoots", []))
    sensitive = list(policy.get("sensitiveRoots", []))

    if not _under(rel, allowed):
        raise ContractViolation("READ_OUTSIDE_AUTHORIZED_BOUNDARY", [f"$: {rel}"])
    if _under(rel, denied) or _under(rel, sensitive):
        raise ContractViolation("READ_DENIED", [f"$: {rel}"])

    root = Path(project_root).expanduser().resolve()
    target = (root / rel).resolve()
    try:
        target.relative_to(root)
    except ValueError as error:
        raise ContractViolation("READ_PATH_ESCAPE", [f"$: {rel}"]) from error

    # The declared path may be safe while a symlink/junction resolves into a
    # denied/sensitive root. Policy is therefore applied again to physical roots.
    physical_allowed = _physical_under(target, root, allowed)
    physical_denied = _physical_under(target, root, denied) or _physical_under(target, root, sensitive)
    if not physical_allowed:
        raise ContractViolation("READ_RESOLVED_OUTSIDE_AUTHORIZED_BOUNDARY", [f"$: {rel} -> {target}"])
    if physical_denied:
        raise ContractViolation("READ_RESOLVED_TARGET_DENIED", [f"$: {rel} -> {target}"])
    return target


def authorize_write_target(
    project_root: str | Path,
    ceiling: Mapping[str, Any],
    *,
    relative_path: str,
    operation: str,
    intent: str,
    now: datetime | None = None,
) -> Path:
    """Authorize an EDIT target while rejecting filesystem alias paths.

    The Phase-1 Minimal Trust Contract Slice intentionally chooses a conservative
    rule: an EDIT target may not traverse symlink/junction/reparse aliases, and an
    existing target with multiple hard links is rejected because path-based policy
    cannot prove the other aliases remain inside the delegated ceiling.
    """
    policy = validate_write_ceiling(ceiling, now=now)
    rel = _norm_rel(relative_path)
    if operation not in set(policy["allowedOperations"]):
        raise ContractViolation("WRITE_OPERATION_NOT_AUTHORIZED", [f"$: {operation}"])
    if intent not in set(policy["allowedIntent"]):
        raise ContractViolation("WRITE_INTENT_NOT_AUTHORIZED", [f"$: {intent}"])
    allowed = list(policy["allowedWriteRoots"])
    forbidden = list(policy.get("forbiddenWriteRoots", []))
    if not _under(rel, allowed) or _under(rel, forbidden):
        raise ContractViolation("WRITE_OUTSIDE_DELEGATED_CEILING", [f"$: {rel}"])

    root = Path(project_root).expanduser().resolve()
    aliases = _alias_components(root, rel)
    if aliases:
        raise ContractViolation("WRITE_ALIAS_NOT_ALLOWED", [f"$: alias component(s): {', '.join(aliases)}"])

    declared = root / rel
    target = declared.resolve(strict=False)
    try:
        target.relative_to(root)
    except ValueError as error:
        raise ContractViolation("WRITE_PATH_ESCAPE", [f"$: {rel}"]) from error

    if not _physical_under(target, root, allowed) or _physical_under(target, root, forbidden):
        raise ContractViolation("WRITE_RESOLVED_TARGET_OUTSIDE_CEILING", [f"$: {rel} -> {target}"])

    if target.exists():
        try:
            if target.stat().st_nlink > 1:
                raise ContractViolation("WRITE_HARDLINK_NOT_ALLOWED", [f"$: {rel} has multiple physical aliases"])
        except OSError as error:
            raise ContractViolation("WRITE_TARGET_IDENTITY_UNKNOWN", [f"$: cannot stat {rel}"]) from error
    return target


def validate_write_physical_target(project_root: str | Path, relative_path: str) -> Path:
    """Re-check a previously authorized write target at receipt/reconciliation time.

    This does not grant authority. It only verifies that the declared target has
    not become an alias or escaped the project after authorization.
    """
    rel = _norm_rel(relative_path)
    root = Path(project_root).expanduser().resolve()
    aliases = _alias_components(root, rel)
    if aliases:
        raise ContractViolation("WRITE_ALIAS_NOT_ALLOWED", [f"$: alias component(s): {', '.join(aliases)}"])
    target = (root / rel).resolve(strict=False)
    try:
        target.relative_to(root)
    except ValueError as error:
        raise ContractViolation("WRITE_PATH_ESCAPE", [f"$: {rel}"]) from error
    if target.exists():
        try:
            if target.stat().st_nlink > 1:
                raise ContractViolation("WRITE_HARDLINK_NOT_ALLOWED", [f"$: {rel} has multiple physical aliases"])
        except OSError as error:
            raise ContractViolation("WRITE_TARGET_IDENTITY_UNKNOWN", [f"$: cannot stat {rel}"]) from error
    return target


def physical_target_identity(path: str | Path) -> tuple[int, int]:
    """Expose a stable local physical identity for change-set alias dedupe."""
    return _physical_identity(Path(path))


__all__ = [
    "validate_read_boundary", "validate_write_ceiling", "authorize_read_path", "authorize_write_target",
    "physical_target_identity", "validate_write_physical_target",
]
