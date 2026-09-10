# Stage 14 Protocol — Formal Control/Treatment Qualification

## Scope

Create a preregistered decision boundary for comparing a Control and a
Treatment. This stage may validate the qualification machinery, but it may not
promote synthetic fixtures, local Core runs, labels, or historical artifacts to
real-world evidence.

The only allowed final decisions are:

- PROMOTE_CANDIDATE — every required evidence gate passes;
- HOLD — the candidate is technically prepared but one or more required
  evidence inputs are absent;
- REJECT — a required invariant is violated or the candidate is invalid.

## Required fields

The formal record must freeze:

- candidate version and source digest;
- Control and Treatment definitions;
- fixed task families, projects, and expected/oracle material;
- Host, model, reasoning, permission, and toolchain conditions;
- sample size, repetition, inclusion/exclusion, and Holdout separation;
- metrics, thresholds, failure/recovery handling, and stopping rule;
- independent labeling/evaluation and evidence digests;
- authority, privacy, legal, and claim boundaries.

## Evidence rules

1. No adaptive recommendation or release promotion may affect the run being
   measured.
2. Development fixtures and controlled benchmark outputs remain controlled
   evidence; they cannot satisfy the real-world gate.
3. Holdout data is selected and sealed independently; it is never a substitute
   chosen by the implementation.
4. Missing Real Host, External Project, or independent label evidence yields
   HOLD, not PASS.
5. Do not alter expected/oracle, permissions, or source after the comparison
   begins.

## Three rounds

### Round 1 — preregistration freeze

- Freeze Control/Treatment definitions, metrics, thresholds, and exclusion
  rules.
- Map the fields to the existing qualification schemas.

### Round 2 — mechanics validation

- Run the existing qualification, collection, and signal-validity acceptance
  scripts.
- Confirm they preserve controlled-only and NOT_MEASURED states.

### Round 3 — decision audit

- Check the real-world and independent-evidence gates.
- Emit exactly one of PROMOTE_CANDIDATE, HOLD, or REJECT.
- Keep the decision separate from controlled harness PASS results.

## Completion gate

The stage is complete when a formal decision is recorded, the missing gates are
enumerated, and no controlled result is relabeled as real-world qualification.
