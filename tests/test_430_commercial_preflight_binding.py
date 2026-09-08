from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import zipfile

from web_ui_quality.commercial_preflight import run_preflight


def _load_release_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "release.py"
    spec = importlib.util.spec_from_file_location("wuq_release_sorting_430_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_json(path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def _tree_digest(rows):
    digest = hashlib.sha256()
    for row in sorted(rows, key=lambda item: item["path"].encode("utf-8")):
        digest.update(row["path"].encode("utf-8"))
        digest.update(b"\0")
        digest.update(row["sha256"].encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _write_complete_fixture(tmp_path):
    package = tmp_path / "package"
    package.mkdir()
    (package / ".codex-plugin").mkdir()
    (package / ".codex-plugin" / "plugin.json").write_text(
        json.dumps({
            "name": "web-ui-quality", "version": "4.3.0",
            "author": {"name": "Example Commercial Entity"},
            "interface": {"developerName": "Example Commercial Entity"},
        }, ensure_ascii=False), encoding="utf-8"
    )
    (package / "pyproject.toml").write_text(
        '[project]\nversion = "4.3.0"\nauthors = [{name = "Example Commercial Entity"}]\n', encoding="utf-8"
    )
    required = (
        "LICENSE", "EULA_TEMPLATE.md", "PRIVACY_NOTICE_TEMPLATE.md", "SUPPORT_POLICY_TEMPLATE.md",
        "SECURITY.md", "SECURITY_RESPONSE_POLICY.md", "COMMERCIAL_RELEASE_CHECKLIST.md",
    )
    for name in required:
        (package / name).write_text(f"verified {name}\n", encoding="utf-8")
    (package / "runtime").mkdir()
    (package / "runtime" / "example.py").write_text("print('runtime')\n", encoding="utf-8")
    _refresh_fixture_candidate(package, tmp_path / "candidate.zip")
    return package, tmp_path / "candidate.zip"


def _refresh_fixture_candidate(package, candidate):
    rows = []
    generated_manifests = {"RELEASE-MANIFEST.json", "COMPOSITE-RELEASE-MANIFEST.json"}
    for path in sorted(item for item in package.rglob("*") if item.is_file() and item.name not in generated_manifests):
        relative = path.relative_to(package).as_posix()
        data = path.read_bytes()
        rows.append({"path": relative, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    tree = _tree_digest(rows)
    identity = {
        "schemaVersion": "2", "product": "web-ui-quality", "pluginVersion": "4.3.0", "packageVersion": "4.3.0",
        "packageStage": "4.3.0-stable", "kernelVersion": "4.2.3", "kernelBaseVersion": "4.0.0-rc.1",
        "protocolVersion": "3.0", "receiptProtocolVersion": "3.0", "evidenceSchemaVersion": "3.0",
    }
    release = {**identity, "stage": "4.3.0-commercial-stable", "root": "web-ui-quality/", "fileCount": len(rows), "packageTreeDigest": tree, "files": rows}
    composite = {**identity, "packageTreeDigest": tree, "realCodexHostQualification": "NOT_MEASURED", "nativeWindowsQualification": "NOT_MEASURED"}
    release_bytes = (json.dumps(release, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    composite_bytes = (json.dumps(composite, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    with zipfile.ZipFile(candidate, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for row in rows:
            archive.writestr(f"web-ui-quality/{row['path']}", (package / row["path"]).read_bytes())
        archive.writestr("web-ui-quality/RELEASE-MANIFEST.json", release_bytes)
        archive.writestr("web-ui-quality/COMPOSITE-RELEASE-MANIFEST.json", composite_bytes)


def _rewrite_candidate(candidate, output, *, replace=None, remove=(), extra=None, manifest_edit=None):
    remove = set(remove)
    with zipfile.ZipFile(candidate) as source:
        entries = {name.replace("\\", "/"): source.read(info) for info in source.infolist() for name in [info.filename]}
    if replace:
        for name, data in replace.items():
            entries[name] = data
    for name in remove:
        entries.pop(name, None)
    if extra:
        entries.update(extra)
    if manifest_edit:
        name = "web-ui-quality/RELEASE-MANIFEST.json"
        value = json.loads(entries[name].decode("utf-8"))
        manifest_edit(value)
        entries[name] = (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries.items():
            archive.writestr(name, data)


def test_release_uses_one_canonical_utf8_path_order_for_files_and_manifest(tmp_path, monkeypatch) -> None:
    release = _load_release_module()
    root = tmp_path / "package"
    (root / "runtime").mkdir(parents=True)
    relative_names = ("z.txt", "é.txt", "e\u0301.txt", "中.txt")
    for name in relative_names:
        (root / "runtime" / name).write_text(name, encoding="utf-8")
    monkeypatch.setattr(release, "ROOT", root)

    expected = sorted(
        (root / "runtime" / name for name in relative_names),
        key=lambda path: path.relative_to(root).as_posix().encode("utf-8"),
    )
    assert release._files() == expected

    entries = release._entries()
    manifest_bytes = next(data for name, data, _mode in entries if name == "web-ui-quality/RELEASE-MANIFEST.json")
    manifest = json.loads(manifest_bytes.decode("utf-8"))
    assert [row["path"] for row in manifest["files"]] == [
        path.relative_to(root).as_posix() for path in expected
    ]
    assert manifest["packageTreeDigest"] == release._package_tree_digest(manifest["files"])


def test_preflight_requires_exact_versioned_evidence_directory(tmp_path) -> None:
    package = tmp_path / "package"
    package.mkdir()
    (package / "pyproject.toml").write_text('[project]\nversion = "4.3.0"\n', encoding="utf-8")

    exact = package / "release-evidence-4.3.0"
    exact.mkdir()
    _write_json(exact / "tests.json", {"releaseRunId": "run-430"})
    _write_json(exact / "preview-matrix.json", {"releaseRunId": "run-430", "status": "PASS"})

    result = run_preflight(package, evidence_root=exact)
    checks = {item["id"]: item for item in result["checks"]}
    assert result["releaseEvidenceLine"] == "4.3.0"
    assert checks["RELEASE-EVIDENCE-VERSION"]["status"] == "PASS"
    assert result["status"] == "RC_ONLY"


def test_preflight_rejects_legacy_test_evidence_name(tmp_path) -> None:
    package = tmp_path / "package"
    package.mkdir()
    (package / "pyproject.toml").write_text('[project]\nversion = "4.3.0"\n', encoding="utf-8")
    exact = package / "release-evidence-4.3.0"
    exact.mkdir()
    _write_json(exact / "test-output.txt", {"releaseRunId": "run-430"})

    result = run_preflight(package, evidence_root=exact)
    check = {item["id"]: item for item in result["checks"]}["RELEASE-TEST-EVIDENCE"]

    assert check["status"] == "FAIL"
    assert check["detail"]["canonicalName"] == "tests.json"
    assert check["detail"]["legacyFilesRejected"] == ["test-output.txt"]


def test_preflight_binds_commercial_files_to_candidate_bytes(tmp_path) -> None:
    package, candidate = _write_complete_fixture(tmp_path)
    _rewrite_candidate(candidate, tmp_path / "tampered.zip", replace={"web-ui-quality/LICENSE": b"different candidate content\n"})
    candidate = tmp_path / "tampered.zip"
    # The source manifest is the package-root record used by Preflight.
    _refresh_fixture_candidate(package, tmp_path / "source-reference.zip")
    with zipfile.ZipFile(tmp_path / "source-reference.zip") as archive:
        (package / "RELEASE-MANIFEST.json").write_bytes(archive.read("web-ui-quality/RELEASE-MANIFEST.json"))

    evidence = package / "release-evidence-4.3.0"
    evidence.mkdir()
    result = run_preflight(package, evidence_root=evidence, candidate_archive=candidate)
    check = {item["id"]: item for item in result["checks"]}["PACKAGE-ROOT-CANDIDATE-CONTENT"]

    assert check["status"] == "FAIL"
    assert check["detail"]["contentMatch"] is False
    license_row = next(row for row in check["detail"]["requiredCommercialFiles"] if row["path"] == "LICENSE")
    assert license_row["match"] is False


def test_preflight_accepts_exact_commercial_files_from_candidate(tmp_path) -> None:
    package, candidate = _write_complete_fixture(tmp_path)
    with zipfile.ZipFile(candidate) as archive:
        (package / "RELEASE-MANIFEST.json").write_bytes(archive.read("web-ui-quality/RELEASE-MANIFEST.json"))

    evidence = package / "release-evidence-4.3.0"
    evidence.mkdir()
    result = run_preflight(package, evidence_root=evidence, candidate_archive=candidate)
    check = {item["id"]: item for item in result["checks"]}["PACKAGE-ROOT-CANDIDATE-CONTENT"]

    assert check["status"] == "PASS"
    assert check["detail"]["contentMatch"] is True
    assert check["detail"]["archiveValidation"] is True


def test_preflight_rejects_tampered_runtime_manifest_extra_and_missing_entries(tmp_path) -> None:
    package, candidate = _write_complete_fixture(tmp_path)
    with zipfile.ZipFile(candidate) as archive:
        (package / "RELEASE-MANIFEST.json").write_bytes(archive.read("web-ui-quality/RELEASE-MANIFEST.json"))

    cases = {
        "runtime": dict(replace={"web-ui-quality/runtime/example.py": b"tampered runtime\n"}),
        "manifest": dict(manifest_edit=lambda value: value.__setitem__("packageTreeDigest", "0" * 64)),
        "extra": dict(extra={"web-ui-quality/extra.txt": b"unexpected\n"}),
        "missing": dict(remove={"web-ui-quality/runtime/example.py"}),
    }
    for label, options in cases.items():
        tampered = tmp_path / f"{label}.zip"
        _rewrite_candidate(candidate, tampered, **options)
        result = run_preflight(package, evidence_root=package / "release-evidence-4.3.0", candidate_archive=tampered)
        check = {item["id"]: item for item in result["checks"]}["PACKAGE-ROOT-CANDIDATE-CONTENT"]
        assert check["status"] == "FAIL", label
        assert check["detail"]["archiveValidation"] is False, label


def test_preflight_rejects_source_mismatch_and_identity_placeholders(tmp_path) -> None:
    package, candidate = _write_complete_fixture(tmp_path)
    with zipfile.ZipFile(candidate) as archive:
        (package / "RELEASE-MANIFEST.json").write_bytes(archive.read("web-ui-quality/RELEASE-MANIFEST.json"))
    (package / "runtime" / "example.py").write_text("source changed after candidate\n", encoding="utf-8")
    result = run_preflight(package, evidence_root=package / "release-evidence-4.3.0", candidate_archive=candidate)
    content = {item["id"]: item for item in result["checks"]}["PACKAGE-ROOT-CANDIDATE-CONTENT"]
    assert content["detail"]["sourcePackageMatch"] is False

    (package / ".codex-plugin" / "plugin.json").write_text(
        '{"name":"web-ui-quality","version":"4.3.0","author":{"name":"Web UI Quality Contributors"},"interface":{"developerName":"Web UI Quality Contributors"}}',
        encoding="utf-8",
    )
    (package / "pyproject.toml").write_text(
        '[project]\nversion = "4.3.0"\nauthors = [{name = "<LEGAL_ENTITY>"}]\n', encoding="utf-8"
    )
    _refresh_fixture_candidate(package, tmp_path / "identity.zip")
    with zipfile.ZipFile(tmp_path / "identity.zip") as archive:
        (package / "RELEASE-MANIFEST.json").write_bytes(archive.read("web-ui-quality/RELEASE-MANIFEST.json"))
    result = run_preflight(package, evidence_root=package / "release-evidence-4.3.0", candidate_archive=tmp_path / "identity.zip")
    identity = {item["id"]: item for item in result["checks"]}["COMMERCIAL-IDENTITY-PLACEHOLDERS"]
    assert identity["status"] == "FAIL"
    assert {hit["file"] for hit in identity["detail"]["placeholderHits"]} == {".codex-plugin/plugin.json", "pyproject.toml"}


def test_preflight_rejects_short_release_evidence_directory_name(tmp_path) -> None:
    package = tmp_path / "package"
    package.mkdir()
    (package / "pyproject.toml").write_text('[project]\nversion = "4.3.0"\n', encoding="utf-8")
    wrong = package / "release-evidence-4.3"
    wrong.mkdir()

    result = run_preflight(package, evidence_root=wrong)
    checks = {item["id"]: item for item in result["checks"]}
    assert checks["RELEASE-EVIDENCE-VERSION"]["status"] == "FAIL"
    assert checks["RELEASE-EVIDENCE-VERSION"]["detail"]["expectedDirectory"] == "release-evidence-4.3.0"
