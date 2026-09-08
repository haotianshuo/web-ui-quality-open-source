"""Fail-closed Browser Standard contracts for trusted host-collected evidence.

The runtime never controls a browser.  Public digests prove deterministic
consistency only; Standard authority additionally requires an in-memory host
receipt that cannot be reconstructed from report JSON.
"""

from __future__ import annotations

import copy
import json
import re
import struct
import zlib
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Iterable, Mapping, Sequence
from urllib.parse import unquote, urlsplit

from .contracts import ContractViolation, canonical_json, digest_json, sha256_hex


ENVIRONMENTS = {"local", "test", "staging", "production"}
RESULTS = {"PASS", "NOT_VERIFIED"}
SAFE_ACTIONS = {"safe_read_only", "local_ui_state"}
WRITE_ACTIONS = {"submit", "upload", "approval", "message", "state_write"}
HIGH_RISK_ACTIONS = {"payment", "publish", "delete", "account_change"}
ALLOWED_METHODS = {"GET", "HEAD"}
ALLOWED_RESOURCE_TYPES = {"document", "stylesheet", "script", "fetch", "xhr", "image", "font", "other"}
EXPECTED_BROWSER = {
    "surface": "codex_in_app_browser",
    "browserName": "Codex In-app Browser",
    "browserType": "iab",
    "engine": "Chromium",
    "isolationKind": "task_context",
}
EXPECTED_VIEWPORTS = ((375, 812), (768, 1024), (1440, 900))
REQUIRED_GEOMETRY_IDS = {
    "app-header", "evidence-panel", "task-search", "load-status", "simulate-failure", "status-region"
}
REQUIRED_INTERACTIONS = {
    ("menu-toggle", "click"): ("expanded:true", "expanded:false"),
    ("task-search", "fill"): ("filtered:1",),
    ("load-status", "click"): ("loading", "success"),
    ("simulate-failure", "click"): ("loading", "error"),
}
REQUIRED_PROBE_FLAGS = {
    "pageAccess",
    "viewportAndDpr",
    "domGeometry",
    "click",
    "input",
    "screenshot",
    "console",
    "networkFailure",
    "isolatedContext",
    "networkRedaction",
    "screenshotRedaction",
    "sideEffectClassification",
}
FIXED_DOWNLOAD_DIRECTORY = "web-ui-quality/.browser-test-workspace/downloads"
NETWORK_GUARD_MODES = {"controlled_loopback_manifest", "unavailable"}
SENSITIVE_MARKER = "BROWSER_SENSITIVE_FIXTURE_DO_NOT_CAPTURE"
SENSITIVE_SERIALIZED_RE = re.compile(
    r"(?ix)(?:"
    r"bearer\s+[a-z0-9._~+/-]{8,}|"
    r"(?:authorization|cookie|password|passwd|api[_-]?key|access[_-]?token|secret)\s*(?:=|:)\s*[^\s,;]{6,}|"
    r"[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}|"
    r"(?<!\d)1[3-9]\d{9}(?!\d)"
    r")"
)
SAFE_REF_RE = re.compile(r"^[A-Za-z0-9._:/-]{1,160}$")
WITNESS_RECEIPT_RE = re.compile(r"^[0-9a-f]{64}$")
WITNESS_WINDOW_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
CONTROLLED_FIXTURE_HASHES = {
    "index.html": "94e611481382ac17c409235651c0e90641b315d6d70ac404137400cbd05b6c0d",
    "styles.css": "5a7f6603d7a2c86aa66e0d1d02f3ce8cff4a497a701e356476412e125b50f698",
    "app.js": "a8a0065abea4a5da5d4409e944e50129d39feb1d09e6fa433cd91a781dc2b0d1",
    "server.py": "0612e3eaba7a1607aeb2128d14eeb79509ae27a0491a02fd8b10911864bdcc05",
}
CONTROLLED_AUTOMATIC_TARGETS = ["/", "/api/fail", "/app.js", "/app.js", "/styles.css", "/styles.css"]
SENSITIVE_SAFE_CODES = {
    "bearer": "AUTH_BEARER_REDACTED",
    "email": "EMAIL_REDACTED",
    "phone": "PHONE_REDACTED",
    "id": "ID_REDACTED",
    "marker": "FIXTURE_MARKER_REDACTED",
    "password": "PASSWORD_REDACTED",
}
ID_NUMBER_RE = re.compile(r"(?<!\d)\d{17}[0-9Xx](?!\d)")
_TRUSTED_BROWSER_AUTHORITY = object()
_CONSUMED_RUN_IDS: set[str] = set()


def _safe_error(code: str, message: str) -> ContractViolation:
    return ContractViolation(code, [message])


class _NonSerializable:
    def __reduce__(self) -> Any:
        raise TypeError("trusted Browser contexts are not serializable")

    def __reduce_ex__(self, protocol: int) -> Any:
        raise TypeError("trusted Browser contexts are not serializable")

    def __getstate__(self) -> Any:
        raise TypeError("trusted Browser contexts are not serializable")


@dataclass(frozen=True, slots=True)
class TrustedBrowserAuthorizationContext(_NonSerializable):
    """Host-resolved task/current-conversation authorization for one contract."""

    task_id: str
    plane: str
    evidence_ref: str
    approved_contract_digest: str
    environment_class: str
    role: str
    approved_origins: tuple[str, ...]
    approved_routes: tuple[str, ...]
    side_effect_policy: str
    _authority: object = field(repr=False, compare=False)


@dataclass(frozen=True, slots=True)
class TrustedBrowserEvidenceReceipt(_NonSerializable):
    """In-memory binding of normalized host evidence to one Browser contract."""

    task_id: str
    contract_digest: str
    evidence_ref: str
    evidence_digest: str
    session_binding_digest: str
    result: str
    error_code: str | None
    _contract_json: str = field(repr=False, compare=False)
    _evidence_json: str = field(repr=False, compare=False)
    _authority: object = field(repr=False, compare=False)


@dataclass(slots=True)
class BrowserRunGuard(_NonSerializable):
    """Process-local lifecycle guard; consistency control, not host authority."""

    run_id: str
    evidence_ref: str
    finalized: bool
    browser_action_count: int
    last_browser_action: str | None
    browser_actions_after_finalize: int
    _authority: object = field(repr=False)


@dataclass(slots=True)
class BrowserActionPermit(_NonSerializable):
    """One-shot pre-action DOM permit bound to an active task run."""

    run_id: str
    operation: str
    action_kind: str
    target_snapshot_digest: str
    consumed: bool
    _authority: object = field(repr=False)


