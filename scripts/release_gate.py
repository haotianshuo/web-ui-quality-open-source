#!/usr/bin/env python3
"""Single authoritative 4.3.0 package-local release gate over the sealed 4.2.3 Trust Kernel.

Core mode is dependency-aware and may report Browser as NOT_MEASURED when the
optional browser extra is absent. Full mode requires Playwright + a usable
Chromium-family executable before pytest/acceptance execution; missing browser
capability is a deterministic gate failure, never a pytest collection crash.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shlex
import shutil
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime" / "python"
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from web_ui_quality.browser_locator import resolve_browser_executable
from web_ui_quality.release_info import PACKAGE_STAGE, PACKAGE_VERSION, KERNEL_VERSION, RELEASE_STAGE, configure_stdout


def _safe_find_spec(parent: str, child: str | None = None) -> tuple[bool, str | None]:
    """Probe optional modules without letting missing/broken metadata crash preflight."""
    try:
        parent_spec = importlib.util.find_spec(parent)
    except (ModuleNotFoundError, ImportError, AttributeError, ValueError) as error:
        return False, f"{type(error).__name__}: {error}"
    if parent_spec is None:
        return False, f"{parent} package unavailable"
    if child is None:
        return True, None
    try:
        child_spec = importlib.util.find_spec(child)
    except (ModuleNotFoundError, ImportError, AttributeError, ValueError) as error:
        return False, f"{type(error).__name__}: {error}"
    return child_spec is not None, None if child_spec is not None else f"{child} module unavailable"


def _dependency_preflight(mode: str) -> dict[str, object]:
    pytest_ok, pytest_reason = _safe_find_spec("pytest")
    playwright_ok, playwright_reason = _safe_find_spec("playwright", "playwright.sync_api")
    try:
        browser = resolve_browser_executable("chromium") if playwright_ok else {
            "available": False,
            "reason": playwright_reason or "playwright package unavailable",
            "reasonCode": "PYTHON_PLAYWRIGHT_MODULE_MISSING",
            "resolutionTrace": [],
        }
    except (OSError, RuntimeError, ValueError, ImportError, ModuleNotFoundError) as error:
        browser = {"available": False, "reason": f"browser probe failed safely: {type(error).__name__}: {error}"}
    required_browser = mode == "full"
    missing: list[str] = []
    if not pytest_ok:
        missing.append("pytest")
    if required_browser and not playwright_ok:
        missing.append("playwright.sync_api")
    if required_browser and not bool(browser.get("available")):
        missing.append("chromium-family-executable")
    dependency_reason_codes: list[str] = []
    if not pytest_ok:
        dependency_reason_codes.append("PYTEST_MODULE_MISSING")
    if required_browser and not playwright_ok:
        dependency_reason_codes.append("PYTHON_PLAYWRIGHT_MODULE_MISSING")
    if required_browser and not bool(browser.get("available")):
        browser_reason_code = str(browser.get("reasonCode") or "BROWSER_EXECUTABLE_NOT_FOUND")
        if browser_reason_code not in dependency_reason_codes:
            dependency_reason_codes.append(browser_reason_code)
    status = "PASS" if not missing else "FAIL"
    return {
        "status": status,
        "mode": mode,
        "pytest": "PASS" if pytest_ok else "MISSING",
        "playwright": "PASS" if playwright_ok else "NOT_INSTALLED",
        "browserRuntime": "PASS" if browser.get("available") else "NOT_MEASURED" if not required_browser else "MISSING",
        "reasonCode": "RELEASE_GATE_DEPENDENCY_MISSING" if missing else None,
        "dependencyReasonCodes": dependency_reason_codes,
        "missingCapabilities": missing,
        "pytestReason": pytest_reason,
        "playwrightReason": playwright_reason,
        "browserReason": browser.get("reason"),
        "browserReasonCode": browser.get("reasonCode"),
        "browserResolutionTrace": list(browser.get("resolutionTrace") or []),
        "browserExecutable": browser.get("executable"),
        "remediation": ([
            "Install the declared release-full optional dependencies outside the target project and provide a usable Chromium-family executable."
        ] if missing else []),
        "claimBoundary": "Core validation does not require optional Browser capability. Full release qualification requires Playwright and an executable before tests start.",
    }


def _json_digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _windows_pid_state(pid: int) -> bool | None:
    """Return True/False for a PID, or None when Windows could not inspect it."""
    if os.name != "nt":
        return False
    try:
        completed = subprocess.run(
            ["tasklist.exe", "/FI", f"PID eq {int(pid)}", "/FO", "CSV", "/NH"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    output = completed.stdout or ""
    return f'"{int(pid)}"' in output


def _windows_pid_exists(pid: int) -> bool:
    """Compatibility wrapper; inspection failure is never treated as alive/clean."""
    return _windows_pid_state(pid) is True


def _windows_process_tree_snapshot(root_pid: int) -> tuple[set[int] | None, str | None]:
    """Inspect the native worker tree, preserving an unverifiable result."""
    if os.name != "nt":
        return set(), None
    command = [
        "powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command",
        "Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId | ConvertTo-Json -Compress",
    ]
    try:
        completed = subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
        if completed.returncode != 0:
            return None, f"powershell process snapshot failed with exit code {completed.returncode}"
        value = json.loads((completed.stdout or "[]").lstrip("\ufeff"))
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError, TypeError, ValueError) as error:
        return None, f"windows process snapshot unavailable: {type(error).__name__}: {error}"
    rows = value if isinstance(value, list) else [value] if isinstance(value, dict) else []
    parents: dict[int, set[int]] = {}
    root_seen = False
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            pid = int(row.get("ProcessId")); parent = int(row.get("ParentProcessId"))
        except (TypeError, ValueError):
            continue
        if pid == int(root_pid):
            root_seen = True
        parents.setdefault(parent, set()).add(pid)
    found: set[int] = set(); pending = [int(root_pid)]
    if root_seen:
        found.add(int(root_pid))
    while pending:
        parent = pending.pop()
        for child in parents.get(parent, set()):
            if child not in found:
                found.add(child); pending.append(child)
    return found, None


def _windows_process_tree_pids(root_pid: int) -> set[int]:
    """Compatibility wrapper for callers that only need a successful snapshot."""
    pids, _error = _windows_process_tree_snapshot(root_pid)
    return pids if pids is not None else set()


def _terminate_process_tree(
    pid: int,
    *,
    observed_pids: set[int] | None = None,
    observation_error: str | None = None,
) -> dict[str, object]:
    """Terminate a worker and descendants, returning a cleanup receipt."""
    if os.name == "posix":
        try:
            os.killpg(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        return {"attempted": True, "method": "posix-process-group", "residueFree": True}

    root_pid = int(pid)
    snapshot, snapshot_error = _windows_process_tree_snapshot(root_pid)
    known_pids = {int(value) for value in (observed_pids or set())}
    if snapshot is not None:
        known_pids.update(int(value) for value in snapshot)
    known_pids.add(root_pid)
    inspection_errors = [value for value in (observation_error, snapshot_error) if value]
    states: dict[int, bool | None] = {value: _windows_pid_state(value) for value in sorted(known_pids)}
    live_before = {value for value, state in states.items() if state is True}
    unknown_before = {value for value, state in states.items() if state is None}
    taskkill_exit_codes: list[dict[str, int]] = []
    taskkill_errors: list[str] = []

    # Only PIDs observed in the worker's own tree may be passed to taskkill.
    # Prefer the root tree operation; if the root already disappeared, use the
    # still-live observed descendants individually as a bounded fallback.
    targets = [root_pid] if root_pid in live_before else sorted(live_before)
    attempted_targets: list[int] = []

    def taskkill_observed(target_pid: int) -> None:
        attempted_targets.append(target_pid)
        try:
            completed = subprocess.run(
                ["taskkill.exe", "/PID", str(target_pid), "/T", "/F"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=15,
            )
            exit_code = int(completed.returncode)
            taskkill_exit_codes.append({"pid": target_pid, "exitCode": exit_code})
            if exit_code != 0:
                taskkill_errors.append(f"taskkill failed for observed PID {target_pid} with exit code {exit_code}")
        except (OSError, subprocess.SubprocessError) as error:
            taskkill_errors.append(f"taskkill failed for observed PID {target_pid}: {type(error).__name__}: {error}")

    for target_pid in targets:
        taskkill_observed(target_pid)
    if root_pid in targets:
        # /T normally reaches descendants. Re-scan the already observed child
        # set once so a detached launcher cannot leave a known worker behind.
        for child_pid in sorted(known_pids - {root_pid}):
            child_state = _windows_pid_state(child_pid)
            if child_state is True:
                taskkill_observed(child_pid)
            elif child_state is None:
                inspection_errors.append(f"unable to inspect observed child PID {child_pid} after taskkill")

    deadline = time.monotonic() + 5
    survivors: set[int] = set()
    unknown_after: set[int] = set(unknown_before)
    while True:
        survivors = set()
        unknown_after = set()
        for value in sorted(known_pids):
            state = _windows_pid_state(value)
            if state is True:
                survivors.add(value)
            elif state is None:
                unknown_after.add(value)
        if not survivors or time.monotonic() >= deadline:
            break
        time.sleep(0.05)
    verification_failed = bool(inspection_errors or unknown_before or unknown_after)
    residue_free = not survivors and not verification_failed and not taskkill_errors
    receipt: dict[str, object] = {
        "attempted": bool(attempted_targets),
        "method": "taskkill-tree" if attempted_targets else "windows-process-tree-verification",
        "rootPid": root_pid,
        "observedPids": sorted(known_pids),
        "survivingObservedPids": sorted(survivors),
        "unverifiedObservedPids": sorted(unknown_before | unknown_after),
        "taskkillExitCode": taskkill_exit_codes[0]["exitCode"] if taskkill_exit_codes else None,
        "taskkillExitCodes": taskkill_exit_codes,
        "residueFree": residue_free,
        "verificationStatus": "NOT_VERIFIED" if verification_failed else "FAIL" if survivors or taskkill_errors else "PASS",
    }
    errors = inspection_errors + taskkill_errors
    if errors:
        receipt["errors"] = errors
    return receipt


def _run(command: list[str], env: dict[str, str], *, timeout_s: int = 90) -> dict[str, object]:
    # Child browser/process descendants must never inherit a PIPE owned by this
    # orchestrator: a lingering descendant can keep that pipe open after pytest
    # exits and make communicate() appear hung. Route output to regular files;
    # wait only for the direct gate process, then read bounded diagnostics.
    out_file = tempfile.NamedTemporaryFile(prefix="wuq-gate-out-", suffix=".log", delete=False)
    err_file = tempfile.NamedTemporaryFile(prefix="wuq-gate-err-", suffix=".log", delete=False)
    out_path, err_path = Path(out_file.name), Path(err_file.name)
    try:
        proc = subprocess.Popen(
            command,
            cwd=ROOT,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=out_file,
            stderr=err_file,
            start_new_session=True,
        )
        out_file.close(); err_file.close()
        try:
            code = int(proc.wait(timeout=timeout_s))
            timed_out = False
            # A gate process must not leak background Browser/node/project-tool
            # descendants into the next gate. The direct process has already
            # completed, so any survivor in its private process group is stale.
            # Windows still performs a real post-exit tree inspection; normal
            # exit is not evidence that descendants are absent.
            process_cleanup = _terminate_process_tree(proc.pid)
        except subprocess.TimeoutExpired:
            timed_out = True
            process_cleanup = _terminate_process_tree(proc.pid)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
            code = 124
        stdout = out_path.read_text(encoding="utf-8", errors="replace") if out_path.exists() else ""
        stderr = err_path.read_text(encoding="utf-8", errors="replace") if err_path.exists() else ""
        if stdout:
            print(stdout, end="" if stdout.endswith("\n") else "\n", file=sys.stderr, flush=True)
        if stderr:
            print(stderr, end="" if stderr.endswith("\n") else "\n", file=sys.stderr, flush=True)
        return {
            "command": command,
            "status": "PASS" if code == 0 and process_cleanup.get("residueFree") is True else "FAIL",
            "exitCode": code,
            "processTreeCleanup": process_cleanup,
            **({"reason": f"ORCHESTRATOR_TIMEOUT_{timeout_s}s"} if timed_out else {}),
            **({"stdoutTail": stdout[-2000:]} if code != 0 and stdout else {}),
            **({"stderrTail": stderr[-2000:]} if code != 0 and stderr else {}),
        }
    finally:
        try: out_file.close()
        except Exception: pass
        try: err_file.close()
        except Exception: pass
        out_path.unlink(missing_ok=True); err_path.unlink(missing_ok=True)


def _worker_status_row(index: int, status: str, exit_code: int) -> str:
    """Return one JSONL worker status record.

    The worker status protocol must be shell-independent. Windows ``cmd.exe``
    does not translate ``\t`` inside ``echo`` into a real tab, so a tab-delimited
    batch record can make a successful child look like ``WORKER_ABORTED``.
    """
    return json.dumps(
        {"index": index, "status": status, "exitCode": exit_code},
        separators=(",", ":"),
    )


def _parse_worker_status(text: str) -> dict[int, tuple[str, int]]:
    rows: dict[int, tuple[str, int]] = {}
    for raw in text.splitlines():
        if not raw.strip():
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        index = payload.get("index")
        status = payload.get("status")
        exit_code = payload.get("exitCode")
        if not isinstance(index, int) or index <= 0:
            continue
        if status not in {"PASS", "FAIL"} or not isinstance(exit_code, int):
            continue
        rows[index] = (status, exit_code)
    return rows


def _python_browser_qualification(
    preflight: dict[str, object],
    rows: list[dict[str, object]],
    browser_security_test: str,
    worker: dict[str, object] | None = None,
) -> dict[str, object]:
    """Report Python Browser qualification independently from other gates."""
    module_available = preflight.get("playwright") == "PASS"
    executable_available = preflight.get("browserRuntime") == "PASS"
    row = next(
        (
            item
            for item in rows
            if browser_security_test in list(item.get("command") or [])
        ),
        None,
    )
    attempted = bool(row and row.get("reason") not in {"WORKER_ABORTED", "WORKER_TIMEOUT"})
    receipt = worker.get("browserReceipt") if isinstance(worker, dict) else None
    receipt_ok = (
        isinstance(receipt, dict)
        and receipt.get("status") == "PASS"
        and receipt.get("test") == browser_security_test
        and bool(receipt.get("sha256"))
    )
    if not attempted:
        status = "NOT_VERIFIED"
        reason = "Python Browser security suite was not reached by the release worker."
    elif row and row.get("status") == "PASS" and receipt_ok:
        status = "PASS"
        reason = None
    elif row and row.get("status") == "PASS":
        status = "NOT_VERIFIED"
        reason = "Python Browser suite returned PASS without a live execution receipt."
    else:
        status = "FAIL"
        reason = "Python Browser security suite executed but did not pass."
    return {
        "runtime": "python-playwright",
        "moduleAvailable": module_available,
        "browserExecutableAvailable": executable_available,
        "executed": attempted,
        "status": status,
        "reason": reason,
        "command": list(row.get("command") or []) if isinstance(row, dict) else [],
        "browserBacked": bool(receipt_ok),
        "executionBranch": "LIVE_PYTHON_PLAYWRIGHT" if receipt_ok else "NOT_VERIFIED",
        "browserTestSentinel": "PASS" if receipt_ok else "NOT_VERIFIED",
        "receiptSha256": receipt.get("sha256") if isinstance(receipt, dict) else None,
        "workerOutputSha256": worker.get("stdoutSha256") if isinstance(worker, dict) else None,
        "executionRecord": {
            "status": "PASS" if receipt_ok else "NOT_VERIFIED",
            "executed": receipt_ok,
            "commandDigest": worker.get("execution", {}).get("commandDigest") if isinstance(worker, dict) and isinstance(worker.get("execution"), dict) else None,
            "outputSha256": worker.get("stdoutSha256") if isinstance(worker, dict) else None,
            "receiptSha256": receipt.get("sha256") if isinstance(receipt, dict) else None,
            "browserExecutable": preflight.get("browserExecutable"),
            "source": "release_gate_worker",
        },
    }


def _windows_worker_script(commands: list[list[str]], status_path: Path) -> str:
    """Render the native ``cmd.exe`` worker using JSONL status records."""
    lines = ["@echo off", f'type nul > "{status_path}"']
    for index, command in enumerate(commands, start=1):
        # The recovered checkout may live under a non-ASCII path.  Embedding
        # that path directly in a UTF-8 batch file is not reliable when
        # cmd.exe parses it under a different active code page.  Keep the
        # batch source ASCII and expand the Unicode Python path from the
        # environment at execution time instead.
        if command and str(command[0]) == str(sys.executable):
            tail = subprocess.list2cmdline(command[1:])
            rendered = '"%WUQ_GATE_PYTHON%"' + (f" {tail}" if tail else "")
        else:
            rendered = subprocess.list2cmdline(command)
        pass_row = _worker_status_row(index, "PASS", 0)
        fail_prefix = json.dumps({"index": index, "status": "FAIL"}, separators=(",", ":"))[:-1]
        lines.extend([
            f"echo __WUQ_GATE_START__ {index} 1>&2",
            rendered,
            "set code=%errorlevel%",
            f'if "%code%"=="0" (echo {pass_row}>>"{status_path}") else (echo {fail_prefix},"exitCode":%code%}}>>"{status_path}" & exit /b %code%)',
        ])
    lines.append("exit /b 0")
    return "\r\n".join(lines) + "\r\n"


def _run_worker(commands: list[list[str]], env: dict[str, str], *, timeout_s: int = 900) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Execute every release gate under one short-lived platform worker.

    A single worker prevents the Python release orchestrator from accumulating
    browser/project-tool process state between repeated Popen calls. Each child
    command still has an explicit status row, and the worker exits on first
    failure so RELEASE cannot be upgraded by later PASS results.
    """
    tmp_dir = Path(tempfile.mkdtemp(prefix="wuq-release-worker-"))
    status_path = tmp_dir / "status.jsonl"
    out_path = tmp_dir / "stdout.log"
    err_path = tmp_dir / "stderr.log"
    browser_receipt_path = tmp_dir / "browser-receipt.json"
    try:
        worker_env = dict(env)
        worker_env["WUQ_BROWSER_RECEIPT_PATH"] = str(browser_receipt_path)
        if os.name == "nt":
            worker_env["WUQ_GATE_PYTHON"] = sys.executable
        if os.name == "posix":
            script_path = tmp_dir / "worker.sh"
            lines = ["#!/usr/bin/env bash", "set +e", f": > {shlex.quote(str(status_path))}"]
            for index, command in enumerate(commands, start=1):
                rendered = shlex.join(command)
                pass_row = shlex.quote(_worker_status_row(index, "PASS", 0))
                lines.extend([
                    f"printf '%s\\n' {shlex.quote(f'__WUQ_GATE_START__ {index}')} >&2",
                    f"timeout --foreground 120s {rendered}",
                    "code=$?",
                    f"if [ \"$code\" -eq 0 ]; then printf '%s\\n' {pass_row} >> {shlex.quote(str(status_path))}; else printf '{{\"index\":{index},\"status\":\"FAIL\",\"exitCode\":%s}}\\n' \"$code\" >> {shlex.quote(str(status_path))}; exit \"$code\"; fi",
                ])
            lines.append("exit 0")
            script_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            script_path.chmod(0o755)
            worker_command = ["bash", str(script_path)]
        else:
            script_path = tmp_dir / "worker.cmd"
            script_path.write_text(_windows_worker_script(commands, status_path), encoding="utf-8")
            # Pass the batch file as a separate argument to ``call``.  The
            # ``cmd /s /c <path>`` form strips the outer quotes around a path
            # before command parsing; a recovered checkout commonly lives in
            # a path containing spaces, so that form can split the worker
            # script at the first space and report a false WORKER_ABORTED.
            worker_command = ["cmd.exe", "/d", "/c", "call", str(script_path)]

        with out_path.open("wb") as stdout, err_path.open("wb") as stderr:
            proc = subprocess.Popen(worker_command, cwd=ROOT, env=worker_env, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr, start_new_session=True)
            timed_out = False
            try:
                code = int(proc.wait(timeout=timeout_s))
                # Normal completion is checked exactly like timeout cleanup;
                # a Windows worker is not considered clean without inspection.
                process_cleanup = _terminate_process_tree(proc.pid)
            except subprocess.TimeoutExpired:
                timed_out = True
                process_cleanup = _terminate_process_tree(proc.pid)
                try: proc.wait(timeout=5)
                except subprocess.TimeoutExpired: pass
                code = 124

        stdout_bytes = out_path.read_bytes() if out_path.exists() else b""
        stderr_bytes = err_path.read_bytes() if err_path.exists() else b""
        stdout_text = stdout_bytes.decode("utf-8", errors="replace")
        stderr_text = stderr_bytes.decode("utf-8", errors="replace")
        if stdout_text:
            print(stdout_text, end="" if stdout_text.endswith("\n") else "\n", file=sys.stderr, flush=True)
        if stderr_text:
            print(stderr_text, end="" if stderr_text.endswith("\n") else "\n", file=sys.stderr, flush=True)

        status_by_index = _parse_worker_status(
            status_path.read_text(encoding="utf-8", errors="replace")
        ) if status_path.exists() else {}
        rows: list[dict[str, object]] = []
        for index, command in enumerate(commands, start=1):
            if index in status_by_index:
                state, exit_code = status_by_index[index]
                rows.append({"command": command, "status": state, "exitCode": exit_code})
            elif any(i < index and state == "FAIL" for i, (state, _c) in status_by_index.items()):
                break
            else:
                # Worker stopped at this command without writing a normal row.
                rows.append({"command": command, "status": "FAIL", "exitCode": code, "reason": "WORKER_TIMEOUT" if timed_out else "WORKER_ABORTED"})
                break
        receipt: dict[str, object] | None = None
        if browser_receipt_path.is_file():
            try:
                value = json.loads(browser_receipt_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError):
                value = None
            if isinstance(value, dict):
                receipt = {
                    "status": value.get("status"),
                    "test": value.get("test"),
                    "releaseRunId": value.get("releaseRunId"),
                    "sha256": hashlib.sha256(browser_receipt_path.read_bytes()).hexdigest(),
                    "bytes": browser_receipt_path.stat().st_size,
                }
        status_rows = [
            {"index": index, "command": gate_command_identity(row["command"]), "status": row["status"], "exitCode": row["exitCode"]}
            for index, row in enumerate(rows, start=1)
        ]
        execution = {
            "schemaVersion": "1",
            "commandCount": len(commands),
            "commandDigest": _json_digest([gate_command_identity(command) for command in commands]),
            "statusRowsDigest": _json_digest(status_rows),
            "stdoutSha256": hashlib.sha256(stdout_bytes).hexdigest(),
            "stderrSha256": hashlib.sha256(stderr_bytes).hexdigest(),
            "stdoutBytes": len(stdout_bytes),
            "stderrBytes": len(stderr_bytes),
            "timedOut": timed_out,
            "processTreeCleanup": process_cleanup,
        }
        return rows, {
            "status": "PASS" if code == 0 and process_cleanup.get("residueFree") is True and len(rows) == len(commands) and all(row["status"] == "PASS" for row in rows) else "FAIL",
            "exitCode": code,
            "stdoutSha256": execution["stdoutSha256"],
            "stderrSha256": execution["stderrSha256"],
            "execution": execution,
            "browserReceipt": receipt,
            **({"reason": f"WORKER_TIMEOUT_{timeout_s}s"} if timed_out else {}),
        }
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


