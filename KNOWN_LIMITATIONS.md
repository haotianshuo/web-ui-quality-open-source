> Package: **4.3.0** · Package Stage: **Commercial Stable** · Trust Kernel: **4.2.3** · Kernel Base Lineage: **4.0.0-rc.1** · Receipt Protocol: **3.0** · Evidence Schema: **3.0**

## Trust Kernel 4.2.3 Release Integrity + Trust UX boundary

The package identity is 4.3.0; this section describes the 4.2.3 Trust Kernel.


- 4.2.3 intentionally does not promote v5 ranking or new adaptive repair intelligence; its scope is trust, browser security, release integrity and user experience.
- Fixed Workflow remains authoritative. Production shadow observations and qualification tooling are non-authoritative and cannot change writes, Claim state, TaskResult, or user-visible success/failure.
- Real-world predictive validity remains `NOT_MEASURED` until independently labelled, Host-attested production-shadow evidence is collected.
- Real Codex Host pre-write enforcement remains `NOT_MEASURED`; package-local simulated-Host tests do not substitute for a real Host capability attestation.
- Adaptive Guidance and Adaptive Exploration remain `NOT_ACTIVE` in 4.2.3.
- Browser evidence redaction is best-effort. Known secret patterns and known/annotated sensitive DOM fields are redacted/masked, but arbitrary visual PII in screenshots/canvas/video or unannotated page text is not universally recognized.
- `outerIsolationAttestation`-style Host evidence is a Host assertion unless an external OS/container verifier supplies independent proof; Runtime does not convert an attestation into remote-attestation evidence.
- Exact request authorization may require explicit policy entries for GraphQL POST reads, WebSocket endpoints, dangerous GET routes, authenticated XHR/fetch GET reads, and authenticated document navigation. Query-bearing approvals/navigation routes bind a normalized query digest rather than raw values. This conservative default can make some authenticated/realtime applications `NOT_VERIFIED` until the Host/user supplies a bounded authorization; WUQ does not claim to prove that every possible GET endpoint is semantically read-only.

## Historical release-candidate boundary

- 4.1.0-rc.1 is feature-frozen. Subsequent changes are restricted to qualification evidence, release blockers, and RC hardening.
- Fixed Workflow remains authoritative. Production shadow observations and qualification tooling are non-authoritative and cannot change writes, Claim state, TaskResult, or user-visible success/failure.
- Real-world predictive validity remains `NOT_MEASURED` until independently labelled, Host-attested production-shadow evidence is collected.
- Real Codex Host pre-write enforcement remains `NOT_MEASURED`; package-local simulated-Host tests do not substitute for a real Host capability attestation.
- Adaptive Guidance and Adaptive Exploration remain `NOT_ACTIVE` in RC.1.

## 4.1.0-alpha.7 final-Alpha boundary

- The collection pack prepares privacy-reduced research artifacts; it does not itself obtain real Host attestation or independent labels.
- HMAC pseudonymization reduces direct identifier leakage but is not anonymization against a party that possesses the caller key or auxiliary re-identification data. Keep the key outside the project and outside the exported pack.
- The export uses an allowlist of current shadow fields. Future shadow schema fields are not exported until explicitly reviewed.
- Real-world predictive validity and real Codex Host enforcement remain `NOT_MEASURED`. Adaptive Guidance/Exploration remain inactive.
- alpha.7 is feature-frozen; later 4.1 changes are restricted to qualification evidence, release blockers, and RC hardening.

## 4.1.0-alpha.6 qualification boundary

- The package ships a qualification **harness**, not collected real-world qualification evidence. `realWorldPredictiveValidity` remains `NOT_MEASURED`.
- `PRODUCTION_SHADOW` rows count toward the real-world pre-gate only when provenance is `HOST_ATTESTED` and the outcome label is independently sourced. This package does not fabricate that Host attestation.
- `CONTROLLED_BENCHMARK` can exercise independent-oracle qualification logic but cannot substitute for production-shadow evidence. `SYNTHETIC_FIXTURE` is test-only.
- A `READY_FOR_PHASE3_5_PREREGISTRATION` result is not a capability score and does not activate Profile, Clamp, Guidance, Exploration, Write Authority, or Claim Authority.
- HOLDOUT analysis remains opt-in and must not be used for development tuning.

## 4.1.0-alpha.5 experimental boundary

- Production `run` emits non-authoritative capability-shadow observations; the alpha.5 dataset builder and validity analyzer are offline research tools, not runtime controllers.
- Only explicitly independent `EXTERNAL_ORACLE`, `HOST_ACCEPTANCE`, or `HUMAN_BLIND_REVIEW` labels are eligible for development validity analysis. `FIXED_WORKFLOW_PROXY` and `SYNTHETIC_FIXTURE` labels cannot establish predictive validity.
- HOLDOUT labels are excluded by default and require explicit opt-in analysis.
- Development-only precision/recall/FPR metrics are pre-gate research evidence; they do not authorize a Profile/Clamp transition.
- No model capability score is produced. Semantic signals do not participate in runtime decisions.
- Profile/Clamp recommendations remain `NOT_EVALUATED_UNTIL_SIGNAL_VALIDITY_GATE`.
- Adaptive Guidance and Adaptive Exploration remain `NOT_ACTIVE`.
- Real-world signal predictive validity and real Codex Host enforcement remain `NOT_MEASURED`.


