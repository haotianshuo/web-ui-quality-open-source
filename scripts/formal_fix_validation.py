#!/usr/bin/env python3
"""Run the bounded, contract-driven Formal Qualification fix validation.

This runner consumes the immutable Formal fixture/oracles read-only, creates a
fresh fixture clone for every selected Treatment execution, and writes only
new validation evidence.  It deliberately does not call the historical full
Formal runner or its task-ID-specific claim logic.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import re
import subprocess
import sys
import tempfile
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Mapping
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime" / "python"
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

MATRIX = [(390, 844), (768, 1024), (1440, 900)]
MATRIX_SET = set(MATRIX)
BASELINE_SHA = "f6f830942fb9dd2fe4ae188934fa20e00662ab98"
FIXTURE_SHA = "de36ac253d942f2f3805230ce8a2083a9b56d56c"
RECEIPT_KEY = b"formal-codex-host-receipt-key-20260910"
MODEL = "Local Treatment validation Host"

ROUND_TASKS: dict[int, tuple[str, ...]] = {
    1: ("Q05", "Q12", "Q14", "Q15", "Q16", "Q17", "Q19", "Q20", "Q28", "Q30"),
    2: ("Q16", "Q17", "Q28", "Q19"),
    3: ("Q12", "Q14", "Q16", "Q28", "Q20"),
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args], check=True, capture_output=True,
        text=True, encoding="utf-8", errors="replace",
    )
    return result.stdout.strip()


def _tracked_hashes(root: Path) -> dict[str, str]:
    files = [item for item in _git(root, "ls-files").splitlines() if item.strip()]
    return {item.replace("\\", "/"): _sha256_file(root / item) for item in files}


def _manifest_digest(hashes: Mapping[str, str]) -> str:
    body = json.dumps(dict(sorted(hashes.items())), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _sha256_bytes(body)


def _origin(url: str) -> str:
    parsed = urlsplit(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def _port(url: str) -> int | None:
    return urlsplit(url).port


def _task_field(body: str, name: str, task_id: str) -> str:
    match = re.search(rf"^- {re.escape(name)}: `([^`]*)`", body, flags=re.MULTILINE)
    if not match:
        raise RuntimeError(f"missing {name} for {task_id}")
    return match.group(1)


def _parse_allowed(raw: str) -> list[str]:
    if raw == "[]":
        return []
    return [item.strip() for item in raw.strip("[]").split(",") if item.strip()]


def _load_tasks(formal_root: Path) -> dict[str, dict[str, Any]]:
    markdown = (formal_root / "FORMAL_QUALIFICATION_TASK_FREEZE.md").read_text(encoding="utf-8")
    blocks = re.split(r"^## (Q\d+) — .+$", markdown, flags=re.MULTILINE)
    parsed: dict[str, dict[str, Any]] = {}
    for index in range(1, len(blocks), 2):
        task_id, body = blocks[index:index + 2]
        if not task_id.startswith("Q"):
            continue
        parsed[task_id] = {
            "taskId": task_id,
            "taskText": _task_field(body, "taskText", task_id),
            "fixturePath": _task_field(body, "fixturePath", task_id),
            "scope": _task_field(body, "scope", task_id),
            "allowedWrites": _parse_allowed(_task_field(body, "allowedWrites", task_id)),
            "browserTarget": _task_field(body, "browserTarget", task_id),
        }
    oracles = json.loads((formal_root / "FORMAL_QUALIFICATION_ORACLES.json").read_text(encoding="utf-8"))
    oracle_map = {str(row["taskId"]): dict(row) for row in oracles["tasks"]}
    for task_id, task in parsed.items():
        if task_id not in oracle_map:
            raise RuntimeError(f"oracle missing for {task_id}")
        markdown_allowed = list(task["allowedWrites"])
        task.update(oracle_map[task_id])
        if markdown_allowed != list(task.get("allowedWrites") or []):
            raise RuntimeError(f"task/oracle scope mismatch for {task_id}")
    if len(parsed) != 30:
        raise RuntimeError(f"expected 30 frozen task inputs, got {len(parsed)}")
    return parsed


def _load_freeze() -> tuple[dict[str, Any], str]:
    path = ROOT / "FORMAL_FIX_TASK_FREEZE.json"
    freeze = json.loads(path.read_text(encoding="utf-8"))
    return freeze, _sha256_file(path)


@contextmanager
def _live_server(root: Path, port: int) -> Iterator[None]:
    from browser_probe import start_server

    process = start_server(root, port)
    try:
        yield
    finally:
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)


def _probe(root: Path, evidence_path: Path, url: str, page_id: str, *, live: bool) -> dict[str, Any]:
    from browser_probe import probe

    screenshot_dir = evidence_path.parent / (evidence_path.stem + "-screenshots")
    if live:
        port = _port(url)
        if port is None:
            raise RuntimeError(f"live target has no port: {url}")
        result = probe(url, page_id, screenshot_dir, start_root=root, start_port=port)
    else:
        result = probe(url, page_id, screenshot_dir)
    _json(evidence_path, result)
    return result


def _records(probe_result: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    return [row for row in list((probe_result or {}).get("records") or []) if isinstance(row, Mapping)]


def _healthy(probe_result: Mapping[str, Any] | None) -> bool:
    rows = _records(probe_result)
    return bool(rows) and all(
        row.get("httpStatus") == 200
        and not row.get("navigationError")
        and not list(row.get("pageErrors") or [])
        for row in rows
    )


def _matrix_complete(probe_result: Mapping[str, Any] | None) -> bool:
    observed = {
        (int((row.get("requestedViewport") or {}).get("width", -1)), int((row.get("requestedViewport") or {}).get("height", -1)))
        for row in _records(probe_result)
    }
    return observed == MATRIX_SET and len(_records(probe_result)) == len(MATRIX)


def _no_overflow(probe_result: Mapping[str, Any] | None) -> bool:
    rows = _records(probe_result)
    return bool(rows) and all(
        float((row.get("metric") or {}).get("documentScrollWidth", 0))
        <= float((row.get("metric") or {}).get("clientWidth", -1)) + 0.5
        for row in rows
    )


def _runtime_good(probe_result: Mapping[str, Any] | None) -> bool:
    return _healthy(probe_result) and all(
        str(((row.get("metric") or {}).get("statusText")) or "") == "Active"
        for row in _records(probe_result)
    )


def _focus_good(probe_result: Mapping[str, Any] | None) -> bool:
    rows = _records(probe_result)
    if not rows:
        return False
    for row in rows:
        metric = row.get("metric") or {}
        outline = str(metric.get("outlineStyle") or "") not in {"", "none"}
        try:
            width = float(str(metric.get("outlineWidth") or "0").replace("px", ""))
        except (TypeError, ValueError):
            width = 0
        shadow = str(metric.get("boxShadow") or "") not in {"", "none"}
        if not bool(metric.get("active")) or not ((outline and width > 0) or shadow):
            return False
    return True


def _contrast_good(probe_result: Mapping[str, Any] | None) -> bool:
    rows = _records(probe_result)
    return bool(rows) and all(float(((row.get("metric") or {}).get("contrastRatio")) or 0) >= 4.5 for row in rows)


def _clipping_good(probe_result: Mapping[str, Any] | None) -> bool:
    rows = _records(probe_result)
    return bool(rows) and all(
        float(((row.get("metric") or {}).get("scrollHeight")) or 99999)
        <= float(((row.get("metric") or {}).get("clientHeight")) or 0) + 0.5
        for row in rows
    )


def _repair_before_good(oracle: Mapping[str, Any], probe_result: Mapping[str, Any] | None) -> bool:
    prop = str(oracle.get("property") or "")
    rows = _records(probe_result)
    if prop == "runtime-status":
        return bool(rows) and any(row.get("pageErrors") and "Waiting" in str(((row.get("metric") or {}).get("statusText")) or "") for row in rows)
    if prop == "focus-visibility":
        return bool(rows) and not _focus_good(probe_result)
    if prop == "contrast":
        return bool(rows) and any(float(((row.get("metric") or {}).get("contrastRatio")) or 99) < 4.5 for row in rows)
    if prop == "content-clipping":
        return bool(rows) and any(
            float(((row.get("metric") or {}).get("scrollHeight")) or 0) > float(((row.get("metric") or {}).get("clientHeight")) or -1) + 0.5
            and (row.get("metric") or {}).get("overflowY") == "hidden"
            for row in rows
        )
    if prop == "horizontal-overflow":
        return bool(rows) and not _no_overflow(probe_result)
    return False


def _oracle_claim(task: Mapping[str, Any], before: Mapping[str, Any] | None, after: Mapping[str, Any] | None) -> str:
    category = str(task.get("category") or "")
    prop = str(task.get("property") or "")
    if category == "clean-negative":
        return "CLEAN_CONFIRMED" if _healthy(before) and _no_overflow(before) and _matrix_complete(before) else "NOT_VERIFIED"
    if category == "evidence-insufficient":
        return "NOT_VERIFIED"
    if prop == "runtime-status":
        good = _repair_before_good(task, before) and _runtime_good(after) and _matrix_complete(after)
    elif prop == "focus-visibility":
        good = _repair_before_good(task, before) and _healthy(after) and _focus_good(after) and _matrix_complete(after)
    elif prop == "contrast":
        good = _repair_before_good(task, before) and _healthy(after) and _contrast_good(after) and _matrix_complete(after)
    elif prop == "content-clipping":
        good = _repair_before_good(task, before) and _healthy(after) and _clipping_good(after) and _matrix_complete(after)
    elif prop == "horizontal-overflow":
        good = _repair_before_good(task, before) and _healthy(after) and _no_overflow(after) and _matrix_complete(after)
    else:
        good = False
    return str(task.get("oracleClass")) if good else "NOT_VERIFIED"


def _replace_once(raw: bytes, pattern: str, replacement: str, *, flags: int = 0) -> bytes:
    newline = "\r\n" if b"\r\n" in raw else "\n"
    text = raw.decode("utf-8").replace("\r\n", "\n")
    updated, count = re.subn(pattern, replacement, text, count=1, flags=flags)
    if count != 1:
        raise RuntimeError(f"Host patch anchor count for {pattern!r}: {count}")
    return updated.replace("\n", newline).encode("utf-8")


def _test_id(oracle: Mapping[str, Any]) -> str:
    match = re.search(r"data-testid=['\"]([^'\"]+)['\"]", str(oracle.get("targetSelector") or ""))
    if not match:
        raise RuntimeError("oracle targetSelector has no data-testid")
    return match.group(1)


def _target_class(test_id: str) -> str:
    return test_id


def _host_after_bytes(oracle: Mapping[str, Any], before: bytes) -> bytes:
    prop = str(oracle.get("property") or "")
    test_id = _test_id(oracle)
    class_name = _target_class(test_id)
    if prop == "runtime-status":
        return _replace_once(
            before,
            r'const\s+\w+\s*=\s*document\.querySelector\("#[^"]+"\);\n\s*\w+\.textContent\s*=\s*"Active";',
            f'const status = document.querySelector("[data-testid=\'{test_id}\']");\n    status.textContent = "Active";',
        )
    if prop == "focus-visibility":
        pattern = rf"(?P<selector>\.{re.escape(class_name)}:focus(?:,\s*\.[A-Za-z0-9_-]+:focus)?)\s*\{{\s*outline:\s*none;\s*box-shadow:\s*none;\s*\}}"
        return _replace_once(before, pattern, r"\g<selector> { outline: 3px solid #1d4ed8; outline-offset: 2px; box-shadow: none; }")
    if prop == "contrast":
        pattern = rf"(\.{re.escape(class_name)}\s*\{{[^}}]*?background:\s*#efefef;\s*color:\s*)#c5c5c5;"
        return _replace_once(before, pattern, r"\g<1>#172033;")
    if prop == "content-clipping":
        pattern = rf"(\.{re.escape(class_name)}\s*\{{[^}}]*?)height:\s*96px;\s*overflow:\s*hidden;"
        return _replace_once(before, pattern, r"\g<1>min-height: 96px; height: auto; overflow: visible;")
    if prop == "horizontal-overflow":
        pattern = rf"(\.{re.escape(class_name)}\s*\{{[^}}]*?width:\s*)(\d+px);"
        return _replace_once(before, pattern, r"\g<1>100%; max-width: \g<2>;")
    raise RuntimeError(f"no generic Host patch for oracle property {prop!r}")


def _make_receipt(binding: Mapping[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schemaVersion": "3", "receiptProtocolVersion": "3.0", "pluginVersion": "4.3.0", "kernelVersion": "4.2.3",
        "receiptId": "receipt-" + uuid.uuid4().hex,
        "packageTreeDigest": binding["packageTreeDigest"], "activationId": binding["activationId"], "runId": binding["runId"],
        "sessionId": binding["sessionId"], "taskId": binding["taskId"], "nonce": binding["nonce"], "issuedAt": binding["issuedAt"],
        "expiresAt": binding["expiresAt"], "freshnessEpoch": binding["freshnessEpoch"], "baselineDigest": binding["baselineDigest"],
        "targetDigest": binding["targetDigest"], "changeSetDigest": binding["changeSetDigest"], "verificationPolicyDigest": binding["verificationPolicyDigest"],
        "hostIdentity": binding["hostIdentity"], "attestationIdentity": binding["attestationIdentity"],
        "authorizationTicketDigest": binding["authorizationTicketDigest"], "actualOperation": "EDIT", "applyResult": "APPLIED",
        "entries": [
            {"entryId": f"entry-{index:02d}", "canonicalPath": row["canonicalPath"], "actualOperation": "EDIT", "entryResult": "APPLIED",
             "actualBeforeHash": row["expectedBeforeHash"], "actualAfterHash": row["intendedAfterHash"], "reasonCode": None}
            for index, row in enumerate(binding["entries"], start=1)
        ],
        "receiptDigest": "", "integrityMechanism": "HMAC_SHA256", "integrityTag": "",
    }
    from web_ui_quality.contracts import digest_json

    payload["receiptDigest"] = digest_json({key: value for key, value in payload.items() if key not in {"receiptDigest", "integrityTag"}})
    payload["integrityTag"] = "hmac:" + hmac.new(RECEIPT_KEY, payload["receiptDigest"].encode("utf-8"), hashlib.sha256).hexdigest()
    return payload


def _wuq(root: Path, artifacts: Path, task: Mapping[str, Any], *, task_id: str, session_id: str, mode: str, existing_run: Path | None = None, after_url: str | None = None, candidate: Mapping[str, Any] | None = None, receipt: Mapping[str, Any] | None = None) -> dict[str, Any]:
    from web_ui_quality.experience_fix import run_experience_fix

    url = str(task["browserTarget"])
    kwargs: dict[str, Any] = {
        "request": str(task["taskText"]), "mode": mode, "task_id": task_id, "session_id": session_id,
        "url": url, "files": list(task.get("allowedWrites") or []), "viewports": MATRIX,
        "locale": "zh-CN", "theme": "light", "browser": "chromium", "allowed_origins": [_origin(url)],
        "environment": "test", "auth_state": "anonymous",
    }
    if existing_run is not None:
        kwargs["existing_run"] = existing_run
    if after_url is not None:
        kwargs["after_url"] = after_url
    if candidate is not None:
        kwargs["host_patch_candidate"] = candidate
    if receipt is not None:
        kwargs["host_write_receipt"] = receipt
        kwargs["host_receipt_hmac_key"] = RECEIPT_KEY
    return run_experience_fix(root, artifacts, **kwargs)


def _summary_wuq(result: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(result, Mapping):
        return {}
    task_result = result.get("taskResult") if isinstance(result.get("taskResult"), Mapping) else {}
    comparison = result.get("comparison") if isinstance(result.get("comparison"), Mapping) else {}
    verification = result.get("repairVerification") if isinstance(result.get("repairVerification"), Mapping) else {}
    return {
        "status": result.get("status"), "mode": result.get("mode"), "runId": result.get("runId"),
        "hostWriteProtocol": result.get("hostWriteProtocol"), "comparisonStatus": comparison.get("status"),
        "repairVerificationStatus": verification.get("status"), "taskResultOutcome": task_result.get("outcome"),
        "taskResultReasonCode": task_result.get("reasonCode"), "runDir": result.get("runDir"),
    }


def _run_one(round_no: int, task: Mapping[str, Any], freeze_sha: str, formal_root: Path, evidence_root: Path) -> dict[str, Any]:
    from web_ui_quality.qualification_harness import expected_execution_contract, validate_frozen_task_result

    task_id = str(task["taskId"])
    contract = expected_execution_contract(task)
    run_label = f"R{round_no}-{task_id}-{uuid.uuid4().hex[:10]}"
    arm_root = evidence_root / run_label
    clone = arm_root / "fixture"
    arm_root.mkdir(parents=True, exist_ok=False)
    subprocess.run(["git", "clone", "--quiet", "--no-hardlinks", str(formal_root / "qualification-fixture"), str(clone)], check=True, capture_output=True, text=True)
    start_tree = _git(clone, "rev-parse", "HEAD")
    if start_tree != FIXTURE_SHA:
        raise RuntimeError(f"fixture SHA mismatch for {run_label}: {start_tree}")
    baseline = _tracked_hashes(clone)
    url = str(task["browserTarget"])
    live = str(task.get("property") or "") != "unreachable-target"
    before = _probe(clone, arm_root / "browser-before.json", url, str(task["pageId"]), live=live)
    session_id = f"formal-fix-validation-r{round_no}-{task_id.lower()}-{uuid.uuid4().hex[:8]}"
    internal_task_id = f"formal-fix-validation-r{round_no}-{task_id.lower()}"
    before_wuq: dict[str, Any] = {}
    prepared_wuq: dict[str, Any] = {}
    final_wuq: dict[str, Any] = {}
    after: dict[str, Any] | None = None
    receipt_status = "NOT_APPLICABLE"
    candidate_status = "NOT_APPLICABLE"

    if contract["mode"] == "FIX_AND_VERIFY":
        port = _port(url)
        if port is None:
            raise RuntimeError(f"repair target has no port: {url}")
        with _live_server(clone, port):
            before_wuq = _wuq(clone, arm_root / "wuq", task, task_id=internal_task_id, session_id=session_id, mode="FIX_AND_VERIFY")
        _json(arm_root / "wuq-before-summary.json", _summary_wuq(before_wuq))
        if str(before_wuq.get("mode") or "").upper() != "FIX_AND_VERIFY":
            raise RuntimeError(f"WUQ did not enter FIX_AND_VERIFY for {run_label}: {before_wuq.get('mode')!r}")
        run_path = arm_root / "wuq" / str(before_wuq["runId"])
        source_path = clone / str(task["allowedWrites"][0])
        before_bytes = source_path.read_bytes()
        after_bytes = _host_after_bytes(task, before_bytes)
        candidate = {
            "runId": before_wuq["runId"], "taskId": internal_task_id, "sessionId": session_id,
            "hostIdentity": MODEL, "attestationIdentity": f"formal-fix-validation-{run_label}",
            "entries": [{"canonicalPath": str(task["allowedWrites"][0]), "operation": "EDIT", "expectedBeforeHash": _sha256_bytes(before_bytes), "intendedAfterHash": _sha256_bytes(after_bytes)}],
        }
        _json(arm_root / "host-patch-candidate.json", candidate)
        with _live_server(clone, port):
            prepared_wuq = _wuq(clone, arm_root / "wuq", task, task_id=internal_task_id, session_id=session_id, mode="FIX_AND_VERIFY", existing_run=run_path, candidate=candidate)
        _json(arm_root / "wuq-prepared-summary.json", _summary_wuq(prepared_wuq))
        binding = prepared_wuq.get("hostApplyBindingV3")
        if not isinstance(binding, Mapping):
            path = run_path / "report" / "host-apply-binding-v3.json"
            if path.is_file():
                binding = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(binding, Mapping):
            raise RuntimeError(f"WUQ did not produce V3 binding for {run_label}")
        candidate_status = "BOUND_V3"
        source_path.write_bytes(after_bytes)
        receipt = _make_receipt(binding)
        _json(arm_root / "host-write-receipt-v3.json", receipt)
        receipt_status = "CREATED_FOR_LOCAL_TREATMENT_VALIDATION"
        with _live_server(clone, port):
            final_wuq = _wuq(clone, arm_root / "wuq", task, task_id=internal_task_id, session_id=session_id, mode="FIX_AND_VERIFY", existing_run=run_path, after_url=url, receipt=receipt)
        _json(arm_root / "wuq-final-summary.json", _summary_wuq(final_wuq))
        after = _probe(clone, arm_root / "browser-after.json", url, str(task["pageId"]), live=live)
    else:
        port = _port(url)
        if live and port is not None:
            with _live_server(clone, port):
                final_wuq = _wuq(clone, arm_root / "wuq", task, task_id=internal_task_id, session_id=session_id, mode="CHECK")
        else:
            final_wuq = _wuq(clone, arm_root / "wuq", task, task_id=internal_task_id, session_id=session_id, mode="CHECK")
        _json(arm_root / "wuq-final-summary.json", _summary_wuq(final_wuq))

    claim = _oracle_claim(task, before, after)
    end_hashes = _tracked_hashes(clone)
    changed = sorted({path for path, value in end_hashes.items() if baseline.get(path) != value} | {path for path in end_hashes if path not in baseline})
    allowed = {str(item).replace("\\", "/") for item in list(task.get("allowedWrites") or [])}
    protected_files = task.get("protectedFiles")
    if isinstance(protected_files, list):
        protected_rows = list(protected_files)
    elif str(protected_files) == "all-other-tracked":
        protected_rows = [path for path in baseline if path not in allowed]
    else:
        protected_rows = list(baseline)
    protected_ok = all(end_hashes.get(str(path)) == baseline.get(str(path)) for path in protected_rows)
    scope_ok = set(changed) <= allowed and protected_ok
    before_matrix = _matrix_complete(before)
    after_matrix = _matrix_complete(after) if contract["mode"] == "FIX_AND_VERIFY" else True
    wuq_final_summary = _summary_wuq(final_wuq)
    wuq_repair_gate = (
        contract["mode"] != "FIX_AND_VERIFY"
        or (
            wuq_final_summary.get("mode") == "FIX_AND_VERIFY"
            and wuq_final_summary.get("hostWriteProtocol") == "V3"
            and wuq_final_summary.get("comparisonStatus") == "IMPROVEMENT_CLAIM_ALLOWED"
            and wuq_final_summary.get("repairVerificationStatus") == "VERIFIED"
            and wuq_final_summary.get("taskResultOutcome") == "VERIFIED"
        )
    )
    observed = {"mode": wuq_final_summary.get("mode"), "finalClaim": claim, "taskResult": final_wuq.get("taskResult") if isinstance(final_wuq.get("taskResult"), Mapping) else {}}
    contract_result = validate_frozen_task_result(task, observed)
    false_verified = claim in {"CLEAN_CONFIRMED", "REPAIRED_VERIFIED", "RECOVERED_VERIFIED", "FINDING_CONFIRMED"} and str(task.get("oracleClass")) == "NOT_VERIFIED"
    pass_result = bool(
        contract_result["status"] == "PASS"
        and claim == str(task["oracleClass"])
        and scope_ok
        and before_matrix
        and after_matrix
        and not false_verified
        and wuq_repair_gate
    )
    record = {
        "schemaVersion": "1", "runId": run_label, "round": round_no, "taskId": task_id,
        "timestamp": _now(), "baselineSha": BASELINE_SHA, "fixtureSha": start_tree, "freezeSha256": freeze_sha,
        "browserMatrix": [{"width": width, "height": height} for width, height in MATRIX],
        "oracleClass": task["oracleClass"], "property": task["property"], "category": task["category"],
        "expectedExecution": contract, "observedMode": wuq_final_summary.get("mode"), "observedClaim": claim,
        "validation": "PASS" if pass_result else "NOT_VERIFIED",
        "contractValidation": contract_result,
        "negativeChecks": {
            "beforeDefectOrCleanCondition": _repair_before_good(task, before) if contract["mode"] == "FIX_AND_VERIFY" else claim == str(task["oracleClass"]),
            "beforeMatrixComplete": before_matrix, "afterMatrixComplete": after_matrix,
            "scopeExact": scope_ok, "protectedFilesUnchanged": protected_ok,
            "wuqRepairGate": wuq_repair_gate, "falseVerified": false_verified,
            "unexpectedWrites": sorted(set(changed) - allowed),
        },
        "source": {
            "startTree": start_tree, "endTree": _git(clone, "rev-parse", "HEAD"),
            "startManifest": _manifest_digest(baseline), "endManifest": _manifest_digest(end_hashes),
            "filesChanged": changed, "allowedWrites": sorted(allowed), "candidateStatus": candidate_status,
            "receiptStatus": receipt_status,
        },
        "browserEvidence": {
            "before": str((arm_root / "browser-before.json").resolve()),
            "after": str((arm_root / "browser-after.json").resolve()) if after is not None else None,
            "beforeRecords": len(_records(before)), "afterRecords": len(_records(after)),
            "beforePageErrors": sum(len(list(row.get("pageErrors") or [])) for row in _records(before)),
            "afterPageErrors": sum(len(list(row.get("pageErrors") or [])) for row in _records(after)),
        },
        "wuqEvidence": {
            "before": _summary_wuq(before_wuq), "prepared": _summary_wuq(prepared_wuq), "final": wuq_final_summary,
            "artifactRoot": str((arm_root / "wuq").resolve()),
        },
        "claimBoundary": "This record covers only the frozen task, the three Browser viewports, and the declared source scope. It is not full Formal, Holdout, Real Host, GA, or Open Source evidence.",
    }
    _json(arm_root / "validation-record.json", record)
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description="Run bounded Formal Qualification fix validation")
    parser.add_argument("--formal-root", type=Path, default=ROOT.parent / "formal-qualification-20260910")
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--only", dest="only_tasks", action="append", help="Debug-only task filter; may be repeated")
    parser.add_argument("--skip-ledger", action="store_true", help="Do not write the repository validation ledger (for debug runs)")
    args = parser.parse_args()
    formal_root = args.formal_root.resolve()
    if str(formal_root) not in sys.path:
        sys.path.insert(0, str(formal_root))
    freeze, freeze_sha = _load_freeze()
    if str(freeze.get("baselineSha")) != BASELINE_SHA or str(freeze.get("fixtureSha")) != FIXTURE_SHA:
        raise RuntimeError("fix freeze does not bind the required baseline/fixture")
    tasks = _load_tasks(formal_root)
    if str(_git(formal_root / "qualification-fixture", "rev-parse", "HEAD")) != FIXTURE_SHA:
        raise RuntimeError("immutable qualification fixture is not at the frozen SHA")
    selected_tasks = {str(value).strip() for value in (args.only_tasks or ()) if str(value).strip()}
    known_tasks = {task_id for task_ids in ROUND_TASKS.values() for task_id in task_ids}
    unknown_tasks = sorted(selected_tasks - known_tasks)
    if unknown_tasks:
        raise RuntimeError(f"unknown validation task filter: {', '.join(unknown_tasks)}")
    selected_round_tasks = {
        round_no: tuple(task_id for task_id in task_ids if not selected_tasks or task_id in selected_tasks)
        for round_no, task_ids in ROUND_TASKS.items()
    }
    evidence_root = (args.evidence_root or Path(tempfile.gettempdir()) / ("formal-fix-validation-" + uuid.uuid4().hex[:12])).resolve()
    evidence_root.mkdir(parents=True, exist_ok=False)
    records: list[dict[str, Any]] = []
    started = time.perf_counter()
    for round_no, task_ids in selected_round_tasks.items():
        for task_id in task_ids:
            print(f"START Round {round_no} {task_id}", flush=True)
            record = _run_one(round_no, tasks[task_id], freeze_sha, formal_root, evidence_root)
            records.append(record)
            print(f"DONE Round {round_no} {task_id} validation={record['validation']} claim={record['observedClaim']}", flush=True)
    if not args.skip_ledger:
        ledger_path = ROOT / "FORMAL_FIX_VALIDATION_LEDGER.jsonl"
        if ledger_path.exists():
            raise RuntimeError(f"refusing to overwrite existing validation ledger: {ledger_path}")
        with ledger_path.open("x", encoding="utf-8", newline="\n") as handle:
            for record in records:
                handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    summary = {
        "schemaVersion": "1", "baselineSha": BASELINE_SHA, "fixtureSha": FIXTURE_SHA, "freezeSha256": freeze_sha,
        "rounds": {str(round_no): list(task_ids) for round_no, task_ids in selected_round_tasks.items()},
        "recordCount": len(records), "passCount": sum(record["validation"] == "PASS" for record in records),
        "notVerifiedCount": sum(record["validation"] != "PASS" for record in records),
        "falseVerifiedCount": sum(bool(record["negativeChecks"]["falseVerified"]) for record in records),
        "evidenceRoot": str(evidence_root), "elapsedSeconds": round(time.perf_counter() - started, 3),
        "claimBoundary": "Bounded Treatment validation only; no full Formal rerun and no Real Host/GA/Open Source promotion.",
    }
    _json(evidence_root / "validation-summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True), flush=True)
    return 0 if summary["notVerifiedCount"] == 0 and summary["falseVerifiedCount"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
