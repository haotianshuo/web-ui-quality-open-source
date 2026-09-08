from __future__ import annotations

import hashlib
import importlib.util
import json
import zipfile
from pathlib import Path


def _ga_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "ga_promotion.py"
    spec = importlib.util.spec_from_file_location("wuq_ga_promotion_430_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _browser_record(runtime: str, *, browser_backed: bool = False) -> dict:
    record = {
        "runtime": runtime,
        "moduleAvailable": True,
        "browserExecutableAvailable": True,
        "executed": True,
        "status": "PASS",
        "reason": None,
    }
    if browser_backed:
        record.update({"browserBacked": True, "executionBranch": "LIVE_NODE_PLAYWRIGHT"})
    return record


def _valid_full_gate(ga) -> dict:
    release_gate = ga._load_release_gate_module()
    commands = release_gate.build_gate_commands("full")
    identities = [release_gate.gate_command_identity(command) for command in commands]
    rows = [{"command": list(command), "status": "PASS", "exitCode": 0} for command in commands]
    status_rows = [
        {"index": index, "command": identity, "status": row["status"], "exitCode": row["exitCode"]}
        for index, (identity, row) in enumerate(zip(identities, rows), start=1)
    ]
    return {
        "status": "PASS",
        "mode": "full",
        "requiredGateCount": 33,
        "passedGateCount": 33,
        "gates": rows,
        "worker": {
            "status": "PASS",
            "exitCode": 0,
            "execution": {
                "commandCount": 33,
                "commandDigest": ga._json_digest(identities),
                "statusRowsDigest": ga._json_digest(status_rows),
                "timedOut": False,
                "processTreeCleanup": {"residueFree": True},
                "stdoutSha256": "a" * 64,
                "stderrSha256": "b" * 64,
            },
        },
    }


def _live_browser_record(ga, *, browser_backed: bool) -> dict:
    record = _browser_record("node-playwright", browser_backed=browser_backed)
    record.update({
        "command": ["node", "browser-check"],
        "executionBranch": "LIVE_NODE_PLAYWRIGHT",
        "receiptSha256": "a" * 64,
        "executionRecord": {
            "status": "PASS",
            "executed": True,
            "browserExecutable": "chrome.exe",
            "commandDigest": "b" * 64,
            "reportSha256": "c" * 64,
        },
    })
    return record


def test_ga_promotion_rejects_a_self_consistent_one_file_candidate(tmp_path) -> None:
    ga = _ga_module()
    candidate = tmp_path / "candidate.zip"
    tree_digest = "a" * 64
    manifest = {
        "packageVersion": "4.3.0",
        "packageTreeDigest": tree_digest,
    }
    with zipfile.ZipFile(candidate, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("web-ui-quality/RELEASE-MANIFEST.json", json.dumps(manifest))

    evidence = tmp_path / "release-evidence-4.3.0"
    result = ga.evaluate(candidate, evidence)

    assert result["decision"] == "NOT_ELIGIBLE"
    assert any(item["code"] == "CANDIDATE_ARCHIVE_CONTENT_INVALID" for item in result["blockers"])


def test_full_gate_validation_requires_detailed_worker_receipt() -> None:
    ga = _ga_module()
    result, detail = ga._validate_full_gate({
        "status": "PASS",
        "mode": "full",
        "requiredGateCount": 33,
        "passedGateCount": 33,
        "gates": [{"command": ["python", "-c", "pass"], "status": "PASS", "exitCode": 0}] * 33,
    })
    assert result is False
    assert detail["reason"]


def test_full_gate_rejects_32_of_33_even_with_a_valid_worker_receipt() -> None:
    ga = _ga_module()
    value = _valid_full_gate(ga)
    value["passedGateCount"] = 32

    result, detail = ga._validate_full_gate(value)

    assert result is False
    assert detail["reason"]


def test_full_gate_rejects_tampered_status_row_digest() -> None:
    ga = _ga_module()
    value = _valid_full_gate(ga)
    value["worker"]["execution"]["statusRowsDigest"] = "d" * 64

    result, detail = ga._validate_full_gate(value)

    assert result is False
    assert "digest" in detail["reason"]


def test_browser_qualification_rejects_unverified_or_unbacked_branches() -> None:
    ga = _ga_module()
    live = _live_browser_record(ga, browser_backed=True)

    assert ga._browser_record_ok(live) is True
    live["status"] = "NOT_VERIFIED"
    assert ga._browser_record_ok(live) is False

    unbacked = _live_browser_record(ga, browser_backed=False)
    assert ga._browser_record_ok(unbacked, require_browser_backed=True) is False


def test_promotion_uses_only_canonical_tests_json() -> None:
    ga = _ga_module()

    assert ga._TEST_EVIDENCE_NAMES == ("tests.json",)


def test_preview_validation_rejects_empty_shell() -> None:
    ga = _ga_module()
    result, detail = ga._validate_preview_evidence({"releaseRunId": "run", "status": "PASS"}, Path.cwd())
    assert result is False
    assert detail["reason"]


def test_ga_promotion_is_not_eligible_without_evidence(tmp_path) -> None:
    ga = _ga_module()
    result = ga.evaluate(tmp_path / "missing.zip", tmp_path / "release-evidence-4.3.0")

    assert result["decision"] == "NOT_ELIGIBLE"
    assert any(item["code"] == "CANDIDATE_ARCHIVE_MISSING" for item in result["blockers"])
