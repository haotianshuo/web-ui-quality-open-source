"""Ground existing project source into a portable Design IR.

This module is used by the Codex Desktop skill runtime.  It reads only supported
Web source files, stores only project-relative paths, and creates a semantic tree
from evidence present in the project.  It deliberately avoids pretending that a
source-only scan proves rendered geometry or hidden behaviour.
"""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Mapping

from .component_registry import detect_framework
from .design_ir import build_document, make_node, make_product_node, validate_design_ir
from .design_system_map import build_design_system_map
from .scope_policy import collect_project_sources

_UI_SUFFIXES = {".html", ".htm", ".jsx", ".tsx", ".js", ".ts", ".vue", ".svelte", ".css", ".scss", ".less"}
_MAX_FILES = 180
_MAX_BYTES = 384_000

_ROLE_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("navigation", (r"<\s*(?:nav|aside)\b", r"\b(?:sidebar|navbar|navigation|menu-item|router-link|nav-item)\b", r"<(?:Link|NavLink|Menu)\b")),
    ("table", (r"<\s*table\b", r"<(?:DataTable|Table|AgGrid|GridTable)\b", r"\b(?:columns|columnDefs)\s*[:=]")),
    ("form", (r"<\s*form\b", r"<(?:Form|FormItem|Field)\b", r"\b(?:useForm|react-hook-form|vee-validate|formGroup)\b")),
    ("chart", (r"<(?:Chart|LineChart|BarChart|PieChart|AreaChart)\b", r"\b(?:recharts|echarts|apexcharts|chart\.js|highcharts|d3\.)\b", r"<\s*canvas\b")),
    ("tabs", (r"<(?:Tabs|TabList|TabPanel)\b", r"\b(?:tab-list|tabs__|role=[\"']tab)")),
    ("dialog", (r"<\s*dialog\b", r"<(?:Dialog|Modal|ConfirmDialog)\b", r"\b(?:modal|dialog)\b")),
    ("drawer", (r"<(?:Drawer|Sheet|SidePanel)\b", r"\b(?:drawer|side-panel|offcanvas)\b")),
    ("input", (r"<\s*(?:input|textarea|select)\b", r"<(?:Input|Textarea|Select|Combobox|DatePicker)\b")),
    ("button", (r"<\s*button\b", r"<(?:Button|IconButton|ActionButton)\b")),
    ("list", (r"<\s*(?:ul|ol)\b", r"<(?:List|VirtualList|Tree|MenuList)\b")),
    ("card", (r"<(?:Card|Panel|Tile|MetricCard)\b", r"\b(?:card|panel|tile)\b")),
    ("badge", (r"<(?:Badge|Tag|Chip|Status)\b", r"\b(?:badge|status-tag|chip)\b")),
    ("image", (r"<\s*img\b", r"<(?:Image|Avatar)\b")),
)

_LABELS = {
    "navigation": "Navigation", "table": "Data table", "form": "Form", "chart": "Chart",
    "tabs": "Tabs", "dialog": "Dialog", "drawer": "Drawer", "input": "Input controls",
    "button": "Actions", "list": "List", "card": "Cards", "badge": "Status", "image": "Media",
}


def _read(path: Path) -> str | None:
    try:
        if path.stat().st_size > _MAX_BYTES:
            return None
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None


def _iter_sources(root: Path) -> tuple[list[tuple[Path, str]], dict[str, Any]]:
    paths, _skipped, hygiene = collect_project_sources(
        root, suffixes=_UI_SUFFIXES, max_files=_MAX_FILES, max_file_bytes=_MAX_BYTES, max_total_bytes=12 * 1024 * 1024
    )
    result: list[tuple[Path, str]] = []
    for path in paths:
        text = _read(path)
        if text is not None:
            result.append((path, text))
    return result, hygiene


