# Stage 02 Protocol — Windows Encoding Boundary

Status: FROZEN BEFORE ROUND 1
Stage: 02
Objective: Make user-visible stdout, JSON, `nextAction`, and `observations` stable and readable across UTF-8 and Windows GBK/cp936 conditions, without rewriting the CLI.
Baseline SHA: `ea41be16dfb04c079d858de2f2ef9a08a7575ac8`

## Scope

Only the stdout/stderr and serialized JSON encoding boundary is in scope. The change may touch the shared `release_info` stdout configuration, the CLI renderer, and focused tests. It must not change task semantics, authority, Browser policy, claim promotion, or the internal result schema.

## Frozen user-completion contract

A Chinese request or Chinese `nextAction`/`observations` must remain readable when the CLI is run interactively or through redirected output under UTF-8 and cp936-compatible Windows conditions. JSON must remain valid UTF-8 data at the process boundary; `--ci` must retain its existing exit semantics and only its human-visible text encoding may change.

## Test matrix / oracle

| Mode / environment | Required observation |
| --- | --- |
| UTF-8 terminal, plain text | Chinese labels and next action readable; exit unchanged |
| cp936/GBK terminal, plain text | Chinese labels and next action readable; no replacement characters or encode error |
| UTF-8 terminal, `--json` | valid JSON; Chinese `nextAction` and `observations` survive round-trip |
| cp936/GBK-compatible redirected `--json` | valid UTF-8 JSON bytes; Chinese fields survive round-trip |
| UTF-8 and cp936 `--ci` | exit code remains contract-defined; diagnostic text readable |
| Chinese request | request is preserved/handled without mojibake |

The oracle rejects `UnicodeEncodeError`, replacement characters (`�`), invalid JSON, or changed semantic fields. A passing encoding test does not imply a `VERIFIED` claim.

## Fixed rounds

1. Round 1: reproduce the boundary behavior, record the baseline, implement the smallest encoding-boundary correction, and add focused tests.
2. Round 2: adversarially exercise redirected streams, explicit `PYTHONIOENCODING`, cp936-compatible wrappers, JSON round-trips, and CI exit behavior.
3. Round 3: repeat on a fresh process/environment where feasible, run focused and full regression tests, and verify no semantic output drift.

If the stage remains unresolved, at most two official/documented web rescues are allowed, followed by `UNRESOLVED` and Stage 03. No encoding workaround may silently change evidence or authority semantics.

## Authority boundary

Encoding is presentation/transport only. It cannot grant file write authority, change Browser authorization, alter evidence, or upgrade `NOT_VERIFIED` to `VERIFIED`.
