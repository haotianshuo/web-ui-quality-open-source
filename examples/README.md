# Examples

- `ui-inventory-demo/` shows a small local inventory input and output flow.
- `qualification-collection/` contains deterministic qualification fixtures;
  it is not a real-user or real-Host benchmark.
- `scope-drift-demo/` shows a bounded repair request together with the actual
  `NOT_VERIFIED` result and the project-drift gate that prevents an untrusted
  change from being reported as verified.

Run examples only against disposable local data unless you have separately
approved the project, Browser, and Host permissions they require. The examples
do not upload source or grant write authority by themselves.
