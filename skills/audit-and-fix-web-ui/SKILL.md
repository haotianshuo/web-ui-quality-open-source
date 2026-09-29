---
name: audit-and-fix-web-ui
description: "Inspect and improve real website and workbench UI: layout, typography, icon proportions, color roles, spacing, imagery, responsive composition and complete interactions. Use one natural-language run entry; ground repairs in real pages and project source, with Host-applied writes and honest verification."
---

# Web UI Quality 4.4.0

**唯一公共运行入口：** `python -B scripts/run_runtime.py ...`。Skill 内部脚本仅为实现细节，测试与文档不得绕开该入口。

> Current plugin/package: 4.4.0 · Current Trust Kernel: 4.2.3 · Kernel base: 4.0.0-rc.1 · Receipt protocol: 3.0 · Evidence schema: 3.0

## Default product entry

The product outcome is a coherent, polished, usable real page—not a successful audit report. For UI work, visual finish and task behavior are independent acceptance requirements. Scope/evidence controls protect the work; they are not its main deliverable. A narrow repair may leave unrelated areas unreviewed, but must not excuse visible defects in the selected surface as “non-blocking” merely because a button still works.

### Visual repair loop

For appearance, UI quality, imagery or responsive-layout requests, read [visual-density-and-design-system.md](references/visual-density-and-design-system.md) before proposing changes. For creating/replacing imagery also read [design-intelligence-and-builder.md](references/design-intelligence-and-builder.md).

1. Open the real target and inspect both the whole composition and the affected components. Bind the page/version/state to the source being changed; a preserved Before is not the latest delivery preview.
2. Use rendered measurements to locate risks, then inspect screenshots to judge grouping, optical icon size/centering, palette roles, hierarchy, whitespace and asset suitability. A DOM box or contrast pass does not establish visual quality.
3. Give each relevant candidate a concrete disposition: confirmed defect with evidence and owning source, intentional design with a reason, or unverified. Do not silently discard candidates outside the Top 3, or ask ordinary users to fill evidence JSON.
4. Fix the owning layout/component/token/asset in the authorized scope. For shared styles, identify and check affected representative pages; do not independently patch each occurrence or overwrite established brand decisions.
5. Reopen the same route/state at the applicable viewports. Review actual rendered results, including long labels and narrow widths. Continue targeted correction if confirmed visual defects remain; do not stop because tests, clicks or receipts pass.
6. Report separately: the specific defect outcome, visual finish of the reviewed surface, interaction completeness, and unreviewed scope. Host visual review is not user aesthetic approval and must never be recorded as such.

### Shared icon evidence and repair

- Measure and report three distinct references: decorative surface center, icon element-box center, and visible graphic bounds. A centered DOM box does not establish that the rendered graphic is centered. Alpha bounds, geometry bounds, and pixel centroids remain measurements; judge optical balance from the normal-size screenshot and use magnification only to locate artifacts.
- For a suspected cropped icon, bind the evidence to the exact resource actually used by that element, the CSS crop mechanism, computed size and position, selected crop/cell when measurable, and component selector. Do not label every PNG referenced from the same script as a sprite. An independently used PNG, brand mark, photograph, and content image remain counterexamples unless their own rendered use proves otherwise.
- Give the Host the selector, exact resource URL/path, crop details, and confirmed shared source owner when source mapping proves it. If the source file or call site cannot be confirmed, name the missing mapping evidence and do not guess an owner.
- Keep graphic scale, decorative backplate, and interactive hit area separate. Intentional transparent hit-area space and normal asymmetric icon geometry are not defects by themselves. A candidate or P2 label never makes a screenshot-confirmed defect optional; repair confirmed visible defects in the authorized scope.
- Prefer a pinned, licensed set of standalone vector icons for generic function glyphs when the project lacks a suitable vector source. Keep valid brand marks and content imagery intact, preserve replaced assets for rollback, and do not use overflow, pseudo-elements, per-icon offsets, or sprite crops to conceal damaged artwork.

For required photos, hero artwork, textured illustrations or generated bitmap assets, use the Host's available built-in image-generation tool by default. Do not substitute locally drawn SVG/CSS, geometric placeholders or a renamed raster export for requested generated imagery. Reuse suitable approved assets and established vector icon sets. If generation is unavailable, disclose that specific missing capability, retain existing assets, and never claim a generated asset was produced. The Runtime prepares evidence and guidance; the Host invokes generation and applies selected assets.

Use one entry:

```bash
python -B scripts/run_runtime.py run <URL-or-project> --request "<user request>"
```

The Host resolves exactly one mode:

