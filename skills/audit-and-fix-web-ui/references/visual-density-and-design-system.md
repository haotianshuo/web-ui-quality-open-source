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

Judge the requested surface against these concrete questions, not a universal beauty score:

- **Composition and alignment:** do headings, labels, metrics and actions share intentional baselines? Does available width fit real content without orphaned short labels or shrinking everything?
- **Icons:** distinguish the hit target, decorated backing surface, icon box and visible ink. Check optical size/centering, sprite-cell padding, image transparency and consistency with adjacent text. Enlarging every touch target's glyph is not a general fix.
- **Color:** separate brand, action, status, surface and text roles. Check dominant color balance, surface separation, muted-text legibility and state meaning against the existing product. Contrast compliance alone does not prove a harmonious palette; arbitrary color counts do not prove a defect.
- **Space and grouping:** distinguish space within a component, between repeated components and between sections. Adjacent rounded cards with almost no gap may visually merge; a deliberate flat divided list is a valid different composition. Avoid solving every grouping problem with extra borders and shadows.
- **Images:** assess task fit, style, crop, resolution, aspect ratio and visible quality. File extension, alpha occupancy and image-generation provenance do not by themselves establish good imagery.
- **Responsive finish:** choose a useful arrangement at each width. Verify real long content, not only overflow=0. Short labels need not always be single-line, but unintended fragmentary wrapping is not accepted as a finished composition.

For each confirmed defect record the owning shared style/component/asset, the intended change and how the After will demonstrate it. Recheck affected pages when that owner is shared. Preserve deliberate differences between page types.

Heuristic P2/P3 is a discovery priority, not permission to ignore a confirmed visual defect. Review it against the actual request. “It still clicks” is not a visual acceptance reason. Use the existing visual-review contract for explicit Host/human judgement; do not synthesize scores or claim approval without viewing the relevant images. Missing image viewing remains unreviewed.

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
