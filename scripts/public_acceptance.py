#!/usr/bin/env python3
"""4.2.3 trust-kernel public compatibility acceptance.

Use package_public_acceptance.py for the outward package identity. This file is
retained for frozen 4.0 evidence compatibility and intentionally reports the
4.0 kernel evidence version.
"""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
from typing import Callable
from unittest import mock
from contextlib import redirect_stdout


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime" / "python"
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from web_ui_quality.design_gallery import build_design_gallery  # noqa: E402
from web_ui_quality.design_intelligence import generate_design_candidates  # noqa: E402
from web_ui_quality.experience_journey_intelligence import infer_product_type  # noqa: E402
from web_ui_quality.implementation_agent import (  # noqa: E402
    execute_isolated_transformation,
    finalize_design_selection,
)
from web_ui_quality.project_semantics import build_project_semantic_map  # noqa: E402
from web_ui_quality.project_source_ir import build_project_design_ir  # noqa: E402
from web_ui_quality.release_info import KERNEL_BASE_VERSION, KERNEL_VERSION, PACKAGE_VERSION, RELEASE_STAGE  # noqa: E402
from web_ui_quality.smart_product_discovery import (  # noqa: E402
    apply_cached_product_confirmation,
    build_product_discovery,
    export_product_discovery,
    load_cached_product_discovery,
)
from web_ui_quality.commercial_upgrade import run_commercial_upgrade  # noqa: E402
from web_ui_quality.workflow_policy import (  # noqa: E402
    EVIDENCE_CLASSES,
    bind_trusted_workflow_approval,
)
from web_ui_quality.__main__ import main as cli_main  # noqa: E402
from web_ui_quality.playwright_adapter import _context_options  # noqa: E402
from web_ui_quality.quick_ui import QUICK_UI_VIEWPORTS, summarize_top_ui_issues  # noqa: E402


EXPECTED_VERSION = "4.2.3"
EXPECTED_PACKAGE_VERSION = "4.3.0"


def _tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def _identity() -> str:
    manifest = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    schema = json.loads((ROOT / "schemas" / "product-experience-report.schema.json").read_text(encoding="utf-8"))
    if KERNEL_VERSION != EXPECTED_VERSION or KERNEL_BASE_VERSION != "4.0.0-rc.1":
        raise RuntimeError("frozen kernel version identity differs")
    if PACKAGE_VERSION != EXPECTED_PACKAGE_VERSION or manifest.get("version") != EXPECTED_PACKAGE_VERSION:
        raise RuntimeError("experimental package and plugin version identities differ")
    version_contract = schema.get("properties", {}).get("generator", {}).get("properties", {}).get("packageVersion", {})
    if version_contract.get("const") != EXPECTED_PACKAGE_VERSION:
        raise RuntimeError("public schema version identity differs")
    if schema.get("properties", {}).get("generator", {}).get("properties", {}).get("workflowContractVersion", {}).get("const") != "5":
        raise RuntimeError("workflow contract version identity differs")
    return f"package {EXPECTED_PACKAGE_VERSION} / kernel {EXPECTED_VERSION}"


def _classification() -> str:
    if infer_product_type(intent="web-experience", page_type="landing-page") != "landing":
        raise RuntimeError("source-grounded landing classification was overridden by generic intent")
    if infer_product_type(product_type="commerce", intent="web-experience", page_type="landing-page") != "commerce":
        raise RuntimeError("explicit product type did not keep precedence")
    return "explicit type, page evidence, and generic intent precedence"


