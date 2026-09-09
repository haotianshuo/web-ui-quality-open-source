#!/usr/bin/env python3
"""Build one immutable, source-bound Shadow Candidate.

The commercial package remains 4.3.0.  A Shadow Candidate is an external
candidate wrapper around the exact bytes produced by ``release.py``; it does
not change package authority, browser qualification, or Commercial GA state.
The output directory must be new so a later source tree can never silently
overwrite an earlier candidate.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime" / "python"
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))
RELEASE = ROOT / "scripts" / "release.py"
_CANDIDATE_VERSION = re.compile(r"^4\.4\.0-alpha\.\d+-shadow$")


def _load_release_module() -> Any:
    spec = importlib.util.spec_from_file_location("wuq_release_for_shadow_candidate", RELEASE)
    if spec is None or spec.loader is None:
        raise RuntimeError("release.py could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_exclusive(path: Path, data: bytes) -> None:
    with path.open("xb") as stream:
        stream.write(data)


def build(output_dir: str | Path, *, candidate_version: str, release_run_id: str) -> dict[str, Any]:
    """Build a deterministic candidate and return its binding record.

    ``output_dir`` is deliberately exclusive: an existing directory is a
    release-integrity failure, not a location to reuse.  The generated ZIP and
    TAR contain only the canonical package entries; ``candidate-build.json``
    stays outside the package as a sidecar binding record.
    """
    if not _CANDIDATE_VERSION.fullmatch(candidate_version):
        raise ValueError(f"unsupported Shadow Candidate version: {candidate_version}")
    run_id = str(release_run_id).strip()
    if not run_id:
        raise ValueError("release_run_id must be non-empty")

    output = Path(output_dir).expanduser().resolve()
    if output.exists():
        raise FileExistsError(f"Shadow Candidate output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)

    release = _load_release_module()
    release._validate_identity()
    entries = release._entries()
    archive_audit = release._audit_entries(entries)
    zip_data = release._zip_bytes(entries)
    tar_data = release._tar_bytes(entries)
    if zip_data != release._zip_bytes(entries) or tar_data != release._tar_bytes(entries):
        raise RuntimeError("Shadow Candidate archive reproducibility check failed")

    entry_map = {name: data for name, data, _mode in entries}
    release_manifest_name = f"{release.PRODUCT_NAME}/RELEASE-MANIFEST.json"
    composite_manifest_name = f"{release.PRODUCT_NAME}/COMPOSITE-RELEASE-MANIFEST.json"
    try:
        manifest = json.loads(entry_map[release_manifest_name].decode("utf-8"))
        composite = json.loads(entry_map[composite_manifest_name].decode("utf-8"))
    except (KeyError, UnicodeError, json.JSONDecodeError) as error:
        raise RuntimeError("generated package manifests are unavailable or invalid") from error
    if not isinstance(manifest, dict) or not isinstance(composite, dict):
        raise RuntimeError("generated package manifests must be JSON objects")
    if manifest.get("packageTreeDigest") != composite.get("packageTreeDigest"):
        raise RuntimeError("generated package manifests disagree on packageTreeDigest")

    stem = f"{release.PRODUCT_NAME}-{candidate_version}-candidate"
    zip_path = output / f"{stem}.zip"
    tar_path = output / f"{stem}.tar.gz"
    digest_path = output / f"{stem}.sha256"
    build_path = output / "candidate-build.json"
    output.mkdir()
    _write_exclusive(zip_path, zip_data)
    _write_exclusive(tar_path, tar_data)
    digests = {
        zip_path.name: {"bytes": len(zip_data), "sha256": _sha256_bytes(zip_data)},
        tar_path.name: {"bytes": len(tar_data), "sha256": _sha256_bytes(tar_data)},
    }
    digest_text = "".join(f"{row['sha256']}  {name}\n" for name, row in sorted(digests.items()))
    _write_exclusive(digest_path, digest_text.encode("utf-8"))

    record: dict[str, Any] = {
        "schemaVersion": "1",
        "artifactType": "web-ui-quality-shadow-candidate",
        "candidateVersion": candidate_version,
        "releaseRunId": run_id,
        "packageVersion": release.PACKAGE_VERSION,
        "packageStage": release.PACKAGE_STAGE,
        "kernelVersion": release.KERNEL_VERSION,
        "kernelBaseVersion": release.KERNEL_BASE_VERSION,
        "releaseStage": release.RELEASE_STAGE,
        "sourceRoot": str(ROOT),
        "sourcePackageTreeDigest": manifest.get("packageTreeDigest"),
        "packageTreeDigest": manifest.get("packageTreeDigest"),
        "manifestFileCount": manifest.get("fileCount"),
        "archiveEntryCount": len(entries),
        "archiveDirectory": str(output),
        "candidateArchive": str(zip_path),
        "candidateTarGz": str(tar_path),
        "digestFile": str(digest_path),
        "archiveDigests": digests,
        "manifestDigests": {
            "RELEASE-MANIFEST.json": _sha256_bytes(entry_map[release_manifest_name]),
            "COMPOSITE-RELEASE-MANIFEST.json": _sha256_bytes(entry_map[composite_manifest_name]),
        },
        "archiveAudit": archive_audit,
        "archiveValidation": "PASS",
        "reproducible": True,
        "independentQualification": "NOT_MEASURED",
        "promotionAllowed": False,
        "promotionDecision": "HOLD",
        "claimBoundary": "This sidecar binds one deterministic local Shadow Candidate to one current source package tree. It does not prove independent archive qualification, Browser/Host qualification, project runtime success, or Commercial GA.",
    }
    _write_exclusive(build_path, (json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    return record


def main() -> int:
    from web_ui_quality.release_info import configure_stdout

    configure_stdout()
    parser = argparse.ArgumentParser(description="Build one immutable source-bound Shadow Candidate")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--candidate-version", required=True)
    parser.add_argument("--release-run-id", required=True)
    args = parser.parse_args()
    try:
        result = build(
            args.output_dir,
            candidate_version=args.candidate_version,
            release_run_id=args.release_run_id,
        )
    except (FileExistsError, OSError, RuntimeError, ValueError, SystemExit) as error:
        print(json.dumps({"status": "FAIL", "error": str(error)}, ensure_ascii=False))
        return 1
    print(json.dumps({"status": "PASS", **result}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
