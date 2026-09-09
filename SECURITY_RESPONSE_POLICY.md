> Package: **4.3.0** · Package Stage: **4.3.0-open-source** · Trust Kernel: **4.2.3** · Kernel Base Lineage: **4.0.0-rc.1** · Receipt Protocol: **3.0** · Evidence Schema: **3.0**

# Security response policy

This policy covers the Apache source candidate. It does not authorize access to
a user's project or replace an incident-response plan.

## Intake

Use the GitHub Security Advisory form or email `xrlcom@126.com` with subject
`Security report — web-ui-quality`. Do not use a public issue for a vulnerability
or include live secrets and private customer data.
The address is a public project contact only and is not a copyright-holder
declaration.

## Triage

We record the affected version and environment, reproduce locally where
possible, and assess confidentiality, integrity, availability, authority, and
evidence impact. An unmeasured Browser or Host boundary remains unverified
during triage.

## Fix and disclosure

The response may include a workaround, a constrained deployment recommendation,
a patch, or a release hold. Disclosure timing is coordinated with the reporter
when practical and must not expose private data or imply unsupported Host,
provider, or remote-attestation guarantees.

## Release linkage

Security changes should identify the exact package version and package-tree
digest. A security record does not itself grant release approval; provenance,
privacy, security, and release checks remain separate decisions.
