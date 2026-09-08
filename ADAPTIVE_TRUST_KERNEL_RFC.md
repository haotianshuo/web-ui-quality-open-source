> Package: **4.3.0** · Package Stage: **Commercial Stable** · Trust Kernel: **4.2.3** · Kernel Base Lineage: **4.0.0-rc.1** · Receipt Protocol: **3.0** · Evidence Schema: **3.0**

# Web UI Quality 4.3.0 — Adaptive Trust Kernel RFC (Trust Kernel 4.2.3)

**Status:** `NOT_ACTIVE_IN_STABLE`  
**Authority effect:** `NO_AUTHORITY_EFFECT`  
**Claim effect:** `NO_CLAIM_EFFECT`

This document is a non-authoritative design proposal. It cannot change write authority, verification thresholds, or the default Stable execution path without controlled real-host evidence and a later explicit release decision.

## Principle

**模型负责聪明，Web UI Quality 负责可信。**

The Host model owns reasoning, diagnosis, design and implementation choices. Web UI Quality owns the trust boundary around real-world project changes.

## Hard Gates

No future mode may skip:

- Protected Scope;
- Write Authority separated from Host execution;
- V3 Host Receipt;
- exact Before/After file hashes;
- Unexpected Drift detection;
- Project Tool Gate when required;
- Required Verification;
- Claim Boundary;
- No Evidence, No PASS.

Model capability must never weaken these gates.

## Soft Guidance

The following may become adaptive after real controlled evidence exists:

- scan depth;
- relevant-context count;
- finding count, with a maximum of 3 and no quota-filling;
- whether multiple design directions are useful;
- explanation length;
- whether whole-site inventory is necessary;
- non-authoritative heuristic ranking.

## Proposed modes

### LITE

Characteristics: narrow, low-risk, local UI adjustment with a small known target. LITE may reduce discovery and explanation, but still requires the same applicable authority, receipt, drift, verification and claim gates.

### STANDARD

Characteristics: normal component/page repair, responsive issues, shared-component fixes, targeted Browser coverage and project-tool checks where applicable.

### STRICT

Characteristics: authenticated/high-risk SaaS, broad redesign, permission/order/payment/admin flows, wider change budgets or changes with greater regression impact. STRICT increases evidence and verification coverage; it does not create new Runtime intelligence authority.

## Read Scope vs Write Scope

`Read Scope Expansion` and `Write Scope Expansion` are permanently separate decisions. A Host model may request more source context to find the root cause without receiving authority to modify those files. Any write-scope expansion requires a new bound authority decision and must be reflected in subsequent receipt and verification bindings.

## Delta Context

Future context delivery should send stable trust facts once, then send changes/deltas where safe. Protected Scope, current authority, claim boundary and required verification must remain available even when contextual guidance is compressed.

## Evidence Digest

Evidence objects remain machine-verifiable source records. A model-facing Evidence Digest may summarize those records for context efficiency, but a digest is never a replacement for the underlying evidence and cannot upgrade its trust class.

## Evidence required before activation

No adaptive mode becomes authoritative without controlled A/B evidence using the same repositories, tasks, models, reasoning settings and permissions. Required metrics include Trusted Task Completion Rate, False VERIFIED Rate, scope violations, regression escape, closed-loop entry, first-pass success, human interventions, abandonment, resume success, wall time and trusted-completion cost/Token use. Evidence must identify its type according to `PRODUCT_MEASUREMENT_SPEC.md`.

## Compatibility and rollback

- Existing Fixed Workflow remains the safe fallback.
- Any adaptive decision must be reversible to the fixed baseline without changing persisted authority semantics.
- Persisted runs must record the policy/version that produced guidance.
- A future adaptive release must preserve V3 receipt verification and existing claim-boundary behavior.
- Rollback occurs if False VERIFIED, protected-scope violations, verification gaps, task abandonment, or unexplained closed-loop failures regress beyond predeclared thresholds.

## Failure conditions

Activation is prohibited when evidence is synthetic-only, when Host/Browser capabilities are not measurable, when a mode needs to relax a Hard Gate to improve completion rate, or when the adaptive path cannot be independently distinguished from authority-bearing state.
