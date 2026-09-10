from __future__ import annotations

import io
from pathlib import Path

import pytest

from web_ui_quality import __main__ as cli
from web_ui_quality.agent_adapter import render_agent_result
from web_ui_quality.experience_fix import run_experience_fix
from web_ui_quality.task_result import build_task_result


VIEWPORTS = ((390, 844), (768, 1024), (1440, 900))


def _browser_record(url: str, width: int, height: int) -> dict[str, object]:
    viewport = {"width": width, "height": height}
    return {
        "label": f"{width}x{height}",
        "url": url,
        "viewport": viewport,
        "requestedViewport": dict(viewport),
        "actualBrowserViewport": dict(viewport),
        "reportedEvidenceViewport": dict(viewport),
        "viewportNormalization": {
            "status": "MATCHED",
            "requested": dict(viewport),
            "actual": dict(viewport),
            "reported": dict(viewport),
            "documentScrollWidth": width,
            "bodyScrollWidth": width,
            "mismatches": [],
        },
        "httpStatus": 200,
        "evidenceStatus": "VERIFIED",
        "validRender": True,
        "status": "PASS",
        "pageErrors": [],
        "requestFailures": [],
        "criticalRequestFailures": [],
        "blockedRequests": [],
        "horizontalOverflow": False,
        "resourceIntegrity": {"status": "PASS", "coreFailures": []},
        "stability": {"status": "STABLE", "samples": 3},
        "mutationFirewall": {"status": "PASS"},
    }


def _inspection_report(url: str, *, status: str, finding: bool, records: bool = True) -> dict[str, object]:
    rows = [_browser_record(url, width, height) for width, height in VIEWPORTS] if records else []
    top_findings = [{"summary": "mobile overflow", "resultLabel": "现在会出错", "severity": "high"}] if finding else []
    return {
        "schemaVersion": "2.3-p0a",
        "status": status,
        "deliveryConclusion": "inspection result",
        "target": {"url": url, "projectRoot": ".", "source": "project+url"},
        "preflight": {
            "status": "READY" if records else "NOT_VERIFIED",
            "canContinue": records,
            "authRequired": False,
            "blockers": [],
            "warnings": [],
            "browser": {"available": True},
        },
        "pageHealth": {"pageStatus": "PASS" if status == "PASS" else "NOT_VERIFIED", "browserExecuted": records},
        "runtime": {
            "status": "PASS" if records else "NOT_VERIFIED",
            "url": url,
            "records": rows,
            "viewports": [{"width": width, "height": height} for width, height in VIEWPORTS],
        },
        "journey": {"status": "PASS" if status == "PASS" else "NOT_VERIFIED", "journey": [], "runs": []},
        "findings": top_findings,
        "topFindings": top_findings,
        "coverageSummary": {"viewports": [f"{w}x{h}" for w, h in VIEWPORTS]},
        "open": "index.html",
    }


