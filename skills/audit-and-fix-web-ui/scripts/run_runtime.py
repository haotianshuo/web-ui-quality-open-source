#!/usr/bin/env python3
"""Run the bundled Web UI Quality Runtime without installing the package."""

from __future__ import annotations

import sys
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[3]
RUNTIME_ROOT = PLUGIN_ROOT / "runtime" / "python"

for stream in (sys.stdin, sys.stdout, sys.stderr):
    reconfigure = getattr(stream, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8")

if str(RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(RUNTIME_ROOT))

from web_ui_quality.__main__ import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
