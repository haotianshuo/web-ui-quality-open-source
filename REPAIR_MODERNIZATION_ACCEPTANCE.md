> Package: **4.3.0** · Package Stage: **4.3.0-open-source** · Trust Kernel: **4.2.3** · Kernel Base Lineage: **4.0.0-rc.1** · Receipt Protocol: **3.0** · Evidence Schema: **3.0**

# Repair and modernization acceptance

The acceptance contract is about trustworthy completion, not about making a
change look successful.

- Existing project failures remain baseline state.
- Authentication and protected files remain explicit decisions.
- Runtime cannot self-authorize writes or project-tool execution.
- Project-tool failure or `NOT_VERIFIED` cannot be hidden by Browser evidence.
- Unexpected drift blocks a verified claim.
- Resume restores workflow state but not write authority.
- Partial repository coverage remains visible.
- Design directions are proposals; a declared direction is not proof of a
  rendered structural difference.

The deterministic fixture and attack suites qualify the mechanics of these
rules. They do not measure real Host-agent repair accuracy or production
outcomes.

