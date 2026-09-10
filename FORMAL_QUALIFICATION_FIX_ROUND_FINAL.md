# Formal Qualification Fix Round — Final

Date: 2026-09-11
Branch: `formal-qualification-fixes`
Baseline: `f6f830942fb9dd2fe4ae188934fa20e00662ab98`
Decision: `FORMAL_FIX_REAL_HOST_NOT_CLOSED`

## Decision boundary

The local bounded Treatment fix round is validated: all 19 scheduled records passed, including the required negative and protected-scope checks. Real Host validation was not genuinely performed in this environment, so the Formal fix is not closed as a Real Host result and no Real Host ledger is emitted.

This is not a full Formal qualification result, Holdout result, GA decision, release decision, or Open Source eligibility decision.

## Frozen inputs

- Qualification fixture: `de36ac253d942f2f3805230ce8a2083a9b56d56c`
- Freeze file: `FORMAL_FIX_TASK_FREEZE.json`
- Freeze SHA-256: `6d14932839240a732139a8837d5c047add53ecebb3c5e84a936870f1e53bbfa3`
- Browser matrix: `390x844`, `768x1024`, `1440x900`
- Final validation ledger SHA-256: `ad7fb868df0fe99aab64f6f117ffb1d588c6034f6fbc495e5f4b41b995478c23`

The freeze binds the baseline, fixture, selected tasks, oracle class, expected outcome, declared write scope, and negative conditions. Each validation run cloned the frozen fixture into a fresh directory.

## Changes made

- P1-A: task-objective comparison for runtime health, focus affordance, contrast, clipping, and horizontal overflow. The comparison gate now requires the named objective's measured before defect, clean after state, complete matched Browser evidence, and structural evidence; unrelated generic health cannot promote a stale or missing target.
- P1-B: scoped write intent and protected-scope handling. Q17's requested `styles.css` repair is distinct from its protected `package.json`/`README.md` scope; negated “other files” language no longer converts the whole request into read-only.
- P1-C: explicit security-audit language is required for the specialized security route. A business request containing “安全中心” remains a repair request.
- Harness P2: execution mode and expected claim are derived from the frozen oracle contract (`oracleClass`, `category`, `property`, and `allowedWrites`), not from task-ID or natural-language heuristics. Q27 classification regressions and negative cases are covered by tests.
- General Browser fix: mobile CSS viewport normalization and horizontal-overflow measurement use the realized visual/CSS viewport, while preserving raw `innerWidth` as an observation. This closes the 390px mobile emulation false mismatch without weakening the gate.

No lower `VERIFIED` threshold, oracle replacement, historical Formal runner change, or write-authority expansion was made.

## Replayed failures and validation

The six original failures are recorded in [`FORMAL_FIX_FAILURE_REPLAY.md`](FORMAL_FIX_FAILURE_REPLAY.md), including the failure node, evidence boundary, and before/after claim path. The final bounded ledger is [`FORMAL_FIX_VALIDATION_LEDGER.jsonl`](FORMAL_FIX_VALIDATION_LEDGER.jsonl).

| Validation | Result |
| --- | --- |
| Round 1: Q05, Q12, Q14, Q15, Q16, Q17, Q19, Q20, Q28, Q30 | 10/10 PASS |
| Round 2: Q16, Q17, Q28, Q19 | 4/4 PASS |
| Round 3: Q12, Q14, Q16, Q28, Q20 | 5/5 PASS |
| Total | 19/19 PASS |
| False `VERIFIED` | 0 |
| Unauthorized/unexpected writes | 0 |
| Protected-file drift | 0 |
| Scope mismatch | 0 |

Q16 passed three independent clean-state runs (one in each round). Q05 remained clean with no writes. Q19 and Q20 correctly remained `NOT_VERIFIED` under insufficient/unreachable or stale evidence conditions.

The validation evidence root is `C:\Users\Administrator\AppData\Local\Temp\formal-fix-validation-3ac1c4e95295`. The earlier failed attempt was preserved as `C:\Users\Administrator\AppData\Local\Temp\FORMAL_FIX_VALIDATION_LEDGER.failed-20260911.jsonl` and is not used as final evidence.

## Test evidence

- Focused changed/regression suites: `54 passed`
- Browser/security/viewport suites: `83 passed`
- Full test suite: `756 passed in 8:51`

The full suite was run with the bundled Playwright Python package and Chromium available, so Browser-related tests were not treated as an unavailable capability.

## Formal-1 immutability check

The four Formal-1 evidence files were read-only inputs and were not modified:

| File | SHA-256 |
| --- | --- |
| `formal-qualification-20260910/FORMAL_CONTROL_TREATMENT_QUALIFICATION_FINAL.md` | `d9f6c73d80fc5b11970416aa300622dd208c3ccb665604ae024b0f9e2d9d379a` |
| `formal-qualification-20260910/FORMAL_QUALIFICATION_FINDINGS.md` | `04b94890b08ce4fe4b41d9c6490c008fdd56123a5c3f3a978e743a8937c28e8a` |
| `formal-qualification-20260910/FORMAL_CONTROL_TREATMENT_LEDGER.jsonl` | `70b1f19f6d70c15112f94a882d3940c950a0b3f292d253f146a761cc78717711` |
| `formal-qualification-20260910/FORMAL_EXECUTION_INCIDENTS.jsonl` | `7f712950148b8f73e99da33cfaee9cd6a4e94c88aed0e106b9c8369172bf71fb` |

## Real Host and non-actions

Real Host validation for Q12, Q16, Q17, Q28, Q30, and Q19 was not genuinely executed, so its status is `NOT_AVAILABLE` and no `FORMAL_FIX_REAL_HOST_LEDGER.jsonl` is present. No Host, Holdout, GA, release, Open Source, push, publish, or ZIP claim is made.

The deferred scope is recorded in [`FORMAL_FIX_DEFERRED_ISSUES.md`](FORMAL_FIX_DEFERRED_ISSUES.md).