@pytest.mark.parametrize(
    ("case", "status", "finding", "expected_browser"),
    (
        ("T01", "FAIL", True, "BROWSER_NOT_VERIFIED"),
        ("T02", "PASS", False, "BROWSER_PASS"),
        ("T06", "PASS", False, "BROWSER_PASS"),
    ),
)
def test_read_only_browser_lifecycle_reaches_all_result_surfaces(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
    status: str,
    finding: bool,
    expected_browser: str,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "index.html").write_text("<main>fixture</main>\n", encoding="utf-8")
    target_url = "http://app.test/current"

    monkeypatch.setattr(
        "web_ui_quality.experience_fix.run_smart_acceptance",
        lambda *args, **kwargs: _inspection_report(str(kwargs["url"]), status=status, finding=finding),
    )
    result = run_experience_fix(
        project,
        tmp_path / "artifacts",
        request="检查当前页面，不要为了找问题修改文件。",
        mode="CHECK",
        task_id=f"read-only-{case}",
        session_id=f"read-only-session-{case}",
        url=target_url,
    )

    task = result["taskResult"]
    assert result["intentRoute"]["writeAuthorized"] is False
    assert result.get("hostWriteReceipt") is None
    assert "fixPlan" not in result
    assert "repairReport" not in result
    assert result["evidenceLifecycle"]["browser"] == {
        "requested": True,
        "attempted": True,
        "executed": True,
        "measured": True,
        "verified": expected_browser == "BROWSER_PASS",
    }
    assert result["browserExecutionStatus"] == expected_browser
    assert task["kind"] == "INSPECTION"
    assert task["verification"]["browser"] == expected_browser
    assert result["userOutcome"]["verified"]["browser"] == expected_browser

    machine = cli._repair_machine_contract(result)
    assert machine["verification"]["browser"] == expected_browser
    agent = render_agent_result("codex", result)
    assert agent["taskResult"]["verification"]["browser"] == expected_browser
    assert agent["writeAuthorized"] is False
    stream = io.StringIO()
    cli._emit_human_repair_report(result, stream=stream)
    human = stream.getvalue()
    if expected_browser == "BROWSER_PASS":
        assert "目标页面已在本次浏览器条件下验证" in human
    else:
        assert "页面尚未在真实浏览器中完成充分验证" in human


def test_unexecuted_browser_remains_not_measured(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "index.html").write_text("<main>fixture</main>\n", encoding="utf-8")
    monkeypatch.setattr(
        "web_ui_quality.experience_fix.run_smart_acceptance",
        lambda *args, **kwargs: _inspection_report(str(kwargs["url"]), status="NOT_VERIFIED", finding=False, records=False),
    )

    result = run_experience_fix(
        project,
        tmp_path / "artifacts",
        request="检查当前页面，不要修改文件。",
        mode="CHECK",
        task_id="read-only-no-browser",
        session_id="read-only-no-browser-session",
        url="http://app.test/current",
    )

    assert result["evidenceLifecycle"]["browser"]["executed"] is False
    assert result["browserExecutionStatus"] == "NOT_MEASURED"
    assert result["taskResult"]["verification"]["browser"] == "NOT_MEASURED"
    assert result.get("hostWriteReceipt") is None


def test_task_result_does_not_promote_unbound_or_invalid_browser_status() -> None:
    stale = build_task_result(
        {
            "status": "FAIL",
            "mode": "CHECK",
            "browserExecutionStatus": "BROWSER_PASS",
            "before": {"preflight": {"browser": {"available": True}}, "runtime": {"records": []}},
        }
    )
    assert stale["verification"]["browser"] == "NOT_MEASURED"

    wrong_target_and_viewport = build_task_result(
        {
            "status": "FAIL",
            "mode": "CHECK",
            "browserExecutionStatus": "BROWSER_NOT_VERIFIED",
            "evidenceLifecycle": {"browser": {"requested": True, "attempted": True, "executed": True, "measured": True, "verified": False}},
            "before": {
                "preflight": {"browser": {"available": True}},
                "runtime": {"url": "http://app.test/old", "records": [{"url": "http://app.test/old", "viewportNormalization": {"status": "MISMATCH"}}]},
            },
        }
    )
    assert wrong_target_and_viewport["verification"]["browser"] == "BROWSER_NOT_VERIFIED"


def test_t05_unreachable_repair_stays_inconclusive_and_not_verified() -> None:
    result = build_task_result(
        {
            "status": "NOT_VERIFIED",
            "mode": "FIX_AND_VERIFY",
            "repairVerification": {"status": "NOT_VERIFIED", "blockers": ["target unreachable"], "warnings": []},
            "repairReport": {"status": "NOT_VERIFIED", "verificationSummary": {"overall": "NOT_VERIFIED", "browser": "INCONCLUSIVE", "hostWrite": "HOST_WRITE_V3_VERIFIED"}},
        }
    )
    assert result["outcome"] == "NOT_VERIFIED"
    assert result["verification"]["browser"] == "INCONCLUSIVE"
