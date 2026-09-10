# Formal Qualification Fix Round — failure replay

This replay was recorded from the immutable Formal-1 artifacts before any
change on `formal-qualification-fixes`. The baseline is
`f6f830942fb9dd2fe4ae188934fa20e00662ab98`. The historical ledger and
qualification fixture were not edited.

## Q12 — runtime status

- Intent: `修复订阅页面状态一直出错的问题，完成后重新打开页面确认显示正常。`
- Patch and scope: Host candidate and V3 receipt both bound `app.js`; the
  receipt says `EDIT/APPLIED`. No scope expansion was observed.
- Browser evidence: Before had three stable HTTP 200/rendered records with
  one page error per viewport and page health `RUNTIME_BROKEN`. After had
  three stable HTTP 200/rendered records with zero errors; the independent
  probe observed the `Active` status.
- Comparison: `INCONCLUSIVE`; Before was rejected as
  `BROWSER_EVIDENCE_NOT_VERIFIED`, `BROWSER_RECORD_NOT_PASS`, and
  `BROWSER_RUNTIME_ERRORS`, while After was clean.
- Evidence graph and final result: graph
  `COMPLETE_PENDING_OR_NONVERIFIED_CHAIN`, `requiredMissing=[]`; TaskResult
  `COMPLETED / NOT_VERIFIED`, reason `INSUFFICIENT_EVIDENCE`.
- Failure node and taxonomy: the generic runtime-side usability gate rejected
  the expected defect-bearing Before records, so the comparison never reached
  the runtime-status transition. Classification: comparator false negative.
- Evidence: `formal-qualification-20260910/rounds/round-1/Q12/host-treatment/`
  (`wuq/<run>/before/evidence/smart-acceptance-report.json`,
  `after/evidence/smart-acceptance-report.json`, `compare/comparison.json`,
  `wuq/final-result.json`).
## Q14 — keyboard focus visibility

- Intent: `修复工作区访问页面用键盘操作时看不出当前焦点的问题，完成后用键盘焦点确认。`
- Patch and scope: Host candidate and V3 receipt were bound to `styles.css`
  and report `EDIT/APPLIED`.
- Browser evidence: all three viewports were stable HTTP 200, rendered, and
  `PASS/VERIFIED`. The measured `missingFocusAffordance` count changed from
  `1` in every Before record to `0` in every After record.
- Comparison: `COMPARABLE_NO_PROVEN_IMPROVEMENT`; the generic record status,
  page health, and high-severity finding sets did not encode that measured
  keyboard transition.
- Evidence graph and final result: graph
  `COMPLETE_PENDING_OR_NONVERIFIED_CHAIN`, `requiredMissing=[]`; TaskResult
  `COMPLETED / NOT_VERIFIED`, reason `INSUFFICIENT_EVIDENCE`.
- Failure node and taxonomy: the generic comparator ignored the measured
  keyboard objective even though the evidence was current and complete.
  Classification: comparator/evidence-binding false negative.
- Evidence: `formal-qualification-20260910/rounds/round-1/Q14/host-treatment/`
  (`wuq/<run>/before/evidence/smart-acceptance-report.json`,
  `after/evidence/smart-acceptance-report.json`, `compare/comparison.json`,
  `wuq/final-result.json`).

## Q16 — contrast

- Intent: the frozen scope-protected contrast repair for the `Sign in securely`
  target; only `styles.css` was allowed.
- Patch and scope: Host candidate and V3 receipt were bound to `styles.css`
  and report `EDIT/APPLIED`; protected files were unchanged.
- Browser evidence: all three viewports were stable HTTP 200 and rendered. The
  Before measurement contained one low-contrast sample per viewport with ratio
  `1.5 < 4.5`; After contained a measured empty low-contrast list. The generic
  page-health/auth boundary reported `AUTH_REQUIRED`, so the records were
  `NOT_VERIFIED` and the journey was not executed.
- Comparison: `INCONCLUSIVE`; both Browser sides were rejected by
  `BROWSER_RECORD_NOT_PASS` and `BROWSER_EVIDENCE_NOT_VERIFIED` despite the
  target-specific contrast transition.
