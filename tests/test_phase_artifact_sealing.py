"""Regression tests: compare and report must be sealed like before and after.

The final report is what the user actually reads. Recording only a caller
supplied payload digest leaves the conclusion layer unprotected: PASS could be
rewritten to FAIL after the fact without any tamper signal.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from web_ui_quality.contracts import ContractViolation
from web_ui_quality.experience_run import (
    create_experience_run,
    load_experience_run,
    record_phase_artifact,
    seal_after,
    seal_before,
    validate_after_binding,
    write_phase_file,
)

TARGET = {"url": "http://localhost:3000"}
CONDITIONS = {"viewport": "1440x900"}


def _completed_run(tmp_path: Path) -> Path:
    arts = tmp_path / "arts"
    arts.mkdir()
    run = create_experience_run(
        arts, task_id="T", session_id="S", mode="CHECK",
        target=TARGET, conditions=CONDITIONS, run_id="wuq-aaaabbbbccccdddd",
    )
    run_dir = Path(run["runDir"])
    write_phase_file(run_dir, "before", "shot.txt", "before-pixels")
    seal_before(run_dir)
    validate_after_binding(
        run_dir, task_id="T", session_id="S", target=TARGET, conditions=CONDITIONS,
    )
    write_phase_file(run_dir, "after", "shot.txt", "after-pixels")
    seal_after(run_dir)
    return run_dir


def _write_report(run_dir: Path, payload: dict) -> dict:
    write_phase_file(run_dir, "report", "final.json", json.dumps(payload))
    return record_phase_artifact(run_dir, "report", payload)


def test_report_payload_tampering_is_detected(tmp_path: Path) -> None:
    """Rewriting the sealed report file on disk must fail verification."""
    run_dir = _completed_run(tmp_path)
    _write_report(run_dir, {"status": "PASS", "top3": ["a", "b", "c"]})

    target = run_dir / "report" / "final.json"
    target.write_text(json.dumps({"status": "FAIL", "top3": ["x"]}), encoding="utf-8")

    with pytest.raises(ContractViolation) as excinfo:
        load_experience_run(run_dir)
    assert excinfo.value.code in {"EVIDENCE_MANIFEST_MISMATCH", "RUN_STATE_TAMPERED"}


def test_report_seal_removal_is_detected(tmp_path: Path) -> None:
    """Deleting the report seal must not silently downgrade the phase."""
    run_dir = _completed_run(tmp_path)
    _write_report(run_dir, {"status": "PASS"})

    (run_dir / "report" / ".sealed").unlink()

    with pytest.raises(ContractViolation):
        load_experience_run(run_dir)


def test_report_phase_is_sealed_with_manifest_and_seal(tmp_path: Path) -> None:
    """Report must use the same manifest plus seal model as before and after."""
    run_dir = _completed_run(tmp_path)
    result = _write_report(run_dir, {"status": "PASS"})

    assert (run_dir / "report" / "manifest.json").is_file()
    assert (run_dir / "report" / ".sealed").is_file()
    assert result["manifestDigest"]
    assert load_experience_run(run_dir)["phases"]["report"]["status"] == "SEALED"


def test_compare_payload_tampering_is_detected(tmp_path: Path) -> None:
    """The compare phase carries the improvement claim and needs the same guard."""
    run_dir = _completed_run(tmp_path)
    write_phase_file(run_dir, "compare", "diff.json", json.dumps({"delta": "improved"}))
    record_phase_artifact(run_dir, "compare", {"delta": "improved"})

    (run_dir / "compare" / "diff.json").write_text(
        json.dumps({"delta": "regressed"}), encoding="utf-8"
    )

    with pytest.raises(ContractViolation):
        load_experience_run(run_dir)


def test_recorded_payload_is_persisted_as_evidence(tmp_path: Path) -> None:
    """The recorded conclusion must exist on disk under the signed manifest.

    Callers may write a rich phase file and record a summary payload, so the
    payload itself needs to be sealed evidence rather than an unverifiable digest.
    """
    run_dir = _completed_run(tmp_path)
    write_phase_file(run_dir, "report", "final.json", json.dumps({"status": "PASS"}))
    manifest = record_phase_artifact(run_dir, "report", {"status": "PASS", "top3": ["a"]})

    artifact = run_dir / "report" / "artifact.json"
    assert json.loads(artifact.read_text(encoding="utf-8")) == {"status": "PASS", "top3": ["a"]}
    assert "artifact.json" in {row["path"] for row in manifest["files"]}
    assert manifest["payloadDigest"]


def test_recorded_payload_tampering_is_detected(tmp_path: Path) -> None:
    """Rewriting the recorded payload must fail verification."""
    run_dir = _completed_run(tmp_path)
    write_phase_file(run_dir, "report", "final.json", json.dumps({"status": "PASS"}))
    record_phase_artifact(run_dir, "report", {"status": "PASS"})

    (run_dir / "report" / "artifact.json").write_text(
        json.dumps({"status": "FAIL"}), encoding="utf-8"
    )

    with pytest.raises(ContractViolation):
        load_experience_run(run_dir)


def test_report_cannot_be_sealed_twice(tmp_path: Path) -> None:
    """Re-sealing would allow replacing an already published conclusion."""
    run_dir = _completed_run(tmp_path)
    _write_report(run_dir, {"status": "PASS"})

    with pytest.raises(ContractViolation):
        record_phase_artifact(run_dir, "report", {"status": "PASS"})


def test_compare_requires_evidence_files(tmp_path: Path) -> None:
    """Sealing an empty phase would create evidence-free authority."""
    run_dir = _completed_run(tmp_path)

    with pytest.raises(ContractViolation):
        record_phase_artifact(run_dir, "compare", {"delta": "improved"})
