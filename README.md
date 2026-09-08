> Package: **4.3.0** · Package Stage: **Commercial Stable** · Trust Kernel: **4.2.3** · Kernel Base Lineage: **4.0.0-rc.1** · Receipt Protocol: **3.0** · Evidence Schema: **3.0**

# Web UI Quality 4.3.0

**Public source release (MIT) — Trust-Controlled Web Change Runtime**

This repository is a clean public source snapshot. It contains the project
runtime, examples, tests, and Codex plugin manifest. Private archives, chat
records, browser storage, external worktrees, and internal evolution evidence
are intentionally outside this repository. See [PUBLICATION.md](PUBLICATION.md)
for the boundary and provenance record.

## Install and try it

From a local checkout:

```bash
python -m pip install -e .
web-ui-quality doctor
```

Run the self-contained public checks with:

```bash
python -B -m pytest -q
```

## Contact

For project questions, provenance corrections, or contribution coordination,
contact `xrlcom@126.com`. Do not send passwords, API keys, cookies, storage
state, private customer data, or other secrets by email. Security reports
should follow [SECURITY.md](SECURITY.md).

## 4.3.0 Commercial Stable status

4.3.0 preserves the 4.2.3 Trust Kernel and V3 receipt/evidence authority while adding a bounded, non-authoritative intelligence extension: Task Fingerprint/Graph observations, execution budgets, design intent routing, candidate arena binding, evidence-qualified design gates, and memory-authority decisions. These additions cannot write project files or promote VERIFIED claims by themselves.


4.2.3 keeps the established repair reasoning model and does **not** promote v5 ranking, Adaptive Guidance, or Adaptive Exploration. This release closes the native-Windows junction qualification fixture, authenticated Browser navigation Query binding, synthetic-browser harness isolation, and Trust failure-state UX without creating a second Agent brain.

**Product definition:** 让 AI 修改 Web 项目时不越界、可验证、可追溯。

The Host model is responsible for reasoning and implementation quality. Web UI Quality is the trust control layer responsible for scope, authority, evidence, drift, verification, and claim boundaries. It is not a second brain that competes with a stronger Host model.

Claim boundaries remain strict: package-local release tests do not become real Codex Host evidence. Native-Windows qualification is maintained as external evidence bound to the exact release artifact SHA-256 and is not self-promoted by package metadata. Real Codex Host qualification remains `NOT_MEASURED / EXTERNAL_QUALIFICATION_INTERFACE_UNAVAILABLE` until the Host exposes a real qualification interface. Real-browser capability is qualified only by the required Full Release Gate and its recorded Browser evidence.

### Current claim boundary

- `Fixed Workflow = AUTHORITATIVE`
- `Receipt Protocol = 3.0`
- `Legacy V2 Receipt = HISTORY/READ ONLY FOR 4.2 VERIFIED CLAIMS`
- `Adaptive Guidance = NOT_ACTIVE`
- `Adaptive Exploration = NOT_ACTIVE`
- `v5 Ranking = NOT_INCLUDED`
- `Native Windows Qualification = EXTERNAL_ARTIFACT_BOUND_EVIDENCE`
- `Real Codex Host Qualification = NOT_MEASURED`

### Release-manifest file counts

`RELEASE-MANIFEST.json.fileCount` counts the deterministic content tree **before** the two generated manifest files are appended to the archive. The physical ZIP therefore contains `fileCount + 2` files when both `RELEASE-MANIFEST.json` and `COMPOSITE-RELEASE-MANIFEST.json` are present. `verify_distribution.py` checks this relationship and the package-tree digest; the difference is intentional and is not a missing-file condition.

## Historical kernel-base closure model

This release keeps one consolidated runtime instead of maintaining parallel execution stacks:

