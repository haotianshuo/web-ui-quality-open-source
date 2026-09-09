> Package: **4.3.0** · Package Stage: **4.3.0-open-source** · Trust Kernel: **4.2.3** · Kernel Base Lineage: **4.0.0-rc.1** · Receipt Protocol: **3.0** · Evidence Schema: **3.0**

# Product measurement specification

Web UI Quality aims to help AI-assisted Web changes stay scoped, verifiable,
and traceable. It is not a second reasoning model.

## Evidence labels

Every metric must carry one label:

- `REAL_HOST`
- `REAL_USER`
- `CONTROLLED_BENCHMARK`
- `SYNTHETIC_SCENARIO`
- `NOT_MEASURED`

Synthetic results cannot be relabeled as real-user, real-model, or production
evidence.

## Trusted task completion

A task is trusted-complete only when the intended scoped change is completed,
Protected Scope is respected, required verification is present, no disqualifying
regression escapes, and the final claim does not exceed coverage.

Useful supporting measures include false `VERIFIED` rate, protected-scope
violations, regression escapes, closed-loop entry, first-pass success, user
interventions, abandonment, resume success, wall time, and cost per trusted
completion. Each published measurement needs its sample, population, Host/model
identity where relevant, and evidence label.

