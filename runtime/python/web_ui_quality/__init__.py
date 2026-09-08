"""Web UI Quality Core runtime."""

from .release_info import PACKAGE_VERSION, EXPERIMENTAL_VERSION, experimental_identity
from .browser_standard import (
    BrowserActionPermit,
    BrowserRunGuard,
    TrustedBrowserAuthorizationContext,
    TrustedBrowserEvidenceReceipt,
    authorize_action,
    authorize_dom_action,
    authorize_navigation,
    bind_trusted_browser_authorization,
    bind_trusted_browser_evidence,
    browser_session_binding_digest,
    build_browser_safety_report,
    build_controlled_fixture_manifest,
    consume_dom_action_permit,
    create_browser_contract,
    create_browser_run_guard,
    evaluate_capability_probe,
    finalize_browser_run,
    issue_dom_action_permit,
    reconcile_network_evidence,
    reconcile_response_receipt_evidence,
    record_browser_action,
    require_browser_run_active,
    resolve_browser_outcome,
    sanitize_console_evidence,
    sanitize_network_evidence,
    validate_browser_contract,
    validate_browser_report,
    validate_browser_report_structure,
    validate_cleanup,
    validate_controlled_fixture_manifest,
    validate_geometry_evidence,
    validate_redaction_counts,
    validate_screenshot_evidence,
)
from .contracts import (
    ContractViolation,
    build_source_scope_manifest,
    canonical_json,
    plan_digest,
    source_scope_fingerprint,
    validate_finding,
    validate_productization_plan,
)
from .accessibility import normalize_accessibility_result
from .attempts import AttemptLimiter, issue_fingerprint
from .browser_provider import BrowserProvider, unavailable_browser_capability
from .builtin_rules import builtin_rule_registry, coverage_for_findings
from .coverage import CoverageLedger, RuleMetadata, RuleRegistry
from .design_context import build_project_reference, critique_design, freeze_design_context
from .evidence_normalizer import normalize_envelopes
from .provider_contracts import ProviderEnvelope
from .provider_registry import CapabilityDescriptor, CapabilityProbe, ProviderRegistry, default_provider_registry, probe_provider
from .risk import escalate_risk, risk_from_impacts
from .safe_edit_bridge import PatchCandidate, build_patch_candidate
from .core import audit_html_document, audit_project, canonicalize_external_html
from .playwright_adapter import compare_pages, playwright_capability
from .quick_ui import QUICK_UI_VIEWPORTS, run_quick_ui, summarize_top_ui_issues
from .smart_acceptance import run_smart_acceptance
from .condition_registry import STANDARD_VIEWPORTS, RunConditions, ViewportCondition, compare_conditions, normalize_viewports
from .experience_run import create_experience_run, load_experience_run, record_phase_artifact, seal_after, seal_before, validate_after_binding, write_phase_file
from .experience_fix import run_experience_fix
from .page_health import evaluate_page_health
from .readiness import assess_readiness
from .resource_integrity import classify_resource_events
from .mutation_firewall import BrowserMutationFirewall
from .reversible_probe import run_reversible_probe
from .project_launcher import classify_command, expand_lifecycle_scripts, inspect_project_start
from .host_bridge import (
    HostTaskScope, TrustedHostWriteReceipt, bind_narrow_project_local_ui_edit, bridge_request,
    require_host_scope, require_verified_host_write, verify_host_write_receipt,
)
from .repair_recipe import build_repair_recipe, build_repair_recipes
from .source_assurance import command_safety_plan, resolve_change_scope, run_source_assurance
from .comparison_gate import evaluate_improvement_claim
from .command_policy import classify_script_tree
from .source_parsers import parse_source
from .business_context import build_context_v2, context_summary, mark_stale
from .acceptance_findings import normalize_finding, normalize_findings, top_findings
from .orchestrator import run_full_audit
from .visual_judgment import judge_visual_improvement
from .visual_review import normalize_visual_review, review_template
from .reporting import generate_html_report
from .collaboration import export_collaboration_bundle
from .commercial_preflight import run_preflight
from .experience_core import build_experience_core
from .experience_engine import analyze_experience_project, build_experience_diagnosis, collect_experience_sources, export_experience_analysis
from .experience_proof import build_experience_proof, trusted_experience_geometry
from .experience_consultant import build_experience_consultant, build_experience_consultation
from .consultant_preview import generate_consultant_preview
from .product_experience_consultant import (
    build_experience_intake,
    build_business_reasoning,
    build_design_reasoning,
    build_transformation_report,
    build_product_experience_report,
    export_product_experience_report,
)
from .commercial_upgrade import run_commercial_upgrade
from .design_gallery import build_design_gallery
from .implementation_agent import execute_isolated_transformation
from .outcome_measurement import build_measurement_template, export_outcome_report, measure_outcome
from .production_validation import validate_transformation
from .experience_journey_intelligence import analyze_user_journey, build_experience_score_report, infer_product_type
from .visual_transformation_engine import build_transformation_plan
from .design_simulation_engine import simulate_journey
from .experience_loop import build_measurement_loop
from .executive_experience_report import build_executive_report, build_executive_brief
from .schema_validation import validate_instance, validation_errors, check_schema_bundle
from .experience_model import build_experience_model
from .experience_preview import generate_experience_preview
from .experience_studio import build_library_artifact, generate_experience_studio, generate_library_gallery
from .experience_catalog import catalog_metrics, page_skeleton_catalog, interaction_catalog, state_catalog
from .ux_repair import analyze_ux_sources
from .design_system_map import build_design_system_map
from .experience_quality import evaluate_plan_readiness
from .experience_evaluator import evaluate_experience
from .experience_modernization import build_modernization_strategy
from .pattern_library import PATTERNS, route_patterns
from .visual_system import build_visual_system, direction_catalog
from .interaction_states import build_interaction_contract
from .design_ir import build_document, make_node, make_product_node, normalise_node, normalise_product_node, summarise_design_ir, validate_design_ir
from .figma_input import convert_figma_payload, fetch_and_import_figma, import_figma_json, parse_figma_reference
from .screenshot_input import analyse_screenshot, import_screenshot
from .component_registry import source_catalog, component_recipes, recommend_components, detect_framework
from .design_intelligence import archetype_catalog, generate_design_candidates, apply_candidate_to_plan
from .production_mapper import build_production_plan, generate_production_scaffold, discover_local_components
from .visual_builder import generate_visual_builder
from .design_pipeline import run_design_pipeline
from .trusted_evidence import (
    TrustedRealTargetContext,
    TrustedUIBrowserEvidence,
    bind_local_browser_evidence,
    bind_trusted_real_target,
)
from .safe_edit import (
    TrustedApplyReceipt,
    TrustedApprovalContext,
    TrustedRollbackApprovalContext,
    apply_change_set,
    bind_trusted_current_conversation_approval,
    bind_trusted_rollback_approval,
    check_plan_stale,
    prepare_change_set,
    prepare_r1_change,
    read_enterprise_differences,
    rollback_preview_digest,
    rollback_change_set,
)
from .workflow_policy import (
    ANSWER_ROUND_ACTIONS,
    DIAGNOSIS_ONLY_ACTIONS,
    TrustedWorkflowApproval,
    bind_trusted_workflow_approval,
    confirmation_digest,
    is_answer_round_action,
    is_diagnosis_only_action,
    require_trusted_workflow_approval,
    required_scope_for_action,
)

