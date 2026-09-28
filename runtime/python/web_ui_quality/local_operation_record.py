"""Bounded local observations for Host-applied edits without independent attestation.

These records are intentionally distinct from Host write receipts.  They describe
the file state and Browser evidence observed by the local Runtime, but cannot
identify the writer or resist someone who can edit the project or run directory.
"""
from __future__ import annotations

import difflib
import json
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from .contracts import ContractViolation, digest_json, hash_file
from .experience_run import load_experience_run
from .phase1_boundaries import validate_write_physical_target
from .project_baseline import compare_project_baseline, load_project_baseline


LOCAL_OPERATION_RECORD_TYPE = "WEB_UI_QUALITY_LOCAL_OPERATION_RECORD_V1"
LOCAL_OPERATION_PREP_TYPE = "WEB_UI_QUALITY_LOCAL_OPERATION_PREP_V1"
_TRUST_BOUNDARY = (
    "This is a local observation of file state and Browser evidence. It is not an "
    "independent Host attestation, does not prove who made the change, and does "
    "not resist a writer with access to the project or run directory."
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path, *, code: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ContractViolation(code, [f"$: cannot read {path.name}"]) from error
    if not isinstance(value, dict):
        raise ContractViolation(code, [f"$: {path.name} must contain an object"])
    return value


def _write_exclusive(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    try:
        with path.open("xb") as handle:
            handle.write(data)
    except FileExistsError as error:
        raise ContractViolation("LOCAL_OPERATION_ARTIFACT_EXISTS", [f"$: refusing to overwrite {path.name}"]) from error


def record_related_run(
    run_dir: str | Path,
    related_run_dir: str | Path,
    *,
    task_id: str,
    target_digest: str,
    reason: str,
) -> dict[str, Any]:
    """Link a new repair run to an immutable discovery run without editing it."""
    current = load_experience_run(run_dir)
    prior = load_experience_run(related_run_dir)
    prior_root = Path(prior["runDir"]).resolve()
    if prior["runId"] == current["runId"]:
        raise ContractViolation("RELATED_RUN_MISMATCH", ["$: a run cannot be related to itself"])
    if prior.get("taskId") != task_id or current.get("taskId") != task_id:
        raise ContractViolation("RELATED_RUN_MISMATCH", ["$: related runs must belong to the same project task"])
    if prior.get("targetDigest") != target_digest or current.get("targetDigest") != target_digest:
        raise ContractViolation("RELATED_RUN_MISMATCH", ["$: related runs must bind the same project and route"])
    if prior.get("phases", {}).get("before", {}).get("status") != "SEALED":
        raise ContractViolation("RELATED_RUN_BEFORE_REQUIRED", ["$: the discovery run must have a sealed Before"])
    relation = {
        "schemaVersion": "1",
        "recordType": "WEB_UI_QUALITY_REPAIR_RUN_RELATION_V1",
        "relation": "REPAIR_CONTINUATION_FROM_IMMUTABLE_DISCOVERY",
        "discoveryRunId": str(prior["runId"]),
        "repairRunId": str(current["runId"]),
        "taskId": task_id,
        "targetDigest": target_digest,
        "discoveryConditionsDigest": str(prior.get("conditionsDigest") or ""),
        "repairConditionsDigest": str(current.get("conditionsDigest") or ""),
        "reason": reason,
        "createdAt": _now(),
        "claimBoundary": "This links task history; it does not copy or alter the discovery run's findings or Before evidence.",
    }
    relation["contentDigest"] = digest_json(relation)
    _write_exclusive(Path(current["runDir"]) / "report" / "related-run.json", relation)
    return relation


def prepare_local_operation(
    run_dir: str | Path,
    project_root: str | Path,
    *,
    task_id: str,
    session_id: str,
    plan: Mapping[str, Any],
    receipt_binding: Mapping[str, Any],
    scope_baseline: Mapping[str, Any],
    host_apply_binding_v3: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Snapshot explicitly scoped files before the Host applies an authorized edit."""
    if host_apply_binding_v3:
        raise ContractViolation("LOCAL_OPERATION_V3_MIXED", ["$: local operation records cannot be combined with a V3 apply binding"])
    root = Path(project_root).expanduser().resolve()
    run = load_experience_run(run_dir)
    run_root = Path(run["runDir"]).resolve()
    if run.get("taskId") != task_id or run.get("sessionId") != session_id:
        raise ContractViolation("LOCAL_OPERATION_RUN_MISMATCH", ["$: task/session do not match the selected run"])
    if run.get("phases", {}).get("before", {}).get("status") != "SEALED":
        raise ContractViolation("LOCAL_OPERATION_BEFORE_REQUIRED", ["$: a sealed Before is required before local Host apply"])
    if not plan.get("scopeConfirmed"):
        raise ContractViolation("LOCAL_OPERATION_SCOPE_UNCONFIRMED", ["$: explicit source scope is not confirmed"])
    scope = sorted({str(row.get("path") or "").replace("\\", "/") for row in plan.get("files", []) if isinstance(row, Mapping)})
    bound_scope = sorted({str(item).replace("\\", "/") for item in receipt_binding.get("sourceScope", [])})
    baseline_rows = {str(row.get("path")): row for row in scope_baseline.get("files", []) if isinstance(row, Mapping)}
    project_baseline = load_project_baseline(run_root)
    project_rows = {str(row.get("path")): row for row in project_baseline.get("files", []) if isinstance(row, Mapping)}
    if not scope or scope != bound_scope or any(not item for item in scope):
        raise ContractViolation("LOCAL_OPERATION_SCOPE_MISMATCH", ["$: fix plan and task binding must contain the same explicit file scope"])
    if receipt_binding.get("runId") != run.get("runId") or receipt_binding.get("taskId") != task_id or receipt_binding.get("sessionId") != session_id:
        raise ContractViolation("LOCAL_OPERATION_RUN_MISMATCH", ["$: source binding does not match the selected run"])
    if receipt_binding.get("baselineDigest") != project_baseline.get("baselineDigest"):
        raise ContractViolation("LOCAL_OPERATION_BASELINE_MISMATCH", ["$: source binding project baseline differs from sealed Before"])
    if receipt_binding.get("scopeBaselineDigest") != scope_baseline.get("scopeBaselineDigest"):
        raise ContractViolation("LOCAL_OPERATION_BASELINE_MISMATCH", ["$: scope baseline digest differs from task binding"])
    preapply_drift = compare_project_baseline(project_baseline, root, target_files=scope)
    if preapply_drift.get("unindexedTargets") or preapply_drift.get("added") or preapply_drift.get("removed") or preapply_drift.get("changed"):
        raise ContractViolation("LOCAL_OPERATION_PREAPPLY_DRIFT", ["$: project files changed after the new repair run's sealed Before; rebase instead of recording a local edit"])

    files: list[dict[str, Any]] = []
    snapshot_root = run_root / "report" / "local-operation" / "before"
    for rel in scope:
        path = validate_write_physical_target(root, rel)
        if not path.is_file() or path.is_symlink():
            raise ContractViolation("LOCAL_OPERATION_TARGET_INVALID", [f"$: source file is not a regular file: {rel}"])
        expected_scope = baseline_rows.get(rel)
        expected_project = project_rows.get(rel)
        if expected_scope is None or expected_project is None:
            raise ContractViolation("LOCAL_OPERATION_BASELINE_INCOMPLETE", [f"$: {rel} is missing from a sealed baseline"])
        current_hash = hash_file(path)
        if current_hash != expected_scope.get("sha256") or current_hash != expected_project.get("sha256"):
            raise ContractViolation("LOCAL_OPERATION_FILE_DRIFT", [f"$: {rel} changed after the sealed Before"])
        snapshot = snapshot_root.joinpath(*PurePosixPath(rel).parts)
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        try:
            with path.open("rb") as source, snapshot.open("xb") as target:
                data = source.read()
                target.write(data)
        except FileExistsError as error:
            raise ContractViolation("LOCAL_OPERATION_ARTIFACT_EXISTS", [f"$: refusing to replace the Before snapshot for {rel}"]) from error
        files.append({
            "canonicalPath": rel,
            "beforeSha256": current_hash,
            "beforeBytes": len(data),
            "snapshotPath": snapshot.relative_to(run_root).as_posix(),
        })

    prep: dict[str, Any] = {
        "schemaVersion": "1",
        "recordType": LOCAL_OPERATION_PREP_TYPE,
        "status": "READY_FOR_HOST_APPLY",
        "runId": str(run["runId"]),
        "taskId": task_id,
        "sessionId": session_id,
        "projectRoot": str(root),
        "targetDigest": str(run.get("targetDigest") or ""),
        "conditionsDigest": str(run.get("conditionsDigest") or ""),
        "baselineDigest": str(run.get("baselineDigest") or ""),
        "projectBaselineDigest": str(project_baseline.get("baselineDigest") or ""),
        "scopeBaselineDigest": str(scope_baseline.get("scopeBaselineDigest") or ""),
        "planDigest": str(plan.get("planDigest") or ""),
        "approvedSourceScope": scope,
        "files": files,
        "writeAuthority": "HOST_ONLY_USER_AUTHORIZATION_REQUIRED",
        "runtimeProjectWriteAuthority": False,
        "independentHostAttestation": "NOT_PROVIDED",
        "claimBoundary": _TRUST_BOUNDARY,
        "preparedAt": _now(),
    }
    prep["contentDigest"] = digest_json(prep)
    _write_exclusive(run_root / "report" / "local-operation-prep.json", prep)
    return prep


def check_local_operation_prewrite(
    run_dir: str | Path,
    project_root: str | Path,
    *,
    task_id: str,
    session_id: str,
) -> dict[str, Any]:
    """Check the exact prepared scope immediately before the Host writes it."""
    root = Path(project_root).expanduser().resolve()
    run = load_experience_run(run_dir)
    run_root = Path(run["runDir"]).resolve()
    if run.get("taskId") != task_id or run.get("sessionId") != session_id:
        raise ContractViolation("LOCAL_OPERATION_RUN_MISMATCH", ["$: task/session do not match the selected run"])
    if run.get("phases", {}).get("before", {}).get("status") != "SEALED":
        raise ContractViolation("LOCAL_OPERATION_BEFORE_REQUIRED", ["$: a sealed Before is required before local Host apply"])
    prep = _read_json(run_root / "report" / "local-operation-prep.json", code="LOCAL_OPERATION_PREP_MISSING")
    if prep.get("recordType") != LOCAL_OPERATION_PREP_TYPE or prep.get("contentDigest") != digest_json({key: value for key, value in prep.items() if key != "contentDigest"}):
        raise ContractViolation("LOCAL_OPERATION_PREP_INVALID", ["$: local preparation record type or content digest is invalid"])
    if any(prep.get(key) != run.get(key) for key in ("runId", "taskId", "sessionId", "targetDigest", "conditionsDigest", "baselineDigest")):
        raise ContractViolation("LOCAL_OPERATION_RUN_MISMATCH", ["$: preparation record belongs to another run/task/target/condition"])
    plan = _read_json(run_root / "report" / "fix-plan.json", code="LOCAL_OPERATION_PLAN_MISSING")
    result = _read_json(run_root / "report" / "fix-plan-result.json", code="LOCAL_OPERATION_PLAN_MISSING")
    binding = result.get("hostReceiptBinding") if isinstance(result.get("hostReceiptBinding"), Mapping) else {}
    scope = sorted(str(item).replace("\\", "/") for item in prep.get("approvedSourceScope", []))
    plan_scope = sorted(str(row.get("path") or "").replace("\\", "/") for row in plan.get("files", []) if isinstance(row, Mapping))
    binding_scope = sorted(str(item).replace("\\", "/") for item in binding.get("sourceScope", []))
    if not scope or scope != plan_scope or scope != binding_scope or plan.get("planDigest") != prep.get("planDigest") or binding.get("planDigest") != prep.get("planDigest"):
        raise ContractViolation("LOCAL_OPERATION_SCOPE_MISMATCH", ["$: prep, fix plan, and task binding must retain the exact prepared scope and plan"])
    if binding.get("runId") != run.get("runId") or binding.get("taskId") != task_id or binding.get("sessionId") != session_id:
        raise ContractViolation("LOCAL_OPERATION_RUN_MISMATCH", ["$: persisted task binding belongs to another run/task/session"])
    if result.get("hostApplyBindingV3") or (run_root / "report" / "host-apply-binding-v3.json").exists():
        raise ContractViolation("LOCAL_OPERATION_V3_MIXED", ["$: a local operation cannot replace or accompany a V3 apply binding"])

    project_baseline = load_project_baseline(run_root)
    drift = compare_project_baseline(project_baseline, root, target_files=scope)
    if drift.get("unindexedTargets") or drift.get("added") or drift.get("removed") or drift.get("changed"):
        raise ContractViolation("LOCAL_OPERATION_FILE_DRIFT", ["$: project files changed after local preparation; do not apply against a drifted Before"])
    prep_files = {str(row.get("canonicalPath")): row for row in prep.get("files", []) if isinstance(row, Mapping)}
    files: list[dict[str, str]] = []
    for rel in scope:
        row = prep_files.get(rel)
        if not isinstance(row, Mapping):
            raise ContractViolation("LOCAL_OPERATION_SCOPE_MISMATCH", [f"$: no pre-write snapshot exists for {rel}"])
        target = validate_write_physical_target(root, rel)
        snapshot = (run_root / str(row.get("snapshotPath") or "")).resolve()
        try:
            snapshot.relative_to(run_root)
        except ValueError as error:
            raise ContractViolation("LOCAL_OPERATION_SNAPSHOT_PATH_INVALID", [f"$: snapshot for {rel} escapes the run directory"]) from error
        if not target.is_file() or target.is_symlink() or not snapshot.is_file():
            raise ContractViolation("LOCAL_OPERATION_TARGET_INVALID", [f"$: prepared source or snapshot is unavailable: {rel}"])
        before_hash = str(row.get("beforeSha256") or "")
        if hash_file(target) != before_hash or hash_file(snapshot) != before_hash:
            raise ContractViolation("LOCAL_OPERATION_FILE_DRIFT", [f"$: {rel} changed after local preparation"])
        files.append({"canonicalPath": rel, "sha256": before_hash})
    check: dict[str, Any] = {
        "schemaVersion": "1",
        "recordType": "WEB_UI_QUALITY_LOCAL_OPERATION_PREWRITE_CHECK_V1",
        "status": "READY_FOR_HOST_APPLY",
        "runId": str(run["runId"]),
        "taskId": task_id,
        "sessionId": session_id,
        "targetDigest": str(run.get("targetDigest") or ""),
        "conditionsDigest": str(run.get("conditionsDigest") or ""),
        "baselineDigest": str(run.get("baselineDigest") or ""),
        "projectBaselineDigest": str(project_baseline.get("baselineDigest") or ""),
        "planDigest": str(prep.get("planDigest") or ""),
        "approvedSourceScope": scope,
        "files": files,
        "projectDrift": drift,
        "runtimeProjectWriteAuthority": False,
        "independentHostAttestation": "NOT_PROVIDED",
        "claimBoundary": _TRUST_BOUNDARY,
        "checkedAt": _now(),
    }
    check["contentDigest"] = digest_json(check)
    _write_exclusive(run_root / "report" / "local-operation-prewrite-check.json", check)
    return check


def observe_local_operation(
    run_dir: str | Path,
    project_root: str | Path,
    *,
    task_id: str,
    session_id: str,
) -> dict[str, Any]:
    """Compare sealed Before, approved scope, current files, and observed project drift."""
    root = Path(project_root).expanduser().resolve()
    run = load_experience_run(run_dir)
    run_root = Path(run["runDir"]).resolve()
    if run.get("taskId") != task_id or run.get("sessionId") != session_id:
        raise ContractViolation("LOCAL_OPERATION_RUN_MISMATCH", ["$: task/session do not match the selected run"])
    if run.get("phases", {}).get("before", {}).get("status") != "SEALED":
        raise ContractViolation("LOCAL_OPERATION_BEFORE_REQUIRED", ["$: a sealed Before is required for local After"])
    prep = _read_json(run_root / "report" / "local-operation-prep.json", code="LOCAL_OPERATION_PREP_MISSING")
    prep_digest = str(prep.get("contentDigest") or "")
    if prep.get("recordType") != LOCAL_OPERATION_PREP_TYPE or prep_digest != digest_json({key: value for key, value in prep.items() if key != "contentDigest"}):
        raise ContractViolation("LOCAL_OPERATION_PREP_INVALID", ["$: local preparation record type or content digest is invalid"])
    if any(prep.get(key) != run.get(run_key) for key, run_key in (("runId", "runId"), ("taskId", "taskId"), ("sessionId", "sessionId"), ("targetDigest", "targetDigest"), ("conditionsDigest", "conditionsDigest"), ("baselineDigest", "baselineDigest"))):
        raise ContractViolation("LOCAL_OPERATION_RUN_MISMATCH", ["$: preparation record belongs to another run/task/target/condition"])
    prewrite = _read_json(run_root / "report" / "local-operation-prewrite-check.json", code="LOCAL_OPERATION_PREWRITE_CHECK_REQUIRED")
    if prewrite.get("recordType") != "WEB_UI_QUALITY_LOCAL_OPERATION_PREWRITE_CHECK_V1" or prewrite.get("status") != "READY_FOR_HOST_APPLY" or prewrite.get("contentDigest") != digest_json({key: value for key, value in prewrite.items() if key != "contentDigest"}):
        raise ContractViolation("LOCAL_OPERATION_PREWRITE_CHECK_INVALID", ["$: local pre-write check type or content digest is invalid"])
    if any(prewrite.get(key) != prep.get(prep_key) for key, prep_key in (("runId", "runId"), ("taskId", "taskId"), ("sessionId", "sessionId"), ("targetDigest", "targetDigest"), ("conditionsDigest", "conditionsDigest"), ("baselineDigest", "baselineDigest"), ("projectBaselineDigest", "projectBaselineDigest"), ("planDigest", "planDigest"), ("approvedSourceScope", "approvedSourceScope"))):
        raise ContractViolation("LOCAL_OPERATION_RUN_MISMATCH", ["$: pre-write check belongs to another run or prepared scope"])

    plan = _read_json(run_root / "report" / "fix-plan.json", code="LOCAL_OPERATION_PLAN_MISSING")
    result = _read_json(run_root / "report" / "fix-plan-result.json", code="LOCAL_OPERATION_PLAN_MISSING")
    binding = result.get("hostReceiptBinding") if isinstance(result.get("hostReceiptBinding"), Mapping) else {}
    scope = sorted(str(item).replace("\\", "/") for item in prep.get("approvedSourceScope", []))
    plan_scope = sorted(str(row.get("path") or "").replace("\\", "/") for row in plan.get("files", []) if isinstance(row, Mapping))
    binding_scope = sorted(str(item).replace("\\", "/") for item in binding.get("sourceScope", []))
    if plan.get("planDigest") != prep.get("planDigest") or binding.get("planDigest") != prep.get("planDigest"):
        raise ContractViolation("LOCAL_OPERATION_PLAN_DRIFT", ["$: prepared fix plan changed after local scope preparation"])
    if not scope or scope != plan_scope or scope != binding_scope:
        raise ContractViolation("LOCAL_OPERATION_SCOPE_MISMATCH", ["$: local preparation, fix plan, and task binding do not have the same exact scope"])
    if binding.get("runId") != run.get("runId") or binding.get("taskId") != task_id or binding.get("sessionId") != session_id:
        raise ContractViolation("LOCAL_OPERATION_RUN_MISMATCH", ["$: persisted task binding belongs to another run/task/session"])
    if result.get("hostApplyBindingV3") or (run_root / "report" / "host-apply-binding-v3.json").exists():
        raise ContractViolation("LOCAL_OPERATION_V3_MIXED", ["$: a local record cannot replace or accompany a V3 apply binding"])

    project_baseline = load_project_baseline(run_root)
    drift = compare_project_baseline(project_baseline, root, target_files=scope)
    if drift.get("unindexedTargets"):
        raise ContractViolation("LOCAL_OPERATION_BASELINE_INCOMPLETE", ["$: an approved source file is not indexed in the sealed project baseline"])
    all_changed = set(str(item) for item in drift.get("changed", [])) | set(str(item) for item in drift.get("added", [])) | set(str(item) for item in drift.get("removed", []))
    unapproved = sorted(all_changed - set(scope))
    if unapproved:
        raise ContractViolation("LOCAL_OPERATION_SCOPE_EXCEEDED", [f"$: changed project file is outside the approved scope: {item}" for item in unapproved])
    if set(str(item) for item in drift.get("added", [])) & set(scope) or set(str(item) for item in drift.get("removed", [])) & set(scope):
        raise ContractViolation("LOCAL_OPERATION_EDIT_REQUIRED", ["$: local operation records only edits to existing approved files"])
    changed_scope = sorted(all_changed & set(scope))
    if not changed_scope:
        raise ContractViolation("LOCAL_OPERATION_NO_CHANGE", ["$: no approved source file changed since its sealed Before"])

    prep_files = {str(row.get("canonicalPath")): row for row in prep.get("files", []) if isinstance(row, Mapping)}
    prewrite_files = {str(row.get("canonicalPath")): row for row in prewrite.get("files", []) if isinstance(row, Mapping)}
    if sorted(prewrite_files) != scope or any(prewrite_files[rel].get("sha256") != prep_files.get(rel, {}).get("beforeSha256") for rel in scope):
        raise ContractViolation("LOCAL_OPERATION_PREWRITE_CHECK_INVALID", ["$: pre-write check file set or hashes differ from the prepared scope"])
    changes: list[dict[str, Any]] = []
    for rel in changed_scope:
        before_row = prep_files.get(rel)
        if not isinstance(before_row, Mapping):
            raise ContractViolation("LOCAL_OPERATION_SCOPE_MISMATCH", [f"$: no prepared snapshot exists for {rel}"])
        snapshot = (run_root / str(before_row.get("snapshotPath") or "")).resolve()
        try:
            snapshot.relative_to(run_root)
        except ValueError as error:
            raise ContractViolation("LOCAL_OPERATION_SNAPSHOT_PATH_INVALID", [f"$: snapshot for {rel} escapes the run directory"]) from error
        if not snapshot.is_file() or hash_file(snapshot) != before_row.get("beforeSha256"):
            raise ContractViolation("LOCAL_OPERATION_SNAPSHOT_DRIFT", [f"$: prepared Before snapshot for {rel} is missing or changed"])
        target = validate_write_physical_target(root, rel)
        if not target.is_file() or target.is_symlink():
            raise ContractViolation("LOCAL_OPERATION_TARGET_INVALID", [f"$: approved file is no longer a regular file: {rel}"])
        before_bytes = snapshot.read_bytes()
        after_bytes = target.read_bytes()
        try:
            before_text = before_bytes.decode("utf-8")
            after_text = after_bytes.decode("utf-8")
        except UnicodeError as error:
            raise ContractViolation("LOCAL_OPERATION_TEXT_DIFF_UNAVAILABLE", [f"$: cannot create a text diff for {rel}"]) from error
        diff = "".join(difflib.unified_diff(
            before_text.splitlines(keepends=True), after_text.splitlines(keepends=True),
            fromfile=f"before/{rel}", tofile=f"after/{rel}",
        ))
        changes.append({
            "canonicalPath": rel,
            "operation": "EDIT",
            "beforeSnapshotPath": str(before_row.get("snapshotPath") or ""),
            "beforeSha256": str(before_row.get("beforeSha256")),
            "afterSha256": hash_file(target),
            "beforeBytes": len(before_bytes),
            "afterBytes": len(after_bytes),
            "unifiedDiff": diff,
        })
    return {
        "projectRoot": str(root),
        "runId": str(run["runId"]),
        "taskId": task_id,
        "sessionId": session_id,
        "targetDigest": str(run.get("targetDigest") or ""),
        "conditionsDigest": str(run.get("conditionsDigest") or ""),
        "baselineDigest": str(run.get("baselineDigest") or ""),
        "projectBaselineDigest": str(prep.get("projectBaselineDigest") or ""),
        "scopeBaselineDigest": str(prep.get("scopeBaselineDigest") or ""),
        "planDigest": str(prep.get("planDigest") or ""),
        "prewriteCheckDigest": str(prewrite.get("contentDigest") or ""),
        "prewriteCheckedAt": str(prewrite.get("checkedAt") or ""),
        "approvedSourceScope": scope,
        "observedChangedFiles": [row["canonicalPath"] for row in changes],
        "files": changes,
        "projectDrift": drift,
        "independentHostAttestation": "NOT_PROVIDED",
        "claimBoundary": _TRUST_BOUNDARY,
    }


def complete_local_operation_record(
    observation: Mapping[str, Any],
    *,
    condition_match: bool,
    browser_comparison: Mapping[str, Any],
    after_report: Mapping[str, Any],
    after_manifest: Mapping[str, Any],
    repair_verification: Mapping[str, Any],
    run_dir: str | Path,
) -> dict[str, Any]:
    """Attach actual After checks to a locally observed edit record."""
    run_root = Path(run_dir).expanduser().resolve()
    run = load_experience_run(run_root)
    conditions = dict(run.get("conditions") or {})
    payload: dict[str, Any] = {
        "schemaVersion": "1",
        "recordType": LOCAL_OPERATION_RECORD_TYPE,
        "recordStatus": "LOCAL_OBSERVATION_COMPLETE",
        "createdAt": _now(),
        **dict(observation),
        "observationBasis": "The local Runtime compared the sealed Before snapshot with current project files after Host editing.",
        "authorizationBoundary": {
            "approvedSourceScope": list(observation.get("approvedSourceScope") or []),
            "projectWriteAuthority": "USER_AUTHORIZATION_AND_HOST_EXECUTION",
            "runtimeGrantedWriteAuthority": False,
            "writerIdentity": "NOT_INDEPENDENTLY_AUTHENTICATED",
        },
        "scopeCompliance": "PASS",
        "sameConditionAfter": {
            "conditionsMatch": bool(condition_match),
            "beforeConditionsDigest": str(observation.get("conditionsDigest") or ""),
            "afterManifestDigest": str(after_manifest.get("manifestDigest") or ""),
            "afterManifestPath": "after/manifest.json",
            "browserReportPath": "after/smart-acceptance-report.json",
            "browserStatus": str(after_report.get("status") or "NOT_MEASURED"),
            "browserPageHealth": after_report.get("pageHealth"),
            "browserComparisonStatus": str(browser_comparison.get("status") or "NOT_MEASURED"),
            "repairVerificationStatus": str(repair_verification.get("status") or "NOT_VERIFIED"),
            "viewports": list(conditions.get("viewports") or []),
        },
        "independentHostAttestation": "NOT_PROVIDED",
        "signature": None,
        "recordDigestClaim": "The contentDigest is a content identifier only; it is not a signature or tamper-proof guarantee.",
        "claimBoundary": _TRUST_BOUNDARY,
    }
    payload["contentDigest"] = digest_json(payload)
    _write_exclusive(run_root / "report" / "local-operation-record.json", payload)
    return payload


__all__ = [
    "LOCAL_OPERATION_PREP_TYPE", "LOCAL_OPERATION_RECORD_TYPE", "record_related_run",
    "prepare_local_operation", "check_local_operation_prewrite", "observe_local_operation",
    "complete_local_operation_record",
]
