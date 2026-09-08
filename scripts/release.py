#!/usr/bin/env python3
"""Validate and reproducibly package the Web UI Quality public source release."""
from __future__ import annotations

import argparse
import ast
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import tarfile
import zipfile


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime" / "python"
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from web_ui_quality.release_info import (PRODUCT_NAME, PACKAGE_STAGE, PACKAGE_VERSION, KERNEL_VERSION, KERNEL_BASE_VERSION, PROTOCOL_VERSION, RECEIPT_PROTOCOL_VERSION, EVIDENCE_SCHEMA_VERSION, RELEASE_STAGE)  # noqa: E402


ROOT_FILES = {
    "README.md", "LICENSE", "THIRD_PARTY_NOTICES.md", "CHANGELOG.md", "SECURITY.md",
    "KNOWN_LIMITATIONS.md", "ARCHITECTURE.md", "COMMERCIAL_RELEASE_CHECKLIST.md",
    "COMPATIBILITY_MATRIX.md", "REPAIR_MODERNIZATION_ACCEPTANCE.md", "GUIDED_REPAIR_QUICKSTART.md", "AGENT_BENCHMARK_PROTOCOL.md",
    "ADAPTIVE_TRUST_KERNEL_RFC.md", "PRODUCT_MEASUREMENT_SPEC.md",
    "EULA_TEMPLATE.md", "PRIVACY_NOTICE_TEMPLATE.md", "SUPPORT_POLICY_TEMPLATE.md", "SECURITY_RESPONSE_POLICY.md",
    "MANIFEST.in", "pyproject.toml", "setup.cfg", "run_tests.py",
    "PUBLICATION.md", "NOTICE.md", "CONTRIBUTING.md", "pytest.ini",
}
# The public snapshot deliberately excludes the private evolution ledger and
# external challenge evidence. Public packaging must use this same boundary.
ROOT_DIRS = {".codex-plugin", "assets", "examples", "references", "runtime", "schemas", "scripts", "skills", "tests"}
EXCLUDED_PARTS = {
    ".git", ".pytest_cache", ".test-workspace", "__pycache__", "build", "dist",
    "external-proof", "reports",
}
HISTORICAL_HEADING = re.compile(r"(?im)^#{1,3}\s+\d+\.\d+\.\d+[^\n]*\bRC\d*\b")
STALE_PACKAGE_VERSIONS = {".".join(parts) for parts in (("3", "6", "0"), ("3", "6", "1"), ("3", "6", "2"), ("3", "7", "0"), ("3", "7", "1"), ("3", "7", "2"), ("3", "7", "3"))}
DEFAULT_GATE_TIMEOUT_SECONDS = 180
# release_gate.py owns a 900-second worker deadline. Allow that worker to
# report its own result, plus a bounded minute for parent/process cleanup.
FULL_RELEASE_GATE_TIMEOUT_SECONDS = 960

CURRENT_USER_DOCS = {
    "README.md", "ARCHITECTURE.md", "KNOWN_LIMITATIONS.md", "COMPATIBILITY_MATRIX.md",
    "COMMERCIAL_RELEASE_CHECKLIST.md", "REPAIR_MODERNIZATION_ACCEPTANCE.md", "GUIDED_REPAIR_QUICKSTART.md", "SECURITY.md", "AGENT_BENCHMARK_PROTOCOL.md",
    "ADAPTIVE_TRUST_KERNEL_RFC.md", "PRODUCT_MEASUREMENT_SPEC.md",
}

COMMERCIAL_DOCUMENTS = {
    "EULA_TEMPLATE.md", "PRIVACY_NOTICE_TEMPLATE.md", "SUPPORT_POLICY_TEMPLATE.md", "SECURITY_RESPONSE_POLICY.md",
}


