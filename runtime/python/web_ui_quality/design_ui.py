"""Optional local UI adapters for structured Web UI Quality results.

The workflow does not depend on this module.  Core validation and JSON
artifacts remain usable when no UI is requested; this module only owns the
filesystem boundary for rendering an optional human-facing surface.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any


def render_design_ui(
    report: Mapping[str, Any],
    gallery_dir: str | Path,
    *,
    html_renderer: Callable[[Mapping[str, Any]], str],
    brief_renderer: Callable[[Mapping[str, Any]], str],
) -> dict[str, str]:
    """Render the optional decision UI without adding a runtime dependency.

    Renderers are injected so the core report builder does not own UI file
    layout or host integration.  A future Codex host adapter can replace this
    boundary without changing candidate validation or report generation.
    """
    root = Path(gallery_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    (root / "index.html").write_text(html_renderer(report), encoding="utf-8")
    (root / "executive-decision-brief.md").write_text(brief_renderer(report), encoding="utf-8")
    return {
        "status": "RENDERED",
        "artifact": "design-gallery/index.html",
        "brief": "design-gallery/executive-decision-brief.md",
        "command": "web-ui-quality design-ui <upgrade-output>",
    }
