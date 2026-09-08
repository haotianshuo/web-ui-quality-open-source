#!/usr/bin/env python3
"""Evaluate final 4.3.0 machine eligibility for one exact Candidate ZIP.

This is an eligibility evaluator, not a release approver.  It never emits
``APPROVED_FOR_GA`` or ``COMMERCIAL_GA`` and it never treats one Browser
runtime as evidence for another.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from pathlib import PurePosixPath
import re
import sys
import zipfile
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime" / "python"
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))
EXPECTED_VERSION = "4.3.0"
EXPECTED_EVIDENCE_ROOT = "release-evidence-4.3.0"
EXPECTED_GATE_COUNT = 33
EXPECTED_IDENTITY = {
    "schemaVersion": "2",
    "product": "web-ui-quality",
    "pluginVersion": EXPECTED_VERSION,
    "packageVersion": EXPECTED_VERSION,
    "packageStage": "4.3.0-stable",
    "kernelVersion": "4.2.3",
    "kernelBaseVersion": "4.0.0-rc.1",
    "protocolVersion": "3.0",
    "receiptProtocolVersion": "3.0",
    "evidenceSchemaVersion": "3.0",
}
EXPECTED_PREFLIGHT_CHECK_IDS = {
    "FILE-LICENSE", "FILE-EULA_TEMPLATE.md", "FILE-PRIVACY_NOTICE_TEMPLATE.md",
    "FILE-SUPPORT_POLICY_TEMPLATE.md", "FILE-SECURITY.md", "FILE-SECURITY_RESPONSE_POLICY.md",
    "FILE-COMMERCIAL_RELEASE_CHECKLIST.md", "LEGAL-PLACEHOLDERS", "COMMERCIAL-IDENTITY-PLACEHOLDERS", "RELEASE-EVIDENCE-VERSION",
    "RELEASE-TEST-EVIDENCE", "EXPERIENCE-PREVIEW-EVIDENCE", "RELEASE-BINDING",
    "RELEASE-EVIDENCE-BINDING", "FULL-GATE-BINDING", "DISTRIBUTION-BINDING",
    "PACKAGE-TREE-BINDING", "PACKAGE-ROOT-CANDIDATE-CONTENT", "CANDIDATE-SHA-BINDING",
    "PACKAGE-VERSION-BINDING", "EXTERNAL-PROJECTS",
}
EXPECTED_DISTRIBUTION_CHECK_IDS = {f"DIST-{index:03d}" for index in range(1, 9)}
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_VALID_EXTERNAL_PROJECT_STATUSES = {
    "STATIC_PIPELINE_EXECUTED",
    "STATIC_PROVEN",
    "BROWSER_PROVEN",
    "REAL_PAGE_PROVEN",
}
_TEST_EVIDENCE_NAMES = ("tests.json",)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _safe_relative_path(value: Any) -> str | None:
    if not isinstance(value, str) or not value or "\x00" in value:
        return None
    normalized = value.replace("\\", "/")
    if normalized.startswith("/") or re.match(r"^[A-Za-z]:/", normalized):
        return None
    parts = normalized.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        return None
    parsed = PurePosixPath(normalized)
    if parsed.is_absolute() or ".." in parsed.parts:
        return None
    return normalized


def _load_release_module() -> Any:
    path = ROOT / "scripts" / "release.py"
    spec = importlib.util.spec_from_file_location("wuq_release_for_ga_validation", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("release.py could not be loaded for package validation")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _expected_source_rows() -> tuple[list[dict[str, Any]], str]:
    """Derive the expected package content from the current source packager."""
    release = _load_release_module()
    rows: list[dict[str, Any]] = []
    for path in release._files():
        data = path.read_bytes()
        rows.append({
            "path": path.relative_to(ROOT).as_posix(),
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        })
    return rows, release._package_tree_digest(rows)


def _validate_candidate_archive(path: Path) -> dict[str, Any]:
    """Validate archive bytes, exact file set, manifests, and source composition."""
    result: dict[str, Any] = {"status": "FAIL", "errors": [], "manifest": None, "packageTreeDigest": None}
    errors: list[str] = result["errors"]
    if not path.is_file():
        errors.append("archive is missing")
        return result
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            normalized_infos: dict[str, zipfile.ZipInfo] = {}
            for info in infos:
                name = _safe_relative_path(info.filename)
                if name is None:
                    errors.append(f"unsafe archive path: {info.filename!r}")
                    continue
                if info.is_dir():
                    errors.append(f"directory entry is not allowed: {name}")
                if name in normalized_infos:
                    errors.append(f"duplicate archive path: {name}")
                normalized_infos[name] = info
            if set(name.split("/", 1)[0] for name in normalized_infos) != {"web-ui-quality"}:
                errors.append("archive must contain exactly one web-ui-quality top-level directory")
            release_name = "web-ui-quality/RELEASE-MANIFEST.json"
            composite_name = "web-ui-quality/COMPOSITE-RELEASE-MANIFEST.json"
            release_manifest: dict[str, Any] | None = None
            composite_manifest: dict[str, Any] | None = None
            for name, label in ((release_name, "RELEASE-MANIFEST.json"), (composite_name, "COMPOSITE-RELEASE-MANIFEST.json")):
                info = normalized_infos.get(name)
                if info is None:
                    errors.append(f"{label} is missing")
                    continue
                try:
                    value = json.loads(archive.read(info).decode("utf-8"))
                except (OSError, UnicodeError, json.JSONDecodeError, zipfile.BadZipFile) as error:
                    errors.append(f"{label} is invalid: {type(error).__name__}")
                    continue
                if not isinstance(value, dict):
                    errors.append(f"{label} is not a JSON object")
                elif name == release_name:
                    release_manifest = value
                else:
                    composite_manifest = value
            result["manifest"] = release_manifest
            if release_manifest:
                result["packageTreeDigest"] = release_manifest.get("packageTreeDigest")
            for label, value in (("release", release_manifest), ("composite", composite_manifest)):
                if value is None:
                    continue
                for key, expected in EXPECTED_IDENTITY.items():
                    if value.get(key) != expected:
                        errors.append(f"{label} identity mismatch: {key}")
            if release_manifest is not None:
                if release_manifest.get("stage") != "4.3.0-commercial-stable":
                    errors.append("release manifest stage mismatch")
                if release_manifest.get("root") != "web-ui-quality/":
                    errors.append("release manifest root mismatch")
                rows = release_manifest.get("files")
                if not isinstance(rows, list):
                    errors.append("release manifest files is not a list")
                    rows = []
                if release_manifest.get("fileCount") != len(rows):
                    errors.append("release manifest fileCount does not match files")
                row_map: dict[str, dict[str, Any]] = {}
                for row in rows:
                    if not isinstance(row, dict):
                        errors.append("release manifest contains a non-object file row")
                        continue
                    relative = _safe_relative_path(row.get("path"))
                    digest = row.get("sha256")
                    size = row.get("bytes")
                    if relative is None or not _HEX64.fullmatch(str(digest or "")) or isinstance(size, bool) or not isinstance(size, int) or size < 0:
                        errors.append(f"release manifest contains an invalid file row: {row!r}")
                        continue
                    if relative in row_map:
                        errors.append(f"release manifest contains duplicate file row: {relative}")
                    row_map[relative] = {"path": relative, "bytes": size, "sha256": str(digest)}
                expected_archive_names = {f"web-ui-quality/{relative}" for relative in row_map} | {release_name, composite_name}
                if set(normalized_infos) != expected_archive_names:
                    extras = sorted(set(normalized_infos) - expected_archive_names)
                    missing = sorted(expected_archive_names - set(normalized_infos))
                    if extras:
                        errors.append(f"archive contains unknown extra files: {extras}")
                    if missing:
                        errors.append(f"archive is missing files: {missing}")
                for relative, row in row_map.items():
                    name = f"web-ui-quality/{relative}"
                    info = normalized_infos.get(name)
                    if info is None:
                        continue
                    data = archive.read(info)
                    if info.file_size != len(data) or len(data) != row["bytes"]:
                        errors.append(f"archive byte count mismatch: {relative}")
                    if hashlib.sha256(data).hexdigest() != row["sha256"]:
                        errors.append(f"archive file digest mismatch: {relative}")
                actual_tree = hashlib.sha256(
                    b"".join(
                        relative.encode("utf-8") + b"\0" + row["sha256"].encode("ascii") + b"\n"
                        for relative, row in sorted(row_map.items(), key=lambda item: item[0].encode("utf-8"))
                    )
                ).hexdigest()
                if actual_tree != release_manifest.get("packageTreeDigest"):
                    errors.append("release manifest packageTreeDigest does not match its rows")
                if composite_manifest is not None and composite_manifest.get("packageTreeDigest") != actual_tree:
                    errors.append("composite manifest packageTreeDigest does not match release rows")
                try:
                    expected_rows, expected_tree = _expected_source_rows()
                except (OSError, RuntimeError, ImportError, ValueError) as error:
                    errors.append(f"source package expectation unavailable: {type(error).__name__}: {error}")
                else:
                    expected_map = {row["path"]: row for row in expected_rows}
                    if set(row_map) != set(expected_map):
                        errors.append("candidate content file set does not equal current source package file set")
                    for relative, expected in expected_map.items():
                        if row_map.get(relative) != expected:
                            errors.append(f"candidate content differs from current source: {relative}")
                    if expected_tree != actual_tree:
                        errors.append("candidate package tree differs from current source package tree")
    except (OSError, zipfile.BadZipFile, RuntimeError) as error:
        errors.append(f"archive cannot be opened: {type(error).__name__}: {error}")
    result["status"] = "PASS" if not errors else "FAIL"
    result["errors"] = sorted(set(errors))
    return result


def _archive_manifest(path: Path) -> dict[str, Any] | None:
    try:
        with zipfile.ZipFile(path) as archive:
            names = {name.replace("\\", "/") for name in archive.namelist()}
            name = "web-ui-quality/RELEASE-MANIFEST.json"
            if name not in names:
                return None
            value = json.loads(archive.read(name).decode("utf-8"))
    except (OSError, zipfile.BadZipFile, KeyError, UnicodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _run_id(value: Mapping[str, Any] | None) -> str | None:
    if not isinstance(value, Mapping):
        return None
    result = str(value.get("releaseRunId") or value.get("runId") or "").strip()
    return result or None


def _browser_record_ok(value: Any, *, require_browser_backed: bool = False) -> bool:
    if not isinstance(value, Mapping):
        return False
    required = (
        "runtime", "moduleAvailable", "browserExecutableAvailable", "executed", "status", "reason",
        "executionBranch", "receiptSha256", "executionRecord",
    )
    if any(field not in value for field in required):
        return False
    if not bool(value.get("moduleAvailable")) or not bool(value.get("browserExecutableAvailable")):
        return False
    if value.get("executed") is not True or value.get("status") != "PASS":
        return False
    if not isinstance(value.get("command"), list) or not value.get("command"):
        return False
    if not isinstance(value.get("receiptSha256"), str) or not _HEX64.fullmatch(value["receiptSha256"]):
        return False
    execution = value.get("executionRecord")
    if not isinstance(execution, Mapping) or execution.get("status") != "PASS" or execution.get("executed") is not True:
        return False
    if not isinstance(execution.get("browserExecutable"), str) or not execution["browserExecutable"]:
        return False
    if not isinstance(execution.get("commandDigest"), str) or not _HEX64.fullmatch(execution["commandDigest"]):
        return False
    report_digest = execution.get("reportSha256") or execution.get("outputSha256")
    if not isinstance(report_digest, str) or not _HEX64.fullmatch(report_digest):
        return False
    if value.get("executionBranch") in {None, "", "NOT_VERIFIED", "NOT_RUN"}:
        return False
    if require_browser_backed and value.get("browserBacked") is not True:
        return False
    return True


def _validate_test_evidence(value: Mapping[str, Any] | None, evidence: Path) -> tuple[bool, dict[str, Any]]:
    if not isinstance(value, Mapping) or value.get("schemaVersion") != "1" or value.get("status") != "PASS":
        return False, {"reason": "missing schema/status"}
    tests = value.get("tests")
    if not isinstance(tests, list) or not tests:
        return False, {"reason": "tests list is empty"}
    names: set[str] = set()
    for row in tests:
        if not isinstance(row, Mapping) or not isinstance(row.get("name"), str) or not row["name"] or row["name"] in names:
            return False, {"reason": "test rows are not unique structured records"}
        names.add(row["name"])
        if row.get("status") != "PASS" or isinstance(row.get("passed"), bool) or not isinstance(row.get("passed"), int) or row["passed"] <= 0:
            return False, {"reason": f"test row is not a non-empty PASS: {row.get('name')}"}
        if row.get("stderrBytes") != 0:
            return False, {"reason": f"test row has stderr: {row.get('name')}"}
        ref = _safe_relative_path(row.get("evidence"))
        if ref is None or not (evidence / ref).is_file():
            return False, {"reason": f"test evidence file is missing: {row.get('evidence')}"}
    full_gate = value.get("fullGate")
    if not isinstance(full_gate, Mapping) or full_gate.get("status") != "PASS" or full_gate.get("requiredGateCount") != EXPECTED_GATE_COUNT or full_gate.get("passedGateCount") != EXPECTED_GATE_COUNT:
        return False, {"reason": "test evidence does not bind exact Full Gate"}
    full_ref = _safe_relative_path(full_gate.get("evidence"))
    if full_ref is None or not (evidence / full_ref).is_file():
        return False, {"reason": "full-gate evidence reference is missing"}
    distribution = value.get("distribution")
    if not isinstance(distribution, Mapping) or distribution.get("status") != "PASS" or distribution.get("checks") != 8:
        return False, {"reason": "test evidence does not bind Distribution Verifier"}
    dist_ref = _safe_relative_path(distribution.get("evidence"))
    if dist_ref is None or not (evidence / dist_ref).is_file():
        return False, {"reason": "distribution evidence reference is missing"}
    ordinary = value.get("ordinaryUserFlow")
    if not isinstance(ordinary, Mapping) or ordinary.get("status") != "PASS" or ordinary.get("noManualReceiptHmacDigestStorageStateOrHostJsonEditingRequired") is not True:
        return False, {"reason": "ordinary-user flow boundary is missing"}
    return True, {"testCount": len(tests), "names": sorted(names)}


def _validate_preview_evidence(value: Mapping[str, Any] | None, evidence: Path) -> tuple[bool, dict[str, Any]]:
    if not isinstance(value, Mapping) or value.get("schemaVersion") != "1" or value.get("status") != "PASS" or value.get("generationStatus") != "PASS":
        return False, {"reason": "preview evidence is not an executed structured PASS"}
    if value.get("experienceStatus") != "DIAGNOSIS_READY" or value.get("designPipelineValid") is not True or value.get("visualBuilderValid") is not True:
        return False, {"reason": "preview pipeline identity/validity is incomplete"}
    if value.get("allPatternPreviewsValid") is not True or value.get("allStylePreviewsValid") is not True or value.get("requestedCandidateCount") != 3 or value.get("candidateCount") != 3:
        return False, {"reason": "preview candidate matrix is incomplete"}
    required = value.get("requiredFiles")
    preview_root = value.get("previewRoot")
    if not isinstance(required, list) or not required or not isinstance(preview_root, str):
        return False, {"reason": "preview required files are missing"}
    try:
        root = Path(preview_root).expanduser().resolve()
        if not root.is_dir() or not root.is_relative_to(evidence.parent):
            return False, {"reason": "preview root is outside the current run"}
    except (OSError, RuntimeError, ValueError):
        return False, {"reason": "preview root is invalid"}
    for raw in required:
        try:
            item = Path(str(raw)).expanduser().resolve()
            if not item.is_file() or not item.is_relative_to(root):
                return False, {"reason": f"preview required file is missing or escapes preview root: {raw}"}
        except (OSError, RuntimeError, ValueError):
            return False, {"reason": f"preview required file is invalid: {raw}"}
    browser_status = value.get("browserStatus")
    branch = value.get("browserExecutionBranch")
    receipt = value.get("browserReceipt")
    if browser_status == "NOT_MEASURED":
        if branch != "NOT_RUN" or receipt is not None:
            return False, {"reason": "unmeasured Preview has a contradictory Browser receipt"}
    elif browser_status == "PASS":
        if branch in {None, "NOT_RUN", "BROWSER_UNAVAILABLE_EXPLICIT_BOUNDARY"} or not isinstance(receipt, Mapping):
            return False, {"reason": "Preview PASS has no live Browser receipt"}
        digest = receipt.get("reportSha256") or receipt.get("sha256")
        if not isinstance(digest, str) or not _HEX64.fullmatch(digest):
            return False, {"reason": "Preview Browser receipt has no report digest"}
    else:
        return False, {"reason": f"unknown Preview Browser branch: {browser_status}"}
    return True, {"requiredFileCount": len(required), "browserStatus": browser_status, "browserExecutionBranch": branch}


def _validate_full_gate(value: Mapping[str, Any] | None) -> tuple[bool, dict[str, Any]]:
    if not isinstance(value, Mapping) or value.get("status") != "PASS" or value.get("mode") != "full" or value.get("requiredGateCount") != EXPECTED_GATE_COUNT or value.get("passedGateCount") != EXPECTED_GATE_COUNT:
        return False, {"reason": "Full Gate identity/count/status is invalid"}
    rows = value.get("gates")
    if not isinstance(rows, list) or len(rows) != EXPECTED_GATE_COUNT:
        return False, {"reason": "Full Gate does not contain exactly 33 detailed rows"}
    try:
        release_gate = _load_release_gate_module()
        expected = [release_gate.gate_command_identity(command) for command in release_gate.build_gate_commands("full")]
    except (OSError, RuntimeError, ImportError, AttributeError, ValueError) as error:
        return False, {"reason": f"expected Full Gate command identity unavailable: {type(error).__name__}"}
    observed: list[str] = []
    for row in rows:
        if not isinstance(row, Mapping) or not isinstance(row.get("command"), list):
            return False, {"reason": "Full Gate contains an invalid command row"}
        identity = release_gate.gate_command_identity(row["command"])
        observed.append(identity)
        if row.get("status") != "PASS" or row.get("exitCode") != 0:
            return False, {"reason": f"Full Gate row did not PASS with exitCode 0: {identity}"}
    if len(set(observed)) != EXPECTED_GATE_COUNT or observed != expected:
        return False, {"reason": "Full Gate command identities are missing, duplicated, or out of order"}
    worker = value.get("worker")
    execution = worker.get("execution") if isinstance(worker, Mapping) else None
    if not isinstance(worker, Mapping) or worker.get("status") != "PASS" or worker.get("exitCode") != 0 or not isinstance(execution, Mapping):
        return False, {"reason": "Full Gate worker execution receipt is missing"}
    if execution.get("commandCount") != EXPECTED_GATE_COUNT or execution.get("commandDigest") != _json_digest(expected) or execution.get("timedOut") is not False:
        return False, {"reason": "Full Gate worker command receipt is invalid"}
    status_rows = [
        {"index": index, "command": identity, "status": row["status"], "exitCode": row["exitCode"]}
        for index, (identity, row) in enumerate(zip(observed, rows), start=1)
    ]
    if execution.get("statusRowsDigest") != _json_digest(status_rows):
        return False, {"reason": "Full Gate status row receipt digest does not match detailed rows"}
    cleanup = execution.get("processTreeCleanup")
    if not isinstance(cleanup, Mapping) or cleanup.get("residueFree") is not True:
        return False, {"reason": "Full Gate process cleanup is not residue-free"}
    for key in ("stdoutSha256", "stderrSha256"):
        if not isinstance(execution.get(key), str) or not _HEX64.fullmatch(execution[key]):
            return False, {"reason": f"Full Gate execution receipt lacks {key}"}
    return True, {"commandCount": len(rows), "commandDigest": execution.get("commandDigest"), "statusRowsDigest": execution.get("statusRowsDigest")}


def _load_release_gate_module() -> Any:
    path = ROOT / "scripts" / "release_gate.py"
    spec = importlib.util.spec_from_file_location("wuq_release_gate_for_ga_validation", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("release_gate.py could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _validate_distribution(value: Mapping[str, Any] | None) -> tuple[bool, dict[str, Any]]:
    if not isinstance(value, Mapping) or value.get("status") != "PASS":
        return False, {"reason": "Distribution Verifier status is not PASS"}
    checks = value.get("checks")
    if not isinstance(checks, list) or len(checks) != 8:
        return False, {"reason": "Distribution Verifier does not contain exactly eight checks"}
    observed = [row.get("id") for row in checks if isinstance(row, Mapping)]
    if set(observed) != EXPECTED_DISTRIBUTION_CHECK_IDS or len(observed) != len(set(observed)) or any(row.get("status") != "PASS" for row in checks if isinstance(row, Mapping)):
        return False, {"reason": "Distribution Verifier checks are incomplete or not PASS"}
    if not any(isinstance(row, Mapping) and row.get("id") == "DIST-007" and row.get("status") == "PASS" for row in checks):
        return False, {"reason": "DIST-007 is not PASS"}
    browser = value.get("browserQualification")
    if not isinstance(browser, Mapping):
        return False, {"reason": "Distribution Browser qualification is missing"}
    for key, backed in (("nodePlaywright", False), ("dist007", True)):
        if not _browser_record_ok(browser.get(key), require_browser_backed=backed):
            return False, {"reason": f"Distribution Browser branch {key} is not receipt-bound"}
    return True, {"checkCount": len(checks)}


def _validate_preflight(value: Mapping[str, Any] | None) -> tuple[bool, dict[str, Any]]:
    if not isinstance(value, Mapping) or value.get("status") != "GA_READY" or value.get("declaredVersion") != EXPECTED_VERSION or value.get("releaseEvidenceLine") != EXPECTED_VERSION:
        return False, {"reason": "Commercial Preflight is not GA_READY with the expected version"}
    checks = value.get("checks")
    if not isinstance(checks, list) or len(checks) != len(EXPECTED_PREFLIGHT_CHECK_IDS):
        return False, {"reason": "Commercial Preflight check list is incomplete"}
    ids = [row.get("id") for row in checks if isinstance(row, Mapping)]
    if set(ids) != EXPECTED_PREFLIGHT_CHECK_IDS or len(ids) != len(set(ids)) or any(row.get("status") != "PASS" for row in checks if isinstance(row, Mapping)):
        return False, {"reason": "Commercial Preflight contains missing, duplicate, or non-PASS checks"}
    blocking = value.get("blocking")
    if blocking not in ([], None):
        return False, {"reason": "Commercial Preflight still reports blocking checks"}
    if not isinstance(value.get("evidenceRoot"), str) or not isinstance(value.get("candidateArchive"), str):
        return False, {"reason": "Commercial Preflight does not bind evidence and candidate paths"}
    return True, {"checkCount": len(checks), "checkIds": ids}


def _external_project_row_ok(item: Mapping[str, Any], proof_dir: Path) -> bool:
    project = item.get("project")
    repository = item.get("repository")
    commit = item.get("commit")
    report = item.get("auditReport")
    if not all(isinstance(value, str) and value.strip() for value in (project, repository, commit)) or item.get("status") not in _VALID_EXTERNAL_PROJECT_STATUSES or not isinstance(report, Mapping):
        return False
    if report.get("status") != "PASS" or report.get("projectName") != project or report.get("repository") != repository or report.get("commit") != commit or report.get("workingTreeClean") is not True:
        return False
    if not isinstance(report.get("trackedFileCount"), int) or report["trackedFileCount"] <= 0 or not _HEX64.fullmatch(str(report.get("sourceTreeDigest") or "")):
        return False
    checks = report.get("checks")
    if not isinstance(checks, list) or not checks or any(not isinstance(row, Mapping) or row.get("status") != "PASS" for row in checks):
        return False
    report_path_value = item.get("auditReportPath")
    if not isinstance(report_path_value, str) or not report_path_value:
        return False
    report_path = Path(report_path_value).expanduser().resolve()
    try:
        if not report_path.is_file() or not report_path.is_relative_to(proof_dir):
            return False
    except (OSError, RuntimeError, ValueError):
        return False
    stored = item.get("auditReportSha256")
    return isinstance(stored, str) and _HEX64.fullmatch(stored) and _sha256(report_path) == stored and _read_json(report_path) == dict(report)


def _external_project_count(value: Mapping[str, Any] | None, proof_dir: Path | None = None) -> int:
    rows = value.get("projects", []) if isinstance(value, Mapping) else []
    if not isinstance(rows, list) or proof_dir is None:
        return 0
    unique: set[tuple[str, str, str]] = set()
    for item in rows:
        if not isinstance(item, Mapping) or not _external_project_row_ok(item, proof_dir):
            continue
        key = (str(item["project"]), str(item["repository"]), str(item["commit"]))
        if key not in unique:
            unique.add(key)
    return len(unique)


def evaluate(candidate: str | Path, evidence_root: str | Path) -> dict[str, Any]:
    candidate_path = Path(candidate).expanduser().resolve()
    evidence = Path(evidence_root).expanduser().resolve()
    blockers: list[dict[str, Any]] = []

    def require(condition: bool, code: str, detail: Any) -> None:
        if not condition:
            blockers.append({"code": code, "detail": detail})

    require(candidate_path.is_file(), "CANDIDATE_ARCHIVE_MISSING", str(candidate_path))
    require(evidence.is_dir(), "EVIDENCE_ROOT_MISSING", str(evidence))
    require(evidence.name == EXPECTED_EVIDENCE_ROOT, "EVIDENCE_ROOT_NOT_EXACT", {"expected": EXPECTED_EVIDENCE_ROOT, "provided": evidence.name})

    candidate_sha = _sha256(candidate_path) if candidate_path.is_file() else None
    candidate_validation = _validate_candidate_archive(candidate_path) if candidate_path.is_file() else {"status": "FAIL", "errors": ["archive is missing"], "manifest": None, "packageTreeDigest": None}
    manifest = candidate_validation.get("manifest")
    require(candidate_validation.get("status") == "PASS", "CANDIDATE_ARCHIVE_CONTENT_INVALID", candidate_validation.get("errors"))
    require(manifest is not None, "CANDIDATE_MANIFEST_MISSING_OR_INVALID", "web-ui-quality/RELEASE-MANIFEST.json")
    package_version = str((manifest or {}).get("packageVersion") or "")
    tree_digest = str((manifest or {}).get("packageTreeDigest") or "")
    require(package_version == EXPECTED_VERSION, "PACKAGE_VERSION_MISMATCH", {"expected": EXPECTED_VERSION, "provided": package_version or None})
    require(bool(tree_digest), "PACKAGE_TREE_DIGEST_MISSING", "Candidate manifest has no packageTreeDigest")

    binding = _read_json(evidence / "release-binding.json") if evidence.is_dir() else None
    full_gate = _read_json(evidence / "full-gate.json") if evidence.is_dir() else None
    distribution = _read_json(evidence / "distribution.json") if evidence.is_dir() else None
    preflight = _read_json(evidence / "commercial-preflight.json") if evidence.is_dir() else None
    proof = _read_json(evidence / "external-proof" / "summary.json") if evidence.is_dir() else None
    require(binding is not None, "RELEASE_BINDING_MISSING_OR_INVALID", "release-binding.json")
    require(full_gate is not None, "FULL_GATE_EVIDENCE_MISSING_OR_INVALID", "full-gate.json")
    require(distribution is not None, "DISTRIBUTION_EVIDENCE_MISSING_OR_INVALID", "distribution.json")
    require(preflight is not None, "COMMERCIAL_PREFLIGHT_EVIDENCE_MISSING_OR_INVALID", "commercial-preflight.json")
    require(proof is not None, "EXTERNAL_PROOF_MISSING_OR_INVALID", "external-proof/summary.json")

    binding_run_id = _run_id(binding)
    report_run_ids = {
        value
        for value in (_run_id(full_gate), _run_id(distribution), _run_id(preflight), binding_run_id, _run_id(proof))
        if value
    }
    test_path = next((evidence / name for name in _TEST_EVIDENCE_NAMES if (evidence / name).is_file()), None) if evidence.is_dir() else None
    test_evidence = _read_json(test_path) if test_path else None
    preview_path = evidence / "preview-matrix.json" if evidence.is_dir() else None
    preview = _read_json(preview_path) if preview_path and preview_path.is_file() else None
    test_evidence_ok, test_evidence_detail = _validate_test_evidence(test_evidence, evidence) if evidence.is_dir() else (False, {"reason": "evidence root is missing"})
    preview_evidence_ok, preview_evidence_detail = _validate_preview_evidence(preview, evidence) if evidence.is_dir() else (False, {"reason": "evidence root is missing"})
    require(test_evidence_ok, "TEST_EVIDENCE_MISSING_OR_INVALID", test_evidence_detail)
    require(preview_evidence_ok, "PREVIEW_EVIDENCE_MISSING_OR_INVALID", preview_evidence_detail)
    report_run_ids.update(value for value in (_run_id(test_evidence), _run_id(preview)) if value)
    require(bool(binding_run_id), "RELEASE_RUN_ID_MISSING", "release-binding.json has no releaseRunId")
    require(bool(binding_run_id) and report_run_ids == {binding_run_id}, "RELEASE_RUN_ID_MISMATCH", {"expected": binding_run_id, "observed": sorted(report_run_ids)})

    full_gate_ok, full_gate_detail = _validate_full_gate(full_gate)
    preflight_ok, preflight_detail = _validate_preflight(preflight)
    distribution_ok, distribution_detail = _validate_distribution(distribution)
    require(full_gate_ok, "TECHNICAL_FULL_GATE_NOT_33_OF_33", full_gate_detail)
    require(preflight_ok, "COMMERCIAL_PREFLIGHT_NOT_READY", preflight_detail)
    require(distribution_ok, "DISTRIBUTION_NOT_PASS", distribution_detail)
    dist007 = next((item for item in (distribution or {}).get("checks", []) if isinstance(item, Mapping) and item.get("id") == "DIST-007"), None)
    require(isinstance(dist007, Mapping) and dist007.get("status") == "PASS", "DIST_007_NOT_PASS", dist007)

    python_browser = ((full_gate or {}).get("browserQualification") or {}).get("pythonPlaywright")
    node_browser = ((distribution or {}).get("browserQualification") or {}).get("nodePlaywright")
    dist_browser = ((distribution or {}).get("browserQualification") or {}).get("dist007")
    require(_browser_record_ok(python_browser), "PYTHON_BROWSER_QUALIFICATION_NOT_PASS", python_browser)
    require(_browser_record_ok(node_browser), "NODE_BROWSER_QUALIFICATION_NOT_PASS", node_browser)
    require(_browser_record_ok(dist_browser, require_browser_backed=True), "DIST_007_BROWSER_BACKING_NOT_PASS", dist_browser)

    proof_dir = evidence / "external-proof" if evidence.is_dir() else None
    proven_projects = _external_project_count(proof, proof_dir)
    require(isinstance(proof, Mapping) and proof.get("status") == "PASS" and proof.get("requiredProjects") == 3 and proof.get("provenProjects") == 3, "EXTERNAL_PROOF_SUMMARY_NOT_PASS", {"status": (proof or {}).get("status"), "required": (proof or {}).get("requiredProjects"), "proven": (proof or {}).get("provenProjects")})
    require(proven_projects >= 3, "EXTERNAL_PROJECT_PROOF_INCOMPLETE", {"provenProjects": proven_projects, "required": 3})
    require((binding or {}).get("packageVersion") == EXPECTED_VERSION, "BINDING_PACKAGE_VERSION_MISMATCH", (binding or {}).get("packageVersion"))
    require((binding or {}).get("packageTreeDigest") == tree_digest, "BINDING_PACKAGE_TREE_MISMATCH", {"candidate": tree_digest, "bound": (binding or {}).get("packageTreeDigest")})
    require((binding or {}).get("candidateArchiveSha256") == candidate_sha, "BINDING_CANDIDATE_SHA_MISMATCH", {"candidate": candidate_sha, "bound": (binding or {}).get("candidateArchiveSha256")})
    require((binding or {}).get("candidateArchive") == str(candidate_path), "BINDING_CANDIDATE_PATH_MISMATCH", {"candidate": str(candidate_path), "bound": (binding or {}).get("candidateArchive")})
    full_digest = _sha256(evidence / "full-gate.json") if (evidence / "full-gate.json").is_file() else None
    distribution_digest = _sha256(evidence / "distribution.json") if (evidence / "distribution.json").is_file() else None
    preflight_digest = _sha256(evidence / "commercial-preflight.json") if (evidence / "commercial-preflight.json").is_file() else None
    require((binding or {}).get("fullGateStatus") == "PASS" and (binding or {}).get("fullGateReportDigest") == full_digest, "BINDING_FULL_GATE_DIGEST_MISMATCH", {"bound": (binding or {}).get("fullGateReportDigest"), "actual": full_digest})
    require((binding or {}).get("distributionStatus") == "PASS" and (binding or {}).get("distributionReportDigest") == distribution_digest, "BINDING_DISTRIBUTION_DIGEST_MISMATCH", {"bound": (binding or {}).get("distributionReportDigest"), "actual": distribution_digest})
    require((binding or {}).get("commercialPreflightStatus") == (preflight or {}).get("status"), "BINDING_PREFLIGHT_STATUS_MISMATCH", {"bound": (binding or {}).get("commercialPreflightStatus"), "actual": (preflight or {}).get("status")})
    require((binding or {}).get("commercialPreflightReportDigest") == preflight_digest, "BINDING_PREFLIGHT_DIGEST_MISMATCH", {"bound": (binding or {}).get("commercialPreflightReportDigest"), "actual": preflight_digest})
    require((binding or {}).get("testEvidenceDigest") == (_sha256(test_path) if test_path and test_path.is_file() else None), "BINDING_TEST_EVIDENCE_DIGEST_MISMATCH", {"bound": (binding or {}).get("testEvidenceDigest"), "actual": _sha256(test_path) if test_path and test_path.is_file() else None})
    require((binding or {}).get("previewEvidenceDigest") == (_sha256(preview_path) if preview_path and preview_path.is_file() else None), "BINDING_PREVIEW_EVIDENCE_DIGEST_MISMATCH", {"bound": (binding or {}).get("previewEvidenceDigest"), "actual": _sha256(preview_path) if preview_path and preview_path.is_file() else None})
    require((preflight or {}).get("declaredVersion") == EXPECTED_VERSION and (preflight or {}).get("releaseEvidenceLine") == EXPECTED_VERSION, "PREFLIGHT_IDENTITY_MISMATCH", {"declared": (preflight or {}).get("declaredVersion"), "evidenceLine": (preflight or {}).get("releaseEvidenceLine")})
    try:
        preflight_evidence_path = str(Path(str((preflight or {}).get("evidenceRoot") or "")).expanduser().resolve())
        preflight_candidate_path = str(Path(str((preflight or {}).get("candidateArchive") or "")).expanduser().resolve())
    except (OSError, RuntimeError, ValueError):
        preflight_evidence_path = preflight_candidate_path = ""
    require(preflight_evidence_path == str(evidence), "PREFLIGHT_EVIDENCE_PATH_MISMATCH", {"expected": str(evidence), "bound": (preflight or {}).get("evidenceRoot")})
    require(preflight_candidate_path == str(candidate_path), "PREFLIGHT_CANDIDATE_PATH_MISMATCH", {"expected": str(candidate_path), "bound": (preflight or {}).get("candidateArchive")})
    require((binding or {}).get("postQualificationChanges") == "NONE", "POST_QUALIFICATION_CHANGES_NOT_CLOSED", (binding or {}).get("postQualificationChanges"))

    decision = "GA_ELIGIBLE" if not blockers else "NOT_ELIGIBLE"
    return {
        "decision": decision,
        "packageVersion": EXPECTED_VERSION,
        "packageTreeDigest": tree_digest or None,
        "candidateArchiveSha256": candidate_sha,
        "releaseRunId": binding_run_id,
        "technicalGate": "PASS" if full_gate_ok else "NOT_PASS",
        "commercialPreflight": (preflight or {}).get("status", "NOT_VERIFIED"),
        "distribution": (distribution or {}).get("status", "NOT_VERIFIED"),
        "browserQualification": {
            "pythonPlaywright": python_browser,
            "nodePlaywright": node_browser,
            "dist007": dist_browser,
        },
        "candidateValidation": candidate_validation,
        "evidenceValidation": {
            "tests": test_evidence_detail,
            "preview": preview_evidence_detail,
            "fullGate": full_gate_detail,
            "distribution": distribution_detail,
            "commercialPreflight": preflight_detail,
            "externalProjects": proven_projects,
        },
        "blockers": blockers,
        "claimBoundary": "Eligibility applies only to this exact Candidate archive digest and its matching external evidence. Human approval and COMMERCIAL_GA remain outside this evaluator.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate exact 4.3.0 GA machine eligibility")
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--evidence-root", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    result = evaluate(args.candidate, args.evidence_root)
    serialized = json.dumps(result, ensure_ascii=False, separators=(",", ":") if args.compact else None, indent=None if args.compact else 2, sort_keys=not args.compact)
    print(serialized)
    if args.output:
        output = args.output.expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(serialized + "\n", encoding="utf-8")
    return 0 if result["decision"] == "GA_ELIGIBLE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