def _quick_ui_contract() -> str:
    if QUICK_UI_VIEWPORTS != ((390, 844), (768, 1024), (1440, 900)):
        raise RuntimeError("quick-ui does not default to mobile, small desktop, and desktop")
    context = _context_options(
        viewport=(390, 844), locale="zh-CN", theme="light", storage_state=None,
        extra_http_headers=None, ignore_https_errors=False,
    )
    if context.get("is_mobile") is not True or context.get("has_touch") is not True:
        raise RuntimeError("quick-ui mobile context is not touch enabled")
    records = [{
        "status": "PASS_WITH_WARNINGS",
        "viewport": {"width": 390, "height": 844},
        "renderedQuality": {"findings": [{
            "id": "RENDER-INCONSISTENT-CONTROL-HEIGHT", "severity": "P2",
            "title": "同组控件高度混用", "samples": [{"selector": ".toolbar"}],
        }]},
        "experienceGeometry": {"viewports": [{
            "fixedOcclusions": [{"overlay": ".dock", "target": "button"}],
            "overlaps": [], "dialogs": [], "navigation": [], "alignmentDeviationPx": 0,
        }]},
    }]
    top = summarize_top_ui_issues(records)
    if not top or top[0].get("id") != "UI-FIXED-OCCLUSION" or len(top) > 3:
        raise RuntimeError("quick-ui Top 3 ranking is inconsistent")
    runner = (RUNTIME / "web_ui_quality" / "browser_runner.cjs").read_text(encoding="utf-8")
    required = ("createSecureContext", "launchSecurity", "WEBSOCKET_BLOCKED", "SIDE_EFFECT_BLOCKED", "credentialHeadersByOrigin")
    if ".first()" in runner or "getByTestId" not in runner or not all(token in runner for token in required):
        raise RuntimeError("Browser locator or 4.2 secure-context contract regressed")
    if 'const args = ["--disable-dev-shm-usage"]' not in runner:
        raise RuntimeError("Chromium safe-default launch contract regressed")
    return "three-viewport, strict locator, sandbox-safe launch, shared secure context, and Top 3 contract"


def _project_grounding() -> str:
    with tempfile.TemporaryDirectory(prefix="wuq-public-semantics-") as temp:
        project = Path(temp) / "project"
        project.mkdir()
        (project / "index.html").write_text(
            '<!doctype html><html><head></head><body><div class="product-shell">'
            '<header class="topbar"><a href="#">Accounts</a><button class="primary" id="newAccount">New account</button></header><main class="canvas">'
            '<section id="accounts" class="result-list"><article class="account">Northstar</article></section>'
            '<aside class="record-inspector"><dl class="facts"><div class="fact">Details</div></dl></aside></main></div></body></html>',
            encoding="utf-8",
        )
        (project / "theme.css").write_text(
            ":root{--brand:#7357d8;--surface:#fff;--ink:#172033}.canvas{display:grid}",
            encoding="utf-8",
        )
        generated = project / "reference-output"
        generated.mkdir()
        (generated / "index.html").write_text(
            '<div class="fake-dashboard-shell fake-sidebar"></div>',
            encoding="utf-8",
        )
        semantics = build_project_semantic_map(project)
        if int(semantics.get("coverage", {}).get("groundedRoleCount", 0)) < 4:
            raise RuntimeError("project semantic coverage is too shallow")
        if ".fake-dashboard-shell" in semantics.get("roles", {}).get("shell", {}).get("projectSelectors", []):
            raise RuntimeError("generated reference output polluted project semantics")
        if "#newAccount" in semantics.get("roles", {}).get("item", {}).get("projectSelectors", []):
            raise RuntimeError("an action control was misclassified as a collection item")
        if "#accounts" not in semantics.get("roles", {}).get("collection", {}).get("projectSelectors", []):
            raise RuntimeError("a project collection container was not classified")
        if semantics.get("scopeHygiene", {}).get("excludedDirectoriesByName", {}).get("reference-output") != 1:
            raise RuntimeError("generated reference output was not pruned from source scope")
        design_ir = build_project_design_ir(project)
        candidates = generate_design_candidates({"product": {"type": "saas"}}, design_ir=design_ir, count=3)
        result = execute_isolated_transformation(
            project,
            Path(temp) / "implementation",
            {"product": {"type": "saas"}},
            design_context={
                "semanticMap": semantics,
                "designIr": design_ir,
                "designCandidates": candidates,
                "designSystem": semantics["designSystem"],
            },
        )
        if result.get("status") != "IMPLEMENTED_IN_ISOLATED_COPY" or len(result.get("variants", [])) != 3:
            raise RuntimeError("three project-grounded candidates were not generated")
        css = (Path(temp) / "implementation/generated-preview/variants/direction-1/wuq-experience.css").read_text(encoding="utf-8")
        for selector in (".product-shell", ".topbar", ".canvas", ".record-inspector"):
            if selector not in css:
                raise RuntimeError(f"candidate did not consume project selector {selector}")
        if not (Path(temp) / "implementation/design-intelligence/project-design-ir.json").is_file():
            raise RuntimeError("project Design IR is missing from implementation evidence")
    return "generic selectors, project tokens, Design IR, and three candidates"


