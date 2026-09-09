> Package: **4.3.0** · Package Stage: **4.3.0-open-source** · Trust Kernel: **4.2.3** · Kernel Base Lineage: **4.0.0-rc.1** · Receipt Protocol: **3.0** · Evidence Schema: **3.0**

# Adaptive Trust Kernel RFC

**Status:** `NOT_ACTIVE_IN_4.3.0`

This is a non-authoritative design note. It cannot change write authority,
verification thresholds, or the default workflow.

Future adaptive guidance may change discovery depth, explanation length, or
non-authoritative ranking only after controlled, independently measured
evidence. It may never remove Protected Scope, Host-only write authority,
receipts, drift checks, required verification, or claim boundaries.

Read-scope expansion and write-scope expansion remain separate decisions. A
model may request more context to diagnose a problem without receiving
permission to modify the newly referenced files.

Any future adaptive mode must be reversible to the fixed workflow and must
report false `VERIFIED` outcomes, scope violations, regression escapes,
abandonment, intervention, wall time, and trusted-completion cost. Synthetic
evidence alone cannot activate it.

