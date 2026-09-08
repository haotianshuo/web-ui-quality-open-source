"""Shared secure BrowserContext factory for every WUQ 4.2.3 browser path."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import urlsplit

from .contracts import ContractViolation
from .mutation_firewall import BrowserMutationFirewall, origin

_DEFAULT_SENSITIVE = frozenset({"authorization", "proxy-authorization", "cookie", "x-api-key", "api-key", "x-auth-token", "x-session-token", "x-csrf-token"})
_SENSITIVE_TOKENS = ("auth", "token", "secret", "credential", "session", "csrf", "cookie", "signature", "signed")
_SHARED_HEADER_ALLOWLIST = frozenset({"accept", "accept-language", "cache-control", "pragma", "user-agent", "dnt"})


def is_sensitive_header(name: str, extra: Iterable[str] = ()) -> bool:
    names = _DEFAULT_SENSITIVE | frozenset(str(x).strip().casefold() for x in extra)
    normalized = str(name).strip().casefold()
    return normalized in names or any(token in normalized for token in _SENSITIVE_TOKENS)


def split_headers(headers: Mapping[str, str] | None, *, extra_sensitive: Iterable[str] = ()) -> tuple[dict[str, str], dict[str, str]]:
    safe: dict[str, str] = {}; sensitive: dict[str, str] = {}
    for key, value in dict(headers or {}).items():
        target = sensitive if is_sensitive_header(str(key), extra_sensitive) else safe
        target[str(key)] = str(value)
    return safe, sensitive


def _origin_label(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


@dataclass(slots=True)
class SecureContextAudit:
    context: Any
    firewall: BrowserMutationFirewall
    blocked_requests: list[dict[str, Any]]
    blocked_websockets: list[dict[str, Any]]
    credential_stats: dict[str, Any]

    def report(self) -> dict[str, Any]:
        return {
            "blockedRequestCount": len(self.blocked_requests),
            "blockedWebSocketCount": len(self.blocked_websockets),
            "externalOriginsBlocked": bool(self.blocked_requests or self.blocked_websockets),
            "firewallDecisions": list(self.firewall.decisions),
            "credentials": dict(self.credential_stats),
            "processNetworkIsolation": "NOT_MEASURED",
            "claimBoundary": "Browser routing is enforced in-process; OS/process network isolation is not implied.",
        }


def build_credential_map(
    *,
    target_origin: str,
    all_primary_origins: Iterable[str],
    headers: Mapping[str, str] | None,
    explicit_by_origin: Mapping[str, Mapping[str, str]] | None = None,
    extra_sensitive: Iterable[str] = (),
) -> tuple[dict[str, str], dict[str, dict[str, str]]]:
    safe, sensitive = split_headers(headers, extra_sensitive=extra_sensitive)
    primaries = {origin(str(x)) for x in all_primary_origins}
    if sensitive and len(primaries) > 1 and not explicit_by_origin:
        raise ContractViolation("BROWSER_CREDENTIAL_SCOPE_AMBIGUOUS", ["$: sensitive headers with multiple primary origins require explicit per-origin credential mapping"])
    mapping: dict[str, dict[str, str]] = {}
    if sensitive:
        mapping[origin(target_origin)] = sensitive
    for raw_origin, raw_headers in dict(explicit_by_origin or {}).items():
        o = origin(str(raw_origin))
        _, scoped = split_headers(raw_headers, extra_sensitive=extra_sensitive)
        if len(scoped) != len(dict(raw_headers)):
            raise ContractViolation("BROWSER_CREDENTIAL_MAPPING_INVALID", [f"$: credential map for {o} may contain sensitive headers only"])
        mapping[o] = scoped
    return safe, mapping


def sanitize_headers_for_origin(headers: Mapping[str, str], request_origin: str, credentials: Mapping[str, Mapping[str, str]]) -> tuple[dict[str, str], int, int]:
    """Strip sensitive values outside the exact credential origin and inject only scoped values."""
    output = {str(k): str(v) for k, v in dict(headers).items()}
    stripped = 0
    injected = 0
    for key in list(output):
        if is_sensitive_header(key) and request_origin not in credentials:
            output.pop(key, None)
            stripped += 1
    for key, value in dict(credentials.get(request_origin, {}) or {}).items():
        output[str(key)] = str(value)
        injected += 1
    return output, stripped, injected




def _cookie_domain_matches(host: str, cookie_domain: str) -> bool:
    domain = str(cookie_domain or "").lstrip(".").casefold()
    host = str(host or "").casefold()
    return bool(domain and (host == domain or host.endswith("." + domain)))


def sanitize_storage_state(
    storage_state: str | Path | Mapping[str, Any] | None,
    *,
    credential_origins: Iterable[str],
) -> Mapping[str, Any] | None:
    """Limit Browser-managed credentials to explicitly credentialed origins.

    Cookie values and local-storage values remain opaque to reports. This helper
    only filters the caller-supplied Playwright storage-state object before it
    enters the BrowserContext.
    """
    if storage_state is None:
        return None
    allowed = {origin(str(value)) for value in credential_origins}
    if not allowed:
        raise ContractViolation("BROWSER_STORAGE_STATE_CREDENTIAL_ORIGIN_REQUIRED", ["$: storageState requires at least one explicit credential origin"])
    if isinstance(storage_state, (str, Path)):
        path = Path(storage_state).expanduser().resolve()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ContractViolation("BROWSER_STORAGE_STATE_INVALID", ["$: storageState file must be readable valid JSON"]) from error
    elif isinstance(storage_state, Mapping):
        raw = dict(storage_state)
    else:
        raise ContractViolation("BROWSER_STORAGE_STATE_INVALID", ["$: storageState must be a path or mapping"])
    hosts = {urlsplit(value).hostname or "" for value in allowed}
    cookies = [
        dict(row) for row in list(raw.get("cookies") or [])
        if isinstance(row, Mapping) and any(_cookie_domain_matches(host, str(row.get("domain") or "")) for host in hosts)
    ]
    origins = [
        dict(row) for row in list(raw.get("origins") or [])
        if isinstance(row, Mapping) and origin(str(row.get("origin") or "")) in allowed
    ]
    return {"cookies": cookies, "origins": origins}

def create_secure_context(
    browser: Any,
    *,
    context_options: Mapping[str, Any],
    allowed_origins: Iterable[str],
    credential_headers_by_origin: Mapping[str, Mapping[str, str]] | None = None,
    credential_origins: Iterable[str] = (),
    approved_requests: Sequence[Mapping[str, str]] = (),
    approved_routes: Iterable[str] = (),
    authenticated: bool = False,
    allow_websocket: bool = False,
) -> SecureContextAudit:
    allowed = {origin(str(x)) for x in allowed_origins}
    credentials = {origin(str(k)): {str(h): str(v) for h, v in dict(headers).items()} for k, headers in dict(credential_headers_by_origin or {}).items()}
    credential_scope = {origin(str(value)) for value in credential_origins} | set(credentials)
    if any(key not in allowed for key in credential_scope):
        raise ContractViolation("BROWSER_CREDENTIAL_ORIGIN_NOT_ALLOWED", ["$: every credential origin must also be network-allowed"])
    options = dict(context_options)
    if options.get("storage_state") is not None:
        options["storage_state"] = sanitize_storage_state(options.get("storage_state"), credential_origins=credential_scope)
    shared_headers = dict(options.get("extra_http_headers") or {})
    _, leaked_sensitive = split_headers(shared_headers)
    if leaked_sensitive:
        raise ContractViolation("BROWSER_CONTEXT_SENSITIVE_HEADERS_FORBIDDEN", ["$: sensitive headers must be origin-bound via credential_headers_by_origin, never BrowserContext-wide"])
    unknown_shared = [key for key in shared_headers if str(key).strip().casefold() not in _SHARED_HEADER_ALLOWLIST]
    if unknown_shared:
        raise ContractViolation("BROWSER_CONTEXT_UNKNOWN_SHARED_HEADER_FORBIDDEN", [f"$.extra_http_headers.{key}: unknown caller header must be origin-bound explicitly" for key in sorted(unknown_shared)])
    options["service_workers"] = "block"
    options["accept_downloads"] = False
    context = browser.new_context(**options)
    firewall = BrowserMutationFirewall(
        allowed,
        allow_websocket=allow_websocket,
        approved_routes=approved_routes,
        approved_requests=approved_requests,
        authenticated=authenticated,
    )
    blocked_requests: list[dict[str, Any]] = []
    blocked_websockets: list[dict[str, Any]] = []
    stats = {"used": bool(credentials), "boundOriginIds": sorted(_origin_label(x) for x in credentials), "injectedHeaderCount": 0, "strippedHeaderCount": 0, "valuesRecorded": False}

    def route_handler(route: Any) -> None:
        request = route.request
        decision = firewall.evaluate(url=request.url, method=request.method, resource_type=str(request.resource_type or "unknown"))
        if not decision.allow:
            blocked_requests.append(decision.to_dict()); route.abort("blockedbyclient"); return
        request_origin = origin(request.url) if urlsplit(request.url).hostname else urlsplit(request.url).scheme
        header_scope = credentials if request_origin in credentials else ({request_origin: {}} if request_origin in credential_scope else {})
        headers, stripped, injected = sanitize_headers_for_origin(request.headers, request_origin, header_scope)
        stats["strippedHeaderCount"] += stripped
        stats["injectedHeaderCount"] += injected
        route.continue_(headers=headers)

    context.route("**/*", route_handler)
    if hasattr(context, "route_web_socket"):
        def websocket_handler(ws: Any) -> None:
            target = str(getattr(ws, "url", ""))
            decision = firewall.evaluate(url=target, method="GET", resource_type="websocket")
            if decision.allow:
                # WUQ 4.2.3 does not grant WebSocket by default. If a caller
                # explicitly enables it, connect only under that machine policy.
                connector = getattr(ws, "connect_to_server", None)
                if callable(connector): connector()
            else:
                blocked_websockets.append(decision.to_dict())
                # Playwright blocks a routed WebSocket unless connect_to_server() is called.
                # Do not call close() inside the sync route handler; that can deadlock.
                return
        context.route_web_socket("**/*", websocket_handler)
    elif allow_websocket:
        context.close()
        raise ContractViolation("BROWSER_WEBSOCKET_CONTROL_UNAVAILABLE", ["$: WebSocket authorization requested but this Playwright lacks route_web_socket"])
    return SecureContextAudit(context=context, firewall=firewall, blocked_requests=blocked_requests, blocked_websockets=blocked_websockets, credential_stats=stats)


def chromium_launch_security_args(*, allow_no_sandbox: bool = False, outer_isolation_attested: bool = False) -> list[str]:
    """Return Chromium flags under the same fail-closed isolation policy used by browser consumers."""
    args = ["--headless"]
    if allow_no_sandbox:
        if not outer_isolation_attested:
            raise ContractViolation("BROWSER_OS_ISOLATION_REQUIRED", ["$: --no-sandbox requires explicit outer isolation attestation from the Host"] )
        args.append("--no-sandbox")
    return args


__all__ = ["SecureContextAudit", "build_credential_map", "create_secure_context", "is_sensitive_header", "sanitize_headers_for_origin", "sanitize_storage_state", "split_headers", "chromium_launch_security_args"]