def _next_pages() -> str:
    with tempfile.TemporaryDirectory(prefix="wuq-public-next-") as temp:
        project = Path(temp) / "project"
        (project / "pages").mkdir(parents=True)
        (project / "package.json").write_text(
            json.dumps({"dependencies": {"next": "15.0.0", "react": "19.0.0"}}),
            encoding="utf-8",
        )
        original = (
            "'use client';\n"
            "import type { AppProps } from 'next/app';\n"
            "export default function App({Component,pageProps}:AppProps){return <Component {...pageProps}/>};\n"
        )
        (project / "pages/_app.tsx").write_text(original, encoding="utf-8")
        before = _tree_digest(project)
        result = execute_isolated_transformation(project, Path(temp) / "implementation", {"product": {"type": "saas"}})
        if _tree_digest(project) != before:
            raise RuntimeError("Next.js source project was modified")
        if any(item.get("mode") != "NEXT_PAGES_ROUTER_SOURCE_NATIVE_STYLE" for item in result.get("variants", [])):
            raise RuntimeError("Next.js Pages Router was not mapped to its owning entry")
        candidate = Path(temp) / "implementation/generated-preview/variants/direction-1/pages/_app.tsx"
        source = candidate.read_text(encoding="utf-8")
        if not source.startswith("'use client';") or source.index("wuq-experience/experience-layer.css") < source.index("'use client';"):
            raise RuntimeError("directive-safe import insertion failed")
    return "Next.js Pages Router ownership and directive-safe imports"


def _fallback_and_decision() -> str:
    with tempfile.TemporaryDirectory(prefix="wuq-public-gallery-") as temp:
        project = Path(temp) / "project"
        project.mkdir()
        (project / "index.html").write_text(
            "<!doctype html><html><head></head><body><main><h1>Product</h1><ul><li>One</li></ul></main></body></html>",
            encoding="utf-8",
        )
        upgrade = Path(temp) / "upgrade"
        implementation = execute_isolated_transformation(
            project,
            upgrade / "implementation",
            {"product": {"type": "landing"}},
        )
        unavailable = {
            "status": "NOT_AVAILABLE",
            "reason": "Browser intentionally disabled by public acceptance",
        }
        with mock.patch("web_ui_quality.design_gallery.validate_transformation", return_value=unavailable):
            gallery = build_design_gallery(
                upgrade / "implementation/generated-preview/before",
                implementation,
                upgrade / "validation",
                upgrade / "design-gallery",
            )
        html = (upgrade / "design-gallery/index.html").read_text(encoding="utf-8")
        if gallery.get("status") != "DESIGN_GALLERY_NOT_VERIFIED" or "<img" in html:
            raise RuntimeError("Browser-unavailable gallery contains broken screenshot evidence")
        if "design-decision.json" not in html or "复制给 Codex" not in html:
            raise RuntimeError("gallery decision export is missing")
        for marker in ("普通评审", "设计师", "高管", "改造前", "改造后", "<dialog"):
            if marker not in html:
                raise RuntimeError(f"human decision experience is missing {marker}")
        if not (upgrade / "design-gallery/executive-decision-brief.md").is_file():
            raise RuntimeError("shareable executive decision brief is missing")
        receipt = finalize_design_selection(
            upgrade,
            {
                "selectedVariantId": "direction-2",
                "preferences": {"density": "compact", "brand": "preserve"},
                "notes": {"direction-2": "Keep the navigation"},
            },
        )
        if receipt.get("status") != "DESIGN_SELECTION_FINALIZED":
            raise RuntimeError("design selection was not finalized")
        plan = json.loads((upgrade / "implementation/implementation-plan.json").read_text(encoding="utf-8"))
        if plan.get("selectedVariantId") != "direction-2":
            raise RuntimeError("selected candidate was not promoted to the isolated After tree")
        if not (upgrade / "implementation/source-change.patch").is_file():
            raise RuntimeError("finalized source patch is missing")
    return "complete no-Browser review, decision export, and isolated finalization"


def _human_decision_contract() -> str:
    source = (RUNTIME / "web_ui_quality/design_gallery.py").read_text(encoding="utf-8")
    for marker in ("READY_FOR_HUMAN_DECISION", "finalDecisionOwner", "beforeAfterSynchronized", "reviewAudience"):
        if marker not in source:
            raise RuntimeError(f"decision contract is missing {marker}")
    release_source = (RUNTIME / "web_ui_quality/commercial_upgrade.py").read_text(encoding="utf-8")
    for marker in ("现在只需要决定一个方向", "不会擅自做什么", "技术验证与完整交付物"):
        if marker not in release_source:
            raise RuntimeError(f"executive surface is missing {marker}")
    return "role-aware review, synchronized comparison, executive summary, and natural-language handoff"


