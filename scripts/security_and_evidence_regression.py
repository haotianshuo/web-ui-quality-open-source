#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "runtime" / "python"))

from web_ui_quality.command_policy import classify_command
from web_ui_quality.contracts import ContractViolation, digest_json, hash_file
from web_ui_quality.discovery_cache import cache_key, read_discovery_cache, write_discovery_cache
from web_ui_quality.experience_run import create_experience_run, load_experience_run, seal_after, seal_before, validate_after_binding, write_phase_file
from web_ui_quality.host_bridge import HostTaskScope, bind_narrow_project_local_ui_edit, require_host_scope, verify_host_write_receipt
from web_ui_quality.project_baseline import build_project_baseline
from web_ui_quality.project_launcher import inspect_project_start
from web_ui_quality.source_assurance import command_safety_plan, run_source_assurance


def _symlink_supported(base: Path) -> bool:
    """Probe real symlink capability, not just API presence.

    ``os.symlink`` exists on Windows but raises ``WinError 1314`` unless the
    process holds SeCreateSymbolicLinkPrivilege (Developer Mode or elevation).
    Probing ``hasattr`` therefore turns a missing privilege into a crash that
    hides every later check in this suite.
    """
    if not hasattr(os, "symlink"):
        return False
    probe_target = base / ".symlink-probe-target"
    probe_link = base / ".symlink-probe-link"
    try:
        probe_target.mkdir(exist_ok=True)
        os.symlink(probe_target, probe_link)
    except (OSError, NotImplementedError):
        return False
    finally:
        for path in (probe_link, probe_target):
            try:
                path.unlink() if path.is_symlink() or path.is_file() else path.rmdir()
            except OSError:
                pass
    return True


def expect_code(fn, code: str) -> None:
    try:
        fn()
    except ContractViolation as error:
        assert error.code == code, (error.code, code)
    else:
        raise AssertionError(f"expected {code}")


