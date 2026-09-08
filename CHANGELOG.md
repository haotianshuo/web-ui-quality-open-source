# 4.3.0 — Commercial Stable

- Preserve the sealed 4.2.3 Trust Kernel, Host-only physical-write authority, V3 Receipt protocol, secure Browser policy, TaskResult v1 semantics, and evidence-only Claim Boundary.
- Add bounded non-authoritative intelligence contracts for Task Fingerprint/Graph, execution budgets, controlled replan, design intent, candidate arena, evidence-qualified design gates, and memory authority.
- Reuse the existing 4.2.3 design candidate and design-system pipeline instead of creating a parallel design engine.
- Treat missing patch hunks as NOT_MEASURED for Goal→Change traceability and distinguish changed existing files from newly added files in complexity analysis.
- Keep subjective design findings permanently Advisory and prohibit intelligence extensions from granting write or claim authority.

# 4.2.3 — Commercial Stable

- Promote the fully qualified 4.2.3-rc.5 code line to the final 4.2.3 Commercial Stable identity without changing Runtime behavior, Trust policy, Browser policy, Public API, schemas beyond version identity, or security authority.
- Preserve the rc.5 Windows Browser Oracle discovery closure, rc.4 Query Navigation mainflow closure, V3 Receipt, Protected Scope, Junction/reparse, Drift, and Host-only write authority exactly as qualified.
- Require the authoritative package-local Full Release Gate and deterministic archive validation on the final 4.2.3 tree.
- Native-Windows qualification is external evidence bound to the exact final artifact SHA-256; package metadata does not self-promote external evidence.
- Real Codex Host qualification remains `NOT_MEASURED / EXTERNAL_QUALIFICATION_INTERFACE_UNAVAILABLE`; Commercial Stable does not claim Codex-Host-native enforcement or Host-produced V3 Receipt qualification.

# 4.2.3-rc.5 — Windows Browser Oracle Discovery Closure Candidate

- Fix the Windows Full Gate product defect where release preflight could discover a desktop-installed Chrome/Edge through the shared browser locator while the fault-injection Browser oracle used PATH-only `shutil.which(...)` discovery and then attempted a missing Playwright-bundled Chromium, producing `EXECUTION_FAILED`.
- Reuse `resolve_browser_executable(...)` in the fault-injection Browser oracle so release preflight and benchmark execution share one executable-discovery contract, including Windows `Program Files` desktop installs.
- Preserve Secure Browser Context, local synthetic-fixture restrictions, query authorization, sandbox refusal, V3 Receipt, Protected Scope, Junction/reparse, Drift, and Host authority without feature expansion.
- Add a regression that prevents the Browser oracle from reintroducing PATH-only Chromium discovery.
- Real Codex Host qualification remains `NOT_MEASURED`; this is a release-stabilization fix only.

# 4.2.3-rc.4 — Query Navigation Mainflow Closure Candidate

- Fix the authenticated document-navigation P1 in which callers pre-canonicalized a query-bearing route and `BrowserMutationFirewall` canonicalized it again, dropping the query digest and rejecting the exact approved target as `ROUTE_NOT_APPROVED`.
- Make `BrowserMutationFirewall` the single runtime owner of navigation-route canonicalization; `playwright_adapter`, `smart_acceptance`, and `ui_inventory` now pass raw approved target URLs into Secure Context.
- Preserve the authenticated `ui_inventory` start URL query for the explicitly requested target while keeping evidence privacy: reports expose only `navigation_route_key(...)` digests, never raw query values.
- Add a production-path regression covering `playwright_adapter -> create_secure_context -> BrowserMutationFirewall`: exact approved query navigation is allowed and a changed query remains blocked.
- No change to V3 Receipt, Protected Scope, Host write authority, Junction/reparse policy, Query Digest algorithm, Drift, or Adaptive Trust Kernel authority. This is a release-stabilization fix, not a feature release.
- Real Codex Host qualification remains `NOT_MEASURED`; Stable/Commercial promotion still requires the applicable external qualification policy.

# 4.2.3-rc.3 — Release Identity Closure Candidate

- Closes the current candidate's release identity by adding the missing release notes and updating stale release-gate and Browser-policy version labels.
- Makes no Runtime logic or security-policy change and preserves the 4.2.3-rc.2 Browser oracle behavior.
- Remains a release candidate: real Codex Host qualification is still `NOT_MEASURED` and is not claimed by this release-identity closure.

# 4.2.3-rc.2 — Browser Oracle Evidence Semantics Correction

- Corrects Browser oracle evidence semantics so the enforced network policy and the local synthetic fixture mode are reported as distinct facts rather than conflated under one field.
- Preserves the fail-closed local-fixture, authorization, storage-state, and network boundaries established by 4.2.3-rc.1.
- Does not claim real Codex Host qualification; that environment remains `NOT_MEASURED`.

# 4.2.3-rc.1 — Native Windows + Browser Trust Closure Candidate

- Repairs the native Windows junction qualification fixture by removing `cmd.exe /S` quote rewriting and executing a separately rendered `mklink /J` command line.
- Extends authenticated document-navigation authorization from path-only matching to privacy-preserving Path + Query Digest matching.
- Restricts the fault-injection Browser oracle to local synthetic fixtures, reuses the shared Secure Browser Context, and rejects live URL/auth/storage-state inputs.
- Adds plain-language failure guidance in the Human Task Report: reason, responsible actor, and whether/how the task can continue.
- Remains a release candidate: Native Windows and Real Codex Host commercial qualification require external evidence from those exact environments.

