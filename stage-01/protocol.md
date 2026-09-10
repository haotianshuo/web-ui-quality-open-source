# Stage 01 Protocol — Focus Whitespace Correctness

Status: FROZEN BEFORE ROUND 1
Stage: 01
Objective: Fix the deterministic whitespace-sensitive focus replacement false-negative/false-positive behavior in `_css_has_focus_replacement()`.
Baseline SHA: `ea41be16dfb04c079d858de2f2ef9a08a7575ac8`
Baseline `core.py` SHA-256: `6717D8DE22546AA21EDD8CDCBF760F0499F32F21F97C3C8E2556EA00DCA9C416`

## Scope

Only CSS focus replacement parsing and its regression coverage are in scope. This stage may touch the core focus helper and focused tests. It must not add another accessibility rule, change Browser behavior, change claim authority, or alter unrelated CSS heuristics.

## Frozen user-completion contract

For a CSS source that removes the default focus outline, the user must receive a finding unless the same `:focus` rule contains a real visible replacement. Formatting whitespace must not change that decision.

Success means:

- `outline:none`, `outline: none`, tab-separated `outline: none`, `outline:0`, and `outline: 0` are all treated as removed when no replacement exists.
- `outline: 2px solid`, a non-none `box-shadow`, or a non-none `border`/`border-color` in a `:focus` rule is treated as a replacement.
- A removed outline plus a valid replacement is not reported.
- Selectors without `:focus` do not satisfy the replacement contract.

## Test matrix / oracle

| Input family | Expected helper result |
| --- | --- |
| `outline:none` | `False` |
| `outline: none` | `False` |
| `outline:\tnone` | `False` |
| `outline : none` | `False` |
| `outline:0` | `False` |
| `outline: 0` | `False` |
| `outline:\t0` | `False` |
| `outline:2px solid` | `True` |
| `outline: 2px solid` | `True` |
| valid `box-shadow` replacement | `True` |
| valid `border-color` replacement | `True` |

The finding-level oracle is a second check: no-replacement CSS must contain `A11Y-FOCUS-OUTLINE-REMOVED`; valid replacement CSS must not.

## Fixed rounds

1. Round 1: reproduce the baseline bug, implement the smallest parser/regex correction, and add targeted regression tests.
2. Round 2: run the complete matrix, false-positive controls, and relevant existing focus regressions without changing this protocol.
3. Round 3: run from the cleanest available checkout/environment, repeat the matrix and focused tests, then run the public test entry point and relevant full tests.

If the stage is not PASS after Round 3, perform at most two documented web rescues, each followed by one minimal fix and the full stage checks. Any remaining issue is appended to `UNRESOLVED_ISSUES.md` and the task proceeds to Stage 02.

## Authority boundary

This change only improves static detection. It does not grant write authority, create a Host receipt, collect Browser evidence, or promote any result to `VERIFIED`.
