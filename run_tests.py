#!/usr/bin/env python3
"""Public, self-contained test entry point.

The recovered multi-computer archive contains additional private acceptance
tests that depend on omitted evolution evidence, generated artifacts, or
optional Browser capability. The public command intentionally runs only the
tests under ``tests/public`` so its result is reproducible from this repository.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RUNTIME = ROOT / "runtime" / "python"


def main() -> int:
    tests_dir = ROOT / "tests" / "public"
    if not tests_dir.is_dir():
        print("public tests directory missing", file=sys.stderr)
        return 1

    try:
        import pytest  # noqa: F401
    except ImportError:
        print("pytest unavailable; internal tests cannot run", file=sys.stderr)
        return 1

    env_path = str(RUNTIME)
    completed = subprocess.run(
        [sys.executable, "-B", "-m", "pytest", str(tests_dir), "-q"],
        cwd=str(ROOT),
        env={**_env(), "PYTHONPATH": env_path},
        check=False,
    )
    return completed.returncode


def _env() -> dict[str, str]:
    import os

    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    return env


if __name__ == "__main__":
    raise SystemExit(main())
