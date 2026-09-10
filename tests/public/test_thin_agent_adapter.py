from __future__ import annotations

from web_ui_quality.agent_adapter import (
    ADAPTER_CAPABILITIES,
    SUPPORTED_HARNESSES,
    adapter_descriptor,
    build_authority_handshake,
    bridge_agent_tool,
    discover_agent_capabilities,
    render_agent_result,
    route_agent_request,
)


def _codex_surface(payload: dict[str, str]) -> dict:
    return route_agent_request("codex", payload["prompt"])


def _claude_surface(payload: dict[str, str]) -> dict:
    return route_agent_request("claude-code", payload["message"])


def test_two_harnesses_reach_the_same_core_intent_contract() -> None:
    payload = {"prompt": "请检查移动端按钮，不要修改登录逻辑", "message": "请检查移动端按钮，不要修改登录逻辑"}
    codex = _codex_surface(payload)
    claude = _claude_surface(payload)
    assert codex["request"] == claude["request"]
    assert codex["request"]["taskIntent"] == "CHECK"
    assert codex["writeAuthorized"] is False
    assert claude["writeAuthorized"] is False
    assert codex["request"]["conflictStatus"] == "NONE"


def test_four_harnesses_share_one_bounded_adapter_surface() -> None:
    descriptors = [adapter_descriptor(name) for name in SUPPORTED_HARNESSES]
    assert [row["harness"] for row in descriptors] == list(SUPPORTED_HARNESSES)
    for descriptor in descriptors:
        assert descriptor["capabilities"] == list(ADAPTER_CAPABILITIES)
        assert descriptor["writeAuthorized"] is False
        assert descriptor["externalVerification"] == "NOT_MEASURED"


def test_capability_discovery_is_core_output_under_an_adapter_envelope() -> None:
    result = discover_agent_capabilities("opencode")
    assert result["harness"] == "opencode"
    assert result["writeAuthorized"] is False
    assert "browserCapability" in result["coreCapabilities"]
    assert result["coreCapabilities"]["browserCapability"]["claimBoundary"]


def test_authority_handshake_and_tool_bridge_fail_closed() -> None:
    handshake = build_authority_handshake("cursor/vs code", task_id="task-1", requested_action="repair")
    bridge = bridge_agent_tool(
        "cursor-vscode",
        "submitPatchCandidate",
        task_id="task-1",
        payload={"candidate": "shown-only"},
    )
    assert handshake["authorityStatus"] == "HOST_AUTHORITY_REQUIRED"
    assert handshake["writeAuthorized"] is False
    assert bridge["delivery"] == "CURRENT_CONVERSATION_HOST_BRIDGE"
    assert bridge["writeAuthorized"] is False
    assert bridge["authorizationGranted"] is False


def test_result_rendering_is_same_core_task_result_for_two_harnesses() -> None:
    raw = {
        "status": "FAIL",
        "before": {"topFindings": [{"ruleId": "BUTTON_LABEL", "summary": "label missing"}]},
    }
    codex = render_agent_result("codex", raw, request="check this page")
    claude = render_agent_result("claude", raw, request="check this page")
    assert codex["taskResult"] == claude["taskResult"]
    assert codex["taskResult"]["reasonCode"] == "FINDINGS_DETECTED"
    assert codex["writeAuthorized"] is False
