# Browser and verification

## Evidence layers

1. Static source evidence proves only what is present in inspected files.
2. Serialized screenshots and reports are candidate evidence.
3. The bundled Playwright adapter creates process-local `browser_proven` evidence using fresh isolated contexts.
4. `real_page_proven` additionally requires trusted Host confirmation that the target is an approved real product page.
5. Human Step 10 reasons remain separate from automated Browser metrics.

## Preferred UI-first path

Use `check` before source diagnosis for ordinary acceptance work. It captures mobile `390×844`, small-desktop `768×1024`, and desktop `1440×900`, then combines screenshot evidence, representative-render checks, runtime health, and an explicit or safe A1 journey with Outcome Proof. Use `quick-ui` only for screenshot-only compatibility work. Review screenshots manually before accepting its Top 3.

After a fix, use `quick-ui` again on the same route and state. Use `browser-compare` or `audit-and-compare` when a formal same-condition Before/After artifact is required.

Do not treat page-load success as a complete critical journey. Add task-specific read-only or reversible journey evidence through the trusted Host. Payment, publication, deletion, account changes, uploads, external messages, and irreversible state changes are outside the default Browser adapter.

## Legacy Browser Standard

The legacy `browser_standard.py` contract remains for existing controlled-Fixture and host-attestation integrations. It is intentionally strict and should not be expanded to carry ordinary product behavior.

## Result semantics

- `PASS`: all applicable blocking checks and trusted evidence pass.
- `PASS_WITH_WARNINGS`: only non-blocking P2/P3 or trusted Browser warnings remain.
- `FAIL`: any P0/P1, Browser failure, journey failure, or hard red line remains.
- `NOT_VERIFIED`: required Browser, real-target, journey, or human evidence is missing.

Non-2xx navigation is always `FAIL`. Semantic locators stay strict by default: multiple matches must be resolved by improving the user-facing locator or specifying an intentional `nth`; the runtime must not silently select the first match. Mobile widths use a touch-enabled mobile Browser context, and standalone controls are checked against the 44px target contract.
