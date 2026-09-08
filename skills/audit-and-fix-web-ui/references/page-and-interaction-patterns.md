# Page And Interaction Patterns

Load only patterns supported by the detected page capabilities.

## Page Modes

- Application shell: stable navigation, current location, responsive composition, and permission-aware entry points.
- List/detail: search, filtering, selection, empty/loading/error states, stable detail context, and return behavior.
- Form/wizard: labels, requirements, validation, draft preservation, review-before-submit, recovery, and duplicate-submit prevention.
- Timeline/approval: actor, timestamp, state transitions, reasons, current responsibility, and safe high-risk actions.
- Chat/AI: message identity, sending/failed/retry states, streaming status, interruption, and untrusted-content boundaries.
- Media: aspect ratio, load/error/alt behavior, zoom/fullscreen, responsive sources, and keyboard operation.
- Order/status: explicit amount/state/outcome, pending/failure recovery, and no automatic real transaction.
- Dashboard/admin: dense but scannable hierarchy, filters, tables, bulk-action safety, and preserved administrator exceptions.
- Editor: unsaved state, validation, preview, undo expectations, and leave protection.
- Login/permission: honest access states; never bypass authentication or infer authorization from hidden DOM.

## Interaction States

For each applicable component consider default, hover, focus, active, disabled, loading, empty, success, failure, permission denied, offline, retrying, completed, cancelled, long text, and narrow viewport. Missing Browser evidence makes dynamic or geometric states unverified, not passed.

## Mature Organization

Prefer list-detail, master-detail, grouped lists, timelines, feeds, tabs, progressive disclosure, drawers, bottom sheets, anchored long pages, grouped forms, three-step wizards, draft save, review-before-submit, confirmation, undo, and recovery when they fit the business task. Select by frequency, impact, and failure risk rather than visual novelty.
