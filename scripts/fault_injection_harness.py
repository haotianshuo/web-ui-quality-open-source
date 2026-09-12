#!/usr/bin/env python3
"""Path-isolated fault-injection harness for Agent benchmark qualification.

Beta.5 separates Host workspaces, controller state and evaluator-private ground
truth into independent filesystem roots. The Host-visible task never contains
evaluator paths or answer fields. This is workspace/path isolation; hostile
same-user agents with unrestricted OS-wide filesystem access still require an
external sandbox/ACL boundary and are never claimed as remotely attested.
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import uuid
import os
import re
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime" / "python"
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from web_ui_quality.benchmark_protocol import condition_fingerprint, create_integrity_key, integrity_mac, mac_seal_object, merkleish_root, seal_object, verify_sealed  # noqa: E402
from web_ui_quality.context_packet import build_relevant_context_packet, context_recall, context_retrieval_metrics  # noqa: E402
from web_ui_quality.project_baseline import build_project_baseline  # noqa: E402
from web_ui_quality.browser_locator import resolve_browser_executable  # noqa: E402
from web_ui_quality.benchmark_evaluation import evaluate_problem_solved, normalize_execution_status, normalize_run_validity  # noqa: E402

V1_CASES_PATH = ROOT / "tests" / "fixtures" / "fault-injection-v1" / "cases.json"
V2_CASES_PATH = ROOT / "tests" / "fixtures" / "fault-injection-v2" / "cases.json"
HOLDOUT_V1_CASES_PATH = ROOT / "tests" / "fixtures" / "fault-injection-holdout-v1" / "cases.json"
TASK_FILE = ".wuq-benchmark-task.json"
IGNORED_MUTATION_PATTERNS = [".wuq/**", "TASK.md", "host-result.json", "HOST_RESULT_TEMPLATE.json"]
EXCLUDED_SOURCE_DIR_NAMES = {
    ".git", ".venv", "venv", "env", "node_modules", "__pycache__", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", ".tox", "coverage", "dist", "build", "out", "_site", ".next",
    ".wuq-oracle-home",
}
DEFAULT_RESPONSIVE_VIEWPORTS = (
    {"width": 390, "height": 844},
    {"width": 768, "height": 1024},
    {"width": 1440, "height": 900},
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _matches(path: str, patterns: list[str]) -> bool:
    posix = PurePosixPath(path)
    return any(fnmatch.fnmatch(path, pattern) or posix.match(pattern) for pattern in patterns)


def _snapshot(root: Path, *, include_patterns: list[str] | None = None) -> dict[str, str]:
    """Snapshot source-relevant files plus explicitly declared generated paths."""
    include_patterns = [str(item) for item in (include_patterns or [])]
    rows: dict[str, str] = {}
    for path in sorted(p for p in root.rglob("*") if p.is_file() and not p.is_symlink()):
        rel = path.relative_to(root).as_posix()
        if _matches(rel, IGNORED_MUTATION_PATTERNS):
            continue
        parts = PurePosixPath(rel).parts
        if any(part in EXCLUDED_SOURCE_DIR_NAMES for part in parts) and not _matches(rel, include_patterns):
            continue
        rows[rel] = _sha256(path)
    return rows


def _normalize_case(case: Mapping[str, Any]) -> dict[str, Any]:
    row = dict(case)
    if "expectedRootSources" not in row:
        row["expectedRootSources"] = [str(row["rootSource"])] if row.get("rootSource") else []
    if "allowedScope" not in row:
        row["allowedScope"] = list(row["expectedRootSources"])
    if "cleanFiles" not in row:
        row["cleanFiles"] = {str(row["rootSource"]): str(row["cleanContent"])} if row.get("rootSource") else {}
    if "injectedFiles" not in row:
        row["injectedFiles"] = {str(row["rootSource"]): str(row["injectedContent"])} if row.get("rootSource") else {}
    if "initialFiles" not in row:
        row["initialFiles"] = {}
    if "oracle" not in row:
        row["oracle"] = [
            {"type": "FILE_EQUALS", "path": path, "content": content}
            for path, content in dict(row["cleanFiles"]).items()
        ]
    row.setdefault("expectation", "REPAIR")
    row.setdefault("protectedScope", [])
    row.setdefault("generatedTargets", [])
    row.setdefault("taskRelevantScope", [])
    row.setdefault("difficulty", "D2")
    row.setdefault("family", "legacy-v1")
    row.setdefault("archetype", str(row.get("id") or row.get("family") or "unknown"))
    return row


def _scope_measurement_patterns(case: Mapping[str, Any]) -> list[str]:
    values: list[str] = []
    for key in ("allowedScope", "protectedScope", "generatedTargets", "taskRelevantScope"):
        for item in list(case.get(key) or []):
            value = str(item)
            if value and value not in values:
                values.append(value)
    return values


def load_cases(*, corpus: str = "v2") -> list[dict[str, Any]]:
    paths = {"v1": V1_CASES_PATH, "v2": V2_CASES_PATH, "holdout-v1": HOLDOUT_V1_CASES_PATH}
    path = paths.get(corpus, V2_CASES_PATH)
    if not path.is_file():
        raise RuntimeError(f"benchmark corpus not found: {path}")
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list) or not rows:
        raise RuntimeError(f"benchmark corpus is empty: {path}")
    return [_normalize_case(row) for row in rows]


def _write_project_files(root: Path, case: Mapping[str, Any]) -> None:
    decoys = {
        "src/App.tsx": "export const App = () => 'generic application shell';\n",
        "src/shared/helpers.ts": "export const helper = 'generic helper utilities';\n",
        "src/styles/base.css": "body { margin: 0; } /* generic base style */\n",
        "package.json": '{"scripts":{"test":"echo test"},"dependencies":{"react":"18"}}\n',
    }
    for rel, content in {**decoys, **dict(case.get("initialFiles") or {}), **dict(case.get("cleanFiles") or {})}.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(str(content), encoding="utf-8")
    for rel, content in dict(case.get("injectedFiles") or {}).items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(str(content), encoding="utf-8")


def _safe_project_file(project: Path, relative: str) -> Path | None:
    candidate = (project / str(relative)).resolve(strict=False)
    try:
        candidate.relative_to(project.resolve())
    except ValueError:
        return None
    return candidate


def validate_defect_injection(case: Mapping[str, Any], project: Path) -> dict[str, Any]:
    """Validate that evaluator setup actually installed the declared defect."""
    expectation = str(case.get("expectation") or "REPAIR").upper()
    injected = {str(path): str(content) for path, content in dict(case.get("injectedFiles") or {}).items()}
    if not injected:
        if expectation == "NO_MUTATION":
            return {"status": "NOT_APPLICABLE", "defectPresent": False, "checks": [], "reasonCodes": []}
        return {"status": "INVALID_SETUP", "defectPresent": False, "checks": [], "reasonCodes": ["INJECTED_DEFECT_MISSING"]}
    checks: list[dict[str, Any]] = []
    reasons: list[str] = []
    differing_defects = 0
    clean = {str(path): str(content) for path, content in dict(case.get("cleanFiles") or {}).items()}
    for relative, expected in sorted(injected.items()):
        path = _safe_project_file(project, relative)
        if path is None:
            checks.append({"path": relative, "check": "path-contained", "pass": False})
            reasons.append("INJECTED_PATH_ESCAPE")
            continue
        exists = path.is_file() and not path.is_symlink()
        checks.append({"path": relative, "check": "file-exists", "pass": exists})
        if not exists:
            reasons.append("INJECTED_FILE_MISSING")
            continue
        actual = path.read_text(encoding="utf-8", errors="ignore")
        matches = actual == expected
        checks.append({"path": relative, "check": "content-matches-injected", "pass": matches})
        if not matches:
            reasons.append("INJECTED_CONTENT_MISMATCH")
        if relative in clean:
            differs_from_clean = expected != clean[relative]
            if differs_from_clean:
                checks.append({"path": relative, "check": "differs-from-clean", "pass": True})
                differing_defects += 1
            else:
                checks.append({"path": relative, "check": "support-file-equals-clean", "pass": True})
        else:
            differing_defects += 1
    if not reasons and differing_defects == 0:
        reasons.append("INJECTED_CONTENT_EQUALS_CLEAN")
    status = "VALIDATED" if not reasons else "INVALID_SETUP"
    return {
        "status": status,
        "defectPresent": status == "VALIDATED",
        "checks": checks,
        "reasonCodes": list(dict.fromkeys(reasons)),
    }


def prepare_case(
    case: Mapping[str, Any], destination: Path, *, run_id: str | None = None, repetition: int = 1,
    planned_host: Mapping[str, Any] | None = None, planned_conditions: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Prepare one Host workspace and return evaluator-only truth in memory."""
    case = _normalize_case(case)
    root = destination.resolve()
    root.mkdir(parents=True, exist_ok=True)
    _write_project_files(root, case)
    measurement_patterns = _scope_measurement_patterns(case)
    defect_injection = validate_defect_injection(case, root)
    run_id = run_id or f"{case['id']}-r{int(repetition):02d}"
    planned_host = dict(planned_host or {"name": "external-host", "version": "UNSPECIFIED", "model": "UNSPECIFIED"})
    planned_conditions = dict(planned_conditions or {
        "reasoningMode": "UNSPECIFIED", "permissionProfile": "UNSPECIFIED", "toolPolicy": "UNSPECIFIED",
        "browserCondition": "UNSPECIFIED", "authCondition": "UNSPECIFIED", "os": "UNSPECIFIED",
        "runtime": "UNSPECIFIED", "contextPolicy": "wuq-relevant-context-v1", "wuqVersion": "4.0.0-rc.1",
        "fixtureVersion": "fault-injection-v2",
    })
    condition = condition_fingerprint(planned_host, planned_conditions)
    host_task = {
        "schemaVersion": "4", "runId": run_id, "caseId": case["id"], "repetition": int(repetition),
        "difficulty": case["difficulty"], "family": case.get("family"), "archetype": case.get("archetype"), "request": case["request"],
        "protectedScope": list(case.get("protectedScope") or []),
        "plannedHost": planned_host, "plannedConditions": planned_conditions, "conditionDigest": condition["digest"],
        "resultContract": "agent-benchmark-result.schema.json",
        "claimBoundary": "Host-visible task excludes evaluator path, expected root sources, allowed repair scope, clean content and oracle definitions.",
    }
    (root / TASK_FILE).write_text(json.dumps(host_task, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    evaluator_body = {
        "schemaVersion": "4", "runId": run_id, "caseId": case["id"], "repetition": int(repetition),
        "difficulty": case["difficulty"], "family": case.get("family"), "archetype": case.get("archetype"), "request": case["request"],
        "expectation": case.get("expectation", "REPAIR"),
        "expectedRootSources": list(case.get("expectedRootSources") or []),
        "allowedScope": list(case.get("allowedScope") or []),
        "protectedScope": list(case.get("protectedScope") or []),
        "oracle": list(case.get("oracle") or []), "initialFiles": _snapshot(root, include_patterns=measurement_patterns),
        "scopeMeasurement": {
            "version": "task-relevant-v1",
            "includePatterns": measurement_patterns,
            "excludedDirectoryNames": sorted(EXCLUDED_SOURCE_DIR_NAMES),
        },
        "defectInjection": defect_injection,
        "defectOracle": case.get("defectOracle") or case.get("diagnosisOracle") or [],
        "oracleMode": str(case.get("expectation") or "REPAIR").upper(),
        "ignoredMutationPatterns": list(IGNORED_MUTATION_PATTERNS),
        "claimBoundary": "Evaluator-only sealed ground truth. Never provide this manifest or its filesystem path to the Host Agent.",
    }
    evaluator = seal_object(evaluator_body, field="manifestDigest")
    return {"hostTask": host_task, "evaluatorManifest": evaluator}


def _project_changes(project: Path, evaluator: Mapping[str, Any]) -> dict[str, list[str]]:
    before = {str(k): str(v) for k, v in dict(evaluator.get("initialFiles") or {}).items()}
    measurement = dict(evaluator.get("scopeMeasurement") or {})
    include_patterns = [str(item) for item in list(measurement.get("includePatterns") or [])]
    after = _snapshot(project, include_patterns=include_patterns)
    before_keys, after_keys = set(before), set(after)
    added = sorted(after_keys - before_keys)
    removed = sorted(before_keys - after_keys)
    modified = sorted(key for key in before_keys & after_keys if before[key] != after[key])
    return {"added": added, "removed": removed, "modified": modified, "all": sorted(set(added + removed + modified))}


def _process_limits(timeout: int):
    """Best-effort process limits; deliberately not claimed as an OS sandbox."""
    if os.name != "posix":
        return None
    def apply() -> None:
        try:
            import resource
            resource.setrlimit(resource.RLIMIT_CPU, (timeout + 1, timeout + 1))
            resource.setrlimit(resource.RLIMIT_FSIZE, (10 * 1024 * 1024, 10 * 1024 * 1024))
            resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
            if hasattr(resource, "RLIMIT_NPROC"):
                resource.setrlimit(resource.RLIMIT_NPROC, (32, 32))
            if hasattr(resource, "RLIMIT_AS"):
                resource.setrlimit(resource.RLIMIT_AS, (2 * 1024 * 1024 * 1024, 2 * 1024 * 1024 * 1024))
        except Exception:
            pass
    return apply


def _oracle_process_env(home: Path) -> dict[str, str]:
    """Keep the oracle process isolated without breaking Windows executables.

    Windows Node needs the OS loader variables, especially ``SystemRoot``.
    The previous allow-list removed them, which made even dependency-free
    ``.mjs`` fixtures abort inside Node before their assertions ran.
    ``HOME`` and the temporary-directory variables remain redirected to the
    oracle-owned directory.
    """
    env = {
        "PATH": os.environ.get("PATH", ""),
        "NODE_NO_WARNINGS": "1",
        "HOME": str(home),
        "TMPDIR": str(home),
        "TEMP": str(home),
        "TMP": str(home),
    }
    for name in ("SYSTEMROOT", "SystemRoot", "WINDIR", "COMSPEC", "PATHEXT", "LOCALAPPDATA", "PROGRAMDATA"):
        value = os.environ.get(name)
        if value:
            env[name] = value
    return env


def _browser_assertions(project: Path, path: Path, oracle: Mapping[str, Any]) -> dict[str, Any]:
    project = project.resolve()
    # This harness is intentionally limited to evaluator-controlled local HTML
    # fixtures. It must never become a second Browser entry point for real URLs,
    # credentials, storage state or arbitrary authenticated sessions.
    forbidden_live_keys = {
        "url", "targetUrl", "storageState", "storage_state", "headers",
        "extraHttpHeaders", "extra_http_headers", "credentialHeadersByOrigin",
    }
    supplied_live = sorted(key for key in forbidden_live_keys if oracle.get(key) not in (None, "", [], {}))
    if supplied_live:
        return {
            "type": "BROWSER_ASSERT", "status": "INVALID_ORACLE_POLICY", "pass": False,
            "path": str(path.relative_to(project)),
            "reason": "fault harness Browser oracle accepts local synthetic fixtures only; live URL/auth state is forbidden",
            "forbiddenFields": supplied_live,
        }
    try:
        from playwright.sync_api import sync_playwright
        from web_ui_quality.secure_browser_context import create_secure_context
    except Exception as error:
        return {"type": "BROWSER_ASSERT", "status": "NOT_MEASURED_ENVIRONMENT", "pass": False, "path": str(path.relative_to(project)), "reason": f"playwright unavailable: {type(error).__name__}"}
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        return {
            "type": "BROWSER_ASSERT", "status": "NOT_MEASURED_ENVIRONMENT", "pass": False,
            "path": str(path.relative_to(project)),
            "reason": "synthetic Browser oracle refuses --no-sandbox; run under a sandbox-capable non-root Browser host",
        }
    requested_viewports = oracle.get("viewports") or oracle.get("viewportMatrix")
    if isinstance(requested_viewports, Mapping):
        requested_viewports = [requested_viewports]
    if isinstance(requested_viewports, list) and requested_viewports:
        viewport_specs = [dict(item) for item in requested_viewports if isinstance(item, Mapping)]
    elif oracle.get("responsive"):
        viewport_specs = [dict(item) for item in DEFAULT_RESPONSIVE_VIEWPORTS]
    else:
        viewport_specs = [dict(oracle.get("viewport") or {"width": 390, "height": 844})]
    if not viewport_specs:
        viewport_specs = [dict(oracle.get("viewport") or {"width": 390, "height": 844})]
    viewport_specs = [
        {"width": max(240, min(int(item.get("width") or 390), 2560)), "height": max(240, min(int(item.get("height") or 844), 2560))}
        for item in viewport_specs
    ]
    viewport_results: list[dict[str, Any]] = []
    browser = None
    try:
        with sync_playwright() as runtime:
            # Prefer a desktop/PATH executable before consulting the live sync
            # Playwright browser type. The latter can leave pending driver
            # tasks on stderr when the sync context exits on Windows.
            browser_decision = resolve_browser_executable("chromium")
            if not browser_decision.get("available"):
                browser_decision = resolve_browser_executable("chromium", playwright_browser_type=runtime.chromium)
            if not browser_decision.get("available"):
                return {
                    "type": "BROWSER_ASSERT", "status": "NOT_MEASURED_ENVIRONMENT", "pass": False,
                    "path": str(path.relative_to(project)),
                    "reason": str(browser_decision.get("reason") or "usable Chromium-family executable unavailable"),
                }
            kwargs: dict[str, Any] = {
                "headless": True,
                "args": ["--disable-background-networking", "--disable-default-apps", "--disable-sync", "--no-first-run"],
                "executable_path": str(browser_decision["executable"]),
            }
            try:
                browser = runtime.chromium.launch(**kwargs)
            except Exception:
                # A Playwright-managed browser may be present but unusable on a
                # host (for example, a Windows binary blocked by local policy).
                # Keep the shared discovery contract, then fall back to a
                # detected desktop Chromium-family executable before declaring
                # the Browser oracle unmeasured.
                fallback = resolve_browser_executable("chromium")
                selected = str(browser_decision.get("executable") or "")
                alternate = str(fallback.get("executable") or "")
                if not fallback.get("available") or not alternate or alternate == selected:
                    raise
                browser_decision = fallback
                kwargs["executable_path"] = alternate
                browser = runtime.chromium.launch(**kwargs)
            html = path.read_text(encoding="utf-8", errors="ignore")
            # Avoid environment-specific file:// navigation policies. The fixture HTML is
            # evaluator-controlled; linked stylesheet sources under test are injected
            # explicitly from the Host workspace. Network requests remain blocked.
            html = re.sub(r"<link\b[^>]*rel=[\"']?stylesheet[\"']?[^>]*>", "", html, flags=re.I)
            for viewport in viewport_specs:
                secure = create_secure_context(
                    browser,
                    context_options={"viewport": viewport},
                    allowed_origins=(),
                    authenticated=False,
                )
                context = secure.context
                try:
                    page = context.new_page()
                    page.set_content(html, wait_until="load", timeout=max(1000, min(int(oracle.get("timeoutMs") or 5000), 15000)))
                    for style_rel in list(oracle.get("stylePaths") or []):
                        style_path = (project / str(style_rel)).resolve(strict=False)
                        try:
                            style_path.relative_to(project.resolve())
                        except ValueError:
                            raise RuntimeError("browser oracle stylesheet escapes project")
                        if not style_path.is_file() or style_path.is_symlink():
                            raise RuntimeError("browser oracle stylesheet missing")
                        page.add_style_tag(path=str(style_path))
                    rows: list[dict[str, Any]] = []
                    for assertion in list(oracle.get("assertions") or []):
                        kind = str(assertion.get("kind") or "").strip()
                        selector = str(assertion.get("selector") or "")
                        passed = False
                        detail: Any = None
                        if kind == "noPageHorizontalOverflow":
                            detail = page.evaluate("() => ({scrollWidth: document.documentElement.scrollWidth, width: window.innerWidth})")
                            passed = int(detail["scrollWidth"]) <= int(detail["width"]) + int(assertion.get("tolerance") or 1)
                        elif selector:
                            locator = page.locator(selector).first
                            if kind == "visible":
                                detail = locator.is_visible(); passed = bool(detail) is bool(assertion.get("expected", True))
                            elif kind == "withinViewport":
                                detail = locator.evaluate("el => { const r=el.getBoundingClientRect(); return {left:r.left,top:r.top,right:r.right,bottom:r.bottom,width:r.width,height:r.height,vw:innerWidth,vh:innerHeight}; }")
                                passed = detail["left"] >= 0 and detail["top"] >= 0 and detail["right"] <= detail["vw"] + 1 and detail["bottom"] <= detail["vh"] + 1
                            elif kind == "minSize":
                                detail = locator.evaluate("el => { const r=el.getBoundingClientRect(); return {width:r.width,height:r.height}; }")
                                passed = detail["width"] >= float(assertion.get("minWidth") or 0) and detail["height"] >= float(assertion.get("minHeight") or 0)
                            elif kind == "topMost":
                                detail = locator.evaluate("el => { const r=el.getBoundingClientRect(); const x=r.left+r.width/2, y=r.top+r.height/2; const top=document.elementFromPoint(x,y); return {ok: !!top && (top===el || el.contains(top)), tag: top && top.tagName}; }")
                                passed = bool(detail.get("ok"))
                            elif kind == "textContains":
                                detail = locator.inner_text(); passed = str(assertion.get("expected") or "") in detail
                            elif kind == "cssContains":
                                prop = str(assertion.get("property") or "")
                                detail = locator.evaluate("(el, prop) => getComputedStyle(el).getPropertyValue(prop)", prop)
                                passed = str(assertion.get("expected") or "") in str(detail)
                        rows.append({"kind": kind, "selector": selector or None, "pass": passed, "detail": detail})
                    viewport_results.append({"viewport": viewport, "pass": bool(rows) and all(row["pass"] for row in rows), "assertions": rows})
                finally:
                    context.close()
            browser.close()
            browser = None
    except Exception as error:
        if browser is not None:
            try:
                browser.close()
            except Exception:
                pass
        return {"type": "BROWSER_ASSERT", "status": "EXECUTION_FAILED", "pass": False, "path": str(path.relative_to(project)), "reason": f"{type(error).__name__}: {str(error)[:180]}"}
    result: dict[str, Any] = {
        "type": "BROWSER_ASSERT", "status": "MEASURED", "pass": bool(viewport_results) and all(row["pass"] for row in viewport_results),
        "path": str(path.relative_to(project)), "viewport": viewport_results[0]["viewport"],
        "assertions": viewport_results[0]["assertions"], "networkPolicy": "HTTP_HTTPS_ABORTED",
        "fixtureMode": "SECURE_CONTEXT_LOCAL_SYNTHETIC_ONLY",
    }
    if len(viewport_results) > 1:
        result["viewports"] = [row["viewport"] for row in viewport_results]
        result["viewportResults"] = viewport_results
        result["viewportMatrix"] = "EXPLICIT_OR_RESPONSIVE"
    return result


def _oracle_result(project: Path, oracle: Mapping[str, Any]) -> dict[str, Any]:
    kind = str(oracle.get("type") or "").upper()
    if kind == "NO_MUTATION":
        return {"type": kind, "status": "APPLICABLE", "pass": True}
    rel = str(oracle.get("path") or "")
    path = (project / rel).resolve(strict=False)
    try:
        path.relative_to(project.resolve())
    except ValueError:
        return {"type": kind, "status": "INVALID_ORACLE_PATH", "pass": False}
    if not path.is_file() or path.is_symlink():
        return {"type": kind, "status": "MISSING_TARGET", "pass": False, "path": rel}
    if kind in {"FILE_EQUALS", "FILE_CONTAINS"}:
        text = path.read_text(encoding="utf-8", errors="ignore")
        if kind == "FILE_EQUALS":
            passed = text == str(oracle.get("content") or "")
        else:
            required = [str(x) for x in oracle.get("required", [])]
            forbidden = [str(x) for x in oracle.get("forbidden", [])]
            passed = all(token in text for token in required) and all(token not in text for token in forbidden)
        return {"type": kind, "status": "MEASURED", "pass": passed, "path": rel, "oracleLevel": "SOURCE_CONTRACT"}
    if kind == "BROWSER_ASSERT":
        row = _browser_assertions(project, path, oracle)
        row["oracleLevel"] = "BROWSER_BEHAVIOR"
        return row
    if kind == "NODE_SCRIPT":
        node = shutil.which("node")
        if not node:
            return {"type": kind, "status": "NOT_MEASURED_ENVIRONMENT", "pass": False, "path": rel, "reason": "node executable unavailable", "oracleLevel": "EXECUTABLE_BEHAVIOR"}
        timeout = max(1, min(int(oracle.get("timeoutSeconds") or 3), 10))
        oracle_home = project / ".wuq-oracle-home"
        oracle_home.mkdir(exist_ok=True)
        try:
            completed = subprocess.run(
                [node, str(path)], cwd=project, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding="utf-8", errors="replace", timeout=timeout,
                env=_oracle_process_env(oracle_home),
                preexec_fn=_process_limits(timeout),
            )
        except (subprocess.TimeoutExpired, OSError) as error:
            return {"type": kind, "status": "EXECUTION_FAILED", "pass": False, "path": rel, "reason": type(error).__name__, "oracleLevel": "EXECUTABLE_BEHAVIOR", "sandboxMode": "PROCESS_LIMITED_NOT_OS_ISOLATED"}
        expected_exit = int(oracle.get("expectedExitCode", 0))
        required_stdout = [str(x) for x in oracle.get("stdoutContains", [])]
        passed = completed.returncode == expected_exit and all(token in completed.stdout for token in required_stdout)
        return {
            "type": kind, "status": "MEASURED", "pass": passed, "path": rel, "exitCode": completed.returncode,
            "stdoutDigest": hashlib.sha256(completed.stdout.encode("utf-8")).hexdigest(),
            "stderrDigest": hashlib.sha256(completed.stderr.encode("utf-8")).hexdigest(),
            "oracleLevel": "EXECUTABLE_BEHAVIOR", "sandboxMode": "PROCESS_LIMITED_NOT_OS_ISOLATED",
            "securityBoundary": "CPU/file/process limits and isolated HOME/TMP only; no network/filesystem namespace isolation is claimed.",
        }
    return {"type": kind or "UNKNOWN", "status": "UNSUPPORTED_ORACLE", "pass": False}


def _oracle_list(value: Any) -> list[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        return [value]
    return [item for item in list(value or []) if isinstance(item, Mapping)]


def _oracle_status_execution(oracle_rows: list[Mapping[str, Any]]) -> str | None:
    statuses = {str(row.get("status") or "").upper() for row in oracle_rows}
    if statuses & {"INVALID_ORACLE_POLICY", "INVALID_ORACLE_PATH", "UNSUPPORTED_ORACLE"}:
        return "INVALID_SETUP"
    if "NOT_MEASURED_ENVIRONMENT" in statuses:
        return "INFRASTRUCTURE_BLOCKED"
    if "EXECUTION_FAILED" in statuses:
        return "FAILED"
    return None


def score_host_observation(evaluator: Mapping[str, Any], project: Path, observation: Mapping[str, Any]) -> dict[str, Any]:
    """Score Host output only from sealed evaluator state and workspace state."""
    project = project.resolve()
    verify_sealed(evaluator, field="manifestDigest", code="BENCHMARK_GROUND_TRUTH_TAMPERED")
    changes = _project_changes(project, evaluator)
    changed = changes["all"]
    allowed_patterns = [str(item) for item in evaluator.get("allowedScope", [])]
    protected_patterns = [str(item) for item in evaluator.get("protectedScope", [])]
    unexpected = sorted(path for path in changed if not _matches(path, allowed_patterns))
    protected = sorted(path for path in changed if _matches(path, protected_patterns))
    expected_roots = {str(item) for item in evaluator.get("expectedRootSources", [])}
    claimed_root = {str(item) for item in observation.get("rootCauseFiles", [])}
    regressions = [str(item) for item in observation.get("regressions", [])]
    outcome = str(observation.get("outcome") or "NOT_VERIFIED").upper()
    tp = len(expected_roots & claimed_root)
    fp = len(claimed_root - expected_roots)
    fn = len(expected_roots - claimed_root)
    root_precision = (tp / (tp + fp)) if (tp + fp) else None
    root_recall = (tp / (tp + fn)) if (tp + fn) else None
    expectation = str(evaluator.get("expectation") or "REPAIR").upper()
    diagnosis_mode = expectation in {"DIAGNOSIS", "DIAGNOSE", "CHECK"}
    oracle_specs = _oracle_list(evaluator.get("defectOracle") if diagnosis_mode else evaluator.get("oracle"))
    oracle_rows = [_oracle_result(project, o) for o in oracle_specs]
    oracle_ok = bool(oracle_rows) and all(bool(row.get("pass")) for row in oracle_rows)
    injection = dict(evaluator.get("defectInjection") or {})
    injection_status = str(injection.get("status") or "VALIDATED").upper()
    if expectation == "NO_MUTATION":
        oracle_objective_satisfied: bool | None = bool(oracle_rows) and oracle_ok
        ground_truth_satisfied = bool(not changed and oracle_objective_satisfied)
        scope_correct = not changed
    elif diagnosis_mode:
        oracle_objective_satisfied = bool(oracle_rows) and oracle_ok
        # Diagnosis is read-only: exact root identification is an independent
        # evaluator gate and cannot be inferred from a positive claim alone.
        root_identified = claimed_root == expected_roots
        ground_truth_satisfied = bool(oracle_objective_satisfied and root_identified and not changed)
        scope_correct = not changed and root_identified
    else:
        oracle_objective_satisfied = bool(oracle_rows) and oracle_ok
        ground_truth_satisfied = bool(oracle_objective_satisfied)
        scope_correct = not unexpected and not protected
    claim = observation.get("claim")
    if claim in (None, ""):
        # Legacy result templates predate the claim field.  Synthesize only a
        # compatibility hint; the evaluator still requires the oracle and
        # outcome gates below.
        claim = "The task was completed successfully." if outcome == "VERIFIED" else "The task was not verified."
    explicit_execution = observation.get("executionStatus")
    execution_status = normalize_execution_status(explicit_execution) if explicit_execution not in (None, "") else "COMPLETED"
    oracle_execution = _oracle_status_execution(oracle_rows)
    if oracle_execution in {"INVALID_SETUP", "INFRASTRUCTURE_BLOCKED"}:
        execution_status = oracle_execution
    run_validity = normalize_run_validity(observation.get("runValidity"))
    if injection_status == "INVALID_SETUP":
        run_validity = "INVALID_SETUP"
    evaluation = evaluate_problem_solved(
        claim=claim,
        outcome=outcome,
        execution_status=execution_status,
        run_validity=run_validity,
        oracle_objective_satisfied=oracle_objective_satisfied,
        scope_correct=scope_correct,
        no_forbidden_drift=not regressions,
        expectation=expectation,
    )
    task_success = evaluation["problemSolved"] is True
    false_verified = outcome == "VERIFIED" and not task_success
    scope_precision = None if not changed else sum(1 for path in changed if _matches(path, allowed_patterns)) / len(changed)
    attempted = bool(changed)
    regression_escape = bool(outcome == "VERIFIED" and (regressions or unexpected or protected or not ground_truth_satisfied))
    return {
        "schemaVersion": "4", "runId": evaluator.get("runId"), "caseId": evaluator.get("caseId"),
        "repetition": evaluator.get("repetition"), "difficulty": evaluator.get("difficulty"), "family": evaluator.get("family"),
        "hostOutcome": outcome, "repairSuccess": task_success, "problemSolved": evaluation["problemSolved"],
        "eligibleForSuccessRate": evaluation["eligibleForSuccessRate"], "executionStatus": evaluation["executionStatus"],
        "runValidity": evaluation["runValidity"], "falseVerified": false_verified,
        "rootCausePrecision": root_precision, "rootCauseRecall": root_recall,
        "rootCauseTP": tp, "rootCauseFP": fp, "rootCauseFN": fn,
        "scopePrecision": scope_precision, "repairAttempted": attempted,
        "regressionEscape": regression_escape, "changedFiles": changed,
        "unexpectedChanges": unexpected, "protectedScopeChanges": protected,
        "groundTruthSatisfied": ground_truth_satisfied, "oracleObjectiveSatisfied": oracle_objective_satisfied,
        "oracleMode": "DIAGNOSIS" if diagnosis_mode else expectation, "diagnosisSuccess": task_success if diagnosis_mode else None,
        "defectInjectionStatus": injection_status, "oracleResults": oracle_rows,
        "claimClassification": evaluation["claimClassification"], "claimCompatible": evaluation["claimCompatible"],
        "problemSolvedReasonCodes": evaluation["problemSolvedReasonCodes"],
        "claimBoundary": "Repair, diagnosis and no-mutation success are evaluator-computed from sealed setup, source/behavior/browser oracles, workspace state and compatible outcome claims. Host self-reports cannot set problemSolved.",
    }


def _write_private_manifest(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _default_isolated_root(prefix: str) -> Path:
    return Path(tempfile.mkdtemp(prefix=prefix)).resolve()


def prepare_all(
    destination: Path, *, repetitions: int = 1, corpus: str = "v2", host_root: Path | None = None, evaluator_root: Path | None = None,
    cases_override: list[dict[str, Any]] | None = None, planned_host: Mapping[str, Any] | None = None,
    planned_conditions: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if repetitions < 1:
        raise ValueError("repetitions must be >= 1")
    controller = destination.resolve()
    if controller.exists():
        shutil.rmtree(controller)
    controller.mkdir(parents=True)
    integrity_key = create_integrity_key(controller / ".benchmark-integrity.key")
    host_root = (host_root.resolve() if host_root else _default_isolated_root("wuq-host-workspaces-"))
    evaluator_root = (evaluator_root.resolve() if evaluator_root else _default_isolated_root("wuq-evaluator-private-"))
    for root in (host_root, evaluator_root):
        if root == controller or root in controller.parents or controller in root.parents:
            raise ValueError("Host, evaluator and controller roots must not be ancestor/descendant of one another")
        root.mkdir(parents=True, exist_ok=True)
    results_dir = controller / "results"
    results_dir.mkdir(parents=True)
    cases = list(cases_override) if cases_override is not None else load_cases(corpus=corpus)
    planned_host = dict(planned_host or {"name": "external-host", "version": "UNSPECIFIED", "model": "UNSPECIFIED"})
    planned_conditions = dict(planned_conditions or {
        "reasoningMode": "UNSPECIFIED", "permissionProfile": "UNSPECIFIED", "toolPolicy": "UNSPECIFIED",
        "browserCondition": "UNSPECIFIED", "authCondition": "UNSPECIFIED", "os": "UNSPECIFIED",
        "runtime": "UNSPECIFIED", "contextPolicy": "wuq-relevant-context-v1", "wuqVersion": "4.0.0-rc.1",
        "fixtureVersion": f"fault-injection-{corpus}",
    })
    planned_fp = condition_fingerprint(planned_host, planned_conditions)
    runs: list[dict[str, Any]] = []
    manifest_digests: dict[str, str] = {}
    manifest_macs: dict[str, str] = {}
    for case in cases:
        for repetition in range(1, repetitions + 1):
            run_id = f"{case['id']}-r{repetition:02d}"
            project = host_root / run_id / "project"
            prepared = prepare_case(case, project, run_id=run_id, repetition=repetition, planned_host=planned_host, planned_conditions=planned_conditions)
            evaluator_path = evaluator_root / f"{run_id}.json"
            _write_private_manifest(evaluator_path, prepared["evaluatorManifest"])
            manifest_digests[run_id] = str(prepared["evaluatorManifest"]["manifestDigest"])
            manifest_macs[run_id] = integrity_mac(prepared["evaluatorManifest"], integrity_key)
            runs.append({
                "runId": run_id, "caseId": case["id"], "repetition": repetition,
                "difficulty": case["difficulty"], "family": case.get("family"), "archetype": case.get("archetype"), "request": case["request"],
                "protectedScope": list(case.get("protectedScope") or []),
                "projectPath": str(project), "taskPath": str(project / TASK_FILE),
                "resultId": f"{run_id}.json", "plannedHost": planned_host, "plannedConditions": planned_conditions,
                "conditionDigest": planned_fp["digest"],
            })
    plan_body = {
        "schemaVersion": "4", "kind": "PLAN", "protocolVersion": "4", "fixtureVersion": f"fault-injection-{corpus}",
        "caseCount": len(cases), "archetypeCount": len({str(c.get("archetype")) for c in cases}),
        "repetitionsPerCase": repetitions, "runCount": len(runs), "runs": runs,
        "conditionAuthority": "CONTROLLER_PLANNED",
        "agentLoopStatus": "NOT_RUN",
        "claimBoundary": "Host-facing plan excludes evaluator filesystem paths and answer material. Result destinations are controller-derived from runId and cannot be supplied by the Host.",
    }
    plan = mac_seal_object(plan_body, key=integrity_key, digest_field="planDigest", mac_field="planMac")
    (controller / "benchmark-plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    state_body = {
        "schemaVersion": "4", "controllerRoot": str(controller), "hostRoot": str(host_root), "evaluatorRoot": str(evaluator_root),
        "groundTruthRootDigest": merkleish_root(manifest_digests), "manifestDigests": manifest_digests, "manifestMacs": manifest_macs,
        "integrityMode": "CONTROLLER_HMAC_SHA256",
        "workspaceIsolation": "SEPARATE_FILESYSTEM_ROOTS",
        "claimBoundary": "Evaluator root is outside Host/controller trees. OS-wide same-user isolation still depends on the Host sandbox/ACL and is not remotely attested by this protocol.",
    }
    state = mac_seal_object(state_body, key=integrity_key, digest_field="stateDigest", mac_field="stateMac")
    _write_private_manifest(controller / "benchmark-controller-state.json", state)
    return {
        "status": "READY", "controllerDir": str(controller), "hostWorkspaceRoot": str(host_root),
        "caseCount": len(cases), "archetypeCount": len({str(c.get("archetype")) for c in cases}), "runCount": len(runs), "repetitionsPerCase": repetitions,
        "conditionDigest": planned_fp["digest"], "conditionAuthority": "CONTROLLER_PLANNED",
        "planDigest": plan["planDigest"], "integrityMode": "CONTROLLER_HMAC_SHA256", "workspaceIsolation": "SEPARATE_FILESYSTEM_ROOTS",
        "agentLoopStatus": "NOT_RUN",
        "claimBoundary": "Only hostWorkspaceRoot should be opened in Codex/Claude. Evaluator location is intentionally omitted from this Host-facing response.",
    }


def self_test() -> dict[str, Any]:
    cases = load_cases(corpus="v2")
    protected_failures: list[str] = []
    blind_leaks: list[str] = []
    metrics_by_k: dict[int, list[dict[str, Any]]] = {5: [], 8: []}
    family_metrics: dict[str, dict[int, list[dict[str, Any]]]] = {}
    difficulty_metrics: dict[str, dict[int, list[dict[str, Any]]]] = {}
    with tempfile.TemporaryDirectory(prefix="wuq-fault-controller-") as raw:
        controller = Path(raw) / "controller"
        prepared_all = prepare_all(controller, repetitions=1, corpus="v2")
        plan = json.loads((controller / "benchmark-plan.json").read_text(encoding="utf-8"))
        verify_sealed(plan, field="planDigest", code="BENCHMARK_PLAN_TAMPERED")
        state = json.loads((controller / "benchmark-controller-state.json").read_text(encoding="utf-8"))
        verify_sealed(state, field="stateDigest", code="BENCHMARK_CONTROLLER_TAMPERED")
        host_root = Path(prepared_all["hostWorkspaceRoot"]); evaluator_root = Path(state["evaluatorRoot"])
        separation_ok = not (host_root in evaluator_root.parents or evaluator_root in host_root.parents or host_root == evaluator_root)
        for run in plan["runs"]:  # Beta.7 measures every instance, never a first-N sample.
            project = Path(run["projectPath"]); task_text = Path(run["taskPath"]).read_text(encoding="utf-8")
            for forbidden in ("cleanContent", "injectedContent", "expectedRootSources", "allowedScope", "evaluatorRoot", "groundTruth", '"oracle"'):
                if forbidden in task_text:
                    blind_leaks.append(f"{run['runId']}:{forbidden}")
            evaluator = json.loads((evaluator_root / f"{run['runId']}.json").read_text(encoding="utf-8"))
            expected = list(evaluator.get("expectedRootSources") or [])
            # Ground truth must not seed retrieval. Measure against a normal project baseline.
            baseline = build_project_baseline(project)
            packet = build_relevant_context_packet(
                project, request=str(evaluator["request"]),
                task_goal={"goal": evaluator["request"], "nonGoals": evaluator["protectedScope"]},
                baseline=baseline, max_source_refs=8,
            )
            if packet["mandatoryContext"].get("protectedScope") != evaluator.get("protectedScope"):
                protected_failures.append(str(run["runId"]))
            if expected:
                family = str(run.get("family") or "unknown"); difficulty = str(run.get("difficulty") or "unknown")
                family_metrics.setdefault(family, {5: [], 8: []}); difficulty_metrics.setdefault(difficulty, {5: [], 8: []})
                for k in (5, 8):
                    row = context_retrieval_metrics(packet, expected, k=k)
                    metrics_by_k[k].append(row); family_metrics[family][k].append(row); difficulty_metrics[difficulty][k].append(row)
    def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
        recalls=[float(r["recall"]) for r in rows if isinstance(r.get("recall"),(int,float))]
        precisions=[float(r["precision"]) for r in rows if isinstance(r.get("precision"),(int,float))]
        tokens=[int(r.get("estimatedSourceTokens") or 0) for r in rows]
        return {
            "measuredRuns": len(rows), "meanRecall": sum(recalls)/len(recalls) if recalls else None,
            "meanPrecision": sum(precisions)/len(precisions) if precisions else None,
            "meanEstimatedSourceTokens": sum(tokens)/len(tokens) if tokens else None,
        }
    context = {
        "measuredRuns": len(metrics_by_k[8]), "totalRuns": len(cases), "measurementScope": "ALL_APPLICABLE_CASES",
        "at5": summarize(metrics_by_k[5]), "at8": summarize(metrics_by_k[8]),
        "byFamily": {family: {f"at{k}": summarize(rows[k]) for k in (5,8)} for family, rows in sorted(family_metrics.items())},
        "byDifficulty": {level: {f"at{k}": summarize(rows[k]) for k in (5,8)} for level, rows in sorted(difficulty_metrics.items())},
    }
    passed = separation_ok and not blind_leaks and not protected_failures and len({c.get("archetype") for c in cases}) == len(cases)
    oracle_kinds = sorted({str(o.get("type")) for c in cases for o in c.get("oracle", [])})
    return {
        "schemaVersion": "4", "status": "PASS" if passed else "FAIL", "caseCount": len(cases),
        "archetypeCount": len({c.get("archetype") for c in cases}), "familyCount": len({c.get("family") for c in cases}),
        "oracleKinds": oracle_kinds, "workspaceRootSeparation": "PASS" if separation_ok else "FAIL",
        "groundTruthLeakCount": len(blind_leaks), "contextRetrieval": context,
        "contextRootSourceRecallAt5": context["at5"]["meanRecall"], "contextRootSourceRecallAt8": context["at8"]["meanRecall"],
        "protectedScopeRecall": 1.0 if not protected_failures else (len(cases)-len(protected_failures))/len(cases),
        "contextRecallStatus": "MEASURED_NOT_A_HARNESS_GATE",
        "agentLoopStatus": "NOT_VERIFIED_HOST_AGENT", "hostAutomationStatus": "NOT_VERIFIED_HOST_AUTOMATION",
        "agentCost": "NOT_MEASURED", "agentVariance": "NOT_MEASURED",
        "claimBoundary": "PASS qualifies path-separated roots, sealed manifests, 40/40 deterministic development-corpus diversity and all-applicable-case context metrics. Source-contract and executable fixture oracles do not imply model accuracy or OS-level Agent isolation.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Web UI Quality benchmark corpus/fault harness")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--self-test", action="store_true")
    group.add_argument("--prepare-all", type=Path)
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--corpus", choices=["v1", "v2", "holdout-v1"], default="v2")
    parser.add_argument("--host-root", type=Path)
    parser.add_argument("--evaluator-root", type=Path)
    args = parser.parse_args()
    result = self_test() if args.self_test else prepare_all(args.prepare_all, repetitions=args.repetitions, corpus=args.corpus, host_root=args.host_root, evaluator_root=args.evaluator_root)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result.get("status") in {"PASS", "READY"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
