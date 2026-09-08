> Package: 4.3.0 · Package Stage: Commercial Stable · Trust Kernel: 4.2.3 · Kernel Base Lineage: 4.0.0-rc.1 · Receipt Protocol: 3.0 · Evidence Schema: 3.0

# Web UI Quality Security Response Policy

This policy describes how security reports for the Web UI Quality package are
handled. It does not authorize access to a customer system and does not replace
the customer’s incident-response plan.

## 1. Report privately

Submit a suspected vulnerability through the commercial order or distribution
channel that supplied the package, using its private security-reporting path.
If that channel supplies a repository security-advisory mechanism, use that
mechanism. Do not disclose secrets, live credentials, private customer data, or
an exploitable production payload in a public issue.

## 2. Useful report contents

Include the affected package version, Trust Kernel version, operating system,
runtime versions, a minimal reproduction, impact, attack preconditions, and
sanitized evidence. Include exact file names or gate identifiers where useful.
Keep the reproduction local and remove API keys, cookies, storage state, HMAC
keys, private URLs, and personal data.

## 3. Triage and containment

The Security owner records receipt, confirms scope, reproduces the report in an
isolated environment where possible, and assigns severity based on
confidentiality, integrity, availability, authority, and evidence impact. A
release or support response may include a workaround, a constrained deployment
recommendation, a patch, or a release hold. A Browser or Host boundary that was
not measured remains unverified during triage.

## 4. Disclosure

The Security owner coordinates a fix, affected-version assessment, release
notes, and disclosure timing with the reporter when feasible. Public disclosure
must not expose customer data or make unsupported claims about remote
attestation, Host-provider security, or business outcomes.

## 5. Release linkage

Security fixes are bound to the exact package version, packageTreeDigest,
Candidate ZIP SHA-256, and releaseRunId. A security response record cannot grant
human release approval; Legal, Privacy, Support, and Security owners must each
record their own approval before Commercial GA.

This policy is distributed with the package and requires manual Security owner
approval before Commercial GA.
