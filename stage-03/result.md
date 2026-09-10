# Stage 03 Result — One Semantic Result

Status: PASS
Baseline SHA: `ea41be16dfb04c079d858de2f2ef9a08a7575ac8`

## Round 1

The baseline JSON and CI results described the same deterministic task but had no canonical reason field; the human renderer explained the raw outcome directly. The smallest fix added a deterministic `reasonCode` projection to `TaskResult`, added it to both schema copies, and made the human explanation use that same code. Targeted regression: `2 passed in 11.56s`.

## Round 2

The reason-code boundary matrix passed for Browser unavailable, network, dependency, environment/policy, insufficient evidence, Host/user decision, drift, inspection findings, and task failure. JSON and CI schema validation passed; their semantic projections matched for the same request. JSON retained exit `0`, CI retained exit `3`, and the focused regression set passed `48 tests in 45.59s`.

## Round 3

- Full repository regression: `685 passed in 423.36s`.
- Public entry point: `11 passed in 43.31s`, exit `0`.
- Repeated semantic matrix and JSON/CI comparison: passed.
- `git diff --check`: exit `0`.
- No web rescue was needed.

## Changed files

- `runtime/python/web_ui_quality/task_result.py`
- `runtime/python/web_ui_quality/__main__.py`
- `schemas/task-result.schema.json`
- `runtime/python/web_ui_quality/schemas/task-result.schema.json`
- `tests/public/test_semantic_result.py`
- `stage-03/protocol.md`

Post-stage hashes:

- `task_result.py`: `C8EB55DB7C1EBC8B68A42DC517305CC136E8F4C8470913BA3628E355E0081B2E`
- `__main__.py`: `6207735B20BC4453FC3EF9A7660DDFF0790BEF8B2CF12E495336B9FD933973C1`
- `schemas/task-result.schema.json`: `E22875C8FDD1A1BBAB871C698C8AB20C95515F8D0AA29E319375F7AF0592EA1D`
- `runtime/python/web_ui_quality/schemas/task-result.schema.json`: `E22875C8FDD1A1BBAB871C698C8AB20C95515F8D0AA29E319375F7AF0592EA1D`
- `test_semantic_result.py`: `68857F3B63955CA449EBC5BACD2CE0C50EFD7ED88FA091E48381EC6DAFB136B7`
- `stage-03/protocol.md`: `D4045FBB5B4C00DACD9E44B420A208B968466891930C1B3DCB84E4101B2043BF`

## Acceptance

- Plain, JSON, and CI expose one semantic result projection for the same request.
- Every emitted task result has a non-empty canonical reason code.
- Human explanation is derived from the canonical reason code.
- Existing CI exit semantics and claim/Host/Browser authority boundaries remain unchanged.
- `STAGE_STATUS = PASS`.

The protocol file was written after the Round 1 baseline comparison due to a procedural timing error. That fact is recorded in the protocol and ledger; no source change preceded the baseline comparison. The work remains uncommitted because local Git author identity is unset; no clean-checkout or commit claim is made.
