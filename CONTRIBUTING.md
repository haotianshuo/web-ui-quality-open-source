# Contributing

Please keep contributions easy to inspect and easy to remove.

1. Create a branch and make focused, real commits. Do not reconstruct or fake
   historical commits that were not preserved.
2. Run `python -B -m pytest -q` before opening a pull request. This is the
   self-contained public test suite selected by `pytest.ini`.
3. If you copy code or an asset from elsewhere, stop and record the exact source,
   version or commit, license, and required notice before adding it. An idea or
   documented behavior is not the same thing as copied source.
4. Never commit chat exports, browser storage, credentials, local absolute paths,
   generated evidence, external repository checkouts, or private audit material.
5. Keep claims honest: public tests do not certify Browser, Host, production, or
   legal qualifications that were not actually measured.

## Contact

For ordinary contribution questions, open a GitHub issue. For a private
security report, email `xrlcom@126.com` with the subject
`Security report — web-ui-quality`; do not include live secrets or private
customer data. This is a public project contact address, not a
copyright-holder declaration.
