# Stage 11 Protocol — Universal Agent Thin Adapter

## Scope

Prove that one WUQ Core can be reached through thin adapter boundaries for
Codex, Claude Code, OpenCode, and Cursor/VS Code. The adapter contract may cover
only:

- installation/integration handoff;
- capability discovery;
- natural-language request routing;
- authority handshake;
- tool bridging;
- result rendering.

The adapter must not implement or copy scope calculation, receipt creation,
drift/oracle logic, evidence graph rules, claim promotion, or Host authority.

## Evidence rules

1. Reuse the existing Core functions for intent, capability, Host bridge, and
   TaskResult.
2. Keep simulated harness wrappers structurally different but semantically
   equivalent; they are contract tests, not Real Host measurements.
3. A descriptor or bridge request must fail closed with writeAuthorized=false.
4. Do not claim that an external Codex, Claude Code, OpenCode, or Cursor/VS Code
   installation was run unless that harness supplies direct evidence.
5. No new permission, credential, network, or source-write path may be added.

## Three rounds

### Round 1 — matrix and canonical adapter

- Freeze the four-harness capability matrix.
- Identify existing Core functions and add only a thin composition boundary if
  one is missing.
- Test a canonical request/result path.

### Round 2 — second harness

- Replay the same safe read and requested-repair inputs through a second
  harness-shaped wrapper.
- Compare canonical intent, capability boundary, Host bridge, and result
  rendering.

### Round 3 — boundary regression

- Run adversarial write/read-only, verify-only, missing-capability, and
  patch-candidate cases.
- Run public/full regressions and diff check.
- Record that simulated wrappers do not establish external Harness or Real Host
  evidence.

## Completion gate

The stage is complete when one Core produces equivalent bounded results through
at least two thin harness wrappers, the four-harness matrix is recorded, and no
adapter path can grant authority or duplicate the trust/evidence engines.
