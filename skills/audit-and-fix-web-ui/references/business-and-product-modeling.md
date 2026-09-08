# Business And Product Modeling

## Model Before Recommending

Identify:

- entities such as customers, orders, files, tasks, messages, users, rewards, addresses, or agents;
- roles and visibility boundaries;
- operations such as view, search, filter, create, edit, upload, review, publish, retry, cancel, or delete;
- states including loading, empty, draft, pending, processing, complete, failed, cancelled, disabled, and permission denied;
- constraints such as required fields, edit windows, confirmation, reversibility, persistence, and cross-device synchronization.

Do not invent an enterprise rule when evidence is absent. Preserve approved terminology, field order, special review steps, administrator density, and documented exceptions unless they conflict with security, access, critical usability, responsive correctness, or accessibility baselines.

## Business Invariants

For an R2 plan record relevant routes, APIs, field semantics, roles and permissions, UI/business states, persistence, high-risk side effects, error/retry semantics, and synchronization. Any required change to an invariant is R3.

## Product Archetypes

Compose industry products from general archetypes: entity management, tasks/workflows, messaging, AI/agents, content feeds, commerce, media browsing, creation/editing, dashboards/admin, immersive experiences, maps/location, and personal service centers. Do not create industry-specific product logic without evidence.

## One Recommendation

For page, workflow, or full-productization work return one plan containing:

- business understanding and current framework;
- archetype and page modes;
- main problems, must-fix items, and recommended optimizations;
- enterprise differences and unverified items;
- one recommendation, selection reason, key tradeoffs, and rejected direction;
- intervention level, write risk, exact proposed scope, invariants, verification, and rollback boundary.

Common patterns may improve information architecture and interaction, but never overwrite user or enterprise business rules.
