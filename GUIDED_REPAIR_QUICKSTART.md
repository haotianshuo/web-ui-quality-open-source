> Package: **4.3.0** · Package Stage: **4.3.0-open-source** · Trust Kernel: **4.2.3** · Kernel Base Lineage: **4.0.0-rc.1** · Receipt Protocol: **3.0** · Evidence Schema: **3.0**

# Guided repair quickstart

This example shows the order of a controlled repair. Use a disposable or
properly backed-up project until the Host and Browser environment has been
qualified for your use case.

## 1. Check the local entry point

```bash
python -B scripts/run_runtime.py --help
```

After installation, the equivalent entry point is:

```bash
web-ui-quality --help
```

## 2. Describe one bounded task

State the target page or component, the files that may change, and the files
that must not change. Inspection and explanation are read-only by default.

## 3. Review before writing

The Host reviews the diagnosis and exact Patch Candidate. Any write must be
bound to the approved scope and the current baseline. Runtime does not create
or persist the Host's write-authority secret.

## 4. Verify the result

Run the applicable project tools and Browser checks. Keep Before/After hashes,
drift results, coverage, and any unmeasured condition in the final TaskResult.
Do not call a repair verified merely because a source file changed or a
synthetic fixture passed.

