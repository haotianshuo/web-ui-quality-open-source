# Browser and verification

## Evidence layers

1. Static source evidence proves only what is present in inspected files.
2. Serialized screenshots and reports are candidate evidence.
3. The bundled Playwright adapter creates process-local `browser_proven` evidence using fresh isolated contexts.
4. `real_page_proven` additionally requires trusted Host confirmation that the target is an approved real product page.
5. Human Step 10 reasons remain separate from automated Browser metrics.

## Preferred UI-first path

Use the normal natural-language `run` entry for ordinary acceptance and repair. Its internal capture covers mobile `390×844`, tablet `768×1024`, and desktop `1440×900`, combining rendered measurements, runtime health and safe task evidence. `check` and `quick-ui` are compatibility helpers, not alternate workflows the user must select. Review the screenshots and all relevant candidates before deciding visual acceptance; Top 3 is only a presentation limit.

After a fix, continue the same normal `run` with its bound Host receipt and `--after-url`, using the same route, state and device conditions. A fresh post-edit run records a new Before and cannot substitute for this continuation. View the resulting screenshots; automated geometry and task success do not establish visual finish.

Do not treat page-load success as a complete critical journey. Add task-specific read-only or reversible journey evidence through the trusted Host. Payment, publication, deletion, account changes, uploads, external messages, and irreversible state changes are outside the default Browser adapter.

## Legacy Browser Standard

The legacy `browser_standard.py` contract remains for existing controlled-Fixture and host-attestation integrations. It is intentionally strict and should not be expanded to carry ordinary product behavior.

## Result semantics

- `PASS`: all applicable blocking checks and trusted evidence pass.
- `PASS_WITH_WARNINGS`: only non-blocking P2/P3 or trusted Browser warnings remain.
- `FAIL`: any P0/P1, Browser failure, journey failure, or hard red line remains.
- `NOT_VERIFIED`: required Browser, real-target, journey, or human evidence is missing.

Non-2xx navigation is always `FAIL`. Semantic locators stay strict by default: multiple matches must be resolved by improving the user-facing locator or specifying an intentional `nth`; the runtime must not silently select the first match. Mobile widths use a touch-enabled mobile Browser context, and standalone controls are checked against the 44px target contract.
