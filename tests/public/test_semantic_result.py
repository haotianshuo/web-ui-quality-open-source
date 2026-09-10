from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

from web_ui_quality.task_result import build_task_result, human_status_explanation


ROOT = Path(__file__).resolve().parents[2]
REQUEST = "检查中文结账页移动端布局，不要修改登录逻辑"


def _cli(*flags: str) -> subprocess.CompletedProcess[bytes]:
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(ROOT / "runtime" / "python")
    environment["PYTHONIOENCODING"] = "cp936:strict"
    return subprocess.run(
        [
            sys.executable,
            "-B",
            "scripts/run_runtime.py",
            "run",
            *flags,
            "examples/scope-drift-demo",
            REQUEST,
        ],
        cwd=ROOT,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=30,
    )


def _task(completed: subprocess.CompletedProcess[bytes]) -> dict[str, object]:
    value = json.loads(completed.stdout.decode("utf-8"))
    return value.get("taskResult", value)


def test_task_result_exposes_one_canonical_reason_code() -> None:
    result = build_task_result(
        {
            "status": "NOT_VERIFIED",
            "before": {
                "preflight": {
                    "browser": {"available": True},
                    "blockers": ["No runnable URL was supplied"],
                }
            },
        },
        request=REQUEST,
    )
    assert result["reasonCode"] == "INSUFFICIENT_EVIDENCE"
    assert human_status_explanation(str(result["reasonCode"])) == "现有证据不足以证明任务成功。"


def test_json_and_ci_share_the_same_semantic_projection() -> None:
    structured = _cli("--json")
    ci = _cli("--ci", "--require", "VERIFIED")
    assert structured.returncode == 0
    assert ci.returncode == 3
    json_task = _task(structured)
    ci_task = _task(ci)
    semantic_fields = (
        "schemaVersion",
        "kind",
        "request",
        "protectedScope",
        "executionStatus",
        "outcome",
        "subjectStatus",
        "reasonCode",
        "coverage",
        "observations",
        "hypotheses",
        "changes",
        "verification",
        "claims",
        "uncertainties",
        "nextAction",
        "taskState",
        "review",
        "claimBoundary",
        "repairStatus",
        "repairReport",
    )
    assert {field: json_task.get(field) for field in semantic_fields} == {
        field: ci_task.get(field) for field in semantic_fields
    }

    plain = _cli()
    assert plain.returncode == 0
    plain_text = plain.stdout.decode("utf-8")
    assert "结果：" in plain_text
    assert human_status_explanation(str(json_task["reasonCode"])) in plain_text
    assert "下一步：" in plain_text


def test_reason_code_distinguishes_environment_evidence_and_authority_boundaries() -> None:
    cases = (
        (
            {"status": "NOT_VERIFIED", "before": {"preflight": {"browser": {"available": False}}}},
            "BROWSER_UNAVAILABLE",
        ),
        (
            {"status": "NOT_VERIFIED", "before": {"preflight": {"blockers": ["network is blocked"]}}},
            "NETWORK_BLOCKED",
        ),
        (
            {"status": "NOT_VERIFIED", "before": {"preflight": {"blockers": ["dependency missing"]}}},
            "DEPENDENCY_MISSING",
        ),
        (
            {"status": "NOT_VERIFIED_ENVIRONMENT"},
            "ENV_BLOCKED",
        ),
        (
            {"status": "AWAITING_HOST_WRITE", "mode": "FIX_AND_VERIFY"},
            "MANUAL_DECISION_REQUIRED",
        ),
        (
            {"status": "FAIL", "mode": "CHECK"},
            "FINDINGS_DETECTED",
        ),
        (
            {"status": "FAIL", "mode": "FIX_AND_VERIFY"},
            "TASK_FAILED",
        ),
    )
    for raw, expected in cases:
        result = build_task_result(raw, request=REQUEST)
        assert result["reasonCode"] == expected
