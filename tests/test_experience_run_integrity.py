"""Attack cases the shipped acceptance script does not cover.

Each test names the specific tampering it simulates.  A silent PASS here means
evidence could be rewritten without the run being marked as tampered.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from conftest import CONDITIONS, TARGET


def _violation():
    from web_ui_quality.contracts import ContractViolation

    return ContractViolation


def _load(run_dir: Path):
    from web_ui_quality.experience_run import load_experience_run

    return load_experience_run(run_dir)


def test_ledger_middle_line_removal_is_detected(sealed_run):
    """Dropping an interior transition must break the hash chain."""
    ledger = sealed_run / "transitions.ndjson"
    lines = ledger.read_text(encoding="utf-8").splitlines(keepends=True)
    assert len(lines) >= 2, "need at least RUN_CREATED plus one transition"
    ledger.write_text("".join(lines[:-1]), encoding="utf-8")

    with pytest.raises(_violation()) as caught:
        _load(sealed_run)
    assert caught.value.code == "RUN_STATE_TAMPERED"


def test_ledger_truncated_to_run_created_invalidates_seal(sealed_run):
    """Rolling the ledger back to creation must not un-seal Before silently."""
    ledger = sealed_run / "transitions.ndjson"
    first = ledger.read_text(encoding="utf-8").splitlines(keepends=True)[0]
    ledger.write_text(first, encoding="utf-8")

    with pytest.raises(_violation()) as caught:
        _load(sealed_run)
    assert caught.value.code in {"RUN_STATE_TAMPERED", "BEFORE_EVIDENCE_REQUIRED"}


def test_seal_file_removal_is_detected(sealed_run):
    """A sealed phase without its seal record must not load as sealed."""
    (sealed_run / "before" / ".sealed").unlink()

    with pytest.raises(_violation()) as caught:
        _load(sealed_run)
    assert caught.value.code == "BEFORE_EVIDENCE_REQUIRED"


def test_evidence_content_edit_is_detected(sealed_run):
    """Editing a sealed file must invalidate the baseline, not just the manifest."""
    (sealed_run / "before" / "page.json").write_text('{"ok":false}', encoding="utf-8")

    with pytest.raises(_violation()) as caught:
        _load(sealed_run)
    assert caught.value.code == "BASELINE_TAMPERED"


def test_manifest_rewritten_to_match_edited_evidence_is_detected(sealed_run):
    """The strongest local attack: edit evidence AND recompute the manifest.

    Only the MAC stands between this and an accepted forged baseline.
    """
    from web_ui_quality.contracts import digest_json, sha256_hex

    evidence = sealed_run / "before" / "page.json"
    forged = b'{"ok":false}'
    evidence.write_bytes(forged)

    manifest_path = sealed_run / "before" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    files = [{"path": "page.json", "sha256": sha256_hex(forged), "bytes": len(forged)}]
    manifest["files"] = files
    manifest["fileCount"] = len(files)
    manifest["filesDigest"] = digest_json(files)
    body = {k: v for k, v in manifest.items() if k not in {"manifestDigest", "integrityMac"}}
    manifest["manifestDigest"] = digest_json(body)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(_violation()) as caught:
        _load(sealed_run)
    assert caught.value.code in {"EVIDENCE_MANIFEST_MISMATCH", "BASELINE_TAMPERED"}


def test_rotated_integrity_key_invalidates_existing_run(sealed_run):
    """A replaced key must fail closed rather than re-anchor the run."""
    import secrets

    from web_ui_quality.experience_run import _KEY_FILE

    key_path = _locate_key(sealed_run, _KEY_FILE)
    key_path.write_bytes(secrets.token_bytes(32))

    with pytest.raises(_violation()) as caught:
        _load(sealed_run)
    assert caught.value.code == "RUN_STATE_TAMPERED"


def test_short_integrity_key_is_rejected(sealed_run):
    """A truncated key must not be silently accepted or regenerated."""
    from web_ui_quality.experience_run import _KEY_FILE

    _locate_key(sealed_run, _KEY_FILE).write_bytes(b"tooshort")

    with pytest.raises(_violation()) as caught:
        _load(sealed_run)
    assert caught.value.code == "RUN_STATE_TAMPERED"


def test_run_id_cannot_be_reused(tmp_path):
    """Re-creating the same runId must not overwrite sealed evidence."""
    from web_ui_quality.experience_run import create_experience_run

    kwargs = dict(
        task_id="t1", session_id="s1", mode="CHECK",
        target=TARGET, conditions=CONDITIONS, run_id="wuq-" + "b" * 16,
    )
    create_experience_run(tmp_path / "runs", **kwargs)
    with pytest.raises(_violation()):
        create_experience_run(tmp_path / "runs", **kwargs)


@pytest.mark.parametrize("bad_id", ["../escape", "wuq-XYZ", "wuq-short", "wuq-" + "a" * 64, "wuq-AAAAAAAAAAAAAAAA"])
def test_invalid_run_ids_are_rejected(tmp_path, bad_id):
    """Run IDs are a path component; only the strict pattern may pass."""
    from web_ui_quality.experience_run import create_experience_run

    with pytest.raises(_violation()):
        create_experience_run(
            tmp_path / "runs", task_id="t1", session_id="s1", mode="CHECK",
            target=TARGET, conditions=CONDITIONS, run_id=bad_id,
        )


def _locate_key(run_dir: Path, key_file: str) -> Path:
    """Find the integrity key next to the artifacts root or in the key store."""
    candidate = run_dir.parent / key_file
    if candidate.exists():
        return candidate
    from web_ui_quality import experience_run

    resolver = getattr(experience_run, "_key_path", None)
    if resolver is None:
        pytest.skip("integrity key location is not discoverable")
    return resolver(run_dir.parent.resolve())
