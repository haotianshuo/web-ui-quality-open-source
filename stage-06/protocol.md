# Stage 06 Protocol — Human-First Intent Router

Status: FROZEN BEFORE ROUND 1
Stage: 06
Objective: Make one- or two-sentence Chinese/English requests route to the smallest safe workflow while keeping internal labels out of the ordinary user surface and preserving the no-authority-expansion boundary.
Baseline SHA: `ea41be16dfb04c079d858de2f2ef9a08a7575ac8`

## Scope

Only the existing intent router, task-intent adapter, control parser, and public regression coverage are in scope. The router may classify inspect/diagnose/explain/repair/verify/compare/accessibility/visual/interaction/performance/regression/release-check concerns into the existing workflows. It must not grant write authority, treat model confidence as approval, or silently ignore a contradictory read-only clause.

## Frozen user-completion contract

An ordinary safe request should reach one clear default workflow with zero or one clarification. A dangerous, credentialed, destructive, or contradictory request must fail closed or ask for an explicit decision. The ordinary surface exposes the user's task and next action; internal route names remain implementation details unless the user explicitly asks for expert output.

Required safety invariants:

- write intent implies Host approval but never `writeAuthorized=true`;
- an explicit whole-task read-only prohibition wins over a conflicting write phrase;
- verify-only requests do not start a new write workflow;
- accessibility/security/performance/responsive signals remain specialty labels, not hidden authority;
- empty or unrecognized input falls back to read-only diagnosis.

## Test matrix / oracle

| Request family | Expected public intent / boundary |
| --- | --- |
| “看看这个页面哪里有问题” / “check this page” | `CHECK` / read-only |
| “只解释，不改代码” / “read only” | `EXPLAIN` / read-only |
| “修一下移动端按钮错位” / “fix the button” | `REPAIR` / Host approval required |
| “验证刚才的修改” / “regression check” | `VERIFY_ONLY` / no write |
| “重新设计这个产品” / “redesign” | transformation workflow / product confirmation |
| accessibility/security/performance request | `CHECK` with specialty label |
| repair plus explicit whole-task read-only clause | conflict / fail closed |
| empty or unknown request | safe read-only fallback |

## Fixed rounds

1. Round 1: replay short Chinese/English requests and identify routing/authority gaps.
2. Round 2: replay ambiguous, contradictory, adversarial, and specialty requests; add only minimal regressions if needed.
3. Round 3: replay the available request-category corpus, public tests, full regressions, and diff check.

If the stage is not PASS after Round 3, perform at most two documented web rescues, each followed by one minimal fix and the full stage checks. Any remaining issue is appended to `UNRESOLVED_ISSUES.md` and the task proceeds to Stage 07.

## Authority boundary

Intent routing is classification only. Router confidence, specialty, and model suggestions cannot authorize source writes, authentication, external actions, Browser navigation, Host receipts, or release claims.
