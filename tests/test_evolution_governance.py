from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVOLUTION = ROOT / "evolution"
DIMENSIONS = {
    "uiInteraction",
    "backendBusiness",
    "dataIntegration",
    "stabilityReliability",
    "securityPrivacy",
    "codeHealth",
}


def _version_key(value: str) -> tuple[int, int, int, int, int]:
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)(?:-alpha\.(\d+)-shadow)?", value)
    assert match, f"not a supported semver track version: {value}"
    major, minor, patch, alpha = match.groups()
    return int(major), int(minor), int(patch), 0 if alpha is None else 1, int(alpha or 0)


def test_ledger_and_board_keep_the_six_fixed_quality_weights() -> None:
    ledger = json.loads((EVOLUTION / "evolution-ledger.json").read_text(encoding="utf-8"))
    board = json.loads((EVOLUTION / "quality-target-board.json").read_text(encoding="utf-8"))

    assert set(ledger["qualityWeights"]) == DIMENSIONS
    assert set(board["weights"]) == DIMENSIONS
    assert ledger["qualityWeights"] == board["weights"]
    assert sum(ledger["qualityWeights"].values()) == 100
    assert ledger["qualityWeights"] == {
        "uiInteraction": 30,
        "backendBusiness": 25,
        "dataIntegration": 15,
        "stabilityReliability": 10,
        "securityPrivacy": 10,
        "codeHealth": 10,
    }


def test_version_ledger_is_monotonic_and_experimental_track_is_fail_closed() -> None:
    from web_ui_quality.release_info import EXPERIMENTAL_VERSION

    ledger = json.loads((EVOLUTION / "evolution-ledger.json").read_text(encoding="utf-8"))
    entries = ledger["entries"]
    assert [_version_key(row["version"]) for row in entries] == sorted(_version_key(row["version"]) for row in entries)
    assert entries[0]["version"] == "4.3.0"
    assert entries[1]["version"] == "4.4.0-alpha.1-shadow"
    assert entries[-1]["version"] == EXPERIMENTAL_VERSION
    assert entries[-1]["promotionAllowed"] is False
    assert entries[-1]["promotionDecision"] == "HOLD"
    assert "Independent exact-archive qualification" in entries[-1]["blocked"][0]
    board_track = json.loads((EVOLUTION / "quality-target-board.json").read_text(encoding="utf-8")).get("track")
    assert board_track
    assert board_track == "SHADOW_ADVISORY_ONLY"


def test_runtime_and_metadata_expose_the_same_next_experimental_identity() -> None:
    from web_ui_quality.release_info import EXPERIMENTAL_STAGE, EXPERIMENTAL_VERSION, experimental_identity

    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    identity = experimental_identity()
    assert EXPERIMENTAL_VERSION == "4.4.0-alpha.18-shadow"
    assert EXPERIMENTAL_STAGE == EXPERIMENTAL_VERSION
    assert identity["experimentalVersion"] == EXPERIMENTAL_VERSION
    assert identity["stage"] == EXPERIMENTAL_STAGE
    assert identity["authorityMode"] == "SHADOW_ADVISORY_ONLY"
    assert f'experimental-package-stage = "{EXPERIMENTAL_VERSION}"' in pyproject


def test_markdown_surfaces_preserve_claim_and_weight_boundaries() -> None:
    ledger = (EVOLUTION / "EVOLUTION_LEDGER.md").read_text(encoding="utf-8")
    board = (EVOLUTION / "QUALITY_TARGET_BOARD.md").read_text(encoding="utf-8")
    from web_ui_quality.release_info import EXPERIMENTAL_VERSION

    for value in ("30%", "25%", "15%", "10%", "NOT_MEASURED", "HOLD", EXPERIMENTAL_VERSION):
        assert value in ledger or value in board
    assert "不能获得写入权限" in ledger
    assert "商业 GA" in board


def test_release_file_walk_includes_the_shipped_evolution_contract() -> None:
    from scripts import release

    included = {path.relative_to(release.ROOT).as_posix() for path in release._files()}
    assert {
        "evolution/evolution-ledger.json",
        "evolution/quality-target-board.json",
        "evolution/EVOLUTION_LEDGER.md",
        "evolution/QUALITY_TARGET_BOARD.md",
    } <= included
