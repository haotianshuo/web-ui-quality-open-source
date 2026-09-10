# Stage 10 Result — Zero User-Managed Python Setup

Status: PASS_WITH_UNRESOLVED_IMPLEMENTATION
Stage objective status: PASS (direction selected; implementation deferred)
Baseline SHA: ea41be16dfb04c079d858de2f2ef9a08a7575ac8

## Round 1 — current baseline

The package metadata declares Python >=3.10, one runtime dependency
Pillow>=10,<13, and an optional Playwright extra. The public README currently
describes a source-checkout installation through python -m pip install -e .;
this is not a zero-user-managed-Python product path.

On Windows 11 with Python 3.12.10 x64, the source CLI help completed with exit
0. The global interpreter has neither setuptools nor wheel. A direct
no-build-isolation wheel probe therefore failed at setuptools.build_meta
import, with no wheel emitted. This is retained as an environment fact, not
silently converted to a package failure.

## Round 2 — isolated option probe

An isolated temporary venv was created without changing the global Python or
Node installation. Installing setuptools and wheel inside that venv allowed the
existing package to build a py3-none-any wheel:

- wheel: web_ui_quality-4.3.0-py3-none-any.whl
- size: 895086 bytes
- SHA-256: 20C663688C152DB4A2832A50190665D61CD6DAFF831AF799593FC175387A185E

A second isolated venv installed the wheel with dependencies deliberately
excluded for this packaging smoke test. The installed CLI help completed with
exit 0. pip uninstall completed with exit 0 and a following package lookup
reported not found. This proves a local package lifecycle, not a clean-machine
runtime with every optional dependency.

## Round 3 — repeatability

A fresh repeat venv installed the same wheel, repeated an upgrade request, ran
CLI help, and uninstalled the package. All lifecycle commands completed with
exit 0; the same-version upgrade was correctly a no-op. A version-changing
upgrade, persistent user data migration, signed binary, or attested release was
not measured.

## Option comparison

| Option | User-facing path | Main benefit | Main cost/risk | Evidence status |
|---|---|---|---|---|
| A — Core plus standalone executable | Download and run one platform executable | No user-managed Python after packaging | Per-OS binaries, larger artifact, signing, updater, crash/debug path | NOT_MEASURED; no executable prototype |
| B — bundled/embedded Python | Download a bundle containing runtime and Core | Predictable runtime and no Python prerequisite | Large security/update responsibility, platform builds, license and attestation review | NOT_MEASURED |
| C — small native bootstrapper plus existing Core | Download a small launcher; it provisions an isolated supported runtime and starts the existing Core | Smallest semantic change; preserves tested Core and can centralize checks | Bootstrap download, cache, permissions, rollback, signing and offline behavior need design | SELECTED DIRECTION; bootstrapper not implemented |
| D — gradual native migration | Keep compatibility path while moving pieces to native | Long-term reduction of Python dependence | Dual runtime and duplicated semantics during migration | DEFERRED; no migration evidence |
| E — Node rewrite as non-default | Add a Node path or rewrite the Core | May align with some Agent/Harness ecosystems | Reimplements result, scope, evidence, and authority semantics; requires new parity proof | DEFERRED; explicitly non-default |

## Decision

Select C as the simplest stable direction for the next authorized packaging
work. The selection is architectural, not a release claim: keep the Python Core,
put prerequisite discovery and isolated-runtime provisioning in a small
bootstrap layer, and make the bootstrap report its state before any task runs.
Do not implement the bootstrapper, change the Core language, or publish a
binary in this stage.

The local evidence supports package build/install/help/uninstall mechanics only.
It does not support “zero setup” for an end user yet.

## NOT_MEASURED

- Clean machine with no Python, no Node, no network, or no administrator rights.
- macOS and Linux installation, upgrade, uninstall, signing, attestation, and
  notarization.
- Windows Defender/SmartScreen, enterprise policy, offline bootstrap, proxy,
  rollback, and crash recovery.
- Full runtime with Pillow and Browser extras installed from a clean machine.
- Standalone executable, embedded runtime, or native bootstrapper artifacts.
- Download size, cold start, memory, and update duration for options A-E.
- License/notice implications of redistributing a runtime or native binary.

## Verification

- Source CLI help: exit 0.
- Initial global wheel attempt: failed because setuptools.build_meta was absent;
  no global package was installed.
- Isolated wheel build: exit 0.
- Isolated install/help/uninstall: exit 0 / 0 / 0.
- Repeat install/same-version upgrade/help/uninstall: exit 0 / 0 / 0 / 0.
- git diff --check: exit 0.
- WUQ source-code changes attributable to Stage 10: 0.
- Protocol SHA-256: 131CDB119A2265C72C08EC03B861A3114ACE871EEC7290BB0C08DAAAD0D9220C.

## Acceptance

- A-E are compared against the requested installation and maintenance metrics.
- The simplest direction supported by current evidence is selected: C.
- Missing clean-machine, other-OS, signing, and native-artifact evidence remains
  explicit and unresolved.
- No Core rewrite, authority expansion, expected/oracle change, or publication
  occurred.