| Mode | User meaning | Default boundary |
| --- | --- | --- |
| `CHECK` | 检查 | Read-only; show Top 3, retain all relevant findings for review |
| `FIX_AND_VERIFY` | 修复并验证 | Immutable Before, narrow Host-bound edit, matching After |
| `DEEP_REDESIGN` | 深度重设计 | Product discovery, one recommended direction with optional alternatives, hard stop for decision |
| `SPECIALIZED_AUDIT` | 专项验收 | Only the explicitly requested specialist scope |

`doctor` and `expert` remain advanced tools. `experience-fix`, `inspect`, `fix`, `redesign`, `audit`, and `ui-inventory` remain compatibility surfaces, not separate product models.

## Beta.5 Benchmark Trust & Corpus Qualification

For local projects, establish a file-indexed Project Baseline before repair evidence is sealed. Treat target-file drift as `REBASE_REQUIRED`, toolchain/config drift as `REVALIDATION_REQUIRED`, and truncated/unindexed coverage as `BASELINE_INCOMPLETE`. Reuse the ExperienceRun Before manifest/HMAC/ledger; do not create a parallel trust store.

For the normal `run` entry, use `--after-url` only to continue the latest matching `FIX_AND_VERIFY` run. Reuse the sealed session identity and require the exact `--host-write-receipt` bound to the persisted fix plan before local-project After verification.

If the user explicitly authorizes a bounded local-observation flow, keep it distinct from V3: pass `--local-operation` and an explicit `--file` scope; use `--related-run` for a new repair run when the discovery record is immutable, then use `--continue-run <run-id> --local-operation-prewrite-check` immediately before Host editing and `--continue-run <run-id> --after-url ...` for the exact same-run After. The Runtime records before/after hashes, a real diff, and the same-condition After, but this record never enters the Host-receipt validators and the repair remains `NOT_VERIFIED` for independent Host attestation. A task requiring V3 must fail closed; do not silently select local observation. If the discovery run's first-discovery seal covers a fix plan that would need replacement, preserve it and start one related repair run from the unmodified source using `--related-run`; this continues the known finding and is not a new discovery.

Unsupported production frameworks must return `FRAMEWORK_NOT_SUPPORTED` with no HTML fallback success. Persist relative project/artifact locations only.

When multiple findings map to one shared source, prefer `SYSTEMIC_ROOT_CAUSE`: one shared patch plus verification across affected surfaces. Do not “fix” the same shared defect independently at every call site.

Patch outcome and patch quality are separate gates. New `!important`, inline-style workarounds, hard-coded pixel growth, dependency-surface changes, or other deterministic debt signals must be surfaced as `QUALITY_RISK` even when screenshots improve.

Project-local `tsc`, `vue-tsc`, `eslint`, `vitest`, `jest`, and `stylelint` are project-owned code. Runtime may resolve/hash an allowlisted tool and prepare an exact Host-gated plan, but may not execute it autonomously or promote its stdout to independent trusted evidence.

Authenticated SaaS/CRM/admin targets are first-class. Authentication profiles are explicit user security decisions and may supply Playwright storage state plus allowed origins. Never copy storage-state credentials into the project or release artifacts.

Verification is budgeted by risk and impact. Targeted checks are preferred for narrow repairs; systemic/high-risk changes require representative plus integration verification. Mandatory PageHealth/EvidenceIntegrity checks are never budgeted away.

The default user-facing result is a Human Task Report adapted from TaskResult v1. CHECK/Inspection, Repair, and Modernization must all render a normal human result. Every public result carries explicit coverage; a Repair VERIFIED claim must never omit Patch/Target/Critical Context coverage. Keep resumability visible but hide internal run IDs from the normal human surface.

## Host reasoning contract and Relevant Context Packet

Do not create a Runtime persona or autonomous model layer. The Host model performs professional reasoning. Runtime should assemble bounded context: Goal, Protected Scope, relevant source refs, baseline state, evidence, current hypotheses/decisions, allowed actions, and verification boundary. Protected Scope, Host-only write/tool authority, and Claim Boundary are mandatory context and must never be trimmed by relevance/token budgets.

The Relevant Context Packet is a retrieval/context plan, not proof of root cause. If the true root source is absent from the packet, classify that as context/retrieval failure rather than silently blaming model reasoning.

## Whole-site UI Asset Inventory

When the user asks for “全站 UI 资产盘点 / 按钮统计 / 风格统计 / UI inventory”, keep the request in `SPECIALIZED_AUDIT` and run the dedicated read-only inventory instead of a generic source audit.

```bash
python -B scripts/run_runtime.py ui-inventory <URL> <output-dir> --project-root <project> --mode full
```

