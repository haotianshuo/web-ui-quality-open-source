# Public release notes

This is the first clean public source snapshot of Web UI Quality 4.3.0. The
maintainer publishes the project-authored source in this repository under the
MIT License.

## What is included

- the Codex plugin manifest and project-owned skill;
- the Python runtime, schemas, examples, and public tests;
- security, scope, evidence, and verification documentation needed to use the
  runtime responsibly;
- a reproducible public-package boundary and a fresh public release history.

## What is intentionally excluded

- recovered ZIP/TAR archives and duplicate historical package folders;
- ChatGPT, Codex, Claude, browser-profile, LevelDB, and other private records;
- external challenge worktrees, downloaded upstream repositories, and raw
  external evidence;
- the private `evolution/` ledger and its source-specific evidence rows;
- local caches, virtual environments, generated release evidence, absolute local
  paths, credentials, and machine-specific configuration.

## Provenance handling

The public tree was copied from the audited package boundary and then rebuilt
as a separate clean snapshot. The preparation audit found no exact whole-file
SHA-256 matches and no normalized long-line matches between the public project
skill and the saved reference snapshots for the external skill material that
was reviewed. That is useful evidence of separation, but it is not a legal
opinion or a guarantee about every historical edit.

The saved Matt Pocock skills repository was treated as a reference for
engineering ideas only; its source files are not included here. The local skill
copies found in the review bundle had no usable license metadata and were also
not included. See [NOTICE.md](NOTICE.md) for reference and dependency notes.

## History policy

The original work was developed across several computers and does not retain a
trustworthy complete Git history. This repository therefore starts with a clean
public baseline instead of inventing per-version commits. Future changes should
be real, small commits, with tests and provenance notes where relevant. The
private audit repository remains the place for unreleased recovery material.

## Claim boundary

Passing the public test command proves only the self-contained tests in this
repository. It does not prove Browser availability, Host-model accuracy,
production compatibility, ownership of material outside this tree, or legal
clearance of future additions.
