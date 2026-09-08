"""Shared artifact helpers for Agent Workflow Governance.

These helpers only write inside an ExperienceRun artifact directory. They never
write a target project and therefore cannot confer Host source-write authority.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping

from .contracts import ContractViolation, digest_json


def now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def safe_run_path(run_dir: str | Path, relative: str) -> Path:
    root = Path(run_dir).expanduser().resolve()
    rel = Path(str(relative).replace("\\", "/"))
    if rel.is_absolute() or ".." in rel.parts or not rel.parts:
        raise ContractViolation("GOVERNANCE_ARTIFACT_PATH_INVALID", [f"$: unsafe artifact path {relative!r}"])
    target = (root / rel).resolve(strict=False)
    try:
        target.relative_to(root)
    except ValueError as error:
        raise ContractViolation("GOVERNANCE_ARTIFACT_PATH_INVALID", ["$: artifact path escapes run directory"]) from error
    return target


def write_json_atomic(run_dir: str | Path, relative: str, value: Mapping[str, Any], *, replace: bool = True) -> Path:
    target = safe_run_path(run_dir, relative)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_symlink() or target.parent.is_symlink():
        raise ContractViolation("GOVERNANCE_ARTIFACT_PATH_INVALID", ["$: symlink artifact path forbidden"])
    if target.exists() and not replace:
        raise ContractViolation("GOVERNANCE_ARTIFACT_EXISTS", [f"$: artifact already exists: {relative}"])
    temp = target.with_name(target.name + ".tmp")
    data = (json.dumps(dict(value), ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n").encode("utf-8")
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(temp, flags, 0o644)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, target)
    finally:
        if temp.exists():
            try:
                temp.unlink()
            except OSError:
                pass
    return target


def read_json(run_dir: str | Path, relative: str, *, code: str = "GOVERNANCE_ARTIFACT_INVALID") -> dict[str, Any]:
    target = safe_run_path(run_dir, relative)
    if not target.is_file() or target.is_symlink():
        raise ContractViolation(code, [f"$: artifact missing: {relative}"])
    try:
        value = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ContractViolation(code, [f"$: artifact unreadable: {relative}"]) from error
    if not isinstance(value, dict):
        raise ContractViolation(code, ["$: artifact root must be an object"])
    return value


def sealed_payload(value: Mapping[str, Any], *, digest_field: str) -> dict[str, Any]:
    body = {k: v for k, v in dict(value).items() if k != digest_field}
    return {**body, digest_field: digest_json(body)}


def verify_digest(value: Mapping[str, Any], *, digest_field: str, code: str) -> str:
    expected = str(value.get(digest_field) or "")
    body = {k: v for k, v in dict(value).items() if k != digest_field}
    actual = digest_json(body)
    if expected != actual:
        raise ContractViolation(code, [f"$.{digest_field}: digest mismatch"])
    return actual