def main() -> int:
    from web_ui_quality.release_info import configure_stdout

    configure_stdout()
    checks: list[tuple[str, bool]] = []
    skipped: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        target = {"kind": "url", "url": "https://example.test:443/app", "route": "/app"}
        conditions = {"url": "https://example.test:443/app", "route": "/app", "locale": "zh-CN", "viewports": [{"width": 390, "height": 844}]}
        run = create_experience_run(base, task_id="task-1", session_id="session-1", mode="FIX_AND_VERIFY", target=target, conditions=conditions, run_id="wuq-0123456789abcdef")
        run_dir = Path(run["runDir"])
        write_phase_file(run_dir, "before", "evidence.json", "{}")
        before = seal_before(run_dir)
        checks.append(("immutable-before-first", before["fileCount"] == 1))
        expect_code(lambda: write_phase_file(run_dir, "before", "second.json", "{}"), "BEFORE_EVIDENCE_IMMUTABLE")
        expect_code(lambda: seal_before(run_dir), "BEFORE_EVIDENCE_IMMUTABLE")
        checks.append(("immutable-before-repeat", True))
        validate_after_binding(run_dir, task_id="task-1", session_id="session-1", mode="FIX_AND_VERIFY", target=target, conditions=conditions, baseline_digest=before["baselineDigest"])
        checks.append(("after-correct-binding", True))
        expect_code(lambda: validate_after_binding(run_dir, task_id="task-2", target=target, conditions=conditions), "BASELINE_IDENTITY_MISMATCH")
        expect_code(lambda: validate_after_binding(run_dir, task_id="task-1", target={**target, "route": "/other"}, conditions=conditions), "TARGET_IDENTITY_MISMATCH")
        expect_code(lambda: validate_after_binding(run_dir, task_id="task-1", target=target, conditions={**conditions, "locale": "en-US"}), "CONDITIONS_MISMATCH")
        checks.append(("after-mismatch-blocked", True))
        write_phase_file(run_dir, "after", "evidence.json", "{}")
        seal_after(run_dir)
        checks.append(("after-sealed", True))

        # Direct evidence tamper must be detected before any later phase can proceed.
        (run_dir / "before" / "evidence.json").write_text('{"tampered":true}', encoding="utf-8")
        expect_code(lambda: load_experience_run(run_dir), "BASELINE_TAMPERED")
        checks.append(("external-before-tamper-detected", True))

        # Path traversal and link/reparse escape.
        expect_code(lambda: create_experience_run(base, task_id="x", session_id="y", mode="CHECK", target={}, conditions={}, run_id="../escaped"), "EXPERIENCE_RUN_ID_INVALID")
        checks.append(("run-id-traversal-blocked", True))
        link_run = create_experience_run(base, task_id="link", session_id="link", mode="CHECK", target={}, conditions={}, run_id="wuq-fedcba9876543210")
        link_dir = Path(link_run["runDir"])
        outside = base / "outside"; outside.mkdir()
        if _symlink_supported(base):
            os.symlink(outside, link_dir / "before" / "link")
            expect_code(lambda: write_phase_file(link_dir, "before", "link/pwned.txt", "x"), "EXPERIENCE_EVIDENCE_PATH_INVALID")
            checks.append(("evidence-symlink-escape-blocked", not (outside / "pwned.txt").exists()))
        else:
            skipped.append("evidence-symlink-escape-blocked")

        # Runtime objects are never authorization.
        forged = HostTaskScope("task-1", "attacker-session", "NARROW_PROJECT_LOCAL_UI_EDIT", ("F-1",), ("src/App.tsx",))
        expect_code(lambda: require_host_scope(forged, mode="NARROW_PROJECT_LOCAL_UI_EDIT", task_id="task-1", session_id="attacker-session", finding_ids=["F-1"], source_scope=["src/App.tsx"]), "HOST_EDITING_REQUIRED")
        claim = bind_narrow_project_local_ui_edit(task_id="task-1", session_id="session-1", finding_ids=["F-1"], source_scope=["src/App.tsx"])
        checks.append(("host-scope-is-non-authoritative", claim.authorization_granted is False))

        host_project = base / "host-project"; (host_project / "src").mkdir(parents=True)
        host_file = host_project / "src" / "App.tsx"; host_file.write_text("export const x = 1;", encoding="utf-8")
        project_baseline = build_project_baseline(host_project)
        before_hash = hash_file(host_file)
        host_file.write_text("export const x = 2;", encoding="utf-8")
        after_hash = hash_file(host_file)
        receipt_files = [{"path": "src/App.tsx", "beforeSha256": before_hash, "afterSha256": after_hash}]
        receipt = {
            "runId": "wuq-0123456789abcdef",
            "taskId": "task-1", "sessionId": "session-1", "findingIds": ["F-1"],
            "sourceScope": ["src/App.tsx"], "exclusions": ["dependencies"],
            "baselineDigest": project_baseline["baselineDigest"],
            "planDigest": "a" * 64,
            "patchCandidateDigest": digest_json({"sourceScope": ["src/App.tsx"], "files": receipt_files}),
            "toolchainDigest": "b" * 64,
            "verificationContextDigest": "c" * 64,
            "files": receipt_files,
        }
        verified = verify_host_write_receipt(
            host_project, receipt, task_id="task-1", session_id="session-1", finding_ids=["F-1"],
            source_scope=["src/App.tsx"], exclusions=["dependencies"], run_id="wuq-0123456789abcdef",
            baseline=project_baseline, plan_digest="a" * 64, toolchain_digest="b" * 64,
            verification_context_digest="c" * 64,
        )
        checks.append(("host-write-receipt-hash-verified", verified.to_dict()["status"] == "HOST_WRITE_VERIFIED"))

        cache_path = base / "cache.json"
        key = cache_key(project_fingerprint="a" * 64, source_scope=["src/App.tsx"], runtime_version="4", schema_version="1.1", input_signature={"x": 1})
        envelope = write_discovery_cache(cache_path, key=key, payload={"productDiscovery": {"name": "demo"}, "authorization": "forbidden", "fullSource": "secret"})
        loaded = read_discovery_cache(cache_path, expected_key=key)
        checks.append(("cache-no-authority", loaded == {"productDiscovery": {"name": "demo"}} and envelope["authority"] is False))

        # Source parsing: unsupported text is not syntax PASS; invalid CSS is a deterministic FAIL.
        source_project = base / "source-project"; source_project.mkdir()
        (source_project / "broken.js").write_text("function broken( {\n return 1;", encoding="utf-8")
        (source_project / "broken.css").write_text("a { color red;", encoding="utf-8")
        (source_project / "valid.py").write_text("x = 1\n", encoding="utf-8")
        js_report = run_source_assurance(source_project, output_dir=base / "source-js", files=["broken.js"])
        css_report = run_source_assurance(source_project, output_dir=base / "source-css", files=["broken.css"])
        py_report = run_source_assurance(source_project, output_dir=base / "source-py", files=["valid.py"])
        checks.append(("unsupported-js-not-verified", js_report["status"] == "NOT_VERIFIED" and js_report["deterministicChecks"][0]["syntaxVerified"] is False))
        checks.append(("invalid-css-fails", css_report["status"] == "FAIL"))
        checks.append(("trusted-python-parser-passes", py_report["status"] == "VERIFIED_WITH_WARNINGS"))

        # One shared command policy must catch compound destruction, write-producing tools, flags, and nested scripts.
        checks.append(("compound-destructive-blocked", classify_command("eslint . && rm -rf /tmp/example")["classification"] == "BLOCKED"))
        checks.append(("ruff-format-needs-approval", classify_command("ruff format .")["classification"] == "REQUIRES_APPROVAL"))
        checks.append(("tsc-outdir-needs-approval", classify_command("tsc --outDir dist")["classification"] == "REQUIRES_APPROVAL"))
        checks.append(("npm-flags-install-blocked", classify_command("npm --silent --prefix . --workspace app install")["classification"] == "BLOCKED"))

        launch_project = base / "launch-project"; launch_project.mkdir()
        (launch_project / "package.json").write_text(json.dumps({"scripts": {"dev": "npm run hidden", "hidden": "rm -rf /tmp/example"}}), encoding="utf-8")
        (launch_project / "node_modules").mkdir()
        start = inspect_project_start(launch_project)
        checks.append(("nested-dangerous-script-blocked", start["status"] == "SCRIPT_BLOCKED"))
        source_plan = command_safety_plan(launch_project)
        dev = next(row for row in source_plan["commands"] if row["id"] == "npm:dev")
        checks.append(("source-assurance-shares-command-policy", dev["classification"] == "BLOCKED" and source_plan["classifier"] == "web_ui_quality.command_policy"))

    failed = [name for name, ok in checks if not ok]
    result = {
        "status": "PASS" if not failed else "FAIL",
        "scope": "SECURITY_AND_EVIDENCE_REGRESSION",
        "checks": [{"id": name, "status": "PASS" if ok else "FAIL"} for name, ok in checks]
        + [{"id": name, "status": "SKIPPED", "reason": "symbolic links unavailable in this environment"} for name in skipped],
    }
    if skipped:
        result["skipped"] = skipped
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
