# Stage 00 Protocol — Baseline & Evidence Freeze

Status: FROZEN BEFORE ROUND 1
Stage: 00
Objective: Establish the immutable execution baseline for the Human-First Universal Agent Evolution run.
Baseline SHA: `ea41be16dfb04c079d858de2f2ef9a08a7575ac8` (`origin/main` as fetched on 2026-09-10)
Execution tree: isolated checkout of the public repository created for this run

## Scope

This stage records the public main checkout, package identity, CLI surface, doctor result, public test entry point, supplied reports, known defects, runtime environment, and dependency availability. It does not change product behavior and does not promote any `NOT_MEASURED`, `NOT_VERIFIED`, or `NOT_ELIGIBLE` state.

The recovered ZIP tree named `source-recovered-4.3.0/web-ui-quality` is preserved as historical/recovery material and is not this stage's edit target. It has no Git metadata and carries a different proprietary package identity.

## Frozen inputs

| Input | SHA-256 | Classification | Use |
| --- | --- | --- | --- |
| `WUQ-GPT5.6-Luna-Max-分阶段持续进化执行指令.md` | `D9FD9466906A23941BCC6202880964A060F4EB7F12E3ACF64B8150FAA807E1FE` | SPEC / EXECUTION | Stage order, evidence rules, safety boundaries, acceptance criteria |
| `WUQ-千人年度调研报告-真实执行推演.md` | `EA43C8AA7415EC9E71300232C76DA151DB25C03A0B676A9DE4DAF319039BBFAD` | EXECUTED claims + SYNTHETIC simulation | Windows fixture observations, 15 run records, synthetic 1000-user model |
| `wuq-real-execution-report.html` | `7E6DF05C4E83E3FB56DE60B6016B07F4EAF0F25004594EAA3CB2AAAB6B9FFB5C` | SUPPLIED EXECUTED report, provenance to be treated as report input | Reported 1000 project-level runs and no VERIFIED result |
| `WUQ-1000-users-12-month-execution-simulation-report.html` | `86A53DFE256676CD96E539C4C9C8CAAEC6D7A22314C016103F1C4688424061E6` | EXECUTED core calls + SYNTHETIC personas | Reported 12000 frozen-plan calls and synthetic longitudinal segmentation |

The reports are not merged into one dataset. The first Markdown report describes 15 real runs plus a synthetic population; the small HTML report describes 1000 claimed real runs; the large HTML report describes 12000 runtime calls with synthetic users and a Linux execution host. These are retained as separate evidence classes until independently reconciled.

## Baseline identity

- Public repository: `haotianshuo/web-ui-quality-open-source`.
- Public `main` observed by `git fetch` and `git ls-remote`: `ea41be16dfb04c079d858de2f2ef9a08a7575ac8`.
- Checkout status before stage work: clean, branch `main` tracking `origin/main`.
- Package: `4.3.0`; public preview: `v4.3.0-oss-preview.1`; public license: Apache-2.0.
- Trust Kernel: `4.2.3`; Receipt Protocol: `3.0`; Evidence Schema: `3.0`.
- Public claim boundary at baseline: Real Host `NOT_MEASURED`; External Blind Holdout `NOT_MEASURED`; Commercial GA `NOT_ELIGIBLE`.
- Local process environment: Windows 11 host context, Python `3.12.10`, Node `v24.18.0`, npm `11.16.0`, desktop Chrome executable present.
- The public checkout has a `tests/public` entry point and no private `evolution/` directory.

## Known defects frozen for later stages

1. `_css_has_focus_replacement()` is whitespace-sensitive and can treat `outline: none` / `outline: 0` with spacing as a replacement because a regex whitespace quantifier can backtrack.
2. Windows text/JSON/CI output may expose encoding differences for Chinese user-visible fields; this is a later Stage 02 target and is not changed here.
3. Browser driver/executable availability is not equivalent to navigation authorization or collected Browser evidence.
4. Text, JSON, and CI output need a single semantic result boundary.
5. REPAIR mapping is rigorous but exposes too much internal mapping burden to ordinary users.
6. Default Browser installation and security opt-in states need clearer user-facing visibility.

## Acceptance criteria / oracle

Stage 00 passes only when the baseline identity is reproducible locally, the four inputs and their evidence classes are recorded, and the known defect list is frozen. The oracle is conservative: package tests prove only the package contract; they do not prove Real Host, external holdout, commercial GA, or real-user benefit.

## Test matrix

| Round | Required work |
| --- | --- |
| Round 1 | Read the public checkout and all four supplied reports; record identity, environment, evidence classes, and known defects. |
| Round 2 | Repeat `--help`, `doctor`, public tests, and a read-only focus-rule reproduction. Preserve all stdout/stderr/exit codes. |
| Round 3 | Rehash frozen inputs and key files, repeat identity/help/doctor checks, verify the checkout and artifacts are consistent, and record any environment limitation. |

After Round 1 begins this protocol is immutable. Any defect in the protocol itself must be recorded as `PROTOCOL_DEFECT` in the stage result rather than edited retroactively.
