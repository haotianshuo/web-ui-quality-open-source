# Stage 08 Protocol — Security Coverage Visibility

Status: FROZEN BEFORE ROUND 1
Stage: 08
Objective: Make security coverage explicit when the opt-in security checks are disabled, while preserving the existing opt-in boundary and never accessing credentials or granting high-risk authority.
Baseline SHA: `ea41be16dfb04c079d858de2f2ef9a08a7575ac8`

## Scope

Review the static audit's `include_security`/`--security-audit` boundary and the Router's security specialty label. The result must distinguish security checks not run from checks actually run, and must keep findings redacted and read-only.

## Frozen user-completion contract

When a request is security-related but the opt-in check is off, the user sees `NOT_MEASURED` for security coverage and a concrete opt-in next action. A clean result with the opt-in off is not a clean security result. Enabling the check only runs the existing bounded static rules; it does not read credentials, navigate, write files, or authorize high-risk actions.

## Test matrix / oracle

| Case | Expected security coverage |
| --- | --- |
| opt-in disabled | `status=NOT_MEASURED`, `enabled=false`, no security findings claimed |
| opt-in enabled | `status=MEASURED`, security findings are reported only from the bounded static subset |
| security-language request | Router remains read-only `CHECK` with `SECURITY` specialty |
| credential-like source | values remain redacted and no source write occurs |

## Fixed rounds

1. Round 1: reproduce the disabled-opt-in visibility gap on an in-memory fixture.
2. Round 2: compare disabled/enabled output and Router/security authority boundaries.
3. Round 3: run public tests, full regressions, and diff check.

If the stage is not PASS after Round 3, perform at most two documented web rescues, each followed by one minimal fix and the full stage checks. Any remaining issue is appended to `UNRESOLVED_ISSUES.md` and the task proceeds to Stage 09.

## Authority boundary

Security coverage is a measurement label, not permission. The opt-in flag cannot bypass Host Policy, authentication, Browser navigation policy, source scope, write gates, or release gates.
