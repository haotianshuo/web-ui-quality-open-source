> Package: 4.3.0 · Package Stage: Commercial Stable · Trust Kernel: 4.2.3 · Kernel Base Lineage: 4.0.0-rc.1 · Receipt Protocol: 3.0 · Evidence Schema: 3.0

# Web UI Quality Support Policy

This policy applies to supported use of Web UI Quality 4.3.0. Support is
provided through the commercial order or distribution channel used to supply the
package. The applicable order may define a different service level.

## 1. Supported scope

Support covers package installation, documented commands, package identity,
release evidence interpretation, Browser qualification boundaries, and
reproducible defects in the shipped Runtime under a supported Python, Node,
PowerShell, and Browser environment. Support does not include implementing a
customer application, repairing customer data, operating customer production,
or supplying a Host provider’s service.

## 2. How to submit a request

Provide the package version, operating-system and runtime versions, a concise
reproduction, the exact command, the relevant non-sensitive log excerpt, and
the release or task identifier. Remove credentials, cookies, tokens, personal
data, and private source before submission. For a security concern, use the
Security Response Policy instead of a public issue.

## 3. Priority

- Critical: a reproducible security issue, data-integrity risk, or release
  boundary failure that could authorize an unsafe action.
- High: a reproducible installation, release-gate, or supported-runtime failure
  that blocks a release or materially blocks a supported workflow.
- Normal: a reproducible defect with a documented workaround or a question
  about a documented capability.
- Informational: usage guidance, enhancement ideas, or unsupported environments.

The support channel acknowledges requests according to the applicable commercial
order. Priority is reassessed when new evidence changes impact or scope.

## 4. Support boundaries

Support personnel may request a sanitized reproduction or isolated diagnostic
run. They must not request customers to disclose secrets or to manually forge
Receipt, HMAC, digest, storage-state, or Host JSON files. A missing Browser,
Host authority, legal approval, or external qualification remains an explicit
boundary rather than a support PASS.

## 5. End of support and changes

Support follows the package lifecycle stated in the commercial order. Security
and release-blocking fixes may be issued independently of feature work. A
policy change requires Support owner review before it is used for a Commercial
GA release.

This policy is distributed with the package and requires manual Support owner
approval before Commercial GA.
