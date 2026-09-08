> Package: **4.3.0** · Package Stage: **Commercial Stable** · Trust Kernel: **4.2.3** · Kernel Base Lineage: **4.0.0-rc.1** · Receipt Protocol: **3.0** · Evidence Schema: **3.0**

# Agent Benchmark Protocol — Web UI Quality 4.3.0 (Trust Kernel 4.2.3; frozen Protocol v4 lineage)

The package identity is 4.3.0; this document records the frozen protocol lineage carried by Trust Kernel 4.2.3.


The frozen Protocol v4 lineage originated in Beta.7, which converged the Architecture Consolidation runtime with the Benchmark Validity line. The benchmark is designed to qualify **measurement mechanics first**. It does not invent Claude/Codex repair scores.

## Trust layout

Preparation creates three independent filesystem roots:

```text
Host workspace root/      <- only this root should be opened in Codex/Claude
Controller root/          <- authenticated plan, immutable results, report, HMAC key
Evaluator private root/   <- sealed ground truth and behavioral oracles
```

The evaluator path, expected root sources, allowed repair scope, clean content, and oracle definitions are excluded from the Host-visible task. Roots cannot be ancestor/descendant of one another.

This is **workspace/path isolation**, not remote attestation. A same-user Agent with unrestricted OS-wide filesystem access can still require an external container, sandbox, or ACL boundary.

## Protocol v4 authenticity

Protocol v4 retains public SHA-256 digests for reproducible content identity and adds a Controller-private HMAC-SHA256 layer:

- `benchmark-plan.json`: `planDigest` + `planMac`
- `benchmark-controller-state.json`: `stateDigest` + `stateMac`
- evaluator manifests: public `manifestDigest`; Controller state stores a private HMAC for every manifest
- Controller integrity key: owner-only file outside Host workspaces

Recomputing a public digest after tampering is therefore insufficient to restore Controller authenticity. This HMAC boundary assumes the Host cannot read the Controller key; unrestricted same-user filesystem access still requires OS-level isolation.

## Controller-planned conditions

Before a run, the Controller binds:

- Host name/version/model
- reasoning mode
- permission profile
- tool policy
- browser/auth condition
- OS/runtime
- context policy
- WUQ version
- fixture version

The Host result must exactly match the planned `conditionDigest`. Mixed fingerprints are reported separately rather than pooled as one comparable cohort.

## Immutable contained ingest

The Host cannot choose the result destination. Storage is derived from the sealed `runId`:

```text
<controller>/results/<runId>.json
```

Absolute paths, `..`, path escapes, and duplicate result writes are rejected.

## Three oracle levels

### Level 1 — Source Contract

`FILE_EQUALS` / `FILE_CONTAINS` verify deterministic source invariants. They are useful for narrow contracts but do **not** prove rendered behavior.

### Level 2 — Executable Behavior

`NODE_SCRIPT` executes a deterministic fixture behavior contract. Protocol v4 applies bounded CPU/file/process resources and an isolated HOME/TMP directory. The result explicitly reports:

```text
PROCESS_LIMITED_NOT_OS_ISOLATED
```

No network namespace or filesystem namespace isolation is claimed. Hostile same-user Agent code requires an external sandbox/container.

### Level 3 — Browser Behavior

`BROWSER_ASSERT` uses Playwright/Chromium to evaluate actual fixture behavior. Supported assertions include:

- element visibility
- within-viewport containment
- minimum touch-target size
- top-layer hit testing with `elementFromPoint`
- page horizontal overflow
- text containment
- computed CSS containment

Fixture HTML is evaluator-controlled; styles under test are loaded from the Host workspace. HTTP/HTTPS requests are aborted during evaluation. If Browser capability is unavailable, the oracle returns an explicit unmeasured environment state rather than silently downgrading to source matching.

## Corpora

### Development corpus

The V2 development corpus contains **40 distinct archetypes** across 12 fault families. Context retrieval metrics are measured across every applicable repair case, not a first-N sample.

The development corpus is allowed to evolve with the system and therefore must not be treated as an independent proof of external validity.

### Frozen holdout-v1

The frozen validation lineage includes **8 obfuscated-root holdout cases** with semantic decoys and a mix of Browser, executable, source-contract, and no-mutation oracles.

Important boundary:

- the holdout is excluded from recall tuning/release thresholds;
- retrieval is reported diagnostically;
- the holdout is hidden from prepared Host workspaces;
- it is shipped with the package, so it is **not secret from maintainers** and is not a true private external benchmark.

A future externally administered hidden corpus is still required for stronger generalization claims.

## Metrics

Root Cause uses set-based micro precision/recall:

- Precision = TP / (TP + FP)
- Recall = TP / (TP + FN)

No-op runs have `scopePrecision = null` and are excluded from mean scope precision. Regression Escape reports distinct denominators for VERIFIED claims, attempted repairs, and successful repairs.

Context retrieval reports Recall@K, Precision@K, selected source bytes, and an estimated source-token budget. These numbers are corpus-specific and must not be advertised as real-repository Token savings without independent measurement.

## Fake-Agent attack qualification

`benchmark_attack_suite.py` distinguishes strategy diversity from probe volume:

- at least 12 adversarial strategy families
- 1200 deterministic stability probes

The suite tests plan/ground-truth tampering, condition spoofing, result replay, path escape, no-op gaming, wrong-root spray, scope spray, false VERIFIED, protected-scope mutation, and oracle-targeted attacks.

Synthetic attack resistance qualifies benchmark infrastructure only; it does not measure model quality.

## Desktop qualification

`desktop_qualification_pack.py` produces Controller-bound queues for real Desktop Host runs. Scores remain `NOT_MEASURED` until a human or external runner actually executes the tasks in the named Host and ingests the results.

## Claim boundary

The package may claim that it contains authenticated benchmark controller mechanics, deterministic development/holdout fixtures, multi-level oracles, and adversarial qualification. It may **not** claim that Claude, Codex, Cursor, or another Host achieves a specific repair accuracy, hallucination reduction, Token saving, or regression reduction until those Hosts are actually measured under controlled comparable conditions.
