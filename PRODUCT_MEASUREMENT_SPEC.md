> Package: **4.3.0** · Package Stage: **Commercial Stable** · Trust Kernel: **4.2.3** · Kernel Base Lineage: **4.0.0-rc.1** · Receipt Protocol: **3.0** · Evidence Schema: **3.0**

# Product Measurement Specification

## Product definition

**让 AI 修改 Web 项目时不越界、可验证、可追溯。**

Web UI Quality is an AI Web-change trust control layer, not a second autonomous reasoning brain. Measurement therefore focuses on trusted task completion and error containment rather than unsupported claims that Runtime makes the underlying model smarter.

## Evidence-type vocabulary

Every reported metric MUST carry exactly one of these evidence labels:

- `REAL_HOST` — measured on an actual supported Host integration;
- `REAL_USER` — measured from real user workflows under an approved study/telemetry protocol;
- `CONTROLLED_BENCHMARK` — reproducible controlled benchmark with known protocol and ground truth;
- `SYNTHETIC_SCENARIO` — simulated/synthetic workload used for product hypotheses only;
- `NOT_MEASURED` — no qualifying evidence exists.

Synthetic results may never be rewritten as real-user, real-model or production evidence.

## North-star metric

### Trusted Task Completion Rate

A task counts only when the user's intended scoped Web change is actually completed, Protected Scope is respected, no disqualifying regression escapes verification, required evidence is present, and the final claim does not exceed coverage.

## Required supporting metrics

| Metric | Definition |
| --- | --- |
| False VERIFIED Rate | Share of `VERIFIED` outcomes contradicted by authoritative evidence/ground truth. |
| Protected Scope Violation Rate | Share of write tasks that modify outside the authorized scope. |
| Regression Escape Rate | Share of completed tasks with a material regression missed by required verification. |
| Closed-loop Entry Rate | Share of in-scope tasks able to enter the complete applicable trust/repair/verification loop. |
| First-pass Success | Share of tasks trusted-complete without user correction/retry. |
| User Interventions | Count of required user actions per task, separated into necessary authority/security actions and avoidable workflow friction. |
| Task Abandonment | Share of started tasks not completed because the workflow was abandoned. |
| Resume Success | Share of eligible resumptions that recover valid workflow state without restoring write authority. |
| P50/P95 Wall Time | End-to-end elapsed time for comparable task cohorts. |
| Token/Cost per Trusted Completion | Model Token/cost divided by trusted-completed tasks; report initial pass and total-with-rework separately. |

## Current evidence boundary for Trust Kernel 4.2.3

- Real Codex Host qualification: `NOT_MEASURED` unless executed on an actual Codex Host.
- Native Windows qualification: `NOT_MEASURED` unless executed natively on Windows.
- Real-user effect: `NOT_MEASURED` without a real-user protocol.
- Real-model accuracy improvement: `NOT_MEASURED` without comparable Host/model experiments.
- Real-world Token savings: `NOT_MEASURED` without comparable usage measurements.
- Package-local deterministic security/acceptance results may be labeled `CONTROLLED_BENCHMARK` only when the exact protocol and result are recorded.

## Reporting rule

Every dashboard, benchmark summary, commercial claim or release note that cites an effect size must include the evidence type, sample size, task population, model/Host identity when applicable, and whether the value is an observed measurement or a synthetic hypothesis.
