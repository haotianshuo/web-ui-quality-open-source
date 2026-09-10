# Stage 13 Protocol — External Real Project Qualification

## Scope

Qualify external public Web projects only when the target, fixed commit,
permission, task, expected/oracle, and verification environment are explicitly
available. A public URL alone is not a qualified Holdout.

## Evidence rules

1. Never use an arbitrary public repository as a Control, Treatment, or Holdout
   substitute.
2. Do not clone, modify, or submit changes to an external project without a
   scoped target and user-authorized task.
3. Preserve the fixed commit and target baseline before any execution.
4. Separate source inventory, Browser result, Host result, user completion, and
   legal/Open Source evidence.
5. A public repository's README, stars, or successful clone cannot prove the
   WUQ task was completed or verified.

## Qualification fields

Each external-project row requires:

- repository URL, owner, license, and fixed commit;
- target task and non-goals;
- source baseline and expected/oracle;
- Host identity, model, permission, and tool trace;
- Browser capability and target reachability;
- before/after evidence, source diff, verification, and receipt;
- authorization and legal boundary.

## Three rounds

### Round 1 — target inventory

- Search the current workspace and supplied evidence for explicitly authorized
  external project targets.
- Freeze candidate rows without inventing missing fields.

### Round 2 — qualification preparation

- Check that each candidate has a fixed commit, expected/oracle, permission,
  and reversible task.
- Run no external task when any required field is absent.

### Round 3 — promotion audit

- Confirm whether any row has complete external evidence.
- Keep the result NOT_MEASURED when no qualified target exists; run only local
  evidence-boundary regression.

## Completion gate

The stage is complete when external candidates are either fully qualified or
explicitly rejected/unmeasured with exact missing inputs. No Holdout substitute
may be selected by inference.