_BROWSER_SECURITY_TEST = "tests/test_420_browser_security.py"
_FULL_ACCEPTANCE_SCRIPTS: tuple[tuple[str, ...], ...] = (
    ("scripts/sync_schema_bundle.py", "--check"),
    ("scripts/package_public_acceptance.py",),
    ("scripts/kernel_public_acceptance.py",),
    ("scripts/mainline_v3_acceptance.py",),
    ("scripts/phase1_acceptance.py",),
    ("scripts/product_experience_acceptance.py",),
    ("scripts/convergence_acceptance.py",),
    ("scripts/security_and_evidence_regression.py",),
    ("scripts/browser_safety_regression.py",),
    ("scripts/trust_integrity_attack_regression.py",),
    ("scripts/real_project_integration.py",),
    ("scripts/public_acceptance.py",),
    ("scripts/ga_readiness_acceptance.py",),
    ("scripts/agent_workflow_governance_acceptance.py",),
    ("scripts/repair_modernization_acceptance.py",),
    ("scripts/release_closure_acceptance.py",),
    ("scripts/guided_repair_hardening_acceptance.py",),
    ("scripts/product_evidence_foundation_acceptance.py",),
    ("scripts/privacy_egress_acceptance.py",),
    ("scripts/fault_injection_harness.py", "--self-test"),
    ("scripts/agent_benchmark_qualification.py", "self-test"),
    ("scripts/benchmark_attack_suite.py",),
    ("scripts/benchmark_validity_acceptance.py",),
    ("scripts/benchmark_holdout_acceptance.py",),
    ("scripts/performance_acceptance.py",),
    ("scripts/v23_acceptance.py",),
    ("scripts/verify_distribution.py", "--compact"),
)


