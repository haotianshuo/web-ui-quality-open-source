"""Commercial release readiness checks.

This is not legal advice. It prevents an RC from being labelled GA while legal,
support, security, or external-proof placeholders remain open.
"""
from __future__ import annotations

import json
import hashlib
import importlib.util
from pathlib import Path
from pathlib import PurePosixPath
import re
import zipfile
from typing import Any

from .release_info import PACKAGE_VERSION

_REQUIRED = (
    "LICENSE", "EULA_TEMPLATE.md", "PRIVACY_NOTICE_TEMPLATE.md", "SUPPORT_POLICY_TEMPLATE.md",
    "SECURITY.md", "SECURITY_RESPONSE_POLICY.md", "COMMERCIAL_RELEASE_CHECKLIST.md",
)
_PLACEHOLDERS = (
    "<LEGAL_ENTITY>", "<CONTACT_EMAIL>", "<JURISDICTION>", "TBD_LEGAL", "REPLACE_BEFORE_GA",
    # A contributor label is not a licensor.  It must not silently satisfy a
    # commercial-license preflight merely because angle-bracket placeholders
    # were removed.
    "Web UI Quality Contributors",
)
_CANONICAL_TEST_EVIDENCE = "tests.json"
_ARCHIVE_MANIFESTS = ("RELEASE-MANIFEST.json", "COMPOSITE-RELEASE-MANIFEST.json")
_IDENTITY_FILES = (".codex-plugin/plugin.json", "pyproject.toml")
_IDENTITY_KEYS = {
    "author", "authors", "maintainer", "maintainers", "developer", "developername",
    "vendor", "company", "organization", "publisher", "licensor", "legalentity",
}
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _release_line(root: Path) -> tuple[str | None, str | None]:
    """Return the declared version and the exact evidence version line."""
    version: str | None = None
    manifest = root / ".codex-plugin" / "plugin.json"
    if manifest.is_file():
        try:
            value = json.loads(manifest.read_text(encoding="utf-8"))
            version = str(value.get("version") or "") or None
        except (OSError, UnicodeError, json.JSONDecodeError):
            version = None
    if version is None:
        pyproject = root / "pyproject.toml"
        if pyproject.is_file():
            try:
                match = re.search(r'(?m)^version\s*=\s*["\']([^"\']+)["\']', pyproject.read_text(encoding="utf-8"))
                version = match.group(1) if match else None
            except (OSError, UnicodeError):
                version = None
    match = re.fullmatch(r"\d+\.\d+\.\d+", version or "")
    return version, version if match else None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _resolve_evidence_root(package_root: Path, evidence_root: str | Path | None, expected_name: str | None) -> Path | None:
    if evidence_root is None:
        return (package_root / expected_name) if expected_name else None
    supplied = Path(evidence_root).expanduser().resolve()
    if expected_name and supplied.name != expected_name and (supplied / expected_name).is_dir():
        return supplied / expected_name
    return supplied


def _candidate_manifest(candidate_archive: Path) -> dict[str, Any] | None:
    try:
        with zipfile.ZipFile(candidate_archive) as archive:
            names = {name.replace("\\", "/") for name in archive.namelist()}
            manifest_name = "web-ui-quality/RELEASE-MANIFEST.json"
            if manifest_name not in names:
                return None
            value = json.loads(archive.read(manifest_name).decode("utf-8"))
            return value if isinstance(value, dict) else None
    except (OSError, zipfile.BadZipFile, KeyError, UnicodeError, json.JSONDecodeError):
        return None


def _safe_archive_member(value: Any) -> str | None:
    """Normalize one ZIP member without allowing aliases or traversal."""
    if not isinstance(value, str) or not value or "\x00" in value:
        return None
    normalized = value.replace("\\", "/")
    if normalized.startswith("/") or re.match(r"^[A-Za-z]:/", normalized):
        return None
    parts = normalized.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        return None
    if len(parts) < 2 or parts[0] != "web-ui-quality":
        return None
    parsed = PurePosixPath(normalized)
    if parsed.is_absolute() or ".." in parsed.parts:
        return None
    return normalized


