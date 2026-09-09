from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib


ROOT = Path(__file__).resolve().parents[2]


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
    assert "4.3.0" in skill_path.read_text(encoding="utf-8")

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
