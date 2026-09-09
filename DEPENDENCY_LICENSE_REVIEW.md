# Dependency license review

This is a qualification record for the current `4.3.0-open-source` source
preview. It is not a runtime lockfile and it does not mean that these packages
are bundled in the Web UI Quality source archive or wheel. Runtime dependency
ranges remain in `pyproject.toml`.

The source package declares one required runtime dependency (`Pillow`) and
optional Browser, validation, test, and development extras. The build system
also uses `setuptools` and `wheel`. The following fixed versions were used for
the Python 3.12 qualification review on 2026-09-09.

| Package | Resolved version | Role | License expression | Compatibility / notice decision |
| --- | ---: | --- | --- | --- |
| Pillow | 12.3.0 | Direct runtime | MIT-CMU | Compatible; keep upstream notice if bundled |
| Playwright | 1.62.0 | Direct optional Browser | Apache-2.0 | Compatible; keep Apache notice if bundled |
| jsonschema | 4.26.0 | Direct optional validation | MIT | Compatible; keep upstream notice if bundled |
| pytest | 9.1.1 | Direct test | MIT | Compatible; keep upstream notice if bundled |
| build | 1.6.0 | Direct development | MIT | Compatible; keep upstream notice if bundled |
| setuptools | 84.0.0 | Direct build-system | MIT | Compatible; keep upstream notice if bundled |
| wheel | 0.48.0 | Direct build-system | MIT | Compatible; keep upstream notice if bundled |
| attrs | 26.1.0 | Transitive (`jsonschema`) | MIT | Compatible; keep upstream notice if bundled |
| colorama | 0.4.6 | Transitive (`build`, `pytest`) | BSD-3-Clause | Compatible; keep upstream notice if bundled |
| greenlet | 3.5.5 | Transitive (`playwright`) | MIT AND PSF-2.0 | Compatible; keep both notices if bundled |
| iniconfig | 2.3.0 | Transitive (`pytest`) | MIT | Compatible; keep upstream notice if bundled |
| jsonschema-specifications | 2025.9.1 | Transitive (`jsonschema`) | MIT | Compatible; keep upstream notice if bundled |
| packaging | 26.3 | Transitive (`build`, `pytest`, `wheel`) | Apache-2.0 OR BSD-2-Clause | Compatible; keep the selected upstream notice if bundled |
| pyee | 13.0.1 | Transitive (`playwright`) | MIT | Compatible; keep upstream notice if bundled |
| Pygments | 2.21.0 | Transitive (`pytest`) | BSD-2-Clause | Compatible; keep upstream notice if bundled |
| pyproject_hooks | 1.2.0 | Transitive (`build`) | MIT | Compatible; keep upstream notice if bundled |
| referencing | 0.37.0 | Transitive (`jsonschema`) | MIT | Compatible; keep upstream notice if bundled |
| rpds-py | 2026.6.3 | Transitive (`jsonschema`, `referencing`) | MIT | Compatible; keep upstream notice if bundled |
| typing_extensions | 4.16.0 | Transitive (`referencing`) | PSF-2.0 | Compatible; keep PSF notice if bundled |

The current public source and wheel contain no files from these distributions.
The dependency review is separate from redistributed-code provenance: a
package name, URL, issue number, or license string in project metadata does not
turn external research or a separately installed dependency into project-owned
source. Any future vendored or bundled material requires a new content-level
provenance decision and its own notice handling before release.
