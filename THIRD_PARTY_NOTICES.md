# Third-party notices

This notice applies to the public Web UI Quality 4.3.0 source snapshot. It records
third-party software that may be installed separately; it is not a complete copyright,
provenance, trademark, or legal-clearance statement. The preparation boundary and
reference-only materials are described in [PUBLICATION.md](PUBLICATION.md) and
[NOTICE.md](NOTICE.md).

The selected package boundary does not intentionally vendor third-party source code,
model weights, browser binaries, JavaScript libraries, fonts, or component packages.
The project-owned status of every source file still requires the provenance review
described in the private audit report before any public redistribution.

Optional interoperability paths support separately installed software:

- Microsoft Playwright (Apache-2.0) for isolated rendered-page comparison.
- Pillow (HPND) for local image inspection and visual difference processing.
- Deque axe-core (MPL-2.0) when an operator supplies a local pinned script.
- Google Lighthouse (Apache-2.0) when an operator explicitly installs an executable.
- `jsonschema` (MIT) for optional full Draft 2020-12 meta-schema validation.

Design and component recommendations may reference publicly documented patterns or package metadata from Figma, W3C Design Tokens, Storybook, shadcn/ui, Radix UI, Base UI, React Aria, Headless UI, Ark UI, Mantine, Chakra UI, Ant Design, TDesign, Arco Design, Semi Design, daisyUI, Puck, GrapesJS, and Craft.js. No implementation from these projects is bundled or automatically installed. A recommendation does not imply endorsement, license approval, version approval, or permission to use a trademark.

Operators remain responsible for reviewing the exact version, license, notices, trademarks, transitive dependencies, and commercial terms of anything they choose to install in a target project.

The package metadata uses dependency ranges rather than a complete lockfile. Before a
release, resolve the exact dependency versions and archive their license and notice
information with the release evidence.
