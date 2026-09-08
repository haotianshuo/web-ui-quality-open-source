"""Fail-closed Browser network and side-effect policy for WUQ 4.2.3."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import urlsplit

from .browser_request_policy import navigation_route_key, query_digest

_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
_EMBEDDED_SCHEMES = {"data", "blob", "about"}
_DANGEROUS_ROUTE_PARTS = {"logout", "log-out", "signout", "sign-out", "delete", "remove", "revoke", "archive", "unsubscribe", "terminate", "reset", "destroy", "buy", "purchase", "confirm", "approve", "promote", "demote", "toggle-admin", "pay", "checkout"}
_AUTHENTICATED_EXACT_GET_TYPES = {"xhr", "fetch", "eventsource", "other"}


def _approval_is_current(row: Mapping[str, Any]) -> bool:
    """Only bound, purpose-limited, unexpired rules can authorize exceptions."""
    if not all(str(row.get(key) or "").strip() for key in ("purpose", "taskId", "runId", "sessionId", "expiresAt")):
        return False
    try:
        expires = datetime.fromisoformat(str(row.get("expiresAt")).replace("Z", "+00:00"))
    except ValueError:
        return False
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    return expires.astimezone(timezone.utc) > datetime.now(timezone.utc)


def origin(value: str) -> str:
    parsed = urlsplit(value)
    scheme = (parsed.scheme or "").lower()
    host = (parsed.hostname or "").lower()
    default_port = 80 if scheme == "http" else 443 if scheme == "https" else None
    authority = host
    if parsed.port is not None and parsed.port != default_port:
        authority = f"{authority}:{parsed.port}"
    return f"{scheme}://{authority}" if host else scheme


@dataclass(frozen=True, slots=True)
class FirewallDecision:
    allow: bool
    code: str
    method: str
    origin: str
    url: str
    resource_type: str

    def to_dict(self) -> dict[str, Any]:
        return {"allow": self.allow, "code": self.code, "method": self.method, "origin": self.origin, "url": self.url.split("?", 1)[0], "resourceType": self.resource_type}


class BrowserMutationFirewall:
    """Exact-origin, fail-closed browser policy.

    ``approved_requests`` is machine-readable authorization. Each row may have
    exact ``origin``, ``method`` and ``path``. A model's natural-language
    judgment never authorizes a side-effect request.
    """

    def __init__(
        self,
        allowed_origins: Iterable[str],
        *,
        allow_websocket: bool = False,
        approved_routes: Iterable[str] = (),
        approved_requests: Sequence[Mapping[str, str]] = (),
        authenticated: bool = False,
    ):
        self.allowed_origins = frozenset(origin(str(item)) for item in allowed_origins)
        self.allow_websocket = bool(allow_websocket)
        self.approved_routes = frozenset(navigation_route_key(str(item)) for item in approved_routes)
        self.rejected_approvals = [dict(item) for item in approved_requests if not _approval_is_current(item)]
        self.approved_requests = tuple(
            {
                "origin": origin(str(item.get("origin") or "")),
                "method": str(item.get("method") or "").upper(),
                "path": str(item.get("path") or ""),
                **({"queryDigest": str(item.get("queryDigest") or "").lower()} if str(item.get("queryDigest") or "").strip() else {}),
            }
            for item in approved_requests if _approval_is_current(item)
        )
        self.authenticated = bool(authenticated)
        self.decisions: list[dict[str, Any]] = []

    def _approved_side_effect(self, target_origin: str, method: str, path: str, raw_query: str = "") -> bool:
        request_digest = query_digest(raw_query) if raw_query else ""
        for row in self.approved_requests:
            if row["origin"] != target_origin or row["method"] != method or row["path"] != path:
                continue
            approved_digest = str(row.get("queryDigest") or "")
            # A request carrying business parameters is never covered by a
            # path-only authorization. Query values are compared by digest and
            # never persisted in firewall evidence.
            if request_digest or approved_digest:
                if request_digest != approved_digest:
                    continue
            return True
        return False

    def evaluate(self, *, url: str, method: str, resource_type: str) -> FirewallDecision:
        parsed = urlsplit(url)
        scheme = (parsed.scheme or "").lower()
        normalized_method = str(method or "GET").upper()
        target_origin = origin(url)
        route_path = parsed.path or "/"
        raw_query = parsed.query or ""
        navigation_key = navigation_route_key(url)
        route_parts = {part.casefold() for part in route_path.replace("_", "-").split("/") if part}
        dangerous_get = normalized_method == "GET" and bool(route_parts & _DANGEROUS_ROUTE_PARTS)
        navigation = resource_type in {"document", "navigation"}
        explicit_approval = self._approved_side_effect(target_origin, normalized_method, route_path, raw_query)
        if scheme in _EMBEDDED_SCHEMES:
            decision = FirewallDecision(True, "SAFE_EMBEDDED_RESOURCE", normalized_method, target_origin, url, resource_type)
        elif scheme not in {"http", "https", "ws", "wss"}:
            decision = FirewallDecision(False, "UNKNOWN_PROTOCOL_BLOCKED", normalized_method, target_origin, url, resource_type)
        elif resource_type == "websocket" or scheme in {"ws", "wss"}:
            ws_allowed = self.allow_websocket and target_origin in self.allowed_origins and self._approved_side_effect(target_origin, "WEBSOCKET", route_path, raw_query)
            decision = FirewallDecision(ws_allowed, "WEBSOCKET_ALLOWED" if ws_allowed else "WEBSOCKET_BLOCKED", normalized_method, target_origin, url, resource_type)
        elif target_origin not in self.allowed_origins:
            decision = FirewallDecision(False, "ORIGIN_NOT_APPROVED", normalized_method, target_origin, url, resource_type)
        elif dangerous_get and not explicit_approval:
            decision = FirewallDecision(False, "SIDE_EFFECT_ROUTE_BLOCKED", normalized_method, target_origin, url, resource_type)
        elif normalized_method not in _SAFE_METHODS and not explicit_approval:
            decision = FirewallDecision(False, "SIDE_EFFECT_BLOCKED", normalized_method, target_origin, url, resource_type)
        elif self.authenticated and normalized_method == "GET" and resource_type in _AUTHENTICATED_EXACT_GET_TYPES and not explicit_approval:
            decision = FirewallDecision(False, "AUTHENTICATED_GET_NOT_APPROVED", normalized_method, target_origin, url, resource_type)
        elif self.authenticated and navigation and not explicit_approval and navigation_key not in self.approved_routes:
            decision = FirewallDecision(False, "ROUTE_NOT_APPROVED", normalized_method, target_origin, url, resource_type)
        else:
            decision = FirewallDecision(True, "ALLOWED_EXPLICIT_REQUEST" if explicit_approval else "ALLOWED_READ", normalized_method, target_origin, url, resource_type)
        self.decisions.append(decision.to_dict())
        return decision

    def route(self, route: Any) -> None:
        request = route.request
        decision = self.evaluate(url=request.url, method=request.method, resource_type=str(request.resource_type or "unknown"))
        if decision.allow:
            route.continue_()
        else:
            route.abort("blockedbyclient")

    @property
    def mutation_attempted(self) -> bool:
        return any(item["code"] in {"SIDE_EFFECT_BLOCKED", "SIDE_EFFECT_ROUTE_BLOCKED", "AUTHENTICATED_GET_NOT_APPROVED"} for item in self.decisions)

    @property
    def network_escape_attempted(self) -> bool:
        return any(item["code"] in {"ORIGIN_NOT_APPROVED", "UNKNOWN_PROTOCOL_BLOCKED", "WEBSOCKET_BLOCKED"} for item in self.decisions)


__all__ = ["BrowserMutationFirewall", "FirewallDecision", "origin"]