def _smart_product_discovery() -> str:
    with tempfile.TemporaryDirectory(prefix="wuq-public-discovery-") as temp:
        project = Path(temp) / "content-operations"
        project.mkdir()
        (project / "package.json").write_text(json.dumps({"name": "content-operations"}), encoding="utf-8")
        (project / "index.html").write_text(
            '<!doctype html><html><head><title>Content Operations</title></head><body><main>'
            '<h1>素材工作台</h1><a href="/assets">素材库</a><a href="/reviews">审核队列</a>'
            '</main></body></html>',
            encoding="utf-8",
        )
        (project / "workflow.ts").write_text(
            "const rolePermissions={editor:['upload','submit'],reviewer:['review','approve','reject'],operator:['assign','track']};\n"
            "const media_asset={state:'draft'}; const states=['submitted','pending-review','approved','rejected','processing','completed','failed'];\n"
            "export const routes=[{path:'/assets'},{path:'/reviews'},{path:'/assignments'}];\n"
            "export function processMedia(){return ['upload','submit','review','approve','reject','revise','assign','download'];}\n",
            encoding="utf-8",
        )
        (project / "credentials.ts").write_text(
            "const secretRolePermissions={superadmin:['publish','delete']};",
            encoding="utf-8",
        )
        before = _tree_digest(project)
        report = build_product_discovery(project)
        if _tree_digest(project) != before or report.get("sourceProjectChanged") is not False:
            raise RuntimeError("product discovery changed the source project")
        process_cached = build_product_discovery(project)
        if process_cached.get("scanStats", {}).get("cacheHit") is not True or process_cached.get("scanStats", {}).get("canonicalScanCount") != 0:
            raise RuntimeError("plugin/skill adapters repeated an unchanged in-process discovery scan")
        if not ({"剪辑或处理人员", "审核员", "运营人员"} & {item.get("label") for item in report.get("rolePermissionMap", [])}):
            raise RuntimeError("product discovery did not reconstruct application roles")
        if len(report.get("operations", [])) < 5 or len(report.get("states", [])) < 4:
            raise RuntimeError("product discovery did not reconstruct workflow actions and states")
        if "素材" not in str(report.get("product", {}).get("job")) and "内容" not in str(report.get("product", {}).get("job")):
            raise RuntimeError("product job was not grounded in content operations")
        if report.get("questionPolicy", {}).get("maximumPerRound") != 3:
            raise RuntimeError("product discovery exceeded the high-impact question limit")
        if len(report.get("questions", [])) < 3 or len(report.get("questionPolicy", {}).get("visibleQuestionIds", [])) > 3:
            raise RuntimeError("product discovery did not preserve bounded question rounds")
        if set(report.get("evidenceClasses", [])) != set(EVIDENCE_CLASSES):
            raise RuntimeError("product discovery evidence classes are incomplete")
        if report.get("scopeHygiene", {}).get("sensitiveNameSkips") != 1:
            raise RuntimeError("sensitive-looking source was not excluded")
        discovery_root = Path(temp) / "understanding-output"
        exported = export_product_discovery(report, discovery_root / "system-understanding")
        if set(exported) != {"understanding", "workbench", "executionBrief", "testPlan", "scanCache"}:
            raise RuntimeError("product discovery artifacts are incomplete")
        html = (discovery_root / "system-understanding/index.html").read_text(encoding="utf-8")
        for marker in ("已核对，交给当前对话确认", "修改一处", "暂时只看检测结果"):
            if marker not in html:
                raise RuntimeError(f"system-understanding action is missing {marker}")
        if len(report.get("questions", [])) > 3 and "保存本轮，继续确认" not in html:
            raise RuntimeError("deferred discovery questions cannot advance to the next visible round")
        if "复制提示词" in html or report.get("executionBrief", {}).get("internalOnly") is not True:
            raise RuntimeError("product discovery exposed an internal prompt-generator workflow")
        cached = load_cached_product_discovery(project, discovery_root)
        if not cached or cached.get("scanStats", {}).get("cacheHit") is not True or cached.get("scanStats", {}).get("canonicalScanCount") != 0:
            raise RuntimeError("unchanged product understanding did not reuse its canonical scan")
        (project / "workflow.ts").write_text((project / "workflow.ts").read_text(encoding="utf-8") + "\n// changed", encoding="utf-8")
        if load_cached_product_discovery(project, discovery_root) is not None:
            raise RuntimeError("changed source incorrectly reused the product understanding cache")
        # Recreate an unchanged cache for the answer-round check; the previous
        # mutation intentionally proved invalidation and must not be hidden.
        (project / "workflow.ts").write_text((project / "workflow.ts").read_text(encoding="utf-8").replace("\n// changed", ""), encoding="utf-8")
        restored_report = build_product_discovery(project)
        export_product_discovery(restored_report, discovery_root / "system-understanding")
        cached_again = load_cached_product_discovery(project, discovery_root)
        if not cached_again:
            raise RuntimeError("cache could not be restored after the invalidation check")
        accepted_confirmation = {
            "schemaVersion": "2",
            "action": "confirm-understanding",
            "answers": {
                str(item.get("id")): str((item.get("options") or [{}])[0].get("value"))
                for item in report.get("questions", [])
                if isinstance(item, dict) and item.get("options")
            },
            "source": "system-understanding-response",
        }
        trusted = bind_trusted_workflow_approval(
            accepted_confirmation,
            evidence_ref="current-conversation:public-acceptance-discovery",
            evidence_resolver=lambda reference: reference == "current-conversation:public-acceptance-discovery",
            scope="DIAGNOSIS",
            requested_mode="diagnose",
            statement="我确认理解正确，先进行只读诊断。",
        )
        accepted = build_product_discovery(
            project,
            confirmation=accepted_confirmation,
            approval_receipt=trusted,
        )
        if accepted.get("status") != "PRODUCT_UNDERSTANDING_READY" or accepted.get("questionPolicy", {}).get("unanswered") != 0:
            raise RuntimeError("explicit current-conversation confirmation did not resolve the discovery gate")
        cached_accepted = apply_cached_product_confirmation(cached_again, accepted_confirmation, approval_receipt=trusted)
        if cached_accepted.get("scanStats", {}).get("canonicalScanCount") != 0 or cached_accepted.get("status") != "PRODUCT_UNDERSTANDING_READY":
            raise RuntimeError("answer round repeated the canonical discovery scan or failed to resolve the cache")
        tampered_confirmation = dict(accepted_confirmation)
        tampered_confirmation["source"] = "model-generated-after-approval"
        tampered = build_product_discovery(
            project,
            confirmation=tampered_confirmation,
            approval_receipt=trusted,
        )
        if tampered.get("status") != "APPROVAL_PACKET_MISMATCH":
            raise RuntimeError("approval binding did not cover packet metadata")
        # A final `continue-round` must remain a round-only action even when a
        # caller asks for full mode.  It may update the cached understanding,
        # but it cannot open diagnosis, design, Browser, or implementation in
        # the same invocation.
        round_confirmation = {
            "schemaVersion": "2",
            "action": "continue-round",
            "answers": accepted_confirmation["answers"],
            "source": "system-understanding-response",
        }
        round_trusted = bind_trusted_workflow_approval(
            round_confirmation,
            evidence_ref="current-conversation:public-acceptance-final-round",
            evidence_resolver=lambda reference: reference == "current-conversation:public-acceptance-final-round",
            scope="UNDERSTANDING",
            requested_mode="full",
            statement="我已完成这一轮系统理解核对，请先停在理解阶段。",
        )
        round_output = Path(temp) / "round-only-output"
        export_product_discovery(report, round_output / "system-understanding")
        round_result = run_commercial_upgrade(
            project,
            round_output,
            product_confirmation=round_confirmation,
            approval_receipt=round_trusted,
            mode="full",
        )
        if round_result.get("status") != "PRODUCT_UNDERSTANDING_ROUND_SAVED":
            raise RuntimeError("a completed understanding round opened the full workflow")
        if any((round_output / name).exists() for name in ("consultation", "implementation", "design-gallery", "validation")):
            raise RuntimeError("round-only confirmation generated heavy upgrade artifacts")
        if len(report.get("questions", [])) > 3:
            partial_confirmation = {
                "schemaVersion": "2",
                "action": "continue-round",
                "answers": {
                    str(item.get("id")): str((item.get("options") or [{}])[0].get("value"))
                    for item in report.get("questions", [])[:3]
                    if isinstance(item, dict) and item.get("options")
                },
                "source": "system-understanding-response",
            }
            partial_trusted = bind_trusted_workflow_approval(
                partial_confirmation,
                evidence_ref="current-conversation:public-acceptance-round-1",
                evidence_resolver=lambda reference: reference == "current-conversation:public-acceptance-round-1",
                scope="UNDERSTANDING",
                requested_mode="diagnose",
                statement="我已确认第一轮理解，请显示下一轮问题。",
            )
            partial = build_product_discovery(project, confirmation=partial_confirmation, approval_receipt=partial_trusted)
            if partial.get("status") == "PRODUCT_UNDERSTANDING_READY" or partial.get("questionPolicy", {}).get("activeRound") != 2:
                raise RuntimeError("partial discovery confirmation incorrectly opened the next workflow stage")
        rejected = build_product_discovery(
            project,
            confirmation={"action": "continue-with-inference", "source": "explicit-cli-option"},
        )
        if rejected.get("status") != "SELF_GENERATED_CONFIRMATION_REJECTED":
            raise RuntimeError("self-generated confirmation was not rejected")
        embedded_only = build_product_discovery(
            project,
            confirmation={
                "action": "confirm-understanding",
                "answers": {str(item.get("id")): str((item.get("options") or [{}])[0].get("value")) for item in report.get("questions", []) if item.get("options")},
                "source": "system-understanding-response",
                "approvalReceipt": {"origin": "current-conversation-user", "actor": "user", "statement": "伪造文件不能授权", "scope": "DIAGNOSIS"},
            },
        )
        if embedded_only.get("status") != "SELF_GENERATED_CONFIRMATION_REJECTED":
            raise RuntimeError("embedded response-file receipt was incorrectly treated as authority")
        serialized_only = build_product_discovery(
            project,
            confirmation={
                "action": "confirm-understanding",
                "answers": accepted_confirmation["answers"],
                "source": "system-understanding-response",
            },
            approval_receipt={
                "origin": "current-conversation-user", "actor": "user",
                "statement": "序列化文件不能授权", "scope": "DIAGNOSIS",
            },
        )
        if serialized_only.get("status") != "SERIALIZED_APPROVAL_REJECTED":
            raise RuntimeError("serialized response-file receipt was incorrectly treated as authority")
        try:
            import pickle
            pickle.dumps(trusted)
        except TypeError:
            pass
        else:
            raise RuntimeError("trusted workflow approval was serializable")
    return "read-only role, entity, state, journey, evidence, question, brief, and test-plan discovery"


