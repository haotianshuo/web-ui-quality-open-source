#!/usr/bin/env python3
"""Public runtime entry for Web UI Quality 4.2.3.

This wrapper intentionally contains no business logic; it exposes the same
installed runtime entry used by the bundled Skill without requiring install.
"""
from __future__ import annotations
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "skills" / "audit-and-fix-web-ui" / "scripts" / "run_runtime.py"
if not TARGET.is_file():
    raise SystemExit(f"bundled runtime entry missing: {TARGET}")
runpy.run_path(str(TARGET), run_name="__main__")
