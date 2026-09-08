"""Trust primitives for Agent benchmark qualification.

This module keeps benchmark controller state outside Host workspaces, seals
controller/evaluator artifacts, constrains all result writes to the controller
results directory, and fingerprints comparable Host conditions.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from .contracts import ContractViolation, digest_json


def canonical_digest(value: Mapping[str, Any]) -> str:
    return digest_json(dict(value))


def seal_object(value: Mapping[str, Any], *, field: str) -> dict[str, Any]:
    body = {k: v for k, v in dict(value).items() if k != field}
    return {**body, field: canonical_digest(body)}


def verify_sealed(value: Mapping[str, Any], *, field: str, code: str) -> str:
    expected = str(value.get(field) or "")
    body = {k: v for k, v in dict(value).items() if k != field and not str(k).endswith("Mac")}
    actual = canonical_digest(body)
    if expected != actual:
        raise ContractViolation(code, [f"{field}: digest mismatch"])
    return actual




def create_integrity_key(path: str | Path) -> bytes:
    """Create a controller-private HMAC key with owner-only permissions.

    The key is intentionally outside Host workspaces. This strengthens controller
    artifact authenticity inside the documented filesystem trust boundary; it is
    not a substitute for OS-level sandboxing against an unrestricted same-user Host.
    """
    target = Path(path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        key = target.read_bytes()
        if len(key) < 32:
            raise ContractViolation("BENCHMARK_INTEGRITY_KEY_INVALID", ["integrity key is too short"])
        return key
    key = secrets.token_bytes(32)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(target, flags, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(key)
        handle.flush()
        os.fsync(handle.fileno())
    return key


def integrity_mac(value: Mapping[str, Any], key: bytes) -> str:
    return hmac.new(key, json.dumps(dict(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"), hashlib.sha256).hexdigest()


def mac_seal_object(value: Mapping[str, Any], *, key: bytes, digest_field: str, mac_field: str) -> dict[str, Any]:
    sealed = seal_object(value, field=digest_field)
    body = {k: v for k, v in sealed.items() if k != mac_field}
    return {**body, mac_field: integrity_mac(body, key)}


def verify_mac_sealed(value: Mapping[str, Any], *, key: bytes, digest_field: str, mac_field: str, digest_code: str, mac_code: str) -> str:
    digest = verify_sealed({k: v for k, v in dict(value).items() if k != mac_field}, field=digest_field, code=digest_code)
    expected = str(value.get(mac_field) or "")
    body = {k: v for k, v in dict(value).items() if k != mac_field}
    actual = integrity_mac(body, key)
    if not expected or not hmac.compare_digest(expected, actual):
        raise ContractViolation(mac_code, [f"{mac_field}: HMAC mismatch"])
    return digest


def safe_relative(value: str, *, code: str = "BENCHMARK_PATH_INVALID") -> str:
    text = str(value).replace("\\", "/").strip()
    path = PurePosixPath(text)
    if not text or path.is_absolute() or ".." in path.parts or any(part in {"", "."} for part in path.parts):
        raise ContractViolation(code, [f"unsafe benchmark-relative path: {value!r}"])
    if len(path.parts) > 12:
        raise ContractViolation(code, ["benchmark path nesting is unreasonable"])
    return path.as_posix()


def contained_path(root: str | Path, relative: str, *, code: str = "BENCHMARK_PATH_ESCAPE") -> Path:
    base = Path(root).expanduser().resolve()
    rel = safe_relative(relative, code=code)
    target = (base / rel).resolve(strict=False)
    try:
        target.relative_to(base)
    except ValueError as error:
        raise ContractViolation(code, [f"path escapes benchmark root: {relative!r}"]) from error
    return target


def immutable_write_json(path: Path, value: Mapping[str, Any], *, code: str = "BENCHMARK_RESULT_IMMUTABLE") -> None:
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        raise ContractViolation(code, [f"artifact already exists: {path.name}"])
    payload = (json.dumps(dict(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def condition_fingerprint(host: Mapping[str, Any], conditions: Mapping[str, Any]) -> dict[str, Any]:
    body = {
        "host": {"name": str(host.get("name") or ""), "version": str(host.get("version") or ""), "model": str(host.get("model") or "")},
        "conditions": dict(conditions),
    }
    return {"digest": canonical_digest(body), **body}


def merkleish_root(rows: Mapping[str, str]) -> str:
    joined = "\n".join(f"{key}:{rows[key]}" for key in sorted(rows))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


__all__ = [
    "canonical_digest", "seal_object", "verify_sealed", "safe_relative", "contained_path",
    "immutable_write_json", "condition_fingerprint", "merkleish_root",
    "create_integrity_key", "integrity_mac", "mac_seal_object", "verify_mac_sealed",
]