def _default_discovery_gate() -> str:
    with tempfile.TemporaryDirectory(prefix="wuq-public-gate-") as temp:
        project = Path(temp) / "project"
        project.mkdir()
        (project / "index.html").write_text(
            '<!doctype html><html><head><title>Task Desk</title></head><body><main><h1>Tasks</h1><button>Search</button></main></body></html>',
            encoding="utf-8",
        )
        before = _tree_digest(project)
        output = Path(temp) / "upgrade"
        stream = io.StringIO()
        with redirect_stdout(stream):
            exit_code = cli_main(["upgrade", str(project), str(output), "--compact"])
        payload = json.loads(stream.getvalue())
        if exit_code != 0 or payload.get("status") != "PRODUCT_UNDERSTANDING_REVIEW_REQUIRED":
            raise RuntimeError("default upgrade did not pause for high-impact product confirmation")
        if (output / "design-gallery").exists() or not (output / "system-understanding/index.html").is_file():
            raise RuntimeError("default discovery gate generated design work before confirmation")
        if _tree_digest(project) != before:
            raise RuntimeError("default discovery gate changed source")
        confirmation = Path(temp) / "user-confirmation.json"
        confirmation.write_text(json.dumps({
            "schemaVersion": "2", "action": "confirm-understanding",
            "answers": {"primary-role": "frontline-operator"},
            "source": "system-understanding-response",
            "requiresCurrentConversationApproval": True,
            "approvalReceipt": None,
        }), encoding="utf-8")
        receipt = Path(temp) / "user-receipt.json"
        receipt.write_text(json.dumps({
            "origin": "current-conversation-user", "actor": "user",
            "statement": "我已核对系统理解，先进行只读诊断。", "scope": "DIAGNOSIS",
        }), encoding="utf-8")
        stream = io.StringIO()
        with redirect_stdout(stream):
            resumed_exit = cli_main([
                "upgrade", str(project), str(output), "--product-confirmation", str(confirmation),
                "--approval-receipt", str(receipt), "--compact",
            ])
        resumed = json.loads(stream.getvalue())
        if resumed_exit != 0 or resumed.get("status") != "SERIALIZED_APPROVAL_REJECTED":
            raise RuntimeError("CLI serialized approval was not rejected")
        packet = json.loads(confirmation.read_text(encoding="utf-8"))
        trusted = bind_trusted_workflow_approval(
            packet,
            evidence_ref="current-conversation:public-acceptance-diagnosis",
            evidence_resolver=lambda reference: reference == "current-conversation:public-acceptance-diagnosis",
            scope="DIAGNOSIS",
            requested_mode="diagnose",
            statement="我已核对系统理解，先进行只读诊断。",
        )
        resumed = run_commercial_upgrade(
            project,
            output,
            product_confirmation=packet,
            approval_receipt=trusted,
            mode="diagnose",
        )
        if resumed.get("status") != "PRODUCT_DIAGNOSIS_READY":
            raise RuntimeError("trusted host approval did not stop at the lightweight diagnosis route")
        if (output / "implementation").exists() or (output / "design-gallery").exists():
            raise RuntimeError("diagnosis route generated heavy design or implementation artifacts")
        if _tree_digest(project) != before:
            raise RuntimeError("diagnosis route changed source")
    return "one-sentence upgrade pauses at system understanding before design"


