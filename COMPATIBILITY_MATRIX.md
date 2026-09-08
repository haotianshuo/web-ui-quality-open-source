> Package: **4.3.0** · Package Stage: **Commercial Stable** · Trust Kernel: **4.2.3** · Kernel Base Lineage: **4.0.0-rc.1** · Receipt Protocol: **3.0** · Evidence Schema: **3.0**

# Compatibility matrix — Web UI Quality 4.3.0 (Trust Kernel 4.2.3)

The package identity is 4.3.0; compatibility rows that refer to the kernel are explicitly labeled 4.2.3.


| Surface | 4.2.3 status | Contract |
|---|---|---|
| `run` | Stable facade | Default inspection/repair/modernization entry |
| `doctor` / `auth` / `expert` | Public CLI | Explicit readiness/security/advanced surfaces |
| Historical commands | Compatibility | Parseable but not recommended for new integrations |
| Root Python exports | Frozen | `public-api-manifest.json`; only `run` is stable for new integrations |
| TaskResult v1 | Stable compatibility contract | Required coverage; legacy repair fields retained as aliases |
| Repair Report | Compatibility source | Adapted into TaskResult/Human Task Report |
| Existing `unified-report` | Historical compatibility | Not reused as a second “TaskResult” concept |
| Sealed Project Baseline | Supported | Global completeness separated from patch-scope coverage |
| Host Write Receipt | Supported | Exact run/task/session/scope/hash binding |
| Host Project Tool Result | Supported | Conditional evidence, read-only filesystem policy, unexpected-write detection |
| Relevant Context Packet v1 | Deterministic context plan | No authority; recall measured independently |
| Repair-scope revert plan | Supported compatibility surface | Host-only execution; exact repair scope, not whole-repo rollback |
| Fault-injection harness | Infrastructure qualified | 10 deterministic fixtures; Host-Agent accuracy NOT_VERIFIED |
| Browser driver | Playwright | Existing Chrome/Edge/Chromium executable may be selected |
| Auth Profile | Supported | User-owned storage-state reference/digest + origin allowlist |
| Unknown production framework generation | Fail closed | No unsupported scaffold PASS |
| Core repair on unfamiliar stacks | Capability/evidence bounded | Read-only exploration may continue; success claims still require verification |
| Portable remote attestation | Not supported | Local integrity scope only |
| External Host AI privacy | Host policy | Runtime does not define Host-provider data retention/transport |

## Performance budget

The existing catastrophic-regression budgets remain release guards. Same-host release-to-release regressions should be investigated using a controlled protocol; The current package does not turn cross-machine timing differences into capability claims.
