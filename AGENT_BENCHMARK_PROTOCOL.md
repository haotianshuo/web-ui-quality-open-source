> Package: **4.3.0** · Package Stage: **4.3.0-open-source** · Trust Kernel: **4.2.3** · Kernel Base Lineage: **4.0.0-rc.1** · Receipt Protocol: **3.0** · Evidence Schema: **3.0**

# Agent benchmark protocol

The benchmark code tests measurement mechanics, evidence binding, and failure
handling. It does not manufacture a Claude, Codex, Cursor, or other Host
accuracy score.

## Independent roots

A controlled run should keep the Host workspace, controller state, and sealed
evaluator material in separate roots. The Host must not choose the result
destination or read the expected answer. A same-user process can still escape
ordinary path separation, so hostile evaluation needs an external sandbox.

## Evidence levels

- Source contracts check deterministic file invariants.
- Executable contracts check a bounded local behavior.
- Browser contracts check a controlled fixture through Playwright.

When a required capability is unavailable, the result is explicitly
`NOT_MEASURED` or environment-blocked; source matching cannot be used as a
silent substitute.

## Claim boundary

Development fixtures, holdouts shipped with this package, and adversarial
probes qualify the controller and scorer. They do not establish real-world
model accuracy, user benefit, token savings, or production safety.

