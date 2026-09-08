from pathlib import Path
import pytest
from web_ui_quality.execution_state import ExecutionState,browser_result_status,evidence_state
from web_ui_quality.intent_router import route_user_intent
from web_ui_quality.user_outcome import user_outcome

def test_state_machine_cannot_skip():
    s=ExecutionState()
    with pytest.raises(ValueError): s.advance("PLAN")
    for stage in ("PREFLIGHT","PLAN","HOST_APPLY","VERIFY","REPORT"): s.advance(stage)
    assert s.stage=="REPORT"

def test_browser_pass_requires_execution_and_measurement():
    with pytest.raises(ValueError): browser_result_status(browser_executed=False,browser_measured=False,browser_verified=True)
    assert browser_result_status(browser_executed=True,browser_measured=True,browser_verified=True)=="BROWSER_PASS"

def test_evidence_lifecycle_is_monotonic():
    with pytest.raises(ValueError): evidence_state(requested=True,attempted=False,executed=True,measured=False,verified=False)

def test_natural_language_defaults_read_only_and_fix_is_routed():
    assert route_user_intent("看看这个页面")["writeRequested"] is False
    assert route_user_intent("帮我修好这个页面")["writeRequested"] is True
    assert route_user_intent("不确定")["readOnlyRequired"] is True

def test_three_user_states():
    assert user_outcome({"status":"VERIFIED"})["result"]=="已完成并验证"
    assert user_outcome({"status":"NOT_VERIFIED"})["result"]=="已完成但部分未验证"
    assert user_outcome({"status":"BLOCKED","blockers":["auth"]})["result"]=="需要你处理"



def test_public_entry_commands_execute() -> None:
    import subprocess
    import sys

    root = Path(__file__).resolve().parents[1]
    commands = (
        [sys.executable, "-B", "scripts/run_runtime.py", "--help"],
        [sys.executable, "-B", "scripts/run_runtime.py", "doctor"],
        [sys.executable, "-B", "scripts/run_runtime.py", "run", "--help"],
        [sys.executable, "-B", "scripts/run_runtime.py", "ui-inventory", "--help"],
    )
    for command in commands:
        completed = subprocess.run(command, cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
        assert completed.returncode == 0, (command, completed.stdout, completed.stderr)


def test_public_docs_use_root_runtime_entry() -> None:
    root = Path(__file__).resolve().parents[1]
    readme = (root / "README.md").read_text(encoding="utf-8")
    skill = (root / "skills" / "audit-and-fix-web-ui" / "SKILL.md").read_text(encoding="utf-8")
    assert "skills/audit-and-fix-web-ui/scripts/run_runtime.py" not in readme
    assert "skills/audit-and-fix-web-ui/scripts/run_runtime.py" not in skill
    assert "web-ui-quality run ." not in readme
    assert "python -B scripts/run_runtime.py" in readme
    assert "python -B scripts/run_runtime.py" in skill



def test_node_holdout_entry_is_cross_platform_path_safe(tmp_path: Path) -> None:
    import json
    import shutil
    import subprocess

    node = shutil.which("node")
    if not node:
        raise AssertionError("Node is required by the shipped NODE_SCRIPT holdout oracle")
    root = Path(__file__).resolve().parents[1]
    cases = json.loads((root / "tests" / "fixtures" / "fault-injection-holdout-v1" / "cases.json").read_text(encoding="utf-8"))
    chosen = [case for case in cases if case.get("id") in {"holdout-latest-query", "holdout-page-index"}]
    assert len(chosen) == 2
    target_root = tmp_path / "路径 with spaces"
    target_root.mkdir()
    for case in chosen:
        for rel, source in case["cleanFiles"].items():
            assert "`file://${process.argv[1]}`" not in source
            assert "pathToFileURL(process.argv[1]).href" in source
            target = target_root / Path(rel).name
            target.write_bytes(source.encode("utf-8"))
            completed = subprocess.run([node, str(target)], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15)
            assert completed.returncode == 0, (completed.stdout, completed.stderr)
            for expected in case["oracle"][0]["stdoutContains"]:
                assert expected in completed.stdout
