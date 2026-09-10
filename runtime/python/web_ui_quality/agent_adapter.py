"""Thin harness composition over the existing Web UI Quality Core.

This module is an integration boundary only. It normalizes harness labels,
delegates intent/capability/result work to existing Core functions, and keeps
Host authority explicitly unavailable to the adapter.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .capability_registry import build_capability_registry
from .host_bridge import bridge_request
from .task_intent_adapter import normalize_task_intent
from .task_result import build_task_result


_HARNESS_ALIASES = {
    "codex": "codex",
    "claude": "claude-code",
    "claude-code": "claude-code",
    "opencode": "opencode",
    "cursor": "cursor-vscode",
    "cursor-vscode": "cursor-vscode",
    "vs-code": "cursor-vscode",
    "cursor/vs code": "cursor-vscode",
}
SUPPORTED_HARNESSES = ("codex", "claude-code", "opencode", "cursor-vscode")
ADAPTER_CAPABILITIES = (
    "install_integration",
    "capability_discovery",
    "intent_routing",
    "authority_handshake",
    "tool_bridge",
    "result_rendering",
)
_CLAIM_BOUNDARY = (
    "Thin adapters connect a Harness to the existing Core; they do not grant "
    "Host write authority or duplicate scope, receipt, drift, evidence, or claim engines."
)


def _harness_id(value: str) -> str:
    key = str(value or "").strip().casefold()
    try:
        return _HARNESS_ALIASES[key]
    except KeyError as error:
        raise ValueError(f"unsupported harness: {value}") from error


def adapter_descriptor(harness: str) -> dict[str, Any]:
    """Describe one thin integration without claiming external verification."""
    harness_id = _harness_id(harness)
    return {
        "schemaVersion": "1",
        "adapterId": f"wuq-thin-{harness_id}",
        "harness": harness_id,
        "core": "web-ui-quality",
        "capabilities": list(ADAPTER_CAPABILITIES),
        "writeAuthorized": False,
        "externalVerification": "NOT_MEASURED",
        "claimBoundary": _CLAIM_BOUNDARY,
    }


def route_agent_request(harness: str, text: str | None) -> dict[str, Any]:
    """Route a request through the canonical Core intent adapter."""
    descriptor = adapter_descriptor(harness)
    return {
        **descriptor,
        "request": normalize_task_intent(text),
    }


def discover_agent_capabilities(
    harness: str,
    browser_executable: str | Path | None = None,
) -> dict[str, Any]:
    """Expose Core capability discovery under a Harness-specific envelope."""
    descriptor = adapter_descriptor(harness)
    return {
        **descriptor,
        "coreCapabilities": build_capability_registry(browser_executable),
    }


def build_authority_handshake(
    harness: str,
    *,
    task_id: str,
    requested_action: str = "inspect",
) -> dict[str, Any]:
    """Describe the Host handoff without authenticating or granting it."""
    descriptor = adapter_descriptor(harness)
    return {
        **descriptor,
        "taskId": str(task_id),
        "requestedAction": str(requested_action),
        "authorityStatus": "HOST_AUTHORITY_REQUIRED",
        "writeAuthorized": False,
        "claimBoundary": _CLAIM_BOUNDARY,
    }


def bridge_agent_tool(
    harness: str,
    action: str,
    *,
    task_id: str,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Forward an allow-listed bridge action while preserving the Core boundary."""
    descriptor = adapter_descriptor(harness)
    bridged = bridge_request(action, task_id=task_id, payload=payload)
    return {
        **descriptor,
        **bridged,
        "writeAuthorized": False,
        "claimBoundary": _CLAIM_BOUNDARY,
    }


def render_agent_result(
    harness: str,
    result: Mapping[str, Any],
    *,
    request: str | None = None,
) -> dict[str, Any]:
    """Render the canonical TaskResult for a Harness-specific surface."""
    descriptor = adapter_descriptor(harness)
    return {
        **descriptor,
        "taskResult": build_task_result(result, request=request),
    }


__all__ = [
    "ADAPTER_CAPABILITIES",
    "SUPPORTED_HARNESSES",
    "adapter_descriptor",
    "build_authority_handshake",
    "bridge_agent_tool",
    "discover_agent_capabilities",
    "render_agent_result",
    "route_agent_request",
]
