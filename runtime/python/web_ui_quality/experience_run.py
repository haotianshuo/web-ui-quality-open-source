"""Tamper-evident Before/After evidence sessions.

The artifact directory is treated as hostile input after every phase.  Before
and After are re-hashed before binding, comparison and reporting.  A local HMAC
anchor detects out-of-band edits under the normal project threat model; it is
not a substitute for Host or operating-system access control.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import stat
import uuid
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from .contracts import ContractViolation, canonical_json, digest_json, sha256_hex

_ALLOWED_MODES = {"CHECK", "FIX_AND_VERIFY", "DEEP_REDESIGN", "SPECIALIZED_AUDIT"}
_PHASES = ("before", "after", "compare", "report")
_RUN_ID_RE = re.compile(r"^wuq-[0-9a-f]{16,32}$")
_KEY_FILE = ".wuq-integrity-key"
_RUN_FILE = "run.json"
_ANCHOR_FILE = "run.anchor.json"
_LEDGER_FILE = "transitions.ndjson"
_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_link_or_reparse(path: Path) -> bool:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & _REPARSE_POINT)


def _ensure_regular(path: Path, code: str) -> None:
    if _is_link_or_reparse(path):
        raise ContractViolation(code, [f"$: symbolic link, junction, or reparse point is forbidden: {path}"])
    try:
        info = path.stat()
    except FileNotFoundError as error:
        raise ContractViolation(code, [f"$: required path missing: {path}"]) from error
    if not stat.S_ISREG(info.st_mode):
        raise ContractViolation(code, [f"$: regular file required: {path}"])


def _ensure_directory(path: Path, code: str) -> None:
    if _is_link_or_reparse(path):
        raise ContractViolation(code, [f"$: symbolic link, junction, or reparse point is forbidden: {path}"])
    try:
        info = path.stat()
    except FileNotFoundError as error:
        raise ContractViolation(code, [f"$: directory missing: {path}"]) from error
    if not stat.S_ISDIR(info.st_mode):
        raise ContractViolation(code, [f"$: directory required: {path}"])


def _inside(root: Path, candidate: Path, code: str) -> None:
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise ContractViolation(code, [f"$: path escapes trusted root: {candidate}"]) from error


def _safe_relative(value: str) -> str:
    pure = PurePosixPath(str(value).replace("\\", "/"))
    if pure.is_absolute() or ".." in pure.parts or not pure.parts or any(part in {"", "."} for part in pure.parts):
        raise ContractViolation("EXPERIENCE_EVIDENCE_PATH_INVALID", [f"$: unsafe path {value!r}"])
    return pure.as_posix()


def _validate_run_id(value: str) -> str:
    rid = str(value)
    if not _RUN_ID_RE.fullmatch(rid):
        raise ContractViolation("EXPERIENCE_RUN_ID_INVALID", ["$: runId must match ^wuq-[0-9a-f]{16,32}$"])
    return rid


def _secure_root(path: str | Path) -> Path:
    raw = Path(path).expanduser()
    raw.mkdir(parents=True, exist_ok=True)
    root = raw.resolve()
    _ensure_directory(root, "EXPERIENCE_ARTIFACT_ROOT_INVALID")
    return root


def _key_store() -> Path:
    """Return the user-level directory that holds evidence integrity keys.

    Keeping the key inside the artifacts root means any process able to edit
    evidence can also read the key and recompute every MAC, which reduces the
    integrity chain to a checksum.  A user-level store outside the artifacts
    tree at least separates the two.  This does not defend against a process
    running as the same user, and it is not remote attestation.
    """
    override = os.environ.get("WUQ_KEY_STORE")
    if override:
        base = Path(override).expanduser()
    elif os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "web-ui-quality"
    else:
        base = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state") / "web-ui-quality"
    store = base / "integrity-keys"
    store.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        try:
            os.chmod(store, 0o700)
        except OSError:
            pass
    return store


def _key_path(artifacts_root: Path) -> Path:
    """Map an artifacts root to its key file, keyed by resolved path.

    Renaming or moving an artifacts root changes this mapping, so existing runs
    under it will no longer verify.  That is intentional: a relocated evidence
    tree is not the tree that was sealed.
    """
    fingerprint = sha256_hex(str(artifacts_root).encode("utf-8"))
    return _key_store() / f"{fingerprint}.key"


def _read_key_file(key_path: Path) -> bytes:
    _ensure_regular(key_path, "RUN_STATE_TAMPERED")
    raw = key_path.read_bytes()
    if len(raw) != 32:
        raise ContractViolation("RUN_STATE_TAMPERED", ["$: invalid artifact integrity key"])
    return raw


def _create_key_file(key_path: Path, raw: bytes) -> bytes | None:
    """Create the key exclusively; return None if another process won the race."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(key_path, flags, 0o600)
    except FileExistsError:
        return None
    with os.fdopen(fd, "wb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    return raw


def _integrity_key(artifacts_root: Path) -> bytes:
    key_path = _key_path(artifacts_root)
    if key_path.exists() or key_path.is_symlink():
        return _read_key_file(key_path)

    legacy = artifacts_root / _KEY_FILE
    if legacy.exists() or legacy.is_symlink():
        # Migrate an in-tree key from an earlier release so sealed runs stay
        # verifiable, then remove the copy that shared the evidence directory.
        raw = _read_key_file(legacy)
        if _create_key_file(key_path, raw) is None:
            return _read_key_file(key_path)
        try:
            legacy.unlink()
        except OSError:
            pass
        return raw

    created = _create_key_file(key_path, secrets.token_bytes(32))
    if created is None:
        return _read_key_file(key_path)
    return created


def _mac(key: bytes, value: Any) -> str:
    return hmac.new(key, canonical_json(value).encode("utf-8"), hashlib.sha256).hexdigest()


def _secure_parent(base: Path, relative_parent: PurePosixPath) -> Path:
    _ensure_directory(base, "EXPERIENCE_EVIDENCE_PATH_INVALID")
    current = base
    for part in relative_parent.parts:
        current = current / part
        if current.exists() or current.is_symlink():
            _ensure_directory(current, "EXPERIENCE_EVIDENCE_PATH_INVALID")
        else:
            os.mkdir(current, 0o755)
            _ensure_directory(current, "EXPERIENCE_EVIDENCE_PATH_INVALID")
        resolved = current.resolve()
        _inside(base.resolve(), resolved, "EXPERIENCE_EVIDENCE_PATH_INVALID")
    return current


def _write_exclusive(base: Path, relative_path: str, data: bytes, *, mode: int = 0o644) -> Path:
    rel = PurePosixPath(_safe_relative(relative_path))
    parent = _secure_parent(base, rel.parent) if rel.parent.parts else base
    target = parent / rel.name
    if target.exists() or target.is_symlink():
        raise ContractViolation("BEFORE_EVIDENCE_IMMUTABLE", [f"$: evidence already exists: {relative_path}"])
    resolved_parent = parent.resolve()
    _inside(base.resolve(), resolved_parent, "EXPERIENCE_EVIDENCE_PATH_INVALID")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(target, flags, mode)
    except (FileExistsError, OSError) as error:
        raise ContractViolation("EXPERIENCE_EVIDENCE_PATH_INVALID", [f"$: secure evidence create failed: {relative_path}"]) from error
    with os.fdopen(fd, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    _ensure_regular(target, "EXPERIENCE_EVIDENCE_PATH_INVALID")
    _inside(base.resolve(), target.resolve(), "EXPERIENCE_EVIDENCE_PATH_INVALID")
    return target


def _append_exclusive_line(path: Path, value: Mapping[str, Any]) -> None:
    _ensure_regular(path, "RUN_STATE_TAMPERED")
    flags = os.O_WRONLY | os.O_APPEND
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags)
    with os.fdopen(fd, "ab") as handle:
        handle.write((canonical_json(dict(value)) + "\n").encode("utf-8"))
        handle.flush()
        os.fsync(handle.fileno())


def _anchor_payload(config: Mapping[str, Any]) -> dict[str, Any]:
    return {"configDigest": digest_json(dict(config)), "runId": config.get("runId"), "createdAt": config.get("createdAt")}


def _read_config(run_dir: Path) -> tuple[dict[str, Any], bytes]:
    _ensure_directory(run_dir, "EXPERIENCE_RUN_MISSING")
    artifacts_root = run_dir.parent.resolve()
    _inside(artifacts_root, run_dir.resolve(), "EXPERIENCE_RUN_MISSING")
    config_path = run_dir / _RUN_FILE
    anchor_path = run_dir / _ANCHOR_FILE
    _ensure_regular(config_path, "RUN_STATE_TAMPERED")
    _ensure_regular(anchor_path, "RUN_STATE_TAMPERED")
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
        anchor = json.loads(anchor_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ContractViolation("RUN_STATE_TAMPERED", [f"$: run metadata unreadable: {type(error).__name__}"]) from error
    key = _integrity_key(artifacts_root)
    payload = _anchor_payload(config)
    if anchor.get("payload") != payload or not hmac.compare_digest(str(anchor.get("mac") or ""), _mac(key, payload)):
        raise ContractViolation("RUN_STATE_TAMPERED", ["$: immutable run configuration or anchor was modified"])
    return config, key


def _ledger_records(run_dir: Path, key: bytes) -> list[dict[str, Any]]:
    ledger = run_dir / _LEDGER_FILE
    _ensure_regular(ledger, "RUN_STATE_TAMPERED")
    records: list[dict[str, Any]] = []
    previous = "0" * 64
    for index, line in enumerate(ledger.read_text(encoding="utf-8").splitlines(), start=1):
        try:
            record = json.loads(line)
        except json.JSONDecodeError as error:
            raise ContractViolation("RUN_STATE_TAMPERED", [f"$: transition ledger line {index} is invalid"]) from error
        body = {key_name: value for key_name, value in record.items() if key_name not in {"recordDigest", "mac"}}
        digest = digest_json(body)
        if record.get("sequence") != index or record.get("previousDigest") != previous or record.get("recordDigest") != digest:
            raise ContractViolation("RUN_STATE_TAMPERED", [f"$: transition ledger chain failed at line {index}"])
        if not hmac.compare_digest(str(record.get("mac") or ""), _mac(key, {"recordDigest": digest, "runId": record.get("runId")})):
            raise ContractViolation("RUN_STATE_TAMPERED", [f"$: transition ledger MAC failed at line {index}"])
        previous = digest
        records.append(record)
    if not records or records[0].get("event") != "RUN_CREATED":
        raise ContractViolation("RUN_STATE_TAMPERED", ["$: RUN_CREATED transition missing"])
    return records


def _append_transition(run_dir: Path, event: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    config, key = _read_config(run_dir)
    records = _ledger_records(run_dir, key)
    previous = records[-1]["recordDigest"]
    body = {
        "sequence": len(records) + 1,
        "runId": config["runId"],
        "event": event,
        "at": _now(),
        "payload": dict(payload),
        "previousDigest": previous,
    }
    record_digest = digest_json(body)
    record = {**body, "recordDigest": record_digest, "mac": _mac(key, {"recordDigest": record_digest, "runId": config["runId"]})}
    _append_exclusive_line(run_dir / _LEDGER_FILE, record)
    return record


def _derive_state(config: Mapping[str, Any], records: list[dict[str, Any]]) -> dict[str, Any]:
    phases = {phase: {"status": "OPEN" if phase == "before" else "PENDING"} for phase in _PHASES}
    baseline = None
    for record in records[1:]:
        payload = dict(record.get("payload") or {})
        if record.get("event") == "BEFORE_SEALED":
            baseline = payload.get("baselineDigest")
            phases["before"] = {"status": "SEALED", "manifest": "before/manifest.json", "digest": baseline}
        elif record.get("event") == "AFTER_SEALED":
            phases["after"] = {"status": "SEALED", "manifest": "after/manifest.json", "digest": payload.get("phaseDigest")}
        elif record.get("event") in {"COMPARE_WRITTEN", "REPORT_WRITTEN"}:
            name = "compare" if record.get("event") == "COMPARE_WRITTEN" else "report"
            phases[name] = {
                "status": "SEALED",
                "manifest": f"{name}/manifest.json",
                "digest": payload.get("manifestDigest"),
                "payloadDigest": payload.get("digest"),
            }
    return {**dict(config), "baselineDigest": baseline, "phases": phases, "ledgerDigest": records[-1]["recordDigest"]}


def _phase_files(phase_dir: Path) -> list[dict[str, Any]]:
    _ensure_directory(phase_dir, "EVIDENCE_MANIFEST_MISMATCH")
    files: list[dict[str, Any]] = []
    for current, dirnames, filenames in os.walk(phase_dir, topdown=True, followlinks=False):
        current_path = Path(current)
        for dirname in list(dirnames):
            candidate = current_path / dirname
            if _is_link_or_reparse(candidate):
                raise ContractViolation("EVIDENCE_MANIFEST_MISMATCH", [f"$: linked evidence directory forbidden: {candidate.relative_to(phase_dir)}"])
        for filename in filenames:
            path = current_path / filename
            if filename in {"manifest.json", ".sealed"} and path.parent == phase_dir:
                continue
            _ensure_regular(path, "EVIDENCE_MANIFEST_MISMATCH")
            resolved = path.resolve()
            _inside(phase_dir.resolve(), resolved, "EVIDENCE_MANIFEST_MISMATCH")
            raw = path.read_bytes()
            files.append({"path": path.relative_to(phase_dir).as_posix(), "sha256": sha256_hex(raw), "bytes": len(raw)})
    return sorted(files, key=lambda row: row["path"])


_PHASE_EVENTS = {
    "before": "BEFORE_SEALED",
    "after": "AFTER_SEALED",
    "compare": "COMPARE_WRITTEN",
    "report": "REPORT_WRITTEN",
}
_PHASE_MISSING_CODES = {
    "before": "BEFORE_EVIDENCE_REQUIRED",
    "after": "AFTER_EVIDENCE_REQUIRED",
    "compare": "EXPERIENCE_PHASE_EVIDENCE_REQUIRED",
    "report": "EXPERIENCE_PHASE_EVIDENCE_REQUIRED",
}
_PHASE_ARTIFACT = "artifact.json"


def _canonical_payload_bytes(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True, default=str).encode("utf-8")


def _manifest_payload(phase: str, files: list[dict[str, Any]], run: Mapping[str, Any], *, baseline_digest: str | None = None, payload_digest: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schemaVersion": "2",
        "phase": phase,
        "files": files,
        "fileCount": len(files),
        "filesDigest": digest_json(files),
        "conditionsDigest": run["conditionsDigest"],
        "targetDigest": run["targetDigest"],
        "taskId": run["taskId"],
        "sessionId": run["sessionId"],
        "runConfigDigest": digest_json({key: run[key] for key in ("runId", "taskId", "sessionId", "mode", "targetDigest", "conditionsDigest", "createdAt")}),
    }
    if baseline_digest is not None:
        payload["baselineDigest"] = baseline_digest
    if payload_digest is not None:
        payload["payloadDigest"] = payload_digest
    return payload


def _validate_phase(run_dir: Path, phase: str) -> dict[str, Any]:
    run = load_experience_run(run_dir, validate_phases=False)
    config, key = _read_config(run_dir)
    phase_dir = run_dir / phase
    manifest_path = phase_dir / "manifest.json"
    seal_path = phase_dir / ".sealed"
    if not manifest_path.is_file() or not seal_path.is_file():
        raise ContractViolation(_PHASE_MISSING_CODES[phase], [f"$: sealed {phase} evidence required"])
    _ensure_regular(manifest_path, "EVIDENCE_MANIFEST_MISMATCH")
    _ensure_regular(seal_path, "EVIDENCE_MANIFEST_MISMATCH")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        seal = json.loads(seal_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ContractViolation("EVIDENCE_MANIFEST_MISMATCH", [f"$: {phase} seal or manifest is invalid"]) from error
    actual_files = _phase_files(phase_dir)
    if manifest.get("files") != actual_files or manifest.get("fileCount") != len(actual_files) or manifest.get("filesDigest") != digest_json(actual_files):
        raise ContractViolation("BASELINE_TAMPERED" if phase == "before" else "EVIDENCE_MANIFEST_MISMATCH", [f"$: {phase} evidence files no longer match the sealed manifest"])
    body = {name: value for name, value in manifest.items() if name not in {"manifestDigest", "integrityMac"}}
    manifest_digest = digest_json(body)
    if manifest.get("manifestDigest") != manifest_digest or not hmac.compare_digest(str(manifest.get("integrityMac") or ""), _mac(key, {"phase": phase, "manifestDigest": manifest_digest, "runId": run["runId"]})):
        raise ContractViolation("EVIDENCE_MANIFEST_MISMATCH", [f"$: {phase} manifest integrity check failed"])
    seal_body = {name: value for name, value in seal.items() if name != "integrityMac"}
    if seal.get("manifestDigest") != manifest_digest or not hmac.compare_digest(str(seal.get("integrityMac") or ""), _mac(key, seal_body)):
        raise ContractViolation("EVIDENCE_MANIFEST_MISMATCH", [f"$: {phase} seal integrity check failed"])
    records = _ledger_records(run_dir, key)
    matching = [record for record in records if record.get("event") == _PHASE_EVENTS[phase]]
    if len(matching) != 1 or matching[0].get("payload", {}).get("manifestDigest") != manifest_digest:
        raise ContractViolation("RUN_STATE_TAMPERED", [f"$: {phase} transition does not match sealed evidence"])
    if phase in {"compare", "report"}:
        # The conclusion layer is what users act on, so the recorded payload must
        # still be the payload on disk, not merely a digest the caller asserted.
        recorded = str(matching[0].get("payload", {}).get("digest") or "")
        artifact = phase_dir / _PHASE_ARTIFACT
        _ensure_regular(artifact, "EVIDENCE_MANIFEST_MISMATCH")
        try:
            persisted = digest_json(json.loads(artifact.read_text(encoding="utf-8")))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise ContractViolation("EVIDENCE_MANIFEST_MISMATCH", [f"$: {phase} artifact is unreadable"]) from error
        if manifest.get("payloadDigest") != recorded or persisted != recorded:
            raise ContractViolation("EVIDENCE_MANIFEST_MISMATCH", [f"$: {phase} payload no longer matches the recorded artifact"])
    if phase == "before":
        expected_baseline = digest_json({
            "files": actual_files,
            "conditionsDigest": run["conditionsDigest"],
            "targetDigest": run["targetDigest"],
            "taskId": run["taskId"],
            "sessionId": run["sessionId"],
        })
        if manifest.get("baselineDigest") != expected_baseline or seal.get("baselineDigest") != expected_baseline or run.get("baselineDigest") != expected_baseline:
            raise ContractViolation("BASELINE_TAMPERED", ["$: baseline digest no longer matches sealed Before evidence"])
    return manifest


def create_experience_run(
    artifacts_root: str | Path,
    *,
    task_id: str,
    session_id: str,
    mode: str,
    target: Mapping[str, Any],
    conditions: Mapping[str, Any],
    run_id: str | None = None,
) -> dict[str, Any]:
    if mode not in _ALLOWED_MODES:
        raise ContractViolation("EXPERIENCE_MODE_INVALID", [f"$.mode: {mode!r}"])
    if not task_id or not session_id:
        raise ContractViolation("EXPERIENCE_BINDING_INVALID", ["$: taskId and sessionId are required"])
    root = _secure_root(artifacts_root)
    rid = _validate_run_id(run_id or f"wuq-{uuid.uuid4().hex[:16]}")
    run_dir = (root / rid).resolve(strict=False)
    _inside(root, run_dir, "EXPERIENCE_RUN_ID_INVALID")
    try:
        run_dir.mkdir(mode=0o755, exist_ok=False)
    except FileExistsError as error:
        raise ContractViolation("EXPERIENCE_RUN_EXISTS", [f"$: runId {rid} already exists"]) from error
    _ensure_directory(run_dir, "EXPERIENCE_RUN_ID_INVALID")
    for phase in _PHASES:
        (run_dir / phase).mkdir(mode=0o755)
    payload: dict[str, Any] = {
        "schemaVersion": "2",
        "runId": rid,
        "taskId": task_id,
        "sessionId": session_id,
        "mode": mode,
        "target": dict(target),
        "targetDigest": digest_json(dict(target)),
        "conditions": dict(conditions),
        "conditionsDigest": digest_json(dict(conditions)),
        "createdAt": _now(),
    }
    key = _integrity_key(root)
    _write_exclusive(run_dir, _RUN_FILE, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8"))
    anchor_payload = _anchor_payload(payload)
    _write_exclusive(run_dir, _ANCHOR_FILE, json.dumps({"payload": anchor_payload, "mac": _mac(key, anchor_payload)}, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8"))
    first_body = {"sequence": 1, "runId": rid, "event": "RUN_CREATED", "at": payload["createdAt"], "payload": {"configDigest": anchor_payload["configDigest"]}, "previousDigest": "0" * 64}
    first_digest = digest_json(first_body)
    first = {**first_body, "recordDigest": first_digest, "mac": _mac(key, {"recordDigest": first_digest, "runId": rid})}
    _write_exclusive(run_dir, _LEDGER_FILE, (canonical_json(first) + "\n").encode("utf-8"))
    return {**payload, "baselineDigest": None, "phases": {phase: {"status": "OPEN" if phase == "before" else "PENDING"} for phase in _PHASES}, "runDir": str(run_dir)}


def _reject_orphan_seals(run_dir: Path, phases: Mapping[str, Any]) -> None:
    """Refuse a phase that is sealed on disk but absent from the ledger.

    The transition chain only proves forward consistency, so truncating it from
    the tail would otherwise regress a sealed phase back to OPEN without any
    tampering signal.  Sealed evidence on disk is itself a record, and it must
    agree with the ledger in both directions.
    """
    for phase in _PHASES:
        if phases.get(phase, {}).get("status") == "SEALED":
            continue
        phase_dir = run_dir / phase
        if (phase_dir / "manifest.json").is_file() and (phase_dir / ".sealed").is_file():
            raise ContractViolation(
                "RUN_STATE_TAMPERED",
                [f"$: {phase} evidence is sealed on disk but its transition is missing from the ledger"],
            )


def load_experience_run(run_dir: str | Path, *, validate_phases: bool = True) -> dict[str, Any]:
    root = Path(run_dir).expanduser().resolve()
    config, key = _read_config(root)
    records = _ledger_records(root, key)
    value = _derive_state(config, records)
    value["runDir"] = str(root)
    _reject_orphan_seals(root, value["phases"])
    if validate_phases:
        for phase in _PHASES:
            if value["phases"][phase]["status"] == "SEALED":
                _validate_phase(root, phase)
    return value


def write_phase_file(run_dir: str | Path, phase: str, relative_path: str, data: bytes | str) -> dict[str, Any]:
    root = Path(run_dir).expanduser().resolve()
    run = load_experience_run(root)
    if phase not in _PHASES:
        raise ContractViolation("EXPERIENCE_PHASE_INVALID", [f"$: {phase}"])
    if run["phases"][phase]["status"] in {"SEALED", "AVAILABLE"}:
        code = "BEFORE_EVIDENCE_IMMUTABLE" if phase == "before" else "EXPERIENCE_PHASE_SEALED"
        raise ContractViolation(code, [f"$: {phase} is sealed"])
    rel = _safe_relative(relative_path)
    raw = data.encode("utf-8") if isinstance(data, str) else bytes(data)
    target = _write_exclusive(root / phase, rel, raw)
    return {"phase": phase, "path": rel, "sha256": sha256_hex(raw), "bytes": len(raw), "resolved": str(target)}


def seal_before(run_dir: str | Path) -> dict[str, Any]:
    root = Path(run_dir).expanduser().resolve()
    run = load_experience_run(root)
    if run["phases"]["before"]["status"] == "SEALED":
        raise ContractViolation("BEFORE_EVIDENCE_IMMUTABLE", ["$: Before already sealed"])
    files = _phase_files(root / "before")
    if not files:
        raise ContractViolation("BEFORE_EVIDENCE_REQUIRED", ["$: Before contains no evidence"])
    baseline = digest_json({"files": files, "conditionsDigest": run["conditionsDigest"], "targetDigest": run["targetDigest"], "taskId": run["taskId"], "sessionId": run["sessionId"]})
    body = _manifest_payload("before", files, run, baseline_digest=baseline)
    manifest_digest = digest_json(body)
    _, key = _read_config(root)
    manifest = {**body, "manifestDigest": manifest_digest, "integrityMac": _mac(key, {"phase": "before", "manifestDigest": manifest_digest, "runId": run["runId"]})}
    seal_body = {"schemaVersion": "2", "phase": "before", "runId": run["runId"], "manifestDigest": manifest_digest, "baselineDigest": baseline}
    seal = {**seal_body, "integrityMac": _mac(key, seal_body)}
    _write_exclusive(root / "before", "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8"))
    _write_exclusive(root / "before", ".sealed", json.dumps(seal, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8"))
    _append_transition(root, "BEFORE_SEALED", {"manifestDigest": manifest_digest, "baselineDigest": baseline})
    _validate_phase(root, "before")
    return manifest


def validate_after_binding(
    run_dir: str | Path,
    *,
    task_id: str,
    target: Mapping[str, Any],
    conditions: Mapping[str, Any],
    baseline_digest: str | None = None,
    session_id: str | None = None,
    mode: str | None = None,
) -> dict[str, Any]:
    root = Path(run_dir).expanduser().resolve()
    run = load_experience_run(root)
    before = _validate_phase(root, "before")
    expected_baseline = str(run.get("baselineDigest") or before.get("baselineDigest") or "")
    if baseline_digest is not None and baseline_digest != expected_baseline:
        raise ContractViolation("BASELINE_IDENTITY_MISMATCH", ["$: baselineDigest does not match"])
    if task_id != run.get("taskId") or (session_id is not None and session_id != run.get("sessionId")) or (mode is not None and mode != run.get("mode")):
        raise ContractViolation("BASELINE_IDENTITY_MISMATCH", ["$: task, session, or mode does not match Before"])
    target_digest = digest_json(dict(target))
    if target_digest != run.get("targetDigest"):
        raise ContractViolation("TARGET_IDENTITY_MISMATCH", ["$: target identity differs from Before"])
    conditions_digest = digest_json(dict(conditions))
    if conditions_digest != run.get("conditionsDigest"):
        raise ContractViolation("CONDITIONS_MISMATCH", ["$: After conditions differ from Before"])
    return {"status": "BOUND", "runId": run["runId"], "baselineDigest": expected_baseline, "conditionsDigest": conditions_digest, "targetDigest": target_digest, "ledgerDigest": run["ledgerDigest"]}


def seal_after(run_dir: str | Path) -> dict[str, Any]:
    root = Path(run_dir).expanduser().resolve()
    run = load_experience_run(root)
    _validate_phase(root, "before")
    if run["phases"]["after"]["status"] == "SEALED":
        raise ContractViolation("EXPERIENCE_PHASE_SEALED", ["$: After already sealed"])
    files = _phase_files(root / "after")
    if not files:
        raise ContractViolation("AFTER_EVIDENCE_REQUIRED", ["$: After contains no evidence"])
    body = _manifest_payload("after", files, run, baseline_digest=run["baselineDigest"])
    manifest_digest = digest_json(body)
    _, key = _read_config(root)
    manifest = {**body, "manifestDigest": manifest_digest, "integrityMac": _mac(key, {"phase": "after", "manifestDigest": manifest_digest, "runId": run["runId"]})}
    phase_digest = digest_json(manifest)
    seal_body = {"schemaVersion": "2", "phase": "after", "runId": run["runId"], "manifestDigest": manifest_digest, "phaseDigest": phase_digest, "baselineDigest": run["baselineDigest"]}
    seal = {**seal_body, "integrityMac": _mac(key, seal_body)}
    _write_exclusive(root / "after", "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8"))
    _write_exclusive(root / "after", ".sealed", json.dumps(seal, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8"))
    _append_transition(root, "AFTER_SEALED", {"manifestDigest": manifest_digest, "phaseDigest": phase_digest, "baselineDigest": run["baselineDigest"]})
    _validate_phase(root, "after")
    return manifest


def record_phase_artifact(run_dir: str | Path, phase: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    """Seal a conclusion phase with the same manifest model used by Before/After.

    Recording only a caller supplied digest would leave the layer users actually
    read unprotected: the compare verdict or the final report could be rewritten
    on disk afterwards with no tamper signal. The payload is therefore persisted
    as evidence, hashed into a signed manifest, and bound to the ledger.
    """
    if phase not in {"compare", "report"}:
        raise ContractViolation("EXPERIENCE_PHASE_INVALID", [f"$: {phase}"])
    root = Path(run_dir).expanduser().resolve()
    run = load_experience_run(root)
    _validate_phase(root, "before")
    if phase == "compare":
        _validate_phase(root, "after")
    if run["phases"][phase]["status"] == "SEALED":
        raise ContractViolation("EXPERIENCE_PHASE_SEALED", [f"$: {phase} already sealed"])
    phase_dir = root / phase
    if not _phase_files(phase_dir):
        raise ContractViolation(
            "EXPERIENCE_PHASE_EVIDENCE_REQUIRED",
            [f"$: {phase} contains no evidence to support its conclusion"],
        )
    payload_digest = digest_json(dict(payload))
    _write_exclusive(phase_dir, _PHASE_ARTIFACT, _canonical_payload_bytes(payload))
    files = _phase_files(phase_dir)
    body = _manifest_payload(phase, files, run, baseline_digest=run["baselineDigest"], payload_digest=payload_digest)
    manifest_digest = digest_json(body)
    _, key = _read_config(root)
    manifest = {**body, "manifestDigest": manifest_digest, "integrityMac": _mac(key, {"phase": phase, "manifestDigest": manifest_digest, "runId": run["runId"]})}
    seal_body = {"schemaVersion": "2", "phase": phase, "runId": run["runId"], "manifestDigest": manifest_digest, "payloadDigest": payload_digest, "baselineDigest": run["baselineDigest"]}
    seal = {**seal_body, "integrityMac": _mac(key, seal_body)}
    _write_exclusive(phase_dir, "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8"))
    _write_exclusive(phase_dir, ".sealed", json.dumps(seal, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8"))
    _append_transition(root, _PHASE_EVENTS[phase], {"digest": payload_digest, "manifestDigest": manifest_digest, "baselineDigest": run["baselineDigest"]})
    _validate_phase(root, phase)
    return manifest


__all__ = [
    "create_experience_run", "load_experience_run", "write_phase_file", "seal_before",
    "validate_after_binding", "seal_after", "record_phase_artifact",
]