def gate_command_identity(command: list[str] | tuple[str, ...]) -> str:
    """Return a stable command identity independent of the active Python path."""
    rendered: list[str] = []
    python_names = {"python", "python.exe", "python3", "python3.exe"}
    for raw in command:
        value = str(raw).replace("\\", "/")
        basename = Path(value).name.casefold()
        if basename in python_names or basename.startswith("python3."):
            value = "<python>"
        else:
            try:
                candidate = Path(raw).expanduser().resolve()
                value = candidate.relative_to(ROOT.resolve()).as_posix() if candidate.is_absolute() else value
            except (OSError, ValueError, RuntimeError):
                pass
        rendered.append(value)
    return json.dumps(rendered, ensure_ascii=False, separators=(",", ":"))


def build_gate_commands(mode: str) -> list[list[str]]:
    """Build the authoritative command list for core or exact Full Gate mode."""
    if mode == "core":
        core_tests = (
            "tests/test_411_ga_identity_closure.py",
            "tests/test_430_plain_user_flow.py",
            "tests/test_schema_bundle_parity.py",
            "tests/test_write_boundary_guard.py",
        )
        return [
            [sys.executable, "-B", "-m", "pytest", "-q", "-s", *core_tests],
            [sys.executable, "-B", "scripts/sync_schema_bundle.py", "--check"],
            [sys.executable, "-B", "scripts/package_public_acceptance.py"],
            [sys.executable, "-B", "scripts/kernel_public_acceptance.py"],
        ]
    if mode != "full":
        raise ValueError(f"unsupported release gate mode: {mode}")

    test_files = [
        path.relative_to(ROOT).as_posix()
        for path in sorted((ROOT / "tests").glob("test_*.py"))
        if path.relative_to(ROOT).as_posix() != _BROWSER_SECURITY_TEST
    ]
    commands: list[list[str]] = []
    batch_sizes = (10, 8, 8, 7)
    offset = 0
    for size in batch_sizes:
        batch = test_files[offset:offset + size]
        offset += size
        if batch:
            commands.append([sys.executable, "-B", "-m", "pytest", "-q", "-s", *batch])
    if offset < len(test_files):
        commands.append([sys.executable, "-B", "-m", "pytest", "-q", "-s", *test_files[offset:]])
    commands.extend([[sys.executable, "-B", *script] for script in _FULL_ACCEPTANCE_SCRIPTS])
    # The final command is deliberately separate so Python Browser evidence is
    # independently identifiable and cannot be inferred from other tests.
    commands.append([sys.executable, "-B", "-m", "pytest", "-q", _BROWSER_SECURITY_TEST])
    return commands


