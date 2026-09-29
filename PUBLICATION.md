# Public source boundary

This is the Web UI Quality 4.4.0 Apache-2.0 source release for the normal
GitHub OSS channel.

- repository: <https://github.com/haotianshuo/web-ui-quality-open-source>;
- release version: `4.4.0`;
- license: Apache-2.0 for project-owned material only;
- PyPI/npm: not published.

The source manifest covers every file selected by the release packager. Its 576
non-self rows match the package paths, current byte counts, hashes, source
labels, and required attribution fields. The manifest itself is included in
the package but cannot contain a self-referential row. The 25 paths omitted by
the previous manifest were traced to their first-introduction commits in the
Web UI Quality repository and reviewed against preserved external project
snapshots. The 32 stale rows were compared with the previous main baseline;
their text matched after line-ending normalization, and their current byte
counts and hashes are now recorded.

`scripts/release.py validate` keeps technical validation separate from formal
source eligibility. The `package` command refuses to write release archives if
the manifest is absent, partial, malformed, incomplete, or out of date.

## Included

- the plugin manifest and user-facing Web UI Quality skill;
- the Python Runtime, mirrored schemas, public examples, and public tests;
- bounded product, security, verification, dependency, and release documents;
- the source manifest and reproducible source-package metadata.

## Excluded

- private `evolution/` records, business copies, browser profiles, screenshots,
  logs, caches, virtual environments, and machine-specific paths;
- commercial templates and demo material;
- historical private or commercial tests that depend on excluded evidence;
- generated audit outputs that are not part of the public Runtime.

## License history and third-party material

The historical `v4.3.0` MIT-licensed source snapshot and the previous `v4.3.1`
Apache-2.0 release remain unchanged. The current source line is Apache-2.0.
No third-party source code, fixtures, images, fonts, icons, browser binaries, or
model weights are bundled. Runtime, Browser, test, and build dependencies are
installed separately and retain their upstream licenses and notices if a
downstream distribution bundles them. See
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and
[DEPENDENCY_LICENSE_REVIEW.md](DEPENDENCY_LICENSE_REVIEW.md).

External project names, URLs, issue/PR identifiers, commit SHAs, and behavior
descriptions are research references; they are not copied source or automatic
attributions. Any future distributed third-party material requires a new
source, license, and notice review.

## Claim boundary

The source review is an engineering provenance record, not a statutory
copyright opinion, contributor assignment, patent clearance, or
non-infringement guarantee. No legal copyright-holder name is inferred from a
Git identity or account.

The bounded local operation record documents observed file changes and After
checks; it is not an independent Host attestation and does not enter the V3
verifier. Commercial GA, production qualification, and broad page-maturity
claims remain unestablished. Page-specific placeholder business operations
remain the responsibility of the host application.
