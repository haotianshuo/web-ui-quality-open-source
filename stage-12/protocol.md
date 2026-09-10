# Stage 12 Protocol — Real Host Pilot

## Scope

The execution instruction requires a pilot of 5-10 real Host tasks with a
stable model, permission profile, project, control/treatment assignment,
request, output, source diff, verification, and receipt evidence.

The current conversation is the requested execution location, but a local Core
or a harness-shaped wrapper is not automatically a Real Host. A pilot result
may be promoted only when the Host identity, model, permission boundary,
tool-call trace, source write, and post-write verification are directly
observable.

## Evidence rules

1. Do not label local CLI/Core probes as Real Host.
2. Do not synthesize user labels, treatment assignments, model calls, receipts,
   or source diffs.
3. All write-capable cases must remain Host-gated and fail closed until an
   actual Host authority object is available.
4. Preserve the five-to-ten task pilot schema even when its fields are
   NOT_MEASURED.
5. A missing external Host is an evidence gap, not permission to relax the
   boundary.

## Pilot record

Each pilot row needs:

- host and harness identity;
- model and permission profile;
- project and fixed task request;
- Control/Treatment assignment;
- input, output, tool trace, source diff, verification and receipt;
- failure/recovery state and claim boundary.

## Three rounds

### Round 1 — pilot freeze

- Freeze a six-task matrix spanning inspect, explain, verify-only, security
  visibility, repair mapping, and a Host-gated write request.
- Check required Host fields and capability prerequisites.

### Round 2 — bounded local probes

- Run the same requests through local Core functions and harness-shaped
  wrappers only to verify routing and fail-closed boundaries.
- Label every result LOCAL_CORE_ONLY.

### Round 3 — promotion audit

- Check whether any row has a real Host identity, model call, permission
  handshake, tool trace, source diff, and receipt.
- Promote nothing when those fields are absent; run boundary regression and
  record NOT_MEASURED.

## Completion gate

The stage is complete as an evidence decision. A PASS requires 5-10 fully
observed Real Host rows. Otherwise the stage closes as NOT_MEASURED with the
exact missing inputs and a preserved pilot matrix.