def _is_included(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    if path.is_dir() or any(
        part in EXCLUDED_PARTS
        or part.endswith(".egg-info")
        or part.startswith("release-evidence-")
        for part in rel.parts
    ):
        return False
    # Historical screenshots/reference outputs are development regression evidence,
    # not part of the user-facing commercial distribution.
    if len(rel.parts) >= 2 and rel.parts[0] == "references" and rel.parts[1] == "history":
        return False
    if len(rel.parts) == 1:
        return rel.name in ROOT_FILES
    if rel.parts and rel.parts[0] == "examples":
        if "output" in rel.parts or any(part.endswith("-evidence") for part in rel.parts[1:]):
            return False
        return path.name != ".DS_Store"
    if rel.parts[0] not in ROOT_DIRS:
        return False
    return path.suffix not in {".pyc", ".pyo"} and path.name != ".DS_Store"


def _files() -> list[Path]:
    return sorted(
        (path for path in ROOT.rglob("*") if _is_included(path)),
        key=lambda path: path.relative_to(ROOT).as_posix().encode("utf-8"),
    )


def _mode(path: Path) -> int:
    try:
        first_line = path.read_bytes().splitlines()[0]
    except (OSError, IndexError):
        first_line = b""
    return 0o755 if first_line.startswith(b"#!") else 0o644


def _package_tree_digest(content_manifest: list[dict[str, object]]) -> str:
    """Digest normalized paths + raw-byte digests; generated manifests are excluded."""
    h = hashlib.sha256()
    for item in sorted(content_manifest, key=lambda row: str(row["path"]).encode("utf-8")):
        path = str(item["path"]).replace("\\", "/")
        h.update(path.encode("utf-8")); h.update(b"\0"); h.update(str(item["sha256"]).encode("ascii")); h.update(b"\n")
    return h.hexdigest()


def _entries() -> list[tuple[str, bytes, int]]:
    entries: list[tuple[str, bytes, int]] = []
    content_manifest: list[dict[str, object]] = []
    for path in _files():
        relative = path.relative_to(ROOT).as_posix()
        data = path.read_bytes()
        entries.append((f"{PRODUCT_NAME}/{relative}", data, _mode(path)))
        content_manifest.append({"path": relative, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    content_manifest.sort(key=lambda row: str(row["path"]).replace("\\", "/").encode("utf-8"))
    tree_digest = _package_tree_digest(content_manifest)
    identity = {
        "pluginVersion": PACKAGE_VERSION, "packageVersion": PACKAGE_VERSION,
        "packageStage": PACKAGE_STAGE,
        "kernelVersion": KERNEL_VERSION, "kernelBaseVersion": KERNEL_BASE_VERSION,
        "protocolVersion": PROTOCOL_VERSION, "receiptProtocolVersion": RECEIPT_PROTOCOL_VERSION,
        "evidenceSchemaVersion": EVIDENCE_SCHEMA_VERSION,
    }
    release_manifest = {
        "schemaVersion": "2", "product": PRODUCT_NAME, **identity, "stage": RELEASE_STAGE,
        "root": f"{PRODUCT_NAME}/", "fileCount": len(content_manifest), "packageTreeDigest": tree_digest,
        "files": content_manifest,
        "claimBoundary": "This manifest proves deterministic package-tree composition. The final archive SHA-256 is external and is not self-referenced here; Real Codex Host qualification is not implied.",
    }
    composite = {
        "schemaVersion": "2", "product": PRODUCT_NAME, **identity, "packageTreeDigest": tree_digest,
        "realCodexHostQualification": "NOT_MEASURED", "nativeWindowsQualification": "NOT_MEASURED",
        "v5Included": False, "adaptiveGuidanceActive": False, "adaptiveExplorationActive": False,
        "claimBoundary": "4.3.0 Release Integrity + Trust UX Closure identity and tree composition only; historical 4.1.1 evidence is not promoted into 4.3.0.",
    }
    for name, payload in (("RELEASE-MANIFEST.json", release_manifest), ("COMPOSITE-RELEASE-MANIFEST.json", composite)):
        data=(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)+"\n").encode("utf-8")
        entries.append((f"{PRODUCT_NAME}/{name}", data, 0o644))
    return sorted(entries, key=lambda item: item[0])

def parse_release_doc_identity(text: str) -> dict[str, str | None]:
    """Parse the structured release header instead of searching loose text."""
    header = "\n".join(text.splitlines()[:12])

    def value(pattern: str) -> str | None:
        match = re.search(pattern, header, flags=re.IGNORECASE | re.MULTILINE)
        return match.group(1).strip() if match else None

    field_prefix = r"(?:^\s*>\s*|\s*·\s*)"
    package = value(field_prefix + r"Package\s*:\s*\*{0,2}([^*\s]+)\*{0,2}")
    if package is None:
        package = value(field_prefix + r"Current\s+(?:plugin/)?package\s*:\s*\*{0,2}([^*\s]+)\*{0,2}")
    return {
        "packageVersion": package,
        "packageStage": value(field_prefix + r"Package Stage\s*:\s*\*{0,2}([^*]+?)\*{0,2}(?:\s*·|\s*$)"),
        "kernelVersion": value(field_prefix + r"(?:Trust Kernel|Current kernel)\s*:\s*\*{0,2}([^*\s]+)\*{0,2}"),
        "kernelBaseVersion": value(field_prefix + r"(?:Kernel Base Lineage|Kernel base)\s*:\s*\*{0,2}([^*\s]+)\*{0,2}"),
        "receiptProtocol": value(field_prefix + r"(?:Receipt Protocol|Receipt\s*/\s*Evidence protocol)\s*:\s*\*{0,2}([^*\s]+)\*{0,2}"),
        "evidenceSchema": value(field_prefix + r"Evidence Schema\s*:\s*\*{0,2}([^*\s]+)\*{0,2}"),
    }


def _validate_identity() -> None:
    plugin = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    runtime_info = (ROOT / "runtime" / "python" / "web_ui_quality" / "release_info.py").read_text(encoding="utf-8")
    if ROOT.name != PRODUCT_NAME or plugin.get("name") != PRODUCT_NAME:
        raise SystemExit("plugin folder and manifest name must both be web-ui-quality")
    if plugin.get("license") != "MIT" or 'license = "MIT"' not in pyproject:
        raise SystemExit("public source license metadata is inconsistent")
    if plugin.get("version") != PACKAGE_VERSION: raise SystemExit("plugin manifest version is inconsistent")
    if f'version = "{PACKAGE_VERSION}"' not in pyproject: raise SystemExit("pyproject version is inconsistent")
    checks = {
        "PLUGIN_VERSION": PACKAGE_VERSION, "KERNEL_VERSION": KERNEL_VERSION, "KERNEL_BASE_VERSION": KERNEL_BASE_VERSION,
        "PROTOCOL_VERSION": PROTOCOL_VERSION, "RECEIPT_PROTOCOL_VERSION": RECEIPT_PROTOCOL_VERSION, "EVIDENCE_SCHEMA_VERSION": EVIDENCE_SCHEMA_VERSION,
    }
    for field, value in checks.items():
        if f'{field} = "{value}"' not in runtime_info: raise SystemExit(f"runtime identity mismatch: {field}")
    if f'commercial-release-stage = "{RELEASE_STAGE}"' not in pyproject: raise SystemExit("release stage is inconsistent")
    public_dir, runtime_dir = ROOT / "schemas", ROOT / "runtime" / "python" / "web_ui_quality" / "schemas"
    public = {p.name: p.read_bytes() for p in public_dir.glob("*.json")}
    packaged = {p.name: p.read_bytes() for p in runtime_dir.glob("*.json")}
    if public != packaged: raise SystemExit("public/runtime schema bundles are not full-parity")
    product_schema=json.loads(public["product-experience-report.schema.json"])
    schema_version=product_schema.get("properties",{}).get("generator",{}).get("properties",{}).get("packageVersion",{}).get("const")
    if schema_version != PACKAGE_VERSION: raise SystemExit("product report schema package identity mismatch")
    expected_doc_identity = {
        "packageVersion": PACKAGE_VERSION,
        "packageStage": "Commercial Stable",
        "kernelVersion": KERNEL_VERSION,
        "kernelBaseVersion": KERNEL_BASE_VERSION,
        "receiptProtocol": RECEIPT_PROTOCOL_VERSION,
        "evidenceSchema": EVIDENCE_SCHEMA_VERSION,
    }
    for name in sorted(CURRENT_USER_DOCS):
        path = ROOT / name
        if not path.is_file():
            raise SystemExit(f"user-facing document identity mismatch: {name}")
        text = path.read_text(encoding="utf-8")
        identity = parse_release_doc_identity(text)
        if any(identity.get(field) != expected for field, expected in expected_doc_identity.items()):
            raise SystemExit(f"structured user-facing document identity mismatch: {name}: {identity}")
        package_mentions = re.findall(
            r"(?im)^\s*>\s*(?:Current\s+(?:plugin/)?package|Package)\s*:\s*\*{0,2}([^*\s]+)",
            text,
        )
        if any(value != PACKAGE_VERSION for value in package_mentions):
            raise SystemExit(f"conflicting package identity in user-facing document: {name}")
        for line in text.splitlines():
            if re.match(r"^\s*#{1,6}.*Web UI Quality\s+\d+\.\d+\.\d+", line, flags=re.IGNORECASE) and PACKAGE_VERSION not in line and "Trust Kernel" not in line:
                raise SystemExit(f"conflicting package heading in user-facing document: {name}")
    for name in sorted(COMMERCIAL_DOCUMENTS):
        path = ROOT / name
        if not path.is_file():
            raise SystemExit(f"required commercial document is missing: {name}")
        text = path.read_text(encoding="utf-8")
        if any(token in text for token in ("<LEGAL_ENTITY>", "<CONTACT_EMAIL>", "<JURISDICTION>", "TBD_LEGAL", "REPLACE_BEFORE_GA")):
            raise SystemExit(f"commercial document still contains a release placeholder: {name}")
    skill=ROOT/"skills"/"audit-and-fix-web-ui"/"SKILL.md"
    if not skill.is_file() or PACKAGE_VERSION not in skill.read_text(encoding="utf-8"): raise SystemExit("Skill release identity is inconsistent")
    wrapper=ROOT/"scripts"/"run_runtime.py"
    if not wrapper.is_file(): raise SystemExit("public runtime entry is missing")
    readme=(ROOT/"README.md").read_text(encoding="utf-8")
    for match in re.finditer(r"\[[^\]]+\]\(([^)]+\.md)\)", readme):
        target=match.group(1)
        if "://" not in target and not (ROOT/target).is_file(): raise SystemExit(f"README references missing Markdown file: {target}")

def _validate_python() -> int:
    count = 0
    for path in sorted((ROOT / "runtime" / "python" / "web_ui_quality").rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        ast.parse(source, filename=str(path), feature_version=(3, 10))
        compile(source, str(path), "exec")
        count += 1
    return count


def _run(
    command: list[str],
    env: dict[str, str] | None = None,
    *,
    timeout_s: int = DEFAULT_GATE_TIMEOUT_SECONDS,
) -> None:
    """Run one authoritative gate in an isolated process session.

    Release gates intentionally inherit the real stdout/stderr streams. Some
    browser/test descendants in supported Host environments can stall when a
    Python parent owns/captures their output descriptor even after the direct
    child exits. Inherited streams plus a new process session avoid that class
    of orchestration deadlock; reliability is more important than quiet logs.
    """
    print(f"release gate: {' '.join(command)}", file=sys.stderr, flush=True)
    try:
        runner = ["bash", "-lc", shlex.join(command)] if os.name == "posix" else command
        completed = subprocess.run(
            runner, cwd=ROOT, env=env, timeout=timeout_s,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
    except subprocess.TimeoutExpired as error:
        raise SystemExit(f"release gate timed out after {timeout_s}s: {' '.join(command)}") from error
    if completed.returncode:
        raise SystemExit(completed.returncode)


def _run_sequence(commands: list[list[str]], env: dict[str, str] | None = None) -> None:
    """Run release gates in one shell session on POSIX to avoid nested-parent lifecycle stalls."""
    if os.name != "posix":
        for command in commands:
            _run(command, env=env)
        return
    lines = ["set -euo pipefail"]
    for command in commands:
        rendered = shlex.join(command)
        lines.append(f"echo 'release gate: {rendered}' >&2")
        lines.append(f"timeout 180s {rendered}")
    script = "\n".join(lines)
    completed = subprocess.run(
        ["bash", "-lc", script], cwd=ROOT, env=env,
        stdin=subprocess.DEVNULL, start_new_session=True,
    )
    if completed.returncode:
        raise SystemExit(completed.returncode)


def _audit_entries(entries: list[tuple[str, bytes, int]]) -> dict[str, object]:
    errors: list[str] = []
    names = [name for name, _, _ in entries]
    if not names or any(not name.startswith(f"{PRODUCT_NAME}/") for name in names):
        errors.append("archive must contain one web-ui-quality/ root")
    if len(names) != len(set(names)):
        errors.append("archive contains duplicate paths")
    for name, data, _ in entries:
        parts = Path(name).parts
        if any(
            part in {"__pycache__", ".pytest_cache", ".test-workspace", "build", "dist"}
            or part.endswith(".egg-info")
            or part.startswith("release-evidence-")
            or part.startswith("RELEASE_REPORT_")
            or part == "PKG-INFO"
            for part in parts
        ):
            errors.append(f"forbidden archive path: {name}")
        if Path(name).suffix.casefold() in {".md", ".txt", ".py", ".json", ".toml", ".yaml", ".yml", ".html", ".css", ".js"}:
            text = data.decode("utf-8", errors="replace")
            is_history = f"{PRODUCT_NAME}/references/history/" in name
            is_changelog = name == f"{PRODUCT_NAME}/CHANGELOG.md"
            if not (is_history or is_changelog) and any(version in text for version in STALE_PACKAGE_VERSIONS):
                errors.append(f"stale product version in {name}")
            if not (is_history or is_changelog):
                for line in text.splitlines():
                    if HISTORICAL_HEADING.search(line) and PACKAGE_VERSION.casefold() not in line.casefold():
                        errors.append(f"historical release heading in {name}")
                        break
    if errors:
        raise SystemExit("archive audit failed:\n- " + "\n- ".join(sorted(set(errors))))
    return {"status": "PASS", "files": len(entries), "root": f"{PRODUCT_NAME}/"}


def _tar_bytes(entries: list[tuple[str, bytes, int]]) -> bytes:
    raw = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as archive:
            for name, data, mode in entries:
                info = tarfile.TarInfo(name)
                info.size = len(data)
                info.mode = mode
                info.mtime = 0
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                archive.addfile(info, io.BytesIO(data))
    return raw.getvalue()


def _zip_bytes(entries: list[tuple[str, bytes, int]]) -> bytes:
    raw = io.BytesIO()
    with zipfile.ZipFile(raw, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data, mode in entries:
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = (mode & 0xFFFF) << 16
            archive.writestr(info, data)
    return raw.getvalue()


def validate() -> dict[str, object]:
    _validate_identity()
    python_files = _validate_python()
    env = dict(os.environ)
    env["PYTHONPATH"] = str(RUNTIME) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    public_tests = ROOT / "tests" / "public"
    public_tests_status = "AVAILABLE" if public_tests.is_dir() and (ROOT / "run_tests.py").is_file() else "NOT_DISTRIBUTED"
    # The public snapshot has a self-contained test entry point. Full Browser,
    # Host, commercial, and private-evolution qualifications are not silently
    # represented as public PASS results.
    _run(
        [sys.executable, "-B", "run_tests.py"],
        env=env,
        timeout_s=DEFAULT_GATE_TIMEOUT_SECONDS,
    )
    audit = _audit_entries(_entries())
    return {
        "status": "PASS",
        "commercialGA": "NOT_ESTABLISHED",
        "promotionStatus": "CANDIDATE_ONLY",
        "version": PACKAGE_VERSION,
        "packageStage": PACKAGE_STAGE,
        "stage": RELEASE_STAGE,
        "pythonFiles": python_files,
        "publicTests": "PASS",
        "publicTestsDirectory": public_tests_status,
        "fullInternalRegression": "NOT_RUN_PUBLIC_SNAPSHOT",
        "browserQualification": "NOT_MEASURED",
        "hostQualification": "NOT_MEASURED",
        "privateEvolutionEvidence": "EXCLUDED_FROM_PUBLIC_SNAPSHOT",
        "archiveAudit": audit,
    }


def package() -> tuple[Path, Path, Path]:
    validation = validate()
    entries = _entries()
    tar_data = _tar_bytes(entries)
    zip_data = _zip_bytes(entries)
    if tar_data != _tar_bytes(entries) or zip_data != _zip_bytes(entries):
        raise SystemExit("reproducibility check failed")
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    stem = f"{PRODUCT_NAME}-{PACKAGE_VERSION}"
    tar_path = dist / f"{stem}.tar.gz"
    zip_path = dist / f"{stem}.zip"
    digest_path = dist / f"{stem}.sha256"
    tar_path.write_bytes(tar_data)
    zip_path.write_bytes(zip_data)
    digests = {
        tar_path.name: hashlib.sha256(tar_data).hexdigest(),
        zip_path.name: hashlib.sha256(zip_data).hexdigest(),
    }
    digest_path.write_text("".join(f"{digest}  {name}\n" for name, digest in sorted(digests.items())), encoding="utf-8")
    report = {**validation, "artifacts": digests, "reproducible": True}
    (dist / f"{stem}.build.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return tar_path, zip_path, digest_path


def main() -> int:
    from web_ui_quality.release_info import configure_stdout

    configure_stdout()
    parser = argparse.ArgumentParser(description="Validate or package Web UI Quality")
    parser.add_argument("command", choices=("validate", "package"), nargs="?", default="validate")
    args = parser.parse_args()
    if args.command == "validate":
        print(json.dumps(validate(), ensure_ascii=False, indent=2, sort_keys=True))
    else:
        tar_path, zip_path, digest_path = package()
        print(json.dumps({
            "status": "PASS",
            "commercialGA": "NOT_ESTABLISHED",
            "promotionStatus": "CANDIDATE_ONLY",
            "version": PACKAGE_VERSION,
            "packageStage": PACKAGE_STAGE,
            "stage": RELEASE_STAGE,
            "tar": str(tar_path),
            "zip": str(zip_path),
            "sha256": str(digest_path),
        }, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
