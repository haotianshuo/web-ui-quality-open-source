# Stage 04 Protocol — Browser Capability Clarity

Status: FROZEN BEFORE ROUND 1
Stage: 04
Objective: Make Browser readiness legible as separate capability dimensions so local launch readiness cannot be mistaken for completed verification.
Baseline SHA: `ea41be16dfb04c079d858de2f2ef9a08a7575ac8`

## Scope

Only the capability registry, `doctor` projection, and public regression coverage are in scope. The stage may add a compact capability-clarity object and human-readable boundary text. It must not bypass Host Policy, authorize navigation, execute a target journey merely because a local Browser is installed, or turn serialized/candidate evidence into trusted Browser evidence.

## Frozen user-completion contract

The diagnostic result must distinguish these independent dimensions:

| Dimension | Meaning | Doctor default when it cannot be measured |
| --- | --- | --- |
| Browser Installed | A usable desktop or managed Chromium-family executable was resolved | `AVAILABLE` or `MISSING` |
| Driver Available | The selected Playwright driver can be imported | `AVAILABLE` or `MISSING` |
| Navigation Authorized | This task/Host permits navigation to the requested target | `NOT_MEASURED` |
| Target Reachable | The target responded under the selected conditions | `NOT_MEASURED` |
| Evidence Collected | A real target run produced Browser evidence | `NOT_MEASURED` |

`AVAILABLE` may describe only a local launch prerequisite. It must never mean `Browser Verification Completed`. A blocked target, Host policy decision, or missing URL must remain separately visible and fail closed.

## Test matrix / oracle

1. Driver and executable available: local capability is available, while navigation authorization, target reachability, and evidence remain `NOT_MEASURED`.
2. Driver available but executable missing: executable is `MISSING`; no verification is inferred.
3. Executable available but driver missing: driver is `MISSING`; no verification is inferred.
4. A simulated Host/navigation block: capability remains an environment fact, the navigation dimension is `BLOCKED`, and the result cannot be `VERIFIED`.
5. A successful live run is not fabricated by doctor output; only an actual Browser receipt/result may mark evidence collected.

The JSON shape must be deterministic, explain the next action for missing/blocked dimensions, and retain the existing provider-specific diagnostics and authority boundaries.

## Fixed rounds

1. Round 1: reproduce the `AVAILABLE`-but-not-verified ambiguity, implement the smallest capability projection, and add focused regressions.
2. Round 2: exercise available, missing-driver, missing-executable, and blocked-navigation fixtures plus doctor output.
3. Round 3: repeat all boundary cases, run public and full regressions, and check the diff.

If the stage is not PASS after Round 3, perform at most two documented web rescues, each followed by one minimal fix and the full stage checks. Any remaining issue is appended to `UNRESOLVED_ISSUES.md` and the task proceeds to Stage 05.

## Authority boundary

Doctor measures local prerequisites only. Navigation authorization belongs to the Host/task policy; target reachability and evidence belong to an executed, bounded Browser run. No capability field in this stage grants write permission, authentication, Host authority, or release qualification.