def _lightweight_security_and_profile() -> str:
    with tempfile.TemporaryDirectory(prefix="wuq-public-policy-") as temp:
        project = Path(temp) / "project"
        project.mkdir()
        (project / "index.html").write_text('<a target="_blank" href="/external">External</a>', encoding="utf-8")
        from web_ui_quality.core import audit_project
        light = audit_project(project)
        deep = audit_project(project, include_security=True)
        if light.get("securityAudit") != "OPT_IN_ONLY" or any(item.get("category") == "security" for item in light.get("findings", [])):
            raise RuntimeError("default product audit still runs security findings")
        if deep.get("securityAudit") != "RUN" or not any(item.get("category") == "security" for item in deep.get("findings", [])):
            raise RuntimeError("opt-in security audit is unavailable")
        unknown = build_product_discovery(project, model_profile="future-unknown")
        if unknown.get("modelCapabilityProfile", {}).get("id") != "baseline":
            raise RuntimeError("unknown model profile did not fall back to baseline")
        if unknown.get("questionPolicy", {}).get("mayProceedWithInference") is not False:
            raise RuntimeError("inference bypass remains enabled")
        bounded = Path(temp) / "bounded-project"
        bounded.mkdir()
        for index in range(365):
            (bounded / f"screen-{index}.ts").write_text("export const screen = %r;" % index, encoding="utf-8")
        incomplete = build_product_discovery(bounded)
        if incomplete.get("status") != "DISCOVERY_SCOPE_INCOMPLETE" or not incomplete.get("materialUnknowns"):
            raise RuntimeError("over-budget discovery did not stop with an explicit scope boundary")
    return "light default path, opt-in security findings, and baseline model fallback"


