"""Bounded product-discovery report cache; authority and sensitive source are excluded."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .contracts import digest_json

_ALLOWED_KEYS = {"projectSemanticSummary", "sourceScope", "fileHashes", "productDiscovery", "evidenceIndex", "unknowns", "questions"}
_FORBIDDEN = {"authorization", "approval", "hostAuthority", "credentials", "browserAuthority", "applyReceipt", "fullSource"}


def cache_key(*, project_fingerprint: str, source_scope: list[str], runtime_version: str, schema_version: str, input_signature: Mapping[str, Any]) -> str:
    return digest_json({"projectFingerprint": project_fingerprint, "sourceScope": source_scope, "runtimeVersion": runtime_version, "schemaVersion": schema_version, "inputSignature": dict(input_signature)})


def write_discovery_cache(path: str | Path, *, key: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    sanitized = {name: value for name, value in payload.items() if name in _ALLOWED_KEYS and name not in _FORBIDDEN}
    envelope = {"schemaVersion": "1.1", "cacheKey": key, "createdAt": datetime.now(timezone.utc).isoformat(), "payload": sanitized, "payloadDigest": digest_json(sanitized), "authority": False}
    target = Path(path).expanduser().resolve(); target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(envelope, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return envelope


def read_discovery_cache(path: str | Path, *, expected_key: str) -> dict[str, Any] | None:
    target = Path(path).expanduser().resolve()
    if not target.is_file():
        return None
    value = json.loads(target.read_text(encoding="utf-8"))
    if value.get("cacheKey") != expected_key or value.get("authority") is not False:
        return None
    payload = value.get("payload")
    if not isinstance(payload, dict) or digest_json(payload) != value.get("payloadDigest"):
        return None
    return payload


__all__ = ["cache_key", "write_discovery_cache", "read_discovery_cache"]
