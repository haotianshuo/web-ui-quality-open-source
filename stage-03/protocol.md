# Stage 03 Protocol — One Semantic Result

Status: FROZEN AFTER ROUND 1 BASELINE (procedural timing deviation recorded)
Stage: 03
Objective: Give every renderer one canonical semantic TaskResult, including a stable `reasonCode`, while preserving existing status, claim, Host, and Browser authority boundaries.
Baseline SHA: `ea41be16dfb04c079d858de2f2ef9a08a7575ac8`

The Round 1 baseline comparison was completed before this protocol file was written because of an execution-order error. No source change was made before that baseline comparison. This deviation is recorded rather than represented as a pre-existing protocol freeze.

## Scope

Only the semantic result builder, its two schema copies, the human renderer's use of the semantic result, and public regression coverage are in scope. This stage may add one canonical reason field and its deterministic projection. It must not create a second result contract, change exit-code policy, grant write authority, manufacture Browser or Host evidence, or promote `NOT_VERIFIED` to `VERIFIED`.

## Frozen user-completion contract

For one deterministic request, plain text, JSON, and CI must describe the same semantic result. The machine-readable result must expose a non-empty canonical `reasonCode`; the human explanation must be derived from that code. JSON and CI may retain their distinct transport and exit semantics, but their semantic fields must agree.

The reason code is explanatory evidence, not an authority grant. It must distinguish at least:

- `VERIFIED`
- `BROWSER_UNAVAILABLE`
- `NETWORK_BLOCKED`
- `DEPENDENCY_MISSING`
- `ENV_BLOCKED`
- `INSUFFICIENT_EVIDENCE`
- `MANUAL_DECISION_REQUIRED`
- `DRIFT_DETECTED`
- `FINDINGS_DETECTED`
- `TASK_FAILED`

## Test matrix / oracle

| Input condition | Expected reason code |
| --- | --- |
| verified result | `VERIFIED` |
| Browser unavailable | `BROWSER_UNAVAILABLE` |
| network or offline blocker | `NETWORK_BLOCKED` |
| dependency/package/module blocker | `DEPENDENCY_MISSING` |
| environment or policy-not-verified result | `ENV_BLOCKED` |
| no runnable URL or other insufficient preflight evidence | `INSUFFICIENT_EVIDENCE` |
| Host write/auth/scope/review decision required | `MANUAL_DECISION_REQUIRED` |
| unexpected project drift | `DRIFT_DETECTED` |
| inspection findings | `FINDINGS_DETECTED` |
| deterministic repair/task failure | `TASK_FAILED` |

The same request must produce equal semantic projections for JSON and CI. The schema validator must accept both outputs, and CI's existing exit behavior must remain unchanged.

## Fixed rounds

1. Round 1: reproduce the baseline result shape and reason ambiguity, implement the smallest canonical projection, and add focused tests.
2. Round 2: run the reason-code boundary matrix, JSON/CI schema and semantic-equivalence checks, and relevant existing result regressions.
3. Round 3: repeat the matrix and focused checks, then run the public entry point, full repository tests, and `git diff --check`.

If the stage is not PASS after Round 3, perform at most two documented web rescues, each followed by one minimal fix and the full stage checks. Any remaining issue is appended to `UNRESOLVED_ISSUES.md` and the task proceeds to Stage 04.

## Authority boundary

This stage standardizes explanation and serialization only. A reason code cannot create a Host receipt, establish Browser execution, authorize a write, or qualify a release. Existing `NOT_MEASURED`, `NOT_VERIFIED`, `RC_ONLY`, and `NOT_ELIGIBLE` boundaries remain explicit.
