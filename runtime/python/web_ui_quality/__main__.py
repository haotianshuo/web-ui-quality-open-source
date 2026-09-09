"""Command-line entry point for Web UI Quality.

The CLI never accepts serialized JSON as formal Browser or approval authority.
Local Browser comparison is trusted only because it is generated and consumed
inside the same process with an isolated Playwright context.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Mapping

from .browser_standard import validate_browser_report_structure
from .contracts import (
    ContractViolation,
    digest_json,
    build_source_scope_manifest,
    load_json,
    plan_digest,
    source_scope_fingerprint,
)
from .core import audit_html_document, audit_project
from .playwright_adapter import compare_pages
from .quick_ui import run_quick_ui
from .smart_acceptance import run_smart_acceptance
from .source_assurance import run_source_assurance
from .external_providers import capabilities as external_capabilities, run_lighthouse
from .visual_diff import capability as visual_capability
from .orchestrator import run_full_audit
from .visual_review import review_template
from .reporting import generate_html_report
from .collaboration import export_collaboration_bundle
from .commercial_preflight import run_preflight
from .report_server import serve_report
from .review_workflow import record_review
from .experience_preview import generate_experience_preview
from .experience_studio import build_library_artifact, generate_experience_studio
from .experience_catalog import catalog_metrics, get_skeleton, page_skeleton_catalog
from .ux_repair import analyze_ux_sources
from .design_system_map import build_design_system_map
from .experience_evaluator import evaluate_experience
from .experience_modernization import build_modernization_strategy
from .pattern_library import PATTERNS
from .visual_system import direction_catalog
from .design_pipeline import run_design_pipeline
from .figma_input import import_figma_json, fetch_and_import_figma
from .screenshot_input import analyse_screenshot, import_screenshot, capability as screenshot_capability
from .component_registry import source_catalog, component_recipes, detect_framework, recommend_components
from .experience_engine import analyze_experience_project, export_experience_analysis
from .design_intelligence import archetype_catalog, generate_design_candidates
from .production_mapper import build_production_plan, generate_production_scaffold
from .visual_builder import generate_visual_builder
from .product_experience_consultant import build_product_experience_report, export_product_experience_report
from .commercial_upgrade import refresh_commercial_ui_state, run_commercial_upgrade
from .design_gallery import render_design_gallery
from .smart_product_discovery import (
    apply_cached_product_confirmation,
    build_product_discovery,
    export_product_discovery,
    load_cached_product_discovery,
)
from .workflow_policy import (
    EVIDENCE_CLASSES,
    is_answer_round_action,
    is_diagnosis_only_action,
    model_capability_profile,
    normalize_mode,
    required_scope_for_action,
    validate_confirmation,
)
from .implementation_agent import finalize_design_selection
from .outcome_measurement import export_outcome_report, measure_outcome
from .production_validation import browser_runtime_capability, validate_transformation
from .release_info import PACKAGE_VERSION, configure_stdout, package_identity, release_identity, experimental_identity
from .adaptive_intelligence import verification_profile
from .schema_validation import check_schema_bundle, validate_instance
from .capability_registry import build_capability_registry
from .fix_workflow import prepare_fix_workflow
from .intent_router import route_user_intent
from .experience_fix import _target_identity, run_experience_fix
from .experience_run import load_experience_run
from .run_checkpoint import find_latest_compatible_run
from .ui_inventory import run_ui_inventory
from .auth_profiles import save_auth_profile, load_auth_profile
from .task_result import build_task_result, human_status_label, human_status_explanation


_SEVERITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}

_PUBLIC_COMMANDS = {"run", "doctor", "auth", "expert"}
_COMPATIBILITY_COMMANDS = {"experience-fix", "inspect", "fix", "redesign", "audit", "ui-inventory"}
_EXPERT_COMMAND_DESCRIPTIONS = {
    "check": "legacy smart acceptance compatibility route",
    "quick-ui": "screenshot-first compatibility route",
    "source-check": "read-only explicit source scope assurance",
    "browser-compare": "same-condition Browser before/after comparison",
    "audit-html-stdin": "audit one HTML document from stdin",
    "audit-and-compare": "integrated source and Browser comparison",
    "full-audit": "full opt-in static, Browser, accessibility and performance workflow",
    "ui-inventory": "read-only whole-site UI asset inventory and drift report",
    "consult": "compact product-experience consultation",
    "product-consult": "complete product journey and planning workflow",
    "upgrade": "read-only product diagnosis or explicitly requested isolated upgrade",
    "commercial-upgrade": "advanced full isolated candidate workflow",
    "design-ui": "render the optional decision workbench on demand",
    "finalize-design": "promote a selected isolated design candidate",
    "validate-transformation": "validate runnable Before/After candidates",
    "measure-outcome": "compare observational event exports",
    "prepare-change-set": "generate a read-only Patch Candidate for Host application",
    "apply-change-set": "disabled compatibility route; Codex Host owns source writes",
    "rollback-change-set": "disabled compatibility route; Host applies reverse Patch Candidate",
}
_INTERNAL_COMMANDS = (
    "lighthouse", "visual-review-template", "render-report", "serve-report", "export-collaboration",
    "record-review", "experience-analyze", "experience-plan", "design-pipeline", "figma-import",
    "screenshot-import", "component-registry", "production-plan", "visual-builder", "experience-catalog",
    "ux-repair-plan", "design-system-map", "render-experience-preview", "evaluate-experience",
    "modernization-plan", "commercial-preflight", "digest-plan", "manifest", "validate-browser-report",
)

_COMMAND_LIFECYCLE = {
    **{name: "public" for name in _PUBLIC_COMMANDS},
    **{name: "compatibility" for name in _COMPATIBILITY_COMMANDS},
    **{name: "expert" for name in _EXPERT_COMMAND_DESCRIPTIONS if name not in _PUBLIC_COMMANDS and name not in _COMPATIBILITY_COMMANDS},
    **{name: "internal-compatibility" for name in _INTERNAL_COMMANDS},
}



def _add_audit_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--instruction-source", default="user_current_conversation")
    parser.add_argument("--role")
    parser.add_argument("--state", action="append")
    parser.add_argument("--project-reference", type=Path)
    parser.add_argument("--business-context", type=Path, help="explicit role, frequency, environment, task, success metric and constraints")
    parser.add_argument("--evidence", type=Path, help="candidate evidence only; cannot establish formal PASS")
    parser.add_argument("--summary", "--user-summary", dest="summary", action="store_true")
    parser.add_argument("--security-audit", action="store_true", help="opt in to static security findings; omitted from the lightweight audit")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument(
        "--fail-on",
        choices=("none", "P0", "P1", "P2", "P3"),
        default="none",
        help="return exit code 1 when a finding at or above this severity exists",
    )


def _add_product_discovery_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--screenshot", action="append", type=Path, default=[], help="observed page screenshot; may be repeated")
    parser.add_argument("--multimodal-overlay", type=Path, help="optional host semantic overlay for the first screenshot")
    parser.add_argument("--product-confirmation", type=Path, help="product-confirmation.json downloaded from system understanding")
    parser.add_argument("--approval-receipt", type=Path, help="serialized candidate evidence only; a process-local host approval object is required to continue")
    parser.add_argument("--mode", choices=("diagnose", "full"), help="diagnose is the safe default; full creates isolated design candidates only when explicitly requested")
    parser.add_argument("--model-profile", help="optional host capability profile or model label; unknown values fall back to the baseline contract")
    parser.add_argument("--security-audit", action="store_true", help="opt in to the separate static security findings; off by default in product consultation")
    parser.add_argument("--design-ui", action="store_true", help="opt in to rendering the local design decision workbench")
    # Kept parseable for old callers, but never accepted as authorization.
    parser.add_argument("--assume-discovery", action="store_true", help=argparse.SUPPRESS)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="web-ui-quality",
        description=f"Web UI Quality {PACKAGE_VERSION} — inspect, fix, redesign, or run an explicit audit",
        epilog="普通任务使用 run；doctor 用于环境诊断，auth 用于显式登录态，expert 仅用于高级与兼容入口。",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_cmd = subparsers.add_parser("run", help="默认入口：一句话描述问题，系统自动建立基线、诊断、规划修复并验证")
    run_cmd.add_argument("target", help="local Web project directory or accessible URL")
    run_cmd.add_argument("request_text", nargs="?", help="natural-language task, e.g. 修复订单页移动端错位，不要动登录逻辑")
    run_cmd.add_argument("--request", dest="request_option", help="same as positional request_text; retained for scripts and compatibility")
    run_cmd.add_argument("--url", help="accessible runtime URL when target is a local project")
    run_cmd.add_argument("--after-url", help="After URL; resumes the latest matching FIX_AND_VERIFY run")
    run_cmd.add_argument("--host-write-receipt", type=Path, help="V3 Host receipt bound to the persisted apply binding; legacy receipts are history-only")
    run_cmd.add_argument("--host-patch-candidate", type=Path, help="pre-write Host patch candidate used to prepare the V3 apply binding")
    run_cmd.add_argument("--approve-request", action="append", default=[], metavar="ORIGIN,METHOD,PATH[?QUERY]", help="exact temporary Browser request authorization; query values are stored only as a digest; may be repeated, use WEBSOCKET as method for ws/wss")
    run_cmd.add_argument("--host-tool-result", type=Path, action="append", default=[], help="Host project-tool result receipt JSON; may be repeated")
    run_cmd.add_argument("--file", action="append", default=[], help="optional explicit project-relative source scope; may be repeated")
    run_cmd.add_argument("--auth-profile", help="named authentication profile; explicit user security decision")
    run_cmd.add_argument("--storage-state", type=Path, help="explicit Playwright storage-state JSON; prefer --auth-profile for reuse")
    run_cmd.add_argument("--allow-origin", action="append", default=[], help="additional origin explicitly allowed for this run; may be repeated")
    run_cmd.add_argument("--browser-executable", type=Path, help="browser executable used after the Playwright driver is available")
    run_cmd.add_argument("--json", action="store_true", help="emit the stable Beta.3 TaskResult v1 machine contract as JSON")
    run_cmd.add_argument("--expert-json", action="store_true", help="emit the complete internal Runtime result for diagnostics/integration")
    run_cmd.add_argument("--ci", action="store_true", help="CI mode: machine-readable output and repair-status exit codes; VERIFIED is required")
    run_cmd.add_argument("--require", choices=("VERIFIED",), help="require the named repair status; currently VERIFIED")
    run_cmd.add_argument("--compact", action="store_true", help="compatibility: emit compact full Runtime JSON (expert surface)")

    auth_cmd = subparsers.add_parser("auth", help="register a named authentication profile from an existing Playwright storage-state file")
    auth_cmd.add_argument("name", help="profile name, for example staging-admin")
    auth_cmd.add_argument("storage_state", type=Path, help="existing Playwright storage-state JSON; credentials are not copied into the project")
    auth_cmd.add_argument("--allow-origin", action="append", default=[], help="origin allowed when this profile is used; may be repeated")
    auth_cmd.add_argument("--compact", action="store_true", help="emit compact JSON")

    experience_cmd = subparsers.add_parser("experience-fix", help="compatibility entry retained for existing integrations")
    experience_cmd.add_argument("target", help="project directory, accessible URL, or project directory used with --url")
    experience_cmd.add_argument("artifacts_root", help="root directory; each run is written to artifacts/<run-id>/")
    experience_cmd.add_argument("--request", help="current user request used only for intent routing; it never grants authority")
    experience_cmd.add_argument("--mode", choices=("CHECK", "FIX_AND_VERIFY", "DEEP_REDESIGN", "SPECIALIZED_AUDIT"))
    experience_cmd.add_argument("--task-id", help="Host task identity; standalone CLI creates a non-authorizing local identity")
    experience_cmd.add_argument("--session-id", help="Host session identity; standalone CLI creates a non-authorizing local identity")
    experience_cmd.add_argument("--url", help="accessible URL when target is a project directory")
    experience_cmd.add_argument("--existing-run", type=Path, help="existing sealed ExperienceRun used for After or continued work")
    experience_cmd.add_argument("--after-url", help="After URL; requires matching sealed Before")
    experience_cmd.add_argument("--host-write-receipt", type=Path, help="V3 Host receipt bound to the persisted apply binding; legacy receipts are history-only")
    experience_cmd.add_argument("--host-patch-candidate", type=Path, help="pre-write Host patch candidate used to prepare the V3 apply binding")
    experience_cmd.add_argument("--approve-request", action="append", default=[], metavar="ORIGIN,METHOD,PATH[?QUERY]", help="exact temporary Browser request authorization; query values are stored only as a digest; may be repeated")
    experience_cmd.add_argument("--host-tool-result", type=Path, action="append", default=[], help="Host project-tool result receipt JSON; may be repeated")
    experience_cmd.add_argument("--file", action="append", default=[], help="minimum project-relative source scope for focused fix")
    experience_cmd.add_argument("--business-context", type=Path)
    experience_cmd.add_argument("--viewport", action="append", help="WIDTHxHEIGHT; defaults to 390x844, 768x1024, 1440x900")
    experience_cmd.add_argument("--allow-origin", action="append", default=[])
    experience_cmd.add_argument("--environment", choices=("local", "test", "staging", "production", "unknown"))
    experience_cmd.add_argument("--locale", default="zh-CN")
    experience_cmd.add_argument("--theme", choices=("light", "dark", "no-preference"), default="light")
    experience_cmd.add_argument("--browser", choices=("chromium", "firefox", "webkit"), default="chromium", help="Browser engine; chromium is the default")
    experience_cmd.add_argument("--browser-executable", type=Path, help="explicit browser executable; otherwise Chrome/Edge/Chromium is auto-detected")
    experience_cmd.add_argument("--user-role")
    experience_cmd.add_argument("--auth-state", default="anonymous")
    experience_cmd.add_argument("--storage-state", type=Path, help="Playwright storage-state JSON used for authenticated Browser evidence")
    experience_cmd.add_argument("--test-data-state", default="unspecified")
    experience_cmd.add_argument("--compact", action="store_true")

    inspect_cmd = subparsers.add_parser("inspect", help="专业入口：检查真实页面体验，不修改项目")
    inspect_cmd.add_argument("target", help="runnable URL or local project directory")
    inspect_cmd.add_argument("output_dir")
    inspect_cmd.add_argument("--url", help="runnable URL when target is a project directory")
    inspect_cmd.add_argument("--business-context", type=Path)
    inspect_cmd.add_argument("--journey", type=Path, help="optional safe A0/A1 journey JSON")
    inspect_cmd.add_argument("--viewport", action="append", help="WIDTHxHEIGHT; defaults to 390x844, 768x1024, 1440x900")
    inspect_cmd.add_argument("--allow-origin", action="append", default=[])
    inspect_cmd.add_argument("--environment", choices=("local", "test", "staging", "production", "unknown"))
    inspect_cmd.add_argument("--locale", default="zh-CN")
    inspect_cmd.add_argument("--theme", choices=("light", "dark", "no-preference"), default="light")
    inspect_cmd.add_argument("--browser", choices=("chromium", "firefox", "webkit"), default="chromium", help="Browser engine; chromium is the default")
    inspect_cmd.add_argument("--browser-executable", type=Path, help="explicit browser executable; otherwise Chrome/Edge/Chromium is auto-detected")
    inspect_cmd.add_argument("--storage-state", type=Path)
    inspect_cmd.add_argument("--headers", type=Path)
    inspect_cmd.add_argument("--ignore-https-errors", action="store_true")
    inspect_cmd.add_argument("--compact", action="store_true")

    fix_cmd = subparsers.add_parser("fix", help="准备最小修复范围；由可信 Host 确认后才能写入")
    fix_cmd.add_argument("project_root")
    fix_cmd.add_argument("output_dir")
    fix_cmd.add_argument("--file", action="append", default=[], help="project-relative file in the proposed scope; may be repeated")
    fix_cmd.add_argument("--evidence", type=Path, help="optional prior inspection report")
    fix_cmd.add_argument("--goal", default="修复已确认的 Web UI 问题")
    fix_cmd.add_argument("--compact", action="store_true")

    redesign_cmd = subparsers.add_parser("redesign", help="理解产品并启动 1–3 个隔离设计方向；不修改原项目")
    redesign_cmd.add_argument("project_root")
    redesign_cmd.add_argument("output_dir", nargs="?")
    redesign_cmd.add_argument("--product-name")
    redesign_cmd.add_argument("--product-type", choices=("crm", "saas", "landing", "commerce", "ai-product", "mobile"))
    redesign_cmd.add_argument("--business-context", type=Path)
    redesign_cmd.add_argument("--browser-executable", type=Path)
    redesign_cmd.add_argument("--journey", type=Path)
    redesign_cmd.add_argument("--baseline-events", type=Path)
    redesign_cmd.add_argument("--after-events", type=Path)
    redesign_cmd.add_argument("--outcome-provider", choices=("generic", "ga4", "mixpanel", "posthog"), default="generic")
    redesign_cmd.add_argument("--outcome-config", type=Path)
    redesign_cmd.add_argument("--directions", type=int, choices=(1, 2, 3), default=3, help="number of genuine product directions; 1–3, default 3 for compatibility")
    _add_product_discovery_options(redesign_cmd)
    redesign_cmd.set_defaults(mode="full")
    redesign_cmd.add_argument("--compact", action="store_true")

    expert_help = "\n".join(f"  {name:<26} {description}" for name, description in sorted(_EXPERT_COMMAND_DESCRIPTIONS.items()))
    expert_cmd = subparsers.add_parser(
        "expert", help="查看兼容、自动化和调试命令",
        description="兼容、自动化和调试命令",
        epilog=expert_help + "\n\n其余可解析命令属于 internal-compatibility，不承诺稳定 API；运行 `web-ui-quality expert` 查看完整生命周期。", formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    expert_cmd.add_argument("--compact", action="store_true")

    audit = subparsers.add_parser("audit", help="执行明确指定的只读专项；默认进行源码体验审计")
    audit.add_argument("project_root")
    _add_audit_options(audit)

    html = subparsers.add_parser("audit-html-stdin", help="audit one HTML document supplied on stdin")
    html.add_argument("--source-name", default="remote-page.html")
    html.add_argument("--source-url")
    html.add_argument("--canonicalize-external", action="store_true")
    _add_audit_options(html)

    quick_ui = subparsers.add_parser(
        "quick-ui",
        help="capture one real page at mobile, small-desktop, and desktop sizes and report only the Top 3 visible UI problems",
    )
    quick_ui.add_argument("url")
    quick_ui.add_argument("output_dir")
    quick_ui.add_argument("--viewport", action="append", help="WIDTHxHEIGHT; replaces the 390x844 and 1440x900 defaults")
    quick_ui.add_argument("--allow-origin", action="append", default=[])
    quick_ui.add_argument("--locale", default="zh-CN")
    quick_ui.add_argument("--theme", choices=("light", "dark", "no-preference"), default="light")
    quick_ui.add_argument("--browser", choices=("chromium", "firefox", "webkit"), default="chromium")
    quick_ui.add_argument("--browser-executable", type=Path, help="explicit browser executable; otherwise auto-detect a desktop install")
    quick_ui.add_argument("--storage-state", type=Path)
    quick_ui.add_argument("--headers", type=Path)
    quick_ui.add_argument("--ignore-https-errors", action="store_true")
    quick_ui.add_argument("--compact", action="store_true")

    check = subparsers.add_parser(
        "check",
        help="v2.3 smart acceptance: preflight, three viewports, one safe journey, Outcome Proof, Top 3, and explicit coverage boundaries",
    )
    check.add_argument("target", help="runnable URL or local project directory")
    check.add_argument("output_dir")
    check.add_argument("--url", help="runnable URL when target is a project directory")
    check.add_argument("--business-context", type=Path, help="optional explicit Business Context JSON")
    check.add_argument("--journey", type=Path, help="optional safe A0/A1 journey JSON with Outcome Proof")
    check.add_argument("--viewport", action="append", help="WIDTHxHEIGHT; defaults to 390x844, 768x1024, 1440x900")
    check.add_argument("--allow-origin", action="append", default=[])
    check.add_argument("--environment", choices=("local", "test", "staging", "production", "unknown"))
    check.add_argument("--locale", default="zh-CN")
    check.add_argument("--theme", choices=("light", "dark", "no-preference"), default="light")
    check.add_argument("--browser", choices=("chromium", "firefox", "webkit"), default="chromium")
    check.add_argument("--browser-executable", type=Path, help="explicit browser executable; otherwise auto-detect a desktop install")
    check.add_argument("--storage-state", type=Path)
    check.add_argument("--headers", type=Path)
    check.add_argument("--ignore-https-errors", action="store_true")
    check.add_argument("--compact", action="store_true")

    source_check = subparsers.add_parser(
        "source-check",
        help="local-only v2.3 P0-B-S foundation: lock an explicit change scope, run deterministic checks, and produce a command-safety plan",
    )
    source_check.add_argument("project_root")
    source_check.add_argument("output_dir")
    source_check.add_argument("--file", action="append", default=[], help="project-relative file in the approved change scope; may be repeated")
    source_check.add_argument("--base-ref", help="optional Git comparison base when no explicit files are supplied")
    source_check.add_argument("--intent", default="review current change")
    source_check.add_argument("--compact", action="store_true")

    browser = subparsers.add_parser(
        "browser-compare",
        help="capture same-condition before/after evidence in isolated Playwright contexts",
    )
    browser.add_argument("before_url")
    browser.add_argument("after_url")
    browser.add_argument("output_dir")
    browser.add_argument("--viewport", action="append", help="WIDTHxHEIGHT; may be repeated")
    browser.add_argument("--allow-origin", action="append", default=[])
    browser.add_argument("--locale", default="zh-CN")
    browser.add_argument("--theme", choices=("light", "dark", "no-preference"), default="light")
    browser.add_argument("--browser", choices=("chromium", "firefox", "webkit"), default="chromium")
    browser.add_argument("--browser-executable", type=Path, help="explicit browser executable; otherwise auto-detect a desktop install")
    browser.add_argument("--compact", action="store_true")
    browser.add_argument("--journey", type=Path, help="safe declarative journey JSON")
    browser.add_argument("--allow-submit", action="store_true", help="legacy submit approval; prefer --approve-action")
    browser.add_argument("--approve-action", action="append", default=[], help="approve one journey step id; may be repeated")
    browser.add_argument("--storage-state", type=Path, help="Playwright storage-state JSON; keep outside source control")
    browser.add_argument("--headers", type=Path, help="JSON object with explicit extra HTTP headers")
    browser.add_argument("--axe-script", type=Path, help="local pinned axe.min.js")
    browser.add_argument("--ignore-https-errors", action="store_true")
    browser.add_argument("--no-trace", action="store_true")
    browser.add_argument("--no-visual-diff", action="store_true")

    integrated = subparsers.add_parser(
        "audit-and-compare",
        help="run static audit plus locally trusted Browser comparison in one process",
    )
    integrated.add_argument("project_root")
    integrated.add_argument("before_url")
    integrated.add_argument("after_url")
    integrated.add_argument("output_dir")
    integrated.add_argument("--viewport", action="append")
    integrated.add_argument("--allow-origin", action="append", default=[])
    integrated.add_argument("--locale", default="zh-CN")
    integrated.add_argument("--theme", choices=("light", "dark", "no-preference"), default="light")
    integrated.add_argument("--browser", choices=("chromium", "firefox", "webkit"), default="chromium")
    integrated.add_argument("--browser-executable", type=Path, help="explicit browser executable; otherwise auto-detect a desktop install")
    integrated.add_argument("--role")
    integrated.add_argument("--state", action="append")
    integrated.add_argument("--summary", action="store_true")
    integrated.add_argument("--compact", action="store_true")
    integrated.add_argument("--journey", type=Path)
    integrated.add_argument("--allow-submit", action="store_true")
    integrated.add_argument("--approve-action", action="append", default=[])
    integrated.add_argument("--storage-state", type=Path)
    integrated.add_argument("--headers", type=Path)
    integrated.add_argument("--axe-script", type=Path)
    integrated.add_argument("--ignore-https-errors", action="store_true")
    integrated.add_argument("--business-context", type=Path)
    integrated.add_argument("--project-reference", type=Path)
    integrated.add_argument("--no-trace", action="store_true")
    integrated.add_argument("--no-visual-diff", action="store_true")

    lighthouse = subparsers.add_parser("lighthouse", help="run an optional local Lighthouse audit")
    lighthouse.add_argument("url")
    lighthouse.add_argument("output_dir")
    lighthouse.add_argument("--compact", action="store_true")
    lighthouse.add_argument("--executable", type=Path, help="explicit pinned local Lighthouse binary")

    full = subparsers.add_parser("full-audit", help="unified static, Browser, journey, rendered quality, axe, Lighthouse, report and collaboration workflow")
    full.add_argument("project_root"); full.add_argument("before_url"); full.add_argument("after_url"); full.add_argument("output_dir")
    full.add_argument("--viewport", action="append"); full.add_argument("--allow-origin", action="append", default=[])
    full.add_argument("--browser", choices=("chromium","firefox","webkit"), default="chromium")
    full.add_argument("--browser-executable", type=Path, help="explicit browser executable; otherwise auto-detect a desktop install")
    full.add_argument("--locale", default="zh-CN")
    full.add_argument("--theme", choices=("light", "dark", "no-preference"), default="light")
    full.add_argument("--ignore-https-errors", action="store_true")
    full.add_argument("--no-trace", action="store_true")
    full.add_argument("--no-visual-diff", action="store_true")
    full.add_argument("--business-context", type=Path); full.add_argument("--project-reference", type=Path)
    full.add_argument("--journey", type=Path); full.add_argument("--approve-action", action="append", default=[])
    full.add_argument("--storage-state", type=Path); full.add_argument("--headers", type=Path); full.add_argument("--axe-script", type=Path)
    full.add_argument("--lighthouse", action="store_true"); full.add_argument("--lighthouse-executable", type=Path)
    full.add_argument("--visual-review", type=Path); full.add_argument("--compact", action="store_true")

    visual_template = subparsers.add_parser("visual-review-template", help="emit the qualitative visual review contract")
    visual_template.add_argument("--output", type=Path)

    render = subparsers.add_parser("render-report", help="generate the self-contained HTML workbench from a unified report")
    render.add_argument("report"); render.add_argument("output_dir")

    serve = subparsers.add_parser("serve-report", help="serve a generated HTML workbench on localhost")
    serve.add_argument("report_dir")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=0)
    serve.add_argument("--open", action="store_true", dest="open_browser")

    collaboration = subparsers.add_parser("export-collaboration", help="export SARIF, GitHub summary and review-state files")
    collaboration.add_argument("report"); collaboration.add_argument("output_dir")

    review_cmd = subparsers.add_parser("record-review", help="append an auditable review decision to a Git-friendly review file")
    review_cmd.add_argument("review_file")
    review_cmd.add_argument("--report-digest")
    review_cmd.add_argument("--reviewer", required=True)
    review_cmd.add_argument("--decision", choices=("NOT_REVIEWED","APPROVED","CHANGES_REQUESTED","REJECTED"), required=True)
    review_cmd.add_argument("--comment", default="")

    experience_analyze = subparsers.add_parser("experience-analyze", help="build an evidence-bounded schema 3.1 experience diagnosis and Before/After preview")
    experience_analyze.add_argument("project_root")
    experience_analyze.add_argument("output_dir")
    experience_analyze.add_argument("--business-context", type=Path)
    experience_analyze.add_argument("--screenshot", type=Path, help="optional screenshot for Screenshot-to-Experience modelling")
    experience_analyze.add_argument("--multimodal-overlay", type=Path, help="optional host semantic overlay for the screenshot")
    experience_analyze.add_argument("--target-framework", choices=("react", "vue", "svelte", "solid", "html", "web-components"))
    experience_analyze.add_argument("--title")
    experience_analyze.add_argument("--no-preview", action="store_true")
    experience_analyze.add_argument("--compact", action="store_true")

    consult = subparsers.add_parser(
        "consult",
        help="get a plain-language Top 3, one recommended direction, Before/After preview, and safe handoff",
    )
    consult.add_argument("project_root")
    consult.add_argument("output_dir")
    consult.add_argument(
        "--goal",
        choices=("web-experience", "crm-saas", "screenshot", "mobile", "user-flow"),
        help="what the user wants to improve; inferred from the page when omitted",
    )
    consult.add_argument("--business-context", type=Path)
    consult.add_argument("--screenshot", type=Path, help="optional reference screenshot; never treated as verified Before evidence")
    consult.add_argument("--multimodal-overlay", type=Path)
    consult.add_argument("--target-framework", choices=("react", "vue", "svelte", "solid", "html", "web-components"))
    consult.add_argument("--title")
    consult.add_argument("--compact", action="store_true")

    product_consult = subparsers.add_parser(
        "product-consult",
        help="create the complete product journey, transformation concepts, executive brief, and measurement handoff",
    )
    product_consult.add_argument("project_root")
    product_consult.add_argument("output_dir")
    product_consult.add_argument("--product-name")
    product_consult.add_argument("--product-type", choices=("crm", "saas", "landing", "commerce", "ai-product", "mobile"))
    product_consult.add_argument("--goal", choices=("web-experience", "crm-saas", "screenshot", "mobile", "user-flow"))
    product_consult.add_argument("--business-context", type=Path)
    product_consult.add_argument("--screenshot", type=Path, help="optional visual reference; never promoted to verified production evidence")
    product_consult.add_argument("--multimodal-overlay", type=Path)
    product_consult.add_argument("--target-framework", choices=("react", "vue", "svelte", "solid", "html", "web-components"))
    product_consult.add_argument("--security-audit", action="store_true", help="opt in to static security findings")
    product_consult.add_argument("--compact", action="store_true")

    upgrade = subparsers.add_parser(
        "upgrade",
        help="one-command read-only understanding and diagnosis; use --mode full only for an explicitly requested isolated upgrade",
    )
    upgrade.add_argument("project_root")
    upgrade.add_argument("output_dir", nargs="?", help="optional; defaults to a new sibling experience-upgrade directory")
    upgrade.add_argument("--product-name")
    upgrade.add_argument("--product-type", choices=("crm", "saas", "landing", "commerce", "ai-product", "mobile"))
    upgrade.add_argument("--business-context", type=Path)
    upgrade.add_argument("--browser-executable", type=Path)
    upgrade.add_argument("--journey", type=Path)
    upgrade.add_argument("--baseline-events", type=Path)
    upgrade.add_argument("--after-events", type=Path)
    upgrade.add_argument("--outcome-provider", choices=("generic", "ga4", "mixpanel", "posthog"), default="generic")
    upgrade.add_argument("--outcome-config", type=Path)
    _add_product_discovery_options(upgrade)
    upgrade.set_defaults(mode="diagnose")
    upgrade.add_argument("--compact", action="store_true")

    commercial_upgrade = subparsers.add_parser(
        "commercial-upgrade",
        help="explicit full workflow with three isolated candidates, optional Browser proof, and outcome measurement",
    )
    commercial_upgrade.add_argument("project_root")
    commercial_upgrade.add_argument("output_dir")
    commercial_upgrade.add_argument("--product-name")
    commercial_upgrade.add_argument("--product-type", choices=("crm", "saas", "landing", "commerce", "ai-product", "mobile"))
    commercial_upgrade.add_argument("--business-context", type=Path)
    commercial_upgrade.add_argument("--target-framework", choices=("react", "vue", "svelte", "solid", "html", "web-components"))
    commercial_upgrade.add_argument("--browser-executable", type=Path)
    commercial_upgrade.add_argument("--browser-single-process", action="store_true")
    commercial_upgrade.add_argument("--journey", type=Path, help="optional safe journey JSON array")
    commercial_upgrade.add_argument("--baseline-events", type=Path)
    commercial_upgrade.add_argument("--after-events", type=Path)
    commercial_upgrade.add_argument("--outcome-provider", choices=("generic", "ga4", "mixpanel", "posthog"), default="generic")
    commercial_upgrade.add_argument("--outcome-config", type=Path)
    _add_product_discovery_options(commercial_upgrade)
    commercial_upgrade.set_defaults(mode="full")
    commercial_upgrade.add_argument("--compact", action="store_true")

    finalize_design = subparsers.add_parser(
        "finalize-design",
        help="promote a gallery decision inside the isolated upgrade output and rebuild its patch",
    )
    finalize_design.add_argument("upgrade_output")
    finalize_design.add_argument("decision", type=Path, help="design-decision.json downloaded from the gallery")
    finalize_design.add_argument("--compact", action="store_true")

    design_ui = subparsers.add_parser(
        "design-ui",
        help="按需渲染隔离升级输出中的设计决策工作台；默认流程不会启动 UI",
    )
    design_ui.add_argument("upgrade_output", help="包含 design-gallery/design-review.json 的升级输出目录")
    design_ui.add_argument("--compact", action="store_true")

    validate_transformation_cmd = subparsers.add_parser(
        "validate-transformation",
        help="validate runnable Before/After directories in Chromium at desktop, tablet, and mobile widths",
    )
    validate_transformation_cmd.add_argument("before_dir")
    validate_transformation_cmd.add_argument("after_dir")
    validate_transformation_cmd.add_argument("output_dir")
    validate_transformation_cmd.add_argument("--browser-executable", type=Path)
    validate_transformation_cmd.add_argument("--browser-single-process", action="store_true")
    validate_transformation_cmd.add_argument("--journey", type=Path)
    validate_transformation_cmd.add_argument("--compact", action="store_true")

    measure_outcome_cmd = subparsers.add_parser(
        "measure-outcome",
        help="compare baseline and post-change GA4, Mixpanel, PostHog, or generic event exports",
    )
    measure_outcome_cmd.add_argument("baseline_events")
    measure_outcome_cmd.add_argument("after_events")
    measure_outcome_cmd.add_argument("output_dir")
    measure_outcome_cmd.add_argument("--provider", choices=("generic", "ga4", "mixpanel", "posthog"), default="generic")
    measure_outcome_cmd.add_argument("--config", type=Path)
    measure_outcome_cmd.add_argument("--compact", action="store_true")


    experience = subparsers.add_parser("experience-plan", help="build the UI Experience Core and an interactive preview studio")
    experience.add_argument("project_root")
    experience.add_argument("output_dir")
    experience.add_argument("--business-context", type=Path)
    experience.add_argument("--project-reference", type=Path)
    experience.add_argument("--title")
    experience.add_argument("--pattern", choices=tuple(item.id for item in PATTERNS), help="explicitly override the selected page pattern")
    experience.add_argument("--skeleton", help="explicitly override the routed page skeleton by catalog id")
    experience.add_argument("--visual-direction", choices=tuple(item["id"] for item in direction_catalog()), help="explicitly override the visual direction")
    experience.add_argument("--figma-json", type=Path, help="offline Figma REST JSON export")
    experience.add_argument("--figma-reference", help="Figma URL or file key; token comes from FIGMA_ACCESS_TOKEN")
    experience.add_argument("--screenshot", type=Path, help="UI screenshot for local visual analysis")
    experience.add_argument("--multimodal-overlay", type=Path, help="optional host-generated semantic overlay JSON for screenshot input")
    experience.add_argument("--target-framework", choices=("react","vue","svelte","html"))
    experience.add_argument("--candidate-count", type=int, choices=(1, 2, 3), default=3, help="candidate count 1–3; default 3 for compatibility")
    experience.add_argument("--compact", action="store_true")

    design_pipeline = subparsers.add_parser("design-pipeline", help="run visual input, aesthetic candidates, component mapping, visual builder and production scaffold")
    design_pipeline.add_argument("project_root"); design_pipeline.add_argument("output_dir")
    design_pipeline.add_argument("--experience-plan", type=Path); design_pipeline.add_argument("--business-context", type=Path)
    design_pipeline.add_argument("--figma-json", type=Path); design_pipeline.add_argument("--figma-reference")
    design_pipeline.add_argument("--screenshot", type=Path); design_pipeline.add_argument("--multimodal-overlay", type=Path)
    design_pipeline.add_argument("--target-framework", choices=("react","vue","svelte","html")); design_pipeline.add_argument("--candidate-count", type=int, choices=(1, 2, 3), default=3, help="candidate count 1–3; default 3 for compatibility")
    design_pipeline.add_argument("--title"); design_pipeline.add_argument("--compact", action="store_true")

    figma_import = subparsers.add_parser("figma-import", help="import offline Figma JSON or an explicit Figma REST reference into neutral Design IR")
    figma_import.add_argument("source"); figma_import.add_argument("output_dir")
    figma_import.add_argument("--rest", action="store_true", help="treat source as Figma URL/file key and use FIGMA_ACCESS_TOKEN")
    figma_import.add_argument("--compact", action="store_true")

    screenshot_import = subparsers.add_parser("screenshot-import", help="analyse a screenshot locally and emit neutral Design IR")
    screenshot_import.add_argument("image"); screenshot_import.add_argument("output_dir")
    screenshot_import.add_argument("--multimodal-overlay", type=Path); screenshot_import.add_argument("--compact", action="store_true")

    registry = subparsers.add_parser("component-registry", help="show license-aware production component sources and recipes")
    registry.add_argument("--project-root", type=Path); registry.add_argument("--component", action="append", default=[]); registry.add_argument("--framework", choices=("react","vue","svelte","html")); registry.add_argument("--compact", action="store_true")

    production = subparsers.add_parser("production-plan", help="map an Experience Core plan to local and permissively licensed production components")
    production.add_argument("project_root"); production.add_argument("experience_plan"); production.add_argument("output_dir")
    production.add_argument("--design-ir", type=Path); production.add_argument("--target-framework", choices=("react","vue","svelte","html")); production.add_argument("--compact", action="store_true")

    visual_builder = subparsers.add_parser("visual-builder", help="create the local drag-and-drop Design IR editor")
    visual_builder.add_argument("experience_plan"); visual_builder.add_argument("output_dir")
    visual_builder.add_argument("--design-ir", type=Path); visual_builder.add_argument("--candidates", type=Path); visual_builder.add_argument("--production-plan", type=Path); visual_builder.add_argument("--title")

    catalog = subparsers.add_parser("experience-catalog", help="list supported enterprise patterns and visual directions")
    catalog.add_argument("--compact", action="store_true")
    catalog.add_argument("--full", action="store_true", help="emit the complete production pattern library")

    repair = subparsers.add_parser("ux-repair-plan", help="detect layout, interaction, responsive, and visual consistency repair opportunities")
    repair.add_argument("project_root"); repair.add_argument("output")
    repair.add_argument("--compact", action="store_true")

    token_map = subparsers.add_parser("design-system-map", help="extract and normalise project visual tokens without replacing the existing design language")
    token_map.add_argument("project_root"); token_map.add_argument("output")
    token_map.add_argument("--compact", action="store_true")

    render_experience = subparsers.add_parser("render-experience-preview", help="render an existing Experience Core JSON into an interactive preview")
    render_experience.add_argument("experience_plan")
    render_experience.add_argument("output_dir")
    render_experience.add_argument("--title")

    evaluate = subparsers.add_parser("evaluate-experience", help="compare outcome metrics instead of relying on pixel change alone")
    evaluate.add_argument("before_metrics")
    evaluate.add_argument("after_metrics")
    evaluate.add_argument("--visual-review", type=Path)
    evaluate.add_argument("--compact", action="store_true")

    modernization = subparsers.add_parser("modernization-plan", help="turn an Experience Core plan into a user-value-led modernization strategy")
    modernization.add_argument("experience_plan")
    modernization.add_argument("output")
    modernization.add_argument("--compact", action="store_true")

    preflight = subparsers.add_parser("commercial-preflight", help="block GA while legal, support or external-proof items remain open")
    preflight.add_argument("package_root", nargs="?", default=".")
    preflight.add_argument("--evidence-root", type=Path)
    preflight.add_argument("--candidate-archive", type=Path)
    preflight.add_argument("--compact", action="store_true")

    digest = subparsers.add_parser("digest-plan", help="print the deterministic digest of a complete plan JSON file")
    digest.add_argument("plan")

    manifest = subparsers.add_parser("manifest", help="print an explicit read-only source-scope manifest")
    manifest.add_argument("project_root")
    manifest.add_argument("paths", nargs="+")

    inventory = subparsers.add_parser("ui-inventory", help="全站 UI 资产盘点：统计页面、按钮、颜色、字号、圆角与 UI Drift；只读")
    inventory.add_argument("start_url", help="要扫描的真实 http(s) 起始 URL")
    inventory.add_argument("output_dir", help="JSON、HTML 与截图的输出目录")
    inventory.add_argument("--project-root", type=Path, help="可选源码根目录，用于补充路由发现和 Design Token 对照")
    inventory.add_argument("--route", action="append", default=[], help="额外扫描的站内路由；可重复传入")
    inventory.add_argument("--mode", choices=("quick", "full"), default="full", help="quick 降低单页 DOM 采样上限；full 使用完整采样预算")
    inventory.add_argument("--max-pages", type=int, default=100, help="最多扫描的页面模板数，范围 1..500，默认 100")
    inventory.add_argument("--viewport", default="1440x900", help="盘点视口 WIDTHxHEIGHT，默认 1440x900")
    inventory.add_argument("--allow-origin", action="append", default=[], help="允许加载的额外资源源（origin）；可重复传入")
    inventory.add_argument("--locale", default="zh-CN", help="浏览器 locale，默认 zh-CN")
    inventory.add_argument("--theme", choices=("light", "dark", "no-preference"), default="light", help="浏览器颜色方案")
    inventory.add_argument("--browser", choices=("chromium", "firefox", "webkit"), default="chromium", help="Browser engine；默认 chromium")
    inventory.add_argument("--browser-executable", type=Path, help="显式 Browser 可执行文件；不传时自动探测 Chrome/Edge/Chromium")
    inventory.add_argument("--storage-state", type=Path, help="Playwright storage-state JSON，用于已登录会话；请勿提交到源码仓库")
    inventory.add_argument("--headers", type=Path, help="显式额外 HTTP headers 的 JSON 对象文件")
    inventory.add_argument("--ignore-https-errors", action="store_true", help="仅在受控测试环境忽略 HTTPS 证书错误")
    inventory.add_argument("--compact", action="store_true", help="终端输出紧凑 JSON")

    doctor = subparsers.add_parser("doctor", help="check runtime, schemas, and optional Browser capability")
    doctor.add_argument("--browser-executable", type=Path, help="显式 Browser 路径；不传时自动探测本机 Chrome/Edge/Chromium")
    doctor.add_argument("--compact", action="store_true", help="终端输出紧凑 JSON")

    prepare = subparsers.add_parser("prepare-change-set", help="host-gated API only; CLI cannot verify conversation approval")
    prepare.add_argument("project_root")
    prepare.add_argument("plan")
    prepare.add_argument("changes")

    apply_parser = subparsers.add_parser("apply-change-set", help="host-gated API only; JSON cannot carry trusted approval")
    apply_parser.add_argument("project_root")
    apply_parser.add_argument("change_set")

    rollback = subparsers.add_parser("rollback-change-set", help="host-gated API only; requires in-memory apply receipt")
    rollback.add_argument("project_root")
    rollback.add_argument("change_set")

    browser_report = subparsers.add_parser(
        "validate-browser-report",
        help="validate a redacted legacy Browser Safety Report without granting authority",
    )
    browser_report.add_argument("report")

    # Internal commands remain parseable for compatibility, but normal help only
    # exposes the user-level product surface. Expert mode lists the rest.
    subparsers.metavar = "{run,doctor,auth,expert}"
    subparsers._choices_actions = [
        action for action in subparsers._choices_actions
        if getattr(action, "dest", None) in _PUBLIC_COMMANDS
    ]
    return parser


def _emit(value: Any, *, compact: bool = False, stream: Any | None = None) -> None:
    if stream is None:
        stream = sys.stdout
    if compact:
        text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    else:
        text = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)
    print(text, file=stream)


def _repair_status(result: dict[str, Any]) -> str:
    verification = result.get("repairVerification") if isinstance(result.get("repairVerification"), dict) else {}
    report = result.get("repairReport") if isinstance(result.get("repairReport"), dict) else {}
    return str(verification.get("status") or report.get("status") or result.get("status") or "NOT_VERIFIED").upper()


def _ci_exit_for_repair_status(status: str) -> int:
    value = str(status or "NOT_VERIFIED").upper()
    if value == "VERIFIED":
        return 0
    if value == "REVIEW_REQUIRED":
        return 2
    if value in {"NOT_VERIFIED", "SCOPE_NOT_CONFIRMED", "AWAITING_HOST_WRITE", "PARTIAL", "INDETERMINATE"}:
        return 3
    if value in {"FAIL", "FAILED", "BLOCKED", "FRAMEWORK_NOT_SUPPORTED", "REJECTED", "REGRESSED", "INVALID"}:
        return 4
    return 3


def _repair_machine_contract(result: dict[str, Any], *, request: str | None = None) -> dict[str, Any]:
    """Compatibility name for the Beta.3 TaskResult machine contract."""
    task_result = result.get("taskResult") if isinstance(result.get("taskResult"), dict) else build_task_result(result, request=request)
    return dict(task_result)


def _emit_human_repair_report(result: dict[str, Any], *, request: str | None = None, stream: Any | None = None) -> None:
    """Render the thin four-part Human Task Report.

    Machine reason codes, digests, run IDs, receipt protocol details and the
    evidence graph remain available through ``--json`` / ``--expert-json`` but
    are deliberately not the default user surface.
    """
    if stream is None:
        stream = sys.stdout
    task = result.get("taskResult") if isinstance(result.get("taskResult"), dict) else build_task_result(result, request=request)
    outcome = str(task.get("outcome") or "NOT_VERIFIED")
    outcome_upper = outcome.upper()
    if outcome_upper == "VERIFIED":
        user_state = "已完成并验证"
    elif outcome_upper in {"FAILED", "FAIL", "BLOCKED", "AUTH_REQUIRED", "SCOPE_NOT_CONFIRMED", "AWAITING_HOST_WRITE", "USER_ACTION_REQUIRED"}:
        user_state = "需要你处理"
    else:
        user_state = "已完成但部分未验证"

    print("结果：", file=stream)
    print(f"- {user_state}。", file=stream)
    print(f"- 原因：{human_status_explanation(outcome)}", file=stream)
    if outcome_upper in {"AUTH_REQUIRED"}:
        owner = "你需要先完成当前页面或宿主要求的认证。"
        continuity = "认证完成后可以继续同一任务；写权限不会因恢复自动获得。"
    elif outcome_upper in {"AWAITING_HOST_WRITE"}:
        owner = "当前宿主/工作区需要先确认并应用本次实际文件修改。"
        continuity = "宿主确认后可以继续验证，不需要重新开始分析。"
    elif outcome_upper in {"SCOPE_NOT_CONFIRMED"}:
        owner = "你只需要确认当前最小修改范围；系统不会在范围不明时冒险写入。"
        continuity = "确认范围后可以继续。"
    elif outcome_upper in {"FAILED", "FAIL", "BLOCKED"}:
        owner = "先处理上方已经确定的失败条件；系统不会用视觉结果覆盖它。"
        continuity = "阻断解除后可以重新验证。"
    else:
        owner = "系统会继续使用现有任务状态补齐缺失证据；仅在确实需要授权时再请你处理。"
        continuity = "可以继续；当前状态不会被误报为完全验证。"
    print(f"- 需要谁处理：{owner}", file=stream)
    print(f"- 是否可以继续：{continuity}", file=stream)

    changes = [str(item) for item in list(task.get("changes") or []) if str(item).strip()]
    print("\n改了什么：", file=stream)
    if changes:
        for item in changes[:8]:
            print(f"- {item}", file=stream)
    else:
        print("- 本次没有记录源码修改。", file=stream)

    verification = task.get("verification") if isinstance(task.get("verification"), dict) else {}
    coverage = task.get("coverage") if isinstance(task.get("coverage"), dict) else {}
    print("\n验证了什么：", file=stream)
    browser = str(verification.get("browser") or "NOT_MEASURED").upper()
    host_write = str(verification.get("hostWrite") or "NOT_APPLICABLE").upper()
    tools = str(verification.get("projectTools") or "NOT_APPLICABLE").upper()
    drift = str(verification.get("projectDrift") or "NOT_APPLICABLE").upper()
    if browser in {"PASS", "VERIFIED", "BROWSER_PASS", "IMPROVEMENT_CLAIM_ALLOWED"}:
        print("- 目标页面已在本次浏览器条件下验证。", file=stream)
    else:
        print("- 页面尚未在真实浏览器中完成充分验证。", file=stream)
    before_report = result.get("before") if isinstance(result.get("before"), dict) else {}
    before_summary = before_report.get("coverageSummary") if isinstance(before_report.get("coverageSummary"), dict) else {}
    settings = before_summary.get("settingsSummary") if isinstance(before_summary.get("settingsSummary"), dict) else {}
    if settings.get("plainSummary"):
        print(f"- 设置摘要：{settings['plainSummary']}", file=stream)
    if host_write in {"VERIFIED_V3", "HOST_WRITE_V3_VERIFIED"}:
        print("- 宿主已确认本次实际文件修改。", file=stream)
    elif changes or str(task.get("kind") or "").upper() == "REPAIR":
        print("- 修改尚未得到当前宿主确认，因此暂不能标记为已验证完成。", file=stream)
    if tools == "FAIL":
        print("- 项目检查失败，视觉改善不会覆盖这个失败。", file=stream)
    elif tools not in {"NOT_APPLICABLE", "", "PASS", "VERIFIED"}:
        print("- 项目检查仍有未验证项。", file=stream)
    if drift in {"FAIL", "UNEXPECTED_DRIFT"}:
        print("- 检测到计划范围外的变化，已阻止成功声明。", file=stream)

    covered: list[str] = []
    if coverage.get("patchScope") not in {None, "UNKNOWN", "NOT_APPLICABLE"}:
        covered.append(f"修改范围={coverage.get('patchScope')}")
    if coverage.get("target") not in {None, "UNKNOWN", "NOT_APPLICABLE"}:
        covered.append(f"目标文件={coverage.get('target')}")
    if coverage.get("criticalContext") not in {None, "UNKNOWN", "NOT_APPLICABLE"}:
        covered.append(f"关键上下文={coverage.get('criticalContext')}")
    if covered:
        suffix = "；未覆盖整个仓库。" if str(coverage.get("globalProject") or "").upper() in {"PARTIAL", "UNKNOWN"} else "。"
        print("- 覆盖范围：" + "，".join(covered) + suffix, file=stream)

    raw_next = str(task.get("nextAction") or "").strip()
    lower_next = raw_next.casefold()
    if "receipt" in lower_next or "host" in lower_next or "patch candidate" in lower_next:
        next_action = "请回到当前宿主/工作区应用本次建议修改，然后继续同一任务完成验证。"
    elif "--url" in raw_next or "url" in lower_next:
        next_action = "请提供一个当前可访问的目标页面，或先启动本地应用。"
    elif raw_next:
        next_action = raw_next
    else:
        next_action = "查看上面的未验证项，只处理当前最小阻断后再继续。"
    print("\n下一步：", file=stream)
    print(f"- {next_action}", file=stream)
    state = task.get("taskState") if isinstance(task.get("taskState"), dict) else {}
    if state.get("resumable"):
        print("- 任务已保存，可说“继续上次任务”恢复。", file=stream)

def _configure_stdio() -> None:
    """Keep the installed console entry point UTF-8 on redirected Windows IO.

    Delegates to the shared implementation so the CLI and the acceptance
    scripts cannot drift apart.
    """
    configure_stdout()


def _load_modernization_plan(path: Path) -> dict[str, Any]:
    """Load the minimum Experience Core contract required by modernization-plan."""
    value = load_json(path)
    if not isinstance(value, dict):
        raise ContractViolation("CLI_INPUT_INVALID", ["$: expected an Experience Core object"])
    if value.get("schemaVersion") != "3.0":
        raise ContractViolation("CLI_INPUT_VERSION_UNSUPPORTED", ["$.schemaVersion: expected 3.0"])
    required = ("experienceModel", "selectedPattern", "selectedSkeleton", "interactionContract", "uxRepairPlan")
    missing = [key for key in required if key not in value]
    if missing:
        raise ContractViolation("CLI_INPUT_INVALID", [f"$: missing fields: {', '.join(missing)}"])
    for key in required:
        if not isinstance(value[key], dict):
            raise ContractViolation("CLI_INPUT_INVALID", [f"$.{key}: expected object"])
    return value


def _optional_mapping(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    value = load_json(path)
    if not isinstance(value, dict):
        raise ContractViolation("CLI_INPUT_INVALID", [f"$: expected object in {path.name}"])
    return value


def _prepare_product_discovery(
    project: Path,
    output: Path,
    context: dict[str, Any],
    args: argparse.Namespace,
) -> tuple[dict[str, Any], dict[str, Any] | None, dict[str, Any] | None]:
    """Run one bounded understanding pass and stop until the user confirms."""
    mode = normalize_mode(getattr(args, "mode", None), default="diagnose")
    if getattr(args, "assume_discovery", False):
        raise ContractViolation(
            "SELF_GENERATED_CONFIRMATION_REJECTED",
            ["$: --assume-discovery 已移除；模型或序列化文件不能代替当前对话中的用户确认"],
        )
    confirmation = _optional_mapping(getattr(args, "product_confirmation", None))
    approval = _optional_mapping(getattr(args, "approval_receipt", None))
    if approval:
        confirmation = dict(confirmation or {})
        confirmation["approvalReceipt"] = approval
        # A serialized candidate may carry answers for diagnostics, but it is
        # intentionally rejected as authority.  Real Codex hosts call the
        # in-process API with TrustedWorkflowApproval instead.
        if isinstance(approval.get("answers"), dict):
            confirmation["answers"] = dict(approval["answers"])
        if approval.get("action"):
            confirmation["action"] = approval["action"]
    profile = model_capability_profile(getattr(args, "model_profile", None))

    # A conversational resume reuses the unchanged read-only understanding;
    # it never reuses an approval or silently widens the scope. Answer rounds
    # update only the cached evidence ledger, avoiding another token-heavy
    # reconstruction of the same source tree.
    cached = (
        load_cached_product_discovery(
            project,
            output,
            business_context=context,
            screenshot_paths=getattr(args, "screenshot", []),
            multimodal_overlay=_optional_mapping(getattr(args, "multimodal_overlay", None)),
        )
        if output.exists() else None
    )
    if cached is not None and confirmation:
        discovery = apply_cached_product_confirmation(
            cached,
            confirmation,
            approval_receipt=approval,
            model_profile=profile["id"],
        )
    elif cached is not None:
        discovery = cached
    else:
        discovery = build_product_discovery(
            project,
            business_context=context,
            screenshot_paths=getattr(args, "screenshot", []),
            multimodal_overlay=_optional_mapping(getattr(args, "multimodal_overlay", None)),
            confirmation=confirmation,
            approval_receipt=approval,
            model_profile=profile["id"],
        )
    discovery = dict(discovery)
    discovery["requestedMode"] = mode
    discovery["modelCapabilityProfile"] = profile

    requested_action = str((confirmation or {}).get("action") or "").strip().casefold()
    required_gate_scope = required_scope_for_action(requested_action, mode)
    validation = validate_confirmation(
        confirmation,
        approval=approval,
        required_scope=required_gate_scope,
        required_mode=mode,
    ) if confirmation else {
        "trusted": False,
        "status": "CURRENT_CONVERSATION_APPROVAL_REQUIRED",
        "reason": "首次运行必须先把系统理解卡交给用户核对。",
        "scope": "FULL" if mode == "full" else "DIAGNOSIS",
    }
    audit_only = validation.get("status") == "AUDIT_ONLY" or str((confirmation or {}).get("action") or "") == "audit-only"
    questions_ready = (
        not discovery.get("materialUnknowns")
        and int((discovery.get("questionPolicy") or {}).get("unanswered", 0)) == 0
        and not bool((discovery.get("questionPolicy") or {}).get("scopeIncomplete"))
    )
    # A round acknowledgement is deliberately a terminal action for this
    # invocation.  Even when it resolves the final question, it must return
    # the updated understanding card and wait for a fresh diagnosis/full
    # approval.  This prevents a `full` caller from turning `continue-round`
    # into an implicit design request.
    answer_round_only = is_answer_round_action(requested_action)
    diagnosis_only = is_diagnosis_only_action(requested_action)
    can_continue = (
        bool(validation.get("trusted"))
        and questions_ready
        and discovery.get("status") == "PRODUCT_UNDERSTANDING_READY"
        and not answer_round_only
        and not (diagnosis_only and mode == "full")
    )
    if audit_only:
        can_continue = False
    if output.exists():
        existing = {item.name for item in output.iterdir()}
        if existing - {"system-understanding"}:
            # A completed consultation/upgrade must be resumed by its own
            # command; never overwrite or append to a user decision package.
            if not (output / "system-understanding" / "system-understanding.json").is_file():
                raise ValueError("product discovery can only pause in a new output directory or resume its own understanding output")
    if can_continue:
        return discovery, confirmation, None

    artifacts = export_product_discovery(discovery, output / "system-understanding")
    if audit_only:
        status = "PRODUCT_DISCOVERY_AUDIT_ONLY"
        message = "已停在检测结果；不会生成建议、设计或实施候选。"
        next_action = "如果要讨论改良方案，请在当前对话中先确认系统理解。"
    elif validation.get("status") == "SELF_GENERATED_CONFIRMATION_REJECTED":
        status = "SELF_GENERATED_CONFIRMATION_REJECTED"
        message = "回答文件不能代替当前对话中的用户确认；没有继续执行任何升级阶段。"
        next_action = "请由用户在当前对话中逐项核对未知内容，再由可信宿主绑定不可序列化的确认对象。"
    elif answer_round_only:
        status = str(discovery.get("status") or "PRODUCT_UNDERSTANDING_REVIEW_REQUIRED")
        message = "本轮理解回答已保存；即使问题已全部回答，也不会在同一动作中进入诊断或完整升级。"
        next_action = "请在当前对话中重新确认系统理解，并明确选择只读诊断或完整升级范围。"
    elif diagnosis_only and mode == "full":
        status = "DIAGNOSIS_SCOPE_REQUIRED"
        message = "继续诊断动作不能打开完整升级范围；需要新的完整升级确认。"
        next_action = "先完成只读诊断，若要生成隔离候选，请重新明确要求完整升级。"
    elif not confirmation:
        status = "PRODUCT_UNDERSTANDING_REVIEW_REQUIRED"
        message = "我先重建了系统任务、角色与流程；请在当前对话中核对理解卡。"
        next_action = "先回答理解卡中的每个高影响问题；回答文件本身不会触发设计或写入。"
    elif validation.get("status") in {"CURRENT_CONVERSATION_APPROVAL_REQUIRED", "INVALID_APPROVAL_RECEIPT", "SERIALIZED_APPROVAL_REJECTED", "APPROVAL_PACKET_MISMATCH", "APPROVAL_MODE_MISMATCH", "SCOPE_APPROVAL_REQUIRED", "EXPLICIT_ANSWERS_REQUIRED", "CONFIRMATION_ACTION_INVALID"}:
        status = str(validation.get("status"))
        message = str(validation.get("reason") or "需要当前对话中的用户确认。")
        next_action = "先回答理解卡中的每个高影响问题；回答文件本身不会触发设计或写入。"
    else:
        status = str(discovery.get("status") or "PRODUCT_UNDERSTANDING_REVIEW_REQUIRED")
        message = "我先重建了系统任务、角色与流程；请核对不确定项。"
        next_action = "确认后默认只生成通俗诊断；只有明确要求完整升级时才生成三套隔离候选。"
    payload = {
        "status": status,
        "mode": mode,
        "product": discovery.get("product"),
        "message": message,
        "open": str(output / "system-understanding" / artifacts["workbench"]),
        "openFirst": str(output / "system-understanding" / artifacts["workbench"]),
        "questions": discovery.get("questions"),
        "questionPolicy": discovery.get("questionPolicy"),
        "evidenceSummary": discovery.get("evidenceSummary"),
        "materialUnknowns": discovery.get("materialUnknowns", []),
        "confirmation": discovery.get("confirmation"),
        "nextAction": next_action,
        "resume": {
            "confirmationFile": "product-confirmation.json",
            "approvalReceipt": "current-conversation-only; bind a process-local host approval object (serialized JSON is rejected)",
            "option": "--product-confirmation",
            "approvalOption": "--approval-receipt",
            "mode": mode,
        },
        "sourceProjectChanged": False,
        "patchIntegrationAuthorized": False,
        "modelCapabilityProfile": profile,
    }
    # Return a pause payload even when the scanner itself found no questions;
    # a high-confidence model interpretation is not a user confirmation.
    return discovery, confirmation, payload


def _schema_health(schema_dir: Path) -> dict[str, Any]:
    """Validate schemas in clean hosts, with deeper validation when available."""
    builtin = check_schema_bundle(schema_dir)
    if builtin["status"] != "PASS":
        return builtin
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        return {**builtin, "fullMetaSchemaValidation": "OPTIONAL_DEPENDENCY_NOT_INSTALLED"}
    errors: list[dict[str, str]] = []
    for path in sorted(schema_dir.glob("*.json")):
        try:
            schema = json.loads(path.read_text(encoding="utf-8"))
            Draft202012Validator.check_schema(schema)
        except Exception as error:
            errors.append({"file": path.name, "error": str(error)})
    return {
        "status": "PASS" if not errors else "FAIL",
        "checked": len(list(schema_dir.glob("*.json"))),
        "errors": errors,
        "engine": "jsonschema-draft-2020-12",
        "fullMetaSchemaValidation": "PASS" if not errors else "FAIL",
    }


def _viewports(raw: list[str] | None) -> list[tuple[int, int]] | None:
    if not raw:
        return None
    result: list[tuple[int, int]] = []
    for item in raw:
        try:
            width, height = item.lower().split("x", 1)
            result.append((int(width), int(height)))
        except (ValueError, AttributeError) as error:
            raise ContractViolation("BROWSER_VIEWPORT_INVALID", [f"$: invalid viewport {item!r}"]) from error
    return result


def _finding_exit(report: dict[str, Any], fail_on: str) -> int:
    if fail_on == "none":
        return 0
    threshold = _SEVERITY_ORDER[fail_on]
    return 1 if any(_SEVERITY_ORDER.get(item.get("severity"), 99) <= threshold for item in report.get("findings", [])) else 0


def _approved_request_rows(values: list[str] | None) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for raw in values or []:
        parts = [part.strip() for part in str(raw).split(",", 2)]
        if len(parts) != 3 or not all(parts):
            raise ContractViolation("BROWSER_REQUEST_APPROVAL_INVALID", ["$: --approve-request requires ORIGIN,METHOD,PATH"])
        origin_value, method, path = parts
        if not path.startswith("/"):
            raise ContractViolation("BROWSER_REQUEST_APPROVAL_INVALID", ["$: approved request path must start with /"])
        rows.append({"origin": origin_value, "method": method.upper(), "path": path})
    return rows


def _host_receipt_hmac_key() -> bytes | None:
    value = os.environ.get("WUQ_HOST_RECEIPT_HMAC_KEY")
    return value.encode("utf-8") if value else None


def _result_exit(result: dict[str, Any]) -> int:
    status = str(result.get("status") or "").upper()
    return 1 if status in {"FAIL", "BLOCKED", "FRAMEWORK_NOT_SUPPORTED", "ERROR", "INVALID", "REJECTED"} else 0


def main(argv: list[str] | None = None) -> int:
    _configure_stdio()
    args = _parser().parse_args(argv)
    try:
        if args.command == "auth":
            result = save_auth_profile(args.name, args.storage_state, allowed_origins=args.allow_origin)
            safe = {k: v for k, v in result.items() if k not in {"storageStatePath"}}
            safe["storageState"] = "REGISTERED_OUTSIDE_PROJECT"
            _emit(safe, compact=args.compact)
            return 0

        if args.command == "run":
            request_text = (args.request_option or args.request_text or "").strip()
            if args.request_option and args.request_text and args.request_option.strip() != args.request_text.strip():
                raise ContractViolation("REQUEST_AMBIGUOUS", ["$: provide the task either as positional text or --request, not two different requests"])
            if not request_text:
                raise ContractViolation("REQUEST_REQUIRED", ['$: describe what you want to inspect, fix, or modernize, e.g. web-ui-quality run . "修复订单页移动端错位"'])
            target_path = Path(args.target).expanduser()
            artifacts_root = (target_path.resolve() / ".wuq" / "runs") if target_path.is_dir() else (Path.cwd() / ".wuq" / "runs")
            run_url = args.url or args.after_url
            storage_state = args.storage_state
            auth_state = "anonymous"
            allowed = list(args.allow_origin)
            if args.auth_profile:
                profile = load_auth_profile(args.auth_profile)
                storage_state = Path(profile["storageStatePath"])
                auth_state = f"profile:{args.auth_profile}"
                allowed = sorted(set(allowed) | set(profile.get("allowedOrigins", [])))
            elif storage_state is not None:
                auth_state = "explicit-storage-state"
            target_identity = str(target_path.resolve()) if target_path.exists() else str(args.target)
            stable_task_id = f"cli-task-{digest_json({'target': target_identity})[:16]}"
            existing_run = None
            selected_mode = None
            host_write_receipt = _optional_mapping(args.host_write_receipt)
            host_patch_candidate = _optional_mapping(args.host_patch_candidate)
            host_tool_results = [_optional_mapping(path) for path in args.host_tool_result]
            if host_patch_candidate is not None and not args.after_url:
                candidate_run_id = str(host_patch_candidate.get("runId") or "").strip()
                if not candidate_run_id:
                    raise ContractViolation("HOST_PATCH_CANDIDATE_RUN_MISMATCH", ["$.runId: patch candidate must identify the existing repair run"])
                candidate_dir = artifacts_root / candidate_run_id
                if not candidate_dir.is_dir():
                    raise ContractViolation("HOST_PATCH_CANDIDATE_RUN_MISMATCH", ["$.runId: candidate run is not present under this project artifact root"])
                prior_run = load_experience_run(candidate_dir)
                if str(prior_run.get("taskId")) != stable_task_id:
                    raise ContractViolation("HOST_PATCH_CANDIDATE_RUN_MISMATCH", ["$.runId: candidate run does not belong to the current target task"])
                existing_run = candidate_dir
                session_id = str(prior_run["sessionId"])
                selected_mode = "FIX_AND_VERIFY"
            elif args.after_url:
                run_target_identity, _, _ = _target_identity(args.target, run_url)
                receipt_run_id = str((host_write_receipt or {}).get("runId") or "").strip()
                if receipt_run_id:
                    candidate = artifacts_root / receipt_run_id
                    if not candidate.is_dir():
                        raise ContractViolation("RECEIPT_RUN_NOT_FOUND", ["$.runId: Host receipt refers to a run that is not present under this project artifact root"])
                    prior_run = load_experience_run(candidate)
                    if str(prior_run.get("taskId")) != stable_task_id:
                        raise ContractViolation("RECEIPT_RUN_MISMATCH", ["$.runId: receipt run does not belong to the current target task"])
                    existing_run = candidate
                else:
                    existing_run = find_latest_compatible_run(
                        artifacts_root, task_id=stable_task_id, target_identity=run_target_identity, mode="FIX_AND_VERIFY",
                    )
                    prior_run = load_experience_run(existing_run)
                session_id = str(prior_run["sessionId"])
                selected_mode = "FIX_AND_VERIFY"
            elif host_patch_candidate is None:
                session_id = f"cli-session-{uuid.uuid4().hex[:16]}"
            result = run_experience_fix(
                args.target, artifacts_root, request=request_text, mode=selected_mode,
                task_id=stable_task_id, session_id=session_id, url=run_url,
                existing_run=existing_run, after_url=args.after_url, files=args.file,
                allowed_origins=allowed, approved_requests=_approved_request_rows(args.approve_request), auth_state=auth_state,
                browser_executable=args.browser_executable, storage_state=storage_state,
                host_write_receipt=host_write_receipt, host_patch_candidate=host_patch_candidate,
                host_receipt_hmac_key=_host_receipt_hmac_key(), host_tool_results=host_tool_results,
            )
            if args.compact:
                _emit(result, compact=True)
            elif args.expert_json:
                _emit(result, compact=False)
            elif args.json or args.ci:
                _emit(_repair_machine_contract(result, request=request_text), compact=False)
            else:
                _emit_human_repair_report(result, request=request_text)
            if args.ci or args.require:
                return _ci_exit_for_repair_status(_repair_status(result))
            return _result_exit(result)

        if args.command == "experience-fix":
            local_id = uuid.uuid4().hex[:16]
            result = run_experience_fix(
                args.target, args.artifacts_root, request=args.request, mode=args.mode,
                task_id=args.task_id or f"cli-task-{local_id}", session_id=args.session_id or f"cli-session-{local_id}",
                url=args.url, existing_run=args.existing_run, after_url=args.after_url, files=args.file,
                business_context=_optional_mapping(args.business_context), viewports=_viewports(args.viewport),
                locale=args.locale, theme=args.theme, browser=args.browser, allowed_origins=args.allow_origin, approved_requests=_approved_request_rows(args.approve_request),
                environment=args.environment, user_role=args.user_role, auth_state=args.auth_state,
                test_data_state=args.test_data_state, browser_executable=args.browser_executable, storage_state=args.storage_state,
                host_write_receipt=_optional_mapping(args.host_write_receipt), host_patch_candidate=_optional_mapping(args.host_patch_candidate),
                host_receipt_hmac_key=_host_receipt_hmac_key(), host_tool_results=[_optional_mapping(path) for path in args.host_tool_result],
            )
            _emit(result, compact=args.compact)
            return _result_exit(result)

        if args.command == "ui-inventory":
            viewport_values = _viewports([args.viewport]) or [(1440, 900)]
            result = run_ui_inventory(
                args.start_url, output_dir=args.output_dir, project_root=args.project_root,
                routes=args.route, mode=args.mode, max_pages=args.max_pages, viewport=viewport_values[0],
                locale=args.locale, theme=args.theme, browser_name=args.browser,
                allow_origins=args.allow_origin, storage_state=args.storage_state,
                extra_http_headers=_optional_mapping(args.headers),
                ignore_https_errors=args.ignore_https_errors, browser_executable=args.browser_executable,
            )
            _emit(result, compact=args.compact)
            return _result_exit(result)

        if args.command == "expert":
            _emit({
                "status": "AVAILABLE",
                "message": "普通任务使用 run；旧入口保留为 compatibility，专家与 internal-compatibility 命令不承诺稳定公共 API。",
                "compatibilityCommands": sorted(_COMPATIBILITY_COMMANDS),
                "commands": _EXPERT_COMMAND_DESCRIPTIONS,
                "internalCommands": {name: "internal compatibility surface; not a stable public API" for name in _INTERNAL_COMMANDS},
                "lifecycle": _COMMAND_LIFECYCLE,
            }, compact=args.compact)
            return 0

        if args.command == "fix":
            result = prepare_fix_workflow(
                args.project_root, args.output_dir, files=args.file, evidence=args.evidence, goal=args.goal,
            )
            _emit(result, compact=args.compact)
            return 0

        if args.command == "inspect":
            args.command = "check"
        elif args.command == "redesign":
            args.command = "upgrade"

        if args.command == "audit":
            report = audit_project(
                args.project_root,
                instruction_source=args.instruction_source,
                role=args.role,
                state=args.state,
                project_reference=_optional_mapping(args.project_reference),
                evidence=_optional_mapping(args.evidence),
                business_context=_optional_mapping(args.business_context),
                include_security=bool(getattr(args, "security_audit", False)),
            )
            _emit(report["uiProductCapability"]["evidenceAndDelivery"]["userSummary"] if args.summary else report, compact=args.compact)
            return _finding_exit(report, args.fail_on)

        if args.command == "audit-html-stdin":
            report = audit_html_document(
                sys.stdin.read(),
                source_name=args.source_name,
                source_url=args.source_url,
                instruction_source=args.instruction_source,
                canonicalize_external=args.canonicalize_external,
                role=args.role,
                state=args.state,
                project_reference=_optional_mapping(args.project_reference),
                evidence=_optional_mapping(args.evidence),
                business_context=_optional_mapping(args.business_context),
                include_security=bool(getattr(args, "security_audit", False)),
            )
            _emit(report["uiProductCapability"]["evidenceAndDelivery"]["userSummary"] if args.summary else report, compact=args.compact)
            return _finding_exit(report, args.fail_on)

        if args.command == "check":
            report = run_smart_acceptance(
                args.target,
                output_dir=args.output_dir,
                url=args.url,
                business_context=_optional_mapping(args.business_context),
                journey_steps=load_json(args.journey) if args.journey else None,
                viewports=_viewports(args.viewport),
                locale=args.locale,
                theme=args.theme,
                allow_origins=args.allow_origin,
                environment=args.environment,
                browser_name=args.browser,
                storage_state=args.storage_state,
                extra_http_headers=_optional_mapping(args.headers),
                ignore_https_errors=args.ignore_https_errors, browser_executable=args.browser_executable,
            )
            _emit(report, compact=args.compact)
            return 1 if report.get("status") in {"FAIL", "BLOCKED"} else 0

        if args.command == "source-check":
            report = run_source_assurance(
                args.project_root, output_dir=args.output_dir, files=args.file,
                base_ref=args.base_ref, intent=args.intent,
            )
            _emit(report, compact=args.compact)
            return 1 if report.get("status") in {"FAIL", "BLOCKED"} else 0

        if args.command == "quick-ui":
            report = run_quick_ui(
                args.url,
                output_dir=args.output_dir,
                viewports=_viewports(args.viewport),
                locale=args.locale,
                theme=args.theme,
                allow_origins=args.allow_origin,
                browser_name=args.browser,
                storage_state=args.storage_state,
                extra_http_headers=_optional_mapping(args.headers),
                ignore_https_errors=args.ignore_https_errors, browser_executable=args.browser_executable,
            )
            _emit(report, compact=args.compact)
            return 1 if report["status"] == "FAIL" else 0

        if args.command == "browser-compare":
            report, _receipt = compare_pages(
                args.before_url,
                args.after_url,
                output_dir=args.output_dir,
                viewports=_viewports(args.viewport),
                locale=args.locale,
                theme=args.theme,
                allow_origins=args.allow_origin,
                browser_name=args.browser,
                journey_steps=load_json(args.journey) if args.journey else None,
                allow_submit=args.allow_submit,
                trace=not args.no_trace,
                visual_diff=not args.no_visual_diff,
                storage_state=args.storage_state, extra_http_headers=_optional_mapping(args.headers),
                ignore_https_errors=args.ignore_https_errors, axe_script=args.axe_script,
                approved_action_ids=args.approve_action, browser_executable=args.browser_executable,
            )
            _emit(report, compact=args.compact)
            return 1 if report["status"] == "FAIL" else 0

        if args.command == "audit-and-compare":
            browser_report, receipt = compare_pages(
                args.before_url,
                args.after_url,
                output_dir=args.output_dir,
                viewports=_viewports(args.viewport),
                locale=args.locale,
                theme=args.theme,
                allow_origins=args.allow_origin,
                browser_name=args.browser,
                journey_steps=load_json(args.journey) if args.journey else None,
                allow_submit=args.allow_submit,
                trace=not args.no_trace,
                visual_diff=not args.no_visual_diff,
                storage_state=args.storage_state, extra_http_headers=_optional_mapping(args.headers),
                ignore_https_errors=args.ignore_https_errors, axe_script=args.axe_script,
                approved_action_ids=args.approve_action, browser_executable=args.browser_executable,
            )
            report = audit_project(
                args.project_root,
                role=args.role,
                state=args.state,
                project_reference=_optional_mapping(args.project_reference),
                business_context=_optional_mapping(args.business_context),
                trusted_browser_evidence=receipt,
                include_security=bool(getattr(args, "security_audit", False)),
            )
            report["browserComparisonReport"] = browser_report
            _emit(report["uiProductCapability"]["evidenceAndDelivery"]["userSummary"] if args.summary else report, compact=args.compact)
            return 1 if report["verificationReport"]["result"] == "FAIL" else 0

        if args.command == "lighthouse":
            result = run_lighthouse(args.url, output_dir=args.output_dir, executable=args.executable)
            _emit(result, compact=args.compact)
            return 1 if result.get("status") == "FAIL" else 0

        if args.command == "full-audit":
            report = run_full_audit(
                args.project_root, args.before_url, args.after_url, output_dir=args.output_dir,
                business_context=_optional_mapping(args.business_context), project_reference=_optional_mapping(args.project_reference),
                journey_steps=load_json(args.journey) if args.journey else None, viewports=_viewports(args.viewport),
                storage_state=args.storage_state, extra_http_headers=_optional_mapping(args.headers),
                allow_origins=args.allow_origin, approved_action_ids=args.approve_action, axe_script=args.axe_script,
                run_lighthouse_engine=args.lighthouse, lighthouse_executable=args.lighthouse_executable,
                visual_review=_optional_mapping(args.visual_review), browser_name=args.browser, browser_executable=args.browser_executable,
                locale=args.locale, theme=args.theme, ignore_https_errors=args.ignore_https_errors,
                trace=not args.no_trace, visual_diff=not args.no_visual_diff,
            )
            _emit(report, compact=args.compact)
            return 1 if report.get("overallResult") == "FAIL" else 0

        if args.command == "visual-review-template":
            value = review_template()
            if args.output:
                args.output.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
                _emit({"status":"PASS","output":str(args.output)})
            else: _emit(value)
            return 0

        if args.command == "render-report":
            path = generate_html_report(load_json(Path(args.report)), output_dir=args.output_dir)
            _emit({"status":"PASS","report":str(path)})
            return 0

        if args.command == "serve-report":
            serve_report(args.report_dir, host=args.host, port=args.port, open_browser=args.open_browser)
            return 0

        if args.command == "export-collaboration":
            _emit(export_collaboration_bundle(load_json(Path(args.report)), args.output_dir))
            return 0

        if args.command == "record-review":
            _emit(record_review(args.review_file, report_digest=args.report_digest, reviewer=args.reviewer, decision=args.decision, comment=args.comment))
            return 0

        if args.command == "consult":
            context = dict(_optional_mapping(args.business_context) or {})
            if args.goal:
                context["consultantIntent"] = args.goal
            if args.screenshot:
                context["screenshot"] = True
            report = audit_project(args.project_root, business_context=context)
            core = report.get("experienceCore") if isinstance(report.get("experienceCore"), dict) else {}
            product = report.get("productizationPlan") if isinstance(report.get("productizationPlan"), dict) else {}
            model = dict(core.get("experienceModel") or {}) if isinstance(core.get("experienceModel"), dict) else dict(context)
            if args.goal:
                model["consultantIntent"] = args.goal
            if args.screenshot:
                model["screenshot"] = True
            overlay = _optional_mapping(args.multimodal_overlay)
            screenshot_result: dict[str, Any] = {}
            screenshot_model = None
            if args.screenshot:
                screenshot_result = analyse_screenshot(args.screenshot, multimodal_overlay=overlay)
                if isinstance(screenshot_result.get("experienceModel"), dict):
                    screenshot_model = screenshot_result["experienceModel"]
            diagnosis = analyze_experience_project(
                args.project_root,
                model,
                page_modes=product.get("pageModes", []),
                screenshot_model=screenshot_model,
                framework=args.target_framework,
            )
            exported = export_experience_analysis(
                diagnosis,
                args.output_dir,
                title=args.title,
                source_screenshot=args.screenshot,
            )
            consultation = diagnosis.get("experienceConsultant") if isinstance(diagnosis.get("experienceConsultant"), dict) else {}
            visible_problems = [
                {key: item.get(key) for key in ("title", "whyItMatters", "suggestion", "impact", "confidence")}
                for item in consultation.get("topProblems", [])
                if isinstance(item, dict)
            ]
            visible_directions = [
                {
                    key: item.get(key)
                    for key in (
                        "id", "name", "summary", "bestFor", "tradeoff",
                        "recommended", "whyRecommended", "actionLabel",
                    )
                }
                for item in consultation.get("directions", [])
                if isinstance(item, dict)
            ]
            result = {
                "status": consultation.get("status"),
                "message": consultation.get("opening"),
                "businessSummary": consultation.get("businessSummary"),
                "topProblems": visible_problems,
                "directions": visible_directions,
                "selectedDirectionId": consultation.get("selectedDirectionId"),
                "open": exported.get("consultantPreview"),
                "artifacts": {
                    "consultation": exported.get("experienceConsultant"),
                    "technicalDiagnosis": exported.get("diagnosis"),
                    "experienceProof": exported.get("experienceProof"),
                },
                "nextStep": consultation.get("guidedFlow", {}).get("nextAction") if isinstance(consultation.get("guidedFlow"), dict) else None,
                "claimBoundary": consultation.get("claimBoundary"),
                "screenshotStatus": screenshot_result.get("status") if screenshot_result else None,
            }
            _emit(result, compact=args.compact)
            return 0

        if args.command == "upgrade":
            context = dict(_optional_mapping(args.business_context) or {})
            if args.product_name:
                context["productName"] = args.product_name
            if args.product_type:
                context["productType"] = args.product_type
            if hasattr(args, "directions"):
                context["designCandidateCount"] = int(args.directions)
            journey_value = load_json(args.journey) if args.journey else None
            if journey_value is not None and not isinstance(journey_value, list):
                raise ContractViolation("JOURNEY_INVALID", ["$: upgrade journey must be a JSON array"])
            if bool(args.baseline_events) != bool(args.after_events):
                raise ContractViolation("OUTCOME_INPUT_INCOMPLETE", ["$: baseline-events and after-events must be supplied together"])
            project = Path(args.project_root).expanduser().resolve()
            if args.output_dir:
                output = Path(args.output_dir).expanduser().resolve()
            else:
                base = project.parent / f"{project.name}-experience-upgrade"
                output = base
                suffix = 2
                while output.exists() and any(output.iterdir()):
                    output = base.with_name(f"{base.name}-{suffix}")
                    suffix += 1
            discovery, confirmation, pause = _prepare_product_discovery(project, output, context, args)
            if pause:
                _emit(pause, compact=args.compact)
                return 0
            result = run_commercial_upgrade(
                project, output, business_context=context,
                product_name=args.product_name or context.get("productName"),
                product_type=args.product_type, browser_executable=args.browser_executable,
                journey=journey_value, baseline_events=args.baseline_events, after_events=args.after_events,
                outcome_provider=args.outcome_provider, outcome_config=_optional_mapping(args.outcome_config),
                product_confirmation=confirmation, product_discovery=discovery,
                approval_receipt=_optional_mapping(getattr(args, "approval_receipt", None)),
                mode=normalize_mode(args.mode, default="diagnose"),
                security_audit=bool(getattr(args, "security_audit", False)),
                model_profile=getattr(args, "model_profile", None),
                design_ui=bool(getattr(args, "design_ui", False)),
            )
            if result.get("mode") == "diagnose":
                _emit({
                    "status": result.get("status"), "mode": "diagnose", "product": result.get("product"),
                    "message": "已完成只读产品诊断；没有生成设计候选，也没有修改目标项目。",
                    "open": str(output / "consultation" / "product-experience-brief" / "index.html"),
                    "report": str(output / "commercial-release-report.html"),
                    "nextAction": "先确认诊断与推荐方向；只有明确要求完整升级时才生成隔离候选。",
                    "gates": result.get("gates"), "sourceProjectChanged": False, "patchIntegrationAuthorized": False,
                }, compact=args.compact)
                return 0 if result.get("status") == "PRODUCT_DIAGNOSIS_READY" else 1
            ui = result.get("ui") if isinstance(result.get("ui"), Mapping) else {}
            open_artifact = (
                str(output / str(ui.get("artifact")))
                if ui.get("status") == "RENDERED" and ui.get("artifact")
                else None
            )
            _emit({
                "status": result.get("status"), "mode": result.get("mode"), "product": result.get("product"), "selectedVariantId": result.get("selectedVariantId"),
                "message": "已生成隔离设计候选；现在只需要比较并确认一个方向。",
                "open": open_artifact, "openFirst": open_artifact, "ui": ui,
                "report": str(output / "commercial-release-report.html"), "decision": result.get("decision"),
                "nextAction": (result.get("decision") or {}).get("nextActions", ["按需运行 design-ui"])[0],
                "nonTechnicalSteps": ["比较候选作品", "切换 Before / After 与设备", "确认方向", "交给 Codex 定稿"],
                "gates": result.get("gates"), "sourceProjectChanged": False, "patchIntegrationAuthorized": False,
            }, compact=args.compact)
            return 0 if result.get("status") == "COMMERCIAL_WORKFLOW_PASS" else 1

        if args.command == "commercial-upgrade":
            context = dict(_optional_mapping(args.business_context) or {})
            if args.product_name:
                context["productName"] = args.product_name
            if args.product_type:
                context["productType"] = args.product_type
            journey_value = load_json(args.journey) if args.journey else None
            if journey_value is not None and not isinstance(journey_value, list):
                raise ContractViolation("JOURNEY_INVALID", ["$: commercial-upgrade journey must be a JSON array"])
            if bool(args.baseline_events) != bool(args.after_events):
                raise ContractViolation("OUTCOME_INPUT_INCOMPLETE", ["$: baseline-events and after-events must be supplied together"])
            project = Path(args.project_root).expanduser().resolve()
            output = Path(args.output_dir).expanduser().resolve()
            discovery, confirmation, pause = _prepare_product_discovery(project, output, context, args)
            if pause:
                _emit(pause, compact=args.compact)
                return 0
            result = run_commercial_upgrade(
                project,
                output,
                business_context=context,
                product_name=args.product_name,
                product_type=args.product_type,
                target_framework=args.target_framework,
                browser_executable=args.browser_executable,
                browser_single_process=args.browser_single_process,
                journey=journey_value,
                baseline_events=args.baseline_events,
                after_events=args.after_events,
                outcome_provider=args.outcome_provider,
                outcome_config=_optional_mapping(args.outcome_config),
                product_confirmation=confirmation,
                product_discovery=discovery,
                approval_receipt=_optional_mapping(getattr(args, "approval_receipt", None)),
                mode=normalize_mode(args.mode, default="full"),
                security_audit=bool(getattr(args, "security_audit", False)),
                model_profile=getattr(args, "model_profile", None),
                design_ui=bool(getattr(args, "design_ui", False)),
            )
            ui = result.get("ui") if isinstance(result.get("ui"), Mapping) else {}
            open_artifact = (
                str(Path(output) / str(ui.get("artifact")))
                if result.get("mode") == "full" and ui.get("status") == "RENDERED" and ui.get("artifact")
                else ("consultation/product-experience-brief/index.html" if result.get("mode") != "full" else None)
            )
            _emit({
                "status": result.get("status"),
                "release": result.get("generator"),
                "product": result.get("product"),
                "decision": result.get("decision"),
                "gates": result.get("gates"),
                "open": open_artifact,
                "openFirst": open_artifact,
                "ui": ui,
                "nextAction": ((result.get("decision") or {}).get("nextActions") or ["按需运行 design-ui"])[0] if result.get("mode") == "full" else "先确认只读诊断与推荐方向。",
                "report": "commercial-release-report.json",
                "sourceProjectChanged": result.get("sourceProjectChanged"),
                "patchIntegrationAuthorized": result.get("patchIntegrationAuthorized"),
            }, compact=args.compact)
            return 0 if result.get("status") == "COMMERCIAL_WORKFLOW_PASS" else 1

        if args.command == "design-ui":
            upgrade_output = Path(args.upgrade_output).expanduser().resolve()
            gallery_dir = upgrade_output / "design-gallery"
            report_path = gallery_dir / "design-review.json"
            if not report_path.is_file():
                raise ContractViolation(
                    "DESIGN_REVIEW_REQUIRED",
                    [f"$: missing {report_path}; run an isolated upgrade first"],
                )
            report_value = load_json(report_path)
            if not isinstance(report_value, Mapping):
                raise ContractViolation("DESIGN_REVIEW_INVALID", ["$: design-review.json must contain an object"])
            rendered_report = dict(report_value)
            rendered_report["ui"] = {"requested": True, "status": "RENDERED"}
            ui_state = {"requested": True, **render_design_gallery(rendered_report, gallery_dir)}
            rendered_report["ui"] = ui_state
            report_path.write_text(
                json.dumps(rendered_report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            release = refresh_commercial_ui_state(upgrade_output, ui_state)
            _emit({
                "status": "DESIGN_UI_RENDERED",
                "mode": "on-demand",
                "open": str(gallery_dir / "index.html"),
                "openFirst": str(gallery_dir / "index.html"),
                "artifacts": {
                    "workbench": str(gallery_dir / "index.html"),
                    "brief": str(gallery_dir / "executive-decision-brief.md"),
                    "designReview": str(report_path),
                },
                "releaseReportUpdated": release is not None,
                "sourceProjectChanged": False,
            }, compact=args.compact)
            return 0

        if args.command == "finalize-design":
            result = finalize_design_selection(args.upgrade_output, args.decision)
            _emit(result, compact=args.compact)
            return 0

        if args.command == "validate-transformation":
            journey_value = load_json(args.journey) if args.journey else []
            if not isinstance(journey_value, list):
                raise ContractViolation("JOURNEY_INVALID", ["$: journey must be a JSON array"])
            result = validate_transformation(
                args.before_dir,
                args.after_dir,
                args.output_dir,
                browser_executable=args.browser_executable,
                journey=journey_value,
                single_process=args.browser_single_process,
            )
            _emit(result, compact=args.compact)
            return 0 if result.get("status") in {"PASS", "PASS_WITH_WARNINGS"} else 1

        if args.command == "measure-outcome":
            result = measure_outcome(
                args.baseline_events,
                args.after_events,
                provider=args.provider,
                config=_optional_mapping(args.config),
            )
            schema_dir = Path(__file__).resolve().parent / "schemas"
            validate_instance(
                result,
                json.loads((schema_dir / "outcome-measurement.schema.json").read_text(encoding="utf-8")),
                base_dir=schema_dir,
            )
            artifacts = export_outcome_report(result, args.output_dir)
            _emit({"status": result["status"], "decision": result["decision"], "artifacts": artifacts}, compact=args.compact)
            return 0 if result.get("status") == "PASS" else 1

        if args.command == "product-consult":
            context = dict(_optional_mapping(args.business_context) or {})
            if args.goal:
                context["consultantIntent"] = args.goal
            if args.product_type:
                context["productType"] = args.product_type
            if args.product_name:
                context["productName"] = args.product_name
            if args.screenshot:
                context["screenshot"] = True
            audit = audit_project(args.project_root, business_context=context, include_security=bool(getattr(args, "security_audit", False)))
            out = Path(args.output_dir).expanduser().resolve()
            out.mkdir(parents=True, exist_ok=True)
            if audit.get("status") == "NOT_APPLICABLE":
                (out / "audit-result.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
                _emit({
                    "status": "NOT_APPLICABLE",
                    "reason": "AUDIT_SCOPE_EMPTY",
                    "message": "没有发现可分析的 Web UI 源码；请提供页面源码、截图或正确的项目目录。",
                    "artifacts": {"audit": "audit-result.json"},
                }, compact=args.compact)
                return 0
            core = audit.get("experienceCore") if isinstance(audit.get("experienceCore"), dict) else {}
            productization = audit.get("productizationPlan") if isinstance(audit.get("productizationPlan"), dict) else {}
            model = dict(core.get("experienceModel") or {}) if isinstance(core.get("experienceModel"), dict) else dict(context)
            model.update({key: value for key, value in context.items() if value not in (None, "")})
            overlay = _optional_mapping(args.multimodal_overlay)
            screenshot_result: dict[str, Any] = {}
            screenshot_model = None
            if args.screenshot:
                screenshot_result = analyse_screenshot(args.screenshot, multimodal_overlay=overlay)
                if isinstance(screenshot_result.get("experienceModel"), dict):
                    screenshot_model = screenshot_result["experienceModel"]
            diagnosis = analyze_experience_project(
                args.project_root,
                model,
                page_modes=productization.get("pageModes", []),
                screenshot_model=screenshot_model,
                framework=args.target_framework,
            )
            diagnosis_artifacts = export_experience_analysis(
                diagnosis,
                out / "technical-analysis",
                title=args.product_name,
                source_screenshot=args.screenshot,
            )
            report = build_product_experience_report(
                diagnosis,
                business_context=context,
                product_name=args.product_name,
            )
            schema_dir = Path(__file__).resolve().parent / "schemas"
            schema = json.loads((schema_dir / "product-experience-report.schema.json").read_text(encoding="utf-8"))
            validate_instance(report, schema, base_dir=schema_dir)
            artifacts = export_product_experience_report(report, out)
            validation = json.loads((out / artifacts["validation"]).read_text(encoding="utf-8"))
            _emit({
                "status": report["status"],
                "release": release_identity(),
                "consultationValidation": validation.get("status"),
                "message": report.get("opening"),
                "product": report["product"],
                "topProblems": [
                    {key: item.get(key) for key in ("title", "whyItMatters", "suggestion", "impact")}
                    for item in report.get("topProblems", [])
                ],
                "recommendedDirection": report.get("executiveBrief", {}).get("recommendedTransformation"),
                "open": artifacts["brief"],
                "artifacts": {**artifacts, "technicalAnalysis": diagnosis_artifacts},
                "sourceWriteAuthorized": False,
                "screenshotStatus": screenshot_result.get("status") if screenshot_result else None,
            }, compact=args.compact)
            return 0 if validation.get("status") == "PASS" else 1

        if args.command == "experience-analyze":
            context = dict(_optional_mapping(args.business_context) or {})
            report = audit_project(args.project_root, business_context=context)
            core = report.get("experienceCore") if isinstance(report.get("experienceCore"), dict) else {}
            product = report.get("productizationPlan") if isinstance(report.get("productizationPlan"), dict) else {}
            overlay = _optional_mapping(args.multimodal_overlay)
            screenshot_result: dict[str, Any] = {}
            screenshot_model = None
            if args.screenshot:
                screenshot_result = analyse_screenshot(args.screenshot, multimodal_overlay=overlay)
                if isinstance(screenshot_result.get("experienceModel"), dict):
                    screenshot_model = screenshot_result["experienceModel"]
            diagnosis = analyze_experience_project(
                args.project_root,
                core.get("experienceModel") if isinstance(core.get("experienceModel"), dict) else context,
                page_modes=product.get("pageModes", []),
                screenshot_model=screenshot_model,
                framework=args.target_framework,
            )
            exported = export_experience_analysis(
                diagnosis,
                args.output_dir,
                title=args.title,
                source_screenshot=args.screenshot,
                preview=not args.no_preview,
            )
            result = {
                "status": diagnosis.get("status"),
                "analysis": exported,
                "diagnosis": diagnosis,
                "screenshotStatus": screenshot_result.get("status") if screenshot_result else None,
            }
            _emit(result, compact=args.compact)
            return 0

        if args.command == "experience-plan":
            context = dict(_optional_mapping(args.business_context) or {})
            if args.pattern:
                context["patternOverride"] = args.pattern
            if args.visual_direction:
                context["visualDirection"] = args.visual_direction
            if args.skeleton:
                get_skeleton(args.skeleton)
                context["skeletonOverride"] = args.skeleton
            report = audit_project(
                args.project_root,
                business_context=context,
                project_reference=_optional_mapping(args.project_reference),
            )
            out = Path(args.output_dir).expanduser().resolve(); out.mkdir(parents=True, exist_ok=True)
            if report.get("status") == "NOT_APPLICABLE":
                audit_path = out / "audit-result.json"
                audit_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
                _emit({
                    "status": "NOT_APPLICABLE",
                    "reason": "AUDIT_SCOPE_EMPTY",
                    "auditResult": "audit-result.json",
                    "designIr": None,
                    "candidateCount": 0,
                    "visualBuilder": None,
                    "productionMapping": {"status": "FRAMEWORK_NOT_SUPPORTED"},
                }, compact=args.compact)
                return 0
            plan = dict(report["experienceCore"])
            overlay = _optional_mapping(args.multimodal_overlay)
            screenshot_model = None
            if args.screenshot:
                screenshot_analysis = analyse_screenshot(args.screenshot, multimodal_overlay=overlay)
                if isinstance(screenshot_analysis.get("experienceModel"), dict):
                    screenshot_model = screenshot_analysis["experienceModel"]
            diagnosis = analyze_experience_project(
                args.project_root,
                plan.get("experienceModel") if isinstance(plan.get("experienceModel"), dict) else context,
                page_modes=report.get("productizationPlan", {}).get("pageModes", []),
                screenshot_model=screenshot_model,
                framework=args.target_framework,
            )
            plan["experienceDiagnosis"] = diagnosis
            plan.pop("experienceDigest", None)
            plan["experienceDigest"] = digest_json(plan)
            report["experienceCore"] = plan
            sidecar = export_experience_analysis(
                diagnosis,
                out,
                title=args.title,
                source_screenshot=args.screenshot,
            )
            plan_path = out / "experience-core.json"
            plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
            preview = generate_experience_preview(plan, out / "preview", title=args.title)
            studio = generate_experience_studio(plan, out / "studio", title=args.title)
            pipeline = run_design_pipeline(
                args.project_root, out / "design-intelligence", experience_plan=plan,
                figma_json=args.figma_json, figma_reference=args.figma_reference, screenshot=args.screenshot,
                multimodal_overlay=overlay, target_framework=args.target_framework,
                candidate_count=args.candidate_count, title=args.title,
            )
            result_status = "FRAMEWORK_NOT_SUPPORTED" if pipeline.get("status") == "FRAMEWORK_NOT_SUPPORTED" else "PASS"
            result = {"status":result_status, "experienceStatus":diagnosis.get("status"), "experienceCore":plan, "plan":"experience-core.json", "preview":"preview/index.html", "studio":"studio/index.html", "modernizationPreview":sidecar.get("preview"), "experienceDiagnosis":sidecar.get("diagnosis"), "designIntelligence":pipeline}
            _emit(result, compact=args.compact)
            return 1 if result_status == "FRAMEWORK_NOT_SUPPORTED" else 0

        if args.command == "design-pipeline":
            result = run_design_pipeline(
                args.project_root, args.output_dir, experience_plan=_optional_mapping(args.experience_plan),
                business_context=_optional_mapping(args.business_context), figma_json=args.figma_json,
                figma_reference=args.figma_reference, screenshot=args.screenshot,
                multimodal_overlay=_optional_mapping(args.multimodal_overlay), target_framework=args.target_framework,
                candidate_count=args.candidate_count, title=args.title,
            )
            _emit(result, compact=args.compact); return 1 if result.get("status") == "FRAMEWORK_NOT_SUPPORTED" else 0

        if args.command == "figma-import":
            result = fetch_and_import_figma(args.source, args.output_dir) if args.rest else import_figma_json(args.source, args.output_dir)
            _emit(result, compact=args.compact); return 0

        if args.command == "screenshot-import":
            result = import_screenshot(args.image, args.output_dir, multimodal_overlay=_optional_mapping(args.multimodal_overlay))
            _emit(result, compact=args.compact); return 0 if result.get("status") == "PASS" else 1

        if args.command == "component-registry":
            if args.project_root:
                stack = detect_framework(args.project_root); framework = args.framework or stack["framework"]
                value = recommend_components(args.component or ["button","input","dialog","data-grid"], framework=framework)
                value["project"] = stack
            else:
                value = {"schemaVersion":"2.2","status":"CATALOG_READY","sources":source_catalog(),"recipes":component_recipes()}
            _emit(value, compact=args.compact); return 0

        if args.command == "production-plan":
            exp = load_json(Path(args.experience_plan)); ir = _optional_mapping(args.design_ir)
            plan = build_production_plan(args.project_root, exp, design_ir=ir, target_framework=args.target_framework)
            result = generate_production_scaffold(plan, exp, args.output_dir)
            status = "FRAMEWORK_NOT_SUPPORTED" if plan.get("status") == "FRAMEWORK_NOT_SUPPORTED" else "PASS"
            _emit({"status":status,"productionPlan":plan,"scaffold":result}, compact=args.compact); return 1 if status == "FRAMEWORK_NOT_SUPPORTED" else 0

        if args.command == "visual-builder":
            path = generate_visual_builder(
                load_json(Path(args.experience_plan)), args.output_dir, design_ir=_optional_mapping(args.design_ir),
                candidates=_optional_mapping(args.candidates), production_plan=_optional_mapping(args.production_plan), title=args.title,
            )
            _emit({"status":"PASS","visualBuilder":"index.html"}); return 0

        if args.command == "experience-catalog":
            value = build_library_artifact() if args.full else {"metrics":catalog_metrics(), "patterns":[item.to_dict() for item in PATTERNS], "visualDirections":direction_catalog(), "pageSkeletons":page_skeleton_catalog()}
            _emit(value, compact=args.compact)
            return 0

        if args.command in {"ux-repair-plan", "design-system-map"}:
            project = Path(args.project_root).expanduser().resolve()
            sources = []
            for path in sorted(project.rglob("*")):
                if path.is_file() and path.suffix.casefold() in {".html", ".htm", ".css", ".js", ".jsx", ".ts", ".tsx", ".vue", ".svelte"} and path.stat().st_size <= 1_048_576:
                    try: sources.append({"path":str(path.relative_to(project)).replace("\\", "/"), "text":path.read_text(encoding="utf-8")})
                    except (UnicodeDecodeError, OSError): pass
            value = analyze_ux_sources(sources, {}) if args.command == "ux-repair-plan" else build_design_system_map(sources)
            output = Path(args.output).expanduser().resolve(); output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
            _emit({"status":"PASS", "output":str(output), "result":value}, compact=args.compact)
            return 0

        if args.command == "render-experience-preview":
            plan = load_json(Path(args.experience_plan))
            path = generate_experience_preview(plan, args.output_dir, title=args.title)
            _emit({"status":"PASS", "preview":str(path)})
            return 0

        if args.command == "evaluate-experience":
            result = evaluate_experience(
                load_json(Path(args.before_metrics)), load_json(Path(args.after_metrics)),
                visual_review=_optional_mapping(args.visual_review),
            )
            _emit(result, compact=args.compact)
            return 1 if result["status"] == "REGRESSED" else 0

        if args.command == "modernization-plan":
            result = build_modernization_strategy(_load_modernization_plan(Path(args.experience_plan).expanduser()))
            output = Path(args.output).expanduser().resolve(); output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
            _emit({
                "status": result["readiness"]["status"],
                "executionStatus": "PASS",
                "output":str(output),
                "strategy":result,
            }, compact=args.compact)
            return 0

        if args.command == "commercial-preflight":
            result = run_preflight(args.package_root, evidence_root=args.evidence_root, candidate_archive=args.candidate_archive); _emit(result, compact=args.compact); return 0 if result["status"] == "GA_READY" else 1

        if args.command == "digest-plan":
            _emit({"planDigest": plan_digest(load_json(Path(args.plan)))}, compact=True)
            return 0

        if args.command == "manifest":
            value = build_source_scope_manifest(args.project_root, args.paths)
            _emit({"sourceScopeManifest": value, "sourceScopeFingerprint": source_scope_fingerprint(value)})
            return 0

        if args.command == "doctor":
            package_root = Path(__file__).resolve().parent
            schema_dir = package_root / "schemas"
            schemas = sorted(path.name for path in schema_dir.glob("*.json")) if schema_dir.exists() else []
            schema_health = _schema_health(schema_dir) if schema_dir.exists() else {"status": "FAIL", "checked": 0, "errors": [{"file": "schemas", "error": "missing directory"}]}
            capability_registry = build_capability_registry(args.browser_executable)
            browser = capability_registry.get("pythonPlaywright", {})
            result = {
                "runtime": "PASS",
                "python": sys.version.split()[0],
                "packagedSchemas": schemas,
                "schemaStatus": "PASS" if len(schemas) >= 24 and schema_health.get("status") == "PASS" else schema_health.get("status", "FAIL"),
                "schemaHealth": schema_health,
                "browser": browser,
                "candidateBrowser": capability_registry.get("nodeCandidateValidation", {}),
                "capabilities": capability_registry,
                "visualDiff": visual_capability(),
                "externalProviders": external_capabilities(),
                "screenshotInput": screenshot_capability(),
                "designIntelligence": {"archetypes": len(archetype_catalog()), "componentSources": len(source_catalog()), "visualBuilder": "AVAILABLE"},
                "packageIdentity": package_identity(),
                "productExperience": {
                    **release_identity(),
                    "smartProductDiscovery": "AVAILABLE",
                    "evidenceClasses": list(EVIDENCE_CLASSES),
                    "questionPolicy": {"maximumPerRound": 3, "roundsByDefault": 1, "mayProceedWithInference": False},
                    "workflowStates": ["DISCOVERY", "AWAITING_USER_CONFIRMATION", "DIAGNOSIS", "AWAITING_IMPLEMENTATION_APPROVAL", "IMPLEMENTATION", "VERIFICATION"],
                    "defaultMode": "diagnose",
                    "modelCapabilityProfiles": ["baseline", "standard", "advanced"],
                    "unknownModelProfile": "baseline",
                    "securityAudit": "OPT_IN_ONLY",
                    "sourceWriteAuthority": "HOST_APPROVAL_REQUIRED",
                    "smartAcceptance": {"phase": "P0-A", "command": "check", "outcomeProof": "AVAILABLE", "findingSchema": "v2"},
                    "laterPhases": {"P0-B-R": "NOT_EXECUTED", "P0-B-S": "NOT_EXECUTED", "P1": "NOT_APPLICABLE_TO_THIS_RELEASE"},
                    "brief": "AVAILABLE", "journeySimulation": "AVAILABLE", "measurementHandoff": "AVAILABLE",
                },
                "experimentalTrack": {
                    **experimental_identity(),
                    "module": "adaptive_intelligence",
                    "qualification": {
                        "runtimeWiring": "PASS",
                        "controlledBenchmark": "PASS_SYNTHETIC_ONLY",
                        "realHostAgentMetrics": "NOT_MEASURED",
                        "enforcement": "NOT_ACTIVE",
                        "operatorNextStep": "Collect comparable real Host/Agent runs before selective enforcement.",
                    },
                    "profiles": {
                        "HARDEN_PROFILE": verification_profile("HARDEN_PROFILE")["cases"],
                        "ADAPT_PROFILE": verification_profile("ADAPT_PROFILE")["cases"],
                    },
                },
                "browserStatus": capability_registry.get("browserStatus"),
            }
            _emit(result, compact=args.compact)
            return 0 if result["schemaStatus"] == "PASS" else 1

        if args.command == "prepare-change-set":
            raise ContractViolation("HOST_EDITING_REQUIRED", ["$: Runtime can generate a Patch Candidate only; the Codex Host must apply it"])
        if args.command == "apply-change-set":
            raise ContractViolation("HOST_EDITING_REQUIRED", ["$: Runtime does not write project files; the Codex Host must apply the Patch Candidate"])
        if args.command == "rollback-change-set":
            raise ContractViolation("HOST_EDITING_REQUIRED", ["$: Runtime does not roll back project files; the Codex Host must apply the reverse Patch Candidate"])
        if args.command == "validate-browser-report":
            report = validate_browser_report_structure(load_json(Path(args.report)))
            _emit(
                {
                    "structureValid": True,
                    "candidateResult": report["candidateResult"],
                    "effectiveResult": "NOT_VERIFIED",
                    "authorityVerified": False,
                    "errorCode": "SERIALIZED_BROWSER_AUTHORITY_FORBIDDEN",
                },
                compact=True,
            )
            return 2
        raise ContractViolation("COMMAND_INVALID", ["$: unsupported command"])
    except ContractViolation as error:
        _emit({"error": error.as_user_dict()}, compact=True, stream=sys.stderr)
        return 5 if getattr(args, "command", None) == "run" and getattr(args, "ci", False) else 2
    except (OSError, UnicodeError) as error:
        _emit({"error": {"code": "IO_ERROR", "errors": [type(error).__name__]}}, compact=True, stream=sys.stderr)
        return 5 if getattr(args, "command", None) == "run" and getattr(args, "ci", False) else 2
    except (ValueError, json.JSONDecodeError) as error:
        _emit({"error": {"code": "INPUT_INVALID", "errors": [str(error)]}}, compact=True, stream=sys.stderr)
        return 5 if getattr(args, "command", None) == "run" and getattr(args, "ci", False) else 2


if __name__ == "__main__":
    raise SystemExit(main())
