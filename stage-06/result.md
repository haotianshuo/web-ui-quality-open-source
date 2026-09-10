# Stage 06 Result — Human-First Intent Router

Status: PASS_WITH_ENVIRONMENT_LIMITATION
Stage objective status: PASS
Baseline SHA: `ea41be16dfb04c079d858de2f2ef9a08a7575ac8`

## Round 1

The short Chinese/English request matrix reproduced a usability gap: ordinary positive requests such as “请修改按钮颜色”, “please change the button color”, and “帮我调整移动端布局” were routed to read-only diagnosis because the router did not recognize those common mutation verbs. The baseline still correctly handled inspect, explain, verify-only, redesign, specialty, and empty-input cases.

The minimal fix added the missing Chinese and English mutation signals to the existing router, control parser, and public task-intent adapter. It did not add a new authority path. Focused routing matrix after the test-harness correction: `40 passed`.

## Round 2

- Ordinary read-only requests remain `CHECK`/`EXPLAIN` and do not request writes.
- Verify/regression requests remain `VERIFY_ONLY`; a phrase such as “验证刚才的修改” is not treated as a new repair.
- A scoped non-goal such as “不要修改登录逻辑” no longer becomes a positive write signal.
- A mixed request such as “帮我修好，但不要修改任何文件” remains `INTENT_CONFLICT`, fail-closed, with `writeAuthorized=false`.
- Accessibility, security, and performance phrases remain specialty labels; they do not expand authority.
- The focused adversarial and compatibility set passed: `40 passed in 0.99s`.

One semantic regression appeared during the first full run: the scoped non-goal “不要修改登录逻辑” caused JSON/CI repair projections to differ. It was corrected by removing negated write clauses before positive mutation detection. The focused semantic and plain-flow recheck passed: `29 passed in 12.72s`.

## Round 3

- Public entry point: `33 passed in 45.71s`, exit `0`.
- Full repository: `698 passed, 8 skipped, 1 failed in 400.68s`.
- The sole failure was the existing Browser execution sentinel, `PLAYWRIGHT_SYNC_API_REQUIRED_FOR_FULL_BROWSER_GATE`, because the active Python 3.12 environment has no Playwright module. This is recorded as an environment capability limitation, not relabeled as a router pass.
- `git diff --check`: exit `0`.
- No web rescue was used; the remaining failure is unrelated to intent routing and installing a Browser dependency would change the execution environment rather than repair this stage's logic.

The supplied report identifies a synthetic 1000-user / 12-month simulation, but the four supplied files do not contain its original machine-readable 1000-request-category corpus. Therefore the exact category replay is `NOT_MEASURED`; the available short-request and adversarial corpus was replayed as FACT evidence, and synthetic user counts remain SYNTHETIC evidence.

## Changed files

- `runtime/python/web_ui_quality/intent_router.py`
- `runtime/python/web_ui_quality/control_intent.py`
- `runtime/python/web_ui_quality/task_intent_adapter.py`
- `tests/public/test_intent_router_surface.py`

Post-stage hashes:

- `intent_router.py`: `80019C01286A62843438A6140BFF5AC725F502BECE9499EDB6A5578346D1C663`
- `control_intent.py`: `3E32D57E9ACF124100C35581B2858347B923702C718FF6EAB71FBA2C7B3746DA`
- `task_intent_adapter.py`: `064E37E6B311616AD68DAAC2D918140CBDD08C38B057F099422172A067398E19`
- `test_intent_router_surface.py`: `A976AF9774825F4C85EBA3D1D5F00B1E76F094BAF51C15B8B0BFFBB97C4750DB`
- `stage-06/protocol.md`: `33515AAE98F793D9A732FDA0A40FF84B4F87E713B6450D5A07CED60924299D34`

## Acceptance

- One- or two-sentence ordinary requests reach the smallest existing workflow more reliably.
- Internal route names remain implementation details of the normalized result; public intent is `CHECK`, `EXPLAIN`, `REPAIR`, or `VERIFY_ONLY`.
- Router confidence and mutation wording never set `writeAuthorized=true`.
- Negated protected scope, contradictory requests, and unavailable evidence remain explicit and fail closed.
- `STAGE_STATUS = PASS_WITH_ENVIRONMENT_LIMITATION`; router objective is complete, while Browser execution and the unavailable synthetic category corpus remain unmeasured.
