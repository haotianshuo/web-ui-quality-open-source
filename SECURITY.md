> Package: **4.3.0** · Package Stage: **Commercial Stable** · Trust Kernel: **4.2.3** · Kernel Base Lineage: **4.0.0-rc.1** · Receipt Protocol: **3.0** · Evidence Schema: **3.0**

# Security and trust boundary — Web UI Quality 4.3.0 (Trust Kernel 4.2.3)

The package identity is 4.3.0; the Trust Kernel identity is 4.2.3.

## Reporting a Vulnerability

If you discover a security vulnerability in this open-source repository, report
it privately through one of these channels:

- **GitHub Security Advisories:** [open a private report](https://github.com/haotianshuo/web-ui-quality-open-source/security/advisories/new)
- **Email:** `xrlcom@126.com` with the subject `[SECURITY] web-ui-quality`

Do not disclose credentials, private customer data, or an exploitable payload in
a public issue. Please include the affected version, operating system, a
minimal sanitized reproduction, impact, and any relevant file or gate name.
See [SECURITY_RESPONSE_POLICY.md](SECURITY_RESPONSE_POLICY.md) for the handling
boundary. Response timing and public acknowledgements depend on the report and
available maintainer capacity; this project does not promise an unconditional
service-level agreement.


- Runtime cannot invent, infer, deserialize or cache source-write authority.
- Runtime produces Patch Candidates only; the Host owns actual project writes and repair-scope restoration.
- Host Write Receipts are bound to run/task/session, finding/source scope, baseline/plan/toolchain/verification digests and file Before/After hashes.
- Project-owned tools remain untrusted execution. Host plans bind binary hash, argv/cwd, network/resource/filesystem policy and run identity.
- Missing project-tool filesystem enforcement remains `NOT_VERIFIED`; reported unexpected writes fail verification.
- Unexpected repository drift outside the Host write scope blocks final `VERIFIED`.
- Resume restores workflow state only and keeps `writeAuthorization=false`.
- Browser unavailable/policy-blocked states remain unverified and cannot fabricate screenshots or source blame.
- TaskResult requires explicit coverage; a bounded patch claim cannot silently become a whole-project claim.
- Relevant Context Packet carries no authority. Protected Scope and Host-only execution rules are mandatory context and are not removed by the source-reference budget.
- Repair-scope revert plans are non-authoritative and tamper-evident; they do not contain prior file bytes and cannot promise whole-repository restoration.


## 4.2.3 Browser security and evidence persistence

- Every WUQ Browser consumer uses the shared secure Browser-context/launch policy. `--no-sandbox` is denied unless the external Host explicitly attests outer isolation; that attestation is **not** independent OS verification.
- Network permission is exact-origin. Side-effect methods, dangerous GET routes, authenticated XHR/fetch GET requests, authenticated document navigation, and WebSocket endpoints require exact machine-readable authorization; no model recommendation grants network authority. Query-bearing request and navigation authorization binds the normalized query by SHA-256 digest without persisting raw values.
- `fault_injection_harness.py` is a local synthetic-fixture evaluator, not a production Browser entry point. It rejects live URL/auth/storage-state inputs and reuses the shared Secure Browser Context; it will report `NOT_MEASURED_ENVIRONMENT` rather than add `--no-sandbox` merely to make a benchmark run under root.
- Credential-like headers are origin-bound and fail closed when supplied as unknown BrowserContext-wide headers. Storage state is filtered to explicit credential origins.
- Persisted console/page-error/DOM/geometry text is best-effort redacted for common credentials, JWT/query secrets, email addresses and phone-like PII. Known sensitive form/annotated DOM nodes are masked before screenshots.
- Screenshot masking is **not** universal visual-PII recognition. Arbitrary names, account balances, medical data, canvas pixels or unannotated text may still appear. Mark additional regions with `data-wuq-sensitive` and use an external enterprise redaction policy where required.
- Browser route enforcement is in-process. Process/network isolation and remote attestation remain `NOT_MEASURED` unless independently provided by the Host environment.

## Runtime network / privacy boundary

Core Runtime network-capable imports are checked by `scripts/privacy_egress_acceptance.py`. Explicit exceptions are documented capabilities, currently including:

- `figma_input.py` — explicit Figma network adapter;
- `report_server.py` — local report-serving socket infrastructure.

The command policy also blocks direct network utility execution such as curl/wget/ssh/scp/ftp/netcat through the protected project-tool path.

This gate does **not** make claims about the external Host AI provider. Codex/Claude Code/Cursor or another Host may read/send project context according to its own product, deployment and enterprise data policy. Web UI Quality Runtime contains no OpenAI/Anthropic client and does not itself decide Host-model retention or transport.

Local HMAC/seal integrity is tamper-evident under the local process threat model; it is not remote attestation and cannot resist an administrator controlling both local evidence and integrity keys.
