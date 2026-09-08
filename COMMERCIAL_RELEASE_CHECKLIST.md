> Package: **4.3.0** · Package Stage: **Commercial Stable** · Trust Kernel: **4.2.3** · Kernel Base Lineage: **4.0.0-rc.1** · Receipt Protocol: **3.0** · Evidence Schema: **3.0**

# Commercial release requirements — Web UI Quality 4.3.0 (Trust Kernel 4.2.3)

The package identity is 4.3.0 and the Trust Kernel identity is 4.2.3.


A 4.3.0 Commercial Stable package, using the 4.2.3 Trust Kernel, may ship only when Truth Integrity, Browser Security, Release Integrity, public-entry compatibility, and honesty boundaries remain intact. The authoritative package-local Full Release Gate must PASS. Native-Windows qualification is external artifact-bound evidence. Real Codex Host qualification remains an explicitly separate integration claim and may remain `NOT_MEASURED / EXTERNAL_QUALIFICATION_INTERFACE_UNAVAILABLE`; the package must not claim Codex-Host-native enforcement without that evidence.

## Product surface

- `run` remains the default entry.
- CHECK/Inspection receives a normal Human Task Report and never instructs ordinary users to read `--expert-json`.
- `TaskResult v1` validates against public and packaged identical schemas.
- `coverage` is required; a verified repair cannot omit Patch/Target/Critical Context coverage.
- Human output discloses Patch vs Global coverage.
- Legacy repair-machine fields remain compatibility aliases only where explicitly documented; 4.2.3 trust claims use current receipt/evidence contracts.

## Trust kernel

- Public `run` write-backed verification accepts only trusted Receipt Protocol v3 for a new `VERIFIED` claim; legacy receipts are history/migration-only.
- Host Write Receipt / Tool Result / Drift / Checkpoint / Auth regressions remain green.
- Unexpected write or unexpected repository drift blocks `VERIFIED`.
- Resume never restores write permission.
- Project tool evidence remains conditional and Host-gated.
- Repair-scope revert plan carries no write authority and cannot claim whole-repository restoration.

## Product evidence

- `scripts/fault_injection_harness.py --self-test` prepares exactly 40 deterministic legacy qualification fixtures.
- Deterministic Root-Source Recall@5/8 is reported as a measured product signal, not a harness PASS gate.
- Protected Scope Recall is 100% in the qualification fixtures.
- Harness output explicitly reports `NOT_VERIFIED_HOST_AGENT`; Claude/Codex repair accuracy/cost/variance remain NOT_MEASURED until an external Desktop Host run is ingested.
- Host/controller/evaluator roots are path-separated; plan and evaluator manifests are sealed; result ingest is controller-contained and immutable.
- Root Cause Precision/Recall use set semantics; no-op Scope Precision is N/A; Regression Escape exposes multiple denominators.
- `scripts/benchmark_attack_suite.py` completes 1200 deterministic Fake-Agent probes.
- No release note may claim Claude/Codex accuracy, False VERIFIED rate or model pass@k from synthetic harness infrastructure alone.

## Privacy

- `scripts/privacy_egress_acceptance.py` passes.
- New Runtime network-capable imports require an explicit adapter/infrastructure allowlist decision.
- Host AI provider data handling is documented as a Host/deployment responsibility, not silently attributed to the Runtime.

## Release integrity

- `python -B scripts/release_gate.py --mode full` is the single authoritative package-local release decision; every required gate must be `PASS`.
- dependency preflight runs before tests. Core validation may report optional Browser capability as `NOT_MEASURED`; Full qualification requires Playwright and a usable Chromium-family executable and must fail deterministically when either is absent.
- public-mainline V3 end-to-end acceptance, package/kernel acceptance, full pytest modules, Product Experience, Security/Evidence, Browser Safety, Trust Integrity, Real Project, Agent Governance, Repair/Modernization, Benchmark, Performance and Distribution gates pass.
- schema bundles are byte/JSON equivalent.
- current user distributions do not require historical GA/PATCH status JSON merely to prove old claims existed; historical evidence is not promoted into current 4.2.3 evidence.
- final archive has one `web-ui-quality/` root and excludes caches, `.git`, evidence caches and nested release archives.
- Real Codex Host and native-Windows qualification remain separate external evidence and are not upgraded by package-local PASS.
- Native Windows qualification must execute the real `cmd.exe` worker success/failure integration test; non-Windows runs may only report that test as skipped / `NOT_MEASURED`.
- Native Windows qualification must also execute the junction/reparse-point write-boundary regression; Linux symlink coverage does not substitute for Windows filesystem semantics.