# 4.2.2 — Trust Release Candidate / Package-local Stable Candidate

- Reclassified the package from commercial Stable to candidate while Native Windows and real Codex Host qualification remain `NOT_MEASURED`; the Python package version remains 4.2.2.
- Replaced the Windows release-worker tab-delimited `.cmd` status protocol with JSONL so successful native Windows child processes cannot be misparsed as `WORKER_ABORTED` merely because `cmd.exe` echoed literal `\\t` characters.
- Added a native-`cmd.exe` success/failure regression that is intentionally skipped outside Windows and therefore cannot be promoted into Native Windows evidence on Linux/macOS.
- Hardened authenticated Browser GET handling: XHR/fetch-style GET reads require exact machine authorization; query-bearing approvals bind a normalized SHA-256 query digest without persisting raw query values.
- Changed ordinary Human Task Report wording from editor-specific language to Host/workspace-neutral language.
- Release evidence now carries the explicit package stage; exact collected/pass/skip counts and environment provenance must be regenerated from the same candidate artifact instead of reusing earlier 4.2.2 validation numbers.

- Fixed dependency preflight so missing optional Playwright/Browser capabilities produce structured Core/Full gate outcomes instead of import tracebacks.
- Forced package-local acceptance to load the current `runtime/python` tree and report its runtime location/digest, preventing an externally installed older package from contaminating release evidence.
- Standardized UTF-8 subprocess handling for release/acceptance paths without changing project-file encodings.
- Bound Browser request approvals to task/run/session, purpose, expiry and RunConditions; unbound approvals fail closed.
- Kept V3 Receipt, Protected Scope, Drift, Project Tool, Required Verification and Claim Boundary as non-skippable trust gates.
- Simplified the default Human Task Report to four areas: result, changes, verification and next step. Machine/expert reason codes remain available outside the normal human surface.
- Added a measurement specification that keeps synthetic scenarios separate from real Host/user evidence.
- Added an Adaptive Trust Kernel RFC only. It is `NOT_ACTIVE_IN_STABLE`, has `NO_AUTHORITY_EFFECT` and `NO_CLAIM_EFFECT`.
- Real Codex Host qualification, Native Windows qualification, real-user effect, real-model accuracy and real-world Token savings remain `NOT_MEASURED` unless independently executed.

# 4.2.1 — Trust & Release Closure

- Make Host Write Receipt v3 the only receipt protocol that can support a new 4.2+ `VERIFIED` repair claim. Legacy receipts remain readable for history/migration and deterministic failure diagnosis only.
- Add a public-mainline V3 apply binding: Patch Candidate → immutable V3 Host Apply Binding → external Host write → HMAC-attested V3 receipt → After verification. Runtime never self-signs or self-authorizes the Host write.
- Wire ExecutionState, evidence lifecycle projection, and UserOutcome into the guided repair result so `DISCOVER/PREFLIGHT/PLAN/HOST_APPLY/VERIFY/REPORT` cannot be represented as a verified repair without the required evidence path.
- Add one dependency-aware release gate. Core validation reports optional Browser capability as `NOT_MEASURED`; Full release qualification requires Playwright plus an executable and fails deterministically at preflight instead of pytest collection.
- Remove current-package dependence on historical 4.1 GA/PATCH status JSON. Historical evidence is not promoted into the current package claim.
- Harden the Browser policy: shared Chromium launch policy, no implicit `--no-sandbox`, exact authorization for dangerous GET/WebSocket/request paths, fail-closed handling of custom credential-like headers, and origin-bound credential state.
- Keep v5 Context Ranking, Adaptive Guidance, and Adaptive Exploration out of this closure release. Frozen holdout results remain diagnostic; real Codex Host and native-Windows qualification remain `NOT_MEASURED`.

# 4.2.0 — Trust Integrity / Secure Browser Baseline

- Introduced Receipt Protocol 3.0 contracts, secure Browser-context controls, execution-state contracts, and the 4.2 release identity baseline.
- This release is retained as the architectural predecessor to 4.2.1; 4.2.1 closes the public-mainline, release-gate, and contract-convergence gaps found during review.

# 4.1.1 — GA Identity / Documentation Closure

- Keep the 4.1 feature set frozen; no Runtime capability, Context Ranking, Adaptive behavior, Write Authority, Claim Authority, or Trust Kernel logic is added.
- Change the outward package classifier from Beta to `Production/Stable`.
- Clean current Quickstart, Commercial Checklist, Architecture, Security, Compatibility, and Acceptance document identities so the installed package consistently presents `4.1.1`.
- Split package-level public acceptance from frozen-kernel public compatibility acceptance while retaining the historical `public_acceptance.py` compatibility entry point.
- Preserve the frozen kernel evidence identity at `4.0.0-rc.1`; historical Benchmark/Kernel evidence is not rewritten as 4.1.1 evidence.
- Keep real-world predictive validity and real Codex Host pre-write enforcement explicitly `NOT_MEASURED`.
- Context Ranking v2 is intentionally excluded from the stable patch and remains a separate research track requiring a new independent holdout before stable adoption.