__all__ = [
    "BrowserActionPermit",
    "BrowserProvider",
    "BrowserRunGuard",
    "ContractViolation",
    "CoverageLedger",
    "RuleMetadata",
    "RuleRegistry",
    "AttemptLimiter",
    "CapabilityDescriptor",
    "CapabilityProbe",
    "ProviderEnvelope",
    "ProviderRegistry",
    "PatchCandidate",
    "TrustedApplyReceipt",
    "TrustedApprovalContext",
    "TrustedBrowserAuthorizationContext",
    "TrustedBrowserEvidenceReceipt",
    "TrustedRollbackApprovalContext",
    "TrustedRealTargetContext",
    "TrustedUIBrowserEvidence",
    "TrustedWorkflowApproval",
    "ANSWER_ROUND_ACTIONS",
    "DIAGNOSIS_ONLY_ACTIONS",
    "authorize_action",
    "authorize_dom_action",
    "authorize_navigation",
    "audit_html_document",
    "audit_project",
    "builtin_rule_registry",
    "build_browser_safety_report",
    "build_controlled_fixture_manifest",
    "build_project_reference",
    "canonicalize_external_html",
    "compare_pages",
    "apply_change_set",
    "bind_trusted_current_conversation_approval",
    "bind_trusted_browser_authorization",
    "bind_trusted_browser_evidence",
    "bind_trusted_rollback_approval",
    "bind_local_browser_evidence",
    "bind_trusted_real_target",
    "bind_trusted_workflow_approval",
    "browser_session_binding_digest",
    "confirmation_digest",
    "is_answer_round_action",
    "is_diagnosis_only_action",
    "build_source_scope_manifest",
    "canonical_json",
    "coverage_for_findings",
    "default_provider_registry",
    "critique_design",
    "create_browser_contract",
    "create_browser_run_guard",
    "consume_dom_action_permit",
    "evaluate_capability_probe",
    "finalize_browser_run",
    "freeze_design_context",
    "issue_dom_action_permit",
    "plan_digest",
    "probe_provider",
    "playwright_capability",
    "QUICK_UI_VIEWPORTS",
    "run_quick_ui",
    "summarize_top_ui_issues",
    "prepare_change_set",
    "prepare_r1_change",
    "read_enterprise_differences",
    "rollback_preview_digest",
    "rollback_change_set",
    "require_trusted_workflow_approval",
    "required_scope_for_action",
    "reconcile_network_evidence",
    "reconcile_response_receipt_evidence",
    "record_browser_action",
    "require_browser_run_active",
    "resolve_browser_outcome",
    "sanitize_console_evidence",
    "sanitize_network_evidence",
    "check_plan_stale",
    "source_scope_fingerprint",
    "issue_fingerprint",
    "normalize_accessibility_result",
    "normalize_envelopes",
    "escalate_risk",
    "risk_from_impacts",
    "build_patch_candidate",
    "unavailable_browser_capability",
    "run_full_audit",
    "judge_visual_improvement",
    "normalize_visual_review",
    "review_template",
    "generate_html_report",
    "export_collaboration_bundle",
    "run_preflight",
    "build_experience_core",
    "analyze_experience_project",
    "build_experience_diagnosis",
    "collect_experience_sources",
    "export_experience_analysis",
    "build_experience_proof",
    "build_experience_consultant",
    "build_experience_consultation",
    "generate_consultant_preview",
    "build_experience_intake",
    "build_business_reasoning",
    "build_design_reasoning",
    "build_transformation_report",
    "build_product_experience_report",
    "export_product_experience_report",
    "run_commercial_upgrade",
    "build_design_gallery",
    "execute_isolated_transformation",
    "build_measurement_template",
    "export_outcome_report",
    "measure_outcome",
    "validate_transformation",
    "analyze_user_journey",
    "build_experience_score_report",
    "infer_product_type",
    "build_transformation_plan",
    "simulate_journey",
    "build_measurement_loop",
    "build_executive_report",
    "build_executive_brief",
    "validate_instance",
    "validation_errors",
    "check_schema_bundle",
    "trusted_experience_geometry",
    "build_experience_model",
    "generate_experience_preview",
    "generate_experience_studio",
    "generate_library_gallery",
    "build_library_artifact",
    "catalog_metrics",
    "page_skeleton_catalog",
    "interaction_catalog",
    "state_catalog",
    "analyze_ux_sources",
    "build_design_system_map",
    "evaluate_plan_readiness",
    "evaluate_experience",
    "build_modernization_strategy",
    "PATTERNS",
    "route_patterns",
    "build_visual_system",
    "direction_catalog",
    "build_interaction_contract",
    "validate_finding",
    "validate_browser_contract",
    "validate_browser_report",
    "validate_browser_report_structure",
    "validate_cleanup",
    "validate_controlled_fixture_manifest",
    "validate_geometry_evidence",
    "validate_productization_plan",
    "validate_redaction_counts",
    "validate_screenshot_evidence",
    "build_document",
    "make_node",
    "make_product_node",
    "normalise_node",
    "normalise_product_node",
    "summarise_design_ir",
    "validate_design_ir",
    "convert_figma_payload",
    "fetch_and_import_figma",
    "import_figma_json",
    "parse_figma_reference",
    "analyse_screenshot",
    "import_screenshot",
    "source_catalog",
    "component_recipes",
    "recommend_components",
    "detect_framework",
    "archetype_catalog",
    "generate_design_candidates",
    "apply_candidate_to_plan",
    "build_production_plan",
    "generate_production_scaffold",
    "discover_local_components",
    "generate_visual_builder",
    "run_design_pipeline",
    "run_smart_acceptance",
    "command_safety_plan",
    "resolve_change_scope",
    "run_source_assurance",
    "build_context_v2",
    "context_summary",
    "mark_stale",
    "normalize_finding",
    "normalize_findings",
    "top_findings",
    "STANDARD_VIEWPORTS",
    "RunConditions",
    "ViewportCondition",
    "compare_conditions",
    "normalize_viewports",
    "create_experience_run",
    "load_experience_run",
    "seal_after",
    "seal_before",
    "validate_after_binding",
    "write_phase_file",
    "run_experience_fix",
    "evaluate_page_health",
    "assess_readiness",
    "classify_resource_events",
    "BrowserMutationFirewall",
    "run_reversible_probe",
    "classify_command",
    "expand_lifecycle_scripts",
    "inspect_project_start",
    "HostTaskScope",
    "bind_narrow_project_local_ui_edit",
    "bridge_request",
    "require_host_scope",
    "build_repair_recipe",
    "build_repair_recipes",

    "record_phase_artifact",
    "verify_host_write_receipt",
    "TrustedHostWriteReceipt",
    "require_verified_host_write",
    "evaluate_improvement_claim",
    "classify_script_tree",
    "parse_source",
]

