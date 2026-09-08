"""Evidence-bounded UI Experience Modernization Engine.

The engine composes page understanding, layout, responsive, visual, design-pattern,
and component intelligence into one schema 3.1 diagnosis. Static and screenshot
signals remain candidates; only explicitly browser-measured observations can create
rendered findings.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .component_registry import component_recipes, detect_framework, recommend_components
from .contracts import digest_json
from .experience_patterns import match_experience_patterns
from .experience_proof import build_experience_proof, trusted_experience_geometry
from .experience_consultant import build_experience_consultation
from .consultant_preview import generate_consultant_preview
from .layout_intelligence import analyze_layout
from .modernization_preview import generate_modernization_preview
from .page_understanding import build_page_understanding
from .responsive_experience import analyze_responsive_experience
from .scope_policy import WEB_SOURCE_SUFFIXES, collect_project_sources
from .visual_intelligence import analyze_visual_intelligence
from .trusted_evidence import TrustedUIBrowserEvidence


_PRIORITY_ORDER = {"must-fix": 0, "should-fix": 1, "candidate": 2}
_SEVERITY_ORDER = {"UX1": 0, "UX2": 1, "UX3": 2}
_PAGE_SCENARIOS = {
    "saas-dashboard": "dashboard",
    "landing-page": "landing",
    "mobile-workflow": "mobile",
}


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _normalise_token(value: Any) -> str:
    return str(value or "").strip().casefold().replace("_", "-").replace(" ", "-")


def _framework_from_sources(sources: Sequence[Mapping[str, Any]]) -> str:
    counts = {"react": 0, "vue": 0, "svelte": 0, "html": 0}
    for item in sources:
        suffix = Path(str(item.get("path") or "")).suffix.casefold()
        if suffix in {".jsx", ".tsx"}:
            counts["react"] += 1
        elif suffix == ".vue":
            counts["vue"] += 1
        elif suffix == ".svelte":
            counts["svelte"] += 1
        elif suffix in {".html", ".htm"}:
            counts["html"] += 1
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    if not ranked or ranked[0][1] == 0:
        return "unknown"
    if len(ranked) > 1 and ranked[0][1] == ranked[1][1]:
        return "unknown"
    return ranked[0][0]


def _viewport_rows(observed: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    raw = observed.get("viewports")
    if isinstance(raw, Mapping):
        return [dict(item) for item in raw.values() if isinstance(item, Mapping)]
    if isinstance(raw, list):
        return [dict(item) for item in raw if isinstance(item, Mapping)]
    return []


def _number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result == result else None


def _pattern_evidence(
    page: Mapping[str, Any],
    responsive: Mapping[str, Any],
    visual: Mapping[str, Any],
    observed: Mapping[str, Any],
) -> dict[str, Any]:
    inventory = page.get("componentInventory") if isinstance(page.get("componentInventory"), list) else []
    counts = {
        str(item.get("type")): int(item.get("count") or 0)
        for item in inventory if isinstance(item, Mapping)
    }
    hierarchy = (
        visual.get("model", {}).get("visualHierarchy", {})
        if isinstance(visual.get("model"), Mapping)
        else {}
    )
    focal = hierarchy.get("focalSequence") if isinstance(hierarchy.get("focalSequence"), list) else []
    primary_count = int((hierarchy.get("ctaHierarchy") or {}).get("primaryCount") or 0) if isinstance(hierarchy, Mapping) else 0
    evidence: dict[str, Any] = {
        "evidenceTier": "rendered_runtime" if observed else "visual_static",
        "confidence": "high" if observed else "medium" if inventory else "low",
        "dominantRegionCount": sum(
            1 for item in focal if isinstance(item, Mapping) and float(item.get("score") or 0) >= 60
        ),
        "primaryButtonCountAboveFold": primary_count,
        "hasSearch": counts.get("search", 0) > 0,
        "hasFilter": counts.get("filter", 0) > 0,
        "hasSort": counts.get("table", 0) > 0,
        "hasPaginationOrIncrementalLoad": counts.get("pagination", 0) > 0,
    }
    for row in _viewport_rows(observed):
        width = _number(row.get("width") or row.get("clientWidth") or row.get("viewportWidth"))
        if width is None:
            continue
        role = "desktop" if width >= 1200 else "tablet" if width >= 600 else "mobile"
        client = _number(row.get("clientWidth") or row.get("width"))
        scroll = _number(row.get("scrollWidth"))
        occupancy = _number(row.get("contentOccupancy"))
        if occupancy is None:
            content = _number(row.get("contentWidth"))
            occupancy = content / width if content is not None and width else None
        evidence.setdefault("viewports", {}).setdefault(role, {})
        if occupancy is not None:
            evidence["viewports"][role]["contentOccupancyRatio"] = round(occupancy, 4)
        if client is not None and scroll is not None:
            evidence["viewports"][role]["horizontalOverflowPx"] = max(0, round(scroll - client, 2))
    if isinstance(evidence.get("viewports"), Mapping):
        desktop = evidence["viewports"].get("desktop", {})
        mobile = evidence["viewports"].get("mobile", {})
        if "contentOccupancyRatio" in desktop:
            evidence["desktopContentOccupancyRatio"] = desktop["contentOccupancyRatio"]
        if "horizontalOverflowPx" in mobile:
            evidence["mobileHorizontalOverflowPx"] = mobile["horizontalOverflowPx"]
    return evidence


def _finding_recommendation(item: Mapping[str, Any]) -> dict[str, Any]:
    rendered = str(item.get("evidenceMode") or "") == "rendered-observation"
    severity = str(item.get("severity") or "UX3")
    priority = (
        "must-fix" if rendered and severity == "UX1"
        else "should-fix" if rendered
        else "candidate"
    )
    verification = item.get("verification") if isinstance(item.get("verification"), list) else []
    return {
        "id": str(item.get("id") or "EXPERIENCE-FINDING"),
        "priority": priority,
        "severity": severity,
        "category": str(item.get("category") or "experience"),
        "title": str(item.get("title") or "体验改进"),
        "userProblem": str(item.get("userExplanation") or item.get("userImpact") or ""),
        "userImpact": str(item.get("userImpact") or ""),
        "evidence": {
            "mode": item.get("evidenceMode"),
            "confidence": item.get("confidence"),
            "facts": item.get("evidence"),
        },
        "recommendation": str(item.get("recommendation") or ""),
        "implementation": item.get("implementation") or {},
        "verificationNeeded": list(verification),
        "claim": "observed-problem" if rendered else "source-risk",
    }


def _pattern_recommendations(patterns: Mapping[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for matched in patterns.get("matched", []) if isinstance(patterns.get("matched"), list) else []:
        if not isinstance(matched, Mapping):
            continue
        match = matched.get("match") if isinstance(matched.get("match"), Mapping) else {}
        runtime = str(matched.get("evidenceTier")) in {"rendered_runtime", "interaction_probe"}
        result.append({
            "id": f"PATTERN-{matched.get('id')}",
            "priority": "should-fix" if runtime else "candidate",
            "category": str(matched.get("scope") or "design-pattern"),
            "title": str(matched.get("name") or "成熟体验规律"),
            "userProblem": str(matched.get("userImpact") or ""),
            "evidence": {
                "mode": matched.get("evidenceTier"),
                "facts": match.get("observedFacts", []),
                "detectors": match.get("matchedDetectors", []),
            },
            "recommendation": str(matched.get("recommendation") or ""),
            "implementation": list(matched.get("implementationHints") or []),
            "verificationNeeded": list(match.get("verificationNeeded") or []),
            "claim": "observed-problem" if runtime else "source-risk",
            "brandCopyProhibited": True,
        })
    candidates = patterns.get("candidates") if isinstance(patterns.get("candidates"), list) else []
    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            continue
        match = candidate.get("match") if isinstance(candidate.get("match"), Mapping) else {}
        if not match.get("matchedDetectors"):
            continue
        result.append({
            "id": f"PATTERN-{candidate.get('id')}",
            "priority": "candidate",
            "category": str(candidate.get("scope") or "design-pattern"),
            "title": str(candidate.get("name") or "体验规律候选"),
            "userProblem": str(match.get("inference") or candidate.get("userImpact") or ""),
            "evidence": {
                "mode": candidate.get("evidenceTier"),
                "facts": match.get("observedFacts", []),
                "detectors": match.get("matchedDetectors", []),
            },
            "recommendation": str(candidate.get("recommendation") or ""),
            "implementation": list(candidate.get("implementationHints") or []),
            "verificationNeeded": list(match.get("verificationNeeded") or []),
            "claim": "improvement-candidate",
            "brandCopyProhibited": True,
        })
    return result


def _component_recommendations(component: Mapping[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    rows = component.get("recommendations") if isinstance(component.get("recommendations"), list) else []
    for row in rows:
        if not isinstance(row, Mapping) or not isinstance(row.get("recommended"), Mapping):
            continue
        selected = row["recommended"]
        result.append({
            "id": f"COMPONENT-{str(row.get('component') or '').upper()}",
            "priority": "candidate",
            "category": "component",
            "title": f"为 {row.get('component')} 选择成熟且框架匹配的实现",
            "userProblem": "组件交互、状态和响应式行为需要稳定实现，避免重复造轮子或引入错误框架包。",
            "evidence": {
                "mode": selected.get("evidenceLevel"),
                "framework": component.get("framework"),
                "source": selected.get("id"),
                "resolvedPackage": selected.get("resolvedPackage"),
                "scoreBreakdown": selected.get("scoreBreakdown"),
            },
            "recommendation": f"优先评审 {selected.get('name')}；若项目已有合格组件则继续复用。",
            "implementation": {
                "source": selected.get("id"),
                "package": selected.get("resolvedPackage"),
                "architectureFit": selected.get("architectureFit"),
                "noAutomaticInstallation": True,
            },
            "verificationNeeded": list(row.get("requiredContract") or []),
            "claim": "improvement-candidate",
        })
    return result


def _compose_recommendations(
    layout: Mapping[str, Any],
    responsive: Mapping[str, Any],
    visual: Mapping[str, Any],
    patterns: Mapping[str, Any],
    components: Mapping[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for module in (layout, responsive, visual):
        for item in module.get("findings", []) if isinstance(module.get("findings"), list) else []:
            if isinstance(item, Mapping):
                rows.append(_finding_recommendation(item))
    rows.extend(_pattern_recommendations(patterns))
    rows.extend(_component_recommendations(components))
    unique = {str(item["id"]): item for item in rows}
    return sorted(
        unique.values(),
        key=lambda item: (
            _PRIORITY_ORDER.get(str(item.get("priority")), 9),
            _SEVERITY_ORDER.get(str(item.get("severity")), 9),
            str(item.get("id")),
        ),
    )


def build_experience_diagnosis(
    sources: Sequence[Mapping[str, Any]],
    experience_model: Mapping[str, Any] | None = None,
    *,
    page_modes: Sequence[str] = (),
    observed: Mapping[str, Any] | None = None,
    trusted_browser_evidence: TrustedUIBrowserEvidence | None = None,
    screenshot_model: Mapping[str, Any] | None = None,
    framework: str | None = None,
    existing_imports: Iterable[str] | None = None,
    project_components: Any = None,
) -> dict[str, Any]:
    """Compose a deterministic schema 3.1 experience diagnosis."""

    source_items = [dict(item) for item in sources if isinstance(item, Mapping)]
    model = _mapping(experience_model)
    screenshot = _mapping(screenshot_model)
    rendered, _ = trusted_experience_geometry(trusted_browser_evidence)
    page = build_page_understanding(
        source_items,
        model,
        page_modes=page_modes,
        screenshot_model=screenshot,
        observed=rendered,
    )
    layout = analyze_layout(source_items, rendered)
    responsive = analyze_responsive_experience(source_items, rendered)
    visual = analyze_visual_intelligence(source_items, rendered)

    page_type_obj = page.get("pageType") if isinstance(page.get("pageType"), Mapping) else {}
    page_type = str(page_type_obj.get("id") or "unclassified")
    pattern_evidence = _pattern_evidence(page, responsive, visual, rendered)
    patterns = match_experience_patterns(page_type, pattern_evidence, model)

    framework_value = _normalise_token(framework) or _framework_from_sources(source_items)
    requested = [
        str(item.get("type"))
        for item in page.get("componentInventory", [])
        if isinstance(item, Mapping) and str(item.get("type") or "") in component_recipes()
    ]
    primary_task = model.get("primaryTask")
    if isinstance(primary_task, Mapping):
        primary_task = primary_task.get("value")
    components = recommend_components(
        requested,
        framework=framework_value,
        existing_imports=existing_imports,
        page_type=_PAGE_SCENARIOS.get(page_type, page_type),
        task_type=str(model.get("taskType") or primary_task or "") or None,
        information_density=str(model.get("informationDensity") or "") or None,
        risk=str(model.get("risk") or "") or None,
        project_components=project_components,
    )
    recommendations = _compose_recommendations(layout, responsive, visual, patterns, components)

    has_input = bool(source_items or screenshot)
    if not has_input:
        status = "NOT_APPLICABLE"
    elif page.get("status") != "CLASSIFIED":
        status = "DISCOVERY_REQUIRED"
    else:
        status = "DIAGNOSIS_READY"
    rendered_rows = _viewport_rows(rendered)
    result: dict[str, Any] = {
        "schemaVersion": "3.1",
        "status": status,
        "pageUnderstanding": page,
        "layoutIntelligence": layout,
        "responsiveExperience": responsive,
        "visualIntelligence": visual,
        "componentIntelligence": components,
        "patternMatches": patterns,
        "recommendations": recommendations,
        "previewPlan": {
            "mode": "interactive-before-after",
            "supportedChanges": ["layout", "tokens", "components", "theme", "density", "responsive", "state"],
            "viewports": [
                {"id": "desktop", "width": 1440},
                {"id": "tablet", "width": 768},
                {"id": "mobile", "width": 390},
            ],
            "states": ["ready", "loading", "empty", "error", "success"],
            "authority": "CANDIDATE_ONLY",
        },
        "evidenceSummary": {
            "sourceFiles": len(source_items),
            "static": bool(source_items),
            "screenshot": bool(screenshot),
            "renderedViewports": len(rendered_rows),
            "browser": bool(rendered_rows),
            "discardedUntrustedRenderedInput": bool(observed) and not bool(rendered),
            "trustedBrowserReceipt": bool(trusted_browser_evidence),
        },
        "claimBoundary": (
            "Static source and screenshot evidence produce risks and candidates. Only explicitly browser-measured "
            "observations can establish a rendered problem; user-outcome improvement still requires a controlled "
            "before/after journey or user evidence. Component and preview outputs never authorize installation or production writes."
        ),
    }
    result["experienceProof"] = build_experience_proof(
        result,
        source_items,
        experience_context=model,
        screenshot_model=screenshot,
        trusted_browser_evidence=trusted_browser_evidence,
        untrusted_observed_supplied=bool(observed) and not bool(rendered),
    )
    result["experienceConsultant"] = build_experience_consultation(
        result,
        experience_context=model,
    )
    result["diagnosisDigest"] = digest_json(result)
    return result


def collect_experience_sources(project_root: str | Path) -> tuple[list[dict[str, str]], dict[str, Any]]:
    """Read bounded Web sources using the existing project scope policy."""

    root = Path(project_root).expanduser().resolve(strict=True)
    paths, skipped, hygiene = collect_project_sources(
        root,
        suffixes=WEB_SOURCE_SUFFIXES,
        max_files=800,
        max_file_bytes=1_048_576,
        max_total_bytes=32 * 1024 * 1024,
    )
    sources: list[dict[str, str]] = []
    unreadable: list[str] = []
    for path in paths:
        relative = path.relative_to(root).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            unreadable.append(relative)
            continue
        sources.append({"path": relative, "text": text})
    return sources, {
        "root": ".",
        "sourceCount": len(sources),
        "skipped": skipped,
        "unreadable": unreadable,
        "hygiene": hygiene,
    }


def analyze_experience_project(
    project_root: str | Path,
    experience_model: Mapping[str, Any] | None = None,
    *,
    page_modes: Sequence[str] = (),
    observed: Mapping[str, Any] | None = None,
    trusted_browser_evidence: TrustedUIBrowserEvidence | None = None,
    screenshot_model: Mapping[str, Any] | None = None,
    framework: str | None = None,
    project_components: Any = None,
) -> dict[str, Any]:
    """Collect a project safely and return a sealed experience diagnosis."""

    sources, scope = collect_experience_sources(project_root)
    stack = detect_framework(project_root)
    framework_value = framework or str(stack.get("framework") or "unknown")
    package = stack.get("package") if isinstance(stack.get("package"), Mapping) else {}
    imports: list[str] = []
    for key in ("dependencies", "devDependencies", "peerDependencies"):
        if isinstance(package.get(key), Mapping):
            imports.extend(str(item) for item in package[key])
    diagnosis = build_experience_diagnosis(
        sources,
        experience_model,
        page_modes=page_modes,
        observed=observed,
        trusted_browser_evidence=trusted_browser_evidence,
        screenshot_model=screenshot_model,
        framework=framework_value,
        existing_imports=imports,
        project_components=project_components,
    )
    diagnosis.pop("diagnosisDigest", None)
    diagnosis["project"] = {
        "scope": scope,
        "framework": {
            "status": stack.get("status"),
            "selected": framework_value,
            "detected": stack.get("framework"),
            "evidence": stack.get("evidence", []),
        },
    }
    diagnosis["diagnosisDigest"] = digest_json(diagnosis)
    return diagnosis


def export_experience_analysis(
    diagnosis: Mapping[str, Any],
    output_dir: str | Path,
    *,
    title: str | None = None,
    source_screenshot: str | Path | None = None,
    preview: bool = True,
) -> dict[str, Any]:
    """Write the expert artifacts plus the additive human consultation surface."""

    out = Path(output_dir).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    diagnosis_path = out / "experience-diagnosis.json"
    diagnosis_path.write_text(
        json.dumps(dict(diagnosis), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    proof_path = None
    proof = diagnosis.get("experienceProof")
    if isinstance(proof, Mapping):
        proof_path = out / "experience-proof.json"
        proof_path.write_text(
            json.dumps(dict(proof), ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    consultant = diagnosis.get("experienceConsultant")
    if not isinstance(consultant, Mapping):
        consultant = build_experience_consultation(diagnosis)
    consultant_path = out / "experience-consultant.json"
    consultant_path.write_text(
        json.dumps(dict(consultant), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    consultant_preview_path = None
    if preview and diagnosis.get("status") != "NOT_APPLICABLE" and consultant.get("status") == "CONSULTATION_READY":
        consultant_preview_path = generate_consultant_preview(
            consultant,
            diagnosis,
            out / "consultant-preview",
            title=title,
            reference_screenshot=source_screenshot,
        )
    preview_path = None
    if preview and diagnosis.get("status") != "NOT_APPLICABLE":
        preview_path = generate_modernization_preview(
            diagnosis,
            out / "modernization-preview",
            title=title,
            source_screenshot=source_screenshot,
        )
    return {
        "status": diagnosis.get("status"),
        "diagnosis": diagnosis_path.name,
        "experienceProof": proof_path.name if proof_path else None,
        "experienceConsultant": consultant_path.name,
        "consultantPreview": (
            str(consultant_preview_path.relative_to(out)).replace("\\", "/")
            if consultant_preview_path else None
        ),
        "preview": str(preview_path.relative_to(out)).replace("\\", "/") if preview_path else None,
        "diagnosisDigest": diagnosis.get("diagnosisDigest"),
    }


__all__ = [
    "analyze_experience_project",
    "build_experience_diagnosis",
    "collect_experience_sources",
    "export_experience_analysis",
]