def run() -> dict[str, object]:
    checks: list[dict[str, str]] = []
    cases: tuple[tuple[str, Callable[[], str]], ...] = (
        ("PUB-001", _identity),
        ("PUB-002", _classification),
        ("PUB-003", _project_grounding),
        ("PUB-004", _next_pages),
        ("PUB-005", _fallback_and_decision),
        ("PUB-006", _human_decision_contract),
        ("PUB-007", _smart_product_discovery),
        ("PUB-008", _default_discovery_gate),
        ("PUB-009", _lightweight_security_and_profile),
        ("PUB-010", _quick_ui_contract),
    )
    for identifier, case in cases:
        checks.append({"id": identifier, "status": "PASS", "detail": case()})
    return {
        "status": "PASS",
        "version": PACKAGE_VERSION,
        "stage": RELEASE_STAGE,
        "scope": "PUBLIC_DISTRIBUTION_ACCEPTANCE",
        "checks": checks,
    }


def main() -> int:
    from web_ui_quality.release_info import configure_stdout

    configure_stdout()
    try:
        result = run()
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
        result = {
            "status": "FAIL",
            "version": PACKAGE_VERSION,
            "scope": "PUBLIC_DISTRIBUTION_ACCEPTANCE",
            "error": str(error),
        }
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