```text
Natural-language request
        │
        ▼
Intent Router
Diagnose / Repair / Verify-only / Explain / Transform / Specialized Audit
        │
        ▼
Real-page UX layer
Real page / PageHealth / safe task / Before-After
        │
        ▼
Governance layer
Current-session approval / evidence classes / bounded discovery cache
        │
        ▼
4.0 Trust / Repair Kernel
Baseline / Protected Scope / Host Receipt / Tool Gate / Drift / Coverage
        │
        ├──── Transformation branch: Product Understanding / 1–3 Design Directions / Decision Workbench
        │
        ▼
Risk Tier + Change Budget + Evidence Dependency Graph
        │
        ▼
TaskResult
```

No duplicate legacy runtime is embedded. The 4.0 Trust / Repair Kernel and tamper-evident ExperienceRun remain authoritative for success claims and evidence integrity.

### Risk Tier and Change Budget

Focused repair now produces a deterministic `T0`–`T4` mutation risk tier and a bounded Change Budget. The budget limits file-count expansion and blocks unapproved dependency/config/new-file changes. A budget PASS is only a scope-control result; it never grants write authority or proves correctness.

### Evidence Dependency Graph

Each consolidated run derives an Evidence Dependency Graph linking Task Goal, Project Baseline, Before evidence, patch scope, Host Write Receipt, After evidence, project tools, Patch Quality, Drift, comparison, and final verification. The graph makes claim dependencies inspectable but cannot upgrade weak evidence into `VERIFIED`.

## Benchmark validity boundary

The benchmark subsystem remains part of the same runtime contract as Risk Tier, Change Budget, Evidence Graph, Intent Router, and the 4.0 Trust/Repair Kernel. Benchmark Protocol v4 adds Controller-private HMAC authentication, the 40-archetype development corpus, a frozen 8-case obfuscated-root holdout, and three oracle levels: source contract, executable behavior, and Playwright browser behavior.

The holdout is **diagnostic, not a tuned release gate**. It is hidden from prepared Host workspaces but shipped with the package, so it is not represented as a secret external benchmark. Executable oracles report `PROCESS_LIMITED_NOT_OS_ISOLATED`; hostile same-user Agent execution still requires an external container/ACL/OS sandbox.

Real Host/model repair accuracy, Token savings, and false-VERIFIED reduction remain `NOT_MEASURED` until real comparable Host runs are ingested.

## Product boundary

The deployment model is deliberately simple:

```text
Host AI model
  understands / reasons / proposes
        │
        ▼
Web UI Quality
  context + scope + evidence + trust + verification
        │
        ▼
Host
  writes files / runs project tools / grants authority
```

The Python Runtime does not contain a second autonomous LLM brain. It does not turn a persona or a model recommendation into execution authority.


### 4.2.3 authoritative write path

For a write-backed repair, a new `VERIFIED` claim requires Receipt Protocol v3 on the public repair path:

```text
Patch Candidate
→ immutable V3 Host Apply Binding
→ external Host authorization/write
→ HMAC-attested V3 Host Write Receipt
→ After verification
→ TaskResult / UserOutcome
```

The HMAC key is supplied by the Host environment (`WUQ_HOST_RECEIPT_HMAC_KEY`) and is never generated, persisted, or promoted to authority by Runtime. Legacy receipts remain readable for historical/migration diagnostics but cannot support a new 4.2+ `VERIFIED` claim.

Exact Browser request exceptions are also Host/user-bound. Repeat `--approve-request ORIGIN,METHOD,PATH[?QUERY]` only for a required endpoint (use method `WEBSOCKET` for an exact WebSocket path); query values are normalized and stored only as a SHA-256 digest, never as raw approval evidence. Authenticated XHR/fetch GET requests are fail-closed unless explicitly approved, and no coarse “allow all POST/WS” switch is provided.

## Controlled repair loop

```text
Request
→ Task Goal / Protected Scope
→ Sealed Project Baseline
→ Browser / Source Evidence
→ Diagnosis / Patch Candidate
→ Host Write Boundary
→ Host Project-Tool Boundary
→ Unexpected Drift / Patch Quality
→ Before/After Outcome
→ Final Decision
→ TaskResult
```