# 4.1.0 — General Availability

- Promote the feature-frozen 4.1 package from RC.1 to GA without enabling Adaptive Guidance or Adaptive Exploration.
- Keep the 4.0.0-rc.1 kernel evidence identity frozen and distinct from the 4.1.0 package identity.
- Preserve Fixed Workflow as the authoritative execution/result path; production shadow and qualification tooling remain non-authoritative.
- Keep real-world predictive validity and real Codex Host pre-write enforcement explicitly `NOT_MEASURED`.
- GA maintenance is limited to qualification evidence plus security, bug, packaging/integrity, and compatibility fixes.

# 4.1.0-rc.1 — Release Candidate Hardening

- Feature-frozen Release Candidate; no new controller, agent, adaptive policy, authority mechanism, or product capability is introduced.
- Promote outward package identity from final Alpha to `4.1.0-rc.1` while retaining `4.0.0-rc.1` as the frozen kernel evidence identity.
- Keep Fixed Workflow authoritative and production shadow/external qualification non-authoritative.
- Keep real-world signal predictive validity and real Codex Host pre-write enforcement `NOT_MEASURED`.
- Add RC readiness, install/upgrade, package-integrity, and honesty gates; only release-blocker repairs are permitted after this point.

# 4.1.0-alpha.7 — External Qualification Collection + Product Closure

- Final planned 4.1 Alpha; feature development freezes after this package.
- Add allowlist-only production-shadow export with caller-key HMAC pseudonymization of task/session bindings and request digests.
- Add Host-attestation request and independent-label request contracts; neither request can self-promote into authoritative provenance or a confirmatory label.
- Add collection manifest that preserves `realWorldPredictiveValidity = NOT_MEASURED`, `Adaptive Guidance = NOT_ACTIVE`, and `real Codex Host enforcement = NOT_MEASURED`.
- Add package-self-reproducible collection acceptance covering privacy leakage, stable/key-scoped pseudonyms, schema parity, and non-authoritative boundaries.
- No new controller, agent, model score, Profile/Clamp activation, write authority, or Claim authority.

# 4.1.0-alpha.6 — Independent Shadow Qualification Harness

- Add machine-readable Qualification Plan, Qualification Case, and Qualification Report contracts.
- Separate `PRODUCTION_SHADOW`, `CONTROLLED_BENCHMARK`, and `SYNTHETIC_FIXTURE` evidence so controlled/synthetic rows cannot satisfy a real-world gate.
- Require independent outcome labels plus `HOST_ATTESTED` provenance before a production shadow row can count as real-world qualification evidence.
- Add duplicate task-binding protection, coverage gates, per-signal preregistered threshold checks, and explicit HOLDOUT exclusion by default.
- Keep qualification offline and non-authoritative; passing the pre-gate can only make a signal eligible for later Phase 3.5 preregistration, never activate Adaptive Guidance.
- Real-world predictive validity and real Codex Host enforcement remain `NOT_MEASURED` in the shipped package.

# 4.1.0-alpha.5 — Shadow Dataset & Signal Validity Pre-Gate

- Add an offline dataset builder for production capability-shadow observations.
- Add explicit outcome-label provenance: independent external labels are separated from Fixed Workflow proxy and synthetic labels.
- Exclude HOLDOUT labels from development analysis by default.
- Add deterministic per-signal TP/FP/FN/TN, precision, recall, and false-positive-rate metrics for labelled development rows.
- Keep `predictiveValidity = NOT_MEASURED` when no independent real labels exist; synthetic acceptance data is test-only.
- Do not emit model capability scores, Profile/Clamp recommendations, or any adaptive effect.
- Fixed Workflow remains authoritative; Adaptive Guidance and Adaptive Exploration remain NOT_ACTIVE.

# 4.1.0-alpha.4 — Phase2 Capability Shadow Observation

- Production shadow artifacts now include mechanical and derived-deterministic capability signals.
- Signals have `authorityEffect = NONE` and `adaptiveEffect = NONE`; semantic signals are not used.
- No model capability score, autonomy recommendation, or profile transition is produced.
- Offline summaries report frequency only and keep `predictiveValidity = NOT_MEASURED` until the Signal Validity Gate.
- Fixed Workflow remains authoritative; Adaptive Guidance and Adaptive Exploration remain NOT_ACTIVE.

# 4.1.0-alpha.3 — Phase1 Runtime Shadow Wiring

- Wire the Phase1 observer into the real `run_experience_fix` production path as a non-authoritative sidecar.
- Fixed Workflow remains the only authoritative workflow; shadow failures are fail-open and cannot change result, authority, claims, evidence, or TaskResult.
- Persist shadow observations under `experimental/phase1-shadow/`, outside sealed Before/After/Compare/Report evidence phases.
- Keep real Codex Host enforcement `NOT_MEASURED`; Adaptive guidance/exploration remain inactive.
- Add package-self-reproducible runtime shadow acceptance and no-authority regression tests.

# 4.1.0-alpha.2 — Phase1 Boundary Closure