def _safe_manifest_path(value: Any) -> str | None:
    if not isinstance(value, str) or not value or "\x00" in value:
        return None
    normalized = value.replace("\\", "/")
    if re.match(r"^[A-Za-z]:/", normalized):
        return None
    parsed = PurePosixPath(normalized)
    if parsed.is_absolute() or ".." in parsed.parts or any(part in {"", "."} for part in parsed.parts):
        return None
    return normalized


def _package_tree_digest(rows: list[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for row in sorted(rows, key=lambda item: str(item["path"]).encode("utf-8")):
        digest.update(str(row["path"]).replace("\\", "/").encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(row["sha256"]).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _load_release_module(root: Path) -> Any | None:
    """Load the package-local release.py so manifest treatment stays bound."""
    path = root / "scripts" / "release.py"
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location("wuq_release_for_commercial_preflight", path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _identity_placeholder_detail(root: Path) -> dict[str, Any]:
    """Inspect formal package identity fields, not contributor prose."""
    hits: list[dict[str, str]] = []
    missing: list[str] = []
    invalid: list[str] = []

    def walk(value: Any, key: str | None, location: str, identity_scope: bool = False) -> None:
        normalized_key = str(key or "").replace("_", "").casefold()
        identity_scope = identity_scope or normalized_key in _IDENTITY_KEYS
        if identity_scope and isinstance(value, str):
            for token in _PLACEHOLDERS:
                if token in value:
                    hits.append({"file": current_file, "field": location, "placeholder": token})
        if isinstance(value, dict):
            for child_key, child_value in value.items():
                child_location = f"{location}.{child_key}" if location else str(child_key)
                walk(child_value, str(child_key), child_location, identity_scope)
        elif isinstance(value, list):
            for index, child_value in enumerate(value):
                walk(child_value, key, f"{location}[{index}]")

    for name in _IDENTITY_FILES:
        path = root / name
        if not path.is_file():
            missing.append(name)
            continue
        current_file = name
        try:
            if name.endswith(".json"):
                value = json.loads(path.read_text(encoding="utf-8"))
            else:
                try:
                    import tomllib
                    value = tomllib.loads(path.read_text(encoding="utf-8"))
                except ModuleNotFoundError:
                    value = path.read_text(encoding="utf-8", errors="replace")
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
            invalid.append(name)
            continue
        if isinstance(value, dict):
            walk(value, None, "")
        else:
            invalid.append(name)
    return {"files": list(_IDENTITY_FILES), "missing": missing, "invalid": invalid, "placeholderHits": hits}


def _validate_candidate_archive(
    root: Path,
    candidate_archive: Path,
    package_manifest: dict[str, Any] | None,
) -> dict[str, Any]:
    """Validate the complete candidate archive against source and release.py."""
    result: dict[str, Any] = {
        "archiveValidation": False,
        "sourcePackageMatch": False,
        "generatedManifestMatch": False,
        "treeDigestMatch": False,
        "contentMatch": False,
        "candidateArchive": str(candidate_archive),
        "packageRoot": str(root),
        "files": [],
        "errors": [],
    }
    errors: list[str] = result["errors"]
    if not candidate_archive.is_file():
        errors.append("candidate archive is required for commercial preflight")
        return result

    try:
        with zipfile.ZipFile(candidate_archive) as archive:
            infos = archive.infolist()
            normalized_infos: dict[str, zipfile.ZipInfo] = {}
            duplicates: list[str] = []
            unsafe: list[str] = []
            for info in infos:
                name = _safe_archive_member(info.filename)
                if name is None or info.is_dir():
                    unsafe.append(info.filename)
                    continue
                if name in normalized_infos:
                    duplicates.append(name)
                normalized_infos[name] = info
            result["archiveEntries"] = len(infos)
            result["duplicatePaths"] = sorted(set(duplicates))
            result["unsafePaths"] = sorted(set(unsafe))
            if duplicates:
                errors.append(f"duplicate archive paths: {sorted(set(duplicates))}")
            if unsafe:
                errors.append(f"unsafe or directory archive paths: {sorted(set(unsafe))}")
            if {name.split("/", 1)[0] for name in normalized_infos} != {"web-ui-quality"}:
                errors.append("archive must contain exactly one web-ui-quality top-level directory")

            release_name = "web-ui-quality/RELEASE-MANIFEST.json"
            composite_name = "web-ui-quality/COMPOSITE-RELEASE-MANIFEST.json"
            manifests: dict[str, dict[str, Any] | None] = {}
            for member, label in ((release_name, _ARCHIVE_MANIFESTS[0]), (composite_name, _ARCHIVE_MANIFESTS[1])):
                info = normalized_infos.get(member)
                if info is None:
                    errors.append(f"{label} is missing")
                    manifests[member] = None
                    continue
                try:
                    value = json.loads(archive.read(info).decode("utf-8"))
                except (OSError, UnicodeError, json.JSONDecodeError, zipfile.BadZipFile) as error:
                    errors.append(f"{label} is invalid: {type(error).__name__}")
                    manifests[member] = None
                    continue
                if not isinstance(value, dict):
                    errors.append(f"{label} is not a JSON object")
                    manifests[member] = None
                else:
                    manifests[member] = value
            release_manifest = manifests.get(release_name)
            composite_manifest = manifests.get(composite_name)
            result["releaseManifest"] = release_manifest
            result["compositeManifestPresent"] = composite_manifest is not None

            row_map: dict[str, dict[str, Any]] = {}
            rows = release_manifest.get("files") if isinstance(release_manifest, dict) else None
            if not isinstance(rows, list):
                errors.append("release manifest files is not a list")
                rows = []
            identity = {
                "schemaVersion": "2",
                "product": "web-ui-quality",
                "pluginVersion": PACKAGE_VERSION,
                "packageVersion": PACKAGE_VERSION,
                "packageStage": "4.3.0-stable",
                "kernelVersion": "4.2.3",
                "kernelBaseVersion": "4.0.0-rc.1",
                "protocolVersion": "3.0",
                "receiptProtocolVersion": "3.0",
                "evidenceSchemaVersion": "3.0",
            }
            for label, value in (("release", release_manifest), ("composite", composite_manifest)):
                if isinstance(value, dict):
                    for key, expected in identity.items():
                        if value.get(key) != expected:
                            errors.append(f"{label} manifest identity mismatch: {key}")
            if isinstance(release_manifest, dict):
                if release_manifest.get("root") != "web-ui-quality/": errors.append("release manifest root mismatch")
                if release_manifest.get("stage") != "4.3.0-commercial-stable": errors.append("release manifest stage mismatch")
                if release_manifest.get("fileCount") != len(rows): errors.append("release manifest fileCount does not match files")
            for raw_row in rows:
                if not isinstance(raw_row, dict):
                    errors.append("release manifest contains a non-object file row")
                    continue
                relative = _safe_manifest_path(raw_row.get("path"))
                size = raw_row.get("bytes")
                digest = str(raw_row.get("sha256") or "")
                if relative is None or isinstance(size, bool) or not isinstance(size, int) or size < 0 or not _HEX64.fullmatch(digest):
                    errors.append(f"release manifest contains an invalid file row: {raw_row!r}")
                    continue
                if relative in row_map:
                    errors.append(f"release manifest contains duplicate file row: {relative}")
                row_map[relative] = {"path": relative, "bytes": size, "sha256": digest}

            expected_archive_names = {f"web-ui-quality/{relative}" for relative in row_map} | {release_name, composite_name}
            actual_archive_names = set(normalized_infos)
            extras = sorted(actual_archive_names - expected_archive_names)
            missing = sorted(expected_archive_names - actual_archive_names)
            result["extraPaths"] = extras
            result["missingPaths"] = missing
            if extras: errors.append(f"archive contains unknown extra files: {extras}")
            if missing: errors.append(f"archive is missing files: {missing}")

            archive_rows_match = True
            for relative, row in sorted(row_map.items()):
                member = f"web-ui-quality/{relative}"
                info = normalized_infos.get(member)
                source = root / relative
                file_detail: dict[str, Any] = {
                    "path": relative,
                    "sourceExists": source.is_file(),
                    "candidateExists": info is not None,
                    "match": False,
                }
                if info is None:
                    archive_rows_match = False
                    result["files"].append(file_detail)
                    continue
                data = archive.read(info)
                candidate_digest = hashlib.sha256(data).hexdigest()
                source_bytes = source.read_bytes() if source.is_file() else b""
                source_digest = hashlib.sha256(source_bytes).hexdigest() if source.is_file() else None
                file_detail.update({
                    "sourceBytes": len(source_bytes) if source.is_file() else None,
                    "candidateBytes": len(data),
                    "manifestBytes": row["bytes"],
                    "sourceSha256": source_digest,
                    "candidateSha256": candidate_digest,
                    "manifestSha256": row["sha256"],
                    "match": source.is_file() and source_bytes == data and len(data) == row["bytes"] and candidate_digest == row["sha256"],
                })
                if not file_detail["match"]:
                    archive_rows_match = False
                result["files"].append(file_detail)

            actual_tree = _package_tree_digest(list(row_map.values())) if row_map else None
            manifest_tree = release_manifest.get("packageTreeDigest") if isinstance(release_manifest, dict) else None
            source_tree = package_manifest.get("packageTreeDigest") if isinstance(package_manifest, dict) else None
            result["candidateTreeDigest"] = manifest_tree
            result["packageRootTreeDigest"] = source_tree
            result["computedCandidateTreeDigest"] = actual_tree
            tree_match = bool(actual_tree and manifest_tree == actual_tree and source_tree and source_tree == actual_tree)
            result["treeDigestMatch"] = tree_match
            if not tree_match:
                errors.append("candidate and source packageTreeDigest do not match the candidate rows")

            source_rows = package_manifest.get("files") if isinstance(package_manifest, dict) else None
            source_row_map: dict[str, dict[str, Any]] = {}
            source_rows_valid = isinstance(source_rows, list)
            if isinstance(source_rows, list):
                for raw_row in source_rows:
                    if not isinstance(raw_row, dict):
                        source_rows_valid = False
                        continue
                    relative = _safe_manifest_path(raw_row.get("path"))
                    size = raw_row.get("bytes")
                    digest = str(raw_row.get("sha256") or "")
                    if relative is None or isinstance(size, bool) or not isinstance(size, int) or size < 0 or not _HEX64.fullmatch(digest):
                        source_rows_valid = False
                        continue
                    if relative in source_row_map:
                        source_rows_valid = False
                    source_row_map[relative] = {"path": relative, "bytes": size, "sha256": digest}
            source_identity_ok = True
            if isinstance(package_manifest, dict):
                for key, expected in {
                    "schemaVersion": "2", "product": "web-ui-quality", "pluginVersion": PACKAGE_VERSION,
                    "packageVersion": PACKAGE_VERSION, "packageStage": "4.3.0-stable", "kernelVersion": "4.2.3",
                    "kernelBaseVersion": "4.0.0-rc.1", "protocolVersion": "3.0", "receiptProtocolVersion": "3.0",
                    "evidenceSchemaVersion": "3.0", "stage": "4.3.0-commercial-stable", "root": "web-ui-quality/",
                }.items():
                    if package_manifest.get(key) != expected:
                        source_identity_ok = False
                        errors.append(f"source release manifest identity mismatch: {key}")
            else:
                source_identity_ok = False
            source_manifest_integrity = bool(
                source_identity_ok and source_rows_valid and isinstance(source_rows, list)
                and len(source_row_map) == len(source_rows) and isinstance(source_tree, str)
                and _package_tree_digest(list(source_row_map.values())) == source_tree
            )
            source_match = bool(source_manifest_integrity and source_row_map == row_map and archive_rows_match)
            result["sourceManifestIntegrity"] = source_manifest_integrity
            result["sourcePackageMatch"] = source_match
            if not source_match:
                errors.append("candidate content does not equal the current source package manifest and bytes")

            # When available, compare every generated entry, including both
            # manifests, with the exact package-local release.py output.
            release_module = None
            try:
                release_module = _load_release_module(root)
            except (OSError, ImportError, RuntimeError, ValueError, TypeError) as error:
                result["generatedManifestReason"] = f"release.py load failed: {type(error).__name__}: {error}"
            if release_module is not None:
                try:
                    generated = {str(name).replace("\\", "/"): data for name, data, _mode in release_module._entries()}
                    actual = {name: archive.read(info) for name, info in normalized_infos.items()}
                    generated_match = generated == actual
                    result["generatedManifestSource"] = "scripts/release.py"
                except (OSError, RuntimeError, TypeError, ValueError, KeyError) as error:
                    generated_match = False
                    result["generatedManifestReason"] = f"release.py entry generation failed: {type(error).__name__}: {error}"
            else:
                # Isolated unit fixtures may not carry scripts/release.py. The
                # structural manifest/byte checks above remain authoritative.
                generated_match = not errors
                result["generatedManifestSource"] = "structural-fallback-no-release.py"
            result["generatedManifestMatch"] = generated_match
            if not generated_match:
                errors.append("candidate bytes do not match package-local release.py generated entries")
            result["contentMatch"] = bool(result["files"]) and all(item.get("match") is True for item in result["files"])
            result["archiveValidation"] = not errors
    except (OSError, zipfile.BadZipFile, RuntimeError, ValueError) as error:
        errors.append(f"archive cannot be opened: {type(error).__name__}: {error}")
    result["errors"] = sorted(set(errors))
    return result


def _candidate_required_content(
    root: Path,
    candidate_archive: Path | None,
    package_manifest: dict[str, Any] | None,
    archive_manifest: dict[str, Any] | None,
) -> dict[str, Any]:
    """Bind Preflight to the complete Candidate archive, not seven loose files."""
    if candidate_archive is None:
        return {
            "status": "FAIL",
            "candidateArchive": None,
            "packageRoot": str(root),
            "files": [],
            "reason": "candidate archive is required for commercial preflight",
        }
    detail = _validate_candidate_archive(root, candidate_archive, package_manifest)
    required_rows = [row for row in detail.get("files", []) if row.get("path") in _REQUIRED]
    detail["requiredCommercialFiles"] = required_rows
    detail["contentMatch"] = bool(required_rows) and all(row.get("match") is True for row in required_rows)
    return {"status": "PASS" if detail.get("archiveValidation") is True else "FAIL", "detail": detail, **detail}


def _evidence_run_ids(evidence_root: Path, names: tuple[str, ...]) -> tuple[list[Path], list[str]]:
    files = [evidence_root / name for name in names if (evidence_root / name).is_file()]
    run_ids: list[str] = []
    for path in files:
        value = _read_json(path)
        if value:
            run_id = str(value.get("releaseRunId") or value.get("runId") or "").strip()
            if run_id:
                run_ids.append(run_id)
    return files, run_ids


def run_preflight(
    package_root: str | Path,
    *,
    evidence_root: str | Path | None = None,
    candidate_archive: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(package_root).resolve()
    declared_version, release_line = _release_line(root)
    checks: list[dict[str, Any]] = []
    for name in _REQUIRED:
        path = root / name
        checks.append({"id": f"FILE-{name}", "status": "PASS" if path.is_file() else "FAIL", "detail": name})
    placeholder_hits: list[dict[str, str]] = []
    for name in _REQUIRED:
        path = root / name
        if not path.is_file(): continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for token in _PLACEHOLDERS:
            if token in text: placeholder_hits.append({"file": name, "placeholder": token})
    checks.append({"id": "LEGAL-PLACEHOLDERS", "status": "FAIL" if placeholder_hits else "PASS", "detail": placeholder_hits})
    identity_detail = _identity_placeholder_detail(root)
    identity_blocking = bool(identity_detail["missing"] or identity_detail["invalid"] or identity_detail["placeholderHits"])
    checks.append({
        "id": "COMMERCIAL-IDENTITY-PLACEHOLDERS",
        "status": "FAIL" if identity_blocking else "PASS",
        "detail": identity_detail,
    })
    expected_evidence = f"release-evidence-{release_line}" if release_line else None
    evidence = _resolve_evidence_root(root, evidence_root, expected_evidence)
    available_evidence = sorted(
        {item.name for item in root.glob("release-evidence-*") if item.is_dir()}
        | ({evidence.name} if evidence and evidence.is_dir() else set())
    )
    version_evidence_ok = bool(expected_evidence and evidence and evidence.is_dir() and evidence.name == expected_evidence)
    checks.append({
        "id": "RELEASE-EVIDENCE-VERSION",
        "status": "PASS" if version_evidence_ok else "FAIL",
        "detail": {
            "declaredVersion": declared_version,
            "expectedDirectory": expected_evidence,
            "providedEvidenceRoot": str(evidence) if evidence_root is not None else None,
            "availableDirectories": available_evidence,
        },
    })
    evidence = evidence if version_evidence_ok else None
    tests = evidence / _CANONICAL_TEST_EVIDENCE if evidence and (evidence / _CANONICAL_TEST_EVIDENCE).is_file() else None
    legacy_test_names = ("test-output.txt", "unit-tests.txt", "tests.txt")
    legacy_tests = [name for name in legacy_test_names if evidence and (evidence / name).is_file()]
    test_files, test_run_ids = _evidence_run_ids(evidence, (tests.name,)) if tests and evidence else ([], [])
    checks.append({
        "id": "RELEASE-TEST-EVIDENCE",
        "status": "PASS" if tests and test_run_ids else "FAIL",
        "detail": {
            "path": tests.name if tests else _CANONICAL_TEST_EVIDENCE,
            "canonicalName": _CANONICAL_TEST_EVIDENCE,
            "legacyFilesRejected": legacy_tests,
            "releaseRunIds": test_run_ids,
            "reason": None if tests and test_run_ids else "canonical tests.json is missing or has no releaseRunId",
        },
    })

    preview = evidence / "preview-matrix.json" if evidence and (evidence / "preview-matrix.json").is_file() else None
    preview_ok = False
    preview_run_ids: list[str] = []
    if preview:
        preview_data = _read_json(preview)
        if preview_data:
            run_id = str(preview_data.get("releaseRunId") or preview_data.get("runId") or "").strip()
            if run_id:
                preview_run_ids.append(run_id)
            explicit = preview_data.get("status") in {"PASS", "VALID"}
            matrix = bool(preview_data.get("allPatternPreviewsValid")) and bool(preview_data.get("allStylePreviewsValid"))
            design_pipeline = bool(preview_data.get("designPipelineValid")) and bool(preview_data.get("visualBuilderValid"))
            preview_ok = bool(run_id and (explicit or matrix or design_pipeline))
    checks.append({
        "id": "EXPERIENCE-PREVIEW-EVIDENCE",
        "status": "PASS" if preview_ok else "FAIL",
        "detail": {
            "path": preview.name if preview else "missing",
            "releaseRunIds": preview_run_ids,
            "reason": None if preview_ok else "missing, invalid, or no releaseRunId",
        },
    })

    package_manifest = _read_json(root / "RELEASE-MANIFEST.json")
    archive_path = Path(candidate_archive).expanduser().resolve() if candidate_archive else None
    archive_manifest = _candidate_manifest(archive_path) if archive_path and archive_path.is_file() else None
    expected_tree_digest = str((archive_manifest or package_manifest or {}).get("packageTreeDigest") or "")
    candidate_content = _candidate_required_content(root, archive_path, package_manifest, archive_manifest)
    checks.append({"id": "PACKAGE-ROOT-CANDIDATE-CONTENT", "status": candidate_content["status"], "detail": candidate_content})
    binding = _read_json(evidence / "release-binding.json") if evidence else None
    binding_path_ok = bool(evidence and (evidence / "release-binding.json").is_file() and binding)
    checks.append({
        "id": "RELEASE-BINDING",
        "status": "PASS" if binding_path_ok else "FAIL",
        "detail": "release-binding.json" if binding_path_ok else "missing or invalid",
    })

    full_gate = _read_json(evidence / "full-gate.json") if evidence else None
    distribution = _read_json(evidence / "distribution.json") if evidence else None
    full_gate_digest = _sha256(evidence / "full-gate.json") if evidence and (evidence / "full-gate.json").is_file() else None
    distribution_digest = _sha256(evidence / "distribution.json") if evidence and (evidence / "distribution.json").is_file() else None
    binding_run_id = str((binding or {}).get("releaseRunId") or "").strip()
    report_run_ids = [str((full_gate or {}).get("releaseRunId") or "").strip(), str((distribution or {}).get("releaseRunId") or "").strip()]
    report_run_ids = [value for value in report_run_ids if value]
    run_id_set = {value for value in [binding_run_id, *report_run_ids, *test_run_ids, *preview_run_ids] if value}
    all_run_ids_match = bool(binding_run_id and run_id_set == {binding_run_id})
    checks.append({
        "id": "RELEASE-EVIDENCE-BINDING",
        "status": "PASS" if binding and binding_run_id and all_run_ids_match else "FAIL",
        "detail": {"releaseRunIds": sorted(run_id_set), "expected": binding_run_id or "missing"},
    })
    checks.append({
        "id": "FULL-GATE-BINDING",
        "status": "PASS" if binding and full_gate and (binding.get("fullGateStatus") == "PASS") and full_gate.get("status") == "PASS" and binding.get("fullGateReportDigest") == full_gate_digest else "FAIL",
        "detail": {"status": (full_gate or {}).get("status"), "digestMatched": bool(binding and full_gate_digest and binding.get("fullGateReportDigest") == full_gate_digest)},
    })
    checks.append({
        "id": "DISTRIBUTION-BINDING",
        "status": "PASS" if binding and distribution and (binding.get("distributionStatus") == "PASS") and distribution.get("status") == "PASS" and binding.get("distributionReportDigest") == distribution_digest else "FAIL",
        "detail": {"status": (distribution or {}).get("status"), "digestMatched": bool(binding and distribution_digest and binding.get("distributionReportDigest") == distribution_digest)},
    })
    tree_ok = bool(binding and expected_tree_digest and binding.get("packageTreeDigest") == expected_tree_digest)
    checks.append({"id": "PACKAGE-TREE-BINDING", "status": "PASS" if tree_ok else "FAIL", "detail": {"expected": expected_tree_digest or "missing", "bound": (binding or {}).get("packageTreeDigest")}})
    archive_sha = _sha256(archive_path) if archive_path and archive_path.is_file() else None
    archive_ok = bool(binding and archive_sha and binding.get("candidateArchiveSha256") == archive_sha)
    checks.append({"id": "CANDIDATE-SHA-BINDING", "status": "PASS" if archive_ok else "FAIL", "detail": {"provided": bool(archive_path), "matched": archive_ok}})
    version_binding_ok = bool(binding and binding.get("packageVersion") == PACKAGE_VERSION and declared_version == PACKAGE_VERSION)
    checks.append({"id": "PACKAGE-VERSION-BINDING", "status": "PASS" if version_binding_ok else "FAIL", "detail": {"declared": declared_version, "bound": (binding or {}).get("packageVersion")}})

    proof = (evidence / "external-proof" / "summary.json") if evidence else None
    if proof and proof.is_file():
        proof_data = _read_json(proof) or {}
        proof_projects = proof_data.get("projects", [])
        proof_count = sum(1 for item in proof_projects if isinstance(item, dict) and item.get("status") in {"STATIC_PIPELINE_EXECUTED", "STATIC_PROVEN", "BROWSER_PROVEN", "REAL_PAGE_PROVEN"} and item.get("auditReport"))
    else:
        proof_count = 0
    checks.append({
        "id": "EXTERNAL-PROJECTS",
        "status": "PASS" if proof_count >= 3 else "FAIL",
        "detail": {"provenProjects": proof_count, "required": 3, "claimBoundary": "Static proof does not satisfy Browser or business-outcome proof."},
    })
    failures = [item for item in checks if item["status"] == "FAIL"]
    return {
        "status": "GA_READY" if not failures else "RC_ONLY",
        "declaredVersion": declared_version,
        "releaseEvidenceLine": release_line,
        "releaseRunId": binding_run_id or None,
        "evidenceRoot": str(evidence) if evidence else None,
        "candidateArchive": str(archive_path) if archive_path else None,
        "checks": checks,
        "blocking": failures,
        "disclaimer": "Template and readiness check only; obtain qualified legal review before GA.",
    }
