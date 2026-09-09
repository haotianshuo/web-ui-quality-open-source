> Package: **4.3.0** · Package Stage: **4.3.0-open-source** · Trust Kernel: **4.2.3** · Kernel Base Lineage: **4.0.0-rc.1** · Receipt Protocol: **3.0** · Evidence Schema: **3.0**

# Security

## Report a vulnerability privately

Please do not put a suspected vulnerability, exploit, credential, cookie,
storage state, private URL, or personal data in a public issue.

- Use [GitHub Private Vulnerability Reporting](https://github.com/haotianshuo/web-ui-quality-open-source/security/advisories/new)
  when it is available.
- Otherwise email `xrlcom@126.com` with the subject
  `Security report — web-ui-quality`.

`xrlcom@126.com` is a public project contact address only; it does not identify
the copyright holder.

Include the affected version, operating system/runtime, a minimal sanitized
reproduction, impact, and the relevant file or gate. We aim to acknowledge a
usable report within three business days; timing for a fix depends on severity
and reproducibility.

## Security boundary

- Runtime does not create write authority; the Host or user must authorize the
  applicable write and return the required receipt.
- Protected Scope, Before/After hashes, drift, coverage, and required checks
  remain separate from model reasoning.
- Browser route policy is exact and fail-closed for the request classes it
  governs. Local route enforcement is not an OS sandbox or remote attestation.
- Screenshot and DOM redaction is best effort, not universal visual-PII
  recognition.
- A missing Browser/Host capability remains `NOT_MEASURED` or unverified.
- A local digest or HMAC is tamper-evident under its stated local threat model;
  it is not independent signing.

The Apache source core and any future commercial support or enterprise service
are separate. A commercial service policy cannot reduce rights granted by the
Apache license for files actually included in this repository.