- Closed read/write symlink, junction/reparse, and hardlink alias boundary bypasses in the Phase1 minimal trust-contract slice.
- Fixed Required Claim aggregation so NOT_VERIFIED/INVALIDATED cannot be softened to PARTIAL by sibling VERIFIED claims.
- Added mutation/state-epoch evidence freshness and kept wall-clock age as audit metadata rather than the primary freshness authority.
- Narrowed the Phase1 minimal ReadAuthorizationBoundary schema to controls that are actually enforced.
- Split package identity (4.1.0-alpha.2) from frozen kernel evidence identity (4.0.0-rc.1).
- Added PHASE1 overlay + composite release manifests and made verify_distribution validate the composite before other gates.
- Shipped a self-reproducible Phase0 46-check runner and independent simulated-Host Phase1 acceptance.
- Real Codex Host enforcement remains NOT_MEASURED; Adaptive Runtime remains not production-wired.

# Changelog

## 4.0.0-rc.1 — Closure

- Froze the feature set; no new Runtime, benchmark, retrieval, risk, budget, evidence-authority, or CLI capability was added.
- Fixed the Intent Router precedence bug where repair requests containing responsive/accessibility/performance specialty terms could be downgraded to read-only specialized audits.
- Kept specialty as orthogonal metadata on the existing public contract; repair actions remain `REPAIR_SMALL`/`fix`, explicit read-only language remains authoritative, and routing still never grants Host write authority.
- Aligned conservative control intent with direct optimization requests such as “优化这个页面…”, while keeping “告诉我应该怎么优化” and explicit no-edit language read-only.
- Added a small Convergence Acceptance covering Intent → Risk Tier → Change Budget → verification → Evidence Graph invariants and the known responsive/accessibility regression cases.
- Cleaned current product wording so historical release lineage lives in this changelog rather than the user-facing capability surface.
- Benchmark corpus, frozen holdout, retrieval rules, Trust Kernel, Risk Tier, Change Budget, Evidence Graph, Browser Oracle, and HMAC protocol are unchanged from beta.7.

## 4.0.0-beta.7 — Trust + Benchmark Convergence

- Converged the two divergent beta.6 branches onto the Architecture Consolidation runtime; Risk Tier T0–T4, Change Budget, Evidence Dependency Graph, fine-grained Intent Router, 3.7.5-derived UX, 3.7.4 Governance, 3.7-design-lineage Transformation, and the 4.0 Trust/Repair Kernel are all retained.
- Upgraded benchmark mechanics from the Benchmark Validity Closure: 40 distinct development archetypes, all-applicable-case context metrics, executable behavior oracles, Controller-planned condition authority, and 12 adversarial strategy families / 1200 deterministic probes.
- Added Benchmark Protocol v4 controller-private HMAC-SHA256 authentication. Plan/Controller-state integrity can no longer be restored by merely mutating an artifact and recomputing its public SHA digest; evaluator-manifest MACs are bound into authenticated Controller state.
- Added a frozen 8-case obfuscated-root holdout corpus. Holdout retrieval is reported diagnostically and is explicitly not a release-tuned recall gate. The corpus is hidden from prepared Host workspaces but is shipped with the package and is not claimed secret from maintainers.
- Added Playwright Browser Behavioral Oracles for viewport containment, page overflow, minimum target size, top-layer hit testing, text, and computed CSS assertions. HTTP/HTTPS requests are aborted during fixture evaluation; unavailable browsers yield an explicit unmeasured environment state.
- Hardened NODE_SCRIPT oracle execution with bounded CPU/file/process resources and isolated HOME/TMP while explicitly reporting `PROCESS_LIMITED_NOT_OS_ISOLATED`; hostile same-user Agent execution still requires an external container/ACL/OS sandbox.
- Preserved external Host/model accuracy as NOT_MEASURED until real Codex/Claude-style runs are ingested. Synthetic and holdout acceptance qualify benchmark mechanics, not model quality.
- Rebased the coarse import-time disaster guard from 3.0s to 3.5s after same-environment checks showed beta.7 faster than the beta.6 architecture baseline despite occasional runner p95 jitter; same-environment relative regression remains the meaningful comparison.

## 4.0.0-beta.6 — Architecture Consolidation

- Consolidated the strongest 3.7.5 real-page UX, 3.7.4 governance, and 3.7-design-lineage transformation/decision behavior onto the 4.0 Trust / Repair Kernel instead of creating parallel runtimes.
- Expanded natural-language routing with explicit `VERIFY_ONLY`, `EXPLAIN`, `REPAIR_SMALL`, `TRANSFORM`, and specialized-audit intent metadata while preserving compatibility execution modes and zero write authority.
- Added deterministic T0–T4 Risk Tier classification; protected non-goal clauses such as “不要动登录逻辑” do not themselves escalate mutation risk.
- Added Change Budget with file-count, explicit-scope, new-file, dependency and config boundaries; budget status now participates in final repair verification.
- Added an Evidence Dependency Graph linking Goal, Baseline, Before, scope, Host Write Receipt, After, project tools, Patch Quality, Drift, comparison and final verification.
- Kept 4.0 tamper-evident `ExperienceRun` as the authoritative evidence store rather than downgrading to the older 3.7.5 artifact implementation.
- Preserved the single normal `run` entry and hidden compatibility/expert CLI surface.
- Retained the 40-case deterministic legacy corpus and 1200-run fake-agent attack qualification from beta.5; these still qualify benchmark infrastructure, not real Claude/Codex repair accuracy.

## 4.0.0-beta.5 — Benchmark Trust & Corpus Qualification

