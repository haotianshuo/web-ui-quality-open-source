> Package: **4.3.0** · Package Stage: **4.3.0-open-source** · Trust Kernel: **4.2.3** · Kernel Base Lineage: **4.0.0-rc.1** · Receipt Protocol: **3.0** · Evidence Schema: **3.0**

# Web UI Quality

Web UI Quality is a safety and evidence layer around AI-assisted Web changes.
It helps a Host model understand a request while keeping scope, permissions,
write receipts, verification, and unknowns visible.

This directory is the isolated Apache-2.0 4.3.0 source candidate. Engineering
provenance review is closed for every distributed file listed in
[FINAL_PUBLIC_SOURCE_MANIFEST.json](FINAL_PUBLIC_SOURCE_MANIFEST.json): no
distributed file is classified as NOT_CONFIRMED or RIGHTS_BLOCKED.
The project uses **Web UI Quality contributors** only as a neutral publisher
display label; it is not a legal copyright-holder assertion. The legal holder
name is intentionally not inferred from an account or contact address and is
recorded as `OPTIONAL_FUTURE_IDENTITY_DISCLOSURE`. This is an engineering
closure record, not legal advice.

PUBLIC_GITHUB_RELEASE = HOLD remains in force. This local candidate has not
overwritten the existing public repository, created a new public release, or
been published to PyPI/npm.

## What it provides

- bounded goals and protected file scope;
- Host-gated writes and immutable write receipts;
- Before/After hashes, drift detection, and coverage-aware results;
- optional Browser and project-tool evidence with fail-closed boundaries;
- deterministic schemas, tests, release manifests, and audit-friendly output;
- Codex-compatible plugin metadata and skills.

## Install and try it

Python 3.10 or newer is required.

~~~bash
python -m pip install -e .
web-ui-quality --help
~~~

To run the self-contained public checks from a source checkout:

~~~bash
python -B run_tests.py
~~~

The optional Browser extra installs the Python Playwright driver. A compatible
browser executable and a suitable Host environment are still required for
Browser or Host evidence.

## How a repair is controlled

~~~text
request
  -> goal, protected scope, and baseline
  -> diagnosis and patch candidate
  -> Host authorization and write receipt
  -> applicable project-tool / Browser / drift checks
  -> bounded TaskResult
~~~

Inspection and explanation are read-only by default. The Runtime does not
silently install dependencies, upload source, commit, push, deploy, mutate
production data, or turn a model suggestion into write authority.

## Evidence boundaries

The public tests prove only the self-contained package contract. This snapshot
does not claim real Codex/Claude/other Host accuracy, real-user benefit,
production compatibility, remote attestation, universal accessibility, or
token savings. Browser qualification and Real Host qualification remain
NOT_MEASURED unless an external, reproducible run supplies the required
evidence. Consequently this candidate is not a Commercial GA claim.

## Repository map

- runtime/python/web_ui_quality/ — Python Runtime and CLI;
- skills/ — Codex skill instructions;
- schemas/ — public JSON schemas;
- examples/ — small local examples and qualification fixtures;
- tests/public/ — checks intended to run from a clean checkout;
- NOTICE.md and THIRD_PARTY_NOTICES.md — ownership display and dependency boundary;
- PUBLICATION.md, SOURCE_PROVENANCE.md, and FINAL_PUBLIC_SOURCE_MANIFEST.json — source and release boundary.

Private recovery records, chat history, browser storage, evolution/,
external worktrees, commercial templates, and commercial demo material are
not part of this public core.

## Open-source and commercial boundary

The project-owned source files in this candidate are intended to be released
under Apache License 2.0. Apache covers only the project-owned material that
is actually included; it does not grant trademark rights or imply endorsement.
Any future commercial support or enterprise service is a separate offering and
cannot use an EULA to take away rights granted by Apache for this core.

See [TRADEMARKS.md](TRADEMARKS.md), [LICENSE](LICENSE), and
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Security reports

Please do not disclose a suspected vulnerability in a public issue. Use the
[GitHub Security Advisory form](https://github.com/haotianshuo/web-ui-quality-open-source/security/advisories/new)
or email xrlcom@126.com with the subject Security report — web-ui-quality.
Do not include passwords, API keys, cookies, storage state, private URLs, or
personal data in the report.

## Contact

For ordinary project questions, open a GitHub issue. For private security
reports, use the route above or xrlcom@126.com. This is a public project
contact address, not a copyright-holder declaration.
