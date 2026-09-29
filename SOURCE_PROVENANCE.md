# Source and provenance boundary

The 4.4.0 release's source manifest covers the exact file set
selected by `scripts/release.py`: 577 non-self rows and 578 package inputs
including the self-excluding source manifest. Paths, byte counts, hashes,
provenance labels, license fields, classification reasons, and source
comparison records match the files that the packager will include.

The 25 paths missing from the previous manifest are four Runtime modules, two
validation scripts, and nineteen tests. Git history traces each to a
first-introduction commit in this Web UI Quality repository. Content review
found project-specific Runtime and test code; no third-party attribution or
license header was omitted. Against the preserved external project snapshots,
25 per-file content signatures and 28 additional long-line signatures had no
matches. No exact whole-file match was found in those snapshots.

The 32 rows whose old byte counts or hashes were stale were compared with the
previous `main` source. Their text matched after normalizing line endings;
the byte differences reflected line-ending representation, not new source
content. The rows now record the committed package bytes and hashes. `.gitattributes`
pins distributed text to LF in Windows checkouts while preserving the 24 files
already committed with CRLF or mixed line endings byte-for-byte. The remaining
source rows retain their previously reviewed provenance details.
No third-party source code or assets are included; separately installed
dependencies keep their upstream licenses and notices if redistributed.

The source manifest and packaging checks enforce different facts: the manifest
records source and license review, while the packager independently checks
coverage, recognized provenance labels, required row fields, byte counts, and
hashes. A technical validation PASS does not by itself establish source
eligibility. Missing, partial, malformed, unknown, or stale source records
block formal packaging.

This is an engineering review of the distributed source boundary. It is not a
statutory copyright opinion, contributor assignment, patent clearance, or
non-infringement guarantee. The legal copyright-holder display name remains
optional and is not inferred from a username, Git identity, local account, or
contact email.

Private chat/session records, browser storage, recovered archives, the private
`evolution/` ledger, business copies, screenshots, external project
worktrees, commercial templates, and commercial demo material are outside the
release package. This pass reviewed the preserved project snapshots named in
the source comparison; it did not scan unrelated local worktrees for material
to redistribute.
