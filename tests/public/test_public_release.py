from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

import pytest


ROOT = Path(__file__).resolve().parents[2]
_RELEASE_SPEC = importlib.util.spec_from_file_location("_web_ui_quality_release_script", ROOT / "scripts" / "release.py")
assert _RELEASE_SPEC and _RELEASE_SPEC.loader
_RELEASE = importlib.util.module_from_spec(_RELEASE_SPEC)
sys.modules[_RELEASE_SPEC.name] = _RELEASE
_RELEASE_SPEC.loader.exec_module(_RELEASE)


def _text_files() -> list[Path]:
    return [
        path
        for path in ROOT.rglob("*")
        if path.is_file()
        and ".git" not in path.parts
        and path.suffix.casefold() in {".md", ".txt", ".py", ".json", ".toml", ".yaml", ".yml", ".ps1", ".sh"}
    ]


def test_public_license_is_declared_consistently() -> None:
    plugin = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")

    assert plugin["license"] == "Apache-2.0"
    assert project["license"] == "Apache-2.0"
    assert license_text.lstrip().startswith("Apache License")
    assert "TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION" in license_text


def test_private_and_external_material_is_outside_public_boundary() -> None:
    forbidden_dirs = {"evolution", "external-challenge-track", "codex-sessions", "LevelDB"}
    present_parts = {part for path in ROOT.rglob("*") for part in path.parts}
    assert not (present_parts & forbidden_dirs)

    forbidden_text = re.compile(
        r"(?:[A-Za-z]:\\Users\\|[A-Za-z]:/Users/|-----BEGIN [A-Z ]*PRIVATE KEY-----|\b(?:sk|ghp|github_pat)_[A-Za-z0-9_]{12,})",
        re.IGNORECASE,
    )
    leaked = [
        str(path.relative_to(ROOT))
        for path in _text_files()
        if path.name != "test_public_release.py"
        if forbidden_text.search(path.read_text(encoding="utf-8", errors="replace"))
    ]
    assert leaked == []