A large repository may remain **globally partial** while the exact patch scope and target-adjacent critical toolchain/config context are complete. A bounded patch can therefore be verified without pretending the whole repository was fully scanned.

## TaskResult v1: one public result

The consolidated 4.0 line uses one versioned public `TaskResult` convergence layer for:

- `INSPECTION`
- `REPAIR`
- `MODERNIZATION`

Existing Repair/Audit result shapes remain compatibility surfaces and are adapted into TaskResult instead of creating another independent report family.

Every TaskResult includes `coverage`. A `VERIFIED` repair cannot omit its verification scope. For example:

```text
Repair status: VERIFIED
Patch scope: COMPLETE
Global project: PARTIAL
Target coverage: COMPLETE
Critical context: COMPLETE
```

`VERIFIED` therefore means **verified within the declared coverage**, not “the whole repository is proven clean.”

### Human / machine / expert surfaces

```bash
python -B scripts/run_runtime.py run . "先别改，只看看"               # Human Task Report
python -B scripts/run_runtime.py run . "修复订单页" --json             # TaskResult v1 JSON
python -B scripts/run_runtime.py run . "修复订单页" --expert-json      # full internal Runtime result
```

Inspection no longer falls back to “use --expert-json”; a no-mutation task still receives a normal Human Task Report.

Legacy `executionStatus`, `repairStatus` and `repairReport` fields remain compatibility aliases in the current TaskResult machine contract while new integrations migrate to `outcome`, `coverage`, `verification`, `claims` and `uncertainties`.

## Project tools are conditional evidence

Project-local `tsc`, `vue-tsc`, `eslint`, `vitest`, `jest`, and `stylelint` are project-owned code. Runtime never executes them autonomously. It emits an exact Host-gated plan bound to executable hash, argv, cwd, network policy, timeout, resource policy, filesystem policy and run/task/session identity.

- Tool `PASS` can continue verification only when the bound conditions are confirmed.
- Tool `FAIL` blocks repair success even if the screenshot looks better.
- Tool `NOT_VERIFIED` cannot become `VERIFIED`.
- Unexpected project writes fail the tool gate.
- Unexpected repository drift outside the Host write receipt blocks `VERIFIED`.

## Review and repair-scope revert

After a verified Host write, The frozen repair kernel can expose a tamper-evident **repair-scope revert plan**. It contains only the exact files and Before/After hashes from the verified repair. Runtime still does not write files. Git/IDE/Host must perform any restoration and obtain the original content.

This is intentionally **not** called “restore project”: with a globally partial baseline, Web UI Quality cannot prove the state of files outside the repair scope.

## Relevant Context Packet v1

The package also produces a deterministic context plan for the Host model. Mandatory safety context is never removed by the source-reference budget:

- Task Goal
- Protected Scope
- Host-only write authority
- Host-only project-tool authority
- Claim Boundary

Relevant source references are ranked separately. The packet is a context/retrieval plan, not a claim that the selected files contain the root cause.

## Product evidence: benchmark infrastructure, not marketing claims

The benchmark subsystem uses a **40-archetype deterministic repair development corpus** plus **12 adversarial strategy families / 1200 deterministic probes** to qualify benchmark mechanics. Host workspaces, controller state and evaluator-private ground truth use separate filesystem roots; benchmark plans and evaluator manifests are digest-sealed; result ingest is controller-contained and immutable.

The scorer now reports real set-based Root Cause Precision/Recall, excludes no-op runs from Scope Precision, separates Regression Escape denominators, and groups results by a Host/condition fingerprint. Behavioral oracles accept equivalent valid repairs instead of demanding one exact `cleanContent` string.

It deliberately reports:

```text
agentLoopStatus = NOT_VERIFIED_HOST_AGENT
qualification.agentLoopStatus = NOT_VERIFIED_HOST_AUTOMATION
Claude/Codex repair accuracy = NOT_MEASURED
```

