#!/usr/bin/env python3
"""Attack-grade regression checks for trust and evidence boundaries."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime" / "python"))

from web_ui_quality.contracts import ContractViolation
from web_ui_quality.experience_fix import run_experience_fix
from web_ui_quality.experience_run import create_experience_run, load_experience_run, seal_before, write_phase_file
from web_ui_quality.fix_workflow import prepare_fix_workflow
from web_ui_quality.host_bridge import HostTaskScope, require_host_scope
from web_ui_quality.safe_edit import apply_change_set, bind_trusted_current_conversation_approval, rollback_change_set


def expect_code(fn, code: str) -> bool:
    try:
        fn()
    except ContractViolation as error:
        return error.code == code
    return False


def main() -> int:
    from web_ui_quality.release_info import configure_stdout

    configure_stdout()
    checks: list[tuple[str, bool]] = []
    with tempfile.TemporaryDirectory(prefix="wuq-attack-") as temp:
        root = Path(temp)
        target = {"kind": "url", "url": "https://example.test/app", "route": "/app"}
        conditions = {
            "url": "https://example.test/app", "scheme": "https", "host": "example.test",
            "port": 443, "route": "/app", "query_policy": "exact", "query": "",
            "target_kind": "url", "project_root": None, "locale": "zh-CN",
            "viewports": [{"width": 390, "height": 844}],
        }

        # Run state is anchored and cannot be silently rewritten.
        run = create_experience_run(root / "runs-a", task_id="t1", session_id="s1", mode="CHECK", target=target, conditions=conditions, run_id="wuq-1111111111111111")
        run_dir = Path(run["runDir"])
        config_path = run_dir / "run.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["taskId"] = "attacker-task"
        config_path.write_text(json.dumps(config), encoding="utf-8")
        checks.append(("run-json-tamper-detected", expect_code(lambda: load_experience_run(run_dir), "RUN_STATE_TAMPERED")))

        # Files introduced outside a sealed manifest invalidate the baseline.
        run2 = create_experience_run(root / "runs-b", task_id="t2", session_id="s2", mode="CHECK", target=target, conditions=conditions, run_id="wuq-2222222222222222")
        run2_dir = Path(run2["runDir"])
        write_phase_file(run2_dir, "before", "page.json", "{}")
        seal_before(run2_dir)
        (run2_dir / "before" / "injected.txt").write_text("attack", encoding="utf-8")
        checks.append(("manifest-extra-file-detected", expect_code(lambda: load_experience_run(run2_dir), "BASELINE_TAMPERED")))

        # A Python value constructed inside Runtime cannot grant Host authority.
        forged = HostTaskScope("t3", "s3", "NARROW_PROJECT_LOCAL_UI_EDIT", ("F-1",), ("src/App.tsx",))
        checks.append(("runtime-host-scope-forgery-rejected", expect_code(
            lambda: require_host_scope(forged, mode="NARROW_PROJECT_LOCAL_UI_EDIT", task_id="t3", session_id="s3", finding_ids=["F-1"], source_scope=["src/App.tsx"]),
            "HOST_EDITING_REQUIRED",
        )))

        # Legacy Runtime write/rollback channels remain disabled.
        checks.append(("runtime-approval-minting-disabled", expect_code(
            lambda: bind_trusted_current_conversation_approval({}, evidence_ref="x", evidence_resolver=lambda _: True),
            "HOST_EDITING_REQUIRED",
        )))
        checks.append(("runtime-apply-disabled", expect_code(lambda: apply_change_set(root, {}), "HOST_EDITING_REQUIRED")))
        checks.append(("runtime-rollback-disabled", expect_code(lambda: rollback_change_set(root, {}), "HOST_EDITING_REQUIRED")))

        # No evidence-backed source ownership means no guessed low-risk scope.
        project = root / "project"
        (project / "src").mkdir(parents=True)
        (project / "src" / "App.tsx").write_text("export const App = () => null;", encoding="utf-8")
        plan = prepare_fix_workflow(project, root / "fix-plan")
        checks.append(("unmapped-finding-scope-not-confirmed", plan["status"] == "SCOPE_NOT_CONFIRMED" and plan["risk"] == "UNKNOWN" and plan["files"] == []))

        # Actual After URL identity must be the same sealed target.
        # Use an existing sealed run so the check happens before Browser work.
        run3 = create_experience_run(root / "runs-c", task_id="t4", session_id="s4", mode="FIX_AND_VERIFY", target=target, conditions=conditions, run_id="wuq-3333333333333333")
        run3_dir = Path(run3["runDir"])
        write_phase_file(run3_dir, "before", "smart-acceptance-report.json", json.dumps({"pageHealth": {"pageStatus": "NOT_VERIFIED"}}))
        seal_before(run3_dir)
        checks.append(("different-after-url-blocked", expect_code(
            lambda: run_experience_fix(
                "https://example.test/app", root / "runs-c", request="修复并验证", mode="FIX_AND_VERIFY",
                task_id="t4", session_id="s4", url="https://example.test/app", existing_run=run3_dir,
                after_url="https://different.test/other",
            ),
            "TARGET_IDENTITY_MISMATCH",
        )))

    failed = [name for name, ok in checks if not ok]
    result = {
        "status": "PASS" if not failed else "FAIL",
        "scope": "TRUST_INTEGRITY_ATTACK_REGRESSION",
        "checks": [{"id": name, "status": "PASS" if ok else "FAIL"} for name, ok in checks],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
