# Stage 10 Protocol — Zero User-Managed Python Setup

## Scope

Compare the five installation/runtime directions named by the execution
instruction:

- A: Python Core plus a standalone executable wrapper.
- B: bundled or embedded Python runtime.
- C: small native bootstrapper plus the existing Core.
- D: gradual native migration.
- E: Node rewrite as a non-default alternative.

The decision concerns user-managed prerequisites and operational risk. It does
not authorize a rewrite, a new binary release, signing, publishing, or a new
runtime implementation in this stage.

## Evidence rules

1. Measure the current package and local install/build behavior directly.
2. Separate measured local facts from estimates and NOT_MEASURED cross-platform
   or signing claims.
3. Do not claim a clean-machine result when the machine is not clean or the
   operation was not performed.
4. Keep the existing Python Core as the comparison baseline; no expected,
   oracle, scope, evidence, or authority changes are allowed.
5. Select the simplest stable direction supported by the evidence. If a
   choice requires missing external data, record the choice as provisional and
   keep the unresolved issue.

## Metrics

For each option record:

- clean-install steps and user-managed Python/Node prerequisites;
- administrator requirement;
- package/download footprint and cold-start implications;
- Windows, macOS, and Linux path;
- upgrade, uninstall, signing/attestation, and maintenance burden.

## Three rounds

### Round 1 — current baseline

- Inspect package metadata, entry points, scripts, and documented runtime
  prerequisites.
- Run local help and package-build probes in an isolated temporary directory.

### Round 2 — option comparison

- Compare A-E against the same metrics.
- Run an isolated install/import/help smoke test without changing the user's
  global Python or Node setup.

### Round 3 — repeatability and decision

- Repeat the local wheel/help probe and inspect uninstall/upgrade evidence
  available in the package.
- Choose the smallest stable direction, or record the missing inputs that keep
  the decision provisional.

## Completion gate

The stage is complete when stage-10/result.md records the comparison, direct
probe outputs, decision, NOT_MEASURED items, and confirms no source-code or
authority change.
