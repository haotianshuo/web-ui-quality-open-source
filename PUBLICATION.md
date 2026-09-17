# Public source boundary

This repository is the Web UI Quality 4.3.1 Apache-2.0 source release for the
normal OSS release channel. Release archives are published on the
[project Releases page](https://github.com/haotianshuo/web-ui-quality-open-source/releases):

- repository: <https://github.com/haotianshuo/web-ui-quality-open-source>;
- release version: `4.3.1`;
- license for the release: Apache-2.0;
- PyPI/npm: not published.

The engineering review is closed for the distributed files in
[FINAL_PUBLIC_SOURCE_MANIFEST.json](FINAL_PUBLIC_SOURCE_MANIFEST.json):
`RIGHTS_BLOCKED = 0` and `NOT_CONFIRMED_DISTRIBUTED_FILES = 0`.

## Included

- the plugin manifest and project skill;
- the Python Runtime, schemas, public examples, and public tests;
- bounded security, scope, evidence, verification, and release documentation;
- reproducible source-package metadata and public CI configuration;
- the final file-level source manifest.

## Excluded

- ZIP/TAR recovery archives and duplicate historical package folders;
- ChatGPT/Codex/Claude records, browser profiles, LevelDB, caches, and virtual
  environments;
- the private `evolution/` ledger and external project worktrees/evidence;
- commercial EULA/template files and the commercial demo;
- historical private/commercial/experimental contract tests that require
  excluded evidence or non-public release identities;
- generated screenshots and inventory output that are not needed by the public
  runtime and are not verified for redistribution;
- generated audit outputs, credentials, and machine-specific paths.

## License history

The historical GitHub release `v4.3.0` is a separate MIT-licensed public
source snapshot at its recorded commit. It remains in Git history as a real
historical artifact. It was not rewritten as Apache-2.0. The current 4.3.1
release is the Apache-2.0 source line built from the 4.3.1 release baseline.

The root Apache license covers only the project-owned material included in
the current release. A third-party item, if ever included, keeps its own
license and required notice; the root license does not relicense it.

## Provenance and boundary rules

Every distributed file is classified in the final manifest as an allowed
engineering disposition. External issue and pull-request pages, commit
identifiers, URLs, and behavior descriptions are research evidence only. They
are not copied source and are not automatically dependencies or attributions.

Future additions must record the source, version or commit, license, and any
notice obligation before they are distributed. Do not add chat exports,
browser storage, credentials, local absolute paths, generated evidence,
external repository checkouts, or private audit material.

## Claim boundary

The public tests prove only the self-contained package contract. Commercial GA
remains `NOT_ESTABLISHED`; Real Host, External Blind Holdout, and Browser
qualification remain `NOT_MEASURED`. This release does not establish
production compatibility, model accuracy, or legal clearance of future additions.
