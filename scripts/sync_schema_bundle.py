#!/usr/bin/env python3
"""Synchronize the runtime schema bundle from the canonical public schemas/ tree.

`schemas/` is the single source of truth.  The runtime copy exists only because
installed packages need local schema resources.  This helper is deterministic,
never edits the canonical bundle, and supports a read-only `--check` release
mode.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "schemas"
RUNTIME = ROOT / "runtime" / "python" / "web_ui_quality" / "schemas"


def _bundle(directory: Path) -> dict[str, bytes]:
    return {path.name: path.read_bytes() for path in sorted(directory.glob("*.json"), key=lambda p: p.name)}


def _digest(bundle: dict[str, bytes]) -> str:
    h = hashlib.sha256()
    for name in sorted(bundle, key=lambda value: value.encode("utf-8")):
        h.update(name.encode("utf-8")); h.update(b"\0"); h.update(hashlib.sha256(bundle[name]).hexdigest().encode("ascii")); h.update(b"\n")
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Synchronize packaged runtime schemas from canonical schemas/")
    parser.add_argument("--check", action="store_true", help="read-only: fail if the runtime bundle differs from canonical schemas/")
    args = parser.parse_args()
    canonical = _bundle(CANONICAL)
    if not canonical:
        raise SystemExit("canonical schema bundle is empty")
    runtime = _bundle(RUNTIME)
    if args.check:
        if runtime != canonical:
            public_only = sorted(set(canonical) - set(runtime))
            runtime_only = sorted(set(runtime) - set(canonical))
            changed = sorted(name for name in set(canonical) & set(runtime) if canonical[name] != runtime[name])
            raise SystemExit(f"runtime schema bundle drift: publicOnly={public_only} runtimeOnly={runtime_only} changed={changed}")
        print(json.dumps({"status":"PASS","mode":"CHECK","schemas":len(canonical),"bundleDigest":_digest(canonical)},sort_keys=True))
        return 0
    RUNTIME.mkdir(parents=True, exist_ok=True)
    for path in RUNTIME.glob("*.json"):
        if path.name not in canonical:
            path.unlink()
    for name, data in canonical.items():
        (RUNTIME / name).write_bytes(data)
    print(json.dumps({"status":"PASS","mode":"SYNC","schemas":len(canonical),"bundleDigest":_digest(canonical)},sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
