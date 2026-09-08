# Test scopes

This repository contains two test scopes:

- `tests/public/` is the self-contained public release gate. Run `python -B
  -m pytest -q` or `python -B run_tests.py` from the repository root.
- The other files under `tests/` are recovered internal regression tests. Some
  require the optional Browser dependency, generated evidence, or the private
  `evolution/` ledger that is intentionally excluded from this public snapshot.

The internal tests are retained as provenance and engineering context. A
failure caused by an omitted private artifact or unavailable optional Browser
capability must not be reported as a public-release failure, and must not be
silently relabeled as a pass.
