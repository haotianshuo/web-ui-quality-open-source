# Modern UI Experience Fusion

Use this reference for any page redesign, UI modernisation, interaction improvement, responsive redesign, or visual-system task.

## Order of work

1. Build the Business Experience Model.
2. Route to one modern page pattern.
3. Select or explicitly override one visual direction.
4. Generate the interaction and state contract.
5. Generate and operate the interactive preview.
6. Only then implement the target project.
7. Iterate in a real Browser and evaluate task outcomes.
8. Use Safe Edit and audit controls as guardrails, not as the design source.

## Required completeness

A feature is not complete when it only has a schema or a report field. It must have:

- real input;
- deterministic decision logic;
- user override;
- usable output;
- fallback;
- interactive demonstration where applicable;
- automated test;
- explicit limit;
- acceptance criteria.

## Modern feature rule

Prefer current standards such as Container Queries, View Transitions, OKLCH, Popover, and Anchor Positioning only when they improve the task and have a fallback. Never use new CSS merely to appear modern.

## Visual rule

Build a complete semantic visual system. Do not scatter arbitrary hex values, shadows, radii, or animations. Dynamic material belongs to navigation and control layers; dense content uses stable surfaces.

## Outcome rule

Do not call a redesign improved because pixels changed. Measure task time, steps, errors, responsive quality, state coverage, visual preference, and project consistency. Without qualitative review, return only `IMPROVEMENT_CANDIDATE`.


## v2.1 primary rule

Route one page skeleton, emit only selected component/interaction/state assets into the main plan, and keep the complete catalog in a separate artifact. Always surface visible layout repair and project-token compatibility before recommending decorative changes.
