"""Unified Codex Desktop design intelligence pipeline."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from time import perf_counter
from typing import Any, Mapping

from .component_registry import component_recipes, detect_framework, source_catalog
from .core import audit_project
from .design_intelligence import archetype_catalog, generate_design_candidates
from .adaptive_intelligence import route_design_intent, build_candidate_arena
from .figma_input import fetch_and_import_figma, import_figma_json
from .production_mapper import build_production_plan, generate_production_scaffold
from .project_source_ir import build_project_design_ir
from .schema_validation import validate_instance
from .screenshot_input import import_screenshot
from .visual_builder import generate_visual_builder


def _load(path: str | Path | None, *, base: Path | None = None) -> dict[str, Any] | None:
    if path is None:
        return None
    candidate = Path(path).expanduser()
    if not candidate.is_absolute() and base is not None:
        candidate = base / candidate
    value = json.loads(candidate.resolve().read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object in {candidate.name}")
    return value


def _rel(path: Path, base: Path) -> str:
    return path.relative_to(base).as_posix()


def _seconds(start: float) -> float:
    return round(perf_counter() - start, 4)

def _persist_audit_result(out: Path, audit: Mapping[str, Any]) -> str:
    schema_dir = Path(__file__).resolve().parent / "schemas"
    schema = json.loads((schema_dir / "audit-result.schema.json").read_text(encoding="utf-8"))
    validate_instance(dict(audit), schema, base_dir=schema_dir)
    path = out / "audit-result.json"
    path.write_text(json.dumps(dict(audit), ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return _rel(path, out)


def _not_applicable_pipeline(out: Path, audit: Mapping[str, Any], stack: Mapping[str, Any]) -> dict[str, Any]:
    result = {
        "schemaVersion": "2.2",
        "status": "NOT_APPLICABLE",
        "reason": "AUDIT_SCOPE_EMPTY",
        "projectRoot": ".",
        "auditResult": _persist_audit_result(out, audit),
        "detectedFramework": stack.get("framework"),
        "frameworkStatus": stack.get("status"),
        "designCandidates": None,
        "selectedCandidate": None,
        "productionPlan": None,
        "productionScaffold": {"status": "NOT_SUPPORTED", "reason": "FRAMEWORK_NOT_SUPPORTED"},
        "visualBuilder": None,
        "componentRegistry": None,
        "gates": {
            "productionWriteAuthority": False,
            "humanVisualPreference": "NOT_APPLICABLE",
            "browserVerification": "NOT_APPLICABLE",
        },
    }
    result["pipelineDigest"] = sha256(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    manifest_path = out / "design-pipeline-manifest.json"
    manifest_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return {**result, "manifest": "design-pipeline-manifest.json"}



def _adaptive_surface(plan: Mapping[str, Any], audit: Mapping[str, Any] | None) -> str:
    """Infer a conservative design surface from already-grounded project context."""
    candidates = []
    for source in (plan, audit or {}):
        if not isinstance(source, Mapping):
            continue
        for key in ("surfaceType", "pageType", "productType", "taskType", "selectedSkeleton"):
            value = source.get(key)
            if isinstance(value, Mapping):
                value = value.get("id") or value.get("type")
            if value:
                candidates.append(str(value).casefold())
    text = " ".join(candidates)
    if any(token in text for token in ("landing", "marketing")): return "MARKETING"
    if "portfolio" in text: return "PORTFOLIO"
    if "brand" in text: return "BRAND"
    if any(token in text for token in ("data-table", "data_table", "table")): return "DATA_TABLE"
    if "dashboard" in text: return "DASHBOARD"
    if "admin" in text: return "ADMIN"
    if any(token in text for token in ("auth", "login", "sign-in")): return "AUTH"
    if "checkout" in text: return "CHECKOUT"
    if any(token in text for token in ("government", "public-service", "public_service")): return "PUBLIC_SERVICE"
    return "PRODUCT"


def _adaptive_design_intent(plan: Mapping[str, Any], audit: Mapping[str, Any] | None) -> dict[str, Any]:
    context = audit.get("designContext") if isinstance(audit, Mapping) and isinstance(audit.get("designContext"), Mapping) else {}
    audience = plan.get("audience") or context.get("audience") or "UNKNOWN"
    if isinstance(audience, (list, tuple)):
        audience = ", ".join(str(x) for x in audience)
    language = plan.get("designLanguage") or plan.get("visualStyle") or "PROJECT_EXISTING"
    anti = plan.get("antiReferences") or plan.get("antiReferencesList") or ()
    return route_design_intent(
        surface_type=_adaptive_surface(plan, audit),
        audience=str(audience), design_language=str(language),
        anti_references=anti if isinstance(anti, (list, tuple, set)) else (str(anti),) if anti else (),
        preservation_mode="HIGH",
        confidence="MEDIUM",
    )

def run_design_pipeline(
    project_root: str | Path,
    output_dir: str | Path,
    *,
    experience_plan: Mapping[str, Any] | None = None,
    business_context: Mapping[str, Any] | None = None,
    figma_json: str | Path | None = None,
    figma_reference: str | None = None,
    figma_token: str | None = None,
    screenshot: str | Path | None = None,
    multimodal_overlay: Mapping[str, Any] | None = None,
    target_framework: str | None = None,
    candidate_count: int = 3,
    title: str | None = None,
    runtime_budget_seconds: int = 480,
) -> dict[str, Any]:
    pipeline_started = perf_counter()
    stage_timings: dict[str, float] = {}
    root = Path(project_root).expanduser().resolve(strict=True)
    out = Path(output_dir).expanduser().resolve(); out.mkdir(parents=True, exist_ok=True)
    audit: dict[str, Any] | None = None
    stage_started = perf_counter()
    stack = detect_framework(root)
    stage_timings["frameworkDetection"] = _seconds(stage_started)
    stage_started = perf_counter()
    audit = audit_project(root, business_context=dict(business_context or {}))
    stage_timings["audit"] = _seconds(stage_started)
    if experience_plan is None:
        if audit.get("status") == "NOT_APPLICABLE" and not any((figma_json, figma_reference, screenshot)):
            result = _not_applicable_pipeline(out, audit, stack)
            result["timings"] = {**stage_timings, "total": _seconds(pipeline_started)}
            result["runtimeBudget"] = {"targetSeconds": runtime_budget_seconds, "status": "PASS" if result["timings"]["total"] <= runtime_budget_seconds else "EXCEEDED", "boundedSourceScanning": True}
            digest_payload = {k: v for k, v in result.items() if k not in {"manifest", "pipelineDigest"}}
            result["pipelineDigest"] = sha256(json.dumps(digest_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
            (out / "design-pipeline-manifest.json").write_text(json.dumps({k: v for k, v in result.items() if k != "manifest"}, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
            return result
        plan = audit["experienceCore"]
    else:
        plan = dict(experience_plan)
        if audit.get("status") == "NOT_APPLICABLE" and not any((figma_json, figma_reference, screenshot)):
            result = _not_applicable_pipeline(out, audit, stack)
            result["timings"] = {**stage_timings, "total": _seconds(pipeline_started)}
            result["runtimeBudget"] = {"targetSeconds": runtime_budget_seconds, "status": "PASS" if result["timings"]["total"] <= runtime_budget_seconds else "EXCEEDED", "boundedSourceScanning": True}
            digest_payload = {k: v for k, v in result.items() if k not in {"manifest", "pipelineDigest"}}
            result["pipelineDigest"] = sha256(json.dumps(digest_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
            (out / "design-pipeline-manifest.json").write_text(json.dumps({k: v for k, v in result.items() if k != "manifest"}, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
            return result
    plan_path = out / "experience-core.json"
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    modernization_path: Path | None = None
    if isinstance(plan.get("modernizationStrategy"), Mapping):
        modernization_path = out / "modernization-strategy.json"
        modernization_path.write_text(json.dumps(plan["modernizationStrategy"], ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    import_result: dict[str, Any] | None = None
    import_dir = out / "design-input"; import_dir.mkdir(parents=True, exist_ok=True)
    stage_started = perf_counter()
    selected_inputs = sum(bool(item) for item in (figma_json, figma_reference, screenshot))
    if selected_inputs > 1:
        raise ValueError("select at most one primary visual input: figma_json, figma_reference, or screenshot")
    if figma_json:
        import_result = import_figma_json(figma_json, import_dir)
    elif figma_reference:
        import_result = fetch_and_import_figma(figma_reference, import_dir, token=figma_token)
    elif screenshot:
        import_result = import_screenshot(screenshot, import_dir, multimodal_overlay=multimodal_overlay)
    stage_timings["visualInput"] = _seconds(stage_started)

    stage_started = perf_counter()
    if import_result and import_result.get("status") == "PASS" and import_result.get("designIr"):
        design_ir = _load(import_result["designIr"], base=import_dir)
    else:
        design_ir = build_project_design_ir(root, audit_report=audit)
        design_ir_path = import_dir / "design-ir.json"
        design_ir_path.write_text(json.dumps(design_ir, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        import_result = {
            "schemaVersion": "2.2", "status": "PASS", "provider": "project-source",
            "designIr": "design-ir.json",
            "summary": {"sourceGrounded": True, "renderedGeometryProven": False},
            "limitations": ["Source analysis does not prove rendered geometry or hidden runtime behaviour."],
        }
        (import_dir / "import-report.json").write_text(json.dumps(import_result, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        import_result["report"] = "import-report.json"
    stage_timings["designIr"] = _seconds(stage_started)

    stage_started = perf_counter()
    design_intent = _adaptive_design_intent(plan, audit)
    design_intent_path = out / "design-intent.json"
    design_intent_path.write_text(json.dumps(design_intent, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    candidates = generate_design_candidates(plan, design_ir=design_ir, count=candidate_count)
    candidates_path = out / "design-candidates.json"
    candidates_path.write_text(json.dumps(candidates, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    task_kind = "major_brand" if design_intent.get("surfaceType") in {"MARKETING", "BRAND", "PORTFOLIO"} and candidate_count >= 3 else "significant_redesign" if candidate_count >= 2 else "normal_ui"
    arena = build_candidate_arena(task_kind=task_kind, candidates=list(candidates.get("candidates") or []))
    arena_path = out / "candidate-arena.json"
    arena_path.write_text(json.dumps(arena, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    stage_timings["candidates"] = _seconds(stage_started)
    stage_started = perf_counter()
    production = build_production_plan(root, plan, design_ir=design_ir, target_framework=target_framework)
    production_path = out / "production-plan.json"
    production_path.write_text(json.dumps(production, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    scaffold = generate_production_scaffold(production, plan, out / "production-scaffold")
    stage_timings["productionMapping"] = _seconds(stage_started)
    stage_started = perf_counter()
    builder_path = generate_visual_builder(plan, out / "visual-builder", design_ir=design_ir, candidates=candidates, production_plan=production, title=title)
    stage_timings["visualBuilder"] = _seconds(stage_started)

    registry = {
        "schemaVersion": "2.2", "status": "CATALOG_READY",
        "policy": {"metadataOnly": True, "noAutomaticInstall": True, "licenseReviewRequired": True},
        "sources": source_catalog(), "recipes": component_recipes(),
    }
    registry_path = out / "component-registry.json"
    registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    archetypes_path = out / "design-archetypes.json"
    archetypes_path.write_text(json.dumps({"schemaVersion":"2.2","archetypes":archetype_catalog()}, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    pipeline_status = "FRAMEWORK_NOT_SUPPORTED" if production.get("status") == "FRAMEWORK_NOT_SUPPORTED" else "DESIGN_PIPELINE_READY"
    audit_result = _persist_audit_result(out, audit) if audit is not None else None
    result = {
        "schemaVersion": "2.2", "status": pipeline_status,
        "projectRoot": ".", "experiencePlan": _rel(plan_path, out), "auditResult": audit_result,
        "modernizationStrategy": _rel(modernization_path, out) if modernization_path else None,
        "visualInput": import_result,
        "designIntent": _rel(design_intent_path, out),
        "candidateArena": _rel(arena_path, out),
        "designCandidates": _rel(candidates_path, out), "recommendedCandidate": candidates.get("recommended"), "selectedCandidate": candidates.get("selected"),
        "productionPlan": _rel(production_path, out), "productionScaffold": scaffold,
        "visualBuilder": _rel(builder_path, out), "componentRegistry": _rel(registry_path, out),
        "designArchetypes": _rel(archetypes_path, out),
        "timings": {**stage_timings, "total": _seconds(pipeline_started)},
        "runtimeBudget": {
            "targetSeconds": runtime_budget_seconds,
            "status": "PASS" if _seconds(pipeline_started) <= runtime_budget_seconds else "EXCEEDED",
            "boundedSourceScanning": True,
        },
        "gates": {
            "visualInputAuthority": "CANDIDATE_ONLY",
            "productionWriteAuthority": False,
            "packageInstallation": production.get("installPlan", {}).get("status"),
            "humanVisualPreference": "REQUIRED",
            "browserVerification": "REQUIRED_BEFORE_PRODUCTION",
            "candidateCount": {
                "requested": candidate_count,
                "actual": len(candidates.get("candidates", [])),
                "required": max(1, min(3, int(candidate_count))),
                "status": "PASS" if len(candidates.get("candidates", [])) == max(1, min(3, int(candidate_count))) else "FAIL",
            },
            "candidateDirectionContractDifference": candidates.get("differenceGate", {}).get("status"),
            "candidateStructuralDifference": candidates.get("differenceGate", {}).get("status"),  # compatibility alias; declared-contract only
        },
        "reason": "FRAMEWORK_NOT_SUPPORTED" if pipeline_status == "FRAMEWORK_NOT_SUPPORTED" else None,
    }
    result["pipelineDigest"] = sha256(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    manifest_path = out / "design-pipeline-manifest.json"
    manifest_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return {**result, "manifest": _rel(manifest_path, out)}