Collect rendered DOM + Computed Style for Button/Input/Card/Dialog/Table/Icon, Color/Typography/Radius/Spacing, source/runtime route coverage, component fingerprints, near-duplicate clusters, same-purpose Button drift, page profiles, screenshots, and existing CSS token comparison. Do not turn “different” into “wrong”, do not auto-refactor Design Tokens, and do not write project files from inventory.

## Authority

An explicit request such as “把这个问题修一下” may let the Host bind `NARROW_PROJECT_LOCAL_UI_EDIT` without asking the user the same question again. That scope is limited to the current task, confirmed finding, minimum local UI files, no dependency/API/permission/persistence change, no external transmission, and no deployment.

Runtime code, Python objects, JSON, HTML, cache, old receipts, and downloaded decision files cannot create authority. Runtime generates Patch Candidates only; Codex Host applies them and returns a hash-bound receipt. Any scope expansion requires a new Host decision.

## Immutable ExperienceRun

Every run writes:

```text
artifacts/<run-id>/
├── before/
├── after/
├── compare/
└── report/
```

A valid Before is sealed with per-file SHA-256, signed manifest and seal records, `baselineDigest`, `conditionsDigest`, task identity, target identity, and an append-only transition ledger. It is revalidated from disk before After, comparison, and reporting, and cannot be overwritten or rerun with the same `runId`. After requires the same task, target, baseline, role, auth/data state, locale, theme, reduced-motion setting, Browser, device conditions, Service Worker policy, origins, readiness rule, safe task, and feature flags. A source change created by the authorized repair is recorded as source lineage, not silently ignored.

## Page health before visual quality

Use this blocking order:

```text
RUNTIME_BROKEN
> AUTH_REQUIRED
> RESTRICTED_RENDER
> DATA_NOT_READY
> TASK_FAILED
> NOT_VERIFIED
> VISUAL_FINDINGS
> PASS
```

A clean screenshot cannot override a TypeError, authentication wall, unfinished skeleton, blocked core API/script/style/font, failed safe task, simulated preview, or missing Browser execution.

Readiness combines HTTP status, `document.readyState`, fonts, main content, visible text, skeleton/loading state, page errors, core requests, optional `readySelector`, and project-specific rules. `readySelector` may add certainty but cannot bypass errors.

## Standard device evidence

The sole standard matrix is:

- Mobile: `390×844`, touch, DPR 2, mobile mode
- Tablet: `768×1024`, touch, capability-derived DPR
- Desktop: `1440×900`, pointer, DPR 1

Generate both viewport and full-page screenshots. Use viewport evidence for fixed/sticky layers, dialogs, first-screen hierarchy and current tasks; use full-page evidence for long-page structure and truncation. Project breakpoints may be added but never replace the standard matrix.

## Browser safety

All safe A1 probes run through Mutation Firewall:

- allow policy-approved `GET`, `HEAD`, `OPTIONS`;
- block `POST`, `PUT`, `PATCH`, `DELETE`, Beacon, downloads, and external origins;
- treat WebSocket as blocked or inconclusive by policy.

Prefer unique reversible targets such as `details`, `aria-expanded`, tabs, and frontend-only accordions. Verify restoration. Report exactly: `PASS_RESTORED`, `FAIL_NO_STATE_CHANGE`, `FAIL_NOT_RESTORED`, `NOT_VERIFIED_NO_SAFE_TARGET`, or `BLOCKED_MUTATION_ATTEMPT`.

## Safe project launcher

Startup order is: reuse an existing user service → use a supplied URL → use an existing trusted static server → let the Host run an audited command in isolation → report not startable.

Before any package script, expand `pre<name>`, `<name>`, and `post<name>`, tokenize the shell, classify executable and arguments, and detect writes, downloads, networking and sandbox requirements. Never install or upgrade dependencies, run unknown downloads, kill unrelated processes, or change project configuration to make it start.

## Findings and repairs

Top 3 is ordered by task blockage, severity, viewport breadth, journey criticality, recovery cost, confidence, evidence quality, and regression risk—not hit count or pixel difference.

Every formal repair includes user impact, recommended repair, modern option, compatibility fallback, source scope, evidence refs, confidence, class, and a verification contract. Static heuristics such as fixed widths, `100vh`, `transition: all`, many `!important`, literal colors, high z-index, missing reduced motion, or excessive absolute positioning remain `REPAIR_HINT` until Browser/source/task evidence confirms a finding.

## Retry discipline

One stable issue key permits at most three recorded attempts:

1. `ROOT_CAUSE_MINIMAL_FIX`
2. `ALTERNATIVE_PATH`
3. `SCOPE_REDUCTION` or `FALLBACK`

A fourth attempt and a repeated strategy are forbidden. PASS, FAIL, and NOT_VERIFIED attempts are all recorded.

## Product discovery and redesign

