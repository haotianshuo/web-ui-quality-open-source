# Stage 05 Result — REPAIR Mapping Automation

Status: PASS
Baseline SHA: `ea41be16dfb04c079d858de2f2ef9a08a7575ac8`

## Round 1

The ordinary REPAIR journey reproduced the dead end: with no structured source ownership, the plan was `SCOPE_NOT_CONFIRMED`, `scopeConfirmed=false`, and the next action exposed the internal Finding → Route → Selector → Component → Source File → Source Range chain for the user to complete manually.

The minimal fix added a read-only mapping projection. It consumes structured Finding location fields, validates project-relative files, preserves missing links as `NOT_MEASURED`, and retains multiple source candidates as `AMBIGUOUS`. Focused mapping and existing repair regressions: `37 passed in 16.88s`.

## Round 2

- Complete structured Finding: deterministic six-link mapping with `COMPLETE`/`HIGH` confidence.
- Missing source file or range: `INCOMPLETE`; no filename-based source guess.
- Multiple explicit source candidates: `AMBIGUOUS`; no scope confirmation.
- Missing/escaped/symlink source: `REJECTED`; no write scope.
- Complete mapping in fix preparation: `PATCH_CANDIDATE_REQUIRED`, `hostBridgeAction=submitPatchCandidate`, `writeAuthorized=false`, and `sourceProjectChanged=false`.

## Round 3

- Fresh isolated pytest temp root full regression: `693 passed in 437.79s`.
- Public entry point: `19 passed in 63.89s`, exit `0`.
- `git diff --check`: exit `0`.
- No web rescue was needed.

The first two full-suite attempts each produced `692 passed, 1 error` at the shared Windows integrity-key fixture because pytest reused a stale temporary directory containing an 8-byte key from an earlier date. The isolated rerun passed and the stale historical directory was not deleted.

## Changed files

- `runtime/python/web_ui_quality/fix_workflow.py`
- `tests/public/test_repair_mapping.py`
- `stage-05/protocol.md`

Post-stage hashes:

- `fix_workflow.py`: `0037C4C436F7985C265BBB0EBAF890A812EB9A7173E9163E75C364C895D43290`
- `test_repair_mapping.py`: `028AE27703F945848772B40A06260A9C4F10A3FD9E941A8A61D9484F17806055`
- `stage-05/protocol.md`: `4DCBCB4F11919541DA25B275FD3915893C94E1FC8825BDC84DECE97B57083E5D`

## Acceptance

- A normal structured REPAIR no longer requires the user to hand-author the internal mapping chain.
- Ambiguity, missing evidence, and unsafe paths remain explicit and fail closed.
- Runtime only prepares evidence and Host-facing candidates; it does not write or authorize writes.
- `STAGE_STATUS = PASS`.

This improves repair planning and user recovery. It does not prove that a proposed code change is correct or that a Host applied it.