because deterministic fixtures and fake agents qualify **the benchmark**, not the models. Use `scripts/desktop_qualification_pack.py` to generate a 72-run Codex Desktop / Claude Desktop queue when you want real model measurements.

## Privacy boundary

Core Runtime network imports are protected by a release gate. Explicit network-capable exceptions are documented adapters/infrastructure, currently including Figma input and the local report server.

Web UI Quality Runtime does not contain OpenAI/Anthropic model clients and does not itself decide how the Host AI provider handles source/context. Host AI data handling follows the Host product/deployment policy.

See [SECURITY.md](SECURITY.md) for the exact boundary.

## Browser contract

**Playwright is the Browser driver. Chrome / Edge / Chromium is the executable.** `--browser-executable` selects an executable after the Playwright driver is available; it does not bypass Playwright.

Host policy may still block navigation. Such cases remain `NOT_VERIFIED_ENVIRONMENT`, never product PASS.

## Design / modernization

The existing Design IR and modernization capability remain available, but 4.0 GA is first optimized for **controlled repair of existing Web projects**. Candidate generation can now represent **1–3 real choices**; the default remains three for compatibility with the existing redesign pipeline. A simple fix no longer has to manufacture extra strategic choices when a caller explicitly requests fewer.

Candidate direction-contract difference proves declared direction metadata differs; it does not prove rendered structural difference.

## Public surface

```text
run      default inspection / repair / modernization entry
doctor   environment readiness
auth     explicit authentication profile
expert   advanced and compatibility surfaces
```

Historical commands remain compatibility surfaces. New Python integrations should still start with:

```python
from web_ui_quality import run
result = run(".", "修复订单页移动端错位，不要动登录逻辑")
```

## Non-negotiable trust rules

1. Evidence First. No Evidence, No PASS.
2. Runtime cannot self-authorize project writes.
3. Runtime cannot autonomously execute project-owned tools.
4. Recommendation is not user selection.
5. Resume never restores write authority.
6. Environment failure is not source failure.
7. Visual improvement cannot override required tool failure or unexpected drift.
8. Partial global coverage cannot be rendered as whole-project verification.
9. Protected scope is mandatory context, not optional retrieval content.
10. Local HMAC integrity is tamper-evident, not remote attestation.

## Scope

4.2.3 is focused on controlled repair and UI adjustment of existing Web projects, with incremental modernization retained as an advanced capability. It is best suited to frontend/full-stack teams, QA and Engineering Managers, enterprise legacy-system maintainers, delivery/outsourcing teams, high-risk CRM/ERP/order/permission/payment Web SaaS, and AI Coding Host/Agent integrations. The frozen 4.0.0-rc.1 kernel lineage remains provenance, not the current package identity.

It is **not** a universal backend/database/deployment agent, an autonomous production deployer, a replacement for real user research, or a system that may claim a real repair succeeded without Host/Browser evidence. Synthetic benchmarks are product hypotheses and infrastructure qualification only; they are never promoted to real-model accuracy or real-user evidence.

See [GUIDED_REPAIR_QUICKSTART.md](GUIDED_REPAIR_QUICKSTART.md), [ARCHITECTURE.md](ARCHITECTURE.md), [SECURITY.md](SECURITY.md), [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md), [COMPATIBILITY_MATRIX.md](COMPATIBILITY_MATRIX.md), and [REPAIR_MODERNIZATION_ACCEPTANCE.md](REPAIR_MODERNIZATION_ACCEPTANCE.md).


## External Host-Agent benchmark

See [AGENT_BENCHMARK_PROTOCOL.md](AGENT_BENCHMARK_PROTOCOL.md) for blind workspace preparation, Host result ingestion and aggregation. Without externally produced Host results, the benchmark qualification path intentionally remains `NOT_VERIFIED_HOST_AUTOMATION`.
