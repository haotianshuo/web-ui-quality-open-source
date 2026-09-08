> Package: 4.3.0 · Package Stage: Commercial Stable · Trust Kernel: 4.2.3 · Kernel Base Lineage: 4.0.0-rc.1 · Receipt Protocol: 3.0 · Evidence Schema: 3.0

# Web UI Quality Privacy Notice

This notice describes the local Web UI Quality package. It is not a notice for
the customer’s application, its end users, or the Host provider’s service.

## 1. What the package processes

When operated by a customer, the package may read project files, rendered page
content, Browser console and page-error observations, screenshots, UI geometry,
verification metadata, and files explicitly supplied by the customer. Evidence
may include paths, digests, redacted text, and diagnostic findings. The package
does not need a customer database or production dataset to perform its local
contracts.

## 2. Local-first boundary

The Runtime does not contain an OpenAI, Anthropic, or other Host-model client,
does not silently upload source, and does not silently install dependencies,
commit, push, deploy, or mutate production data. Browser and project-tool
actions are bounded by the local policy and Host authority described in
`SECURITY.md`. A Host or external service may apply its own data practices when
the customer chooses to send context to it; those practices are outside this
package notice.

## 3. Evidence and retention

The customer controls where reports, screenshots, receipts, and logs are stored
and how long they are retained. Evidence should be kept only for the release,
support, audit, or security purpose for which it was collected. Do not store
passwords, API keys, raw cookies, private keys, or unnecessary personal data in
project evidence. Local HMAC and digest checks provide tamper evidence under the
local process threat model; they are not remote attestation.

## 4. Redaction boundary

The package performs best-effort masking for common credential, token, email,
phone-like, and annotated sensitive DOM values. Masking is not universal
privacy recognition: arbitrary names, balances, medical data, canvas pixels,
or unannotated text may remain. Customers must review evidence before sharing
it and must mark additional sensitive regions when appropriate.

## 5. Customer responsibilities

The customer must establish a lawful basis for processing project and user data,
configure approved origins and Browser state, restrict access to evidence,
honor deletion and access obligations, and obtain any required consent. The
customer must not use a local report as proof of compliance for a separate
system without completing that system’s own review.

## 6. Requests and changes

Privacy questions and requests should be submitted through the commercial order
or distribution channel through which the package was supplied. Requests must
identify the package version and the relevant evidence or project scope without
including secrets. Material changes to this notice require Privacy owner review
before the corresponding package is marked GA.

This notice is distributed with the package and requires manual Privacy owner
approval before Commercial GA.
