# Web UI Quality

Verification and trust for AI-assisted Web changes.

Web UI Quality helps you check an AI-generated Web change before calling it
done: what the AI was allowed to change, what actually changed, what was
verified, and what is still unknown.

[![OSS Preview](https://img.shields.io/badge/status-OSS%20Preview-166B4F)](https://github.com/haotianshuo/web-ui-quality-open-source/releases)
[![Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
[![Public CI](https://github.com/haotianshuo/web-ui-quality-open-source/actions/workflows/ci.yml/badge.svg)](https://github.com/haotianshuo/web-ui-quality-open-source/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-yellow)](pyproject.toml)

## Quick Start

This repository contains the current Apache-2.0 open-source release
candidate. It is not published to PyPI yet, so install it from a source
checkout:

~~~bash
git clone https://github.com/haotianshuo/web-ui-quality-open-source.git
cd web-ui-quality-open-source
python -m pip install -e ".[browser]"
web-ui-quality doctor
~~~

The `[browser]` extra installs the Playwright driver. WUQ then uses an
installed Chrome, Edge, or Chromium executable when one is available. If
`doctor` reports `PYTHON_BROWSER_EXECUTABLE_MISSING`, install a browser binary
with `python -m playwright install chromium` (or install Chrome/Edge) and run
`web-ui-quality doctor` again. A missing driver and a missing browser
executable are reported as different reason codes (`PYTHON_PLAYWRIGHT_MODULE_MISSING`
versus `PYTHON_BROWSER_EXECUTABLE_MISSING`); neither status is Browser
verification evidence by itself.

To inspect a local Web project, describe the task in plain language:

~~~bash
web-ui-quality run ./path/to/your-web-project "检查结账页移动端布局，不要修改登录逻辑"
~~~

The default workflow is bounded and does not grant write authority. A repair
that needs a source change must receive the applicable Host write receipt and
current verification evidence before it can be reported as `VERIFIED`.

## What changed in this release

This release includes the boundary-hardening update from [PR #6](https://github.com/haotianshuo/web-ui-quality-open-source/pull/6), plus the visible auth/readiness fixes from PR #8 and PR #9:

- real-user intent routing keeps verification-only requests, scoped repairs,
  and conflicting instructions separate; write-capable repairs remain
  Host-gated;
- evaluator-side benchmark logic separates Host claims from sealed oracle
  results and classifies invalid setup and infrastructure failures
  conservatively;
- evidence graphs and provider envelopes fail closed on missing verification
  and empty evidence (`NOT_MEASURED`/`NOT_VERIFIED`), including the V2-F001
  resource-load regression;
- path, protected-scope, credential-redaction, and installation-identity
  checks make the source-only workflow more explicit;
- landscape mobile viewport coverage and the CLI `--version`/`doctor`
  diagnostics are included.

The update is covered by the public CI matrix and the full-tree regression
suite. Browser, Real Host, External Blind Holdout, Formal, and Commercial GA
qualification remain outside this source-only package; see
[KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md).

## Download the release candidate

The eventual normal-release archives belong on the [project releases page](https://github.com/haotianshuo/web-ui-quality-open-source/releases); this local candidate has not been uploaded by this task.
Each release includes `.zip` and `.tar.gz` source archives plus matching
`.sha256` and `.build.json` metadata. Verify the SHA-256 file before unpacking.
These archives are source distributions, not a PyPI/npm publication or a
production qualification.

## What WUQ verifies

WUQ keeps four questions separate:

~~~text
Scope → Change → Evidence → Verify
~~~

- Scope: which project and files are allowed to be considered;
- Change: what the Host actually applied;
- Evidence: what tests, tools, Browser, and before/after records really ran;
- Verify: whether the evidence is sufficient for the requested claim.

It does not silently install dependencies, upload source, commit, push, deploy,
or turn a model suggestion into write authority.

## One real local example

[`examples/scope-drift-demo/`](examples/scope-drift-demo/) is a small public
fixture for a bounded component repair. The request names one component file;
the companion file is deliberately outside that scope. Run the exact command
below from the repository root:

~~~bash
web-ui-quality run --json --ci --require VERIFIED --file component.html examples/scope-drift-demo "修复 component.html 里的保存按钮；不要修改 companion.txt"
~~~

The command records a real Before state and asks for `VERIFIED`. In a normal
source-only checkout it stops until a trusted Host applies the change and
returns the required evidence. If a Host changes the companion file outside
the approved scope, the project-drift gate keeps the result from becoming
`VERIFIED`. The example is a boundary demonstration, not a claim about model
accuracy or production behavior.

## Current status

The current source and release line is **Web UI Quality 4.3.1**, an Apache-2.0
correctness and reliability maintenance release candidate for the normal OSS
release channel. This local candidate has not been published to GitHub by this
task. The intended release page is the
[project releases page](https://github.com/haotianshuo/web-ui-quality-open-source/releases).
The historical `v4.3.0` release is a separate MIT-licensed source snapshot; it
is retained as history and is not the current 4.3.1 release line.

| Area | Status |
| --- | --- |
| Public source and engineering checks | PASS |
| License for the current release candidate | Apache-2.0 |
| PyPI/npm | Not published |
| Real Host qualification | `NOT_MEASURED` |
| External Blind Holdout | `NOT_MEASURED` |
| Commercial GA qualification | `NOT_ELIGIBLE` |

This release does not claim real Codex/Claude/other Host accuracy, real-user
benefit, production compatibility, universal accessibility, remote
attestation, or token savings. Missing Browser or Host evidence remains
unverified.

## Installation and useful commands

The installed command exposes these stable entry points:

~~~bash
web-ui-quality --help
web-ui-quality run --help
web-ui-quality doctor --help
web-ui-quality auth --help
~~~

For the self-contained public checks from a source checkout:

~~~bash
python -B run_tests.py
~~~

`--ci --require VERIFIED` is available for integrations that should fail when
the requested repair claim is not verified. It does not bypass Host approval,
scope checks, Browser requirements, or project-tool evidence.

## Repository map

- `runtime/python/web_ui_quality/` — Python Runtime and CLI;
- `skills/` — Codex skill instructions;
- `schemas/` — public JSON schemas;
- `examples/` — local fixtures and qualification inputs;
- `tests/public/` — tests intended to run from a clean checkout;
- `PUBLICATION.md` — public/private source boundary;
- `DEPENDENCY_LICENSE_REVIEW.md` — resolved dependency license decisions;
- `FINAL_PUBLIC_SOURCE_MANIFEST.json` — file-level source and license closure.

Private recovery records, chat history, browser storage, `evolution/`,
external worktrees, commercial templates, and commercial demo material are not
part of this public core.

## Release identity for tooling

The following compact identity block is kept for package and manifest checks;
it is not a product capability claim.

> Package: **4.3.1** · Package Stage: **4.3.1-open-source** · Trust Kernel: **4.2.3** · Kernel Base Lineage: **4.0.0-rc.1** · Receipt Protocol: **3.0** · Evidence Schema: **3.0**

## Security and contact

Please do not disclose a suspected vulnerability in a public issue. Use the
[GitHub Security Advisory form](https://github.com/haotianshuo/web-ui-quality-open-source/security/advisories/new)
or email `xrlcom@126.com` with the subject `Security report — web-ui-quality`.
Do not include passwords, API keys, cookies, storage state, private URLs, or
personal data in a report. For ordinary questions, open a GitHub issue.

The email address is a public project contact address; it is not a copyright-
holder declaration. See [LICENSE](LICENSE), [NOTICE.md](NOTICE.md), and
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for the licensing boundary.