def main() -> int:
    configure_stdout()
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("core", "full"), default="full")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--release-run-id")
    args = parser.parse_args()
    release_run_id = str(args.release_run_id or os.environ.get("WUQ_RELEASE_RUN_ID") or f"wuq-4.3.0-release-{uuid.uuid4().hex[:16]}").strip()
    preflight = _dependency_preflight(args.mode)
    rows: list[dict[str, object]] = []
    if preflight["status"] != "PASS":
        payload = {
            "status": "FAIL",
            "packageVersion": PACKAGE_VERSION,
            "packageStage": PACKAGE_STAGE,
            "kernelVersion": KERNEL_VERSION,
            "stage": RELEASE_STAGE,
            "releaseRunId": release_run_id,
            "dependencyPreflight": preflight,
            "browserQualification": {
                "pythonPlaywright": {
                    "runtime": "python-playwright",
                    "moduleAvailable": preflight.get("playwright") == "PASS",
                    "browserExecutableAvailable": preflight.get("browserRuntime") == "PASS",
                    "executed": False,
                    "status": "NOT_VERIFIED",
                    "reason": "Dependency preflight failed before the Browser suite could execute.",
                }
            },
            "gates": rows,
        }
        print(json.dumps(payload, ensure_ascii=False, separators=(",", ":") if args.compact else None, indent=None if args.compact else 2))
        return 1

    env = dict(os.environ)
    env["PYTHONPATH"] = str(RUNTIME) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env["WUQ_RELEASE_RUN_ID"] = release_run_id
    commands = build_gate_commands(args.mode)
    rows, worker = _run_worker(commands, env)
    status = "PASS" if worker["status"] == "PASS" and len(rows) == len(commands) and all(row["status"] == "PASS" for row in rows) else "FAIL"
    python_browser = _python_browser_qualification(preflight, rows, _BROWSER_SECURITY_TEST, worker)
    payload = {
        "status": status,
        "packageVersion": PACKAGE_VERSION,
        "packageStage": PACKAGE_STAGE,
        "kernelVersion": KERNEL_VERSION,
        "stage": RELEASE_STAGE,
        "releaseRunId": release_run_id,
        "mode": args.mode,
        "dependencyPreflight": preflight,
        "browserQualification": {"pythonPlaywright": python_browser},
        "gates": rows,
        "requiredGateCount": len(commands),
        "passedGateCount": sum(1 for row in rows if row["status"] == "PASS"),
        "worker": worker,
        "realCodexHostQualification": "NOT_MEASURED",
        "nativeWindowsQualification": "NOT_MEASURED",
        "claimBoundary": "RELEASE=PASS only when every required package-local gate passes. Real Host/Native Windows qualification remains independent external evidence.",
    }
    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":") if args.compact else None, indent=None if args.compact else 2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
