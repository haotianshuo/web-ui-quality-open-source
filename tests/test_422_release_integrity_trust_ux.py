from __future__ import annotations

import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from web_ui_quality.browser_request_policy import (
    bind_approved_requests,
    navigation_route_key,
    request_policy_digest,
    validate_bound_approved_requests,
)
from web_ui_quality.condition_registry import RunConditions, compare_conditions
from web_ui_quality.contracts import ContractViolation
from web_ui_quality.mutation_firewall import BrowserMutationFirewall


ROOT = Path(__file__).resolve().parents[1]


def _load_release_gate():
    path = ROOT / "scripts" / "release_gate.py"
    spec = importlib.util.spec_from_file_location("wuq_release_gate_422_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_release_gate_parent_package_absent_is_structured(monkeypatch):
    gate = _load_release_gate()

    def fake_find_spec(name):
        if name == "playwright":
            raise ModuleNotFoundError("playwright")
        return SimpleNamespace()

    monkeypatch.setattr(gate.importlib.util, "find_spec", fake_find_spec)
    result = gate._dependency_preflight("core")
    assert result["status"] == "PASS"
    assert result["playwright"] == "NOT_INSTALLED"
    assert result["browserRuntime"] == "NOT_MEASURED"
    json.dumps(result)


def test_release_gate_parent_exists_child_absent_full_fails_before_collection(monkeypatch):
    gate = _load_release_gate()

    def fake_find_spec(name):
        if name == "playwright.sync_api":
            return None
        return SimpleNamespace()

    monkeypatch.setattr(gate.importlib.util, "find_spec", fake_find_spec)
    result = gate._dependency_preflight("full")
    assert result["status"] == "FAIL"
    assert result["reasonCode"] == "RELEASE_GATE_DEPENDENCY_MISSING"
    assert "playwright.sync_api" in result["missingCapabilities"]
    assert "chromium-family-executable" in result["missingCapabilities"]
    json.dumps(result)


def test_release_gate_browser_executable_absent_full_is_structured(monkeypatch):
    gate = _load_release_gate()
    monkeypatch.setattr(gate, "_safe_find_spec", lambda *args, **kwargs: (True, None))
    monkeypatch.setattr(
        gate,
        "resolve_browser_executable",
        lambda *_a, **_k: {"available": False, "reason": "no chromium-family executable"},
    )
    result = gate._dependency_preflight("full")
    assert result["status"] == "FAIL"
    assert result["browserRuntime"] == "MISSING"
    assert result["missingCapabilities"] == ["chromium-family-executable"]
    assert result["remediation"]
    json.dumps(result)


def test_browser_security_collection_keeps_non_browser_tests_when_playwright_is_absent():
    source = (ROOT / "tests" / "test_420_browser_security.py").read_text(encoding="utf-8")
    assert 'pytest.importorskip("playwright.sync_api"' not in source
    assert "BROWSER_REQUIRED = pytest.mark.skipif" in source
    assert source.count("@BROWSER_REQUIRED") == 3


def test_browser_security_collects_full_module_when_playwright_is_absent(tmp_path):
    fake_root = tmp_path / "no-playwright-sync-api"
    fake_package = fake_root / "playwright"
    fake_package.mkdir(parents=True)
    (fake_package / "__init__.py").write_text("# deliberately no sync_api\n", encoding="utf-8")
    env = os.environ.copy()
    runtime_root = ROOT / "runtime" / "python"
    env["PYTHONPATH"] = os.pathsep.join([str(fake_root), str(runtime_root)])
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    completed = subprocess.run(
        [sys.executable, "-B", "-m", "pytest", "--collect-only", "-q", "tests/test_420_browser_security.py"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    assert completed.returncode == 0, completed.stderr
    assert "17 tests collected" in completed.stdout


@pytest.mark.parametrize("compact", [False, True])
def test_release_gate_missing_playwright_outputs_valid_json_without_traceback(monkeypatch, capsys, compact):
    gate = _load_release_gate()
    missing_core = {
        "status": "PASS",
        "mode": "core",
        "pytest": "PASS",
        "playwright": "NOT_INSTALLED",
        "browserRuntime": "NOT_MEASURED",
        "reasonCode": None,
        "missingCapabilities": [],
        "pytestReason": None,
        "playwrightReason": "playwright package unavailable",
        "browserReason": "playwright package unavailable",
        "remediation": [],
        "claimBoundary": "Core validation does not require optional Browser capability.",
    }
    monkeypatch.setattr(gate, "_dependency_preflight", lambda mode: {**missing_core, "mode": mode})

    def fake_worker(commands, env, timeout_s=900):
        return ([{"command": command, "status": "PASS", "exitCode": 0} for command in commands], {"status": "PASS", "exitCode": 0})

    monkeypatch.setattr(gate, "_run_worker", fake_worker)
    monkeypatch.setattr(sys, "argv", ["release_gate.py", "--mode", "core"] + (["--compact"] if compact else []))
    assert gate.main() == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["status"] == "PASS"
    assert payload["dependencyPreflight"]["playwright"] == "NOT_INSTALLED"
    assert payload["dependencyPreflight"]["browserRuntime"] == "NOT_MEASURED"
    assert "Traceback" not in captured.err


@pytest.mark.parametrize("compact", [False, True])
def test_release_gate_full_missing_playwright_fails_before_test_collection(monkeypatch, capsys, compact):
    gate = _load_release_gate()
    missing_full = {
        "status": "FAIL",
        "mode": "full",
        "pytest": "PASS",
        "playwright": "NOT_INSTALLED",
        "browserRuntime": "MISSING",
        "reasonCode": "RELEASE_GATE_DEPENDENCY_MISSING",
        "missingCapabilities": ["playwright.sync_api", "chromium-family-executable"],
        "pytestReason": None,
        "playwrightReason": "playwright package unavailable",
        "browserReason": "playwright package unavailable",
        "remediation": ["Install release-full dependencies."],
        "claimBoundary": "Full release qualification requires Browser capability.",
    }
    monkeypatch.setattr(gate, "_dependency_preflight", lambda mode: missing_full)
    monkeypatch.setattr(gate, "_run_worker", lambda *_a, **_k: pytest.fail("Full mode must fail before test collection"))
    monkeypatch.setattr(sys, "argv", ["release_gate.py", "--mode", "full"] + (["--compact"] if compact else []))
    assert gate.main() == 1
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["status"] == "FAIL"
    assert payload["dependencyPreflight"]["reasonCode"] == "RELEASE_GATE_DEPENDENCY_MISSING"
    assert "Traceback" not in captured.err


def test_windows_release_worker_status_protocol_is_jsonl_not_literal_tabs(tmp_path):
    gate = _load_release_gate()
    script = gate._windows_worker_script(
        [[r"C:\\Python\\python.exe", "-c", "print('ok')"]],
        tmp_path / "status.jsonl",
    )
    assert "\\tPASS\\t" not in script
    assert '"status":"PASS"' in script
    assert '"exitCode":%code%' in script
    assert gate._parse_worker_status('{"index":1,"status":"PASS","exitCode":0}\n') == {1: ("PASS", 0)}
    assert gate._parse_worker_status('{"index":1,"status":"FAIL","exitCode":7}\n') == {1: ("FAIL", 7)}


def test_windows_normal_cleanup_reports_real_verified_tree_state(monkeypatch):
    gate = _load_release_gate()
    monkeypatch.setattr(gate.os, "name", "nt")
    monkeypatch.setattr(gate, "_windows_process_tree_snapshot", lambda _pid: ({101, 202}, None))
    monkeypatch.setattr(gate, "_windows_pid_state", lambda _pid: False)

    receipt = gate._terminate_process_tree(101)

    assert receipt["observedPids"] == [101, 202]
    assert receipt["survivingObservedPids"] == []
    assert receipt["taskkillExitCode"] is None
    assert receipt["residueFree"] is True
    assert receipt["verificationStatus"] == "PASS"


def test_windows_cleanup_cannot_claim_clean_when_process_inspection_fails(monkeypatch):
    gate = _load_release_gate()
    monkeypatch.setattr(gate.os, "name", "nt")
    monkeypatch.setattr(gate, "_windows_process_tree_snapshot", lambda _pid: (None, "CIM_QUERY_FAILED"))
    monkeypatch.setattr(gate, "_windows_pid_state", lambda _pid: None)

    receipt = gate._terminate_process_tree(303)

    assert receipt["residueFree"] is False
    assert receipt["verificationStatus"] == "NOT_VERIFIED"
    assert receipt["unverifiedObservedPids"] == [303]
    assert receipt["taskkillExitCode"] is None


def test_windows_cleanup_bounds_taskkill_to_observed_worker_tree(monkeypatch):
    gate = _load_release_gate()
    monkeypatch.setattr(gate.os, "name", "nt")
    monkeypatch.setattr(gate, "_windows_process_tree_snapshot", lambda _pid: ({404, 405, 999}, None))
    alive = {404: True, 405: True, 999: True}
    calls = []

    def fake_state(pid):
        return alive.get(pid, False)

    def fake_run(command, **_kwargs):
        calls.append(command)
        target = int(command[command.index("/PID") + 1])
        alive[target] = False
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(gate, "_windows_pid_state", fake_state)
    monkeypatch.setattr(gate.subprocess, "run", fake_run)

    receipt = gate._terminate_process_tree(404)

    assert receipt["observedPids"] == [404, 405, 999]
    assert receipt["survivingObservedPids"] == []
    assert receipt["residueFree"] is True
    assert receipt["taskkillExitCode"] == 0
    assert all(command[:2] == ["taskkill.exe", "/PID"] and command[3:] == ["/T", "/F"] for command in calls)
    assert {int(command[2]) for command in calls} == {404, 405, 999}


def test_release_gate_browser_tail_keeps_pytest_capture_enabled():
    source = (ROOT / "scripts" / "release_gate.py").read_text(encoding="utf-8")
    assert "_BROWSER_SECURITY_TEST" in source
    assert '[sys.executable, "-B", "-m", "pytest", "-q", _BROWSER_SECURITY_TEST]' in source
    assert '[sys.executable, "-B", "-m", "pytest", "-q", "-s", _BROWSER_SECURITY_TEST]' not in source


@pytest.mark.skipif(os.name != "nt", reason="native cmd.exe qualification must run on Windows")
def test_native_cmd_worker_distinguishes_success_and_failure():
    gate = _load_release_gate()
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    passed_rows, passed_worker = gate._run_worker([[sys.executable, "-c", "raise SystemExit(0)"]], env, timeout_s=60)
    assert passed_worker["status"] == "PASS"
    assert passed_rows == [{"command": [sys.executable, "-c", "raise SystemExit(0)"], "status": "PASS", "exitCode": 0}]
    failed_rows, failed_worker = gate._run_worker([[sys.executable, "-c", "raise SystemExit(7)"]], env, timeout_s=60)
    assert failed_worker["status"] == "FAIL"
    assert failed_rows[0]["status"] == "FAIL" and failed_rows[0]["exitCode"] == 7


def test_release_closure_ignores_external_old_package(tmp_path):
    fake_root = tmp_path / "external-old"
    package = fake_root / "web_ui_quality"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("__version__='4.1.1'\nraise RuntimeError('external package loaded')\n", encoding="utf-8")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(fake_root)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    completed = subprocess.run(
        [sys.executable, "-B", str(ROOT / "scripts" / "release_closure_acceptance.py")],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["version"] == "4.3.0"
    assert Path(payload["runtimeFile"]).resolve().is_relative_to((ROOT / "runtime" / "python").resolve())
    assert payload["runtimeIdentityDigest"]


def test_utf8_subprocess_contract_handles_chinese_space_path(tmp_path):
    cwd = tmp_path / "中文 测试目录"
    cwd.mkdir()
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    completed = subprocess.run(
        [sys.executable, "-B", str(ROOT / "scripts" / "run_runtime.py"), "--help"],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    assert completed.returncode == 0
    assert "UnicodeDecodeError" not in completed.stderr
    probe = subprocess.run(
        [sys.executable, "-c", "print('中文输出 ✓')"],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=10,
    )
    assert probe.stdout.strip() == "中文输出 ✓"


def test_bound_browser_policy_is_task_run_session_scoped_and_sealed_into_conditions():
    rules = ({"origin": "https://app.test", "method": "POST", "path": "/api/preview"},)
    bound = bind_approved_requests(
        rules,
        task_id="task-1",
        run_id="run-1",
        session_id="session-1",
        purpose="preview-required-for-verification",
    )
    validated = validate_bound_approved_requests(bound, task_id="task-1", run_id="run-1", session_id="session-1")
    assert validated == bound
    assert request_policy_digest(bound)

    before = RunConditions(url="https://app.test/page", route="/page", source_fingerprint="a", approved_request_policy=bound).to_dict()
    after_same = RunConditions(url="https://app.test/page", route="/page", source_fingerprint="a", approved_request_policy=bound).to_dict()
    assert compare_conditions(before, after_same)["match"] is True

    different = bind_approved_requests(
        ({"origin": "https://app.test", "method": "POST", "path": "/api/other"},),
        task_id="task-1",
        run_id="run-1",
        session_id="session-1",
        purpose="preview-required-for-verification",
    )
    after_different = RunConditions(url="https://app.test/page", route="/page", source_fingerprint="a", approved_request_policy=different).to_dict()
    comparison = compare_conditions(before, after_different)
    assert comparison["match"] is False
    assert "approved_request_policy" in comparison["mismatches"]

    with pytest.raises(ContractViolation, match="BROWSER_REQUEST_APPROVAL_BINDING_MISMATCH"):
        validate_bound_approved_requests(bound, task_id="task-1", run_id="other-run", session_id="session-1")


def test_unbound_browser_exception_is_fail_closed():
    firewall = BrowserMutationFirewall(
        {"https://app.test"},
        approved_requests=({"origin": "https://app.test", "method": "POST", "path": "/api/save"},),
    )
    decision = firewall.evaluate(url="https://app.test/api/save", method="POST", resource_type="fetch")
    assert decision.allow is False
    assert decision.code == "SIDE_EFFECT_BLOCKED"
    assert firewall.rejected_approvals


def test_authenticated_unknown_get_api_requires_exact_machine_authorization():
    blocked = BrowserMutationFirewall({"https://app.test"}, authenticated=True).evaluate(
        url="https://app.test/api/execute",
        method="GET",
        resource_type="fetch",
    )
    assert blocked.allow is False
    assert blocked.code == "AUTHENTICATED_GET_NOT_APPROVED"

    bound = bind_approved_requests(
        ({"origin": "https://app.test", "method": "GET", "path": "/api/execute"},),
        task_id="task-get",
        run_id="run-get",
        session_id="session-get",
        purpose="read-endpoint-required-for-verification",
    )
    allowed = BrowserMutationFirewall(
        {"https://app.test"},
        authenticated=True,
        approved_requests=bound,
    ).evaluate(url="https://app.test/api/execute", method="GET", resource_type="fetch")
    assert allowed.allow is True
    assert allowed.code == "ALLOWED_EXPLICIT_REQUEST"


def test_query_bearing_approval_is_digest_bound_without_persisting_values():
    bound = bind_approved_requests(
        ({"origin": "https://app.test", "method": "GET", "path": "/api/action?mode=preview&item=7"},),
        task_id="task-query",
        run_id="run-query",
        session_id="session-query",
        purpose="query-specific-read-required-for-verification",
    )
    rule = bound[0]
    assert rule["path"] == "/api/action"
    assert len(rule["queryDigest"]) == 64
    assert "preview" not in json.dumps(rule)
    assert "item=7" not in json.dumps(rule)

    firewall = BrowserMutationFirewall(
        {"https://app.test"}, authenticated=True, approved_requests=bound
    )
    same = firewall.evaluate(
        url="https://app.test/api/action?mode=preview&item=7",
        method="GET",
        resource_type="fetch",
    )
    changed = firewall.evaluate(
        url="https://app.test/api/action?mode=delete&item=7",
        method="GET",
        resource_type="fetch",
    )
    assert same.allow is True
    assert changed.allow is False and changed.code == "AUTHENTICATED_GET_NOT_APPROVED"


def test_path_only_approval_does_not_cover_query_bearing_business_get():
    bound = bind_approved_requests(
        ({"origin": "https://app.test", "method": "GET", "path": "/api/submit"},),
        task_id="task-query-2",
        run_id="run-query-2",
        session_id="session-query-2",
        purpose="bounded-read",
    )
    result = BrowserMutationFirewall(
        {"https://app.test"}, authenticated=True, approved_requests=bound
    ).evaluate(
        url="https://app.test/api/submit?confirm=1",
        method="GET",
        resource_type="xhr",
    )
    assert result.allow is False
    assert result.code == "AUTHENTICATED_GET_NOT_APPROVED"


def test_authenticated_document_navigation_is_query_bound():
    firewall = BrowserMutationFirewall(
        {"https://app.test"},
        authenticated=True,
        approved_routes={"/workspace?mode=review"},
    )
    exact = firewall.evaluate(
        url="https://app.test/workspace?mode=review",
        method="GET",
        resource_type="document",
    )
    changed = firewall.evaluate(
        url="https://app.test/workspace?mode=delete",
        method="GET",
        resource_type="document",
    )
    assert exact.allow is True
    assert changed.allow is False and changed.code == "ROUTE_NOT_APPROVED"


def test_authenticated_path_only_navigation_approval_does_not_cover_query():
    result = BrowserMutationFirewall(
        {"https://app.test"}, authenticated=True, approved_routes={"/workspace"}
    ).evaluate(
        url="https://app.test/workspace?action=submit",
        method="GET",
        resource_type="navigation",
    )
    assert result.allow is False
    assert result.code == "ROUTE_NOT_APPROVED"


def test_playwright_adapter_authenticated_query_navigation_is_not_double_canonicalized(monkeypatch, tmp_path):
    """Production adapter must pass raw routes to the single firewall canonicalizer."""
    from web_ui_quality import playwright_adapter as adapter
    from web_ui_quality.secure_browser_context import create_secure_context as real_create_secure_context

    target = "https://app.test/workspace?mode=review"
    changed = "https://app.test/workspace?mode=delete"
    captured: dict[str, object] = {}

    class _StopAfterContext(RuntimeError):
        pass

    class _Context:
        def route(self, *_args, **_kwargs):
            return None

        def route_web_socket(self, *_args, **_kwargs):
            return None

        def new_page(self):
            raise _StopAfterContext

        def close(self):
            return None

    class _Browser:
        def new_context(self, **_kwargs):
            return _Context()

    def _capture_secure_context(*args, **kwargs):
        captured["approved_routes"] = set(kwargs.get("approved_routes") or ())
        audit = real_create_secure_context(*args, **kwargs)
        captured["firewall"] = audit.firewall
        return audit

    monkeypatch.setattr(adapter, "create_secure_context", _capture_secure_context)
    with pytest.raises(_StopAfterContext):
        adapter._capture_one(
            _Browser(),
            url=target,
            label="before",
            viewport=(1280, 720),
            output_dir=tmp_path,
            locale="en-US",
            theme="light",
            allowed_origins={"https://app.test"},
            primary_origins={"https://app.test"},
            timeout_ms=1000,
            credential_headers_by_origin={"https://app.test": {"Authorization": "Bearer qualification-only"}},
        )

    # The adapter hands the raw target to SecureContext. Only the firewall
    # canonicalizes it, so the query digest survives exactly once.
    assert captured["approved_routes"] == {target}
    firewall = captured["firewall"]
    assert firewall.approved_routes == {navigation_route_key(target)}
    exact = firewall.evaluate(url=target, method="GET", resource_type="document")
    altered = firewall.evaluate(url=changed, method="GET", resource_type="document")
    assert exact.allow is True
    assert altered.allow is False and altered.code == "ROUTE_NOT_APPROVED"


def test_navigation_callers_leave_runtime_canonicalization_to_firewall():
    """Prevent recurrence in every production caller that creates Secure Context."""
    adapter = (ROOT / "runtime/python/web_ui_quality/playwright_adapter.py").read_text(encoding="utf-8")
    smart = (ROOT / "runtime/python/web_ui_quality/smart_acceptance.py").read_text(encoding="utf-8")
    inventory = (ROOT / "runtime/python/web_ui_quality/ui_inventory.py").read_text(encoding="utf-8")

    assert "approved_routes={navigation_route_key(" not in adapter
    assert "approved_routes={navigation_route_key(" not in smart
    assert "approved_routes=approved_route_urls" in inventory
    # Inventory may canonicalize only for privacy-preserving reporting, never
    # for the value handed into Secure Context / BrowserMutationFirewall.
    assert "approvedRoutes\":sorted(navigation_route_key(value) for value in approved_route_urls)" in inventory


def test_fault_harness_browser_oracle_uses_secure_context_and_rejects_live_entrypoints():
    source = (ROOT / "scripts" / "fault_injection_harness.py").read_text(encoding="utf-8")
    assert "context = browser.new_context" not in source
    assert "create_secure_context(" in source
    assert 'kwargs["args"].append("--no-sandbox")' not in source
    assert "fault harness Browser oracle accepts local synthetic fixtures only" in source
    # Release preflight and the benchmark Browser oracle must share exactly one
    # browser discovery contract. This is required on Windows where Chrome may
    # be installed under Program Files without being on PATH.
    assert 'resolve_browser_executable("chromium", playwright_browser_type=runtime.chromium)' in source
    assert 'shutil.which("chromium") or shutil.which("chromium-browser") or shutil.which("google-chrome")' not in source
    assert '"executable_path": str(browser_decision["executable"])' in source


def test_default_human_report_hides_protocol_codes_and_has_four_sections():
    from web_ui_quality.__main__ import _emit_human_repair_report

    result = {
        "taskResult": {
            "kind": "REPAIR",
            "outcome": "NOT_VERIFIED",
            "changes": ["src/Button.tsx"],
            "verification": {"browser": "NOT_MEASURED", "hostWrite": "HOST_WRITE_RECEIPT_V3_REQUIRED", "projectTools": "NOT_APPLICABLE", "projectDrift": "PASS"},
            "coverage": {"patchScope": "COMPLETE", "target": "COMPLETE", "criticalContext": "COMPLETE", "globalProject": "PARTIAL"},
            "nextAction": "HOST_WRITE_RECEIPT_V3_REQUIRED",
            "taskState": {"resumable": False},
        }
    }
    stream = io.StringIO()
    _emit_human_repair_report(result, stream=stream)
    text = stream.getvalue()
    assert [heading for heading in ("结果：", "改了什么：", "验证了什么：", "下一步：") if heading in text] == ["结果：", "改了什么：", "验证了什么：", "下一步："]
    assert "HOST_WRITE_RECEIPT_V3_REQUIRED" not in text
    assert "Evidence Graph" not in text
    assert "修改尚未得到当前宿主确认" in text
    assert "编辑器" not in text
    assert "未覆盖整个仓库" in text
    assert "原因：" in text
    assert "需要谁处理：" in text
    assert "是否可以继续：" in text
