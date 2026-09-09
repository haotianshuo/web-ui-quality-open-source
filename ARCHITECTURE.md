> Package: **4.3.0** · Package Stage: **4.3.0-open-source** · Trust Kernel: **4.2.3** · Kernel Base Lineage: **4.0.0-rc.1** · Receipt Protocol: **3.0** · Evidence Schema: **3.0**

# Architecture

Web UI Quality is a control and evidence layer around an AI-assisted Web
change. The Host model understands the request and proposes implementation
ideas. Web UI Quality keeps the scope, authority, evidence, verification, and
claim boundary explicit.

## Main flow

```text
user goal
  -> protected scope and baseline
  -> diagnosis and patch candidate
  -> Host authorization and write receipt
  -> project-tool / Browser / drift / patch-quality checks
  -> bounded TaskResult
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