def _role_counts(text: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for role, patterns in _ROLE_PATTERNS:
        amount = 0
        for pattern in patterns:
            amount += len(re.findall(pattern, text, re.I | re.S))
        if amount:
            counts[role] = min(amount, 99)
    return counts


def _title_hint(text: str, fallback: str) -> str:
    for pattern in (r"<h1[^>]*>(.*?)</h1>", r"<title[^>]*>(.*?)</title>", r"(?:title|label|name)\s*[:=]\s*[\"']([^\"']{2,80})"):
        match = re.search(pattern, text, re.I | re.S)
        if match:
            value = re.sub(r"<[^>]+>", " ", match.group(1))
            value = re.sub(r"\s+", " ", value).strip()
            if value:
                return value[:80]
    return fallback


def _node_id(relative: str, suffix: str) -> str:
    return "src-" + sha256(f"{relative}:{suffix}".encode("utf-8")).hexdigest()[:14]


def _route_hints(text: str) -> list[str]:
    values: set[str] = set()
    patterns = (
        r"<Route\b[^>]*\bpath\s*=\s*[\"']([^\"']+)[\"']",
        r"\bpath\s*:\s*[\"'](/[^\"']*)[\"']",
        r"\b(?:router|route)\s*\.(?:add|register)\s*\(\s*[\"'](/[^\"']*)[\"']",
    )
    for pattern in patterns:
        for match in re.findall(pattern, text, re.I | re.S):
            value = str(match).strip()
            if value and not value.startswith(("http://", "https://")):
                values.add(value)
    return sorted(values)


def _build_project_product_model(
    root_name: str,
    sampled: list[dict[str, Any]],
    *,
    primary_task: str | None,
    framework: str | None,
    has_design_tokens: bool,
) -> dict[str, Any]:
    route_records: dict[str, list[dict[str, Any]]] = {}
    explicit_routes: set[str] = set()
    for record in sampled:
        routes = list(record.get("routes") or [])
        if routes:
            explicit_routes.update(str(item) for item in routes)
        else:
            routes = ["/"]
        for route in routes:
            route_records.setdefault(str(route), []).append(record)

    route_nodes: list[dict[str, Any]] = []
    for route_index, route_name in enumerate(sorted(route_records, key=lambda value: (value != "/", value))):
        regions: list[dict[str, Any]] = []
        route_sources: set[str] = set()
        for region_index, record in enumerate(route_records[route_name]):
            paths = [str(item) for item in record.get("sourceFiles", [record["path"]])]
            route_sources.update(paths)
            components: list[dict[str, Any]] = []
            for component_index, (role, count) in enumerate(sorted(record["roles"].items())):
                state_unknown = "Runtime interaction state was not observed; source syntax alone cannot prove behaviour."
                state = make_product_node(
                    f"pm-state-{route_index}-{region_index}-{component_index}", "Interaction State",
                    name=f"{_LABELS.get(role, role.title())} runtime states", evidence_class="unknown",
                    unknown=[state_unknown], source_paths=paths, confidence=0.15, responsive_status="unknown",
                    semantics={"componentRole": role, "state": "unverified"},
                )
                components.append(make_product_node(
                    f"pm-component-{route_index}-{region_index}-{component_index}", "Component",
                    name=_LABELS.get(role, role.title()), evidence_class="observed",
                    observed=[f"Project source contains {count} {role} pattern match(es)."],
                    unknown=["Rendered geometry, visibility, accessibility name, and runtime behaviour are not proven."],
                    evidence_channels={"source": paths}, source_paths=paths, confidence=0.88,
                    risk_level="medium" if role in {"form", "input", "button", "navigation"} else "low",
                    risk_reasons=["Interaction-affecting structure requires Browser verification."] if role in {"form", "input", "button", "navigation"} else [],
                    responsive_status="unknown", design_system_status="inferred" if has_design_tokens else "unknown",
                    design_system_origin="project-token-map" if has_design_tokens else "unknown",
                    semantics={"role": role, "evidenceCount": int(count)}, children=[state],
                ))
            regions.append(make_product_node(
                f"pm-region-{route_index}-{region_index}", "Region", name=str(record["name"]), evidence_class="inferred",
                inferred=["Co-located UI structures are grouped as one planning region."],
                observed=["Source files contain the listed component patterns."],
                unknown=["The rendered region boundary and placement are not observed."],
                evidence_channels={"source": paths}, source_paths=paths, confidence=0.62,
                responsive_status="unknown", design_system_status="inferred" if has_design_tokens else "unknown",
                design_system_origin="project-token-map" if has_design_tokens else "unknown",
                semantics={"structureSignature": record["structureSignature"]}, children=components,
            ))
        journey_name = primary_task or ("Primary project task" if route_name == "/" else f"Task at {route_name}")
        journey = make_product_node(
            f"pm-journey-{route_index}", "Journey", name=journey_name, evidence_class="declared" if primary_task else "inferred",
            declared=[f"Audit context declares the primary task as {primary_task}."] if primary_task else [],
            inferred=[] if primary_task else ["A route-level task is inferred only to organise source evidence."],
            unknown=["Journey completion, sequence, and success outcome are not observed."],
            evidence_channels={"source": sorted(route_sources)}, source_paths=sorted(route_sources), confidence=0.68 if primary_task else 0.42,
            risk_level="unknown", responsive_status="unknown", children=regions,
        )
        route_nodes.append(make_product_node(
            f"pm-route-{route_index}", "Route", name=route_name, evidence_class="observed" if route_name in explicit_routes else "inferred",
            observed=[f"Route path {route_name} is declared in project source."] if route_name in explicit_routes else [],
            inferred=[] if route_name in explicit_routes else ["Root route groups source without an explicit route declaration."],
            unknown=["Route reachability and runtime guards are not observed."],
            evidence_channels={"source": sorted(route_sources)}, source_paths=sorted(route_sources), confidence=0.9 if route_name in explicit_routes else 0.45,
            risk_level="unknown", responsive_status="unknown", semantics={"path": route_name}, children=[journey],
        ))
    if not route_nodes:
        unknown_state = make_product_node(
            "pm-state-unknown", "Interaction State", name="Unknown interaction state", evidence_class="unknown",
            unknown=["No runtime interaction-state evidence is available."], confidence=0.1, responsive_status="unknown",
        )
        unknown_component = make_product_node(
            "pm-component-unknown", "Component", name="Unknown component", evidence_class="unknown",
            unknown=["No semantic component structure was detected."], confidence=0.1, responsive_status="unknown",
            children=[unknown_state],
        )
        unknown_region = make_product_node(
            "pm-region-unknown", "Region", name="Unknown region", evidence_class="unknown",
            unknown=["No rendered or source-grounded region boundary is available."], confidence=0.1,
            responsive_status="unknown", children=[unknown_component],
        )
        route_nodes = [make_product_node(
            "pm-route-unknown", "Route", name="Unknown route", evidence_class="unknown",
            unknown=["No route or semantic UI structure was detected."], confidence=0.1, responsive_status="unknown",
            children=[make_product_node(
                "pm-journey-unknown", "Journey", name="Unknown journey", evidence_class="unknown",
                unknown=["No journey evidence is available."], confidence=0.1, responsive_status="unknown",
                children=[unknown_region],
            )],
        )]
    return make_product_node(
        "pm-product", "Product", name=root_name, evidence_class="declared" if primary_task else "observed",
        declared=[f"Audit context declares the primary task as {primary_task}."] if primary_task else [],
        observed=[f"Project source root is named {root_name}."], evidence_channels={"source": ["."]}, source_paths=["."],
        confidence=0.82 if primary_task else 0.65, risk_level="unknown", responsive_status="unknown",
        design_system_status="observed" if has_design_tokens else "unknown",
        design_system_origin="project-token-map" if has_design_tokens else "unknown",
        semantics={"framework": framework or "unknown", "primaryTask": primary_task}, children=route_nodes,
    )


def build_project_design_ir(project_root: str | Path, *, audit_report: Mapping[str, Any] | None = None) -> dict[str, Any]:
    root = Path(project_root).expanduser().resolve(strict=True)
    stack = detect_framework(root)
    records: list[dict[str, Any]] = []
    css_sources: list[dict[str, Any]] = []
    semantic_totals: Counter[str] = Counter()

    source_items, scope_hygiene = _iter_sources(root)
    for path, text in source_items:
        relative = path.relative_to(root).as_posix()
        if path.suffix.casefold() in {".css", ".scss", ".less"}:
            css_sources.append({"path": relative, "text": text})
        roles = _role_counts(text)
        if not roles:
            continue
        semantic_totals.update(roles)
        normalized_roles = tuple(sorted((role, min(int(count), 3)) for role, count in roles.items()))
        records.append({
            "path": relative,
            "name": _title_hint(text, path.stem.replace("-", " ").replace("_", " ").title()),
            "roles": roles,
            "weight": sum(roles.values()) + len(roles) * 3,
            "structureSignature": sha256(json.dumps(normalized_roles, separators=(",", ":")).encode("utf-8")).hexdigest()[:16],
            "routes": _route_hints(text),
        })

    records.sort(key=lambda item: (-int(item["weight"]), str(item["path"])))
    grouped: dict[str, dict[str, Any]] = {}
    for record in records:
        signature = str(record["structureSignature"])
        group = grouped.get(signature)
        if group is None:
            grouped[signature] = {**record, "sourceFiles": [record["path"]], "occurrenceCount": 1}
            continue
        group["sourceFiles"].append(record["path"])
        group["occurrenceCount"] += 1
        group["weight"] = max(int(group["weight"]), int(record["weight"]))
        for role, count in record["roles"].items():
            group["roles"][role] = int(group["roles"].get(role, 0)) + int(count)
        group["routes"] = sorted(set(group.get("routes", [])) | set(record.get("routes", [])))
    sampled = sorted(grouped.values(), key=lambda item: (-int(item["weight"]), str(item["path"])))[:18]
    sections: list[dict[str, Any]] = []
    for record in sampled:
        children: list[dict[str, Any]] = []
        roles = dict(record["roles"])
        # Preserve meaningful hierarchy instead of emitting a flat, fixed-depth tree.
        # Inputs and actions evidenced in the same file are nested under the form.
        if "form" in roles:
            form_children: list[dict[str, Any]] = []
            for nested_role in ("input", "button", "badge"):
                count = roles.pop(nested_role, 0)
                if count:
                    form_children.append(make_node(
                        _node_id(record["path"], f"form-{nested_role}"), nested_role,
                        name=f"{_LABELS.get(nested_role, nested_role.title())} · {Path(record['path']).name}",
                        semantics={"role": nested_role, "evidenceCount": count, "definitionCount": record["occurrenceCount"], "confidence": "source-grounded"},
                        source={"provider": "project-source", "path": record["path"], "relatedPaths": record["sourceFiles"][:20]},
                    ))
            form_count = roles.pop("form")
            children.append(make_node(
                _node_id(record["path"], "form"), "form",
                name=f"Form · {Path(record['path']).name}",
                semantics={"role": "form", "evidenceCount": form_count, "definitionCount": record["occurrenceCount"], "confidence": "source-grounded"},
                source={"provider": "project-source", "path": record["path"], "relatedPaths": record["sourceFiles"][:20]}, children=form_children,
            ))
        for role, count in sorted(roles.items(), key=lambda item: (-item[1], item[0])):
            children.append(make_node(
                _node_id(record["path"], role), role,
                name=f"{_LABELS.get(role, role.title())} · {Path(record['path']).name}",
                semantics={"role": role, "evidenceCount": count, "definitionCount": record["occurrenceCount"], "confidence": "source-grounded"},
                source={"provider": "project-source", "path": record["path"], "relatedPaths": record["sourceFiles"][:20]},
            ))
        sections.append(make_node(
            _node_id(record["path"], "section"), "section", name=record["name"],
            style={"display": "flex", "direction": "column", "gap": "12px"},
            semantics={
                "sourceFile": record["path"], "sourceFiles": record["sourceFiles"][:20],
                "occurrenceCount": record["occurrenceCount"], "structureSignature": record["structureSignature"],
                "detectedRoles": sorted(record["roles"]),
            },
            source={"provider": "project-source", "path": record["path"], "relatedPaths": record["sourceFiles"][:20]}, children=children,
        ))

    if not sections:
        sections = [make_node(
            "source-summary", "section", name="Project source summary",
            children=[make_node("source-card", "card", name="No semantic UI structure detected", semantics={"confidence": "insufficient-evidence"})],
        )]

    title = root.name
    primary_task: str | None = None
    if audit_report and isinstance(audit_report.get("experienceCore"), Mapping):
        model = audit_report["experienceCore"].get("experienceModel")
        if isinstance(model, Mapping) and model.get("primaryTask"):
            primary_task = str(model["primaryTask"])
            title = primary_task

    header = make_node(
        "project-header", "section", name="Project header",
        children=[make_node("project-title", "text", name="Primary task", content=title)],
    )
    main = make_node(
        "project-main", "section", name="Detected interface regions",
        style={"display": "grid", "gap": "12px"}, children=sections,
    )
    roots = [make_node(
        "project-page", "page", name=root.name,
        style={"layout": "source-grounded", "display": "flex", "direction": "column", "gap": "16px"},
        children=[header, main],
    )]

    token_map = build_design_system_map(css_sources)
    product_model = _build_project_product_model(
        root.name, sampled, primary_task=primary_task, framework=str(stack.get("framework") or "unknown"),
        has_design_tokens=bool(token_map.get("inventory")),
    )
    signature_payload = {
        "framework": stack.get("framework"),
        "paths": [item["path"] for item in sampled],
        "semanticCounts": dict(sorted(semantic_totals.items())),
        "tokenMetrics": token_map.get("metrics", {}),
    }
    project_signature = sha256(json.dumps(signature_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    document = build_document(
        source_type="project-source", source_name=root.name, roots=roots,
        metadata={
            "framework": stack.get("framework"),
            "frameworkEvidence": stack.get("evidence", []),
            "sourceFileCount": len(records),
            "sampledFileCount": len(sampled),
            "uniqueStructureCount": len(grouped),
            "duplicateStructureCount": max(0, len(records) - len(grouped)),
            "semanticCounts": dict(sorted(semantic_totals.items())),
            "deduplicatedSemanticCounts": dict(sorted(Counter(role for item in sampled for role in item["roles"]).items())),
            "scopeHygiene": scope_hygiene,
            "projectSignature": project_signature,
            "analysisConfidence": "source-grounded-not-rendered",
        },
        tokens={
            "semanticAliases": token_map.get("semanticAliases", {}),
            "metrics": token_map.get("metrics", {}),
            "inventory": token_map.get("inventory", {}),
        },
        product_model=product_model,
    )
    errors = validate_design_ir(document)
    if errors:
        raise ValueError("invalid project Design IR: " + "; ".join(errors[:5]))
    return document