## 4.1.0-alpha.3 experimental boundary

- The 4.1 package is a **Phase1 Minimal Trust Contract Slice**, not proof that Codex Desktop/CLI enforces Phase1 write tickets. Real Codex Host enforcement remains `NOT_MEASURED`.
- Fixed Workflow remains authoritative. Phase1 contracts are not yet wired as a production shadow path beside `run`.
- The Phase1 minimal read boundary intentionally omits byte/file/class/network budget controls that are not yet enforced. The target architecture may add them in later phases.
- Phase1 EDIT rejects symlink/junction/reparse aliases and multi-link files conservatively. This may reject a legitimate repository layout rather than risk alias-based write escape.
- State-epoch freshness is authoritative only when the Host/controller supplies the correct current mutation epoch; a real Codex Host epoch source is not yet qualified.

## Historical kernel-base compatibility limitations

- Browser-backed proof requires the Python Playwright driver and a usable Chrome/Edge/Chromium executable. `--browser-executable` does not bypass Playwright.
- Host policy may block localhost or external navigation. Such cases remain `NOT_VERIFIED_ENVIRONMENT`.
- JavaScript/TypeScript/JSX/TSX/Vue/Svelte do not receive built-in syntax PASS from the Python parser layer. Host-approved project tools remain conditional evidence.
- Runtime does not execute project-owned tools or write project files autonomously.
- Large repositories may have globally partial baselines. Exact repair scope and critical context can be complete, but the current bounded-baseline contract never upgrades unindexed repository state to whole-project MATCH.
- Patch Quality detects bounded regression signals; `QUALITY_OK` is not proof of universal maintainability or architecture quality.
- Systemic-root-cause detection depends on source mapping and is conservative when ownership is uncertain.
- Authentication profiles reference user-owned storage-state files; Web UI Quality does not refresh expired login sessions.
- Resume restores workflow state only and keeps `writeAuthorization=false`.
- Local HMAC integrity is tamper-evident but not remote attestation or portable independent signing.
- TaskResult v1 retains legacy repair-machine compatibility aliases during migration; new integrations should use the current TaskResult fields.
- Relevant Context Packet v1 ranks file references deterministically and can miss a true root-cause file. Root-Source Recall is therefore measured separately instead of treating packet selection as truth.
- The included 40-archetype deterministic repair development corpus and 1200-run Fake-Agent attack suite are **benchmark-infrastructure qualification**, not an AI-repair accuracy benchmark. `agentLoopStatus` remains the legacy-compatible `NOT_VERIFIED_HOST_AGENT`; the new qualification report uses `NOT_VERIFIED_HOST_AUTOMATION` until an external Host Agent writes benchmark results. The protocol can aggregate pass@1/pass@k, False VERIFIED, cost and variance once those runs exist, but this package does not fabricate them.
- The static network-egress gate proves the checked Runtime import/command policy, not the external Host AI provider's data handling. Figma input and local report serving remain explicit network-capable exceptions.
- Repair-scope revert plans contain hashes/identity only. Host/Git/IDE must have a way to restore the recorded Before content; the plan is not a repository snapshot.
- Design candidates can be 1–3; candidate direction-contract differences still do not prove rendered structural differences.
- General backend/database/infrastructure repair, cloud Browser farms, autonomous deployment, penetration testing and remote attestation remain outside the 4.2.3 product claim.
- Risk Tier is a conservative static policy classification. It can over- or under-classify unusual project conventions; source paths and explicit user protection clauses are considered, but the tier is not a security audit.
- Change Budget currently enforces file/scope/config/dependency boundaries deterministically. Changed-line enforcement remains `NOT_MEASURED` unless the Host supplies trustworthy line statistics; file/hash/drift gates remain authoritative.
- Evidence Dependency Graph is derived metadata, not remote attestation. Graph completeness does not make an untrusted underlying artifact trustworthy.
- `VERIFY_ONLY` and `EXPLAIN` are public intent distinctions that route through the read-only inspection execution path; they do not create a second verification runtime or infer historical edits without a sealed prior run.
## Beta.7 benchmark validity boundaries

- The 40-case development corpus and 8-case frozen holdout are synthetic fixtures; neither proves performance on a large real legacy repository.
- The holdout is frozen and excluded from tuning gates, but it ships with the package and is not secret from maintainers.
- `NODE_SCRIPT` uses process/resource limits and isolated HOME/TMP only. It is **not** an OS/container sandbox and cannot safely contain a malicious same-user process by itself.
- `BROWSER_ASSERT` blocks HTTP/HTTPS during fixture evaluation, but it is a local deterministic Browser oracle, not a production-environment security boundary.
- Context Recall/Precision and estimated source-token values are corpus-specific diagnostics, not evidence of real-world Token savings.
- External Host/model repair accuracy remains NOT_MEASURED until real runs are ingested under Controller-planned comparable conditions.