def test_public_plugin_and_runtime_import() -> None:
    manifest = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert manifest["name"] == "web-ui-quality"
    skill_path = ROOT / "skills" / "audit-and-fix-web-ui" / "SKILL.md"
    assert skill_path.is_file()
    from web_ui_quality.release_info import PACKAGE_VERSION
    assert PACKAGE_VERSION in skill_path.read_text(encoding="utf-8")

    completed = subprocess.run(
        [sys.executable, "-B", "scripts/run_runtime.py", "--help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout


def test_public_manifest_is_deterministically_hashable() -> None:
    rows = []
    for path in sorted(
        (p for p in ROOT.rglob("*") if p.is_file() and ".git" not in p.parts),
        key=lambda p: p.relative_to(ROOT).as_posix(),
    ):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        rows.append((path.relative_to(ROOT).as_posix(), digest))
    assert rows
    assert len(rows) == len({path for path, _ in rows})


def test_current_publication_identity_is_normal_release() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    publication = (ROOT / "PUBLICATION.md").read_text(encoding="utf-8")
    release_script = (ROOT / "scripts" / "release.py").read_text(encoding="utf-8")
    manifest = json.loads((ROOT / "FINAL_PUBLIC_SOURCE_MANIFEST.json").read_text(encoding="utf-8"))

    stale_badge = "OSS " + "Preview"
    stale_wording = "release " + "candidate"
    stale_status = "NORMAL_RELEASE_" + "CANDIDATE_LOCAL_ONLY"

    assert stale_badge not in readme
    assert stale_wording not in readme.casefold()
    assert stale_wording not in publication.casefold()
    assert manifest["candidate"]["candidateOnly"] is False
    assert manifest["candidate"]["publicGithubRelease"] == "NORMAL_RELEASE"
    assert '"publicationStatus": PUBLICATION_STATUS' in release_script
    assert stale_status not in release_script


def _configure_release_fixture(monkeypatch, tmp_path: Path, *, complete: bool):
    fixture_root = tmp_path / "release-fixture"
    fixture_root.mkdir()

    def source_row(path: Path) -> dict[str, object]:
        data = path.read_bytes()
        return {
            "path": path.name,
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "provenance": "WUQ_ORIGINAL_CONFIRMED",
            "license": "Apache-2.0",
            "classificationReason": "Synthetic source row used to test the release contract.",
            "copyrightBasis": "SYNTHETIC_TEST_FIXTURE",
            "noticeRequirement": "NONE",
            "redistributionDecision": "INCLUDE_IN_APACHE_2_0_CANDIDATE",
            "thirdPartyContentDisposition": "NONE",
            "sourceComparison": {"exactWholeFileHashMatchAgainstSavedExternalSnapshots": 0},
        }

    readme = fixture_root / "README.md"
    readme.write_text("Synthetic, valid source fixture.\n", encoding="utf-8")
    files = [readme]
    if complete:
        notice = fixture_root / "NOTICE.md"
        notice.write_text("A reconciled source row.\n", encoding="utf-8")
        files.append(notice)
        status = "CLOSED_FOR_DISTRIBUTED_FILES"
        third_party_status = status
        rows = [source_row(readme), source_row(notice)]
        scope = {
            "currentSourceFileCount": 3,
            "listedProvenanceFileCount": 2,
            "unlistedSourceFileCount": 0,
            "listedRowsWithStaleCurrentBytesOrHash": 0,
            "manifestSelfReferenceOmitted": True,
            "unlistedFilesChangedInThisCandidate": 0,
            "staleListedFilesChangedInThisCandidate": 2,
        }
    else:
        notice = fixture_root / "NOTICE.md"
        notice.write_text("A second source file.\n", encoding="utf-8")
        files.append(notice)
        status = "CURRENT_BATCH_ONLY"
        third_party_status = "NO_THIRD_PARTY_CONTENT_ADDED_IN_CURRENT_BATCH"
        rows = [{"path": "README.md", "bytes": readme.stat().st_size, "sha256": "0" * 64}]
        scope = {
            "currentSourceFileCount": 3,
            "listedProvenanceFileCount": 1,
            "unlistedSourceFileCount": 1,
            "listedRowsWithStaleCurrentBytesOrHash": 1,
            "manifestSelfReferenceOmitted": True,
            "unlistedFilesChangedInThisCandidate": 0,
            "staleListedFilesChangedInThisCandidate": 0,
        }
    manifest = {
        "RIGHTS_BLOCKED": 0,
        "NOT_CONFIRMED_DISTRIBUTED_FILES": 0,
        "REMOVE_FROM_PUBLIC_RELEASE": 0,
        "fileCount": len(rows),
        "files": rows,
        "engineeringClosure": {
            "status": status,
            "thirdPartyProvenanceStatus": third_party_status,
        },
        "publicPackageScope": scope,
        "validationContract": {
            "allCurrentPackageFilesHaveProvenance": complete,
            "allManifestRowsUseAllowedProvenanceLabels": complete,
            "allowedProvenance": sorted(_RELEASE.ALLOWED_SOURCE_PROVENANCE),
        },
    }
    manifest_path = fixture_root / "FINAL_PUBLIC_SOURCE_MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    files.append(manifest_path)

    monkeypatch.setattr(_RELEASE, "ROOT", fixture_root)
    monkeypatch.setattr(_RELEASE, "_files", lambda: sorted(files, key=lambda path: path.relative_to(fixture_root).as_posix()))
    monkeypatch.setattr(_RELEASE, "_validate_identity", lambda: None)
    monkeypatch.setattr(_RELEASE, "_validate_python", lambda: 1)
    monkeypatch.setattr(_RELEASE, "_run", lambda *args, **kwargs: None)
    return fixture_root, manifest


def test_release_validate_keeps_technical_pass_separate_from_partial_provenance(monkeypatch, tmp_path: Path) -> None:
    _, _ = _configure_release_fixture(monkeypatch, tmp_path, complete=False)

    report = _RELEASE.validate()

    assert report["status"] == "PASS"
    assert report["statusScope"] == "TECHNICAL_CHECKS_ONLY"
    assert report["copyrightProvenance"] == "CURRENT_BATCH_ONLY"
    assert report["formalReleaseEligible"] is False
    assert any("1 public source path" in reason for reason in report["releaseBlockers"])
    assert any("1 provenance row" in reason for reason in report["releaseBlockers"])


@pytest.mark.parametrize("manifest_state", ["missing", "corrupt", "missing_closure", "missing_status", "unknown_status", "missing_scope"])
def test_release_manifest_uncertainty_never_defaults_to_closed(monkeypatch, tmp_path: Path, manifest_state: str) -> None:
    fixture_root, manifest = _configure_release_fixture(monkeypatch, tmp_path, complete=True)
    manifest_path = fixture_root / "FINAL_PUBLIC_SOURCE_MANIFEST.json"
    if manifest_state == "missing":
        manifest_path.unlink()
    elif manifest_state == "corrupt":
        manifest_path.write_text("{broken json", encoding="utf-8")
    elif manifest_state == "missing_closure":
        manifest.pop("engineeringClosure")
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    elif manifest_state == "missing_status":
        manifest["engineeringClosure"].pop("status")
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    elif manifest_state == "unknown_status":
        manifest["engineeringClosure"]["status"] = "CLOSED_ENOUGH"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    elif manifest_state == "missing_scope":
        manifest.pop("publicPackageScope")
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    report = _RELEASE._source_provenance_conclusion()

    assert report["formalReleaseEligible"] is False
    assert report["releaseBlockers"]
    if manifest_state in {"missing", "corrupt", "missing_closure", "missing_status", "unknown_status"}:
        assert report["copyrightProvenance"] == "UNKNOWN"


def test_changing_only_partial_status_cannot_make_incomplete_manifest_eligible(monkeypatch, tmp_path: Path) -> None:
    fixture_root, manifest = _configure_release_fixture(monkeypatch, tmp_path, complete=False)
    manifest["engineeringClosure"]["status"] = "CLOSED_FOR_DISTRIBUTED_FILES"
    manifest["engineeringClosure"]["thirdPartyProvenanceStatus"] = "CLOSED_FOR_DISTRIBUTED_FILES"
    manifest["validationContract"]["allCurrentPackageFilesHaveProvenance"] = True
    (fixture_root / "FINAL_PUBLIC_SOURCE_MANIFEST.json").write_text(json.dumps(manifest), encoding="utf-8")

    report = _RELEASE._source_provenance_conclusion()

    assert report["copyrightProvenance"] == "CLOSED_FOR_DISTRIBUTED_FILES"
    assert report["formalReleaseEligible"] is False
    assert any("1 public source path" in reason for reason in report["releaseBlockers"])
    assert any("1 provenance row" in reason for reason in report["releaseBlockers"])


def test_closed_status_still_requires_current_file_hashes(monkeypatch, tmp_path: Path) -> None:
    fixture_root, _ = _configure_release_fixture(monkeypatch, tmp_path, complete=True)
    (fixture_root / "README.md").write_text("changed after the source manifest\n", encoding="utf-8")

    report = _RELEASE._source_provenance_conclusion()

    assert report["copyrightProvenance"] == "CLOSED_FOR_DISTRIBUTED_FILES"
    assert report["formalReleaseEligible"] is False
    assert any("do not match current bytes or hashes" in reason for reason in report["releaseBlockers"])


def test_closed_status_rejects_unrecognized_row_provenance(monkeypatch, tmp_path: Path) -> None:
    fixture_root, manifest = _configure_release_fixture(monkeypatch, tmp_path, complete=True)
    manifest["files"][0]["provenance"] = "UNREVIEWED"
    (fixture_root / "FINAL_PUBLIC_SOURCE_MANIFEST.json").write_text(json.dumps(manifest), encoding="utf-8")

    report = _RELEASE._source_provenance_conclusion()

    assert report["formalReleaseEligible"] is False
    assert any("unrecognized provenance label" in reason for reason in report["releaseBlockers"])


def test_manifest_cannot_expand_recognized_provenance_labels(monkeypatch, tmp_path: Path) -> None:
    fixture_root, manifest = _configure_release_fixture(monkeypatch, tmp_path, complete=True)
    manifest["validationContract"]["allowedProvenance"].append("UNREVIEWED")
    (fixture_root / "FINAL_PUBLIC_SOURCE_MANIFEST.json").write_text(json.dumps(manifest), encoding="utf-8")

    report = _RELEASE._source_provenance_conclusion()

    assert report["formalReleaseEligible"] is False
    assert any("does not match the recognized source labels" in reason for reason in report["releaseBlockers"])


@pytest.mark.parametrize(
    "field",
    ["license", "classificationReason", "copyrightBasis", "noticeRequirement", "redistributionDecision", "thirdPartyContentDisposition", "sourceComparison"],
)
def test_closed_status_requires_source_and_license_details(monkeypatch, tmp_path: Path, field: str) -> None:
    fixture_root, manifest = _configure_release_fixture(monkeypatch, tmp_path, complete=True)
    manifest["files"][0].pop(field)
    (fixture_root / "FINAL_PUBLIC_SOURCE_MANIFEST.json").write_text(json.dumps(manifest), encoding="utf-8")

    report = _RELEASE._source_provenance_conclusion()

    assert report["formalReleaseEligible"] is False
    assert any(f"is missing {field}" in reason for reason in report["releaseBlockers"])


def test_partial_provenance_blocks_package_before_creating_release_files(monkeypatch, tmp_path: Path, capsys) -> None:
    fixture_root, _ = _configure_release_fixture(monkeypatch, tmp_path, complete=False)
    dist = fixture_root / "dist"
    dist.mkdir()
    sentinel = dist / "keep.txt"
    sentinel.write_text("pre-existing file", encoding="utf-8")
    release_asset = dist / f"web-ui-quality-{_RELEASE.PACKAGE_VERSION}.zip"
    release_asset.write_bytes(b"previous artifact must remain untouched")
    monkeypatch.setattr(sys, "argv", ["release.py", "package"])

    exit_code = _RELEASE.main()
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 2
    assert output["status"] == "BLOCKED"
    assert output["statusScope"] == "FORMAL_PACKAGE_ELIGIBILITY"
    assert output["technicalValidation"] == "PASS"
    assert output["packageStatus"] == "BLOCKED"
    assert output["copyrightProvenance"] == "CURRENT_BATCH_ONLY"
    assert output["formalReleaseEligible"] is False
    assert sentinel.read_text(encoding="utf-8") == "pre-existing file"
    assert release_asset.read_bytes() == b"previous artifact must remain untouched"
    assert sorted(path.name for path in dist.iterdir()) == ["keep.txt", release_asset.name]


def test_complete_provenance_is_shared_by_validate_package_and_build_report(monkeypatch, tmp_path: Path, capsys) -> None:
    fixture_root, _ = _configure_release_fixture(monkeypatch, tmp_path, complete=True)
    direct_validation = _RELEASE.validate()
    monkeypatch.setattr(sys, "argv", ["release.py", "validate"])
    assert _RELEASE.main() == 0
    validate_output = json.loads(capsys.readouterr().out)

    monkeypatch.setattr(sys, "argv", ["release.py", "package"])
    assert _RELEASE.main() == 0
    package_output = json.loads(capsys.readouterr().out)
    build_report = json.loads((fixture_root / "dist" / f"web-ui-quality-{_RELEASE.PACKAGE_VERSION}.build.json").read_text(encoding="utf-8"))

    assert direct_validation["copyrightProvenance"] == "CLOSED_FOR_DISTRIBUTED_FILES"
    assert direct_validation["formalReleaseEligible"] is True
    for report in (validate_output, package_output, build_report):
        assert report["copyrightProvenance"] == direct_validation["copyrightProvenance"]
        assert report["formalReleaseEligible"] is True
        assert report["releaseBlockers"] == []
    assert package_output["packageStatus"] == "PASS"
    assert build_report["packageStatus"] == "PASS"
