# Stage 11 Result — Universal Agent Thin Adapter

Status: PASS_WITH_ENVIRONMENT_LIMITATION
Stage objective status: PASS
Baseline SHA: ea41be16dfb04c079d858de2f2ef9a08a7575ac8

## Round 1 — matrix and canonical adapter

The existing Core boundaries were identified as:

- task_intent_adapter.normalize_task_intent for natural-language routing;
- capability_registry.build_capability_registry for capability discovery;
- host_bridge.bridge_request for the allow-listed bridge envelope;
- task_result.build_task_result for the canonical result.

The thin agent_adapter composition boundary was added. It exposes descriptors,
request routing, capability discovery, authority handoff, tool bridging, and
result rendering. It delegates to the four existing Core functions and always
emits writeAuthorized=false. A static import check found zero imports of
scope_policy, safe_edit, trusted_evidence, receipt verification, drift, or
evidence engines.

The frozen matrix is:

| Harness | Adapter surface | External execution evidence |
|---|---|---|
| Codex | descriptor, route, capability, handshake, bridge, render | NOT_MEASURED |
| Claude Code | same Core composition | NOT_MEASURED |
| OpenCode | same Core composition | NOT_MEASURED |
| Cursor/VS Code | same Core composition, cursor/vs code alias | NOT_MEASURED |

## Round 2 — second harness

Codex-shaped input with a prompt field and Claude Code-shaped input with a
message field reached the same canonical intent result for a scoped read-only
request. The adapter also rendered equal TaskResult objects for both harnesses.
Cursor/VS Code alias normalization and OpenCode capability discovery passed.

## Round 3 — boundary regression

Focused adapter, Router, simple/expert, Browser capability, and semantic-result
set: 27 passed in 17.48s. Authority-handshake and submitPatchCandidate bridge
cases remained fail-closed; no source write was attempted.

Full repository regression: 708 passed, 8 skipped, 1 failed in 400.48s. The
sole failure was the existing PLAYWRIGHT_SYNC_API_REQUIRED_FOR_FULL_BROWSER_GATE
sentinel because Playwright is unavailable in the active environment. No
adapter test failed.

## Changed files

- runtime/python/web_ui_quality/agent_adapter.py
- tests/public/test_thin_agent_adapter.py

Post-stage hashes:

- agent_adapter.py: 26960D8C736EC89C0BB3707EF8DECBB1200AC10EA1A9C566879249D8FE23EA16
- test_thin_agent_adapter.py: DD627CD14186E47BF8CDB613C460A3AEAC83D8D26C6ED8514EEE924AF407658A
- stage-11/protocol.md: 7DC1904085E99D1391BC2A8076E2D8140431DC46BBCF647F7D39E1555A30251C

## NOT_MEASURED

- Any external Codex, Claude Code, OpenCode, Cursor, or VS Code installation.
- Real Host authority handshake, model call, tool execution, source write, or
  post-write receipt.
- Cross-platform adapter installation and version compatibility.
- Harness-specific rendering fidelity beyond the shared canonical result.

## Acceptance

- One Core now has a small shared adapter surface for four named Harnesses.
- At least two different harness-shaped inputs produced equivalent bounded
  results.
- Adapter output and bridge requests cannot grant authority.
- Scope, receipt, drift, evidence, and claim engines were not duplicated.
- Full-suite Browser limitation remains explicit and unchanged.