__version__ = PACKAGE_VERSION

# 4.0 Release Closure: Design IR remains internal/compatibility surface.
from .task_goal import create_task_goal, load_task_goal, update_task_goal, finding_goal_relevance, auto_fix_allowed
from .assumption_graph import add_assumption, register_dependent_artifact, supersede_assumption, load_assumption_graph
from .capability_router import route_capabilities, infer_page_type, MANDATORY_CAPABILITIES
from .decision_ledger import create_decision, supersede_decision, update_verification_status, load_decision_ledger
from .control_intent import parse_control_intent
from .run_checkpoint import create_checkpoint, list_checkpoints, resume_checkpoint, build_run_health
from .outcome_verification import build_outcome_hypothesis, evaluate_outcome, classify_mutation_risk, mutation_verification_plan
from .adaptive_intelligence import (
    TaskFingerprint,
    TaskGraph,
    build_execution_budget,
    consume_budget,
    propose_replan,
    classify_assumption,
    complexity_delta,
    build_traceability_report,
    reproduction_transition,
    route_design_intent,
    compare_design_drift,
    separate_design_review,
    build_memory_entry,
    evaluate_memory_entry,
    candidate_count,
    build_candidate_arena,
    select_candidate,
    verification_profile,
    shadow_supervisor,
)

# Narrow public facade. Historical exports above remain compatibility surfaces.
from .public_api import run
__all__.append("run")
__all__.extend([
    "EXPERIMENTAL_VERSION", "experimental_identity",
    "TaskFingerprint", "TaskGraph", "build_execution_budget", "consume_budget",
    "propose_replan", "classify_assumption", "complexity_delta", "build_traceability_report",
    "reproduction_transition", "route_design_intent", "compare_design_drift", "separate_design_review",
    "build_memory_entry", "evaluate_memory_entry", "candidate_count", "build_candidate_arena",
    "select_candidate", "verification_profile", "shadow_supervisor",
])
