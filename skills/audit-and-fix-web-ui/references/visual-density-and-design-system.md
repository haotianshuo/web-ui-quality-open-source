# Visual Density And Design System

## Evidence Order

Use current user requirements, approved designs, project tokens/components, dominant rendered patterns, then general product patterns. Preserve finalized pages and documented exceptions.

## Reuse Order

1. Existing project components.
2. Existing semantic tokens.
3. Native capability of the current stack.
4. A small project-local component.
5. A third-party dependency only after explicit approval.

Map tokens by semantic meaning first, then nearby value. Do not batch-replace tokens or brand identity without approval.

## Review

Check hierarchy, reading order, primary-action dominance, grid and alignment, spacing rhythm, density, typography, long content, color roles, contrast risk, borders, separators, icons, states, responsive composition, touch reach, keyboard focus, reduced motion, and media behavior.

Adapt composition for mobile, desktop, and intermediate widths instead of shrinking desktop geometry. Keep dense enterprise surfaces compact but breathable; do not turn operational UI into decorative card walls. Button counts, color counts, and motion durations are heuristics, not universal pass thresholds.

Static source can inventory tokens and identify risks. It cannot prove rendered contrast, clipping, font loading, geometry, or visual maturity without Browser/manual evidence.

For ordinary UI repair, use a screenshot-first two-scale review:

1. Whole page: composition, navigation, density, hierarchy, main action, breakpoint reflow, and whether the screen resembles a coherent conventional product rather than mixed patterns.
2. Component geometry: shared left edges, repeated heights, gap rhythm, text-to-control ratio, icon-to-label ratio, crop, overlap, fixed-layer obstruction, dialog fit, and feedback states.

Treat 44px targets, 64px controls with small labels, 8px same-group height differences, 12px alignment drift, or more than two primary-looking actions as review prompts. They are deliberately conservative warnings, not universal pass/fail laws. Confirm them in the screenshot and DOM before editing.

## Applicable Design Context And Two Passes

Use design-context freezing only for new UI, significant reshaping, or design-system convergence—not for a precision fix or ordinary audit. Freeze theme, audience, the page's unique task, brand constraints, approved assets, real content, viewports, existing tokens/components, and protected pages; write `UNKNOWN/NOT_VERIFIED` instead of guessing.

First produce one compact plan for color roles, font roles, layout concept, and at most one memory point, with a requirement or approved-asset basis for each. Then perform a separate `keep/modify/reject` pass. Keep a candidate only when it preserves the approved master; otherwise map it back to existing tokens/components or reject it. This design judgment can recommend one direction but cannot create an audit PASS, and visual claims without fresh Browser evidence remain `NOT_VERIFIED`.
