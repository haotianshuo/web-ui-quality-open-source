# Audit, Evidence, And Severity

## Five Dimensions

1. UI appearance: alignment, overflow, occlusion, responsive behavior, images, long text, icons, state jumps, safe areas, typography, spacing, color, and radius.
2. Page logic: navigation, role entry, state transitions, validation, loading/empty/failure, ordering, next-step guidance, duplicate submission, and synchronization.
3. Defects and junk: console/network errors, broken links/media, empty controls, duplicate IDs, TODO/demo content, dead CSS/code, and unused assets.
4. Basic security: client-side credentials, sensitive disclosure, access-entry risk, dangerous actions, unsafe navigation/DOM, input risk, prompt injection, and evidence leakage. Do not claim penetration testing.
5. Productization and experience: hierarchy, density, primary actions, guidance, business fit, reduced steps, recovery, and safer mature patterns.

## Minimum Accessibility

Check keyboard reachability, focus visibility/order/return, labels and errors, accessible names, custom Name/Role/Value, contrast risk, 200% zoom and mobile reflow, non-color state communication, and reduced motion. Automated or static checks do not certify WCAG; unavailable screen-reader or Browser checks remain unverified.

## Methods

- S: static source/configuration evidence.
- B: real Browser evidence.
- M: user or qualified human confirmation.

Record applicability, `requiredForCurrentGate`, source, trust level, redaction, and state. A valid Finding includes an ID, category, P0–P3 severity, methods, location, instruction/evidence sources, impact, recommendation, and `verified` or `unverified` state.

## Rule Coverage And Provider Evidence

Keep stable rule metadata and record `executed`, `violation`, `pass`, `incomplete`, `inapplicable`, `error`, and `unavailable` separately. `executed` without an outcome and every `incomplete/error/unavailable` item remain `NOT_VERIFIED`; zero Findings cannot hide an unexecuted or failed rule.

Normalize Provider envelopes only after validating the run, Provider/version, target, status, rule, evidence kind/hash, location, limitations, redaction, and attempt count. Deduplicate one issue by stable fingerprint while retaining every source. A Provider pass cannot erase a violation, and Provider severity/impact cannot set P0–P3. Keep only minimal redacted evidence and project-relative locations.

For automated accessibility evidence, retain `violations`, `passes`, `incomplete`, and `inapplicable`. Record engine version, rule set, coverage scope, and manual review items. Manual evidence references the original incomplete evidence ID and does not overwrite it. Zero violations is never a compliance claim.

## Severity And Results

- P0: security, data corruption, major privilege breach, or unrecoverable risk.
- P1: core business or serious usability failure.
- P2: clear defect with a workaround.
- P3: non-blocking improvement.

`PASS` requires every applicable mandatory item. `PASS_WITH_WARNINGS` permits only reviewed non-blocking P2/P3 warnings. P0, unresolved P1, or failed invariant means `FAIL`. Missing critical evidence means `NOT_VERIFIED`. Never convert `unverified`, environment limitation, or an accepted P1 into a pass.
