"""Explicit authentication profiles that reference Playwright storage-state files.

Profiles do not copy credentials into the project or release artifacts.  They
store only a user-level reference plus allowed origins and a content digest so
stale/replaced state is detected before Browser use.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Iterable

from .contracts import ContractViolation, digest_json, hash_file

_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")


def _store() -> Path:
    override = os.environ.get("WUQ_PROFILE_STORE")
    if override:
        root = Path(override).expanduser()
    elif os.name == "nt":
        root = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "web-ui-quality" / "auth-profiles"
    else:
        root = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state") / "web-ui-quality" / "auth-profiles"
    root.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        try: os.chmod(root, 0o700)
        except OSError: pass
    return root


def save_auth_profile(name: str, storage_state: str | Path, *, allowed_origins: Iterable[str]) -> dict[str, Any]:
    if _NAME.fullmatch(str(name)) is None:
        raise ContractViolation("AUTH_PROFILE_INVALID", ["$: profile name must be 1-64 safe characters"])
    state = Path(storage_state).expanduser().resolve()
    if not state.is_file() or state.is_symlink():
        raise ContractViolation("AUTH_PROFILE_STATE_INVALID", ["$: storage-state JSON file is required"])
    try:
        parsed = json.loads(state.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ContractViolation("AUTH_PROFILE_STATE_INVALID", ["$: storage-state must be readable JSON"]) from error
    if not isinstance(parsed, dict):
        raise ContractViolation("AUTH_PROFILE_STATE_INVALID", ["$: storage-state root must be an object"])
    payload = {
        "schemaVersion": "1",
        "name": str(name),
        "storageStatePath": str(state),
        "storageStateSha256": hash_file(state),
        "allowedOrigins": sorted({str(x) for x in allowed_origins}),
    }
    payload["profileDigest"] = digest_json(payload)
    target = _store() / f"{name}.json"
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if os.name != "nt":
        try: os.chmod(target, 0o600)
        except OSError: pass
    return {**payload, "storedAt": str(target)}


def load_auth_profile(name: str) -> dict[str, Any]:
    if _NAME.fullmatch(str(name)) is None:
        raise ContractViolation("AUTH_PROFILE_INVALID", ["$: invalid profile name"])
    path = _store() / f"{name}.json"
    if not path.is_file() or path.is_symlink():
        raise ContractViolation("AUTH_PROFILE_MISSING", [f"$: authentication profile {name!r} does not exist"])
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ContractViolation("AUTH_PROFILE_INVALID", ["$: profile is unreadable"]) from error
    stored_digest = payload.get("profileDigest")
    body = {k: v for k, v in payload.items() if k != "profileDigest"}
    if digest_json(body) != stored_digest:
        raise ContractViolation("AUTH_PROFILE_TAMPERED", ["$: authentication profile metadata changed"])
    state = Path(str(payload.get("storageStatePath") or "")).expanduser().resolve()
    if not state.is_file() or state.is_symlink() or hash_file(state) != payload.get("storageStateSha256"):
        raise ContractViolation("AUTH_PROFILE_STALE", ["$: referenced storage-state is missing or changed; re-import the profile"])
    return payload


__all__ = ["save_auth_profile", "load_auth_profile"]