- Split Host workspaces, benchmark controller and evaluator-private ground truth into separate filesystem roots.
- Added sealed benchmark plans/controller state and per-manifest ground-truth digests.
- Made result ingest controller-contained and immutable; Host result paths are no longer accepted.
- Corrected Root Cause Precision/Recall, no-op Scope Precision and Regression Escape denominators.
- Added condition fingerprints and a benchmark-report schema.
- Added a 40-case deterministic legacy corpus with behavioral oracles.
- Added a 1200-run fake-agent benchmark attack suite and a 72-run Claude/Codex Desktop qualification-pack generator.
- Added p50/p95 performance output with optional same-environment 10% regression comparison.
- Improved evidence-insufficient inspection next action to request a runnable URL before recommending source changes.
- External Claude/Codex repair accuracy remains NOT_MEASURED until real Desktop runs are ingested.

## 4.0.0-beta.4 — Agent Benchmark Qualification

- Reworked the fault-injection harness into blind Host workspaces with evaluator-private ground truth; expected root source, clean content and expected scope are never written into Host-visible project state.
- Added an external Host-Agent result contract and qualification CLI for 10-case × repeated-run preparation, result ingestion and aggregation.
- Ground-truth repair success is evaluator-computed from final workspace state; Host results cannot self-assert `groundTruthRepaired`.
- Added empirical pass@1/pass@k, False VERIFIED, Wilson 95% interval/rule-of-three upper bound, root-cause precision, scope precision, regression escape and host-reported cost/time/token variance summaries.
- Added explicit Host configuration comparability checks; mixed Host/model versions are not treated as a comparable benchmark baseline.
- Preserved `NOT_VERIFIED_HOST_AUTOMATION` when no external Codex/Claude/Cursor-style runner is connected.
- Added benchmark protocol tests and schema parity without expanding the stable root Python API.


## 4.0.0-beta.3 — Product Evidence Foundation

- Added `TaskResult v1` as a convergence layer over existing inspection/repair/modernization results; Beta.2 repair-machine fields remain compatibility aliases.
- Human Task Report now covers CHECK/Inspection as well as repair; ordinary users are no longer redirected to `--expert-json` for read-only checks.
- Made verification `coverage` mandatory in the TaskResult schema; a repair `VERIFIED` requires complete patch/target/critical-context coverage while global coverage remains explicit.
- Added deterministic Relevant Context Packet v1 and Root-Source Recall/Protected-Scope measurement. Mandatory safety context is never removed by source-reference budgets.
- Added a 10-case fault-injection harness qualification. It explicitly reports Host-Agent accuracy/cost/variance as NOT_VERIFIED/NOT_MEASURED until an external model runner executes repeated cases.
- Added executable Runtime network-egress policy acceptance with explicit Figma/local-report-server exceptions.
- Added tamper-evident repair-scope revert plans derived from trusted Host write receipts; Runtime still cannot write or promise whole-repository rollback.
- Candidate generation now supports 1–3 requested product directions while retaining a default of three for compatibility.
- Added Beta.3 product-evidence tests and an independent Product Evidence Foundation acceptance gate.

## 4.0.0-beta.2 — Guided Repair Hardening

- Added `READ_ONLY_PROJECT` to Host-gated project-tool plans plus explicit filesystem-policy enforcement and unexpected-write reporting.
- Added `host-project-tool-result.schema.json`; missing filesystem enforcement is `NOT_VERIFIED`, unexpected writes are `FAIL`.
- Final Repair Verification now consumes bounded project drift; unexpected source/config mutation outside the exact Host write receipt blocks `VERIFIED`.
- Default `run` output is a Human Repair Report; `--json` exposes the stable report envelope and `--expert-json` exposes the internal Runtime result.
- Added CI repair-status exits (`VERIFIED=0`, `REVIEW_REQUIRED=2`, `NOT_VERIFIED=3`, `FAIL=4`, system/contract error=5) and `--require VERIFIED`.
- After verification restores the exact persisted run from `host-write-receipt.runId` when available instead of preferring the latest compatible run.
- Added Beta.2 attack/UX/contract tests and an independent Guided Repair Hardening acceptance gate.

## 4.0.0-beta.1 — Guided Repair

- Promoted the normal user path to one-line `web-ui-quality run . "task"`; `--request` remains script-compatible.
- Added target-adjacent critical toolchain/config coverage for partial large-repository baselines and bound it into exact scope verification.
- Added critical-context drift protection so changed `tsconfig`/package/workspace conditions require revalidation instead of producing patch-scope VERIFIED.
- Separated Host project-tool result authenticity from semantic success; required tool FAIL/NOT_VERIFIED now blocks overall VERIFIED even when Browser outcome improves.
- Added one final Repair Verification decision across Browser outcome, project-tool evidence and Patch Quality; deterministic quality risk produces REVIEW_REQUIRED.
- Made Repair Report expose Browser / Project Tools / Patch Quality / Host Write dimensions plus a human-readable next action.
- Reused exact scope quality signals for large projects so Patch Quality does not depend on a truncated global baseline.
- Added independent Release Closure Acceptance and guided legacy-repair quickstart.
- Removed remaining public wording that overstated declared candidate-direction differences as rendered structural proof.
- Kept the Trust/Evidence kernel, UI Inventory, Design IR, Browser provider, Host write boundary, checkpoint/resume and 127-module acyclic runtime architecture intact.

