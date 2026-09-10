# Stage 05 Protocol — REPAIR Mapping Automation

Status: FROZEN BEFORE ROUND 1
Stage: 05
Objective: Remove the ordinary-user REPAIR dead end by producing a bounded, evidence-backed Finding → Route → Selector → Component → Source File → Source Range mapping candidate without granting write authority.
Baseline SHA: `ea41be16dfb04c079d858de2f2ef9a08a7575ac8`

## Scope

Only read-only repair mapping, the existing fix-preparation plan, and public regression coverage are in scope. The mapper may use a Finding's structured location, route, selector, component/source hints, and line/range evidence. It must reject or mark ambiguous unsupported guesses, preserve protected scope, and leave actual writes to the Host. It must not infer a source file from a filename alone, auto-install dependencies, mutate the project, or authorize a Patch Candidate.

## Frozen user-completion contract

For a request such as “修一下移动端这个按钮错位”, the user should receive either:

1. a bounded mapping candidate with the available chain and explicit confidence/evidence for every link, followed by the existing Host approval boundary; or
2. a short, actionable ambiguity request naming the missing link, without asking the user to understand internal protocol files.

The output must make these links visible and separate:

```text
Finding → Route → Selector → Component → Source File → Source Range
```

`scopeConfirmed` is true only when a real project-relative source file is confirmed by explicit Host scope or structured Finding evidence. A mapping suggestion alone never authorizes a write.

## Test matrix / oracle

| Input | Expected result |
| --- | --- |
| complete structured Finding with location | deterministic complete mapping candidate |
| selector and route present, source file absent | mapping remains incomplete; no guessed file |
| source file present but line/range absent | source file may be scoped, source range is `NOT_MEASURED` |
| multiple equally plausible source files | `AMBIGUOUS`; Host/user decision required |
| path escape, symlink, or missing file | rejected; no scope confirmation |
| complete mapping sent to fix preparation | Patch Candidate required, Runtime write remains false |

## Fixed rounds

1. Round 1: reproduce the current dead end, implement the smallest mapping projection/ambiguity handling, and add focused tests.
2. Round 2: run complete, incomplete, ambiguous, invalid-path, and protected-scope cases.
3. Round 3: run a real fixture repair-preparation journey, public tests, full regressions, and the diff check.

If the stage is not PASS after Round 3, perform at most two documented web rescues, each followed by one minimal fix and the full stage checks. Any remaining issue is appended to `UNRESOLVED_ISSUES.md` and the task proceeds to Stage 06.

## Authority boundary

Mapping is evidence organization and scope planning. Router/AI output is not authority; Runtime cannot write, authenticate, approve, or apply. Host approval and a valid Host receipt remain required for any project change and later verification.
