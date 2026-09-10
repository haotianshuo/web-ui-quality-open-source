# Stage 00 Result — Baseline & Evidence Freeze

Status: PASS
Baseline SHA: `ea41be16dfb04c079d858de2f2ef9a08a7575ac8`

## Round results

### Round 1 — Reproduce / record

- The public main checkout was cloned and fetched from the named public repository.
- The four supplied files were read and hashed; their roles are separated in `protocol.md`.
- The reports contain non-equivalent claims (15 real runs plus synthetic users; a claimed 1000-run report; and a 12000-call synthetic-user report on Linux). No figures were merged or promoted.
- The public checkout identity is package `4.3.0`, `v4.3.0-oss-preview.1`, Apache-2.0, Trust Kernel `4.2.3`, with Real Host and External Blind Holdout still `NOT_MEASURED` and Commercial GA `NOT_ELIGIBLE`.

### Round 2 — CLI / doctor / public test / focus reproduction

| Command | Result |
| --- | --- |
| `scripts/run_runtime.py --help` | exit `0`; standard `run`, `doctor`, `auth`, and `expert` surface shown |
| `scripts/run_runtime.py doctor` | exit `0`; runtime/schema `PASS`, Python Playwright `AVAILABLE`, Node candidate `NOT_AVAILABLE`, Real Host metrics `NOT_MEASURED` |
| read-only `_css_has_focus_replacement()` matrix | exit `0`; whitespace discrepancy reproduced: `outline:none=False`, `outline: none=True`, `outline: 0=True`, valid replacement declarations `True` |
| `run_tests.py` first attempt | exit `1`; public boundary test correctly detected the initial protocol's local absolute paths |
| path-neutral evidence correction + `run_tests.py` | exit `0`; `4 passed` |

The first public-test failure is retained as an evidence event. The correction only removed local absolute paths from the evidence text; it did not alter product code or the public boundary test.

### Round 3 — clean repeatability / consistency

- `HEAD` and `origin/main` both remained `ea41be16dfb04c079d858de2f2ef9a08a7575ac8`.
- Checkout was unchanged except for the new stage evidence files.
- Help repeated with exit `0`.
- Doctor repeated with runtime/schema `PASS`, Browser `AVAILABLE`, Node candidate `false`, Real Host metrics `NOT_MEASURED`.
- Public tests repeated with `4 passed`.
- `git diff --check` exited `0`.
- Protocol and input hashes were rechecked; no input changed during the stage.

## Acceptance

- `BASELINE_IDENTITY = VERIFIED_LOCAL`
- `EVIDENCE_CLASSES = SEPARATED`
- `KNOWN_DEFECTS = FROZEN`
- `STAGE_STATUS = PASS`

No product behavior was changed in Stage 00. No Real Host, External Blind Holdout, GA, or real-user claim was made.