def _validated_task_id(value: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[A-Z0-9][A-Z0-9._:-]{2,95}", value) is None:
        raise _safe_error("BROWSER_CONTRACT_INVALID", "$.taskId: invalid")
    return value


def _validated_ref(value: str, *, code: str) -> str:
    if not isinstance(value, str) or SAFE_REF_RE.fullmatch(value) is None or SENSITIVE_SERIALIZED_RE.search(value):
        raise _safe_error(code, "$: trusted evidence reference is invalid")
    return value


def _normalize_origin(raw: str, *, approved_value: bool = False) -> str:
    if not isinstance(raw, str):
        raise _safe_error("BROWSER_CONTRACT_INVALID", "$.approvedOrigins: expected string")
    parsed = urlsplit(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise _safe_error("BROWSER_CONTRACT_INVALID", "$.approvedOrigins: invalid HTTP(S) origin")
    if approved_value and (parsed.path not in {"", "/"} or parsed.query or parsed.fragment):
        raise _safe_error("BROWSER_CONTRACT_INVALID", "$.approvedOrigins: expected origin without path/query/fragment")
    host = parsed.hostname.lower()
    try:
        port = parsed.port
    except ValueError as error:
        raise _safe_error("BROWSER_CONTRACT_INVALID", "$.approvedOrigins: invalid port") from error
    default = 80 if parsed.scheme == "http" else 443
    authority = host if port in {None, default} else f"{host}:{port}"
    return f"{parsed.scheme.lower()}://{authority}"


def _normalize_route(raw: str) -> str:
    if not isinstance(raw, str) or not raw.startswith("/") or "?" in raw or "#" in raw or "\\" in raw:
        raise _safe_error("BROWSER_CONTRACT_INVALID", "$.approvedRoutes: unsafe route")
    decoded = unquote(raw)
    if "\\" in decoded or not decoded.startswith("/"):
        raise _safe_error("BROWSER_CONTRACT_INVALID", "$.approvedRoutes: unsafe encoded route")
    pure = PurePosixPath(decoded)
    normalized = pure.as_posix() if decoded != "/" else "/"
    if ".." in pure.parts or normalized != decoded:
        raise _safe_error("BROWSER_CONTRACT_INVALID", "$.approvedRoutes: route must be exact and normalized")
    return normalized


def _normalize_string_list(value: Sequence[str], path: str, *, non_empty: bool = True) -> list[str]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise _safe_error("BROWSER_CONTRACT_INVALID", f"{path}: expected string array")
    result = list(value)
    if (non_empty and not result) or any(not isinstance(item, str) or not item for item in result):
        raise _safe_error("BROWSER_CONTRACT_INVALID", f"{path}: invalid string array")
    if len(result) != len(set(result)):
        raise _safe_error("BROWSER_CONTRACT_INVALID", f"{path}: duplicate value")
    return result


def _contract_payload(
    *,
    task_id: str,
    plane: str,
    environment_class: str,
    approved_origins: Sequence[str],
    approved_routes: Sequence[str],
    role: str,
    screenshot_redaction_selectors: Sequence[str],
    download_directory: str,
    network_guard_mode: str,
) -> dict[str, Any]:
    task = _validated_task_id(task_id)
    if plane not in {"build", "runtime"}:
        raise _safe_error("BROWSER_CONTRACT_INVALID", "$.plane: expected build or runtime")
    if environment_class not in ENVIRONMENTS:
        raise _safe_error("BROWSER_ENVIRONMENT_UNVERIFIED", "$.environmentClass: unsupported")
    origins = [_normalize_origin(item, approved_value=True) for item in approved_origins]
    routes = [_normalize_route(item) for item in approved_routes]
    if not origins or len(origins) != len(set(origins)) or not routes or len(routes) != len(set(routes)):
        raise _safe_error("BROWSER_CONTRACT_INVALID", "$: approved Origins/routes must be explicit and unique")
    if not isinstance(role, str) or not role.strip():
        raise _safe_error("BROWSER_CONTRACT_INVALID", "$.role: required")
    if network_guard_mode not in NETWORK_GUARD_MODES:
        raise _safe_error("BROWSER_CONTRACT_INVALID", "$.networkGuardMode: invalid")
    if network_guard_mode == "controlled_loopback_manifest":
        if plane != "build" or environment_class != "local" or any(
            urlsplit(origin).scheme != "http" or urlsplit(origin).hostname != "127.0.0.1" for origin in origins
        ):
            raise _safe_error("BROWSER_CONTRACT_INVALID", "$: controlled manifest mode is loopback Build Plane only")
    selectors = _normalize_string_list(screenshot_redaction_selectors, "$.screenshotRedactionSelectors")
    if download_directory != FIXED_DOWNLOAD_DIRECTORY or ".." in PurePosixPath(download_directory).parts or "\\" in download_directory:
        raise _safe_error("BROWSER_DOWNLOAD_PATH_INVALID", "$.downloadDirectory: Browser v0.3.0 uses one blocked task root")
    return {
        "schemaVersion": "2",
        "taskId": task,
        "plane": plane,
        "environmentClass": environment_class,
        "role": role.strip(),
        "approvedOrigins": origins,
        "approvedRoutes": routes,
        "originApprovalSource": "trusted_host_build_task" if plane == "build" else "trusted_host_current_conversation",
        "productionReadOnly": True,
        "sideEffectPolicy": "read_only",
        "expectedBrowser": copy.deepcopy(EXPECTED_BROWSER),
        "requiredEvidence": {
            "viewports": [{"width": width, "height": height} for width, height in EXPECTED_VIEWPORTS],
            "screenshotPairs": [
                {"viewport": {"width": width, "height": height}, "label": label}
                for width, height in EXPECTED_VIEWPORTS
                for label in ("before", "after")
            ],
            "interactionTargets": [target for target, _ in REQUIRED_INTERACTIONS],
            "requiredNetworkCases": [{"method": "GET", "route": "/api/fail", "status": 503}],
            "expectedFinalRoute": "/",
        },
        "requiredSensitiveSelectorsByRoute": {"/": selectors},
        "networkEvidenceMode": "metadata_enum_only",
        "networkGuardMode": network_guard_mode,
        "downloadPolicy": "block",
        "downloadDirectory": download_directory,
        "digestPurpose": "consistency_only",
    }


def _resolve_host_evidence(reference: str, resolver: Callable[[str], bool], *, code: str) -> None:
    if not callable(resolver):
        raise _safe_error(code, "$: trusted host evidence resolver is required")
    try:
        resolved = resolver(reference)
    except Exception as error:
        raise _safe_error(code, "$: trusted host evidence could not be resolved safely") from error
    if resolved is not True:
        raise _safe_error(code, "$: trusted host evidence is not verified")


def create_browser_run_guard(
    *, run_id: str, evidence_ref: str, evidence_resolver: Callable[[str], bool]
) -> BrowserRunGuard:
    run = _validated_ref(run_id, code="BROWSER_REPORT_INVALID")
    reference = _validated_ref(evidence_ref, code="HOST_TOOL_EVIDENCE_UNAVAILABLE")
    _resolve_host_evidence(reference, evidence_resolver, code="HOST_TOOL_EVIDENCE_UNAVAILABLE")
    if run in _CONSUMED_RUN_IDS:
        raise _safe_error("BROWSER_EVIDENCE_REPLAYED", "$: Browser run was already consumed")
    return BrowserRunGuard(
        run_id=run,
        evidence_ref=reference,
        finalized=False,
        browser_action_count=0,
        last_browser_action=None,
        browser_actions_after_finalize=0,
        _authority=_TRUSTED_BROWSER_AUTHORITY,
    )


def require_browser_run_active(guard: BrowserRunGuard | None) -> BrowserRunGuard:
    if not isinstance(guard, BrowserRunGuard) or guard._authority is not _TRUSTED_BROWSER_AUTHORITY:
        raise _safe_error("HOST_TOOL_EVIDENCE_UNAVAILABLE", "$: process-local Browser run guard is required")
    if guard.finalized:
        raise _safe_error("BROWSER_SESSION_FINALIZED", "$: Browser run is already finalized")
    return guard


def finalize_browser_run(guard: BrowserRunGuard | None, cleanup: Mapping[str, Any]) -> BrowserRunGuard:
    active = require_browser_run_active(guard)
    validate_cleanup(cleanup)
    active.finalized = True
    return active


def record_browser_action(guard: BrowserRunGuard | None, action_name: str) -> BrowserRunGuard:
    """Record host action ordering for candidate consistency; tool records remain authoritative."""

    if not isinstance(guard, BrowserRunGuard) or guard._authority is not _TRUSTED_BROWSER_AUTHORITY:
        raise _safe_error("HOST_TOOL_EVIDENCE_UNAVAILABLE", "$: Browser run guard is required")
    action = _validated_ref(action_name, code="BROWSER_REPORT_INVALID")
    if guard.finalized:
        guard.browser_actions_after_finalize += 1
        raise _safe_error("BROWSER_SESSION_FINALIZED", "$: Browser action attempted after finalization")
    guard.browser_action_count += 1
    guard.last_browser_action = action
    return guard


def bind_trusted_browser_authorization(
    *,
    task_id: str,
    plane: str,
    environment_class: str,
    approved_origins: Sequence[str],
    approved_routes: Sequence[str],
    role: str,
    evidence_ref: str,
    evidence_resolver: Callable[[str], bool],
    side_effect_policy: str = "read_only",
    screenshot_redaction_selectors: Sequence[str] = ("[data-sensitive]",),
    download_directory: str = FIXED_DOWNLOAD_DIRECTORY,
    network_guard_mode: str = "controlled_loopback_manifest",
) -> TrustedBrowserAuthorizationContext:
    if side_effect_policy != "read_only":
        raise _safe_error("BROWSER_SIDE_EFFECT_POLICY_UNSUPPORTED", "$: Browser Standard v0.3.0 is read-only")
    payload = _contract_payload(
        task_id=task_id,
        plane=plane,
        environment_class=environment_class,
        approved_origins=approved_origins,
        approved_routes=approved_routes,
        role=role,
        screenshot_redaction_selectors=screenshot_redaction_selectors,
        download_directory=download_directory,
        network_guard_mode=network_guard_mode,
    )
    reference = _validated_ref(evidence_ref, code="TRUSTED_ORIGIN_APPROVAL_REQUIRED")
    _resolve_host_evidence(reference, evidence_resolver, code="TRUSTED_ORIGIN_APPROVAL_REQUIRED")
    return TrustedBrowserAuthorizationContext(
        task_id=payload["taskId"],
        plane=payload["plane"],
        evidence_ref=reference,
        approved_contract_digest=digest_json(payload),
        environment_class=payload["environmentClass"],
        role=payload["role"],
        approved_origins=tuple(payload["approvedOrigins"]),
        approved_routes=tuple(payload["approvedRoutes"]),
        side_effect_policy="read_only",
        _authority=_TRUSTED_BROWSER_AUTHORITY,
    )


def _require_authorization(context: TrustedBrowserAuthorizationContext | None) -> TrustedBrowserAuthorizationContext:
    if not isinstance(context, TrustedBrowserAuthorizationContext) or context._authority is not _TRUSTED_BROWSER_AUTHORITY:
        raise _safe_error(
            "TRUSTED_ORIGIN_APPROVAL_REQUIRED",
            "$: host-resolved Origin approval context is required",
        )
    return context


def create_browser_contract(
    *,
    plane: str,
    environment_class: str,
    approved_origins: Sequence[str],
    approved_routes: Sequence[str],
    role: str,
    authorization_context: TrustedBrowserAuthorizationContext | None = None,
    task_id: str = "BUILD-BROWSER-STANDARD-001",
    side_effect_policy: str = "read_only",
    screenshot_redaction_selectors: Sequence[str] = ("[data-sensitive]",),
    download_directory: str = FIXED_DOWNLOAD_DIRECTORY,
    network_guard_mode: str = "controlled_loopback_manifest",
    **legacy: Any,
) -> dict[str, Any]:
    if legacy:
        raise _safe_error("BROWSER_CONTRACT_INVALID", f"$: unsupported fields {sorted(legacy)}")
    if side_effect_policy != "read_only":
        raise _safe_error("BROWSER_SIDE_EFFECT_POLICY_UNSUPPORTED", "$: Browser Standard v0.3.0 is read-only")
    context = _require_authorization(authorization_context)
    payload = _contract_payload(
        task_id=task_id,
        plane=plane,
        environment_class=environment_class,
        approved_origins=approved_origins,
        approved_routes=approved_routes,
        role=role,
        screenshot_redaction_selectors=screenshot_redaction_selectors,
        download_directory=download_directory,
        network_guard_mode=network_guard_mode,
    )
    actual_digest = digest_json(payload)
    if (
        context.task_id != payload["taskId"]
        or context.plane != payload["plane"]
        or context.approved_contract_digest != actual_digest
        or context.environment_class != payload["environmentClass"]
        or context.role != payload["role"]
        or list(context.approved_origins) != payload["approvedOrigins"]
        or list(context.approved_routes) != payload["approvedRoutes"]
        or context.side_effect_policy != "read_only"
    ):
        raise _safe_error("BROWSER_APPROVAL_BINDING_MISMATCH", "$: approval is bound to another Browser contract")
    contract = copy.deepcopy(payload)
    contract["approvalEvidenceRef"] = context.evidence_ref
    contract["contractDigest"] = digest_json(contract)
    validate_browser_contract(contract)
    return contract


def validate_browser_contract(contract: Mapping[str, Any]) -> dict[str, Any]:
    required = {
        "schemaVersion", "taskId", "plane", "environmentClass", "role", "approvedOrigins", "approvedRoutes",
        "originApprovalSource", "approvalEvidenceRef", "productionReadOnly", "sideEffectPolicy", "expectedBrowser",
        "requiredEvidence", "requiredSensitiveSelectorsByRoute", "networkEvidenceMode", "downloadPolicy",
        "networkGuardMode", "downloadDirectory", "digestPurpose", "contractDigest",
    }
    if not isinstance(contract, Mapping) or set(contract) != required:
        raise _safe_error("BROWSER_CONTRACT_INVALID", "$: invalid Browser contract field set")
    if contract.get("schemaVersion") != "2" or contract.get("plane") not in {"build", "runtime"}:
        raise _safe_error("BROWSER_CONTRACT_INVALID", "$: invalid Browser contract header")
    _validated_task_id(contract.get("taskId"))
    _validated_ref(contract.get("approvalEvidenceRef"), code="BROWSER_CONTRACT_INVALID")
    if contract.get("environmentClass") not in ENVIRONMENTS or contract.get("productionReadOnly") is not True:
        raise _safe_error("BROWSER_CONTRACT_INVALID", "$: invalid environment/production policy")
    if contract.get("sideEffectPolicy") != "read_only" or contract.get("downloadPolicy") != "block":
        raise _safe_error("BROWSER_SIDE_EFFECT_POLICY_UNSUPPORTED", "$: Browser Standard v0.3.0 is read-only")
    expected_source = "trusted_host_build_task" if contract["plane"] == "build" else "trusted_host_current_conversation"
    if contract.get("originApprovalSource") != expected_source:
        raise _safe_error("BROWSER_CONTRACT_INVALID", "$.originApprovalSource: invalid")
    origins = _normalize_string_list(contract.get("approvedOrigins"), "$.approvedOrigins")
    routes = _normalize_string_list(contract.get("approvedRoutes"), "$.approvedRoutes")
    if origins != [_normalize_origin(item, approved_value=True) for item in origins]:
        raise _safe_error("BROWSER_CONTRACT_INVALID", "$.approvedOrigins: not normalized")
    if routes != [_normalize_route(item) for item in routes]:
        raise _safe_error("BROWSER_CONTRACT_INVALID", "$.approvedRoutes: not normalized")
    if contract.get("expectedBrowser") != EXPECTED_BROWSER:
        raise _safe_error("BROWSER_CONTRACT_INVALID", "$.expectedBrowser: unsupported Browser/engine")
    expected_required = {
        "viewports": [{"width": width, "height": height} for width, height in EXPECTED_VIEWPORTS],
        "screenshotPairs": [
            {"viewport": {"width": width, "height": height}, "label": label}
            for width, height in EXPECTED_VIEWPORTS
            for label in ("before", "after")
        ],
        "interactionTargets": [target for target, _ in REQUIRED_INTERACTIONS],
        "requiredNetworkCases": [{"method": "GET", "route": "/api/fail", "status": 503}],
        "expectedFinalRoute": "/",
    }
    if contract.get("requiredEvidence") != expected_required:
        raise _safe_error("BROWSER_CONTRACT_INVALID", "$.requiredEvidence: invalid")
    selector_map = contract.get("requiredSensitiveSelectorsByRoute")
    if not isinstance(selector_map, dict) or set(selector_map) != {"/"}:
        raise _safe_error("BROWSER_CONTRACT_INVALID", "$.requiredSensitiveSelectorsByRoute: invalid")
    _normalize_string_list(selector_map["/"], "$.requiredSensitiveSelectorsByRoute./")
    if contract.get("networkEvidenceMode") != "metadata_enum_only" or contract.get("digestPurpose") != "consistency_only":
        raise _safe_error("BROWSER_CONTRACT_INVALID", "$: unsafe evidence/digest mode")
    if contract.get("networkGuardMode") not in NETWORK_GUARD_MODES:
        raise _safe_error("BROWSER_CONTRACT_INVALID", "$.networkGuardMode: invalid")
    if contract["networkGuardMode"] == "controlled_loopback_manifest" and (
        contract["plane"] != "build"
        or contract["environmentClass"] != "local"
        or any(urlsplit(origin).scheme != "http" or urlsplit(origin).hostname != "127.0.0.1" for origin in origins)
    ):
        raise _safe_error("BROWSER_CONTRACT_INVALID", "$: controlled manifest mode is loopback Build Plane only")
    if contract.get("downloadDirectory") != FIXED_DOWNLOAD_DIRECTORY:
        raise _safe_error("BROWSER_DOWNLOAD_PATH_INVALID", "$.downloadDirectory: invalid")
    digest_input = {key: copy.deepcopy(value) for key, value in contract.items() if key != "contractDigest"}
    if contract.get("contractDigest") != digest_json(digest_input):
        raise _safe_error("BROWSER_CONTRACT_INVALID", "$.contractDigest: mismatch")
    return copy.deepcopy(dict(contract))


def browser_session_binding_digest(raw_probe: Mapping[str, Any]) -> str:
    required = {"runId", "sessionId", "contextId", "tabId", "contextEvidenceRef"}
    if not isinstance(raw_probe, Mapping) or not required <= set(raw_probe):
        raise _safe_error("BROWSER_REPORT_INVALID", "$: session binding fields are incomplete")
    for key in required:
        _validated_ref(raw_probe[key], code="BROWSER_REPORT_INVALID")
    return digest_json({key: raw_probe[key] for key in ("runId", "sessionId", "contextId", "tabId", "contextEvidenceRef")})


def _require_run_binding(value: Mapping[str, Any], expected: str, path: str) -> None:
    if value.get("runBindingDigest") != expected:
        raise _safe_error("BROWSER_EVIDENCE_REPLAYED", f"{path}.runBindingDigest: evidence belongs to another run")


def evaluate_capability_probe(
    contract: Mapping[str, Any],
    raw_probe: Mapping[str, Any],
    *,
    evidence_resolver: Callable[[str], bool] | None = None,
) -> dict[str, Any]:
    validate_browser_contract(contract)
    required = {
        "runId", "sessionId", "contextId", "tabId", "contextEvidenceRef", "browserName", "browserType", "engine",
        "isolationKind", "tabOwnedByTask", "initialControlledTabs", "personalProfileUsed", "userTabClaimed",
        "historyRead", "cookiesRead", "storageRead", "features",
    }
    if not isinstance(raw_probe, Mapping) or set(raw_probe) != required:
        raise _safe_error("BROWSER_REPORT_INVALID", "$.capabilityProbe: invalid field set")
    for key in ("runId", "sessionId", "contextId", "tabId", "contextEvidenceRef"):
        _validated_ref(raw_probe[key], code="BROWSER_REPORT_INVALID")
    if raw_probe["tabOwnedByTask"] is not True or not isinstance(raw_probe["initialControlledTabs"], int):
        raise _safe_error("BROWSER_CONTEXT_NOT_CLEAN", "$: tab ownership/count is not trusted")
    if raw_probe["initialControlledTabs"] != 0:
        raise _safe_error("BROWSER_CONTEXT_NOT_CLEAN", "$: controlled tab set was not empty at task start")
    for key in ("personalProfileUsed", "userTabClaimed", "historyRead", "cookiesRead", "storageRead"):
        if raw_probe[key] is not False:
            raise _safe_error("PERSONAL_PROFILE_FORBIDDEN", f"$: {key} must be explicitly false")
    flags = raw_probe["features"]
    if not isinstance(flags, dict) or set(flags) != REQUIRED_PROBE_FLAGS or any(not isinstance(item, bool) for item in flags.values()):
        raise _safe_error("BROWSER_REPORT_INVALID", "$.capabilityProbe.features: invalid field set")
    session_binding_digest = browser_session_binding_digest(raw_probe)
    base = {
        "browserName": str(raw_probe["browserName"]),
        "browserType": str(raw_probe["browserType"]),
        "engine": str(raw_probe["engine"]),
        "isolationKind": str(raw_probe["isolationKind"]),
        "sessionBindingDigest": session_binding_digest,
        "runId": raw_probe["runId"],
        "contextEvidenceRef": raw_probe["contextEvidenceRef"],
        "tabOwnedByTask": True,
        "initialControlledTabs": 0,
        "personalProfileUsed": False,
        "userTabClaimed": False,
        "historyRead": False,
        "cookiesRead": False,
        "storageRead": False,
        "features": copy.deepcopy(flags),
    }
    if raw_probe["isolationKind"] != "task_context" or not flags["isolatedContext"]:
        return {"result": "NOT_VERIFIED", "errorCode": "BROWSER_ISOLATION_UNAVAILABLE", "executionLayer": "Lite", **base}
    try:
        _resolve_host_evidence(
            raw_probe["contextEvidenceRef"],
            evidence_resolver,
            code="BROWSER_ISOLATION_UNAVAILABLE",
        )
    except ContractViolation:
        return {
            "result": "NOT_VERIFIED",
            "errorCode": "BROWSER_ISOLATION_UNAVAILABLE",
            "executionLayer": "Lite",
            **base,
        }
    if (
        raw_probe["browserName"] != EXPECTED_BROWSER["browserName"]
        or raw_probe["browserType"] != EXPECTED_BROWSER["browserType"]
        or raw_probe["engine"] != EXPECTED_BROWSER["engine"]
    ):
        return {"result": "NOT_VERIFIED", "errorCode": "BROWSER_ENGINE_UNVERIFIED", "executionLayer": "Lite", **base}
    missing = sorted(key for key, value in flags.items() if value is not True)
    if missing:
        return {
            "result": "NOT_VERIFIED",
            "errorCode": "BROWSER_CAPABILITY_UNAVAILABLE",
            "executionLayer": "Lite",
            "missingCapabilities": missing,
            **base,
        }
    return {"result": "PASS", "errorCode": None, "executionLayer": "Standard", **base}


def authorize_navigation(contract: Mapping[str, Any], target_url: str) -> dict[str, Any]:
    value = validate_browser_contract(contract)
    if value["networkGuardMode"] != "controlled_loopback_manifest":
        raise _safe_error(
            "BROWSER_BEFORE_SEND_GUARD_UNAVAILABLE",
            "$: navigation is unavailable without a controlled pre-send network boundary",
        )
    if not isinstance(target_url, str):
        raise _safe_error("ORIGIN_NOT_APPROVED", "$: target URL is invalid")
    try:
        parsed = urlsplit(target_url)
        if parsed.query or parsed.fragment:
            raise _safe_error("ROUTE_NOT_APPROVED", "$: query and fragment require an explicit frozen contract")
        origin = _normalize_origin(target_url)
        route = _normalize_route(parsed.path or "/")
    except ContractViolation as error:
        if error.code == "ROUTE_NOT_APPROVED":
            raise
        raise _safe_error("ORIGIN_NOT_APPROVED", "$: target URL is not approved") from error
    if origin not in value["approvedOrigins"]:
        raise _safe_error("ORIGIN_NOT_APPROVED", "$: target Origin is not approved")
    if route not in value["approvedRoutes"]:
        raise _safe_error("ROUTE_NOT_APPROVED", "$: target route is not approved")
    return {"origin": origin, "route": route, "decision": "allow"}


def authorize_action(contract: Mapping[str, Any], action_kind: str) -> dict[str, Any]:
    validate_browser_contract(contract)
    if action_kind not in SAFE_ACTIONS | WRITE_ACTIONS | HIGH_RISK_ACTIONS:
        raise _safe_error("SIDE_EFFECT_CLASSIFICATION_REQUIRED", "$: action kind is unknown")
    if action_kind in HIGH_RISK_ACTIONS:
        raise _safe_error("HIGH_RISK_ACTION_EXIT", "$: high-risk action exits Browser Standard")
    if action_kind in WRITE_ACTIONS:
        raise _safe_error("SIDE_EFFECT_BLOCKED", "$: Browser Standard v0.3.0 is read-only")
    return {"actionKind": action_kind, "decision": "allow"}


_DOM_FIELDS = {
    "selector", "tagName", "type", "href", "formAction", "formMethod", "target", "download",
    "dataSideEffect", "contentEditable", "currentUrl",
}


def _normalize_dom_snapshot(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != _DOM_FIELDS:
        raise _safe_error("ACTION_DOM_MISMATCH", "$: DOM target snapshot field set is invalid")
    normalized: dict[str, Any] = {}
    for key in _DOM_FIELDS - {"download", "contentEditable"}:
        if not isinstance(value[key], str):
            raise _safe_error("ACTION_DOM_MISMATCH", f"$.domSnapshot.{key}: expected string")
        normalized[key] = value[key]
    if not isinstance(value["download"], bool) or not isinstance(value["contentEditable"], bool):
        raise _safe_error("ACTION_DOM_MISMATCH", "$: DOM target booleans are invalid")
    normalized["download"] = value["download"]
    normalized["contentEditable"] = value["contentEditable"]
    normalized["tagName"] = normalized["tagName"].lower()
    normalized["type"] = normalized["type"].lower()
    normalized["formMethod"] = normalized["formMethod"].upper()
    return normalized


def authorize_dom_action(
    contract: Mapping[str, Any],
    dom_snapshot: Mapping[str, Any],
    operation: str,
    *,
    claimed_action_kind: str | None = None,
    run_guard: BrowserRunGuard | None = None,
) -> dict[str, Any]:
    if run_guard is not None:
        require_browser_run_active(run_guard)
    value = validate_browser_contract(contract)
    snapshot = _normalize_dom_snapshot(dom_snapshot)
    if operation not in {"click", "fill"}:
        raise _safe_error("ACTION_DOM_MISMATCH", "$: unsupported DOM operation")
    authorize_navigation(value, snapshot["currentUrl"])
    if snapshot["download"]:
        raise _safe_error("DOWNLOAD_BLOCKED", "$: downloads are blocked")
    if snapshot["target"] not in {"", "_self"}:
        raise _safe_error("NEW_TAB_NOT_APPROVED", "$: new-tab/popup actions are blocked")
    dom_is_side_effect = bool(
        snapshot["dataSideEffect"]
        or snapshot["formAction"]
        or snapshot["type"] == "submit"
        or snapshot["formMethod"] not in {"", "GET"}
    )
    if claimed_action_kind in SAFE_ACTIONS and dom_is_side_effect:
        raise _safe_error("ACTION_DOM_MISMATCH", "$: claimed safe action conflicts with DOM side-effect semantics")
    if snapshot["dataSideEffect"]:
        raise _safe_error("SIDE_EFFECT_BLOCKED", "$: DOM target declares a side effect")
    if snapshot["formAction"] or snapshot["type"] == "submit" or snapshot["formMethod"] not in {"", "GET"}:
        raise _safe_error("SIDE_EFFECT_BLOCKED", "$: form submission is blocked")
    if snapshot["href"]:
        if operation != "click":
            raise _safe_error("ACTION_DOM_MISMATCH", "$: href target cannot be filled")
        allowed = authorize_navigation(value, snapshot["href"])
        return {
            "operation": operation,
            "actionKind": "safe_read_only",
            "targetSnapshotDigest": digest_json(snapshot),
            "navigation": allowed,
            "decision": "allow",
        }
    if operation == "fill":
        if snapshot["tagName"] != "input" or snapshot["type"] not in {"search", "text"} or snapshot["contentEditable"]:
            raise _safe_error("ACTION_DOM_MISMATCH", "$: fill is not bound to a safe plain input")
    elif snapshot["tagName"] != "button" or snapshot["type"] != "button":
        raise _safe_error("ACTION_DOM_MISMATCH", "$: click is not bound to a safe local-state button")
    return {
        "operation": operation,
        "actionKind": "local_ui_state",
        "targetSnapshotDigest": digest_json(snapshot),
        "decision": "allow",
    }


def issue_dom_action_permit(
    contract: Mapping[str, Any],
    dom_snapshot: Mapping[str, Any],
    operation: str,
    *,
    run_guard: BrowserRunGuard | None,
    claimed_action_kind: str | None = None,
) -> BrowserActionPermit:
    active = require_browser_run_active(run_guard)
    decision = authorize_dom_action(
        contract,
        dom_snapshot,
        operation,
        claimed_action_kind=claimed_action_kind,
        run_guard=active,
    )
    return BrowserActionPermit(
        run_id=active.run_id,
        operation=operation,
        action_kind=decision["actionKind"],
        target_snapshot_digest=decision["targetSnapshotDigest"],
        consumed=False,
        _authority=_TRUSTED_BROWSER_AUTHORITY,
    )


def consume_dom_action_permit(
    permit: BrowserActionPermit | None,
    current_dom_snapshot: Mapping[str, Any],
    *,
    run_guard: BrowserRunGuard | None,
) -> dict[str, Any]:
    active = require_browser_run_active(run_guard)
    if not isinstance(permit, BrowserActionPermit) or permit._authority is not _TRUSTED_BROWSER_AUTHORITY:
        raise _safe_error("ACTION_DOM_MISMATCH", "$: one-shot DOM action permit is required")
    if permit.consumed or permit.run_id != active.run_id:
        raise _safe_error("BROWSER_EVIDENCE_REPLAYED", "$: DOM action permit was consumed or belongs to another run")
    actual_digest = digest_json(_normalize_dom_snapshot(current_dom_snapshot))
    if actual_digest != permit.target_snapshot_digest:
        raise _safe_error("ACTION_DOM_MISMATCH", "$: DOM target changed before action dispatch")
    permit.consumed = True
    record_browser_action(active, f"dom.{permit.operation}")
    return {
        "operation": permit.operation,
        "actionKind": permit.action_kind,
        "targetSnapshotDigest": actual_digest,
        "decision": "allow",
        "oneShotPermitConsumed": True,
    }


def _valid_rect(value: Any, path: str) -> dict[str, float]:
    if not isinstance(value, Mapping) or set(value) != {"x", "y", "width", "height"}:
        raise _safe_error("BROWSER_REPORT_INVALID", f"{path}: invalid rect")
    result: dict[str, float] = {}
    for key in ("x", "y", "width", "height"):
        item = value[key]
        if not isinstance(item, (int, float)) or item < 0:
            raise _safe_error("BROWSER_REPORT_INVALID", f"{path}.{key}: invalid")
        result[key] = float(item)
    if result["width"] <= 0 or result["height"] <= 0:
        raise _safe_error("BROWSER_REPORT_INVALID", f"{path}: empty rect")
    return result


def _rects_intersect(left: Mapping[str, float], right: Mapping[str, float]) -> bool:
    return not (
        left["x"] + left["width"] <= right["x"]
        or right["x"] + right["width"] <= left["x"]
        or left["y"] + left["height"] <= right["y"]
        or right["y"] + right["height"] <= left["y"]
    )


def _decode_png_size(raw: bytes) -> tuple[int, int]:
    if not raw.startswith(PNG_SIGNATURE):
        raise _safe_error("SCREENSHOT_BYTES_REQUIRED", "$: screenshot is not PNG")
    offset = len(PNG_SIGNATURE)
    width = height = 0
    bit_depth = color_type = 0
    seen_ihdr = seen_idat = seen_iend = False
    idat_closed = False
    compressed_parts: list[bytes] = []
    while offset < len(raw):
        if offset + 12 > len(raw):
            raise _safe_error("SCREENSHOT_BYTES_REQUIRED", "$: truncated PNG chunk")
        length = struct.unpack(">I", raw[offset : offset + 4])[0]
        chunk_type = raw[offset + 4 : offset + 8]
        data_start = offset + 8
        data_end = data_start + length
        crc_end = data_end + 4
        if crc_end > len(raw):
            raise _safe_error("SCREENSHOT_BYTES_REQUIRED", "$: truncated PNG data")
        data = raw[data_start:data_end]
        expected_crc = struct.unpack(">I", raw[data_end:crc_end])[0]
        if zlib.crc32(chunk_type + data) & 0xFFFFFFFF != expected_crc:
            raise _safe_error("SCREENSHOT_BYTES_REQUIRED", "$: invalid PNG CRC")
        if not seen_ihdr:
            if chunk_type != b"IHDR" or length != 13:
                raise _safe_error("SCREENSHOT_BYTES_REQUIRED", "$: PNG IHDR must be first")
            width, height = struct.unpack(">II", data[:8])
            bit_depth, color_type, compression, filter_method, interlace = data[8:13]
            if width <= 0 or height <= 0:
                raise _safe_error("SCREENSHOT_BYTES_REQUIRED", "$: PNG dimensions are invalid")
            allowed_depths = {
                0: {1, 2, 4, 8, 16},
                2: {8, 16},
                3: {1, 2, 4, 8},
                4: {8, 16},
                6: {8, 16},
            }
            if (
                color_type not in allowed_depths
                or bit_depth not in allowed_depths[color_type]
                or compression != 0
                or filter_method != 0
                or interlace != 0
            ):
                raise _safe_error("SCREENSHOT_BYTES_REQUIRED", "$: unsupported or invalid PNG IHDR")
            seen_ihdr = True
        elif chunk_type == b"IHDR":
            raise _safe_error("SCREENSHOT_BYTES_REQUIRED", "$: duplicate PNG IHDR")
        elif chunk_type == b"IDAT":
            if idat_closed:
                raise _safe_error("SCREENSHOT_BYTES_REQUIRED", "$: PNG IDAT chunks are not consecutive")
            seen_idat = True
            compressed_parts.append(data)
        elif chunk_type == b"IEND":
            if not seen_idat or length != 0 or crc_end != len(raw):
                raise _safe_error("SCREENSHOT_BYTES_REQUIRED", "$: PNG IEND/trailing data is invalid")
            seen_iend = True
            break
        elif seen_idat:
            idat_closed = True
        offset = crc_end
    if not (seen_ihdr and seen_idat and seen_iend):
        raise _safe_error("SCREENSHOT_BYTES_REQUIRED", "$: incomplete PNG")
    try:
        decompressor = zlib.decompressobj()
        decoded = decompressor.decompress(b"".join(compressed_parts)) + decompressor.flush()
    except zlib.error as error:
        raise _safe_error("SCREENSHOT_BYTES_REQUIRED", "$: PNG pixel stream is not decodable") from error
    if not decompressor.eof or decompressor.unused_data or decompressor.unconsumed_tail:
        raise _safe_error("SCREENSHOT_BYTES_REQUIRED", "$: PNG pixel stream has trailing or incomplete data")
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color_type]
    row_bytes = (width * channels * bit_depth + 7) // 8
    expected_decoded_size = height * (1 + row_bytes)
    if len(decoded) != expected_decoded_size:
        raise _safe_error("SCREENSHOT_BYTES_REQUIRED", "$: PNG decoded scanline size is invalid")
    return width, height


def validate_geometry_evidence(
    value: Mapping[str, Any], *, expected_run_binding: str | None = None
) -> dict[str, Any]:
    required = {"runBindingDigest", "viewport", "dpr", "document", "criticalElements"}
    if not isinstance(value, Mapping) or set(value) != required:
        raise _safe_error("BROWSER_REPORT_INVALID", "$.geometryEvidence: invalid field set")
    run_binding = value["runBindingDigest"]
    if not isinstance(run_binding, str) or re.fullmatch(r"[0-9a-f]{64}", run_binding) is None:
        raise _safe_error("BROWSER_REPORT_INVALID", "$.geometryEvidence.runBindingDigest: invalid")
    if expected_run_binding is not None:
        _require_run_binding(value, expected_run_binding, "$.geometryEvidence")
    viewport = value["viewport"]
    if not isinstance(viewport, Mapping) or set(viewport) != {"width", "height"} or any(
        not isinstance(viewport[key], int) or viewport[key] <= 0 for key in viewport
    ):
        raise _safe_error("BROWSER_REPORT_INVALID", "$.geometryEvidence.viewport: invalid")
    if not isinstance(value["dpr"], (int, float)) or value["dpr"] <= 0:
        raise _safe_error("BROWSER_REPORT_INVALID", "$.geometryEvidence.dpr: invalid")
    document = value["document"]
    if not isinstance(document, Mapping) or set(document) != {"scrollWidth", "clientWidth", "horizontalOverflow"}:
        raise _safe_error("BROWSER_REPORT_INVALID", "$.geometryEvidence.document: invalid")
    if (
        not isinstance(document["scrollWidth"], (int, float))
        or not isinstance(document["clientWidth"], (int, float))
        or document["horizontalOverflow"] is not False
        or document["scrollWidth"] > document["clientWidth"] + 1
    ):
        raise _safe_error("BROWSER_GEOMETRY_FAILED", "$: horizontal overflow detected")
    elements = value["criticalElements"]
    if not isinstance(elements, list) or not elements:
        raise _safe_error("BROWSER_EVIDENCE_INCOMPLETE", "$.geometryEvidence.criticalElements: required")
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, element in enumerate(elements):
        if not isinstance(element, Mapping) or set(element) != {"id", "rect", "visible", "occluded"}:
            raise _safe_error("BROWSER_REPORT_INVALID", f"$.geometryEvidence.criticalElements[{index}]: invalid")
        identifier = str(element["id"])
        if identifier in seen:
            raise _safe_error("BROWSER_REPORT_INVALID", "$: duplicate critical element")
        seen.add(identifier)
        rect = _valid_rect(element["rect"], f"$.geometryEvidence.criticalElements[{index}].rect")
        if element["visible"] is not True or element["occluded"] is not False:
            raise _safe_error("BROWSER_GEOMETRY_FAILED", f"$: critical element failed visibility for {identifier}")
        normalized.append({"id": identifier, "rect": rect, "visible": True, "occluded": False})
    if not REQUIRED_GEOMETRY_IDS <= seen:
        raise _safe_error("BROWSER_EVIDENCE_INCOMPLETE", "$: required geometry targets are missing")
    return {
        "runBindingDigest": run_binding,
        "viewport": {"width": viewport["width"], "height": viewport["height"]},
        "dpr": float(value["dpr"]),
        "document": {
            "scrollWidth": float(document["scrollWidth"]),
            "clientWidth": float(document["clientWidth"]),
            "horizontalOverflow": False,
        },
        "criticalElements": normalized,
    }


def validate_screenshot_evidence(
    contract: Mapping[str, Any], value: Mapping[str, Any], *, expected_run_binding: str | None = None
) -> dict[str, Any]:
    contract_value = validate_browser_contract(contract)
    required = {
        "runBindingDigest", "label", "viewport", "clip", "expectedPixelSize", "sensitiveSelectorMatches",
        "coordinateSpace", "scrollX", "scrollY", "croppedBytes", "rawPersisted",
    }
    if isinstance(value, Mapping) and "croppedBytes" not in value:
        raise _safe_error("SCREENSHOT_BYTES_REQUIRED", "$: cropped screenshot bytes are required")
    if not isinstance(value, Mapping) or set(value) != required:
        raise _safe_error("TRUSTED_SCREENSHOT_RECEIPT_REQUIRED", "$: trusted screenshot field set is required")
    run_binding = value["runBindingDigest"]
    if not isinstance(run_binding, str) or re.fullmatch(r"[0-9a-f]{64}", run_binding) is None:
        raise _safe_error("BROWSER_REPORT_INVALID", "$.screenshotEvidence.runBindingDigest: invalid")
    if expected_run_binding is not None:
        _require_run_binding(value, expected_run_binding, "$.screenshotEvidence")
    if value["label"] not in {"before", "after"}:
        raise _safe_error("BROWSER_REPORT_INVALID", "$.screenshotEvidence.label: invalid")
    viewport = value["viewport"]
    if not isinstance(viewport, Mapping) or set(viewport) != {"width", "height"} or (
        viewport["width"], viewport["height"]
    ) not in EXPECTED_VIEWPORTS:
        raise _safe_error("SCREENSHOT_COORDINATE_MISMATCH", "$: screenshot viewport does not match contract")
    if value["coordinateSpace"] != "viewport_css_pixels" or value["scrollX"] != 0 or value["scrollY"] != 0:
        raise _safe_error("SCREENSHOT_COORDINATE_MISMATCH", "$: screenshot coordinates are not viewport CSS pixels")
    clip = _valid_rect(value["clip"], "$.screenshotEvidence.clip")
    if clip["x"] + clip["width"] > viewport["width"] + 1 or clip["y"] + clip["height"] > viewport["height"] + 1:
        raise _safe_error("SCREENSHOT_COORDINATE_MISMATCH", "$: screenshot clip exceeds viewport")
    selectors = contract_value["requiredSensitiveSelectorsByRoute"]["/"]
    matches = value["sensitiveSelectorMatches"]
    if not isinstance(matches, Mapping) or set(matches) != set(selectors):
        raise _safe_error("SCREENSHOT_REDACTION_UNVERIFIED", "$: required sensitive selectors were not all queried")
    sensitive_rects: list[dict[str, float]] = []
    match_counts: dict[str, int] = {}
    for selector in selectors:
        rects = matches[selector]
        if not isinstance(rects, list) or not rects:
            raise _safe_error("SCREENSHOT_REDACTION_UNVERIFIED", f"$: selector {selector!r} did not produce a rect")
        normalized_rects = [_valid_rect(item, "$.screenshotEvidence.sensitiveSelectorMatches") for item in rects]
        sensitive_rects.extend(normalized_rects)
        match_counts[selector] = len(normalized_rects)
    if any(_rects_intersect(clip, rect) for rect in sensitive_rects):
        raise _safe_error("SENSITIVE_EVIDENCE_REJECTED", "$: screenshot crop intersects a sensitive region")
    if value["rawPersisted"] is not False:
        raise _safe_error("SENSITIVE_EVIDENCE_REJECTED", "$: raw screenshot persistence is forbidden")
    expected_pixel = value["expectedPixelSize"]
    if not isinstance(expected_pixel, Mapping) or set(expected_pixel) != {"width", "height"} or any(
        not isinstance(expected_pixel[key], int) or expected_pixel[key] <= 0 for key in expected_pixel
    ):
        raise _safe_error("SCREENSHOT_COORDINATE_MISMATCH", "$: expected PNG pixel size is invalid")
    cropped = value["croppedBytes"]
    if not isinstance(cropped, (bytes, bytearray, memoryview)):
        raise _safe_error("SCREENSHOT_BYTES_REQUIRED", "$: cropped screenshot bytes are required")
    raw = bytes(cropped)
    pixel_width, pixel_height = _decode_png_size(raw)
    if (pixel_width, pixel_height) != (expected_pixel["width"], expected_pixel["height"]):
        raise _safe_error("SCREENSHOT_COORDINATE_MISMATCH", "$: decoded PNG size does not match crop operation")
    return {
        "runBindingDigest": run_binding,
        "label": value["label"],
        "viewport": dict(viewport),
        "clip": clip,
        "pixelSize": {"width": pixel_width, "height": pixel_height},
        "sensitiveSelectorMatchCounts": match_counts,
        "sensitiveRects": sensitive_rects,
        "coordinateSpace": "viewport_css_pixels",
        "scrollX": 0,
        "scrollY": 0,
        "sha256": sha256_hex(raw),
        "size": len(raw),
        "persisted": False,
    }


def _response_class(status: int) -> str:
    if status == 0:
        return "network_error"
    if status < 300:
        return "success"
    if status < 400:
        return "redirect"
    if status < 500:
        return "client_error"
    return "server_error"


def _sensitive_safe_code(text: str) -> str | None:
    lowered = text.casefold()
    if "bearer " in lowered:
        return SENSITIVE_SAFE_CODES["bearer"]
    if SENSITIVE_MARKER.casefold() in lowered:
        return SENSITIVE_SAFE_CODES["marker"]
    if "password=" in lowered or "password:" in lowered or "passwd=" in lowered:
        return SENSITIVE_SAFE_CODES["password"]
    if re.search(r"[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}", text, re.IGNORECASE):
        return SENSITIVE_SAFE_CODES["email"]
    if re.search(r"(?<!\d)1[3-9]\d{9}(?!\d)", text):
        return SENSITIVE_SAFE_CODES["phone"]
    if ID_NUMBER_RE.search(text):
        return SENSITIVE_SAFE_CODES["id"]
    return None


def sanitize_network_evidence(
    contract: Mapping[str, Any],
    entries: Iterable[Mapping[str, Any]],
    *,
    expected_run_binding: str | None = None,
) -> list[dict[str, Any]]:
    value = validate_browser_contract(contract)
    sanitized: list[dict[str, Any]] = []
    required = {"runBindingDigest", "url", "resourceType", "method", "status", "durationMs"}
    for index, entry in enumerate(entries):
        if not isinstance(entry, Mapping) or not required <= set(entry):
            raise _safe_error("BROWSER_REPORT_INVALID", f"$.networkEvidence[{index}]: invalid")
        run_binding = entry["runBindingDigest"]
        if not isinstance(run_binding, str) or re.fullmatch(r"[0-9a-f]{64}", run_binding) is None:
            raise _safe_error("BROWSER_REPORT_INVALID", f"$.networkEvidence[{index}].runBindingDigest: invalid")
        if expected_run_binding is not None:
            _require_run_binding(entry, expected_run_binding, f"$.networkEvidence[{index}]")
        allowed = authorize_navigation(value, str(entry["url"]))
        method = str(entry["method"]).upper()
        status = entry["status"]
        duration = entry["durationMs"]
        resource_type = str(entry["resourceType"]).lower()
        if method not in ALLOWED_METHODS:
            raise _safe_error("NETWORK_METHOD_NOT_ALLOWED", f"$.networkEvidence[{index}]: method blocked")
        if not isinstance(status, int) or not 0 <= status <= 599 or not isinstance(duration, (int, float)) or duration < 0:
            raise _safe_error("BROWSER_REPORT_INVALID", f"$.networkEvidence[{index}]: invalid status/duration")
        if 300 <= status < 400:
            raise _safe_error("NAVIGATION_REDIRECT_NOT_APPROVED", f"$.networkEvidence[{index}]: redirects are forbidden")
        if resource_type not in ALLOWED_RESOURCE_TYPES:
            raise _safe_error("BROWSER_REPORT_INVALID", f"$.networkEvidence[{index}]: invalid resource type")
        raw_summary = str(entry.get("summary", ""))
        redaction_code = _sensitive_safe_code(raw_summary) or "METADATA_ONLY"
        sanitized.append(
            {
                "runBindingDigest": run_binding,
                "origin": allowed["origin"],
                "route": allowed["route"],
                "resourceType": resource_type,
                "method": method,
                "status": status,
                "durationMs": round(float(duration), 3),
                "responseClass": _response_class(status),
                "redactionCode": redaction_code,
                "redactionApplied": bool(set(entry) - required),
            }
        )
    return sanitized


def build_controlled_fixture_manifest(contract: Mapping[str, Any], fixture_root: str | Path) -> dict[str, Any]:
    """Preflight the frozen loopback fixture before any server or Browser action."""

    value = validate_browser_contract(contract)
    if value["networkGuardMode"] != "controlled_loopback_manifest":
        raise _safe_error("BROWSER_BEFORE_SEND_GUARD_UNAVAILABLE", "$: controlled fixture manifest is unavailable")
    root = Path(fixture_root).resolve(strict=True)
    required_names = ("index.html", "styles.css", "app.js", "server.py")
    files: dict[str, str] = {}
    texts: dict[str, str] = {}
    for name in required_names:
        target = (root / name).resolve(strict=True)
        if target.parent != root or not target.is_file():
            raise _safe_error("BROWSER_CONTRACT_INVALID", f"$: controlled fixture file invalid: {name}")
        raw = target.read_bytes()
        files[name] = sha256_hex(raw)
        try:
            texts[name] = raw.decode("utf-8")
        except UnicodeDecodeError as error:
            raise _safe_error("BROWSER_CONTRACT_INVALID", f"$: controlled fixture is not UTF-8: {name}") from error

    html = texts["index.html"]
    css = texts["styles.css"]
    script = texts["app.js"]
    server = texts["server.py"]
    resource_targets: list[str] = []
    for match in re.finditer(
        r"(?is)<(?:script|img|iframe)\b[^>]*\bsrc\s*=\s*['\"]([^'\"]+)['\"]|"
        r"<link\b[^>]*\bhref\s*=\s*['\"]([^'\"]+)['\"]",
        html,
    ):
        target = next(group for group in match.groups() if group is not None)
        resource_targets.append(target)
    for pattern in (r"(?is)@import\s+(?:url\()?['\"]?([^'\")\s;]+)", r"(?is)url\(\s*['\"]?([^'\")]+)"):
        resource_targets.extend(match.group(1).strip() for match in re.finditer(pattern, css))
    fetch_targets = [match.group(1) for match in re.finditer(r"(?is)\bfetch\(\s*['\"]([^'\"]+)['\"]", script)]
    if len(re.findall(r"(?i)\bfetch\s*\(", script)) != len(fetch_targets):
        raise _safe_error("BROWSER_BEFORE_SEND_GUARD_UNAVAILABLE", "$: dynamic fetch target cannot be preflighted")
    network_targets = [target for target in resource_targets + fetch_targets if target != "data:,"]
    for target in network_targets:
        absolute = target if urlsplit(target).scheme else value["approvedOrigins"][0] + (target if target.startswith("/") else "/" + target)
        try:
            authorize_navigation(value, absolute)
        except ContractViolation as error:
            code = "NETWORK_ORIGIN_NOT_APPROVED" if error.code == "ORIGIN_NOT_APPROVED" else "NETWORK_ROUTE_NOT_APPROVED"
            raise _safe_error(code, "$: controlled fixture contains an unapproved automatic network target") from error
    if re.search(r"(?is)<meta\b[^>]*http-equiv\s*=\s*['\"]?refresh", html):
        raise _safe_error("NAVIGATION_REDIRECT_NOT_APPROVED", "$: controlled fixture contains meta refresh")
    if re.search(r"(?i)\bXMLHttpRequest\b|\bEventSource\s*\(", script):
        raise _safe_error("BROWSER_BEFORE_SEND_GUARD_UNAVAILABLE", "$: dynamic network API cannot be preflighted")
    if re.search(r"(?i)\bnew\s+WebSocket\s*\(", script):
        raise _safe_error("BROWSER_BEFORE_SEND_GUARD_UNAVAILABLE", "$: WebSocket is unavailable in controlled v0.3.0")
    if re.search(r"(?i)\bsendBeacon\s*\(", script):
        raise _safe_error("NETWORK_METHOD_NOT_ALLOWED", "$: sendBeacon write is blocked")
    if re.search(r"(?i)\bwindow\.open\s*\(", script):
        raise _safe_error("NEW_TAB_NOT_APPROVED", "$: controlled fixture contains window.open")
    if re.search(r"(?i)(?:window\.)?location(?:\.href)?\s*=", script):
        raise _safe_error("NAVIGATION_REDIRECT_NOT_APPROVED", "$: controlled fixture contains script navigation")
    if re.search(r"(?is)<form\b|\btype\s*=\s*['\"]submit['\"]", html):
        raise _safe_error("SIDE_EFFECT_BLOCKED", "$: controlled fixture contains a submit surface")
    if re.search(r"(?is)<a\b[^>]*\bdownload(?:\s|=|>)", html):
        raise _safe_error("DOWNLOAD_BLOCKED", "$: controlled fixture contains a download action")
    if re.search(r"(?is)<[^>]+\btarget\s*=\s*['\"]_blank['\"]", html):
        raise _safe_error("NEW_TAB_NOT_APPROVED", "$: controlled fixture contains target=_blank")
    if re.search(r"send_response\(\s*3\d\d\s*\)|send_header\(\s*['\"]Location", server, re.IGNORECASE):
        raise _safe_error("NAVIGATION_REDIRECT_NOT_APPROVED", "$: controlled server contains a redirect")
    declared_methods = set(re.findall(r"def\s+do_([A-Z]+)\b", server))
    if declared_methods != {"GET", "HEAD"}:
        raise _safe_error("NETWORK_METHOD_NOT_ALLOWED", "$: controlled server must implement only GET and HEAD")
    outbound_client_pattern = re.compile(
        r"(?ix)(?:"
        r"\bimport\s+(?:urllib\.request|requests|http\.client|socket)\b|"
        r"\bfrom\s+(?:urllib|http)\s+import\s+(?:request|client)\b|"
        r"\burlopen\s*\(|"
        r"(?<![\w.])(?:urllib\.request|requests|http\.client|socket)\."
        r")"
    )
    if outbound_client_pattern.search(server):
        raise _safe_error("NETWORK_ORIGIN_NOT_APPROVED", "$: controlled server contains an outbound network client")
    expected_routes = {"/", "/styles.css", "/app.js", "/api/status", "/api/fail"}
    route_literals = set(re.findall(r"['\"](/(?:[^'\"]*))['\"]", server))
    if route_literals != expected_routes:
        raise _safe_error("CONTROLLED_FIXTURE_MANIFEST_MISMATCH", "$: controlled server route set must be exact")
    if files != CONTROLLED_FIXTURE_HASHES:
        raise _safe_error("CONTROLLED_FIXTURE_HASH_MISMATCH", "$: controlled fixture bytes differ from the frozen contract set")
    manifest = {
        "mode": "controlled_loopback_manifest",
        "fixtureHashPolicy": "frozen_v7_exact",
        "fileHashes": files,
        "automaticTargets": sorted(network_targets),
        "blockedDomTargets": ["external-link", "approval-action"],
        "serverRoutes": sorted(expected_routes),
        "serverMethods": ["GET", "HEAD"],
        "redirects": [],
        "manifestDigest": "",
    }
    manifest["manifestDigest"] = digest_json({key: item for key, item in manifest.items() if key != "manifestDigest"})
    return manifest


def validate_controlled_fixture_manifest(value: Mapping[str, Any]) -> dict[str, Any]:
    required = {
        "mode", "fixtureHashPolicy", "fileHashes", "automaticTargets", "blockedDomTargets", "serverRoutes",
        "serverMethods", "redirects", "manifestDigest",
    }
    if (
        not isinstance(value, Mapping)
        or set(value) != required
        or value.get("mode") != "controlled_loopback_manifest"
        or value.get("fixtureHashPolicy") not in {"frozen_v5_exact", "frozen_v7_exact"}
    ):
        raise _safe_error("BROWSER_CONTRACT_INVALID", "$: invalid controlled fixture manifest")
    if value.get("fileHashes") != CONTROLLED_FIXTURE_HASHES:
        raise _safe_error("CONTROLLED_FIXTURE_HASH_MISMATCH", "$: controlled fixture hashes do not match v7")
    if value.get("automaticTargets") != CONTROLLED_AUTOMATIC_TARGETS:
        raise _safe_error("CONTROLLED_FIXTURE_MANIFEST_MISMATCH", "$: automatic target set is invalid")
    if value.get("blockedDomTargets") != ["external-link", "approval-action"]:
        raise _safe_error("CONTROLLED_FIXTURE_MANIFEST_MISMATCH", "$: blocked DOM target set is invalid")
    if value.get("serverMethods") != ["GET", "HEAD"] or value.get("redirects") != []:
        raise _safe_error("BROWSER_CONTRACT_INVALID", "$: controlled server method/redirect contract is invalid")
    if set(value.get("serverRoutes", [])) != {"/", "/styles.css", "/app.js", "/api/status", "/api/fail"}:
        raise _safe_error("BROWSER_CONTRACT_INVALID", "$: controlled server routes are invalid")
    expected = digest_json({key: copy.deepcopy(item) for key, item in value.items() if key != "manifestDigest"})
    if value.get("manifestDigest") != expected:
        raise _safe_error("BROWSER_CONTRACT_INVALID", "$.manifestDigest: mismatch")
    return copy.deepcopy(dict(value))


def _network_set_digest(counter: Counter[tuple[str, str, int]]) -> str:
    return digest_json([[list(key), count] for key, count in sorted(counter.items())])


def reconcile_network_evidence(
    contract: Mapping[str, Any],
    browser_entries: Sequence[Mapping[str, Any]],
    server_entries: Sequence[Mapping[str, Any]],
    *,
    network_complete: bool,
    expected_run_binding: str | None = None,
) -> dict[str, Any]:
    if network_complete is not True:
        raise _safe_error("BROWSER_EVIDENCE_INCOMPLETE", "$: complete observed network evidence is required")
    value = validate_browser_contract(contract)
    browser = sanitize_network_evidence(value, browser_entries, expected_run_binding=expected_run_binding)
    normalized_server: list[dict[str, Any]] = []
    for index, item in enumerate(server_entries):
        if not isinstance(item, Mapping) or set(item) != {"runBindingDigest", "method", "route", "status"}:
            raise _safe_error("BROWSER_REPORT_INVALID", f"$.serverRequestLog[{index}]: invalid")
        run_binding = item["runBindingDigest"]
        if not isinstance(run_binding, str) or re.fullmatch(r"[0-9a-f]{64}", run_binding) is None:
            raise _safe_error("BROWSER_REPORT_INVALID", f"$.serverRequestLog[{index}].runBindingDigest: invalid")
        if expected_run_binding is not None:
            _require_run_binding(item, expected_run_binding, f"$.serverRequestLog[{index}]")
        method = str(item["method"]).upper()
        route = _normalize_route(str(item["route"]))
        status = item["status"]
        if method not in ALLOWED_METHODS:
            raise _safe_error("NETWORK_METHOD_NOT_ALLOWED", f"$.serverRequestLog[{index}]: method blocked")
        if route not in value["approvedRoutes"]:
            raise _safe_error("NETWORK_ROUTE_NOT_APPROVED", f"$.serverRequestLog[{index}]: route blocked")
        if not isinstance(status, int) or not 0 <= status <= 599:
            raise _safe_error("BROWSER_REPORT_INVALID", f"$.serverRequestLog[{index}]: status invalid")
        if 300 <= status < 400:
            raise _safe_error("NAVIGATION_REDIRECT_NOT_APPROVED", f"$.serverRequestLog[{index}]: redirects are forbidden")
        normalized_server.append({"runBindingDigest": run_binding, "method": method, "route": route, "status": status})
    browser_counter = Counter((item["method"], item["route"], item["status"]) for item in browser)
    server_counter = Counter((item["method"], item["route"], item["status"]) for item in normalized_server)
    if browser_counter != server_counter:
        raise _safe_error("NETWORK_EVIDENCE_MISMATCH", "$: Browser and controlled server network sets differ")
    return {
        "browserEvidence": browser,
        "serverRequestLog": normalized_server,
        "networkComplete": True,
        "requestCount": sum(browser_counter.values()),
        "networkSetDigest": _network_set_digest(browser_counter),
    }


def reconcile_response_receipt_evidence(
    contract: Mapping[str, Any],
    browser_entries: Sequence[Mapping[str, Any]],
    server_entries: Sequence[Mapping[str, Any]],
    *,
    network_complete: bool,
    expected_run_binding: str,
) -> dict[str, Any]:
    """Bind controlled Browser response witnesses to the server's post-marker log.

    The receipt is a synthetic, per-response HMAC emitted by the frozen loopback
    server.  Its key never crosses this contract.  A DOM row or server row alone
    has no authority; both exact tuple sets must match before the existing
    metadata-only network validator runs.
    """

    if network_complete is not True:
        raise _safe_error("BROWSER_EVIDENCE_INCOMPLETE", "$: complete response receipt evidence is required")
    if not isinstance(expected_run_binding, str) or WITNESS_RECEIPT_RE.fullmatch(expected_run_binding) is None:
        raise _safe_error("BROWSER_REPORT_INVALID", "$: expected run binding is invalid")
    if not browser_entries or not server_entries:
        raise _safe_error("BROWSER_EVIDENCE_INCOMPLETE", "$: Browser and server receipt rows are required")
    value = validate_browser_contract(contract)
    if len(value["approvedOrigins"]) != 1:
        raise _safe_error("BROWSER_CONTRACT_INVALID", "$: response receipts require one controlled Origin")
    controlled_origin = value["approvedOrigins"][0]

    browser_required = {
        "runBindingDigest", "route", "resourceType", "method", "status", "durationMs",
        "sequence", "witnessReceipt",
    }
    server_required = {
        "runBindingDigest", "windowId", "sequence", "method", "route", "status", "witnessReceipt",
    }
    browser_witnesses: list[tuple[str, str, int, str, str, int, str]] = []
    server_witnesses: list[tuple[str, str, int, str, str, int, str]] = []
    stripped_browser: list[dict[str, Any]] = []
    stripped_server: list[dict[str, Any]] = []

    for index, item in enumerate(browser_entries):
        if not isinstance(item, Mapping) or set(item) != browser_required:
            raise _safe_error(
                "BROWSER_EVIDENCE_INCOMPLETE",
                f"$.networkEvidence[{index}]: response receipt fields are incomplete",
            )
        _require_run_binding(item, expected_run_binding, f"$.networkEvidence[{index}]")
        # The only header exposed to the page for capture-window binding is the
        # already-frozen run digest.  v7 therefore defines the formal window id
        # as that digest instead of persisting a second page-controlled field.
        window_id = expected_run_binding
        sequence = item["sequence"]
        receipt = item["witnessReceipt"]
        if not isinstance(window_id, str) or WITNESS_WINDOW_RE.fullmatch(window_id) is None:
            raise _safe_error("BROWSER_REPORT_INVALID", f"$.networkEvidence[{index}].windowId: invalid")
        if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 1:
            raise _safe_error("BROWSER_REPORT_INVALID", f"$.networkEvidence[{index}].sequence: invalid")
        if not isinstance(receipt, str) or WITNESS_RECEIPT_RE.fullmatch(receipt) is None:
            raise _safe_error("BROWSER_EVIDENCE_INCOMPLETE", f"$.networkEvidence[{index}].witnessReceipt: invalid")
        route = _normalize_route(str(item["route"]))
        allowed = authorize_navigation(value, controlled_origin + route)
        method = str(item["method"]).upper()
        status = item["status"]
        if not isinstance(status, int) or isinstance(status, bool):
            raise _safe_error("BROWSER_REPORT_INVALID", f"$.networkEvidence[{index}].status: invalid")
        browser_witnesses.append(
            (expected_run_binding, window_id, sequence, method, allowed["route"], status, receipt)
        )
        stripped_browser.append(
            {
                "runBindingDigest": copy.deepcopy(item["runBindingDigest"]),
                "url": controlled_origin + route,
                "resourceType": copy.deepcopy(item["resourceType"]),
                "method": copy.deepcopy(item["method"]),
                "status": copy.deepcopy(item["status"]),
                "durationMs": copy.deepcopy(item["durationMs"]),
            }
        )

    for index, item in enumerate(server_entries):
        if not isinstance(item, Mapping) or set(item) != server_required:
            raise _safe_error(
                "BROWSER_EVIDENCE_INCOMPLETE",
                f"$.serverRequestLog[{index}]: response receipt fields are incomplete",
            )
        _require_run_binding(item, expected_run_binding, f"$.serverRequestLog[{index}]")
        window_id = item["windowId"]
        sequence = item["sequence"]
        receipt = item["witnessReceipt"]
        method = str(item["method"]).upper()
        route = _normalize_route(str(item["route"]))
        status = item["status"]
        if not isinstance(window_id, str) or WITNESS_WINDOW_RE.fullmatch(window_id) is None:
            raise _safe_error("BROWSER_REPORT_INVALID", f"$.serverRequestLog[{index}].windowId: invalid")
        if window_id != expected_run_binding:
            raise _safe_error(
                "BROWSER_EVIDENCE_REPLAYED",
                f"$.serverRequestLog[{index}].windowId: capture window does not match the current run",
            )
        if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 1:
            raise _safe_error("BROWSER_REPORT_INVALID", f"$.serverRequestLog[{index}].sequence: invalid")
        if not isinstance(receipt, str) or WITNESS_RECEIPT_RE.fullmatch(receipt) is None:
            raise _safe_error("BROWSER_EVIDENCE_INCOMPLETE", f"$.serverRequestLog[{index}].witnessReceipt: invalid")
        if not isinstance(status, int) or isinstance(status, bool):
            raise _safe_error("BROWSER_REPORT_INVALID", f"$.serverRequestLog[{index}].status: invalid")
        server_witnesses.append(
            (expected_run_binding, window_id, sequence, method, route, status, receipt)
        )
        stripped_server.append(
            {
                "runBindingDigest": expected_run_binding,
                "method": method,
                "route": route,
                "status": status,
            }
        )

    if len(browser_witnesses) != len(server_witnesses):
        raise _safe_error(
            "BROWSER_EVIDENCE_INCOMPLETE",
            "$: Browser and server response receipt row counts differ",
        )

    browser_receipts = [item[-1] for item in browser_witnesses]
    server_receipts = [item[-1] for item in server_witnesses]
    if len(set(browser_receipts)) != len(browser_receipts) or len(set(server_receipts)) != len(server_receipts):
        raise _safe_error("BROWSER_EVIDENCE_REPLAYED", "$: a response receipt was reused")
    browser_counter = Counter(browser_witnesses)
    server_counter = Counter(server_witnesses)
    if browser_counter != server_counter:
        raise _safe_error("NETWORK_WITNESS_MISMATCH", "$: Browser and server response receipt sets differ")
    window_ids = {item[1] for item in browser_witnesses}
    if len(window_ids) != 1:
        raise _safe_error("BROWSER_EVIDENCE_REPLAYED", "$: response receipts span multiple capture windows")

    expected_formal_rows = {
        (1, "GET", "/", 200, "fetch"),
        (2, "GET", "/styles.css", 200, "fetch"),
        (3, "GET", "/app.js", 200, "fetch"),
        (4, "GET", "/api/fail", 503, "fetch"),
    }
    actual_formal_rows = {
        (
            item["sequence"],
            str(item["method"]).upper(),
            _normalize_route(str(item["route"])),
            item["status"],
            str(item["resourceType"]).lower(),
        )
        for item in browser_entries
    }
    if len(browser_witnesses) < len(expected_formal_rows):
        raise _safe_error("BROWSER_EVIDENCE_INCOMPLETE", "$: formal response receipt rows are missing")
    if len(browser_witnesses) != len(expected_formal_rows) or actual_formal_rows != expected_formal_rows:
        raise _safe_error("NETWORK_EVIDENCE_MISMATCH", "$: formal response receipt rows are not exact")

    reconciled = reconcile_network_evidence(
        value,
        stripped_browser,
        stripped_server,
        network_complete=True,
        expected_run_binding=expected_run_binding,
    )
    canonical_witnesses = [list(item) for item, count in sorted(browser_counter.items()) for _ in range(count)]
    reconciled.update(
        {
            "witnessMode": "controlled_loopback_response_receipt",
            "windowId": next(iter(window_ids)),
            "witnessCount": len(browser_witnesses),
            "witnessSetDigest": digest_json(canonical_witnesses),
        }
    )
    return reconciled


def sanitize_console_evidence(
    contract: Mapping[str, Any],
    entries: Iterable[Mapping[str, Any]],
    *,
    expected_run_binding: str | None = None,
) -> list[dict[str, Any]]:
    contract_value = validate_browser_contract(contract)
    sanitized: list[dict[str, Any]] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, Mapping):
            raise _safe_error("BROWSER_REPORT_INVALID", f"$.consoleEvidence[{index}]: invalid")
        run_binding = entry.get("runBindingDigest")
        if not isinstance(run_binding, str) or re.fullmatch(r"[0-9a-f]{64}", run_binding) is None:
            raise _safe_error("BROWSER_REPORT_INVALID", f"$.consoleEvidence[{index}].runBindingDigest: invalid")
        if expected_run_binding is not None:
            _require_run_binding(entry, expected_run_binding, f"$.consoleEvidence[{index}]")
        level = str(entry.get("level", "log")).lower()
        if level == "warning":
            level = "warn"
        if level not in {"debug", "info", "log", "warn", "error"}:
            raise _safe_error("BROWSER_REPORT_INVALID", f"$.consoleEvidence[{index}].level: invalid")
        source: dict[str, str] = {}
        if entry.get("url"):
            allowed = authorize_navigation(contract, str(entry["url"]))
            source = {"origin": allowed["origin"], "route": allowed["route"]}
        message = str(entry.get("message", ""))
        lowered = message.casefold()
        sensitive_code = _sensitive_safe_code(message)
        if sensitive_code is not None:
            event_code = sensitive_code
        elif "controlled async success" in lowered:
            event_code = "ASYNC_SUCCESS"
        elif "controlled network failure" in lowered and "503" in lowered:
            event_code = "NETWORK_FAILURE_503"
        else:
            event_code = "REDACTED_CONSOLE_EVENT"
        related_target = entry.get("relatedTarget")
        related_method = entry.get("relatedMethod")
        related_route = entry.get("relatedRoute")
        related_status = entry.get("relatedStatus")
        if related_target is not None and not isinstance(related_target, str):
            raise _safe_error("BROWSER_REPORT_INVALID", f"$.consoleEvidence[{index}].relatedTarget: invalid")
        if related_method is not None:
            related_method = str(related_method).upper()
            if related_method not in ALLOWED_METHODS:
                raise _safe_error("NETWORK_METHOD_NOT_ALLOWED", f"$.consoleEvidence[{index}].relatedMethod: invalid")
        if related_route is not None:
            related_route = _normalize_route(str(related_route))
            if related_route not in contract_value["approvedRoutes"]:
                raise _safe_error("NETWORK_ROUTE_NOT_APPROVED", f"$.consoleEvidence[{index}].relatedRoute: invalid")
        if related_status is not None and (not isinstance(related_status, int) or not 0 <= related_status <= 599):
            raise _safe_error("BROWSER_REPORT_INVALID", f"$.consoleEvidence[{index}].relatedStatus: invalid")
        sanitized.append(
            {
                "runBindingDigest": run_binding,
                "level": level,
                "eventCode": event_code,
                "source": source,
                "relatedTarget": related_target,
                "relatedMethod": related_method,
                "relatedRoute": related_route,
                "relatedStatus": related_status,
                "redactionApplied": True,
            }
        )
    return sanitized


def validate_redaction_counts(input_count: int, output_count: int, serialized_value: Any) -> dict[str, int]:
    if not isinstance(input_count, int) or not isinstance(output_count, int) or input_count < 0 or output_count < 0:
        raise _safe_error("BROWSER_REPORT_INVALID", "$: redaction counts are invalid")
    if input_count != output_count:
        raise _safe_error("REDACTION_COUNT_MISMATCH", "$: sanitizer must preserve one safe event per input")
    _assert_no_sensitive_serialized(serialized_value)
    return {"inputCount": input_count, "outputCount": output_count, "rawOccurrences": 0}


def validate_cleanup(value: Mapping[str, Any]) -> dict[str, Any]:
    required = {
        "browserTabsClosed", "finalControlledTabs", "serverStopped", "portReleased", "tempRootRemoved",
        "viewportReset", "downloadsRemoved", "rawScreenshotsAbsent", "finalized", "finalizeEvidenceRef",
        "lastBrowserAction", "browserActionsAfterFinalize",
    }
    if not isinstance(value, Mapping) or set(value) != required:
        raise _safe_error("BROWSER_REPORT_INVALID", "$.cleanup: invalid field set")
    boolean_keys = {
        "browserTabsClosed", "serverStopped", "portReleased", "tempRootRemoved", "viewportReset",
        "downloadsRemoved", "rawScreenshotsAbsent",
    }
    if (
        value["finalControlledTabs"] != 0
        or value.get("browserActionsAfterFinalize") != 0
        or any(value[key] is not True for key in boolean_keys)
    ):
        raise _safe_error("BROWSER_CLEANUP_INCOMPLETE", "$: task-owned Browser resources are not fully finalized")
    if value["finalized"] is not True or value.get("lastBrowserAction") != "browser.tabs.finalize":
        raise _safe_error("BROWSER_FINALIZE_REQUIRED", "$: browser.tabs.finalize evidence is required")
    _validated_ref(value["finalizeEvidenceRef"], code="BROWSER_FINALIZE_REQUIRED")
    return copy.deepcopy(dict(value))


def _normalize_navigation(
    contract: Mapping[str, Any],
    entries: Sequence[Mapping[str, Any]],
    *,
    expected_run_binding: str,
    expected_final_url: str,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, Mapping) or set(entry) != {"runBindingDigest", "url", "kind"}:
            raise _safe_error("BROWSER_REPORT_INVALID", f"$.navigationEvidence[{index}]: invalid")
        _require_run_binding(entry, expected_run_binding, f"$.navigationEvidence[{index}]")
        kind = str(entry["kind"])
        if kind == "new_tab":
            raise _safe_error("NEW_TAB_NOT_APPROVED", "$: observed new tab is not approved")
        if kind == "redirect":
            raise _safe_error("NAVIGATION_REDIRECT_NOT_APPROVED", "$: redirects are forbidden")
        if kind not in {"navigation", "final"}:
            raise _safe_error("BROWSER_REPORT_INVALID", f"$.navigationEvidence[{index}].kind: invalid")
        allowed = authorize_navigation(contract, str(entry["url"]))
        result.append({"runBindingDigest": expected_run_binding, "kind": kind, **allowed})
    if not result or not any(item["route"] == "/" for item in result):
        raise _safe_error("BROWSER_EVIDENCE_INCOMPLETE", "$: approved root navigation evidence is required")
    final_entries = [entry for entry in entries if entry.get("kind") == "final"]
    if len(final_entries) != 1 or final_entries[0].get("url") != expected_final_url:
        raise _safe_error("FINAL_URL_MISMATCH", "$: final URL does not match the frozen expected URL")
    return result


def _normalize_interactions(
    contract: Mapping[str, Any], entries: Sequence[Mapping[str, Any]], *, expected_run_binding: str
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    observed: dict[tuple[str, str], tuple[str, ...]] = {}
    required = {
        "runBindingDigest", "target", "operation", "claimedActionKind", "domSnapshot", "observedStates", "result"
    }
    for index, entry in enumerate(entries):
        if not isinstance(entry, Mapping) or set(entry) != required or entry["result"] != "PASS":
            raise _safe_error("BROWSER_REPORT_INVALID", f"$.interactionEvidence[{index}]: invalid")
        _require_run_binding(entry, expected_run_binding, f"$.interactionEvidence[{index}]")
        target = str(entry["target"])
        operation = str(entry["operation"])
        permit = authorize_dom_action(
            contract,
            entry["domSnapshot"],
            operation,
            claimed_action_kind=str(entry["claimedActionKind"]),
        )
        if permit["actionKind"] != entry["claimedActionKind"]:
            raise _safe_error("ACTION_DOM_MISMATCH", "$: claimed action kind differs from DOM classifier")
        states = entry["observedStates"]
        if not isinstance(states, list) or any(not isinstance(item, str) for item in states):
            raise _safe_error("BROWSER_REPORT_INVALID", f"$.interactionEvidence[{index}].observedStates: invalid")
        key = (target, operation)
        if key in observed:
            raise _safe_error("BROWSER_REPORT_INVALID", "$: duplicate interaction target")
        observed[key] = tuple(states)
        result.append(
            {
                "runBindingDigest": expected_run_binding,
                "target": target,
                "operation": operation,
                "actionKind": permit["actionKind"],
                "targetSnapshotDigest": permit["targetSnapshotDigest"],
                "observedStates": list(states),
                "result": "PASS",
            }
        )
    if set(observed) != set(REQUIRED_INTERACTIONS):
        raise _safe_error("BROWSER_EVIDENCE_INCOMPLETE", "$: required real interaction state sequences are incomplete")
    for key, expected_states in REQUIRED_INTERACTIONS.items():
        actual_states = observed[key]
        if actual_states == expected_states:
            continue
        if len(actual_states) == len(expected_states) and set(actual_states) == set(expected_states):
            raise _safe_error("BROWSER_REPORT_CROSS_FIELD_INVALID", f"$: interaction state order is invalid for {key[0]}")
        raise _safe_error("BROWSER_EVIDENCE_INCOMPLETE", f"$: interaction states are incomplete for {key[0]}")
    return result


def _normalize_blocked_actions(
    contract: Mapping[str, Any], entries: Sequence[Mapping[str, Any]], *, expected_run_binding: str
) -> list[dict[str, Any]]:
    required = {
        "runBindingDigest", "target", "operation", "domSnapshot", "expectedCode", "guardAppliedBeforeAction",
        "actionExecuted", "tabDelta", "networkRequests", "urlChanged",
    }
    result: list[dict[str, Any]] = []
    actual_by_target: dict[str, str] = {}
    for index, entry in enumerate(entries):
        if not isinstance(entry, Mapping) or set(entry) != required:
            raise _safe_error("BROWSER_REPORT_INVALID", f"$.blockedActions[{index}]: invalid")
        _require_run_binding(entry, expected_run_binding, f"$.blockedActions[{index}]")
        if (
            entry["guardAppliedBeforeAction"] is not True
            or entry["actionExecuted"] is not False
            or entry["tabDelta"] != 0
            or entry["networkRequests"] != 0
            or entry["urlChanged"] is not False
        ):
            raise _safe_error("BROWSER_EVIDENCE_INCOMPLETE", "$: blocked action lacks pre-action guard evidence")
        try:
            authorize_dom_action(contract, entry["domSnapshot"], str(entry["operation"]))
        except ContractViolation as error:
            actual_code = error.code
        else:
            raise _safe_error("BROWSER_EVIDENCE_INCOMPLETE", "$: action claimed blocked but classifier allowed it")
        if actual_code != entry["expectedCode"]:
            raise _safe_error("ACTION_DOM_MISMATCH", "$: blocked action code does not match DOM semantics")
        target = str(entry["target"])
        actual_by_target[target] = actual_code
        result.append(
            {
                "runBindingDigest": expected_run_binding,
                "target": target,
                "operation": str(entry["operation"]),
                "targetSnapshotDigest": digest_json(_normalize_dom_snapshot(entry["domSnapshot"])),
                "code": actual_code,
                "guardAppliedBeforeAction": True,
                "actionExecuted": False,
                "tabDelta": 0,
                "networkRequests": 0,
                "urlChanged": False,
            }
        )
    expected = {"external-link": "ORIGIN_NOT_APPROVED", "approval-action": "SIDE_EFFECT_BLOCKED"}
    if actual_by_target != expected:
        raise _safe_error("BROWSER_EVIDENCE_INCOMPLETE", "$: required pre-click blocked actions are incomplete")
    return result


def _normalize_host_evidence(
    contract: Mapping[str, Any],
    evidence: Mapping[str, Any],
    *,
    evidence_resolver: Callable[[str], bool],
) -> tuple[dict[str, Any], str, str | None]:
    required = {
        "session", "navigationEvidence", "interactionEvidence", "geometryEvidence", "screenshotEvidence",
        "consoleEvidence", "networkEvidence", "serverRequestLog", "networkComplete", "controlledFixtureManifest",
        "blockedActions", "expectedFinalUrl", "finalUrl", "tabDelta", "cleanup",
    }
    if not isinstance(evidence, Mapping) or set(evidence) != required:
        raise _safe_error("BROWSER_REPORT_INVALID", "$: host evidence field set is invalid")
    cleanup = validate_cleanup(evidence["cleanup"])
    probe = evaluate_capability_probe(contract, evidence["session"], evidence_resolver=evidence_resolver)
    run_binding = probe["sessionBindingDigest"]
    expected_final_url = contract["approvedOrigins"][0] + "/"
    if evidence["expectedFinalUrl"] != expected_final_url:
        raise _safe_error("BROWSER_REPORT_CROSS_FIELD_INVALID", "$: expected final URL differs from contract")
    if probe["result"] != "PASS":
        for key in (
            "navigationEvidence", "interactionEvidence", "geometryEvidence", "screenshotEvidence",
            "consoleEvidence", "networkEvidence", "blockedActions",
        ):
            if evidence[key] not in ([], ()):
                raise _safe_error("BROWSER_REPORT_INVALID", "$: downgraded probe must not claim Standard evidence")
        if evidence["finalUrl"] is not None or evidence["tabDelta"] != 0:
            raise _safe_error("BROWSER_REPORT_INVALID", "$: downgraded probe cannot claim final URL/tab evidence")
        normalized = {
            "capabilityProbe": probe,
            "runBindingDigest": run_binding,
            "expectedFinalUrl": expected_final_url,
            "finalUrl": None,
            "tabDelta": 0,
            "navigationEvidence": [],
            "interactionEvidence": [],
            "geometryEvidence": [],
            "screenshotEvidence": [],
            "consoleEvidence": [],
            "networkEvidence": [],
            "serverRequestLog": [],
            "controlledFixtureManifest": {},
            "networkSetDigest": None,
            "blockedActions": [],
            "cleanup": cleanup,
            "redactionMetrics": {"inputCount": 0, "outputCount": 0, "rawOccurrences": 0},
        }
        return normalized, "NOT_VERIFIED", str(probe["errorCode"])
    if evidence["finalUrl"] != expected_final_url:
        raise _safe_error("FINAL_URL_MISMATCH", "$: final URL does not match frozen root URL")
    if evidence["tabDelta"] != 0:
        raise _safe_error("NEW_TAB_NOT_APPROVED", "$: unexpected controlled tab delta")
    navigation = _normalize_navigation(
        contract,
        list(evidence["navigationEvidence"]),
        expected_run_binding=run_binding,
        expected_final_url=expected_final_url,
    )
    interactions = _normalize_interactions(
        contract, list(evidence["interactionEvidence"]), expected_run_binding=run_binding
    )
    geometries = [
        validate_geometry_evidence(item, expected_run_binding=run_binding) for item in evidence["geometryEvidence"]
    ]
    viewport_keys = [(item["viewport"]["width"], item["viewport"]["height"]) for item in geometries]
    if len(viewport_keys) != len(set(viewport_keys)):
        raise _safe_error("BROWSER_REPORT_CROSS_FIELD_INVALID", "$: duplicate geometry viewport")
    if len(geometries) != len(EXPECTED_VIEWPORTS) or set(viewport_keys) != set(EXPECTED_VIEWPORTS):
        raise _safe_error("BROWSER_EVIDENCE_INCOMPLETE", "$: exact three-viewport geometry matrix is required")
    screenshots = [
        validate_screenshot_evidence(contract, item, expected_run_binding=run_binding)
        for item in evidence["screenshotEvidence"]
    ]
    screenshot_keys = [
        (item["viewport"]["width"], item["viewport"]["height"], item["label"]) for item in screenshots
    ]
    if len(screenshot_keys) != len(set(screenshot_keys)):
        raise _safe_error("BROWSER_REPORT_CROSS_FIELD_INVALID", "$: duplicate screenshot pair")
    expected_pairs = {(width, height, label) for width, height in EXPECTED_VIEWPORTS for label in ("before", "after")}
    if len(screenshots) != 6 or set(screenshot_keys) != expected_pairs:
        raise _safe_error("BROWSER_EVIDENCE_INCOMPLETE", "$: six exact viewport before/after screenshot bytes are required")
    consoles = sanitize_console_evidence(
        contract, evidence["consoleEvidence"], expected_run_binding=run_binding
    )
    event_codes = {item["eventCode"] for item in consoles}
    if not {"ASYNC_SUCCESS", "NETWORK_FAILURE_503"} <= event_codes:
        raise _safe_error("BROWSER_EVIDENCE_INCOMPLETE", "$: required console event codes are missing")
    success_events = [item for item in consoles if item["eventCode"] == "ASYNC_SUCCESS"]
    failure_events = [item for item in consoles if item["eventCode"] == "NETWORK_FAILURE_503"]
    if len(success_events) != 1 or success_events[0]["relatedTarget"] != "load-status":
        raise _safe_error("BROWSER_REPORT_CROSS_FIELD_INVALID", "$: ASYNC_SUCCESS is not bound to load-status")
    if len(failure_events) != 1 or any(
        failure_events[0][key] != expected
        for key, expected in {
            "relatedTarget": "simulate-failure",
            "relatedMethod": "GET",
            "relatedRoute": "/api/fail",
            "relatedStatus": 503,
        }.items()
    ):
        raise _safe_error("BROWSER_REPORT_CROSS_FIELD_INVALID", "$: NETWORK_FAILURE_503 binding is invalid")
    manifest = validate_controlled_fixture_manifest(evidence["controlledFixtureManifest"])
    receipt_mode = any(
        isinstance(item, Mapping) and "witnessReceipt" in item
        for item in list(evidence["networkEvidence"]) + list(evidence["serverRequestLog"])
    )
    if receipt_mode:
        reconciled = reconcile_response_receipt_evidence(
            contract,
            list(evidence["networkEvidence"]),
            list(evidence["serverRequestLog"]),
            network_complete=evidence["networkComplete"],
            expected_run_binding=run_binding,
        )
    else:
        reconciled = reconcile_network_evidence(
            contract,
            list(evidence["networkEvidence"]),
            list(evidence["serverRequestLog"]),
            network_complete=evidence["networkComplete"],
            expected_run_binding=run_binding,
        )
    networks = reconciled["browserEvidence"]
    required_routes = {"/", "/styles.css", "/app.js", "/api/fail"}
    if not required_routes <= {item["route"] for item in networks}:
        raise _safe_error("BROWSER_EVIDENCE_INCOMPLETE", "$: required document/static/failure network cases are missing")
    failure_requests = [item for item in networks if item["method"] == "GET" and item["route"] == "/api/fail"]
    if not failure_requests:
        raise _safe_error("BROWSER_EVIDENCE_INCOMPLETE", "$: controlled 503 evidence is missing")
    if any(item["status"] != 503 for item in failure_requests):
        raise _safe_error("CONTROLLED_503_MISMATCH", "$: GET /api/fail must be exactly 503")
    blocked = _normalize_blocked_actions(
        contract, list(evidence["blockedActions"]), expected_run_binding=run_binding
    )
    redaction_metrics = validate_redaction_counts(
        len(evidence["consoleEvidence"]) + len(evidence["networkEvidence"]),
        len(consoles) + len(networks),
        {"consoleEvidence": consoles, "networkEvidence": networks},
    )
    normalized = {
        "capabilityProbe": probe,
        "runBindingDigest": run_binding,
        "expectedFinalUrl": expected_final_url,
        "finalUrl": expected_final_url,
        "tabDelta": 0,
        "navigationEvidence": navigation,
        "interactionEvidence": interactions,
        "geometryEvidence": sorted(geometries, key=lambda item: (item["viewport"]["width"], item["viewport"]["height"])),
        "screenshotEvidence": sorted(
            screenshots,
            key=lambda item: (item["viewport"]["width"], item["viewport"]["height"], item["label"]),
        ),
        "consoleEvidence": consoles,
        "networkEvidence": networks,
        "serverRequestLog": reconciled["serverRequestLog"],
        "controlledFixtureManifest": manifest,
        # The serialized Browser report keeps the legacy metadata multiset
        # digest so its existing schema validator can recompute it.  The
        # receipt-bearing host evidence is independently bound by
        # hostEvidenceDigest, while reconcile_response_receipt_evidence also
        # exposes witnessSetDigest to the orchestrator ledger.
        "networkSetDigest": reconciled["networkSetDigest"],
        "blockedActions": blocked,
        "cleanup": cleanup,
        "redactionMetrics": redaction_metrics,
    }
    return normalized, "PASS", None


def bind_trusted_browser_evidence(
    contract: Mapping[str, Any],
    authorization_context: TrustedBrowserAuthorizationContext | None,
    run_guard: BrowserRunGuard | None,
    evidence: Mapping[str, Any],
    *,
    evidence_ref: str,
    evidence_resolver: Callable[[str], bool],
) -> TrustedBrowserEvidenceReceipt:
    contract_value = validate_browser_contract(contract)
    context = _require_authorization(authorization_context)
    if not isinstance(run_guard, BrowserRunGuard) or run_guard._authority is not _TRUSTED_BROWSER_AUTHORITY:
        raise _safe_error("HOST_TOOL_EVIDENCE_UNAVAILABLE", "$: Browser run guard is required")
    if not run_guard.finalized:
        raise _safe_error("BROWSER_FINALIZE_REQUIRED", "$: Browser run must be finalized before evidence binding")
    if (
        run_guard.last_browser_action != "browser.tabs.finalize"
        or run_guard.browser_actions_after_finalize != 0
        or not isinstance(evidence, Mapping)
        or not isinstance(evidence.get("cleanup"), Mapping)
        or evidence["cleanup"].get("lastBrowserAction") != run_guard.last_browser_action
        or evidence["cleanup"].get("browserActionsAfterFinalize") != run_guard.browser_actions_after_finalize
    ):
        raise _safe_error("BROWSER_FINALIZE_REQUIRED", "$: browser.tabs.finalize must be the final Browser action")
    if run_guard.run_id in _CONSUMED_RUN_IDS:
        raise _safe_error("BROWSER_EVIDENCE_REPLAYED", "$: Browser run evidence was already consumed")
    if not isinstance(evidence, Mapping) or not isinstance(evidence.get("session"), Mapping) or (
        evidence["session"].get("runId") != run_guard.run_id
    ):
        raise _safe_error("BROWSER_EVIDENCE_REPLAYED", "$: Browser evidence runId does not match current run")
    if (
        context.task_id != contract_value["taskId"]
        or context.approved_contract_digest != digest_json(
            {key: value for key, value in contract_value.items() if key not in {"approvalEvidenceRef", "contractDigest"}}
        )
        or context.evidence_ref != contract_value["approvalEvidenceRef"]
    ):
        raise _safe_error("BROWSER_APPROVAL_BINDING_MISMATCH", "$: approval does not match Browser contract")
    reference = _validated_ref(evidence_ref, code="TRUSTED_BROWSER_RECEIPT_REQUIRED")
    _resolve_host_evidence(reference, evidence_resolver, code="TRUSTED_BROWSER_RECEIPT_REQUIRED")
    normalized, result, error_code = _normalize_host_evidence(
        contract_value,
        evidence,
        evidence_resolver=evidence_resolver,
    )
    _CONSUMED_RUN_IDS.add(run_guard.run_id)
    evidence_json = canonical_json(normalized)
    probe = normalized["capabilityProbe"]
    return TrustedBrowserEvidenceReceipt(
        task_id=contract_value["taskId"],
        contract_digest=contract_value["contractDigest"],
        evidence_ref=reference,
        evidence_digest=digest_json(normalized),
        session_binding_digest=probe["sessionBindingDigest"],
        result=result,
        error_code=error_code,
        _contract_json=canonical_json(contract_value),
        _evidence_json=evidence_json,
        _authority=_TRUSTED_BROWSER_AUTHORITY,
    )


def _require_evidence_receipt(receipt: TrustedBrowserEvidenceReceipt | None) -> TrustedBrowserEvidenceReceipt:
    if not isinstance(receipt, TrustedBrowserEvidenceReceipt) or receipt._authority is not _TRUSTED_BROWSER_AUTHORITY:
        raise _safe_error("TRUSTED_BROWSER_RECEIPT_REQUIRED", "$: non-serializable trusted Browser evidence receipt is required")
    return receipt


def _assert_no_sensitive_serialized(value: Any) -> None:
    def visit(item: Any) -> None:
        if isinstance(item, Mapping):
            for key, nested in item.items():
                visit(key)
                visit(nested)
            return
        if isinstance(item, (list, tuple, set, frozenset)):
            for nested in item:
                visit(nested)
            return
        if not isinstance(item, str):
            return
        # Fixed lowercase SHA-256 values are opaque consistency identifiers. Scanning
        # their random hexadecimal digits as phone/ID text creates false positives.
        if re.fullmatch(r"[0-9a-f]{64}", item):
            return
        if SENSITIVE_MARKER in item or SENSITIVE_SERIALIZED_RE.search(item) or ID_NUMBER_RE.search(item):
            raise _safe_error("SENSITIVE_EVIDENCE_REJECTED", "$: report contains unredacted sensitive evidence")

    visit(value)


def build_browser_safety_report(
    contract: Mapping[str, Any],
    receipt: TrustedBrowserEvidenceReceipt | None,
) -> dict[str, Any]:
    contract_value = validate_browser_contract(contract)
    trusted = _require_evidence_receipt(receipt)
    if (
        trusted.task_id != contract_value["taskId"]
        or trusted.contract_digest != contract_value["contractDigest"]
        or trusted._contract_json != canonical_json(contract_value)
    ):
        raise _safe_error("BROWSER_RECEIPT_MISMATCH", "$: receipt is bound to another Browser contract")
    evidence = json.loads(trusted._evidence_json)
    if trusted.evidence_digest != digest_json(evidence):
        raise _safe_error("BROWSER_RECEIPT_MISMATCH", "$: receipt evidence digest mismatch")
    probe = evidence["capabilityProbe"]
    candidate_result = trusted.result
    if candidate_result == "PASS":
        verified_items = [
            "candidate: process-local Browser contract/session consistency",
            "candidate: controlled loopback manifest and bidirectional network reconciliation",
            "candidate: DOM-bound menu/input/loading-success/loading-error interactions",
            "candidate: six V1 cropped screenshot byte hashes with selector exclusion",
            "candidate: V2 three-viewport geometry, overflow and occlusion",
            "candidate: fixed-enum console/network redaction and controlled 503",
            "candidate: task resource finalization fields",
        ]
        effective_error = "HOST_ATTESTATION_UNAVAILABLE"
    else:
        verified_items = ["candidate: Browser safety contract", "candidate: task resource finalization fields"]
        effective_error = str(trusted.error_code)
    report: dict[str, Any] = {
        "schemaVersion": "3",
        "taskId": contract_value["taskId"],
        "candidateResult": candidate_result,
        "candidateErrorCode": trusted.error_code,
        "result": "NOT_VERIFIED",
        "effectiveResult": "NOT_VERIFIED",
        "errorCode": effective_error,
        "authorityVerified": False,
        "executionLayer": "Lite",
        "environmentClass": contract_value["environmentClass"],
        "approvedOrigins": list(contract_value["approvedOrigins"]),
        "approvedRoutes": list(contract_value["approvedRoutes"]),
        "contractDigest": contract_value["contractDigest"],
        "digestPurpose": "consistency_only",
        "productionReadOnly": True,
        "sideEffectPolicy": "read_only",
        "downloadPolicy": "block",
        "networkEvidenceMode": "metadata_enum_only",
        "networkGuardMode": contract_value["networkGuardMode"],
        "runBindingDigest": evidence["runBindingDigest"],
        "expectedFinalUrl": evidence["expectedFinalUrl"],
        "finalUrl": evidence["finalUrl"],
        "tabDelta": evidence["tabDelta"],
        "browserContext": {
            "role": contract_value["role"],
            "browserName": probe["browserName"],
            "browserType": probe["browserType"],
            "engine": probe["engine"],
            "isolationKind": probe["isolationKind"],
            "sessionBindingDigest": probe["sessionBindingDigest"],
            "contextEvidenceRef": probe["contextEvidenceRef"],
            "tabOwnedByTask": probe["tabOwnedByTask"],
            "initialControlledTabs": probe["initialControlledTabs"],
            "personalProfileUsed": probe["personalProfileUsed"],
            "userTabClaimed": probe["userTabClaimed"],
            "historyRead": probe["historyRead"],
            "cookiesRead": probe["cookiesRead"],
            "storageRead": probe["storageRead"],
        },
        "capabilityProbe": probe,
        "navigationEvidence": evidence["navigationEvidence"],
        "interactionEvidence": evidence["interactionEvidence"],
        "geometryEvidence": evidence["geometryEvidence"],
        "screenshotEvidence": evidence["screenshotEvidence"],
        "consoleEvidence": evidence["consoleEvidence"],
        "networkEvidence": evidence["networkEvidence"],
        "serverRequestLog": evidence["serverRequestLog"],
        "controlledFixtureManifestDigest": evidence.get("controlledFixtureManifest", {}).get("manifestDigest"),
        "networkSetDigest": evidence.get("networkSetDigest"),
        "blockedActions": evidence["blockedActions"],
        "cleanup": evidence["cleanup"],
        "redactionMetrics": evidence["redactionMetrics"],
        "hostEvidenceRef": trusted.evidence_ref,
        "hostEvidenceDigest": trusted.evidence_digest,
        "authorityMode": "external_tool_review_required",
        "receiptBound": True,
        "verifiedItems": verified_items,
        "unverifiedItems": [effective_error],
        "hardMetrics": {
            "unauthorizedWrites": 0,
            "originEscapes": 0,
            "personalProfileReads": 0,
            "sensitiveInformationLeaks": 0,
            "unclearedTaskResources": 0,
        },
        "redactionStatus": "PASS",
    }
    _assert_no_sensitive_serialized(report)
    report["reportDigest"] = digest_json(report)
    validate_browser_report_structure(report)
    return report


def _validate_serialized_screenshot(value: Mapping[str, Any]) -> None:
    required = {
        "runBindingDigest", "label", "viewport", "clip", "pixelSize", "sensitiveSelectorMatchCounts",
        "sensitiveRects", "coordinateSpace", "scrollX", "scrollY", "sha256", "size", "persisted",
    }
    if not isinstance(value, Mapping) or set(value) != required:
        raise _safe_error("BROWSER_REPORT_INVALID", "$.screenshotEvidence: invalid field set")
    if value["label"] not in {"before", "after"} or not isinstance(value["viewport"], Mapping) or (
        value["viewport"].get("width"), value["viewport"].get("height")
    ) not in EXPECTED_VIEWPORTS:
        raise _safe_error("BROWSER_REPORT_INVALID", "$.screenshotEvidence: invalid label/viewport")
    if not isinstance(value["runBindingDigest"], str) or re.fullmatch(r"[0-9a-f]{64}", value["runBindingDigest"]) is None:
        raise _safe_error("BROWSER_REPORT_INVALID", "$.screenshotEvidence.runBindingDigest: invalid")
    clip = _valid_rect(value["clip"], "$.screenshotEvidence.clip")
    pixel_size = value["pixelSize"]
    if not isinstance(pixel_size, Mapping) or set(pixel_size) != {"width", "height"} or any(
        not isinstance(pixel_size[key], int) or pixel_size[key] <= 0 for key in pixel_size
    ):
        raise _safe_error("BROWSER_REPORT_INVALID", "$.screenshotEvidence.pixelSize: invalid")
    rects = [_valid_rect(item, "$.screenshotEvidence.sensitiveRects") for item in value["sensitiveRects"]]
    if not isinstance(value["sensitiveSelectorMatchCounts"], Mapping) or not value["sensitiveSelectorMatchCounts"]:
        raise _safe_error("BROWSER_REPORT_INVALID", "$.screenshotEvidence: selector counts required")
    if any(not isinstance(count, int) or count <= 0 for count in value["sensitiveSelectorMatchCounts"].values()):
        raise _safe_error("BROWSER_REPORT_INVALID", "$.screenshotEvidence: invalid selector count")
    if sum(value["sensitiveSelectorMatchCounts"].values()) != len(rects):
        raise _safe_error("BROWSER_REPORT_CROSS_FIELD_INVALID", "$: selector match counts do not match sensitive rects")
    if any(_rects_intersect(clip, rect) for rect in rects):
        raise _safe_error("SENSITIVE_EVIDENCE_REJECTED", "$: serialized screenshot intersects sensitive rect")
    if (
        value["coordinateSpace"] != "viewport_css_pixels" or value["scrollX"] != 0 or value["scrollY"] != 0
        or not isinstance(value["sha256"], str) or re.fullmatch(r"[0-9a-f]{64}", value["sha256"]) is None
        or not isinstance(value["size"], int) or value["size"] <= 8 or value["persisted"] is not False
    ):
        raise _safe_error("BROWSER_REPORT_INVALID", "$.screenshotEvidence: invalid normalized metadata")


def validate_browser_report_structure(value: Mapping[str, Any]) -> dict[str, Any]:
    required = {
        "schemaVersion", "taskId", "candidateResult", "candidateErrorCode", "result", "effectiveResult",
        "errorCode", "authorityVerified", "executionLayer", "environmentClass", "approvedOrigins", "approvedRoutes",
        "contractDigest", "digestPurpose", "productionReadOnly", "sideEffectPolicy", "downloadPolicy",
        "networkEvidenceMode", "networkGuardMode", "runBindingDigest", "expectedFinalUrl", "finalUrl", "tabDelta",
        "browserContext", "capabilityProbe", "navigationEvidence",
        "interactionEvidence", "geometryEvidence", "screenshotEvidence", "consoleEvidence", "networkEvidence",
        "serverRequestLog", "controlledFixtureManifestDigest", "networkSetDigest", "blockedActions", "cleanup",
        "redactionMetrics", "hostEvidenceRef", "hostEvidenceDigest", "authorityMode", "receiptBound",
        "verifiedItems", "unverifiedItems", "hardMetrics", "redactionStatus", "reportDigest",
    }
    if not isinstance(value, Mapping) or set(value) != required:
        raise _safe_error("BROWSER_REPORT_INVALID", "$: invalid Browser candidate report field set")
    if value.get("schemaVersion") != "3" or value.get("candidateResult") not in RESULTS:
        raise _safe_error("BROWSER_REPORT_INVALID", "$: invalid candidate report header")
    _validated_task_id(value.get("taskId"))
    _validated_ref(value.get("hostEvidenceRef"), code="BROWSER_REPORT_INVALID")
    if (
        value.get("result") != "NOT_VERIFIED" or value.get("effectiveResult") != "NOT_VERIFIED"
        or value.get("authorityVerified") is not False or value.get("executionLayer") != "Lite"
        or value.get("digestPurpose") != "consistency_only" or value.get("productionReadOnly") is not True
        or value.get("sideEffectPolicy") != "read_only" or value.get("downloadPolicy") != "block"
        or value.get("networkEvidenceMode") != "metadata_enum_only"
        or value.get("networkGuardMode") != "controlled_loopback_manifest"
        or value.get("authorityMode") != "external_tool_review_required"
        or value.get("receiptBound") is not True or value.get("redactionStatus") != "PASS"
    ):
        raise _safe_error("BROWSER_REPORT_CROSS_FIELD_INVALID", "$: runtime authority/policy boundary is invalid")
    for key in ("contractDigest", "hostEvidenceDigest"):
        if not isinstance(value.get(key), str) or re.fullmatch(r"[0-9a-f]{64}", value[key]) is None:
            raise _safe_error("BROWSER_REPORT_INVALID", f"$.{key}: invalid")
    if not isinstance(value["runBindingDigest"], str) or re.fullmatch(r"[0-9a-f]{64}", value["runBindingDigest"]) is None:
        raise _safe_error("BROWSER_REPORT_INVALID", "$.runBindingDigest: invalid")
    origins = _normalize_string_list(value.get("approvedOrigins"), "$.approvedOrigins")
    routes = _normalize_string_list(value.get("approvedRoutes"), "$.approvedRoutes")
    if origins != [_normalize_origin(item, approved_value=True) for item in origins] or routes != [_normalize_route(item) for item in routes]:
        raise _safe_error("BROWSER_REPORT_INVALID", "$: report Origins/routes not normalized")
    if value["tabDelta"] != 0 or value["expectedFinalUrl"] != origins[0] + "/":
        raise _safe_error("BROWSER_REPORT_CROSS_FIELD_INVALID", "$: final URL/tab contract is invalid")
    cleanup = validate_cleanup(value["cleanup"])
    expected_metrics = {
        "unauthorizedWrites": 0,
        "originEscapes": 0,
        "personalProfileReads": 0,
        "sensitiveInformationLeaks": 0,
        "unclearedTaskResources": 0,
    }
    if value["hardMetrics"] != expected_metrics or cleanup != value["cleanup"]:
        raise _safe_error("BROWSER_REPORT_CROSS_FIELD_INVALID", "$: hard metrics/cleanup invalid")
    probe = value["capabilityProbe"]
    if not isinstance(probe, Mapping) or not isinstance(probe.get("features"), Mapping) or set(probe["features"]) != REQUIRED_PROBE_FLAGS:
        raise _safe_error("BROWSER_REPORT_INVALID", "$.capabilityProbe: invalid")
    if any(not isinstance(item, bool) for item in probe["features"].values()):
        raise _safe_error("BROWSER_REPORT_INVALID", "$.capabilityProbe.features: invalid")
    context = value["browserContext"]
    context_required = {
        "role", "browserName", "browserType", "engine", "isolationKind", "sessionBindingDigest", "contextEvidenceRef",
        "tabOwnedByTask", "initialControlledTabs", "personalProfileUsed", "userTabClaimed", "historyRead", "cookiesRead",
        "storageRead",
    }
    if not isinstance(context, Mapping) or set(context) != context_required:
        raise _safe_error("BROWSER_REPORT_INVALID", "$.browserContext: invalid")
    if (
        context["sessionBindingDigest"] != probe.get("sessionBindingDigest")
        or value["runBindingDigest"] != context["sessionBindingDigest"]
        or context["contextEvidenceRef"] != probe.get("contextEvidenceRef")
        or context["tabOwnedByTask"] is not True or context["initialControlledTabs"] != 0
        or any(context[key] is not False for key in ("personalProfileUsed", "userTabClaimed", "historyRead", "cookiesRead", "storageRead"))
    ):
        raise _safe_error("BROWSER_REPORT_CROSS_FIELD_INVALID", "$.browserContext: cross-field mismatch")
    redaction = value["redactionMetrics"]
    if redaction != {
        "inputCount": len(value["consoleEvidence"]) + len(value["networkEvidence"]),
        "outputCount": len(value["consoleEvidence"]) + len(value["networkEvidence"]),
        "rawOccurrences": 0,
    }:
        raise _safe_error("REDACTION_COUNT_MISMATCH", "$: report redaction counts do not match safe outputs")

    if value["candidateResult"] == "PASS":
        if (
            value["candidateErrorCode"] is not None or value["errorCode"] != "HOST_ATTESTATION_UNAVAILABLE"
            or value["unverifiedItems"] != ["HOST_ATTESTATION_UNAVAILABLE"]
            or probe.get("result") != "PASS" or probe.get("errorCode") is not None
            or any(item is not True for item in probe["features"].values())
            or context["browserName"] != EXPECTED_BROWSER["browserName"]
            or context["browserType"] != EXPECTED_BROWSER["browserType"]
            or context["engine"] != EXPECTED_BROWSER["engine"]
            or context["isolationKind"] != EXPECTED_BROWSER["isolationKind"]
        ):
            raise _safe_error("BROWSER_REPORT_CROSS_FIELD_INVALID", "$: candidate PASS capability/authority contract failed")
        if value["finalUrl"] != value["expectedFinalUrl"]:
            raise _safe_error("FINAL_URL_MISMATCH", "$: candidate final URL mismatch")
        if not value["navigationEvidence"] or not value["interactionEvidence"] or not value["networkEvidence"]:
            raise _safe_error("BROWSER_REPORT_CROSS_FIELD_INVALID", "$: candidate PASS evidence arrays cannot be empty")
        for array_name in (
            "navigationEvidence", "interactionEvidence", "geometryEvidence", "screenshotEvidence", "consoleEvidence",
            "networkEvidence", "serverRequestLog", "blockedActions",
        ):
            if not isinstance(value[array_name], list):
                raise _safe_error("BROWSER_REPORT_INVALID", f"$.{array_name}: expected array")
            for index, item in enumerate(value[array_name]):
                if not isinstance(item, Mapping):
                    raise _safe_error("BROWSER_REPORT_INVALID", f"$.{array_name}[{index}]: invalid")
                _require_run_binding(item, value["runBindingDigest"], f"$.{array_name}[{index}]")
        final_navigation = [item for item in value["navigationEvidence"] if item.get("kind") == "final"]
        if (
            len(final_navigation) != 1
            or final_navigation[0].get("origin") != origins[0]
            or final_navigation[0].get("route") != "/"
            or any(item.get("kind") not in {"navigation", "final"} for item in value["navigationEvidence"])
        ):
            raise _safe_error("FINAL_URL_MISMATCH", "$: serialized final navigation evidence is invalid")
        geometries = [
            validate_geometry_evidence(item, expected_run_binding=value["runBindingDigest"])
            for item in value["geometryEvidence"]
        ]
        if len(geometries) != 3 or {
            (item["viewport"]["width"], item["viewport"]["height"]) for item in geometries
        } != set(EXPECTED_VIEWPORTS):
            raise _safe_error("BROWSER_REPORT_CROSS_FIELD_INVALID", "$: candidate viewport matrix invalid")
        if len(value["screenshotEvidence"]) != 6:
            raise _safe_error("BROWSER_REPORT_CROSS_FIELD_INVALID", "$: candidate screenshot count invalid")
        for screenshot in value["screenshotEvidence"]:
            _validate_serialized_screenshot(screenshot)
        pairs = {
            (item["viewport"]["width"], item["viewport"]["height"], item["label"])
            for item in value["screenshotEvidence"]
        }
        expected_pairs = {(width, height, label) for width, height in EXPECTED_VIEWPORTS for label in ("before", "after")}
        if pairs != expected_pairs:
            raise _safe_error("BROWSER_REPORT_CROSS_FIELD_INVALID", "$: candidate screenshot pair matrix invalid")
        interactions = {
            (item.get("target"), item.get("operation")): tuple(item.get("observedStates", []))
            for item in value["interactionEvidence"]
        }
        if len(value["interactionEvidence"]) != 4 or interactions != REQUIRED_INTERACTIONS:
            raise _safe_error("BROWSER_REPORT_CROSS_FIELD_INVALID", "$: candidate interaction states invalid")
        console_events = {item.get("eventCode"): item for item in value["consoleEvidence"]}
        if not {"ASYNC_SUCCESS", "NETWORK_FAILURE_503"} <= set(console_events):
            raise _safe_error("BROWSER_EVIDENCE_INCOMPLETE", "$: candidate console events are incomplete")
        if console_events["ASYNC_SUCCESS"].get("relatedTarget") != "load-status" or any(
            console_events["NETWORK_FAILURE_503"].get(key) != expected
            for key, expected in {
                "relatedTarget": "simulate-failure",
                "relatedMethod": "GET",
                "relatedRoute": "/api/fail",
                "relatedStatus": 503,
            }.items()
        ):
            raise _safe_error("BROWSER_REPORT_CROSS_FIELD_INVALID", "$: candidate console correlation is invalid")
        for item in value["networkEvidence"]:
            if (
                item.get("origin") not in origins
                or item.get("route") not in routes
                or item.get("method") not in ALLOWED_METHODS
                or not isinstance(item.get("status"), int)
                or 300 <= item.get("status") < 400
            ):
                raise _safe_error("BROWSER_REPORT_CROSS_FIELD_INVALID", "$: candidate network escaped approved boundary")
        failure_requests = [
            item for item in value["networkEvidence"] if item.get("method") == "GET" and item.get("route") == "/api/fail"
        ]
        if not failure_requests:
            raise _safe_error("BROWSER_EVIDENCE_INCOMPLETE", "$: candidate 503 evidence missing")
        if any(item.get("status") != 503 for item in failure_requests):
            raise _safe_error("CONTROLLED_503_MISMATCH", "$: candidate GET /api/fail must be 503")
        browser_counter = Counter((item.get("method"), item.get("route"), item.get("status")) for item in value["networkEvidence"])
        server_counter = Counter((item.get("method"), item.get("route"), item.get("status")) for item in value["serverRequestLog"])
        if browser_counter != server_counter:
            raise _safe_error("NETWORK_EVIDENCE_MISMATCH", "$: serialized Browser/server network sets differ")
        expected_network_digest = _network_set_digest(browser_counter)
        if value["networkSetDigest"] != expected_network_digest:
            raise _safe_error("BROWSER_REPORT_CROSS_FIELD_INVALID", "$.networkSetDigest: mismatch")
        if not isinstance(value["controlledFixtureManifestDigest"], str) or re.fullmatch(
            r"[0-9a-f]{64}", value["controlledFixtureManifestDigest"]
        ) is None:
            raise _safe_error("BROWSER_REPORT_CROSS_FIELD_INVALID", "$: controlled manifest digest missing")
        blocked = {item.get("target"): item.get("code") for item in value["blockedActions"]}
        if blocked != {"external-link": "ORIGIN_NOT_APPROVED", "approval-action": "SIDE_EFFECT_BLOCKED"}:
            raise _safe_error("BROWSER_REPORT_CROSS_FIELD_INVALID", "$: candidate blocked-action evidence invalid")
        if any(
            item.get("actionExecuted") is not False
            or item.get("tabDelta") != 0
            or item.get("networkRequests") != 0
            or item.get("urlChanged") is not False
            for item in value["blockedActions"]
        ):
            raise _safe_error("BROWSER_REPORT_CROSS_FIELD_INVALID", "$: blocked action side effects are invalid")
    else:
        if (
            not isinstance(value["candidateErrorCode"], str) or value["errorCode"] != value["candidateErrorCode"]
            or value["unverifiedItems"] != [value["errorCode"]]
            or probe.get("result") != "NOT_VERIFIED" or probe.get("errorCode") != value["candidateErrorCode"]
        ):
            raise _safe_error("BROWSER_REPORT_CROSS_FIELD_INVALID", "$: downgraded candidate cross-field contract failed")
        for key in (
            "navigationEvidence", "interactionEvidence", "geometryEvidence", "screenshotEvidence", "consoleEvidence",
            "networkEvidence", "serverRequestLog", "blockedActions",
        ):
            if value[key] != []:
                raise _safe_error("BROWSER_REPORT_CROSS_FIELD_INVALID", "$: downgraded candidate cannot claim Browser evidence")
        if value["controlledFixtureManifestDigest"] is not None or value["networkSetDigest"] is not None:
            raise _safe_error("BROWSER_REPORT_CROSS_FIELD_INVALID", "$: downgraded candidate cannot claim network binding")
        if value["finalUrl"] is not None:
            raise _safe_error("BROWSER_REPORT_CROSS_FIELD_INVALID", "$: downgraded candidate cannot claim final URL")
    digest_input = {key: copy.deepcopy(item) for key, item in value.items() if key != "reportDigest"}
    if value.get("reportDigest") != digest_json(digest_input):
        raise _safe_error("BROWSER_REPORT_INVALID", "$.reportDigest: mismatch")
    _assert_no_sensitive_serialized(value)
    return copy.deepcopy(dict(value))


def validate_browser_report(
    value: Mapping[str, Any],
    receipt: TrustedBrowserEvidenceReceipt | None = None,
) -> dict[str, Any]:
    if receipt is None:
        validate_browser_report_structure(value)
        raise _safe_error(
            "SERIALIZED_BROWSER_AUTHORITY_FORBIDDEN",
            "$: serialized Browser reports cannot establish effective or formal PASS",
        )
    trusted = _require_evidence_receipt(receipt)
    structure = validate_browser_report_structure(value)
    expected_contract = json.loads(trusted._contract_json)
    expected = build_browser_safety_report(expected_contract, trusted)
    if structure != expected:
        raise _safe_error("BROWSER_RECEIPT_MISMATCH", "$: report does not match trusted Browser evidence receipt")
    return structure


def resolve_browser_outcome(primary_error: str | None, cleanup: Mapping[str, Any]) -> dict[str, Any]:
    """Apply cleanup priority without ever returning an effective/formal PASS."""

    try:
        validate_cleanup(cleanup)
    except ContractViolation as cleanup_error:
        return {
            "candidateResult": "FAIL",
            "candidateErrorCode": cleanup_error.code,
            "effectiveResult": "NOT_VERIFIED",
            "authorityVerified": False,
            "errorCode": cleanup_error.code,
            "secondaryCode": primary_error,
            "cleanupComplete": False,
        }
    if primary_error is None:
        return {
            "candidateResult": "PASS",
            "candidateErrorCode": None,
            "effectiveResult": "NOT_VERIFIED",
            "authorityVerified": False,
            "errorCode": "HOST_ATTESTATION_UNAVAILABLE",
            "secondaryCode": None,
            "cleanupComplete": True,
        }
    not_verified = {
        "BROWSER_DISCONNECTED",
        "BROWSER_SCREENSHOT_UNAVAILABLE",
        "BROWSER_SERVER_UNAVAILABLE",
        "BROWSER_CAPABILITY_UNAVAILABLE",
        "BROWSER_ISOLATION_UNAVAILABLE",
        "BROWSER_ENGINE_UNVERIFIED",
        "BROWSER_BEFORE_SEND_GUARD_UNAVAILABLE",
        "HOST_ATTESTATION_UNAVAILABLE",
        "HOST_TOOL_EVIDENCE_UNAVAILABLE",
    }
    return {
        "candidateResult": "NOT_VERIFIED" if primary_error in not_verified else "FAIL",
        "candidateErrorCode": primary_error,
        "effectiveResult": "NOT_VERIFIED",
        "authorityVerified": False,
        "errorCode": primary_error,
        "secondaryCode": None,
        "cleanupComplete": True,
    }