Beta.3 retains the renderable Design IR tree and the Product, Route, Journey, Region, Component, and Interaction State model with explicit evidence classes and source/DOM/visual/runtime channels. Candidate generation supports 1–3 real choices; the compatibility default is three. Never manufacture extra choices merely to satisfy a count. Pairwise declared direction-contract difference is not rendered structural proof.

Discovery caches only bounded reports tied to project fingerprint, source scope, runtime/schema version, and input signature. It never caches authority, credentials, sensitive full source, Browser authority, or apply receipts.

Each answer round is a hard stop. Saving or correcting product understanding may only update the ledger and show the next question. Diagnosis, design, Browser work, and implementation require a new Host task scope.

Deep redesign may produce 1–3 evidence-bounded directions depending on real trade-offs; Conservative Repair, Journey Focused, and System Modernization remain available compatibility directions. Do not manufacture options or claim rendered structural difference unless render/candidate-IR evidence proves it. Every emitted direction must state target user, core problem, tradeoffs, validation method, and known risk.

## Browser-unavailable experience

Keep galleries usable without broken images or fabricated screenshots. Clearly separate “源码候选已生成” from “Browser 尚未验证”. A generic detached mockup is not an After product.

## Completion

A result is complete only when the requested repair is demonstrated on the real product. For visual work, confirmed alignment, icon, color-role, spacing, responsive or asset defects within the selected surface must be resolved or explicitly left unaccepted. Top 3 is presentation prioritization, not a cap on required repairs. Explain the result, changed scope, evidence and remaining limitations in plain language. Pretty reports, file count, page load, click success, and pixel difference are not outcome proof.


## Source Assurance

Only registered trusted parsers may produce syntax PASS. Python, JSON, TOML, bounded HTML and bounded CSS are supported. Readable JavaScript, TypeScript, Vue, Svelte, YAML, Markdown and other unsupported formats remain `NOT_VERIFIED`. Use the single command policy for Source Assurance and project startup; recursively inspect lifecycle and nested package scripts.

## Repair execution boundary

Map each Finding to Route, Selector, Component, Source File and Source Range. If source ownership is not confirmed, return `SCOPE_NOT_CONFIRMED` with `risk = UNKNOWN`. Runtime must not call project write or rollback functions. Generate a Patch Candidate, stop for Host application, verify the Host hash receipt, and then run the bound After.

For a `FIX_AND_VERIFY` task, complete the normal public `run` against the unmodified target first and review its sealed Before and repair plan before any Host write. If the plan lacks a confirmed source scope, let the Host map the reported evidence to the actual project source, then prepare a candidate against that recorded baseline. After the exact bound files are applied and receipted, continue the same run with its `--after-url` and Host receipt. Never start a post-edit run and present the edited project as its Before; if edits came first or the old run has no usable binding, preserve that history and begin a fresh isolated run from the unmodified source.

The primary `run --file` parameter is an explicit Host-confirmed source scope and takes precedence over inferred scope. Do not hand-edit a saved fix plan to inject a path. For local observation, bind the After to an exact `--continue-run` ID; never use “latest matching” to select a local record's run. Local operation records provide T1 file-state consistency only, do not authenticate the writer, and cannot satisfy the V3 Host receipt requirement.

When the user's request names a task outcome, preserve that outcome in the acceptance work even if the user's role is unknown. The rendered report's content-action inventory is a passive locator aid: it records visible controls, action markers, and whether a destination was declared, but it does not execute controls or prove their behavior. Use it to select the control relevant to the requested task, then inspect its visible result in the isolated project. A toast, pressed style, or click event alone is not task completion; verify the expected route or task state. Only activate actions whose effects are read-only or reversible and within the user's authorization. If effects are unknown or may mutate business state, leave the action unexecuted and report `NOT_VERIFIED` with the exact missing proof.

### Beta.3 product-evidence rules

- Project verification tools are Host-gated untrusted execution and default to `READ_ONLY_PROJECT`. Missing filesystem enforcement is NOT_VERIFIED; unexpected writes FAIL and block VERIFIED.
- Final Repair Verification consumes Browser, project tools, Patch Quality, project drift and Host write integrity. No lower-authority success may override unexpected project mutation.
- Default `run` output is the Human Task Report. Use `--json` for TaskResult v1 and `--expert-json` only for internal diagnostics.
- In CI, use `--ci`/`--require VERIFIED`; do not treat normal process completion as proof that the repair is VERIFIED.
For large repositories, distinguish global baseline completeness from exact patch-scope coverage. Project-local tool output enters verification only after Host result binding to the exact recorded plan and binary hash. `recommendedCandidate` is advisory; `selectedCandidate` remains null until the user/Host chooses.
