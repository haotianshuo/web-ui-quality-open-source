#!/usr/bin/env python3
"""Black-box acceptance test for an unpacked Web UI Quality distribution."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import uuid
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_VERSION = "4.3.0"
EXPECTED_KERNEL_VERSION = "4.2.3"
EXPECTED_KERNEL_BASE_VERSION = "4.0.0-rc.1"
EXPECTED_ARTIFACTS = {
    "product-experience-report.json",
    "journey-map.json",
    "experience-transformation-plan.json",
    "executive-brief.json",
    "implementation-handoff.json",
    "measurement-plan.json",
    "product-experience-brief/index.html",
    "consultation-validation-report.json",
    "consultation-validation-report.html",
    "artifact-manifest.json",
}
# The consultation manifest covers its contractual public artifacts.  The
# commercial workflow also emits these six deterministic technical-analysis
# handoff files beside that consultation bundle; they are part of the output
# directory and must be allow-listed explicitly rather than silently ignored.
EXPECTED_TECHNICAL_ANALYSIS_ARTIFACTS = {
    "technical-analysis/consultant-preview/index.html",
    "technical-analysis/experience-consultant.json",
    "technical-analysis/experience-diagnosis.json",
    "technical-analysis/experience-proof.json",
    "technical-analysis/modernization-preview/experience-diagnosis.json",
    "technical-analysis/modernization-preview/index.html",
}
EXPECTED_ARTIFACTS |= EXPECTED_TECHNICAL_ANALYSIS_ARTIFACTS
EXPECTED_MANIFEST_ARTIFACTS = EXPECTED_ARTIFACTS - EXPECTED_TECHNICAL_ANALYSIS_ARTIFACTS
EXPECTED_EVOLUTION_ARTIFACTS = {
    "evolution/evolution-ledger.json",
    "evolution/quality-target-board.json",
    "evolution/EVOLUTION_LEDGER.md",
    "evolution/QUALITY_TARGET_BOARD.md",
}
EXPECTED_EVOLUTION_WEIGHTS = {
    "uiInteraction": 30,
    "backendBusiness": 25,
    "dataIntegration": 15,
    "stabilityReliability": 10,
    "securityPrivacy": 10,
    "codeHealth": 10,
}

RUNTIME = ROOT / "runtime" / "python"
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from web_ui_quality.commercial_upgrade import run_commercial_upgrade  # noqa: E402
from web_ui_quality.release_info import EXPERIMENTAL_VERSION, KERNEL_BASE_VERSION, KERNEL_VERSION, PACKAGE_VERSION  # noqa: E402
from web_ui_quality.production_validation import browser_runtime_capability  # noqa: E402
from web_ui_quality.workflow_policy import bind_trusted_workflow_approval  # noqa: E402


def _runtime_command(*args: str, root: Path = ROOT) -> list[str]:
    return [
        sys.executable,
        "-B",
        str(root / "scripts" / "run_runtime.py"),
        *args,
    ]


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(command, cwd=ROOT, env=env, text=True, encoding="utf-8", errors="replace", capture_output=True)


def _json_output(completed: subprocess.CompletedProcess[str], label: str) -> dict[str, Any]:
    if completed.returncode != 0:
        raise RuntimeError(f"{label} failed ({completed.returncode}): {completed.stderr.strip()}")
    try:
        value = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError(f"{label} did not emit JSON: {error}") from error
    if not isinstance(value, dict):
        raise RuntimeError(f"{label} emitted a non-object result")
    return value


def _json_result(completed: subprocess.CompletedProcess[str], label: str) -> dict[str, Any]:
    try:
        value = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError(f"{label} did not emit JSON: {error}; stderr={completed.stderr.strip()}") from error
    if not isinstance(value, dict):
        raise RuntimeError(f"{label} emitted a non-object result")
    return value


def _tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def _verify_commercial_output(output: Path, *, expected_browser: bool) -> None:
    understanding_root = output / "system-understanding"
    for name in ("index.html", "system-understanding.json", "execution-brief.json", "test-plan.json", "scan-cache.json"):
        if not (understanding_root / name).is_file():
            raise RuntimeError(f"smart product discovery artifact is missing: {name}")
    understanding = json.loads((understanding_root / "system-understanding.json").read_text(encoding="utf-8"))
    if understanding.get("status") != "PRODUCT_UNDERSTANDING_READY":
        raise RuntimeError("commercial workflow did not pass the product-understanding gate")
    if understanding.get("questionPolicy", {}).get("maximumPerRound") != 3:
        raise RuntimeError("product discovery question policy is inconsistent")
    if len(understanding.get("questionPolicy", {}).get("visibleQuestionIds", [])) > 3:
        raise RuntimeError("product discovery workbench exposed more than three questions in one round")
    if set(understanding.get("evidenceClasses", [])) != {
        "SOURCE_CONFIRMED", "PAGE_OBSERVED", "AI_INFERRED", "USER_CONFIRMED",
        "PACKAGE_VERIFIED", "RUNTIME_OBSERVED", "UNKNOWN", "CONFLICTED",
        "NOT_VERIFIED", "SYNTHETIC_HYPOTHESIS",
    }:
        raise RuntimeError("product discovery evidence classes are incomplete")
    if understanding.get("questionPolicy", {}).get("mayProceedWithInference") is not False:
        raise RuntimeError("product discovery can still bypass unresolved business questions")
    if understanding.get("sourceProjectChanged") is not False or understanding.get("scanStats", {}).get("duplicateScanCount") != 0:
        raise RuntimeError("product discovery scan boundary is unsafe")
    execution_brief = json.loads((understanding_root / "execution-brief.json").read_text(encoding="utf-8"))
    test_plan = json.loads((understanding_root / "test-plan.json").read_text(encoding="utf-8"))
    if execution_brief.get("internalOnly") is not True or test_plan.get("safeExecution", {}).get("sourceScan") != "READ_ONLY":
        raise RuntimeError("product discovery brief or test-plan boundary is unsafe")
    if _verify_javascript(understanding_root / "index.html") not in {"PASS", "NOT_AVAILABLE"}:
        raise RuntimeError("product discovery workbench JavaScript is invalid")
    implementation = json.loads((output / "implementation/implementation-plan.json").read_text(encoding="utf-8"))
    change = json.loads((output / "implementation/change-manifest.json").read_text(encoding="utf-8"))
    rollback = json.loads((output / "implementation/rollback-manifest.json").read_text(encoding="utf-8"))
    if implementation.get("status") != "IMPLEMENTED_IN_ISOLATED_COPY" or not implementation.get("changedFiles"):
        raise RuntimeError("isolated implementation did not produce changed source")
    variants = json.loads((output / "implementation/variant-manifest.json").read_text(encoding="utf-8"))
    variant_items = variants.get("variants", [])
    if variants.get("status") not in {"DESIGN_CANDIDATES_READY", "THREE_DESIGN_CANDIDATES_READY"} or len(variant_items) != 3:
        raise RuntimeError("exactly three runnable design candidates were not produced")
    intelligence = output / "implementation/design-intelligence"
    for name in (
        "project-semantic-map.json",
        "project-design-ir.json",
        "project-design-candidates.json",
        "project-design-system-map.json",
    ):
        if not (intelligence / name).is_file():
            raise RuntimeError(f"main-path project design intelligence is missing: {name}")
    coverage = implementation.get("projectSemanticCoverage", {})
    if int(coverage.get("groundedRoleCount", 0)) < 3 or int(coverage.get("projectSelectorCount", 0)) < 3:
        raise RuntimeError("implementation is not grounded in enough project semantics")
    recipe_ids = {item.get("recipe", {}).get("id") for item in variant_items}
    known_recipes = {"operations-workspace", "guided-flow", "calm-focus"}
    if len(recipe_ids) != len(variant_items) or not recipe_ids.issubset(known_recipes):
        raise RuntimeError("design candidates do not expose distinct material composition recipes")
    for item in variants.get("variants", []):
        candidate = output / "implementation" / str(item.get("root"))
        if item.get("status") != "IMPLEMENTED" or not candidate.is_dir():
            raise RuntimeError("a design candidate source tree is missing")
        concept = item.get("designConcept")
        if not isinstance(concept, dict) or not concept.get("designDNA") or not concept.get("selectionReasons"):
            raise RuntimeError("a candidate is missing evidence-backed design intelligence")
    patch = output / "implementation/source-change.patch"
    if not patch.is_file() or patch.stat().st_size < 500 or change.get("patch", {}).get("sha256") != hashlib.sha256(patch.read_bytes()).hexdigest():
        raise RuntimeError("source patch is missing or its integrity does not match")
    for record in change.get("changes", []):
        relative = record.get("path")
        if not isinstance(relative, str) or Path(relative).is_absolute() or ".." in Path(relative).parts:
            raise RuntimeError("change manifest contains an unsafe path")
        after_file = output / "implementation/generated-preview/after" / relative
        before_file = output / "implementation/generated-preview/before" / relative
        if not after_file.is_file():
            raise RuntimeError(f"changed After source is missing: {relative}")
        if hashlib.sha256(after_file.read_bytes()).hexdigest() != record.get("afterSha256") or after_file.stat().st_size != record.get("bytes"):
            raise RuntimeError(f"changed After source integrity mismatch: {relative}")
        expected_before = hashlib.sha256(before_file.read_bytes()).hexdigest() if before_file.is_file() else None
        if record.get("beforeSha256") != expected_before:
            raise RuntimeError(f"changed Before source integrity mismatch: {relative}")
    if rollback.get("originalProjectChanged") is not False:
        raise RuntimeError("rollback contract does not preserve original source")
    before = output / "implementation/generated-preview/before/index.html"
    after = output / "implementation/generated-preview/after/index.html"
    if not before.is_file() or not after.is_file() or before.read_bytes() == after.read_bytes():
        raise RuntimeError("runnable Before/After source evidence is missing")
    outcome = json.loads((output / "outcome/outcome-measurement-report.json").read_text(encoding="utf-8"))
    if outcome.get("status") != "PASS" or outcome.get("decision") != "IMPROVED" or outcome.get("causalClaim") is not False:
        raise RuntimeError("outcome measurement contract did not pass honestly")
    if expected_browser:
        design = json.loads((output / "design-gallery/design-review.json").read_text(encoding="utf-8"))
        design_variants = design.get("variants", [])
        if design.get("status") != "DESIGN_GALLERY_PASS" or len(design_variants) != 3:
            raise RuntimeError("design gallery did not pass")
        if any(item.get("browserStatus") != "PASS" for item in design_variants):
            raise RuntimeError("every design candidate must have a warning-free Browser PASS")
        expected_pairs = len(design_variants) * (len(design_variants) - 1) // 2
        if len(design.get("pairwiseDistinctness", [])) != expected_pairs or any(item.get("status") != "MATERIALLY_DISTINCT" for item in design.get("pairwiseDistinctness", [])):
            raise RuntimeError("design candidates are not materially distinct")
        if not (output / "design-gallery/index.html").is_file():
            raise RuntimeError("interactive design gallery is missing")
        gallery_html = (output / "design-gallery/index.html").read_text(encoding="utf-8")
        if design.get("productDiscovery", {}).get("status") != "PRODUCT_UNDERSTANDING_READY" or "系统理解已完成" not in gallery_html:
            raise RuntimeError("design gallery is missing its product-understanding handoff")
        if "design-decision.json" not in gallery_html or "finalize-design" not in gallery_html:
            raise RuntimeError("design decision export/finalization workbench is missing")
        for variant in design_variants:
            report_ref = variant.get("browserReport")
            if not isinstance(report_ref, str):
                raise RuntimeError("candidate Browser report reference is missing")
            candidate_browser = json.loads((output / report_ref).read_text(encoding="utf-8"))
            journey_viewports = {item.get("viewport", {}).get("id") for item in candidate_browser.get("journey", [])}
            if journey_viewports != {"desktop", "tablet", "mobile"}:
                raise RuntimeError("candidate critical journey did not run at all three viewports")
            after_records = [item for item in candidate_browser.get("records", []) if item.get("label") == "after"]
            keyboard_viewports = {
                item.get("viewport", {}).get("id")
                for item in after_records
                if item.get("metrics", {}).get("keyboard", {}).get("status") == "PASS"
            }
            if keyboard_viewports != {"desktop", "tablet", "mobile"}:
                raise RuntimeError("candidate keyboard focus traversal did not pass at all three viewports")
        browser = json.loads((output / "validation/production-validation-report.json").read_text(encoding="utf-8"))
        if browser.get("status") != "PASS" or not browser.get("browserVersion") or browser.get("warnings"):
            raise RuntimeError("Browser acceptance is not a clean PASS")
        if len(browser.get("journey", [])) < 5 or any(item.get("status") != "PASS" for item in browser.get("journey", [])):
            raise RuntimeError("critical journey evidence is incomplete")
        if len(browser.get("visualDiff", [])) != 3 or any(item.get("status") != "COMPUTED" or float(item.get("changedPixelRatio", 0)) <= 0.001 for item in browser.get("visualDiff", [])):
            raise RuntimeError("three-viewport visual diff evidence is incomplete")
        for group in ("before", "after", "diff"):
            for viewport in ("desktop", "tablet", "mobile"):
                if not (output / f"validation/screenshots/{group}/{viewport}.png").is_file():
                    raise RuntimeError(f"missing {group} {viewport} screenshot")
    else:
        design = json.loads((output / "design-gallery/design-review.json").read_text(encoding="utf-8"))
        gallery_html = (output / "design-gallery/index.html").read_text(encoding="utf-8")
        if design.get("status") != "DESIGN_GALLERY_NOT_VERIFIED" or "<img" in gallery_html:
            raise RuntimeError("Browser-unavailable gallery must remain complete without broken images")
        if "design-decision.json" not in gallery_html or "finalize-design" not in gallery_html:
            raise RuntimeError("Browser-unavailable gallery does not support a user decision")
        if design.get("productDiscovery", {}).get("status") != "PRODUCT_UNDERSTANDING_READY" or "系统理解已完成" not in gallery_html:
            raise RuntimeError("Browser-unavailable gallery is missing its product-understanding handoff")


def _verify_manifest(output: Path) -> None:
    manifest = json.loads((output / "artifact-manifest.json").read_text(encoding="utf-8"))
    if manifest.get("validationStatus") != "PASS":
        raise RuntimeError("artifact manifest validationStatus is not PASS")
    items = manifest.get("artifacts")
    if not isinstance(items, list) or not items:
        raise RuntimeError("artifact manifest has no structured artifact rows")
    listed: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            raise RuntimeError("artifact manifest contains a non-object row")
        relative = item.get("path")
        if not isinstance(relative, str) or Path(relative).is_absolute() or ".." in Path(relative).parts:
            raise RuntimeError("artifact manifest contains an unsafe path")
        if relative in listed:
            raise RuntimeError(f"artifact manifest contains a duplicate path: {relative}")
        listed.append(relative)
        path = output / relative
        if not path.is_file():
            raise RuntimeError(f"artifact listed in manifest is missing: {relative}")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != item.get("sha256") or path.stat().st_size != item.get("bytes"):
            raise RuntimeError(f"artifact integrity mismatch: {relative}")
    expected_listed = EXPECTED_MANIFEST_ARTIFACTS - {"artifact-manifest.json"}
    if set(listed) != expected_listed:
        raise RuntimeError("artifact manifest contains missing or unknown listed artifacts")
    actual = {
        path.relative_to(output).as_posix()
        for path in output.rglob("*")
        if path.is_file()
    }
    if actual != EXPECTED_ARTIFACTS:
        unknown = sorted(actual - EXPECTED_ARTIFACTS)
        missing = sorted(EXPECTED_ARTIFACTS - actual)
        raise RuntimeError(f"commercial distribution contains unknown or missing files: unknown={unknown}, missing={missing}")


def _verify_javascript(page: Path) -> str:
    node = shutil.which("node")
    if node is None:
        return "NOT_AVAILABLE"
    source = page.read_text(encoding="utf-8")
    scripts: list[str] = []
    remainder = source
    while "<script>" in remainder:
        remainder = remainder.split("<script>", 1)[1]
        script, remainder = remainder.split("</script>", 1)
        scripts.append(script)
    if not scripts:
        raise RuntimeError(f"no inline JavaScript found in {page}")
    with tempfile.TemporaryDirectory(prefix="wuq-js-") as temp:
        script_path = Path(temp) / "generated.js"
        script_path.write_text("\n".join(scripts), encoding="utf-8")
        completed = subprocess.run([node, "--check", str(script_path)], text=True, encoding="utf-8", errors="replace", capture_output=True)
        if completed.returncode:
            raise RuntimeError(f"generated JavaScript is invalid: {completed.stderr.strip()}")
    return "PASS"


def _manifest_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tree_digest_from_rows(rows: list[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for row in sorted(rows, key=lambda item: str(item.get("path") or "").encode("utf-8")):
        digest.update(str(row.get("path") or "").replace("\\", "/").encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(row.get("sha256") or "").encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _verify_composite_release(root: Path) -> None:
    composite_path = root / "COMPOSITE-RELEASE-MANIFEST.json"
    release_path = root / "RELEASE-MANIFEST.json"
    for path in (composite_path, release_path):
        if not path.is_file(): raise RuntimeError(f"composite distribution file missing: {path.name}")
    composite=json.loads(composite_path.read_text(encoding="utf-8")); release=json.loads(release_path.read_text(encoding="utf-8"))
    if release.get("packageVersion") != EXPECTED_VERSION or release.get("kernelVersion") != EXPECTED_KERNEL_VERSION or release.get("kernelBaseVersion") != EXPECTED_KERNEL_BASE_VERSION:
        raise RuntimeError("release identity mismatch")
    if composite.get("packageVersion") != EXPECTED_VERSION or composite.get("kernelVersion") != EXPECTED_KERNEL_VERSION or composite.get("kernelBaseVersion") != EXPECTED_KERNEL_BASE_VERSION:
        raise RuntimeError("composite release identity mismatch")
    rows=list(release.get("files") or [])
    for row in rows:
        rel=str(row.get("path") or ""); path=root/rel
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=row.get("sha256") or path.stat().st_size!=row.get("bytes"):
            raise RuntimeError(f"package tree integrity mismatch: {rel}")
    digest=_tree_digest_from_rows(rows)
    if digest != release.get("packageTreeDigest") or digest != composite.get("packageTreeDigest"):
        raise RuntimeError("package tree digest mismatch")
    listed = {str(row.get("path") or "") for row in rows}
    missing = sorted(EXPECTED_EVOLUTION_ARTIFACTS - listed)
    if missing:
        raise RuntimeError("release manifest omits required evolution artifacts: " + ", ".join(missing))


def _verify_evolution_contract(root: Path) -> None:
    """Verify the shipped planning contract is present and fail-closed."""
    paths = {name: root / name for name in EXPECTED_EVOLUTION_ARTIFACTS}
    missing = sorted(name for name, path in paths.items() if not path.is_file())
    if missing:
        raise RuntimeError("required evolution artifact is missing: " + ", ".join(missing))
    ledger = json.loads(paths["evolution/evolution-ledger.json"].read_text(encoding="utf-8"))
    board = json.loads(paths["evolution/quality-target-board.json"].read_text(encoding="utf-8"))
    if ledger.get("product") != "web-ui-quality" or board.get("product") != "web-ui-quality":
        raise RuntimeError("evolution contract product identity is inconsistent")
    if ledger.get("qualityWeights") != EXPECTED_EVOLUTION_WEIGHTS or board.get("weights") != EXPECTED_EVOLUTION_WEIGHTS:
        raise RuntimeError("evolution quality weights are inconsistent")
    if ledger.get("qualityWeights") != board.get("weights") or sum(EXPECTED_EVOLUTION_WEIGHTS.values()) != 100:
        raise RuntimeError("evolution quality weights do not form the fixed 100-point contract")
    entries = ledger.get("entries")
    if not isinstance(entries, list) or not entries:
        raise RuntimeError("evolution ledger has no version entries")
    latest = entries[-1]
    if latest.get("version") != EXPERIMENTAL_VERSION:
        raise RuntimeError("evolution latest version does not match runtime experimental identity")
    if latest.get("promotionAllowed") is not False or latest.get("promotionDecision") != "HOLD":
        raise RuntimeError("evolution latest entry is not fail-closed")
    if board.get("currentVersion") != EXPERIMENTAL_VERSION or board.get("track") != "SHADOW_ADVISORY_ONLY":
        raise RuntimeError("evolution board identity or authority boundary is inconsistent")


def _resolve_browser_for_gate(browser_executable: Path | None) -> tuple[bool, Path | None, dict[str, Any]]:
    """Use the same auto-discovery contract as the production validator."""
    capability = browser_runtime_capability(browser_executable)
    available = bool(capability.get("available"))
    effective = Path(str(capability["executable"])) if available and capability.get("executable") else browser_executable
    return available, effective, capability


def verify(browser_executable: Path | None = None, *, release_run_id: str | None = None) -> dict[str, Any]:
    checks: list[dict[str, str]] = []
    release_run_id = str(release_run_id or os.environ.get("WUQ_RELEASE_RUN_ID") or f"wuq-4.3.0-distribution-{uuid.uuid4().hex[:16]}").strip()
    # The workflow auto-discovers Chrome/Edge/Chromium when no explicit path is
    # supplied.  Gate semantics must follow that same capability decision;
    # checking only ``browser_executable`` incorrectly labels an auto-discovered
    # live run as Browser-unavailable.
    browser_available, effective_browser, browser_capability = _resolve_browser_for_gate(browser_executable)

    manifest = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    if ROOT.name != "web-ui-quality" or manifest.get("name") != ROOT.name:
        raise RuntimeError("plugin root and manifest name do not match")
    if manifest.get("version") != EXPECTED_VERSION or f'version = "{EXPECTED_VERSION}"' not in pyproject:
        raise RuntimeError("distribution package version identity is inconsistent")
    if PACKAGE_VERSION != EXPECTED_VERSION or KERNEL_VERSION != EXPECTED_KERNEL_VERSION or KERNEL_BASE_VERSION != EXPECTED_KERNEL_BASE_VERSION:
        raise RuntimeError("runtime package/kernel identity is inconsistent")
    _verify_composite_release(ROOT)
    _verify_evolution_contract(ROOT)
    checks.append({"id": "DIST-001", "status": "PASS", "detail": f"package {EXPECTED_VERSION} / kernel {EXPECTED_KERNEL_VERSION} / base {EXPECTED_KERNEL_BASE_VERSION} / composite manifest / evolution contract"})

    doctor = _json_output(_run(_runtime_command("doctor", "--compact")), "doctor")
    if doctor.get("runtime") != "PASS" or doctor.get("schemaStatus") != "PASS":
        raise RuntimeError("runtime doctor did not pass")
    package_identity = doctor.get("packageIdentity", {})
    if package_identity.get("packageVersion") != EXPECTED_VERSION or package_identity.get("kernelVersion") != EXPECTED_KERNEL_VERSION or package_identity.get("kernelBaseVersion") != EXPECTED_KERNEL_BASE_VERSION:
        raise RuntimeError("runtime doctor package identity does not match the distribution")
    checks.append({"id": "DIST-002", "status": "PASS", "detail": "runtime and schemas"})

    kernel_public = _json_output(_run([sys.executable, '-B', str(ROOT / 'scripts/kernel_public_acceptance.py')]), 'kernel public acceptance')
    package_public = _json_output(_run([sys.executable, '-B', str(ROOT / 'scripts/package_public_acceptance.py')]), 'package public acceptance')
    if kernel_public.get('status') != 'PASS' or len(kernel_public.get('checks', [])) != 10:
        raise RuntimeError('kernel public distribution acceptance did not pass')
    if package_public.get('status') != 'PASS':
        raise RuntimeError('package public distribution acceptance did not pass')
    checks.append({'id':'DIST-003','status':'PASS','detail':'explicit package public acceptance + frozen-kernel public compatibility acceptance'})

    browser_report_digest = None
    with tempfile.TemporaryDirectory(prefix="wuq-acceptance-") as temp:
        temp_root = Path(temp)
        output = temp_root / "consultation-output"
        consultation = _json_output(
            _run(_runtime_command(
                "product-consult",
                str(ROOT / "examples" / "commercial-demo"),
                str(output),
                "--business-context",
                str(ROOT / "examples" / "commercial-demo" / "business-context.json"),
                "--product-name",
                "Northstar Customer Operations",
                "--product-type",
                "crm",
                "--compact",
            )),
            "commercial demo consultation",
        )
        if consultation.get("status") != "PRODUCT_EXPERIENCE_READY" or consultation.get("consultationValidation") != "PASS":
            raise RuntimeError("commercial demo consultation is not ready")
        if consultation.get("sourceWriteAuthorized") is not False:
            raise RuntimeError("consultation unexpectedly granted source write authority")
        missing = sorted(relative for relative in EXPECTED_ARTIFACTS if not (output / relative).is_file())
        if missing:
            raise RuntimeError("commercial demo artifacts missing: " + ", ".join(missing))
        validation = json.loads((output / "consultation-validation-report.json").read_text(encoding="utf-8"))
        if validation.get("status") != "PASS" or validation.get("readiness", {}).get("commercialGA") != "NOT_ESTABLISHED":
            raise RuntimeError("consultation validation has incorrect readiness semantics")
        _verify_manifest(output)
        js_status = _verify_javascript(output / "product-experience-brief" / "index.html")
        checks.append({"id": "DIST-004", "status": "PASS", "detail": "real CRM consultation and 10 artifacts"})
        checks.append({"id": "DIST-005", "status": js_status, "detail": "generated brief JavaScript"})

        marketplace = temp_root / ".agents" / "plugins" / "marketplace.json"
        install = _json_output(
            _run([
                sys.executable,
                "-B",
                str(ROOT / "scripts" / "install_plugin.py"),
                "--source",
                str(ROOT),
                "--marketplace",
                str(marketplace),
            ]),
            "portable installer",
        )
        installed_root = Path(install["plugin"])
        if install.get("version") != EXPECTED_VERSION or not installed_root.is_dir():
            raise RuntimeError("portable installer returned an inconsistent target")
        installed_doctor = _json_output(_run(_runtime_command("doctor", "--compact", root=installed_root)), "installed doctor")
        if installed_doctor.get("schemaStatus") != "PASS":
            raise RuntimeError("installed runtime doctor did not pass")
        installed_kernel_public = _json_output(_run([sys.executable, '-B', str(installed_root / 'scripts/kernel_public_acceptance.py')]), 'installed kernel public acceptance')
        installed_package_public = _json_output(_run([sys.executable, '-B', str(installed_root / 'scripts/package_public_acceptance.py')]), 'installed package public acceptance')
        if installed_kernel_public.get('status') != 'PASS' or installed_package_public.get('status') != 'PASS':
            raise RuntimeError('installed package/kernel public acceptance did not pass')
        checks.append({"id": "DIST-006", "status": "PASS", "detail": "isolated marketplace install, doctor, and public acceptance"})

        source_before = _tree_digest(ROOT / "examples/commercial-demo")
        commercial_output = temp_root / "commercial-output"
        confirmation = temp_root / "full-approval.json"
        confirmation.write_text(json.dumps({
            "schemaVersion": "2",
            "action": "confirm-understanding",
            "answers": {},
            "source": "system-understanding-response",
            "requiresCurrentConversationApproval": True,
            "approvalReceipt": None,
        }, ensure_ascii=False), encoding="utf-8")
        receipt = temp_root / "full-approval-receipt.json"
        receipt.write_text(json.dumps({
            "origin": "current-conversation-user",
            "actor": "user",
            "statement": "我已核对系统理解，并明确要求生成隔离设计候选。",
            "scope": "FULL",
        }, ensure_ascii=False), encoding="utf-8")
        packet = json.loads(confirmation.read_text(encoding="utf-8"))
        trusted = bind_trusted_workflow_approval(
            packet,
            evidence_ref="current-conversation:distribution-full-upgrade",
            evidence_resolver=lambda reference: reference == "current-conversation:distribution-full-upgrade",
            scope="FULL",
            requested_mode="full",
            statement="我已核对系统理解，并明确要求生成隔离设计候选。",
        )
        business_context = json.loads((ROOT / "examples/commercial-demo/business-context.json").read_text(encoding="utf-8"))
        commercial = run_commercial_upgrade(
            ROOT / "examples/commercial-demo",
            commercial_output,
            business_context=business_context,
            product_name="Northstar Customer Operations",
            product_type="crm",
            baseline_events=ROOT / "examples/commercial-demo/baseline-events.csv",
            after_events=ROOT / "examples/commercial-demo/after-events.csv",
            mode="full",
            product_confirmation=packet,
            approval_receipt=trusted,
            browser_executable=effective_browser,
            design_ui=True,
        )
        if browser_available:
            if commercial.get("status") != "COMMERCIAL_WORKFLOW_PASS":
                raise RuntimeError("live commercial workflow did not pass")
            _verify_commercial_output(commercial_output, expected_browser=True)
            # Capture the report digest while the temporary acceptance output
            # still exists.  Reading it after the context exits silently
            # downgraded a real live run to NOT_VERIFIED.
            browser_report_digest = _manifest_digest(commercial_output / "validation" / "production-validation-report.json")
            checks.append({"id": "DIST-007", "status": "PASS", "detail": "one-command smart product discovery, Design IR 2.0, exactly three candidates, decision workbench, and live Chromium workflow"})
        else:
            if commercial.get("status") != "COMMERCIAL_WORKFLOW_NOT_VERIFIED":
                raise RuntimeError("Browser-unavailable run did not preserve explicit non-pass semantics")
            _verify_commercial_output(commercial_output, expected_browser=False)
            checks.append({"id": "DIST-007", "status": "PASS", "detail": "one-command smart product discovery, project-grounded design work, patch, rollback, and explicit Browser boundary"})
        if _tree_digest(ROOT / "examples/commercial-demo") != source_before:
            raise RuntimeError("commercial workflow changed the target project")

        reference = ROOT / "references/history"
        if reference.exists():
            raise RuntimeError("historical regression evidence must not ship in the user-facing distribution")
        checks.append({"id": "DIST-008", "status": "PASS", "detail": "historical regression evidence is excluded from the user-facing distribution"})

    dist007 = next((item for item in checks if item.get("id") == "DIST-007"), None)
    dist007_status = str((dist007 or {}).get("status") or "NOT_VERIFIED")
    node_executed = bool(browser_available and dist007 is not None)
    if not node_executed:
        node_status = "NOT_VERIFIED"
        node_reason = "Node Browser workflow was not executed with a usable Node Playwright capability."
    elif dist007_status == "PASS":
        node_status = "PASS"
        node_reason = None
    else:
        node_status = "FAIL"
        node_reason = "Node Browser workflow executed but DIST-007 did not pass."
    browser_command = [sys.executable, "-B", "scripts/verify_distribution.py", "--compact"]
    browser_command_digest = hashlib.sha256(json.dumps(browser_command, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()
    browser_execution_status = "PASS" if node_executed and node_status == "PASS" and browser_report_digest else "NOT_VERIFIED"
    browser_receipt_payload = {
        "schemaVersion": "1",
        "status": browser_execution_status,
        "releaseRunId": release_run_id,
        "reportSha256": browser_report_digest,
        "commandDigest": browser_command_digest,
        "source": "verify_distribution.DIST-007",
    }
    browser_receipt_digest = hashlib.sha256(json.dumps(browser_receipt_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    execution_record = {
        "status": browser_execution_status,
        "executed": node_executed and node_status == "PASS",
        "commandDigest": browser_command_digest,
        "reportSha256": browser_report_digest,
        "reportStatus": "PASS" if browser_report_digest else "NOT_VERIFIED",
        "browserExecutable": str(effective_browser) if effective_browser else None,
        "source": "verify_distribution.DIST-007",
    }
    if node_executed and node_status == "PASS":
        node_reason_code = "CAPABILITY_AVAILABLE"
    elif browser_capability.get("reasonCode"):
        node_reason_code = str(browser_capability["reasonCode"])
    elif not browser_capability.get("moduleAvailable"):
        node_reason_code = "NODE_PLAYWRIGHT_MODULE_MISSING"
    elif not browser_available:
        node_reason_code = "NODE_BROWSER_EXECUTABLE_MISSING"
    else:
        node_reason_code = "DIST007_EXECUTION_FAILED"
    browser_qualification = {
        "nodePlaywright": {
            "runtime": "node-playwright",
            "moduleAvailable": bool(browser_capability.get("moduleAvailable")),
            "browserExecutableAvailable": bool(browser_capability.get("executable")) and browser_available,
            "executed": node_executed,
            "status": node_status,
            "reasonCode": node_reason_code,
            "reason": node_reason,
            "command": browser_command,
            "executionBranch": "LIVE_NODE_PLAYWRIGHT" if node_executed and node_status == "PASS" else "NOT_VERIFIED",
            "receiptSha256": browser_receipt_digest,
            "executionRecord": execution_record,
        },
        "dist007": {
            "runtime": "distribution-workflow",
            "moduleAvailable": bool(browser_capability.get("moduleAvailable")),
            "browserExecutableAvailable": bool(browser_capability.get("executable")) and browser_available,
            "executed": bool(dist007 is not None),
            "status": dist007_status,
            "reasonCode": "CAPABILITY_AVAILABLE" if browser_available and dist007_status == "PASS" else node_reason_code,
            "reason": None if browser_available else "DIST-007 used its explicit Browser-unavailable branch.",
            "browserBacked": bool(browser_available and dist007_status == "PASS"),
            "executionBranch": "LIVE_NODE_PLAYWRIGHT" if browser_available else "BROWSER_UNAVAILABLE_EXPLICIT_BOUNDARY",
            "command": browser_command,
            "receiptSha256": browser_receipt_digest,
            "executionRecord": execution_record,
        },
    }
    return {
        "status": "PASS",
        "version": EXPECTED_VERSION,
        "releaseRunId": release_run_id,
        "scope": "COMMERCIAL_RELEASE_WORKFLOW",
        "checks": checks,
        "browserQualification": browser_qualification,
        "environmentBoundaries": ["patch integration", "authenticated production mutation", "causal business claim", "distributor legal terms"],
    }


def main() -> int:
    from web_ui_quality.release_info import configure_stdout

    configure_stdout()
    parser = argparse.ArgumentParser(description="Verify an unpacked Web UI Quality distribution")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--browser-executable", type=Path)
    parser.add_argument("--release-run-id")
    args = parser.parse_args()
    try:
        browser = args.browser_executable
        if browser is None:
            configured = os.environ.get("WUQ_BROWSER_EXECUTABLE") or os.environ.get("WUQ_TEST_BROWSER_EXECUTABLE")
            browser = Path(configured).expanduser().resolve() if configured else None
        result = verify(browser, release_run_id=args.release_run_id)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
        result = {
            "status": "FAIL",
            "releaseRunId": str(args.release_run_id or os.environ.get("WUQ_RELEASE_RUN_ID") or "").strip() or None,
            "error": str(error),
            "browserQualification": {
                "nodePlaywright": {
                    "runtime": "node-playwright",
                    "moduleAvailable": False,
                    "browserExecutableAvailable": False,
                    "executed": False,
                    "status": "NOT_VERIFIED",
                    "reason": "Distribution verification failed before Node Browser qualification completed.",
                },
                "dist007": {
                    "runtime": "distribution-workflow",
                    "moduleAvailable": False,
                    "browserExecutableAvailable": False,
                    "executed": False,
                    "status": "NOT_VERIFIED",
                    "reason": "Distribution verification failed before DIST-007 completed.",
                    "browserBacked": False,
                    "executionBranch": "NOT_RUN",
                },
            },
        }
        print(json.dumps(result, ensure_ascii=False, separators=(",", ":") if args.compact else None, indent=None if args.compact else 2))
        return 1
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":") if args.compact else None, indent=None if args.compact else 2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
