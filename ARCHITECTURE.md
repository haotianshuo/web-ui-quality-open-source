> Package: **4.3.0** · Package Stage: **Commercial Stable** · Trust Kernel: **4.2.3** · Kernel Base Lineage: **4.0.0-rc.1** · Receipt Protocol: **3.0** · Evidence Schema: **3.0**

# Architecture — Web UI Quality 4.3.0 (Trust Kernel 4.2.3)

The package identity is 4.3.0; the Trust Kernel identity is 4.2.3.


4.2.3 is the current Trust/Repair Kernel identity carried by package 4.3.0. It preserves the historical 4.0.0-rc.1 kernel lineage as `kernelBaseVersion` only, while current claim, receipt, browser-security and release contracts are versioned independently. It does **not** add an autonomous second LLM runtime; the Host model remains the reasoning engine.

## Current authoritative mainline

There is one success-claim path for new write-backed repairs:

```text
run
→ run_experience_fix
→ Task Goal + Protected Scope + Baseline
→ Patch Candidate
→ immutable V3 Host Apply Binding
→ external Host write
→ V3 Host Write Receipt
→ Project Tool / Browser / Drift / Patch Quality verification
→ TaskResult
→ Human / Machine / Expert rendering
```

Historical report fields and receipt shapes may remain parseable for migration and diagnosis, but they do not create a parallel authority path. In particular, compatibility aliases such as `repairStatus`, `repairReport`, legacy receipts, historical unified reports, and kernel-base version fields cannot upgrade a current claim to `VERIFIED`.

| Compatibility field/surface | Why it still exists | Current authority |
|---|---|---|
| `repairStatus`, `repairReport` | Older consumers | Alias/read compatibility only |
| Legacy Host receipt | Migration and failure diagnosis | Cannot support a new 4.2.3 `VERIFIED` claim |
| Historical `unified-report` | Older output integrations | Not a second TaskResult authority |
| `kernelBaseVersion=4.0.0-rc.1` | Provenance | No current write/claim authority |
| Historical commands | CLI compatibility | Parseable; `run` is the recommended facade |

## Deployment boundary

```text
User request
   │
Host AI reasoning
   │  proposes hypotheses / changes
   ▼
Task Control + Relevant Context Packet
   │
Project Intelligence ── Evidence Runtime
   │                      │
   └──────────┬───────────┘
              ▼
          Diagnosis
              ▼
       Repair Planning
              ▼
════════ Deterministic Trust Kernel ════════
Scope / Evidence Authority / Integrity
Host Write Boundary / Project Tool Boundary
Drift / Coverage / Checkpoint / Claim Boundary
════════════════════════════════════════════
              ▼
         Verification
              ▼
          TaskResult v1
```


## Consolidated layer contract

The dependency order is intentional and one-way:

1. **UX / Intent** may decide how to understand and present the task.
2. **Governance** may require confirmation or classify evidence.
3. **Trust / Repair Kernel** decides what mutation/tool evidence is admissible.
4. **Verification** decides whether a success claim is allowed.

An upper layer can never replace a lower-layer `NOT_VERIFIED`, `BLOCKED`, failed receipt, unexpected drift, incomplete coverage, or failed Change Budget with a user-friendly PASS.

`Risk Tier` is deterministic policy metadata (`T0` cosmetic → `T4` auth/payment/permission/data). `Change Budget` bounds file and line intent, new files, dependencies and config. Both remain non-authorizing.

`Evidence Dependency Graph` is a derived audit graph over trusted artifacts; its completeness is inspectable, but the underlying Trust Kernel gates remain the authority for `VERIFIED`.

## Existing bounded contexts remain

- **Control** — intent, Task Goal, protected scope, assumptions, decisions, checkpoints/resume.
- **Project Intelligence** — framework/toolchain discovery, UI Inventory, design-system mapping, source ownership, Sealed Project Baseline.
- **Evidence Runtime** — Browser/DOM/network/screenshot/journey/PageHealth observations.
- **Diagnosis** — finding ranking, source mapping and local/systemic-root-cause candidates.
- **Repair** — Patch Candidate, scope expansion, mutation risk, Host bridge/receipts.
- **Verification** — source assurance, project-tool evidence, patch quality, drift, Before/After and final decision.
- **Adapters** — Playwright, project-local tools, axe/Lighthouse, Figma, CI/reporting.

The physical module layout remains intentionally incremental. Dependency direction, a single authoritative trust path, and compatibility are more important than a cosmetic big-bang package move.

## TaskResult convergence

`TaskResult v1` is the public convergence layer, not a new execution subsystem. Existing mode-specific results adapt into one contract:

```text
legacy Repair/Audit/Check result
        │
        ▼
     TaskResult v1
      ├ Human renderer
      ├ --json
      └ --ci
```

`coverage` is required. For a verified repair, Patch/Target/Critical Context coverage must be complete; global project coverage may remain partial and must remain visible.

## Relevant Context Packet v1

The packet is deterministic and carries no authority. It combines mandatory safety context with ranked source references. Mandatory context includes Goal, Protected Scope, Host-only write/tool authority and Claim Boundary. Source selection is budgeted independently.

This creates a measurable failure boundary:

- root source absent from packet → retrieval/context failure;
- root source present but ignored → model reasoning failure;
- correct diagnosis but wrong patch → repair-generation failure;
- correct patch but wrong success claim → verification failure.

## Sealed Project Baseline and coverage

The project baseline remains in the sealed `before/` phase. Large repositories may be globally partial. Exact target files and target-adjacent critical toolchain/config context are independently indexed so patch-scope assurance can be complete without claiming whole-repository completeness.

## Host execution boundaries

Runtime still cannot self-authorize writes or execute project-owned tools. Host Write Receipt and Host Project Tool Result remain exact, hash-bound, run/task/session-bound contracts. Unexpected tool writes or repository drift block `VERIFIED`.

## Repair-scope revert

The frozen kernel can derive a tamper-evident revert plan only from a process-trusted Host Write Receipt. The plan records the repair files plus expected current and target Before hashes. It carries no bytes and no authority; Host/Git/IDE must restore content. Its claim boundary is the exact repair scope, never the whole repository.

## Product evidence architecture

Measurement is split by cost:

1. **Deterministic Trust Suite** — receipts, replay, drift, scope, checkpoint, schemas.
2. **Context/Recall Benchmark** — Root-Source Recall@K, Protected-Scope preservation, selection budget; no model required.
3. **Agent-in-the-loop Benchmark** — external Host Agent + model + WUQ; records model/host version, pass@1/pass@k, cost, variance and False VERIFIED when actually executed.

The frozen benchmark lineage qualifies a 40-archetype deterministic repair development corpus, three-root benchmark path separation, sealed plan/ground-truth state, immutable contained ingest, corrected Precision/Recall/Scope/Regression metrics, behavioral oracles and a 1200-run Fake-Agent attack suite. These qualify the benchmark machinery only; Claude/Codex accuracy remains NOT_MEASURED until real Desktop Host results are ingested.

## Privacy / network egress

Core Runtime imports are checked against an explicit network-capability allowlist. External-network adapters such as Figma input and local networking infrastructure such as the report server are explicit exceptions. Host-model data handling is outside the deterministic Runtime boundary and follows the Host deployment policy.

## Design candidates

Design candidate generation now accepts 1–3 requested directions. The default remains three for compatibility. Direction-contract difference remains a declared-contract gate and does not become rendered structural proof.
