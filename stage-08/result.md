# Stage 08 Result — Security Coverage Visibility

Status: PASS_WITH_ENVIRONMENT_LIMITATION
Stage objective status: PASS
Baseline SHA: `ea41be16dfb04c079d858de2f2ef9a08a7575ac8`

## Round 1

The baseline in-memory fixture reproduced the visibility gap: with `include_security=False`, the result exposed only `securityAudit=OPT_IN_ONLY`, `securityFindingsIncluded=false`, and no explicit `NOT_MEASURED` security status. With the opt-in enabled, the existing bounded static rules found security items.

## Round 2

The minimal change added a `securityCoverage` projection to normal and empty audit results and to the user summary. Disabled coverage now reports `status=NOT_MEASURED`, `enabled=false`, zero claimed security findings, and an explicit `--security-audit` next action. Enabled coverage reports `status=MEASURED`, the bounded finding count/IDs, and a claim boundary that excludes full AppSec, Browser, Host, and production qualification.

The test fixture confirmed that credential-like values remain redacted. A security-language Router request remains `CHECK`/`SECURITY`, read-only, and `writeAuthorized=false`.

The first full run exposed a five-line `core.py` budget overage (`2322 > 2317`). The projection was compressed without removing its behavior; the corrected core is 2309 lines and the affected regression passed (`36 passed`).

## Round 3

- Focused security and boundary set: `52 passed, 3 skipped, 1 deselected in 18.27s`.
- Public entry point: `38 passed in 52.09s`, exit `0`.
- Final full repository: `703 passed, 8 skipped, 1 failed in 397.79s`.
- The sole full-suite failure was the existing Browser execution sentinel, `PLAYWRIGHT_SYNC_API_REQUIRED_FOR_FULL_BROWSER_GATE`, because Playwright is unavailable in the active Python environment.
- `core.py` line budget: `2309`, below the enforced maximum `2317`.
- `git diff --check`: exit `0`.
- No web rescue was used.

## Changed files

- `runtime/python/web_ui_quality/core.py`
- `runtime/python/web_ui_quality/schemas/audit-result.schema.json`
- `schemas/audit-result.schema.json`
- `tests/public/test_security_coverage_visibility.py`

Post-stage hashes:

- `core.py`: `D89DC514915B4BBB2CFFCE01036EF159CC90F53B0A5ABE57629E74F6F18C4D54`
- `runtime audit-result.schema.json`: `E70494FDD13C262747E15CDDD7EC6356ED8F2D7F5B38A78D3634428685B828FA`
- `root audit-result.schema.json`: `E70494FDD13C262747E15CDDD7EC6356ED8F2D7F5B38A78D3634428685B828FA`
- `test_security_coverage_visibility.py`: `BA13F1313E346E89163B1382B78D13CAC9151E1E7CD66A4BCF55A2FDA3254A7E`
- `stage-08/protocol.md`: `C1FB8F0B1F4A8791BE3786782A8BDDA3F977A66FF1C8C349C0612E9B28DA1298`

## Acceptance

- Security not enabled is visibly `NOT_MEASURED`, not an implied clean result.
- Security enabled remains bounded static measurement with redaction and no source mutation.
- The opt-in flag does not grant credentials, navigation, Host, or write authority.
- `STAGE_STATUS = PASS_WITH_ENVIRONMENT_LIMITATION`; the Browser execution capability remains `NOT_MEASURED`.
