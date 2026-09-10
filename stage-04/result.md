# Stage 04 Result — Browser Capability Clarity

Status: PASS
Baseline SHA: `ea41be16dfb04c079d858de2f2ef9a08a7575ac8`

## Round 1

The baseline `doctor` output reported `browserStatus=AVAILABLE` and `pageNavigation.available=true` when the Python Playwright driver and a Chromium executable were present, but exposed no task-level distinction for navigation authorization, target reachability, or collected evidence. A real run against an intentionally unreachable local target reproduced the ambiguity: `browserAvailable=true`, `preflight=BLOCKED`, `browserExecutionStatus=BROWSER_NOT_VERIFIED`, and `verified=false`.

The minimal fix added a non-authoritative capability projection with separate Browser Installed, Driver Available, launch, Navigation Authorized, Target Reachable, Evidence Collected, and Verification dimensions. Doctor now states that `AVAILABLE` is launch-prerequisite status only. Focused regressions: `23 passed in 15.48s`.

## Round 2

- Driver and executable available: `AVAILABLE` for launch; all task-level dimensions remain `NOT_MEASURED` until a bounded run.
- Executable available with missing driver: `BLOCKED`; verification remains `NOT_MEASURED`.
- Driver and executable missing: `MISSING`; verification remains `NOT_MEASURED`.
- Simulated navigation block: launch can remain `AVAILABLE`, navigation is `BLOCKED`, and evidence/verification remain `NOT_MEASURED`.
- Real unreachable-target rerun preserved `BROWSER_NOT_VERIFIED` and did not produce a verified claim.

## Round 3

- Full repository regression: `688 passed in 425.95s`.
- Public entry point: `14 passed in 50.80s`, exit `0`.
- `git diff --check`: exit `0`.
- No web rescue was needed.

## Changed files

- `runtime/python/web_ui_quality/capability_registry.py`
- `runtime/python/web_ui_quality/__main__.py`
- `tests/public/test_browser_capability_clarity.py`
- `stage-04/protocol.md`

Post-stage hashes:

- `capability_registry.py`: `71C301106C5DA092EBEEE67B0A0946F45AFA9A75E43BE20A550061E8B9A6E97A`
- `__main__.py`: `2CEFB6A289D69FCCF3D9533324C5C48194F8A7CB89D7278DB460FD7C5C468494`
- `test_browser_capability_clarity.py`: `029AB368C64FD83AE4A43708CF50FF1FFB1DDF61B48D454F579EBE1C735E8488`
- `stage-04/protocol.md`: `AAF6C55E9745724AF5ABB7609D730A9D167DA042CB6A5A1FF93FFFB76FBB2DA8`

## Acceptance

- Doctor distinguishes launch prerequisites from task-level Browser proof.
- `AVAILABLE` no longer carries an implicit verification meaning; the claim boundary and next action are explicit.
- Blocked or missing conditions remain fail-closed and do not create Browser evidence.
- Host Policy and write authority were not bypassed or changed.
- `STAGE_STATUS = PASS`.

This proves capability explanation and fail-closed separation only. It does not prove a Real Host result, target reachability for an arbitrary project, or release qualification.
