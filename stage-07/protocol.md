# Stage 07 Protocol — Simple View / Expert View

Status: FROZEN BEFORE ROUND 1
Stage: 07
Objective: Keep the default result understandable without Trust Kernel vocabulary while retaining detailed evidence for an explicit machine/expert view.
Baseline SHA: `ea41be16dfb04c079d858de2f2ef9a08a7575ac8`

## Scope

Review the existing default repair-result renderer and the `--json`/`--expert-json` separation. The ordinary surface must answer: what happened, whether it was solved, what was verified, what remains unverified, and what happens next. Receipt, Hash, Evidence Graph, run binding, and raw TaskResult details remain expert/machine evidence.

## Frozen user-completion contract

An ordinary user can understand a result without knowing the Trust Kernel, Receipt Protocol, HMAC, digest, or evidence-graph terminology. Failure and ambiguity must produce a plain next action and must not hide the unverified boundary. Expert output may retain exact machine fields and evidence references.

## Test matrix / oracle

| Surface | Required behavior |
| --- | --- |
| default output | plain-language result, changed, verified, and next-step sections |
| success | says completed and verified only within the recorded scope |
| failure / ambiguity | says what needs handling and preserves the missing-evidence boundary |
| expert/machine output | retains detailed fields without leaking them into default output |

## Fixed rounds

1. Round 1: replay the current default verbose surface and inspect its failure/ambiguity output.
2. Round 2: run the simple-surface regression and compare default versus expert/machine detail retention.
3. Round 3: run failure-path regressions, public tests, full regressions, and diff check.

If the stage is not PASS after Round 3, perform at most two documented web rescues, each followed by one minimal fix and the full stage checks. Any remaining issue is appended to `UNRESOLVED_ISSUES.md` and the task proceeds to Stage 08.

## Authority boundary

Rendering is presentation only. Hiding a protocol detail from the default view never removes it from evidence, grants write authority, upgrades verification, or changes a gate.
