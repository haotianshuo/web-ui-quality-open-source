"""Bound, expiring machine authorization for Browser request exceptions.

Natural-language intent never authorizes network side effects.  Public task
flows bind exact request rules to the immutable task/run/session identity and
seal the resulting policy into RunConditions for Before/After comparability.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import re
from typing import Any, Mapping, Sequence
from urllib.parse import parse_qsl, urlencode, urlsplit

from .contracts import ContractViolation, digest_json

_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "POST", "PUT", "PATCH", "DELETE", "WEBSOCKET"})
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _now(value: datetime | None = None) -> datetime:
    current = value or datetime.now(timezone.utc)
    return current if current.tzinfo is not None else current.replace(tzinfo=timezone.utc)


def _parse_time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as error:
        raise ContractViolation("BROWSER_REQUEST_APPROVAL_INVALID", ["$.expiresAt: valid ISO-8601 timestamp required"]) from error
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def query_digest(raw_query: str) -> str:
    """Return a privacy-preserving digest of a normalized query string.

    Query values are canonicalized in-memory and immediately hashed; the
    approval object never persists the raw query or its values.
    """
    pairs = parse_qsl(str(raw_query or ""), keep_blank_values=True)
    canonical = urlencode(pairs, doseq=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def navigation_route_key(value: str) -> str:
    """Return a query-aware, privacy-preserving key for document navigation.

    Query values are never persisted. Query-bearing routes are represented by
    the normalized path plus a SHA-256 digest, so a path-only authorization
    cannot silently authorize a different business action encoded in Query.
    """
    parsed = urlsplit(str(value or ""))
    path = parsed.path or "/"
    return f"{path}#query-sha256:{query_digest(parsed.query)}" if parsed.query else path


def _rule(row: Mapping[str, Any]) -> dict[str, str]:
    raw_origin = str(row.get("origin") or "").strip()
    parsed = urlsplit(raw_origin)
    if parsed.scheme not in {"http", "https", "ws", "wss"} or not parsed.hostname:
        raise ContractViolation("BROWSER_REQUEST_APPROVAL_INVALID", ["$.origin: exact http/https/ws/wss origin required"])
    default_port = 80 if parsed.scheme in {"http", "ws"} else 443
    origin = f"{parsed.scheme}://{parsed.hostname.lower()}"
    if parsed.port is not None and parsed.port != default_port:
        origin += f":{parsed.port}"
    method = str(row.get("method") or "").strip().upper()
    if method not in _METHODS:
        raise ContractViolation("BROWSER_REQUEST_APPROVAL_INVALID", [f"$.method: unsupported exact method {method!r}"])
    raw_path = str(row.get("path") or "").strip()
    if not raw_path.startswith("/") or "*" in raw_path:
        raise ContractViolation("BROWSER_REQUEST_APPROVAL_INVALID", ["$.path: exact absolute path without wildcards required"])
    split_path = urlsplit(raw_path)
    path = split_path.path or "/"
    supplied_digest = str(row.get("queryDigest") or "").strip().lower()
    if supplied_digest and not _SHA256_RE.fullmatch(supplied_digest):
        raise ContractViolation("BROWSER_REQUEST_APPROVAL_INVALID", ["$.queryDigest: 64 lowercase hex characters required"])
    path_digest = query_digest(split_path.query) if split_path.query else ""
    if supplied_digest and path_digest and supplied_digest != path_digest:
        raise ContractViolation("BROWSER_REQUEST_APPROVAL_INVALID", ["$.queryDigest: does not match the query encoded in $.path"])
    digest = supplied_digest or path_digest
    rule = {"origin": origin, "method": method, "path": path}
    if digest:
        rule["queryDigest"] = digest
    return rule


def bind_approved_requests(
    rows: Sequence[Mapping[str, Any]],
    *,
    task_id: str,
    run_id: str,
    session_id: str,
    purpose: str = "user-confirmed-browser-request",
    ttl_seconds: int = 900,
    now: datetime | None = None,
) -> tuple[dict[str, str], ...]:
    if ttl_seconds <= 0 or ttl_seconds > 3600:
        raise ContractViolation("BROWSER_REQUEST_APPROVAL_INVALID", ["$.ttl: approval expiry must be within 1..3600 seconds"])
    for name, value in {"taskId": task_id, "runId": run_id, "sessionId": session_id, "purpose": purpose}.items():
        if not str(value or "").strip():
            raise ContractViolation("BROWSER_REQUEST_APPROVAL_INVALID", [f"$.{name}: non-empty binding required"])
    issued = _now(now)
    expires = issued + timedelta(seconds=ttl_seconds)
    bound: list[dict[str, str]] = []
    for raw in rows:
        rule = _rule(raw)
        bound.append({
            **rule,
            "purpose": purpose,
            "taskId": task_id,
            "runId": run_id,
            "sessionId": session_id,
            "issuedAt": issued.isoformat(),
            "expiresAt": expires.isoformat(),
        })
    return tuple(bound)


def validate_bound_approved_requests(
    rows: Sequence[Mapping[str, Any]],
    *,
    task_id: str,
    run_id: str,
    session_id: str,
    now: datetime | None = None,
) -> tuple[dict[str, str], ...]:
    current = _now(now)
    normalized: list[dict[str, str]] = []
    for raw in rows:
        rule = _rule(raw)
        for key, expected in {"taskId": task_id, "runId": run_id, "sessionId": session_id}.items():
            if str(raw.get(key) or "") != expected:
                raise ContractViolation("BROWSER_REQUEST_APPROVAL_BINDING_MISMATCH", [f"$.{key}: approval belongs to another task/run/session"])
        purpose = str(raw.get("purpose") or "").strip()
        if not purpose:
            raise ContractViolation("BROWSER_REQUEST_APPROVAL_INVALID", ["$.purpose: approval purpose is required"])
        expires_at = str(raw.get("expiresAt") or "")
        if _parse_time(expires_at) <= current:
            raise ContractViolation("BROWSER_REQUEST_APPROVAL_EXPIRED", ["$.expiresAt: Browser request approval has expired"])
        issued_at = str(raw.get("issuedAt") or "")
        _parse_time(issued_at)
        normalized.append({
            **rule,
            "purpose": purpose,
            "taskId": task_id,
            "runId": run_id,
            "sessionId": session_id,
            "issuedAt": issued_at,
            "expiresAt": expires_at,
        })
    return tuple(normalized)


def request_rule_digest(rows: Sequence[Mapping[str, Any]]) -> str:
    """Digest only the exact route rules, for caller-vs-sealed-policy comparison."""
    return digest_json([_rule(row) for row in rows])


def request_policy_digest(rows: Sequence[Mapping[str, Any]]) -> str:
    return digest_json([dict(row) for row in rows])


__all__ = [
    "bind_approved_requests",
    "validate_bound_approved_requests",
    "request_rule_digest",
    "request_policy_digest",
    "query_digest",
    "navigation_route_key",
]