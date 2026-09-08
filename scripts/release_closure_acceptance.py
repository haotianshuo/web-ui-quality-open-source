#!/usr/bin/env python3
"""Independent Beta-gate acceptance for Release Closure and guided repair."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = (ROOT / "runtime" / "python").resolve()
if str(RUNTIME) in sys.path:
    sys.path.remove(str(RUNTIME))
sys.path.insert(0, str(RUNTIME))

import web_ui_quality
from web_ui_quality import __all__ as ROOT_EXPORTS
from web_ui_quality.contracts import digest_json, hash_file
from web_ui_quality.design_intelligence import generate_design_candidates
from web_ui_quality.outcome_verification import combine_repair_verification
from web_ui_quality.project_baseline import build_project_baseline, compare_project_baseline
from web_ui_quality.project_tool_boundary import plan_project_tool_execution, summarise_host_tool_results, verify_host_tool_result
from web_ui_quality.release_info import PACKAGE_VERSION


def _check(name: str, condition: bool, detail: str = "") -> dict[str, str]:
    return {"check": name, "status": "PASS" if condition else "FAIL", "detail": detail}


def main() -> int:
    checks: list[dict[str, str]] = []
    runtime_file = Path(web_ui_quality.__file__).resolve()
    checks.append(_check("package-local-runtime-loaded", runtime_file.is_relative_to(RUNTIME), str(runtime_file)))
    with tempfile.TemporaryDirectory(prefix="wuq-release-closure-") as raw:
        base = Path(raw)
        project = base / "legacy"
        target = project / "packages" / "orders" / "src" / "Button.tsx"
        target.parent.mkdir(parents=True)
        target.write_text("export const Button=()=> <button>OK</button>\n", encoding="utf-8")
        (project / "packages" / "orders" / "tsconfig.json").write_text('{"compilerOptions":{"strict":true}}', encoding="utf-8")
        (project / "package.json").write_text('{"devDependencies":{"typescript":"5.9.0"}}', encoding="utf-8")
        (project / "000.css").write_text("a{}", encoding="utf-8")
        rel = "packages/orders/src/Button.tsx"
        baseline = build_project_baseline(project, max_files=1, target_files=[rel])
        checks.append(_check(
            "partial-repo-target-and-critical-context",
            baseline["truncated"] is True
            and baseline["targetCoverage"]["status"] == "COMPLETE"
            and baseline["criticalContextCoverage"]["status"] == "COMPLETE"
            and "packages/orders/tsconfig.json" in baseline["criticalContextCoverage"]["indexed"],
        ))
        (project / "packages" / "orders" / "tsconfig.json").write_text('{"compilerOptions":{"strict":false}}', encoding="utf-8")
        drift = compare_project_baseline(baseline, project, target_files=[rel])
        checks.append(_check(
            "critical-context-drift-requires-revalidation",
            drift["status"] == "REVALIDATION_REQUIRED" and drift["patchScopeAssurance"] == "NOT_VERIFIED",
        ))

        tool_project = base / "tool"
        tool_bin = tool_project / "node_modules" / ".bin"
        tool_bin.mkdir(parents=True)
        (tool_bin / "tsc").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        plan = plan_project_tool_execution(tool_project, "tsc", args=["--noEmit"])
        receipt = {
            "planDigest": plan["planDigest"], "tool": plan["tool"], "executableSha256": plan["executableSha256"],
            "argv": plan["argv"], "cwd": plan["cwd"], "exitCode": 2, "stdout": "", "stderr": "type error",
            "timedOut": False, "networkPolicyEnforced": True, "resourcePolicyEnforced": True,
            "filesystemPolicy": plan["filesystemPolicy"], "filesystemPolicyEnforced": True, "unexpectedWrites": [],
        }
        trusted = verify_host_tool_result(tool_project, plan, receipt)
        tool_gate = summarise_host_tool_results([trusted])
        decision = combine_repair_verification(
            browser_outcome_status="IMPROVEMENT_CLAIM_ALLOWED",
            project_tool_status=tool_gate["status"], patch_quality_status="QUALITY_OK",
        )
        checks.append(_check(
            "tool-fail-cannot-be-overridden-by-visual-improvement",
            tool_gate["status"] == "FAIL" and decision["status"] == "FAIL",
        ))

    candidates = generate_design_candidates({"experienceModel": {"primaryTask": "Review orders", "risk": "high"}})
    checks.append(_check(
        "candidate-recommendation-is-not-selection",
        candidates["selected"] is None
        and candidates["recommended"]
        and candidates["differenceGate"]["gateType"] == "DECLARED_DIRECTION_CONTRACT_DIFFERENCE",
    ))

    manifest = json.loads((ROOT / "runtime/python/web_ui_quality/public-api-manifest.json").read_text(encoding="utf-8"))
    checks.append(_check(
        "public-api-manifest-exact",
        manifest.get("packageVersion") == PACKAGE_VERSION
        and manifest.get("exports") == list(ROOT_EXPORTS)
        and manifest.get("stable") == ["run"],
    ))

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    plugin = (ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
    forbidden = ("machine-verified structural-difference", "pairwise structural-difference gate", "结构差异 Gate 验证")
    checks.append(_check(
        "candidate-claim-language-is-honest",
        not any(term in readme or term in plugin for term in forbidden),
    ))

    failed = [row for row in checks if row["status"] != "PASS"]
    print(json.dumps({
        "status": "FAIL" if failed else "PASS",
        "version": PACKAGE_VERSION,
        "runtimeFile": str(runtime_file),
        "runtimeRoot": str(RUNTIME),
        "runtimeIdentityDigest": digest_json({
            "packageInit": hash_file(runtime_file),
            "releaseInfo": hash_file(RUNTIME / "web_ui_quality" / "release_info.py"),
        }),
        "checks": checks,
        "claimBoundary": "This acceptance covers release-closure trust semantics and public product contracts; it is not remote attestation or a production-browser guarantee.",
    }, ensure_ascii=False, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