## 4.0.0-alpha.10 — Release Closure

- Added target-aware Baseline coverage so large legacy repositories may remain globally partial while an explicit repair scope still has complete Before hashes.
- Added a sealed scope-baseline digest to Host Write Receipt verification, removing the previous requirement that every large repository be globally COMPLETE before a local repair can be verified.
- Closed the Host project-tool loop: exact plan, local binary hash, argv/cwd and Host-enforced policy are verified before a result can become `CONDITIONAL_PROJECT_TOOL_EVIDENCE`.
- Kept project-owned tools Host-gated; Runtime still cannot execute them or promote their output to independent parser evidence.
- Split design `recommendedCandidate` from `selectedCandidate`; no candidate is silently selected before human preference.
- Renamed the candidate difference authority to `DECLARED_DIRECTION_CONTRACT_DIFFERENCE`; the legacy structural-difference field remains a compatibility alias only.
- Froze the current 226 root exports in `public-api-manifest.json`; `run` is the only stable new facade and the four post-a6 root additions remain expert-compatibility surfaces.
- Corrected normal CLI guidance to `run / doctor / auth / expert` and updated Product Experience Acceptance accordingly.
- Published the actual performance budgets enforced by the release gate.
- Deliberately deferred the 127-file package reorganization: the current import graph remains acyclic, so Release Closure prioritizes user-blocking repair integrity over a risky big-bang file move.

## 4.0.0-alpha.8 — Trust & Main Run Closure

- Added explicit Project Baseline completeness and fail-closed behavior for truncated or unindexed targets.
- Hardened control intent, finding-to-source ownership, dangerous GET blocking, and authenticated route allowlisting.
- Added tamper-evident decision ledgers and process-trusted Host Write Receipts bound to immutable run identity, exact patch scope, toolchain/verification context, and per-file Before/After hashes.
- Required persisted fix-plan receipt binding before local-project After verification.
- Added `run --after-url` and `--host-write-receipt`; the public entry now resumes the latest matching repair run and reuses its sealed session identity.
- Propagated `FRAMEWORK_NOT_SUPPORTED` through design and production entry points with nonzero CLI exits; unsupported frameworks are never disguised as HTML success.
- Removed machine-specific absolute paths from the primary persisted artifact boundaries and synchronized the public/packaged Schema bundles.
- Kept Alpha.10+ Design IR normalization, Adapter expansion, and Visual Workbench redesign explicitly out of this release claim.

## 4.0.0a7 — Repair & Modernization Consolidation

- Consolidated normal use around `run`, `doctor`, `auth`, and `expert`; historical task commands remain compatibility surfaces.
- Added a Sealed, file-indexed Project Baseline that reuses ExperienceRun Before-phase integrity and classifies target/toolchain drift.
- Added systemic-root-cause planning for one shared patch plus N affected-surface verifications.
- Added baseline-relative Patch Quality checks for newly introduced debt signals.
- Added Host-gated project-tool execution plans for allowlisted local JS/TS verification tools; Runtime never executes project-owned tools autonomously.
- Added explicit Authentication Profiles that reference and digest-bind Playwright storage-state outside the project.
- Added deterministic Verification Budget selection and a unified user-facing Repair Report.
- Clarified the Browser contract: Playwright is the driver; Chrome/Edge/Chromium is the executable; `--browser-executable` does not bypass Playwright.
- Froze the 221 a6 top-level exports as a Compatibility Baseline before package reorganization.
- Added release-document identity/link parity and a performance acceptance gate.
- CI scope remains reporting on the current runner; portable remote attestation is explicitly not claimed.

## 4.0.0a6 — Agent Workflow Governance

- Added tamper-evident Run Checkpoint/Resume bound to ExperienceRun identity and external integrity keys; resume never restores Host source-write authority.
- Added Task Goal Anchor with explicit success criteria, non-goals, scope-change history, and DIRECT/SUPPORTING/UNRELATED auto-fix policy.
- Added Assumption Invalidation Graph with explicit supersession, transitive dependent invalidation, raw-observation retention, and invalidation ledger entries.
- Added adaptive evaluator routing with minimal/standard/full profiles, explainable active/skipped capabilities, and mandatory PageHealth/EvidenceIntegrity safety floor.
- Added append-by-supersession Decision / Trade-off Ledger linking evidence, findings, patches, risks, expected outcomes, and verification plans.
- Added conservative natural-language control intent for check/fix/current-page/full/checkpoint/resume/assumption-revision/protected-scope requests; ambiguous mutation requests fail closed.
- Added outcome-driven verification primitives that require declared acceptance criteria and return NOT_VERIFIED for missing checks.
- Added serial mutation verification policy for HIGH-risk changes plus integration verification.
- Added Run Health as measured operational state only; no fabricated token/context percentages.
- Added nine governance schemas, schema parity coverage, 47 direct governance unit tests, and an independent Agent Workflow Governance Acceptance gate.
- Preserved a5 Browser Provider, CLI product shell, Evidence Integrity, Host Write Boundary, Before/After binding, and distribution-history exclusions.

## 4.0.0a5 — Product Shell Hardening

