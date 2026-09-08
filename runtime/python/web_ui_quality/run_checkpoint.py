"""Tamper-evident checkpoints and safe resume for ExperienceRun."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .contracts import ContractViolation, digest_json
from .experience_run import load_experience_run, _read_config, _mac
from .governance_artifacts import now_iso, safe_run_path

_CHECKPOINT_DIR = "checkpoints"


def _body_digest(value: Mapping[str, Any]) -> str:
    return digest_json({k: v for k, v in dict(value).items() if k not in {"checkpointDigest", "integrityMac"}})


def list_checkpoints(run_dir) -> list[dict[str, Any]]:
    run = load_experience_run(run_dir)
    directory = safe_run_path(run_dir, _CHECKPOINT_DIR)
    if not directory.exists():
        return []
    result = []
    for path in sorted(directory.glob("checkpoint-*.json")):
        cp = _read_checkpoint(path, expected_run_id=run["runId"])
        result.append({"checkpointId": cp["checkpointId"], "sequence": cp["sequence"], "currentPhase": cp["currentPhase"], "createdAt": cp["createdAt"], "checkpointDigest": cp["checkpointDigest"], "path": str(path)})
    return result


def _read_checkpoint(path: Path, *, expected_run_id: str | None = None) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ContractViolation("CHECKPOINT_INVALID", [f"$: unreadable checkpoint {path.name}"]) from error
    if not isinstance(value, dict):
        raise ContractViolation("CHECKPOINT_INVALID", ["$: checkpoint root must be object"])
    if expected_run_id is not None and value.get("runId") != expected_run_id:
        raise ContractViolation("CHECKPOINT_RUN_MISMATCH", ["$.runId: checkpoint belongs to another run"])
    digest = _body_digest(value)
    if value.get("checkpointDigest") != digest:
        raise ContractViolation("CHECKPOINT_TAMPERED", ["$.checkpointDigest: mismatch"])
    run_dir = path.parent.parent
    config, key = _read_config(run_dir)
    if value.get("runId") != config.get("runId"):
        raise ContractViolation("CHECKPOINT_RUN_MISMATCH", ["$.runId: checkpoint does not match immutable run"])
    expected_mac = _mac(key, {"runId": value.get("runId"), "checkpointDigest": digest, "sequence": value.get("sequence")})
    import hmac
    if not hmac.compare_digest(str(value.get("integrityMac") or ""), expected_mac):
        raise ContractViolation("CHECKPOINT_TAMPERED", ["$.integrityMac: checkpoint integrity failed"])
    return value


def create_checkpoint(run_dir, *, current_phase: str, task_goal: Mapping[str, Any] | None = None, assumptions: list[Mapping[str, Any]] | None = None, active_capabilities: list[str] | None = None, journey_identity: Mapping[str, Any] | None = None, findings: list[Mapping[str, Any]] | None = None, accepted_findings: list[str] | None = None, rejected_findings: list[str] | None = None, patch_candidates: list[Mapping[str, Any]] | None = None, applied_writes: list[Mapping[str, Any]] | None = None, verified_writes: list[Mapping[str, Any]] | None = None, pending_verification: list[str] | None = None, decisions: list[Mapping[str, Any]] | None = None, claim_boundary: str = "No Evidence, No PASS; resume never grants project write authority.") -> dict[str, Any]:
    run = load_experience_run(run_dir)
    previous = list_checkpoints(run_dir)
    sequence = len(previous) + 1
    parent = previous[-1]["checkpointDigest"] if previous else None
    before = run.get("phases", {}).get("before", {})
    body = {
        "schemaVersion": "1", "checkpointId": f"checkpoint-{sequence:04d}", "sequence": sequence,
        "runId": run["runId"], "taskId": run["taskId"], "targetIdentity": run.get("target"),
        "currentPhase": current_phase, "taskGoal": dict(task_goal or {}), "assumptions": list(assumptions or []),
        "activeCapabilities": list(active_capabilities or []), "baselineIdentity": {"digest": run.get("baselineDigest"), "status": before.get("status")},
        "journeyIdentity": dict(journey_identity or {}), "findings": list(findings or []), "acceptedFindings": list(accepted_findings or []),
        "rejectedFindings": list(rejected_findings or []), "patchCandidates": list(patch_candidates or []), "appliedWrites": list(applied_writes or []),
        "verifiedWrites": list(verified_writes or []), "pendingVerification": list(pending_verification or []), "decisions": list(decisions or []),
        "claimBoundary": claim_boundary, "createdAt": now_iso(), "parentCheckpoint": parent,
        "writeAuthorization": False, "writeAuthority": "HOST_APPROVAL_REQUIRED",
    }
    digest = digest_json(body)
    _, key = _read_config(Path(run["runDir"]))
    value = {**body, "checkpointDigest": digest, "integrityMac": _mac(key, {"runId": run["runId"], "checkpointDigest": digest, "sequence": sequence})}
    path = safe_run_path(run_dir, f"{_CHECKPOINT_DIR}/checkpoint-{sequence:04d}.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise ContractViolation("CHECKPOINT_EXISTS", [f"$: {path.name}"])
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return value


def resume_checkpoint(run_dir, checkpoint: str | int | None = None, *, task_id: str | None = None) -> dict[str, Any]:
    run = load_experience_run(run_dir)
    checkpoints = list_checkpoints(run_dir)
    if not checkpoints:
        raise ContractViolation("CHECKPOINT_NOT_FOUND", ["$: no checkpoints exist"])
    if checkpoint is None or checkpoint == "latest":
        selected = checkpoints[-1]
    elif isinstance(checkpoint, int) or str(checkpoint).isdigit():
        sequence = int(checkpoint)
        selected = next((x for x in checkpoints if x["sequence"] == sequence), None)
    else:
        name = str(checkpoint)
        selected = next((x for x in checkpoints if x["checkpointId"] == name), None)
    if selected is None:
        raise ContractViolation("CHECKPOINT_NOT_FOUND", [f"$: {checkpoint}"])
    value = _read_checkpoint(Path(selected["path"]), expected_run_id=run["runId"])
    if task_id is not None and value.get("taskId") != task_id:
        raise ContractViolation("CHECKPOINT_TASK_MISMATCH", ["$.taskId: checkpoint belongs to another task"])
    # Resume reuses the baseline identity only. It does not create or bless new Before evidence.
    return {
        **value,
        "resumeStatus": "READY",
        "beforeEvidence": "SEALED_REFERENCE_ONLY" if value.get("baselineIdentity", {}).get("status") == "SEALED" else "NOT_SEALED",
        "writeAuthorization": False,
        "writeAuthority": "HOST_APPROVAL_REQUIRED",
        "resumeClaimBoundary": "Checkpoint state is restored; evidence and Host write authority must be independently revalidated.",
    }




def find_latest_compatible_run(artifacts_root, *, task_id: str, target_identity: Mapping[str, Any] | None = None, mode: str | None = None) -> Path:
    """Find the newest intact ExperienceRun even when it has no checkpoint yet."""
    root = Path(artifacts_root).expanduser().resolve()
    if not root.is_dir():
        raise ContractViolation("EXPERIENCE_RUN_MISSING", ["$: artifacts root does not exist"])
    expected_target = digest_json(dict(target_identity)) if target_identity is not None else None
    candidates: list[tuple[str, Path]] = []
    for run_path in root.iterdir():
        if not run_path.is_dir() or not run_path.name.startswith("wuq-"):
            continue
        try:
            run = load_experience_run(run_path)
        except ContractViolation:
            continue
        if run.get("taskId") != task_id:
            continue
        if mode is not None and run.get("mode") != mode:
            continue
        if expected_target is not None and run.get("targetDigest") != expected_target:
            continue
        candidates.append((str(run.get("createdAt") or ""), run_path))
    if not candidates:
        raise ContractViolation("EXPERIENCE_RUN_MISSING", ["$: no compatible run found"])
    return max(candidates, key=lambda item: item[0])[1]


def find_latest_compatible_checkpoint(artifacts_root, *, task_id: str, target_identity: Mapping[str, Any] | None = None, mode: str | None = None) -> tuple[Path, dict[str, Any]]:
    """Find the newest checkpoint whose immutable run identity matches.

    Compatibility is deliberately narrow: task identity is required, and target
    identity / mode are matched when supplied. Tampered candidate runs are not
    treated as compatible state.
    """
    root = Path(artifacts_root).expanduser().resolve()
    if not root.is_dir():
        raise ContractViolation("CHECKPOINT_NOT_FOUND", ["$: artifacts root does not exist"])
    expected_target = digest_json(dict(target_identity)) if target_identity is not None else None
    candidates: list[tuple[str, Path, dict[str, Any]]] = []
    for run_path in root.iterdir():
        if not run_path.is_dir() or not run_path.name.startswith("wuq-"):
            continue
        try:
            run = load_experience_run(run_path)
            if run.get("taskId") != task_id:
                continue
            if mode is not None and run.get("mode") != mode:
                continue
            if expected_target is not None and run.get("targetDigest") != expected_target:
                continue
            rows = list_checkpoints(run_path)
            if not rows:
                continue
        except ContractViolation:
            continue
        latest = rows[-1]
        candidates.append((str(latest.get("createdAt") or ""), run_path, latest))
    if not candidates:
        raise ContractViolation("CHECKPOINT_NOT_FOUND", ["$: no compatible checkpoint found"])
    _, run_path, latest = max(candidates, key=lambda item: (item[0], item[2].get("sequence", 0)))
    return run_path, _read_checkpoint(Path(latest["path"]), expected_run_id=load_experience_run(run_path)["runId"])


def find_checkpoint_before(run_dir, query: str) -> dict[str, Any]:
    """Resolve “go back to before X” from persisted checkpoint content.

    The lookup never guesses. It finds the first checkpoint containing the query
    in persisted findings/patches/decisions and returns its parent checkpoint.
    """
    needle = str(query or "").strip().casefold()
    if not needle:
        raise ContractViolation("CHECKPOINT_TARGET_NEEDS_EXPLICIT_SCOPE", ["$: resume description is empty"])
    rows = list_checkpoints(run_dir)
    values = [_read_checkpoint(Path(row["path"]), expected_run_id=load_experience_run(run_dir)["runId"]) for row in rows]
    for index, value in enumerate(values):
        searchable = json.dumps({
            "findings": value.get("findings"),
            "patchCandidates": value.get("patchCandidates"),
            "decisions": value.get("decisions"),
            "taskGoal": value.get("taskGoal"),
        }, ensure_ascii=False, sort_keys=True).casefold()
        if needle in searchable:
            if index == 0:
                raise ContractViolation("CHECKPOINT_TARGET_NOT_FOUND", ["$: matching change exists in first checkpoint; no earlier checkpoint exists"])
            return values[index - 1]
    raise ContractViolation("CHECKPOINT_TARGET_NOT_FOUND", [f"$: no checkpoint mentions {query!r}"])


def build_run_health(run_dir, *, active_capabilities: list[str] | None = None, invalidated_artifacts: int = 0, claim_boundary: str = "No Evidence, No PASS") -> dict[str, Any]:
    run = load_experience_run(run_dir)
    checkpoints = list_checkpoints(run_dir)
    phases = run.get("phases", {})
    current = next((name for name in ("report", "compare", "after", "before") if phases.get(name, {}).get("status") == "SEALED"), "before")
    return {
        "schemaVersion": "1", "runId": run["runId"], "phase": current,
        "routesDiscovered": None, "routesExecuted": None,
        "evidenceStatus": {k: v.get("status") for k, v in phases.items()},
        "sourceAssurance": "NOT_MEASURED", "findings": None, "accepted": None, "rejected": None,
        "patchCandidates": None, "appliedWrites": None, "verified": None, "pending": None,
        "invalidatedArtifacts": int(invalidated_artifacts), "checkpoints": len(checkpoints),
        "activeCapabilities": list(active_capabilities or []), "claimBoundary": claim_boundary,
    }


__all__ = ["create_checkpoint", "list_checkpoints", "resume_checkpoint", "find_latest_compatible_run", "find_latest_compatible_checkpoint", "find_checkpoint_before", "build_run_health"]
