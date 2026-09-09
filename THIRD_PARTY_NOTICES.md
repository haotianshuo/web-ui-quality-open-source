# Third-party notices

The source candidate does not vendor the packages below. This table records
the exact resolved qualification environment used for the Python 3.12
dependency/license review so that an installer or downstream packager knows
which upstream notices must remain attached if those packages are redistributed
with an installation. The source archive itself contains none of their source
files or license files.

Direct means declared by this project (including build and test extras);
Transitive means brought in by one of those declarations. The runtime model
continues to use version ranges in pyproject.toml; these versions are the
fixed qualification resolution, not a new runtime lockfile.

| Package | Resolved version | Role | License expression | Notice handling |
| --- | ---: | --- | --- | --- |
| Pillow | 12.3.0 | Direct runtime | MIT-CMU | Keep upstream license/notice if redistributed |
| Playwright | 1.62.0 | Direct optional Browser | Apache-2.0 | Keep Apache license/notice if redistributed |
| jsonschema | 4.26.0 | Direct optional validation | MIT | Keep upstream license/notice if redistributed |
| pytest | 9.1.1 | Direct test | MIT | Keep upstream license/notice if redistributed |
| build | 1.6.0 | Direct development | MIT | Keep upstream license/notice if redistributed |
| setuptools | 84.0.0 | Direct build-system | MIT | Keep upstream license/notice if redistributed |
| wheel | 0.48.0 | Direct build-system | MIT | Keep upstream license/notice if redistributed |
| attrs | 26.1.0 | Transitive (jsonschema) | MIT | Keep upstream license/notice if redistributed |
| colorama | 0.4.6 | Transitive (build, pytest) | BSD-3-Clause | Keep upstream license/notice if redistributed |
| greenlet | 3.5.5 | Transitive (playwright) | MIT AND PSF-2.0 | Keep both upstream license texts if redistributed |
| iniconfig | 2.3.0 | Transitive (pytest) | MIT | Keep upstream license/notice if redistributed |
| jsonschema-specifications | 2025.9.1 | Transitive (jsonschema) | MIT | Keep upstream license/notice if redistributed |
| packaging | 26.3 | Transitive (build, pytest, wheel) | Apache-2.0 OR BSD-2-Clause | Keep the selected upstream license/notice if redistributed |
| pyee | 13.0.1 | Transitive (playwright) | MIT | Keep upstream license/notice if redistributed |
| Pygments | 2.21.0 | Transitive (pytest) | BSD-2-Clause | Keep upstream license/notice if redistributed |
| pyproject_hooks | 1.2.0 | Transitive (build) | MIT | Keep upstream license/notice if redistributed |
| referencing | 0.37.0 | Transitive (jsonschema) | MIT | Keep upstream license/notice if redistributed |
| rpds-py | 2026.6.3 | Transitive (jsonschema, referencing) | MIT | Keep upstream license/notice if redistributed |
| typing_extensions | 4.16.0 | Transitive (referencing) | PSF-2.0 | Keep PSF license/notice if redistributed |

The detailed dependency graph, metadata expressions, license-file paths, and
SHA-256 values are retained in the private audit record
DEPENDENCY_LICENSE_CLOSURE.json. The table above is the public notice
boundary; it does not turn dependencies into project-owned Apache content.

## Research references are not third-party notices

External project names, URLs, issue/PR identifiers, commit SHAs, and behavior
hypotheses informed some detector and test design. They are not copied source,
not bundled dependencies, and not an attribution list. The content-level
review found no distributed upstream source, fixture, image, font, icon, or
screenshot. Future copied expressive material must retain its original notice
and receive a new provenance decision before it is merged.

