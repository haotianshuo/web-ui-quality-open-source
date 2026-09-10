from __future__ import annotations

import json
from pathlib import Path

from web_ui_quality.fix_workflow import build_repair_mapping, prepare_fix_workflow


def _finding(**location: object) -> dict[str, object]:
    return {"id": "UI-BUTTON-001", "location": location}


def _project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    source = project / "src" / "components"
    source.mkdir(parents=True)
    (source / "SaveButton.tsx").write_text("export function SaveButton() { return <button>Save</button>; }\n", encoding="utf-8")
    return project


def test_complete_finding_becomes_a_host_gated_mapping(tmp_path: Path) -> None:
    project = _project(tmp_path)
    finding = _finding(
        route="/settings",
        selector="button",
        component="SaveButton",
        file="src/components/SaveButton.tsx",
        line=1,
        sourceRange={"startLine": 1, "startColumn": 1, "endLine": 1, "endColumn": 70},
    )
    mapping = build_repair_mapping(project, finding)
    assert mapping["status"] == "COMPLETE"
    assert mapping["scopeConfirmed"] is True
    assert mapping["sourceFile"] == "src/components/SaveButton.tsx"
    assert mapping["sourceRange"]["status"] == "MEASURED"
    assert [item["kind"] for item in mapping["chain"]] == [
        "Finding", "Route", "Selector", "Component", "Source File", "Source Range"
    ]


def test_missing_source_file_is_incomplete_without_filename_guessing(tmp_path: Path) -> None:
    project = _project(tmp_path)
    mapping = build_repair_mapping(
        project,
        _finding(route="/settings", selector="button", component="SaveButton", line=1),
    )
    assert mapping["status"] == "INCOMPLETE"
    assert mapping["sourceFile"] is None
    assert "Source File" in mapping["missingLinks"]
    assert mapping["scopeConfirmed"] is False


def test_multiple_explicit_source_candidates_remain_ambiguous(tmp_path: Path) -> None:
    project = _project(tmp_path)
    (project / "src" / "components" / "OtherButton.tsx").write_text("export const OtherButton = () => null;\n", encoding="utf-8")
    mapping = build_repair_mapping(
        project,
        _finding(
            route="/settings", selector="button", component="Button", sourceCandidates=[
                "src/components/OtherButton.tsx", "src/components/SaveButton.tsx"
            ], line=1,
        ),
    )
    assert mapping["status"] == "AMBIGUOUS"
    assert mapping["sourceFile"] is None
    assert mapping["ambiguousCandidates"] == [
        "src/components/OtherButton.tsx", "src/components/SaveButton.tsx"
    ]


def test_invalid_or_missing_source_path_is_rejected(tmp_path: Path) -> None:
    project = _project(tmp_path)
    mapping = build_repair_mapping(project, _finding(route="/settings", selector="button", file="../outside.tsx", line=1))
    assert mapping["status"] == "REJECTED"
    assert mapping["scopeConfirmed"] is False
    assert mapping["rejectedReason"] in {"SOURCE_SCOPE_ESCAPE", "SOURCE_FILE_MISSING"}


def test_fix_preparation_consumes_mapping_and_keeps_runtime_read_only(tmp_path: Path) -> None:
    project = _project(tmp_path)
    finding = _finding(
        route="/settings", selector="button", component="SaveButton",
        file="src/components/SaveButton.tsx", line=1,
    )
    evidence = tmp_path / "finding-evidence.json"
    evidence.write_text(json.dumps({"topFindings": [finding]}), encoding="utf-8")
    plan = prepare_fix_workflow(
        project, tmp_path / "output", evidence=evidence, request="修复设置页移动端按钮错位",
    )
    assert plan["status"] == "PATCH_CANDIDATE_REQUIRED"
    assert plan["repairMapping"]["status"] == "COMPLETE"
    assert plan["scopeConfirmed"] is True
    assert plan["hostBridgeAction"] == "submitPatchCandidate"
    assert plan["writeAuthorized"] is False
    assert plan["sourceProjectChanged"] is False
    assert plan["files"] == [{
        "path": "src/components/SaveButton.tsx",
        "changeType": "candidate",
        "reason": "由显式 Host 范围或 Finding 源码证据确认",
    }]
