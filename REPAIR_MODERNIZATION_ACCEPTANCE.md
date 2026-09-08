> Package: **4.3.0** · Package Stage: **Commercial Stable** · Trust Kernel: **4.2.3** · Kernel Base Lineage: **4.0.0-rc.1** · Receipt Protocol: **3.0** · Evidence Schema: **3.0**

# Repair & Modernization Acceptance — Web UI Quality 4.3.0 (Trust Kernel 4.2.3)

The package identity is 4.3.0; the retained acceptance contract is governed by Trust Kernel 4.2.3.


The retained legacy acceptance scenario is:

> “订单页面手机上坏了，帮我修。这个项目本来就很多报错，登录逻辑别碰。另外其他几个页面好像也有类似问题。”

## Non-negotiable behavior

- Existing failures remain baseline state rather than being blamed on the new repair.
- Authentication and protected scope remain explicit decisions.
- Runtime cannot self-authorize writes or project-tool execution.
- Project-tool FAIL/NOT_VERIFIED cannot be hidden by Browser improvement.
- Unexpected drift cannot become `VERIFIED`.
- Resume never restores write authority.
- Large-repository patch-scope verification never becomes an unlimited whole-project claim.

## Frozen benchmark-trust lineage retained as historical evidence in 4.2.3

1. CHECK/Inspection, Repair and Modernization adapt into TaskResult v1.
2. Inspection receives a human report without requiring `--expert-json`.
3. TaskResult coverage is required; Repair `VERIFIED` requires complete Patch/Target/Critical Context coverage.
4. Global partial coverage remains visible in both machine and human results.
5. Relevant Context Packet keeps Protected Scope as mandatory context and exposes ranked source references without granting authority.
6. The 40-archetype deterministic repair development corpus and Fake-Agent attack suite qualify fixture/scorer/trust infrastructure only; Host Agent repair accuracy remains `NOT_VERIFIED_HOST_AGENT`.
7. Privacy network-egress policy is executable as a release gate.
8. Repair-scope revert plans are Host-only, tamper-evident and explicitly bounded to the repair scope.
9. Design candidate generation accepts 1–3 requested directions; no rendered-structure claim is inferred from declared direction metadata.
