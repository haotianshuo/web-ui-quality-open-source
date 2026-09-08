#!/usr/bin/env python3
"""Synchronize current 4.2.3 release/composite manifests from release.py.

This is a development/release helper. It does not create Host evidence and does
not change the final archive digest. The archive digest is written externally
by the packaging step.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "scripts" / "release.py"
SCHEMA_SYNC = ROOT / "scripts" / "sync_schema_bundle.py"


def main() -> int:
    subprocess.run([sys.executable, "-B", str(SCHEMA_SYNC)], cwd=ROOT, check=True)
    spec = importlib.util.spec_from_file_location("wuq_release_manifest_sync", RELEASE)
    if spec is None or spec.loader is None:
        raise SystemExit("unable to load release.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    written = []
    for name, data, _mode in module._entries():
        rel = Path(name)
        if len(rel.parts) == 2 and rel.name in {"RELEASE-MANIFEST.json", "COMPOSITE-RELEASE-MANIFEST.json"}:
            target = ROOT / rel.name
            target.write_bytes(data)
            written.append(rel.name)
    if len(written) != 2:
        raise SystemExit("release manifest generation did not produce both manifests")
    payload = {
        "status": "PASS",
        "packageVersion": module.PACKAGE_VERSION,
        "kernelVersion": module.KERNEL_VERSION,
        "kernelBaseVersion": module.KERNEL_BASE_VERSION,
        "written": sorted(written),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
