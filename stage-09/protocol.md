# Stage 09 Protocol — GitHub Top-50 Design Philosophy Research

## Scope

This stage studies publicly visible GitHub projects and extracts transferable
design principles for a human-first universal agent. It is a research stage,
not a source-code, asset, or README-copying stage.

The execution target is the current conversation workspace. Any instruction
in the source execution document that asks for a new window is overridden by
the user's explicit request to execute here.

## Evidence rules

1. Record the retrieval date and the public source URL for every observation.
2. Paraphrase observations; do not copy source code, visual assets, or README
   wording.
3. Separate direct observations, design inferences, and `NOT_MEASURED` claims.
4. Do not claim exact Global Top-50 rank, adoption, maintenance health, or
   product behavior unless the current source directly exposes it.
5. Do not turn research into an implementation mandate. Any WUQ action must be
   expressed as a bounded decision or `DEFERRED`.
6. Keep the research deliverable to one file:
   `DESIGN_PHILOSOPHY_RESEARCH.md`.

## Three rounds

### Round 1 — Source and sample freeze

- Retrieve the official GitHub Trending source for the current day.
- Freeze a broad sample of current public projects relevant to agent, browser,
  verification, security, policy, adapter, and developer-tool workflows.
- Record source limitations before interpreting the sample.

### Round 2 — Philosophy extraction

- Classify each sample by its user-facing job and extensibility boundary.
- Extract recurring principles covering first success, installation,
  progressive disclosure, authority, recovery, evidence, cross-platform use,
  and maintenance.
- Mark all unsupported operational claims as `NOT_MEASURED`.

### Round 3 — Independent dedupe and WUQ mapping

- Re-read the sample and deduplicate principles that describe the same user
  outcome.
- Map only the smallest useful implications to WUQ's existing contract.
- Confirm that no source code, asset, README text, or unsupported rank claim was
  copied into the research deliverable.

## Completion gate

The stage is complete when `DESIGN_PHILOSOPHY_RESEARCH.md` contains the source
snapshot, classified sample, deduplicated principles, WUQ implications,
explicit non-measurements, and an integrity check with no source-code changes.
