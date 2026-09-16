from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from agent_benchmark_qualification import _save, aggregate, ingest  # noqa: E402
from fault_injection_harness import (  # noqa: E402
    _oracle_result,
    load_cases,
    prepare_all,
    prepare_case,
    score_host_observation,
)
from web_ui_quality.benchmark_evaluation import (  # noqa: E402
    classify_agent_claim,
    evaluate_problem_solved,
    normalize_execution_status,
)
from web_ui_quality.project_baseline import build_project_baseline  # noqa: E402


def _case(**overrides):
    value = {
        "id": "real-user-regression",
        "request": "repair the known issue",
        "rootSource": "src/bug.css",
        "cleanContent": "good\n",
        "injectedContent": "bad\n",
        "expectedRootSources": ["src/bug.css"],
        "allowedScope": ["src/bug.css"],
        "cleanFiles": {"src/bug.css": "good\n"},
        "injectedFiles": {"src/bug.css": "bad\n"},
        "oracle": [{"type": "FILE_CONTAINS", "path": "src/bug.css", "required": ["good"], "forbidden": ["bad"]}],
        "expectation": "REPAIR",
        "difficulty": "D2",
        "family": "real-user-regression",
        "archetype": "real-user-regression",
    }
    value.update(overrides)
    return value


def test_claim_classifier_rejects_negated_success_and_fixed_width_language() -> None:
    negative = classify_agent_claim("I don't consider the issue solved yet.")
    fixed_width = classify_agent_claim("The layout uses a fixed-width 1000px container.")
    positive = classify_agent_claim("The issue was fixed and verification passed.")

    assert negative["claimStatus"] == "NOT_SUCCESS"
    assert negative["problemSolved"] is False
    assert fixed_width["claimStatus"] == "UNKNOWN"
    assert "NON_RESOLUTION_FIXED_USAGE" in fixed_width["reasonCodes"]
    assert positive["claimStatus"] == "SUCCESS"


@pytest.mark.parametrize(
    ("status", "expected"),
    (
        ("USAGE_LIMIT", "INFRASTRUCTURE_BLOCKED"),
        ("quota exceeded", "INFRASTRUCTURE_BLOCKED"),
        ("INVALID_SETUP", "INVALID_SETUP"),
        ("COMPLETED", "COMPLETED"),
    ),
)
def test_execution_status_normalization_is_explicit(status: str, expected: str) -> None:
    assert normalize_execution_status(status) == expected


def test_problem_solved_requires_oracle_and_compatible_claim() -> None:
    blocked = evaluate_problem_solved(
        claim="The issue was fixed.", outcome="VERIFIED", execution_status="USAGE_LIMIT",
        run_validity="VALID", oracle_objective_satisfied=True, scope_correct=True,
        no_forbidden_drift=True,
    )
    negated = evaluate_problem_solved(
        claim="I don't consider the issue solved yet.", outcome="VERIFIED", execution_status="COMPLETED",
        run_validity="VALID", oracle_objective_satisfied=True, scope_correct=True,
        no_forbidden_drift=True,
    )

    assert blocked["problemSolved"] is None
    assert blocked["eligibleForSuccessRate"] is False
    assert negated["problemSolved"] is False
    assert negated["eligibleForSuccessRate"] is True


def test_diagnosis_uses_defect_oracle_and_does_not_require_mutation(tmp_path: Path) -> None:
    case = _case(
        id="diagnosis-regression",
        archetype="diagnosis-regression",
        expectation="DIAGNOSIS",
        oracle=[],
        defectOracle=[{"type": "FILE_CONTAINS", "path": "src/bug.css", "required": ["bad"], "forbidden": ["good"]}],
    )
    project = tmp_path / "project"
    prepared = prepare_case(case, project)
    row = score_host_observation(
        prepared["evaluatorManifest"], project,
        {"outcome": "VERIFIED", "rootCauseFiles": ["src/bug.css"], "regressions": [], "claim": "The root cause was identified and the problem was diagnosed."},
    )

    assert row["oracleMode"] == "DIAGNOSIS"
    assert row["diagnosisSuccess"] is True
    assert row["problemSolved"] is True
    assert row["changedFiles"] == []


def test_negative_success_claim_cannot_override_a_passing_repair_oracle(tmp_path: Path) -> None:
    case = _case(id="claim-regression", archetype="claim-regression")
    project = tmp_path / "project"
    prepared = prepare_case(case, project)
    (project / "src/bug.css").write_text("good\n", encoding="utf-8")
    row = score_host_observation(
        prepared["evaluatorManifest"], project,
        {"outcome": "VERIFIED", "rootCauseFiles": ["src/bug.css"], "regressions": [], "claim": "I don't consider the issue solved yet."},
    )

    assert row["groundTruthSatisfied"] is True
    assert row["problemSolved"] is False
    assert row["repairSuccess"] is False
    assert "NEGATED_SUCCESS_CLAIM" in row["problemSolvedReasonCodes"]


def test_failed_defect_injection_is_invalid_setup_and_excluded(tmp_path: Path) -> None:
    case = _case(
        id="invalid-injection",
        archetype="invalid-injection",
        injectedFiles={},
        injectedContent=None,
    )
    project = tmp_path / "project"
    prepared = prepare_case(case, project)
    row = score_host_observation(
        prepared["evaluatorManifest"], project,
        {"outcome": "VERIFIED", "rootCauseFiles": ["src/bug.css"], "regressions": [], "claim": "The issue was fixed."},
    )

    assert prepared["evaluatorManifest"]["defectInjection"]["status"] == "INVALID_SETUP"
    assert row["runValidity"] == "INVALID_SETUP"
    assert row["problemSolved"] is None
    assert row["eligibleForSuccessRate"] is False