- Unified Browser executable discovery across public Browser-backed workflows: explicit path, Playwright bundle, PATH, then common Chrome/Edge/Chromium desktop installs.
- Added `--browser-executable` to `experience-fix`, `inspect`, `ui-inventory`, smart acceptance and comparison compatibility paths; `doctor` now reports the same resolver decision.
- Set the CLI program identity to `web-ui-quality` and completed user-facing help for every `ui-inventory` argument.
- Preserved machine JSON Pointer diagnostics while adding a clean CLI-facing ContractViolation representation.
- Added explicit public / expert / internal-compatibility command lifecycle metadata for all 49 reachable subcommands.
- Improved smart-acceptance empty states, screenshot guidance, and Chinese claim/coverage boundaries so reports do not render empty Top-0 sections or point at missing screenshot output.
- Added product-shell regression tests and kept the tamper-evident Evidence/Host-write trust boundary unchanged.
- Commercial release archives now exclude `references/history/`; historical regression screenshots/reference outputs are removed from the upgraded distribution payload.

## 4.0.0a4.post1 — UI Asset Inventory extension

- Added a read-only whole-site UI inventory for pages, Buttons, Inputs, Cards, Dialogs, Tables, Icons, colors, typography, radii, and spacing.
- Added source/runtime route discovery, dynamic-route deduplication, Computed Style fingerprints, near-style/color clustering, same-purpose Button drift, and page style profiles.
- Reused Browser Mutation Firewall, screenshot evidence, and Design System Map token comparison without expanding Runtime write authority.
- Added `ui-inventory` CLI, default intent routing, JSON Schema, fixture coverage, unit/regression tests, and a Browser acceptance harness.

## 4.0.0a4 — Trust Integrity Hardening

- Added trusted source parsers and conservative unsupported-format results.
- Unified command policy with nested package-script and lifecycle expansion.
- Added ExperienceRun v2 tamper detection, strict paths, signed manifests and transition ledger.
- Bound After to actual URL and hardened improvement claims.
- Removed Runtime source-write authority; Host applies Patch Candidates.
- Replaced filename guessing with evidence-backed source ownership.
- Added attack-grade trust-integrity regression.

## 4.0.0a3 — Experience Integrity Rebuild

- Added the single default `experience-fix` entry with Host-routed CHECK, FIX_AND_VERIFY, DEEP_REDESIGN, and SPECIALIZED_AUDIT modes.
- Added immutable ExperienceRun sessions with sealed Before evidence, SHA-256 manifests, strict After binding, and source-lineage recording.
- Separated PageHealth from visual findings and made runtime, auth, resource, data, and task failures outrank cosmetic defects.
- Added composite readiness, resource integrity classification, lifecycle-aware safe project startup, Browser Mutation Firewall, reversible task probes, UX Repair Recipes, bounded discovery cache, Host Bridge contracts, and a three-attempt policy.
- Unified standard evidence conditions to 390×844, 768×1024, and 1440×900 with touch/DPR profiles plus viewport and full-page screenshots.
- Split product experience, security/evidence, Browser safety, distribution, and real-project integration acceptance suites.

## 4.0.0a2 — Product Experience Rebuild

- Added intent-led Inspect, Fix, Redesign, and Specialized Audit routing.
- Reduced normal CLI help while preserving expert compatibility commands.
- Added root-cause failure recovery and a shared Browser capability registry.
- Added read-only fix preparation, honest unknown business context, one primary report entry, and two redesign directions by default.
- Moved old generated reference output into a clearly marked historical directory.

## 4.0.0a2 — v2.3 P0-A Smart Acceptance preview

- Added the single `check` entry point for a runnable URL or local static project.
- Added runtime Preflight for representative rendering, bounded readiness, critical resource blocking, runtime errors, authentication hints, environment classification, and A0/A1 interaction policy.
- Changed the default viewport matrix to mobile `390×844`, small desktop `1024×768`, and desktop `1440×900`.
- Added journey Outcome Proof with one to three user-visible, independent, request, persistence, recovery, or runtime signals; a successful click no longer proves task success.
- Added Business Context v2 provenance and stable context identity.
- Added Acceptance Finding v2 normalization, semantic fingerprints, evidence qualification, four user labels, deduplication, and Top 3 ranking.
- Added explicit product coverage and claim boundaries; discovered source is never reported as executed.
- Added compact smart-acceptance JSON/HTML reports and explicit `NOT_VERIFIED`, `NOT_EXECUTED`, and `NOT_APPLICABLE` states.
- Added local-only `source-check` as a P0-B-S foundation: explicit change scope, dirty-workspace conflict detection, deterministic parsing, npm script expansion, and command safety planning. It never writes source or sends it externally.
- Retained 3.7.5 specialist commands and Safe Edit compatibility. See `IMPLEMENTATION_STATUS_V2.3.md` for phase boundaries.

## 3.7.5 — Screenshot-First UI Quality release

