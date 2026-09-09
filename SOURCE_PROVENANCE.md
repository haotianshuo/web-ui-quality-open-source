# Source and provenance boundary

This candidate starts from one exact audited source snapshot. It is not a
reconstruction of the developer's multi-computer Git history and it does not
invent commits for versions that were not preserved.

The final distributed-file review is recorded in
[FINAL_PUBLIC_SOURCE_MANIFEST.json](FINAL_PUBLIC_SOURCE_MANIFEST.json).
For every file in that manifest, the engineering disposition is closed:

- RIGHTS_BLOCKED = 0;
- NOT_CONFIRMED_DISTRIBUTED_FILES = 0;
- third-party code/content disposition is either none or explicitly
  REFERENCE_ONLY_NOT_DISTRIBUTED_THIRD_PARTY_CODE;
- project-owned source is prepared for Apache-2.0 without changing a third
  party's license.

The evidence used for this engineering classification includes the preserved
source snapshot, historical candidate digests, file-tree and content
comparisons, the user-controlled WUQ development record, and manual review of
the files that mention external projects. These are provenance controls, not a
statutory copyright opinion, contributor assignment, patent clearance, or
non-infringement guarantee.

The user has explicitly confirmed the open-source intent and Apache-2.0 target.
The legal copyright-holder display name is intentionally not inferred from a
username, Git identity, local account, or contact email; it is tracked as
`OPTIONAL_FUTURE_IDENTITY_DISCLOSURE` and is not a general engineering
blocker.

External issue/PR pages, commit SHAs, URLs, and behavior descriptions remain
research references. The review found no distributed upstream source, fixture,
asset, screenshot, icon, or font. If a future change adds one, its original
license and required notice must be recorded before merge.

The boundary intentionally excludes private chat/session records, browser
storage, LevelDB, recovered archives, the private evolution/ ledger, external
project worktrees, commercial templates, and commercial demo material.
It also removes eight historical private/commercial/experimental contract
tests whose assumptions require those excluded materials or non-public release
identities; those files remain in the audit quarantine and are not distributed.
Generated `examples/ui-inventory-evidence/` screenshots and inventory output
are quarantined for the same reason: they are not required by the public
runtime and are not redistributed without separate content provenance.