def test_task_relevant_snapshot_tracks_declared_generated_output_but_ignores_decoy_output(tmp_path: Path) -> None:
    tracked_case = _case(
        id="generated-output",
        archetype="generated-output",
        allowedScope=["src/bug.css", "dist/**"],
        generatedTargets=["dist/**"],
    )
    tracked_project = tmp_path / "tracked"
    tracked = prepare_case(tracked_case, tracked_project)
    (tracked_project / "src/bug.css").write_text("good\n", encoding="utf-8")
    (tracked_project / "dist").mkdir()
    (tracked_project / "dist/bundle.js").write_text("generated-v2\n", encoding="utf-8")
    tracked_row = score_host_observation(
        tracked["evaluatorManifest"], tracked_project,
        {"outcome": "VERIFIED", "rootCauseFiles": ["src/bug.css"], "regressions": [], "claim": "The issue was fixed."},
    )

    ignored_case = _case(id="ignored-output", archetype="ignored-output")
    ignored_project = tmp_path / "ignored"
    ignored = prepare_case(ignored_case, ignored_project)
    (ignored_project / "src/bug.css").write_text("good\n", encoding="utf-8")
    (ignored_project / "dist").mkdir()
    (ignored_project / "dist/bundle.js").write_text("decoy\n", encoding="utf-8")
    ignored_row = score_host_observation(
        ignored["evaluatorManifest"], ignored_project,
        {"outcome": "VERIFIED", "rootCauseFiles": ["src/bug.css"], "regressions": [], "claim": "The issue was fixed."},
    )

    assert "dist/bundle.js" in tracked_row["changedFiles"]
    assert tracked_row["unexpectedChanges"] == []
    assert tracked_row["scopePrecision"] == pytest.approx(1.0)
    assert "dist/bundle.js" not in ignored_row["changedFiles"]


def test_explicit_generated_target_is_indexed_by_project_baseline(tmp_path: Path) -> None:
    output = tmp_path / "project" / "dist" / "bundle.js"
    output.parent.mkdir(parents=True)
    output.write_text("generated\n", encoding="utf-8")

    baseline = build_project_baseline(tmp_path / "project", target_files=["dist/bundle.js"])

    assert baseline["targetCoverage"]["status"] == "COMPLETE"
    assert "dist/bundle.js" in baseline["targetCoverage"]["indexed"]


def test_aggregate_excludes_infrastructure_run_from_success_denominator(tmp_path: Path) -> None:
    case = _case(id="denominator-regression", archetype="denominator-regression")
    controller = tmp_path / "controller"
    prepared = prepare_all(controller, repetitions=2, cases_override=[case])
    plan = json.loads((controller / "benchmark-plan.json").read_text(encoding="utf-8"))
    for index, run in enumerate(plan["runs"]):
        observation = {
            "outcome": "VERIFIED", "rootCauseFiles": ["src/bug.css"], "regressions": [],
            "claim": "The issue was fixed.",
        }
        if run["repetition"] == 1:
            observation["executionStatus"] = "USAGE_LIMIT"
        else:
            project = Path(run["projectPath"])
            (project / "src/bug.css").write_text("good\n", encoding="utf-8")
        host = {
            "schemaVersion": "4", "kind": "HOST_RESULT", "protocolVersion": "4",
            "runId": run["runId"], "caseId": run["caseId"], "repetition": run["repetition"],
            "conditionDigest": run["conditionDigest"], "host": run["plannedHost"], "conditions": run["plannedConditions"],
            "observation": observation,
            "metrics": {"wallTimeSeconds": 1.0, "inputTokens": 1, "outputTokens": 1, "costUsd": 0.0, "hostInteractions": 1},
            "claimBoundary": "test",
        }
        incoming = controller / f"incoming-{index}.json"
        _save(incoming, host)
        ingest(controller, incoming)
    report = aggregate(controller)

    assert report["completedRuns"] == 2
    assert report["eligibleRuns"] == 1
    assert report["successDenominator"] == 1
    assert report["repairSuccessRate"] == pytest.approx(1.0)
    assert report["infrastructureBlockedRuns"] == 1


def test_browser_responsive_oracle_reports_all_requested_viewports_when_available(tmp_path: Path) -> None:
    pytest.importorskip("playwright")
    case = _case(
        id="browser-matrix-regression",
        archetype="browser-matrix-regression",
        cleanFiles={"index.html": "<!doctype html><button id='cta'>Go</button>\n", "src/style.css": "#cta { min-width: 44px; min-height: 44px; }\n"},
        injectedFiles={"index.html": "<!doctype html><button id='cta'>Go</button>\n", "src/style.css": "#cta { min-width: 1px; min-height: 1px; }\n"},
        expectedRootSources=["src/style.css"],
        allowedScope=["src/style.css"],
        oracle=[{"type": "BROWSER_ASSERT", "path": "index.html", "responsive": True, "stylePaths": ["src/style.css"], "assertions": [{"kind": "visible", "selector": "#cta", "expected": True}]}],
    )
    project = tmp_path / "project"
    prepared = prepare_case(case, project)
    (project / "src/style.css").write_text("#cta { min-width: 44px; min-height: 44px; }\n", encoding="utf-8")
    row = score_host_observation(
        prepared["evaluatorManifest"], project,
        {"outcome": "VERIFIED", "rootCauseFiles": ["src/style.css"], "regressions": [], "claim": "The issue was fixed."},
    )
    browser = next(item for item in row["oracleResults"] if item["type"] == "BROWSER_ASSERT")
    assert len(browser["viewports"]) == 3
    assert len(browser["viewportResults"]) == 3
