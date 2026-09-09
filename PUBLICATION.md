# Public source boundary

This repository is an isolated Apache-2.0 source candidate for Web UI Quality
4.3.0. The engineering review is closed for the distributed files in
[FINAL_PUBLIC_SOURCE_MANIFEST.json](FINAL_PUBLIC_SOURCE_MANIFEST.json):
RIGHTS_BLOCKED = 0 and NOT_CONFIRMED_DISTRIBUTED_FILES = 0.

The candidate remains held from public GitHub release because
`PUBLIC_GITHUB_RELEASE = HOLD` is an explicit publication decision. The
copyright identity is `OPTIONAL_FUTURE_IDENTITY_DISCLOSURE`: no legal holder
name is asserted or inferred, but that optional future disclosure is not an
engineering or file-level rights blocker.

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
- the private evolution/ ledger and external project worktrees/evidence;
- commercial EULA/template files and the commercial demo;
- eight historical private/commercial/experimental contract tests that
  require the excluded evolution ledger or non-public release identities;
- generated `examples/ui-inventory-evidence/` screenshots and inventory
  output, which are not needed by the public runtime and are not verified for
  redistribution;
- generated audit outputs, credentials, and machine-specific paths.

## Provenance rules

Every distributed file is classified in the final manifest as one of the
allowed engineering dispositions: WUQ_ORIGINAL_CONFIRMED,
GENERATED_FROM_WUQ_CONFIRMED, THIRD_PARTY_APACHE_COMPATIBLE,
THIRD_PARTY_NOTICE_REQUIRED, REWRITE_INDEPENDENTLY, or an explicitly
documented reference-only disposition. A third-party code, text, fixture,
image, font, icon, or screenshot would keep its own license and notice; none
was found in this candidate's distributed content review.

External issue and pull-request pages, commit identifiers, URLs, and behavior
descriptions are research evidence only. They are not copied source and are
not automatically dependencies or attributions.

## History and claims

PUBLIC_HISTORY_STARTS_FROM_AUDITED_SOURCE_SNAPSHOT is intentional. Future
changes should be real commits with their tests and provenance notes. A passing
public test command proves only the self-contained test contract; it does not
prove ownership, third-party non-infringement, Browser/Host qualification, or
production outcomes.
