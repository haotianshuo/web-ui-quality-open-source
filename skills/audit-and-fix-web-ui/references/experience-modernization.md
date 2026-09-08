# Experience Modernization Strategy

Use this module for broad modernization, user-experience-led upgrades, or requests that combine layout, interaction, visual, responsive, component, state, and workflow work.

## Required output

Create or consume `modernizationStrategy` before implementation. It must contain:

- eight capability centers with independent status and failure isolation;
- a user-value backlog split into now, next, and later;
- first-time, repeat-use, and recovery journeys;
- an applicable state matrix with reason, recovery, persistence, and accessibility;
- static, Browser, expert-review, and field-user evidence levels;
- protected business, write, dependency, and evidence boundaries.

Run:

```bash
python -B scripts/run_runtime.py modernization-plan <experience-core.json> <strategy.json>
```

The normal `experience-plan` flow creates this strategy automatically.

## Prioritization

Order work by frequency, user impact, and failure risk.

1. Fix task blockers, layout breaks, hidden state, data-loss risk, focus failures, and permission confusion.
2. Fix repeated friction, responsive degradation, slow feedback, visual inconsistency, and hard-to-scan density.
3. Improve maintainability and polish after the primary journeys are coherent.
4. Keep Hash, Receipt, and Schema stable as infrastructure; do not present them as the user-value center.

Every priority needs evidence, user impact, a repair, completion evidence, and a fallback or isolation boundary.

## Delivery loop

1. Ground the role, task, frequency, environment, risk, device priority, pain points, and success metric.
2. Route one dominant enterprise pattern and one compatible design DNA; preserve an established project language.
3. Implement the top user-value slice in the narrowest owning components.
4. Cover normal, loading, empty, no-result, error, permission, stale/conflict, unsaved, success, and long-content states when applicable.
5. Validate no more than three critical journeys per pass: first-time, repeat-use, and recovery.
6. Require same-environment Browser evidence before visual or interaction claims.
7. Require expert review before aesthetic completion and field/user data before outcome claims.

## Capability isolation

- Screenshot/Figma input may improve grounding but remains optional candidate evidence.
- Visual Studio edits serializable Design IR and must not write production source.
- Component recommendations are metadata and plans; do not install packages automatically.
- A failed optional provider returns its own unavailable or degraded status while Experience Core remains usable.
- A static, pixel, or schema pass cannot be promoted to Browser, expert, or field proof.

## Completion language

Use `PLAN_READY` only for a grounded, internally complete strategy. Use Browser, expert, and field evidence labels separately. Never use “completed modernization” when any required level is unverified.

