> Package: **4.4.0** · Package Stage: **4.4.0-open-source** · Trust Kernel: **4.2.3** · Kernel Base Lineage: **4.0.0-rc.1** · Receipt Protocol: **3.0** · Evidence Schema: **3.0**

# Architecture

Web UI Quality helps the Host AI improve the visual finish and usability of
real websites and workbenches: layout, typography, icons, color roles, spacing,
imagery, responsive composition and complete interactions. The Host reasons
about observed pages and applies authorized source/asset changes. Runtime
measurements locate risks; qualitative review judges the actual composition.
Scope and evidence controls protect this loop rather than replace its outcome.

## Main flow

```text
user goal
  -> real page, project design context and protected baseline
  -> rendered risks and screenshot-based design judgement
  -> owning component / token / asset and repair candidate
  -> Host authorization and write receipt
  -> same-condition page, interaction and visual-finish review
  -> bounded TaskResult with separate defect and page-quality conclusions
```

The Runtime produces a candidate change; it does not silently grant itself
permission to write project files, install dependencies, commit, push, deploy,
or access production data. A Host or user must provide the applicable
authorization and return the evidence required by the task.

## Boundaries

- Protected Scope is separate from the source context used for diagnosis.
- Host write authority is separate from model reasoning.
- Before and After identity is bound to exact file hashes where applicable.
- A failed, missing, partial, or unmeasured check remains visible in the final
  result and cannot be converted into `VERIFIED` by a friendly explanation.
- A patch-scope result is not a whole-project result.

The package keeps compatibility adapters for older result shapes, but those
adapters do not create a second authority path.

