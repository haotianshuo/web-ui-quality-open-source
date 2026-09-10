# Stage 02 Result — Windows Encoding Boundary

Status: PASS / KEEP
Baseline SHA: `ea41be16dfb04c079d858de2f2ef9a08a7575ac8`

## Round 1

The current public checkout already contains a shared `configure_stdout()` boundary that reconfigures stdout and stderr to UTF-8 with replacement handling. On the Windows host with active code page 936, six subprocess runs (plain, JSON, and CI under `PYTHONIOENCODING=utf-8` and `cp936`) produced valid UTF-8 output, readable Chinese human labels, valid JSON where requested, and the expected CI exit `3`. No product encoding defect was reproduced against the current public baseline.

A public integration regression was added to prevent drift.

## Round 2

The adversarial process matrix passed for `cp936:strict` with `PYTHONUTF8=0`, `cp936:strict` with legacy Windows stdio enabled, and `utf-8:strict` with `PYTHONUTF8=1`. Each plain run exited `0`; each JSON run parsed as UTF-8 JSON; each CI run exited `3`; no replacement character appeared.

Focused encoding tests: `2 passed`.

## Round 3

- Full repository regression: `682 passed in 416.73s`.
- Public entry point: `8 passed in 25.11s`.
- `git diff --check`: exit `0`.
- No semantic result, claim, Host authority, or Browser policy changed.

## Changed files

- `tests/public/test_encoding_boundary.py` — cross-process UTF-8/cp936 and CI contract coverage.

The existing `runtime/python/web_ui_quality/release_info.py` implementation was retained (`KEEP`); no source fix was necessary for the current public main. The older supplied report's encoding observation remains historical/report input, not a current failure claim.

## Acceptance

- Chinese plain-text fields remain readable under UTF-8 and cp936-compatible settings.
- JSON remains valid UTF-8 with `nextAction` and `observations` present.
- CI exit semantics remain unchanged.
- `STAGE_STATUS = PASS`.

This stage validates the process/output boundary only. It does not prove Real Host qualification or `VERIFIED` task outcomes.