- Added `quick-ui`, the new default UI path: capture one real page at mobile `390×844` and desktop `1440×900`, then write two screenshots, a compact JSON report, and an HTML review.
- Reordered the Skill workflow around human screenshot review, visible geometry, focused DOM/CSS/JS root-cause inspection, one implementation direction, and same-condition screenshot verification.
- Added conservative rendered checks for 44px standalone targets, oversized control-to-label proportions, inconsistent same-group control heights, icon/text imbalance, and excessive primary actions.
- Promoted fixed/sticky occlusion, major element overlap, offscreen/oversized dialogs, navigation overflow, and alignment drift into a ranked UI-first Top 3.
- Fixed whitespace normalization in `aria-labelledby` and accessible-name collection.
- Kept semantic Browser locators strict by default, added `testId` support to the Node runner, and stopped silently selecting the first ambiguous match.
- Unified narrow viewport execution around a touch-enabled mobile Browser context and the 44px control target contract.
- Changed non-2xx page navigation from a warning to `FAIL`, fixed journey warning initialization, and executed Python critical journeys at every configured viewport.
- Kept Smart Product Discovery, three-candidate redesign, security, deep accessibility, Lighthouse, framework probes, governance, and outcome measurement as explicit advanced capabilities.

## 3.7.4 — User-Controlled Upgrade release

- Changed the default `upgrade` route to **understand → current-conversation confirmation → read-only diagnosis → stop**. No design candidate, Browser run, security scan, or source write starts automatically.
- Added a hard confirmation ledger: high-impact unknowns are never accepted through a blanket “continue”, a model inference, a fixture, an Agent summary, or a downloaded response file. The host now binds a non-serializable `TrustedWorkflowApproval` to the exact answer packet and requested mode; diagnosis approval is separate from implementation approval.
- Added ten explicit evidence classes, including `UNKNOWN`, `CONFLICTED`, `NOT_VERIFIED`, `PACKAGE_VERIFIED`, `RUNTIME_OBSERVED`, and `SYNTHETIC_HYPOTHESIS`, with claim boundaries that prevent simulated feedback or inferred permissions from being presented as facts.
- Added one canonical bounded scan and a fingerprinted cache. Unchanged resumes reuse the scan; changed source invalidates it, preventing duplicate model/plugin reconstruction and unnecessary Token usage.
- Added a report-only process-local canonical cache shared by plugin/skill adapters in one host process; it never stores authority or source text, and all answer rounds still pass through the confirmation ledger.
- Made deferred answer rounds terminal: `continue-round` and `edit-one` can update the cached understanding ledger but cannot implicitly open diagnosis, design, Browser validation, or implementation, even when the caller requested full mode.
- Added model capability profiles with baseline fallback. GPT-5.3/5.4/5.5 and future or unknown model labels share the same approval and write invariants; higher capability may accelerate optional work but cannot bypass gates.
- Made security findings, deep accessibility, Browser validation, framework probes, and outcome measurement explicit opt-in capabilities. The default consultation remains lightweight and product-focused.
- Preserved isolated full-upgrade work: three materially different candidates, Browser/non-Browser honesty, decision export, rollback evidence, and byte-for-byte source immutability remain available only after an explicit full request.

- Added Smart Product Discovery before diagnosis and design: bounded source, page, and screenshot understanding now reconstructs the product job, application roles, objects, states, routes, protected meaning, and critical journeys without writing the target project.
- Added explicit `SOURCE_CONFIRMED`, `PAGE_OBSERVED`, `AI_INFERRED`, and `USER_CONFIRMED` evidence classes, a maximum-three high-impact question policy, and the three-action understanding workbench.
- Added internal execution-brief and safe test-plan artifacts, a resumable confirmation gate, and a compact system-understanding handoff in the design gallery.
- Added public and distribution acceptance coverage for sensitive-file exclusion, source immutability, discovery export, the pause-before-design default flow, and confirmation resumption.

- Rebuilt the gallery as a three-column design decision workbench for ordinary reviewers, designers, and executives.
- Added synchronized Before / After and desktop / tablet / mobile comparison, plus click-to-zoom visual review.
- Added plain-language fit, major change, trade-off, design rationale, organizational cost, and evidence-boundary views.
- Added a persistent decision dock for candidate choice, density and brand preferences, review notes, portable decision JSON, and a natural-language Codex handoff.
- Added a shareable one-page executive decision brief and replaced the technical-first release page with recommendation, alternatives, risks, and one explicit decision.
- Made the default `upgrade` response lead with the gallery, non-technical steps, and the next action while retaining machine-readable gates.
- Preserved a complete screenshot-free experience when Browser is unavailable; no empty image nodes or broken evidence are rendered.
- Added public acceptance coverage for the complete human-decision surface.

### Retained product-grounding foundations

- Added a bounded project semantic map that derives selectors, roles, components, and design-token aliases from the actual source.
- Moved Project Design IR, Design System Map, and evidence-ranked design concepts into the main upgrade path.
- Compiled each candidate against project-grounded selectors while retaining structural fallbacks for incomplete markup.
- Added Next.js Pages Router ownership and directive-safe imports alongside App Router, React, and Vue mapping.
- Fixed product-type precedence so source-detected landing pages are not overwritten by a generic consultation intent.
- Upgraded the gallery into a decision workbench with direction selection, review notes, density and brand strategy, and portable decision export.
- Added `finalize-design` to promote the chosen isolated candidate and rebuild its patch, manifests, and decision receipt.
- Replaced missing-Browser broken screenshots with a complete degradable review and precise environment repair guidance.
- Unified `doctor` and production validation around the same Node Playwright and Chromium capability check.
- Expanded critical-journey and keyboard-focus validation across desktop, tablet, and mobile viewports.
- Added a public acceptance suite that ships in the commercial archive and covers generic class names, product classification, Next.js Pages Router, Browser fallback, and decision finalization.