- Evidence graph and final result: graph
  `COMPLETE_PENDING_OR_NONVERIFIED_CHAIN`, `requiredMissing=[]`; TaskResult
  `COMPLETED / NOT_VERIFIED`, reason `INSUFFICIENT_EVIDENCE`.
- Failure node and taxonomy: page-health/auth gating prevented a
  target-specific rendered contrast measurement from entering comparison.
  Classification: evidence-binding false negative with an auth-boundary
  interaction.
- Evidence: `formal-qualification-20260910/rounds/round-1/Q16/host-treatment/`
  (`wuq/<run>/before/evidence/smart-acceptance-report.json`,
  `after/evidence/smart-acceptance-report.json`, `compare/comparison.json`,
  `wuq/final-result.json`).

## Q17 — scoped write versus read-only

- Intent: `修复用量详情页在手机上的横向溢出。只允许改 styles.css；其它文件包括 package.json 和 README.md 都禁止修改。`
- Patch and scope: the frozen allowed scope was `styles.css`; no Host patch or
  receipt was created because WUQ stopped before mutation.
- Browser/evidence result: the preserved Before and independent observations
  remained read-only; there was no valid After repair evidence.
- Comparison, evidence graph, and TaskResult: no comparison or evidence graph
  was produced; the incident result was `BLOCKED`, final claim
  `NOT_VERIFIED`, TaskResult reason `SAFETY_REFUSAL`.
- Failure node and taxonomy: the whole-task read-only detector matched the
  scoped tail `其它文件...禁止修改`, producing `INTENT_CONFLICT` before Host
  mutation. Classification: scope-intent false negative.
- Evidence: `formal-qualification-20260910/rounds/round-1/Q17/host-treatment/incident-recovery.json`
  (`INC-R1-Q17-001`).

## Q28 — “安全中心” routing

- Intent: `安全中心的提示内容在手机上显示不全，帮我处理好，并确认完整内容能看见。`
- Patch and scope: a candidate was prepared for `styles.css`, but no trusted
  write receipt or valid After comparison was produced.
- Browser/evidence result: the Before browser evidence was sufficient to show
  the target content-clipping issue, but the router selected CHECK/
  `SPECIALIZED_AUDIT` from the business name and did not enter the repair
  workflow. No repair After evidence existed.
- Comparison, evidence graph, and TaskResult: no valid comparison or evidence
  graph was produced; incident result `BLOCKED`, final claim
  `NOT_VERIFIED`, TaskResult reason `SAFETY_REFUSAL`.
- Failure node and taxonomy: a specialized keyword false positive caused a
  normal repair request to be treated as a read-only audit. Classification:
  specialized-router false positive.
- Evidence: `formal-qualification-20260910/rounds/round-1/Q28/host-treatment/incident-recovery.json`
  (`INC-R1-Q28-001`) and its preserved `wuq/<run>/before/` report.

## Q30 — keyboard focus visibility

- Intent: `邀请协作者页面用键盘操作时看不出当前焦点，帮我改善一下并确认 Tab 到按钮时能看见。`
- Patch and scope: Host candidate and V3 receipt were bound to `styles.css`
  and report `EDIT/APPLIED`.
- Browser evidence: all three viewports were stable HTTP 200, rendered, and
  `PASS/VERIFIED`; `missingFocusAffordance` changed from `1` to `0` in every
  viewport.
- Comparison: `COMPARABLE_NO_PROVEN_IMPROVEMENT`; the same generic comparator
  ignored the keyboard-specific transition.
- Evidence graph and final result: graph
  `COMPLETE_PENDING_OR_NONVERIFIED_CHAIN`, `requiredMissing=[]`; TaskResult
  `COMPLETED / NOT_VERIFIED`, reason `INSUFFICIENT_EVIDENCE`.
- Failure node and taxonomy: target-specific keyboard evidence was present,
  but generic health/finding comparison found no generic improvement.
  Classification: comparator/evidence-binding false negative.
- Evidence: `formal-qualification-20260910/rounds/round-1/Q30/host-treatment/`
  (`wuq/<run>/before/evidence/smart-acceptance-report.json`,
  `after/evidence/smart-acceptance-report.json`, `compare/comparison.json`,
  `wuq/final-result.json`).
