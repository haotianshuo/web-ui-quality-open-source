> Package: **4.3.0** · Package Stage: **4.3.0-open-source** · Trust Kernel: **4.2.3** · Kernel Base Lineage: **4.0.0-rc.1** · Receipt Protocol: **3.0** · Evidence Schema: **3.0**

# Known limitations

These limits are part of the public claim boundary.

- Real Codex/Claude/other Host qualification is `NOT_MEASURED` in this
  snapshot. Package-local tests do not measure a Host model's repair accuracy.
- The included holdout and attack fixtures qualify mechanics and regression
  handling only. They are not a hidden external benchmark.
- Browser evidence needs a compatible Playwright driver and browser. A blocked
  or unavailable Browser remains unverified.
- Local route checks and process limits are not an operating-system sandbox or
  remote attestation. A hostile same-user process needs an external sandbox or
  ACL boundary.
- Large repositories may have partial global inventory. Exact target scope can
  be checked without claiming complete knowledge of every repository file.
- Screenshot masking is best effort. It is not universal recognition of names,
  balances, medical data, canvas pixels, or other visual personal data.
- A local digest or HMAC is tamper-evident under its stated local threat model;
  it is not independent signing or proof of the Host environment.
- The package does not claim universal maintainability, accessibility,
  performance, security, or business-outcome improvement.

