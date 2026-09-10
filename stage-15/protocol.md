# Stage 15 Protocol — Architecture Reduction and Final Handoff

## Scope

Close the staged evolution with a user-facing handoff. Reduce only complexity
that is proven unnecessary and safe to remove; do not alter expected/oracle
semantics, evidence boundaries, authority, or release claims merely to improve
the status label.

The final handoff must include:

- baseline commit and working-tree state;
- stages 00-15, their decisions, tests, and limitations;
- changed files and artifact hashes where available;
- current user completion contract;
- Browser, Host, External Project, Holdout, legal, and release boundaries;
- Zero-Python direction and Thin Adapter result;
- complexity/line-budget inspection;
- unresolved inputs and the next safe action.

## Evidence rules

1. Preserve append-only ledger rows and all failure evidence.
2. Do not remove code without a local reason, focused regression, and a
   measurable complexity benefit.
3. Do not convert NOT_MEASURED, NOT_VERIFIED, HOLD, or NOT_ELIGIBLE into PASS.
4. Do not claim a commit, signed artifact, external Host, real user, or
   commercial release that was not observed.
5. The final report is a handoff, not a new authorization for publishing or
   external coordination.

## Three rounds

### Round 1 — architecture and complexity audit

- Inspect changed source files, line budgets, duplicated paths, and adapter
  boundaries.
- Decide KEEP or remove with evidence; perform no speculative rewrite.

### Round 2 — handoff assembly

- Reconcile all stage results, hashes, checkpoints, unresolved issues, input
  document distinctions, and exact test outcomes.
- Verify that the report points to the current workspace and does not hide
  limitations.

### Round 3 — final regression and integrity

- Run public and full regressions in an isolated test root.
- Run diff check, status, source baseline comparison, and final report hash.
- Record commit limitation if Git author identity is unavailable.

## Completion gate

The stage is complete when the final handoff report is written, the final
regression and integrity results are recorded, no unnecessary architecture was
removed without evidence, and the current status is stated honestly.
