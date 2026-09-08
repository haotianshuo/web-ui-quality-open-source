"""License-aware production component registry and recommendation engine.

The registry stores metadata and integration recipes only.  It does not vendor or
copy third-party component source.  A host may install a recommended package only
with explicit user approval and must preserve the upstream license notice.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from .scope_policy import WEB_SOURCE_SUFFIXES, collect_project_sources

PERMISSIVE_LICENSES = {"MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC"}

_SOURCES: tuple[dict[str, Any], ...] = (
    {
        "id": "project-local", "name": "Project Local Components", "license": "PROJECT",
        "frameworks": ["react", "vue", "svelte", "solid", "html", "web-components"], "package": None,
        "homepage": None, "mode": "reuse-first", "priority": 100,
        "strengths": ["brand consistency", "lowest migration risk", "existing business behaviour"],
        "constraints": ["requires project component discovery and quality checks"],
    },
    {
        "id": "shadcn-ui", "name": "shadcn/ui", "license": "MIT",
        "frameworks": ["react"], "package": "registry-source", "homepage": "https://ui.shadcn.com",
        "mode": "copy-owned-code", "priority": 92,
        "strengths": ["open code", "registry distribution", "Radix-based interactions", "project-owned customisation"],
        "constraints": ["React-first", "generated code must retain applicable notices"],
    },
    {
        "id": "radix-primitives", "name": "Radix Primitives", "license": "MIT",
        "frameworks": ["react"], "package": "radix-ui", "homepage": "https://www.radix-ui.com/primitives",
        "mode": "package", "priority": 95,
        "strengths": ["accessible interaction primitives", "focus management", "unstyled", "keyboard support"],
        "constraints": ["visual styling and higher-level business components remain project work"],
    },
    {
        "id": "base-ui", "name": "Base UI", "license": "MIT",
        "frameworks": ["react"], "package": "@base-ui-components/react", "homepage": "https://base-ui.com",
        "mode": "package", "priority": 89,
        "strengths": ["unstyled accessible components", "composition", "modern React APIs"],
        "constraints": ["React-only"],
    },
    {
        "id": "react-aria", "name": "React Aria", "license": "Apache-2.0",
        "frameworks": ["react"], "package": "react-aria-components", "homepage": "https://react-spectrum.adobe.com/react-aria/",
        "mode": "package", "priority": 94,
        "strengths": ["internationalisation", "accessibility", "input modality handling", "complex collections"],
        "constraints": ["React-only", "higher implementation complexity"],
    },
    {
        "id": "headless-ui", "name": "Headless UI", "license": "MIT",
        "frameworks": ["react", "vue"], "package": "@headlessui/react", "homepage": "https://headlessui.com",
        "packageByFramework": {"react": "@headlessui/react", "vue": "@headlessui/vue"},
        "mode": "package", "priority": 85,
        "strengths": ["accessible headless interactions", "React and Vue", "Tailwind ecosystem"],
        "constraints": ["smaller primitive coverage than specialist libraries"],
    },
    {
        "id": "ark-ui", "name": "Ark UI", "license": "MIT",
        "frameworks": ["react", "vue", "svelte", "solid"], "package": "@ark-ui/react", "homepage": "https://ark-ui.com",
        "packageByFramework": {"react": "@ark-ui/react", "vue": "@ark-ui/vue", "svelte": "@ark-ui/svelte", "solid": "@ark-ui/solid"},
        "mode": "package", "priority": 91,
        "strengths": ["multi-framework headless components", "state machines", "accessible primitives"],
        "constraints": ["package names vary by framework"],
    },
    {
        "id": "mantine", "name": "Mantine", "license": "MIT",
        "frameworks": ["react"], "package": "@mantine/core", "homepage": "https://mantine.dev",
        "mode": "package", "priority": 82,
        "strengths": ["large production component set", "hooks", "forms", "dates", "theming"],
        "constraints": ["stronger library visual/API conventions"],
    },
    {
        "id": "chakra-ui", "name": "Chakra UI", "license": "MIT",
        "frameworks": ["react"], "package": "@chakra-ui/react", "homepage": "https://chakra-ui.com",
        "mode": "package", "priority": 80,
        "strengths": ["accessible styled system", "tokens", "responsive props", "enterprise adoption"],
        "constraints": ["React-only", "runtime/styling conventions affect migration"],
    },
    {
        "id": "ant-design", "name": "Ant Design", "license": "MIT",
        "frameworks": ["react"], "package": "antd", "homepage": "https://ant.design",
        "mode": "package", "priority": 84,
        "strengths": ["enterprise forms", "data display", "tables", "internationalisation", "mature ecosystem"],
        "constraints": ["strong design language", "bundle and migration cost must be measured"],
    },
    {
        "id": "mui-material", "name": "Material UI", "license": "MIT",
        "frameworks": ["react"], "package": "@mui/material", "homepage": "https://mui.com/material-ui/",
        "mode": "package", "priority": 86,
        "strengths": ["production-ready React components", "responsive layout", "theming", "broad component coverage"],
        "constraints": [
            "Material UI official documentation currently implements Material Design 2; Material Design 3 guidance is not equivalent to MUI",
            "React-only", "advanced data-grid capability is provided separately by MUI X",
        ],
    },
    {
        "id": "mui-x", "name": "MUI X Data Grid", "license": "MIT",
        "frameworks": ["react"], "package": "@mui/x-data-grid", "homepage": "https://mui.com/x/react-data-grid/",
        "mode": "package", "priority": 93,
        "strengths": ["virtualisation", "editing", "sorting and filtering", "large-data grid", "advanced data workflows"],
        "licenseTiers": {
            "community": {"package": "@mui/x-data-grid", "license": "MIT"},
            "pro": {"package": "@mui/x-data-grid-pro", "license": "commercial"},
            "premium": {"package": "@mui/x-data-grid-premium", "license": "commercial"},
        },
        "constraints": [
            "the resolved default package is the MIT Community tier",
            "multi-filtering, multi-sorting, pinning, tree data, grouping, pivoting, aggregation, Excel export and other advanced features vary by Pro or Premium commercial tier",
            "the required license tier must be reviewed before claiming an advanced feature is available",
        ],
    },
    {
        "id": "fluent-ui", "name": "Fluent UI", "license": "MIT",
        "frameworks": ["react", "html", "web-components"], "package": "@fluentui/react-components",
        "packageByFramework": {
            "react": "@fluentui/react-components",
            "html": "@fluentui/web-components",
            "web-components": "@fluentui/web-components",
        },
        "homepage": "https://fluent2.microsoft.design/get-started/develop", "mode": "package", "priority": 87,
        "strengths": ["enterprise interaction patterns", "React and Web Components", "accessible feedback", "Microsoft ecosystem"],
        "constraints": ["framework component coverage and maturity must be checked for the selected platform"],
    },
    {
        "id": "carbon", "name": "Carbon Design System", "license": "Apache-2.0",
        "frameworks": ["react", "html", "web-components"], "package": "@carbon/react",
        "packageByFramework": {
            "react": "@carbon/react",
            "html": "@carbon/web-components",
            "web-components": "@carbon/web-components",
        },
        "homepage": "https://carbondesignsystem.com", "mode": "package", "priority": 88,
        "strengths": ["enterprise dashboards", "data-dense layouts", "forms", "data tables", "accessibility guidance"],
        "constraints": [
            "official framework support is React and Web Components; other adapters are community supported",
            "Carbon explicitly states that its data table is not a replacement for a spreadsheet application",
        ],
    },
    {
        "id": "tdesign", "name": "TDesign", "license": "MIT",
        "frameworks": ["react", "vue"], "package": "tdesign-react", "homepage": "https://tdesign.tencent.com",
        "packageByFramework": {"react": "tdesign-react", "vue": "tdesign-vue-next"},
        "mode": "package", "priority": 83,
        "strengths": ["enterprise patterns", "React/Vue", "Chinese product conventions"],
        "constraints": ["framework package names vary"],
    },
    {
        "id": "arco-design", "name": "Arco Design", "license": "MIT",
        "frameworks": ["react", "vue"], "package": "@arco-design/web-react", "homepage": "https://arco.design",
        "packageByFramework": {"react": "@arco-design/web-react", "vue": "@arco-design/web-vue"},
        "mode": "package", "priority": 83,
        "strengths": ["enterprise components", "theme tooling", "React/Vue", "Pro layouts"],
        "constraints": ["framework package names vary"],
    },
    {
        "id": "semi-design", "name": "Semi Design", "license": "MIT",
        "frameworks": ["react"], "package": "@douyinfe/semi-ui", "homepage": "https://semi.design",
        "mode": "package", "priority": 82,
        "strengths": ["B2B components", "design tokens", "complex content and forms"],
        "constraints": ["React-first"],
    },
    {
        "id": "daisyui", "name": "daisyUI", "license": "MIT",
        "frameworks": ["html", "react", "vue", "svelte"], "package": "daisyui", "homepage": "https://daisyui.com",
        "packageByFramework": {"html": "daisyui", "react": "daisyui", "vue": "daisyui", "svelte": "daisyui"},
        "mode": "package", "priority": 70,
        "strengths": ["framework-agnostic class components", "themes", "rapid prototypes"],
        "constraints": ["interaction behaviour must still be provided and tested"],
    },
    {
        "id": "native-web", "name": "Native Web Platform", "license": "PLATFORM",
        "frameworks": ["html", "react", "vue", "svelte", "solid", "web-components"], "package": None, "homepage": "https://developer.mozilla.org",
        "mode": "native", "priority": 75,
        "strengths": ["lowest dependency cost", "progressive enhancement", "portable semantics"],
        "constraints": ["complex composite widgets require careful accessibility engineering"],
    },
)

_COMPONENT_RECIPES: dict[str, dict[str, Any]] = {
    "button": {"sources": ["project-local", "shadcn-ui", "react-aria", "base-ui", "native-web", "fluent-ui", "mui-material", "carbon", "ant-design"], "required": ["focus-visible", "disabled", "loading", "icon-label"]},
    "input": {"sources": ["project-local", "carbon", "fluent-ui", "mantine", "ant-design", "mui-material", "react-aria", "native-web"], "required": ["label", "description", "error", "autocomplete"]},
    "select": {"sources": ["project-local", "radix-primitives", "react-aria", "ark-ui", "headless-ui"], "required": ["typeahead", "keyboard", "portal", "collision"]},
    "combobox": {"sources": ["project-local", "react-aria", "ark-ui", "mantine", "ant-design"], "required": ["async", "empty", "keyboard", "virtualisation-option"]},
    "dialog": {"sources": ["project-local", "radix-primitives", "headless-ui", "ark-ui", "fluent-ui", "carbon", "mui-material", "ant-design", "react-aria", "base-ui"], "required": ["focus-trap", "restore-focus", "escape", "scroll-lock"]},
    "drawer": {"sources": ["project-local", "ark-ui", "ant-design", "tdesign", "arco-design"], "required": ["focus", "close", "mobile-sheet", "safe-area"]},
    "popover": {"sources": ["project-local", "radix-primitives", "base-ui", "react-aria", "ark-ui"], "required": ["collision", "focus", "dismiss", "anchor"]},
    "tooltip": {"sources": ["project-local", "radix-primitives", "react-aria", "base-ui", "ark-ui"], "required": ["delay", "keyboard", "touch-alternative", "aria-description"]},
    "tabs": {"sources": ["project-local", "radix-primitives", "headless-ui", "ark-ui", "fluent-ui", "carbon", "mui-material", "ant-design", "react-aria", "base-ui"], "required": ["keyboard", "activation-mode", "overflow", "deep-link"]},
    "toast": {"sources": ["project-local", "radix-primitives", "ark-ui", "mantine", "chakra-ui"], "required": ["live-region", "timeout", "pause", "action"]},
    "table": {"sources": ["project-local", "carbon", "ant-design", "fluent-ui", "mui-material", "arco-design", "tdesign", "semi-design"], "required": ["responsive-strategy", "sort", "empty", "loading", "row-actions"]},
    "data-grid": {"sources": ["project-local", "mui-x", "ant-design", "carbon", "fluent-ui", "arco-design", "tdesign", "semi-design"], "required": ["virtualisation", "column-management", "keyboard", "selection", "bulk-action"]},
    "form": {"sources": ["project-local", "carbon", "ant-design", "mantine", "fluent-ui", "mui-material", "react-aria", "semi-design"], "required": ["validation", "dirty", "submit-state", "error-summary", "restore"]},
    "date-picker": {"sources": ["project-local", "react-aria", "mantine", "ant-design", "tdesign"], "required": ["locale", "keyboard", "range", "timezone", "invalid"]},
    "tree": {"sources": ["project-local", "react-aria", "ant-design", "arco-design", "tdesign"], "required": ["keyboard", "lazy", "selection", "search", "large-data"]},
    "command-menu": {"sources": ["project-local", "shadcn-ui", "react-aria", "ark-ui"], "required": ["search", "keyboard", "groups", "recent", "escape"]},
    "upload": {"sources": ["project-local", "ant-design", "arco-design", "tdesign", "semi-design"], "required": ["progress", "pause", "retry", "partial-failure", "size-type-validation"]},
    "navigation": {"sources": ["project-local", "carbon", "fluent-ui", "ant-design", "mui-material", "shadcn-ui", "radix-primitives", "tdesign"], "required": ["current", "keyboard", "collapse", "mobile", "permission"]},
    "modal": {"aliasOf": "dialog", "sources": ["project-local", "radix-primitives", "headless-ui", "ark-ui", "fluent-ui", "carbon", "mui-material", "ant-design", "react-aria", "base-ui"], "required": ["focus-trap", "restore-focus", "escape", "scroll-lock"]},
    "card": {"sources": ["project-local", "fluent-ui", "mui-material", "mantine", "ant-design", "carbon", "shadcn-ui", "native-web"], "required": ["single-concept", "focus-visible", "selected-state", "responsive-content", "action-semantics"]},
    "filter": {"sources": ["project-local", "carbon", "mui-x", "ant-design", "shadcn-ui", "ark-ui", "headless-ui", "react-aria"], "required": ["applied-state", "clear-all", "keyboard", "empty", "instant-or-batch", "responsive"]},
    "dashboard": {"sources": ["project-local", "ant-design", "carbon", "shadcn-ui", "mantine", "fluent-ui", "mui-material"], "required": ["shell", "responsive-grid", "information-hierarchy", "loading-empty-error", "filter-state", "action-path"]},
}


def source_catalog() -> list[dict[str, Any]]:
    return [deepcopy(item) for item in _SOURCES]


def component_recipes() -> dict[str, dict[str, Any]]:
    return deepcopy(_COMPONENT_RECIPES)


def validate_source(source: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    license_id = str(source.get("license") or "")
    if license_id not in PERMISSIVE_LICENSES | {"PROJECT", "PLATFORM"}:
        errors.append(f"unsupported or review-required license: {license_id}")
    if not source.get("id") or not source.get("name"):
        errors.append("source id and name are required")
    if not isinstance(source.get("frameworks"), list) or not source.get("frameworks"):
        errors.append("frameworks must be a non-empty list")
    package_by_framework = source.get("packageByFramework")
    if package_by_framework is not None:
        if not isinstance(package_by_framework, Mapping) or not package_by_framework:
            errors.append("packageByFramework must be a non-empty object when provided")
        else:
            frameworks = {str(item) for item in source.get("frameworks", [])}
            for framework, package in package_by_framework.items():
                if str(framework) not in frameworks:
                    errors.append(f"packageByFramework contains undeclared framework: {framework}")
                if not isinstance(package, str) or not package.strip():
                    errors.append(f"packageByFramework package must be a non-empty string: {framework}")
    return errors


def load_external_registry(path: str | Path) -> list[dict[str, Any]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    items = data.get("sources") if isinstance(data, dict) else data
    if not isinstance(items, list):
        raise ValueError("registry must be an array or an object with sources")
    result = []
    for item in items:
        if not isinstance(item, Mapping):
            raise ValueError("registry source must be an object")
        errors = validate_source(item)
        if errors:
            raise ValueError("; ".join(errors))
        result.append(dict(item))
    return result


def detect_framework(project_root: str | Path) -> dict[str, Any]:
    root = Path(project_root).expanduser().resolve()
    package: dict[str, Any] = {}
    candidate_scores: dict[str, int] = {
        "react": 0, "vue": 0, "svelte": 0, "angular": 0,
        "solid": 0, "html": 0, "web-components": 0,
    }
    candidate_evidence: dict[str, list[str]] = {key: [] for key in candidate_scores}
    package_path = root / "package.json"
    dependencies: dict[str, Any] = {}
    if package_path.is_file():
        try:
            package = json.loads(package_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            package = {}
        for key in ("dependencies", "devDependencies", "peerDependencies"):
            if isinstance(package.get(key), Mapping):
                dependencies.update(package[key])
        checks = (
            ("next", "react", 8), ("react", "react", 6),
            ("vue", "vue", 6), ("svelte", "svelte", 6),
            ("@angular/core", "angular", 7), ("solid-js", "solid", 7),
            ("lit", "web-components", 6),
        )
        for package_name, value, weight in checks:
            if package_name in dependencies:
                candidate_scores[value] += weight
                candidate_evidence[value].append(f"package.json:{package_name}")

    source_paths, _skipped, scope_hygiene = collect_project_sources(
        root, suffixes=WEB_SOURCE_SUFFIXES, max_files=800, max_file_bytes=1_048_576, max_total_bytes=32 * 1024 * 1024
    )
    suffix_counts: dict[str, int] = {}
    for path in source_paths:
        suffix = path.suffix.casefold()
        suffix_counts[suffix] = suffix_counts.get(suffix, 0) + 1
    source_checks = (
        (".vue", "vue", 3), (".svelte", "svelte", 3),
        (".jsx", "react", 2), (".tsx", "react", 1),
        (".html", "html", 1), (".htm", "html", 1),
    )
    for suffix, value, weight in source_checks:
        count = suffix_counts.get(suffix, 0)
        if count:
            candidate_scores[value] += min(12, count * weight)
            candidate_evidence[value].append(f"source:{suffix}×{count}")

    ranked = sorted(candidate_scores.items(), key=lambda item: (-item[1], item[0]))
    positive = [item for item in ranked if item[1] > 0]
    ambiguous = len(positive) > 1 and positive[0][1] == positive[1][1]
    framework = "unknown" if not positive or ambiguous else positive[0][0]
    evidence = (
        [value for name, _score in positive for value in candidate_evidence[name]]
        if ambiguous
        else list(candidate_evidence.get(framework, []))
    )
    status = (
        "AMBIGUOUS_FRAMEWORK" if ambiguous
        else "DETECTED" if framework != "unknown"
        else "FRAMEWORK_NOT_SUPPORTED"
    )
    package_manager = _package_manager(root)
    return {
        "status": status,
        "framework": framework,
        "evidence": evidence,
        "evidenceCount": len(evidence),
        "frameworkCandidates": [
            {"framework": name, "score": score, "evidence": candidate_evidence[name]}
            for name, score in positive
        ],
        "webSourceCount": len(source_paths),
        "packageManager": package_manager,
        "package": package,
        "scopeHygiene": scope_hygiene,
    }


def _package_manager(root: Path) -> str | None:
    if (root / "pnpm-lock.yaml").is_file(): return "pnpm"
    if (root / "yarn.lock").is_file(): return "yarn"
    if (root / "bun.lockb").is_file() or (root / "bun.lock").is_file(): return "bun"
    if (root / "package-lock.json").is_file() or (root / "package.json").is_file(): return "npm"
    return None


def _source_by_id(source_id: str, sources: Iterable[Mapping[str, Any]]) -> dict[str, Any] | None:
    for source in sources:
        if source.get("id") == source_id:
            return dict(source)
    return None


_HEADLESS_SOURCE_IDS = frozenset({
    "radix-primitives", "react-aria", "base-ui", "ark-ui", "headless-ui",
})
_OPEN_CODE_SOURCE_IDS = frozenset({"shadcn-ui"})
_STYLED_SUITE_SOURCE_IDS = frozenset({
    "mantine", "chakra-ui", "ant-design", "mui-material", "fluent-ui", "carbon",
    "tdesign", "arco-design", "semi-design", "daisyui",
})
_DATA_SUITE_SOURCE_IDS = frozenset({"mui-x"})
_MATURE_ENTERPRISE_SOURCE_IDS = frozenset({
    "ant-design", "mui-material", "mui-x", "fluent-ui", "carbon",
    "mantine", "tdesign", "arco-design", "semi-design",
})
_DATA_COMPONENTS = frozenset({"table", "data-grid", "filter", "dashboard"})
_PAGE_SOURCE_FIT: dict[str, frozenset[str]] = {
    "dashboard": frozenset({"ant-design", "carbon", "fluent-ui", "mui-material", "mui-x", "mantine", "shadcn-ui"}),
    "crm": frozenset({"ant-design", "carbon", "fluent-ui", "mui-material", "mui-x", "tdesign", "arco-design", "semi-design"}),
    "erp": frozenset({"ant-design", "carbon", "fluent-ui", "mui-x", "tdesign", "arco-design", "semi-design"}),
    "admin": frozenset({"ant-design", "carbon", "fluent-ui", "mui-material", "mui-x", "mantine", "tdesign", "arco-design", "semi-design"}),
    "landing": frozenset({"shadcn-ui", "mui-material", "mantine", "chakra-ui", "daisyui"}),
    "mobile": frozenset({"mui-material", "fluent-ui", "mantine", "shadcn-ui", "radix-primitives", "headless-ui", "ark-ui"}),
    "saas": frozenset({"ant-design", "carbon", "fluent-ui", "mui-material", "mantine", "shadcn-ui"}),
}
_PROJECT_COMPONENT_TERMS: dict[str, tuple[str, ...]] = {
    "button": ("button", "action", "cta"),
    "input": ("input", "field", "search"),
    "select": ("select", "picker", "dropdown"),
    "combobox": ("combobox", "autocomplete", "typeahead"),
    "dialog": ("dialog", "modal"),
    "drawer": ("drawer", "sheet", "panel"),
    "popover": ("popover", "flyout"),
    "tooltip": ("tooltip", "hint"),
    "tabs": ("tabs", "tablist"),
    "toast": ("toast", "notice", "message"),
    "table": ("table", "grid"),
    "data-grid": ("datatable", "data-grid", "datagrid", "table", "grid"),
    "form": ("form", "wizard"),
    "card": ("card", "tile"),
    "filter": ("filter", "query"),
    "dashboard": ("dashboard", "workspace", "workbench"),
    "navigation": ("navigation", "nav", "sidebar", "menu"),
}


def _normalise_choice(value: Any) -> str | None:
    normalised = str(value or "").strip().casefold().replace("_", "-").replace(" ", "-")
    return normalised or None


def _normalise_density(value: Any) -> str | None:
    density = _normalise_choice(value)
    aliases = {
        "dense": "high", "compact": "high", "high-density": "high",
        "comfortable": "low", "spacious": "low", "low-density": "low",
        "medium": "default", "normal": "default", "standard": "default",
    }
    return aliases.get(density, density)


def _resolve_package(source: Mapping[str, Any], framework: str) -> str | None:
    by_framework = source.get("packageByFramework")
    if isinstance(by_framework, Mapping):
        value = by_framework.get(framework)
        return str(value) if value else None
    package = source.get("package")
    return str(package) if package else None


def _resolve_package_for_project(
    source: Mapping[str, Any],
    framework: str,
    import_items: set[str],
    imports_text: str,
) -> str | None:
    default = _resolve_package(source, framework)
    tiers = source.get("licenseTiers")
    if isinstance(tiers, Mapping):
        for tier in ("premium", "pro", "community"):
            details = tiers.get(tier)
            package = details.get("package") if isinstance(details, Mapping) else None
            if package and _package_in_imports(str(package), import_items, imports_text):
                return str(package)
    return default


def _resolved_license(source: Mapping[str, Any], resolved_package: str | None) -> tuple[str | None, str]:
    tiers = source.get("licenseTiers")
    if isinstance(tiers, Mapping):
        for tier, details in tiers.items():
            if isinstance(details, Mapping) and details.get("package") == resolved_package:
                return str(tier), str(details.get("license") or source.get("license") or "")
    return None, str(source.get("license") or "")


def _source_architecture(source: Mapping[str, Any]) -> str:
    source_id = str(source.get("id") or "")
    if source_id == "project-local":
        return "project-local"
    if source.get("mode") == "native":
        return "native"
    if source_id in _OPEN_CODE_SOURCE_IDS:
        return "open-code"
    if source_id in _HEADLESS_SOURCE_IDS:
        return "headless"
    if source_id in _DATA_SUITE_SOURCE_IDS:
        return "data-suite"
    if source_id in _STYLED_SUITE_SOURCE_IDS:
        return "styled-suite"
    return "package"


def _package_in_imports(package: str | None, import_items: set[str], imports_text: str) -> bool:
    if not package:
        return False
    target = package.casefold()
    return target in import_items or any(item.startswith(f"{target}/") for item in import_items) or target in imports_text


def _framework_matches(source: Mapping[str, Any], framework: str) -> bool:
    return framework in {str(item).casefold() for item in source.get("frameworks", [])}


def _normalise_project_components(project_components: Any) -> list[dict[str, Any]]:
    if project_components is None:
        return []
    raw_items: list[Any]
    if isinstance(project_components, Mapping):
        nested = project_components.get("components")
        if isinstance(nested, list):
            raw_items = list(nested)
        elif any(key in project_components for key in ("name", "path", "role", "component", "type")):
            raw_items = [project_components]
        else:
            raw_items = []
            for role, value in project_components.items():
                if isinstance(value, Mapping):
                    raw_items.append({"role": role, **dict(value)})
                elif isinstance(value, list):
                    raw_items.extend(
                        {"role": role, **dict(item)} if isinstance(item, Mapping)
                        else {"role": role, "name": str(item)}
                        for item in value
                    )
                elif value:
                    raw_items.append({"role": role, "name": str(value)})
    elif isinstance(project_components, (str, bytes)):
        raw_items = [project_components]
    else:
        raw_items = list(project_components)
    result: list[dict[str, Any]] = []
    for item in raw_items:
        if isinstance(item, Mapping):
            result.append(dict(item))
        elif item is not None:
            result.append({"name": str(item)})
    return result


def _project_component_match(
    component: str,
    project_components: Iterable[Mapping[str, Any]],
    framework: str,
) -> dict[str, Any] | None:
    canonical = "dialog" if component == "modal" else component
    terms = _PROJECT_COMPONENT_TERMS.get(canonical, (canonical.replace("-", ""),))
    ranked: list[tuple[int, str, dict[str, Any]]] = []
    for raw in project_components:
        item = dict(raw)
        framework_hint = _normalise_choice(item.get("frameworkHint") or item.get("framework"))
        if framework_hint and framework_hint != framework:
            continue
        haystack = " ".join(
            str(item.get(key) or "") for key in ("name", "path", "role", "component", "type")
        ).casefold().replace("_", "").replace("-", "").replace(" ", "")
        score = sum(3 for term in terms if term.replace("-", "").replace(" ", "") in haystack)
        role = _normalise_choice(item.get("role") or item.get("component") or item.get("type"))
        if role in {component, canonical}:
            score += 5
        if score <= 0:
            continue
        signals = item.get("qualitySignals") if isinstance(item.get("qualitySignals"), Mapping) else {}
        score += sum(int(bool(signals.get(key))) for key in ("hasAria", "hasTests", "hasStory"))
        evidence = deepcopy(item)
        evidence["matchScore"] = score
        ranked.append((score, str(item.get("path") or item.get("name") or ""), evidence))
    ranked.sort(key=lambda entry: (-entry[0], entry[1]))
    return ranked[0][2] if ranked else None


def _task_group(task_type: str | None) -> str | None:
    if not task_type:
        return None
    if any(token in task_type for token in ("data", "analytic", "report", "table", "grid", "pivot")):
        return "data-intensive"
    if any(token in task_type for token in ("crud", "workflow", "approval", "operation", "admin")):
        return "workflow"
    if any(token in task_type for token in ("form", "entry", "onboarding", "checkout")):
        return "form"
    if any(token in task_type for token in ("brand", "custom", "design-system")):
        return "custom-design"
    if any(token in task_type for token in ("content", "marketing", "landing")):
        return "content"
    return task_type


def _score_candidate(
    source: Mapping[str, Any],
    *,
    component: str,
    rank: int,
    resolved_package: str | None,
    import_items: set[str],
    imports_text: str,
    prefer_headless: bool,
    page_type: str | None,
    task_type: str | None,
    density: str | None,
    risk: str | None,
    project_match: Mapping[str, Any] | None,
    legacy_project_local: bool,
) -> tuple[int, dict[str, int], dict[str, Any], list[str], list[str], str]:
    source_id = str(source.get("id") or "")
    architecture = _source_architecture(source)
    canonical = "dialog" if component == "modal" else component
    existing = _package_in_imports(resolved_package, import_items, imports_text)
    desired_architecture = (
        "filter-composition" if canonical == "filter"
        else "data-capable-suite" if canonical in _DATA_COMPONENTS
        else "headless-or-open-code" if prefer_headless
        else "styled-suite"
    )
    breakdown: dict[str, int] = {
        "catalogPriority": int(source.get("priority", 50)),
        "recipeOrder": -rank * 2,
        "existingSystem": 40 if existing else 0,
        "projectLocal": 60 if project_match else 25 if legacy_project_local and source_id == "project-local" else 0,
        "architecture": 0,
        "pageScenario": 0,
        "taskScenario": 0,
        "density": 0,
        "dataCapability": 0,
        "risk": 0,
    }
    reasons: list[str] = []
    if existing:
        reasons.append(f"项目已使用当前框架包 {resolved_package}，优先避免引入第二套系统")
    if project_match:
        reasons.append("发现与请求角色匹配的真实项目组件，优先复用并降低迁移风险")
    elif legacy_project_local and source_id == "project-local":
        reasons.append("兼容旧 __project_local__ 信号；该信号未提供真实组件证据")
    if source_id == "project-local":
        breakdown["architecture"] = 18
        architecture_status = "preferred-project"
    elif existing:
        breakdown["architecture"] = 14
        architecture_status = "preferred-existing"
    elif desired_architecture == "filter-composition":
        if architecture == "styled-suite":
            breakdown["architecture"] = 10
            architecture_status = "preferred"
        elif architecture in {"headless", "open-code"}:
            breakdown["architecture"] = 7
            architecture_status = "compatible"
        elif architecture == "data-suite":
            breakdown["architecture"] = 4
            architecture_status = "compatible"
        else:
            breakdown["architecture"] = -2
            architecture_status = "tradeoff"
    elif desired_architecture == "data-capable-suite":
        if architecture == "data-suite":
            breakdown["architecture"] = 18
            architecture_status = "preferred"
        elif architecture == "styled-suite":
            breakdown["architecture"] = 9
            architecture_status = "compatible"
        else:
            breakdown["architecture"] = -12 if architecture in {"headless", "open-code"} else -4
            architecture_status = "tradeoff"
    elif desired_architecture == "headless-or-open-code":
        if architecture in {"headless", "open-code"}:
            breakdown["architecture"] = 12
            architecture_status = "preferred"
        elif architecture == "native":
            breakdown["architecture"] = 4
            architecture_status = "compatible"
        else:
            breakdown["architecture"] = -3
            architecture_status = "tradeoff"
    else:
        if architecture in {"styled-suite", "data-suite"}:
            breakdown["architecture"] = 10
            architecture_status = "preferred"
        else:
            breakdown["architecture"] = -2
            architecture_status = "tradeoff"
    if breakdown["architecture"] > 0:
        reasons.append(f"{architecture} 架构与当前 {desired_architecture} 决策匹配")
    if page_type and source_id in _PAGE_SOURCE_FIT.get(page_type, frozenset()):
        breakdown["pageScenario"] = 8
        reasons.append(f"官方能力形态适合 {page_type} 页面")
    task_group = _task_group(task_type)
    task_fit = {
        "data-intensive": {"mui-x", "ant-design", "carbon", "fluent-ui", "arco-design", "tdesign", "semi-design"},
        "workflow": {"ant-design", "carbon", "fluent-ui", "mantine", "mui-material", "tdesign", "arco-design", "semi-design"},
        "form": {"carbon", "ant-design", "mantine", "fluent-ui", "react-aria", "semi-design"},
        "custom-design": {"shadcn-ui", "radix-primitives", "headless-ui", "ark-ui", "base-ui", "react-aria"},
        "content": {"shadcn-ui", "mui-material", "mantine", "chakra-ui", "daisyui"},
    }
    if task_group and source_id in task_fit.get(task_group, set()):
        breakdown["taskScenario"] = 10 if task_group in {"data-intensive", "workflow", "form"} else 7
        reasons.append(f"组件生态与 {task_group} 任务类型匹配")
    if density == "high":
        if source_id in {"carbon", "ant-design", "fluent-ui", "mui-x", "arco-design", "tdesign", "semi-design"}:
            breakdown["density"] = 10
            reasons.append("支持数据密集或企业紧凑工作区")
        elif source_id in {"mui-material", "mantine"}:
            breakdown["density"] = 4
        elif source_id == "daisyui":
            breakdown["density"] = -3
    elif density == "low" and source_id in {
        "shadcn-ui", "mui-material", "mantine", "chakra-ui",
        "radix-primitives", "headless-ui", "ark-ui",
    }:
        breakdown["density"] = 6
        reasons.append("适合舒展、品牌化的信息呈现")
    data_fit = {
        "table": {"carbon": 14, "ant-design": 13, "fluent-ui": 9, "mui-material": 8},
        "data-grid": {"mui-x": 20, "ant-design": 14, "carbon": 10, "fluent-ui": 9, "arco-design": 8, "tdesign": 8, "semi-design": 8},
        "filter": {"carbon": 14, "mui-x": 12, "ant-design": 12, "ark-ui": 5, "headless-ui": 5, "react-aria": 5, "shadcn-ui": 7},
        "dashboard": {"ant-design": 14, "carbon": 14, "fluent-ui": 9, "mui-material": 9, "mantine": 9, "shadcn-ui": 9},
    }
    breakdown["dataCapability"] = data_fit.get(canonical, {}).get(source_id, 0)
    if breakdown["dataCapability"] > 0:
        reasons.append(f"目录证据覆盖 {canonical} 所需的数据或页面能力")
    if risk == "high":
        if project_match or existing:
            breakdown["risk"] = 12
            reasons.append("高风险任务优先已存在且可在项目中验证的实现")
        elif source_id in _MATURE_ENTERPRISE_SOURCE_IDS:
            breakdown["risk"] = 6
        elif architecture in {"headless", "open-code"}:
            breakdown["risk"] = -4
    limitations = list(source.get("constraints", []))
    if source_id == "project-local" and project_match:
        limitations.append("发现项目组件只证明存在与命名匹配，仍需验证行为、可访问性、响应式和业务状态。")
    if source_id == "project-local" and legacy_project_local and not project_match:
        limitations.append("__project_local__ 是 legacy 兼容信号，不是可核验的项目组件证据。")
    if architecture in {"headless", "open-code"}:
        limitations.append("无样式或开放源码方案仍需项目实现并验证视觉、密度、动效和业务状态。")
    evidence_level = (
        "project-component" if project_match
        else "legacy-sentinel" if source_id == "project-local" and legacy_project_local
        else "existing-dependency" if existing
        else "catalog-only"
    )
    if evidence_level == "catalog-only":
        limitations.append("仅有目录与官方能力元数据，未验证当前项目中的运行时实现。")
    architecture_fit = {
        "requested": desired_architecture,
        "source": architecture,
        "status": architecture_status,
        "score": breakdown["architecture"],
    }
    score = sum(breakdown.values())
    return score, breakdown, architecture_fit, reasons, list(dict.fromkeys(limitations)), evidence_level


def _fit_assessment(
    source: Mapping[str, Any],
    *,
    resolved_package: str | None,
    import_items: set[str],
    imports_text: str,
    required_contract: Iterable[str],
    architecture_fit: Mapping[str, Any],
    evidence_level: str,
) -> dict[str, Any]:
    """Explain integration risk without pretending catalog metadata proves runtime quality."""
    source_id = str(source.get("id") or "")
    architecture = _source_architecture(source)
    already_present = (
        source_id == "project-local" and evidence_level == "project-component"
    ) or _package_in_imports(resolved_package, import_items, imports_text)
    resolved_tier, resolved_license = _resolved_license(source, resolved_package)
    if source.get("license") == "PROJECT":
        license_status = "PROJECT_OWNED"
    elif resolved_tier in {"pro", "premium"}:
        license_status = "COMMERCIAL_LICENSE_REVIEW_REQUIRED"
    elif source_id == "mui-x":
        license_status = "COMMUNITY_MIT_TIER_REVIEW_REQUIRED"
    else:
        license_status = "ALLOWLISTED_REVIEW_REQUIRED"
    return {
        "existingInProject": already_present,
        "evidenceLevel": evidence_level,
        "implementationStatus": "CANDIDATE_ONLY",
        "licenseStatus": license_status,
        "resolvedLicenseTier": resolved_tier,
        "resolvedLicense": resolved_license,
        "migrationRisk": (
            "low" if source_id == "project-local"
            else "medium-high" if architecture in {"styled-suite", "data-suite"}
            else "medium"
        ),
        "bundleRisk": (
            "existing-project" if source_id == "project-local"
            else "measure-full-suite" if architecture in {"styled-suite", "data-suite"}
            else "measure-selected-primitives"
        ),
        "architectureFit": dict(architecture_fit),
        "requiredBehaviourVerification": list(required_contract),
        "requiredEvidence": [
            "真实项目构建通过",
            "键盘、焦点、错误和响应式合同通过",
            "比较按需引入前后的 bundle 与开发启动成本",
            "确认上游版本、传递依赖、许可证和声明",
        ],
        "claimBoundary": "目录或命名证据只证明候选适配，不证明组件在当前项目中已正确实现。",
    }


def _why_not_alternatives(
    selected: Mapping[str, Any] | None,
    alternatives: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    if not selected:
        return []
    result: list[dict[str, Any]] = []
    selected_score = int(selected.get("score", 0))
    selected_existing = bool((selected.get("fitAssessment") or {}).get("existingInProject"))
    for alternative in alternatives:
        reasons = [f"可解释评分低 {max(0, selected_score - int(alternative.get('score', 0)))} 分"]
        alternative_existing = bool((alternative.get("fitAssessment") or {}).get("existingInProject"))
        if selected_existing and not alternative_existing:
            reasons.append("当前项目没有该备选依赖或真实组件证据")
        selected_arch = (selected.get("architectureFit") or {}).get("status")
        alternative_arch = (alternative.get("architectureFit") or {}).get("status")
        if selected_arch in {"preferred-project", "preferred-existing", "preferred"} and alternative_arch == "tradeoff":
            reasons.append("架构类型与当前决策上下文的匹配度较低")
        if alternative.get("id") == "mui-x":
            reasons.append("高级能力需额外核对 Pro/Premium 商业许可层级")
        result.append({
            "id": alternative.get("id"),
            "scoreDelta": selected_score - int(alternative.get("score", 0)),
            "reasons": reasons,
            "claimBoundary": "未选择不代表组件质量较差，只表示当前证据和上下文下排序较低。",
        })
    return result


def recommend_components(
    requested: Iterable[str],
    *,
    framework: str,
    existing_imports: Iterable[str] | None = None,
    prefer_headless: bool = True,
    additional_sources: Iterable[Mapping[str, Any]] | None = None,
    page_type: str | None = None,
    task_type: str | None = None,
    information_density: str | None = None,
    risk: str | None = None,
    project_components: Any = None,
) -> dict[str, Any]:
    sources = source_catalog() + [dict(item) for item in (additional_sources or [])]
    framework_value = _normalise_choice(framework) or "unknown"
    import_items = {str(item).strip().casefold() for item in (existing_imports or []) if str(item).strip()}
    imports_text = " ".join(sorted(import_items))
    legacy_project_local = "__project_local__" in imports_text
    project_items = _normalise_project_components(project_components)
    page_value = _normalise_choice(page_type)
    task_value = _normalise_choice(task_type)
    density_value = _normalise_density(information_density)
    risk_value = _normalise_choice(risk)
    supported_frameworks = {
        str(item).casefold() for source in sources for item in source.get("frameworks", [])
    }
    existing_systems = []
    for source in sources:
        package = _resolve_package_for_project(source, framework_value, import_items, imports_text)
        if package and _package_in_imports(package, import_items, imports_text):
            existing_systems.append(str(source.get("id")))
    context = {
        "pageType": page_value,
        "taskType": task_value,
        "informationDensity": density_value,
        "risk": risk_value,
        "preferHeadless": bool(prefer_headless),
        "existingImports": sorted(item for item in import_items if item != "__project_local__"),
        "existingSystems": list(dict.fromkeys(existing_systems)),
        "projectComponents": {
            "provided": len(project_items),
            "legacySentinelUsed": legacy_project_local,
            "legacy": legacy_project_local,
        },
    }
    policy = {
        "licenseAllowlist": sorted(PERMISSIVE_LICENSES),
        "reuseProjectComponentsFirst": True,
        "noAutomaticInstallation": True,
        "noVendoredThirdPartySource": True,
    }
    base_limitations = [
        "推荐结果是 CANDIDATE_ONLY；目录、导入或命名证据均不证明实现完成。",
        "安装、版本选择、许可证、bundle 和真实交互仍需项目级验证。",
    ]
    if not any((page_value, task_value, density_value, risk_value)):
        base_limitations.append("未提供页面、任务、密度或风险上下文，场景评分只使用已有系统、架构和组件能力证据。")
    if legacy_project_local:
        base_limitations.append("__project_local__ 仅作为 legacy 兼容信号；应改用 project_components 提供真实组件证据。")
    if framework_value not in supported_frameworks:
        return {
            "schemaVersion": "2.2",
            "status": "FRAMEWORK_NOT_SUPPORTED",
            "implementationStatus": "NOT_APPLICABLE",
            "claimBoundary": "不支持的框架不会获得虚构组件或包管理器回退。",
            "framework": framework_value,
            "policy": policy,
            "decisionContext": context,
            "architectureFit": None,
            "limitations": base_limitations,
            "whyNotAlternatives": [],
            "recommendations": [],
            "reason": "No supported Web framework evidence was found; no component or package-manager fallback was invented.",
        }
    recommendations: list[dict[str, Any]] = []
    project_match_count = 0
    for raw_component in dict.fromkeys(str(item) for item in requested):
        component = _normalise_choice(raw_component) or raw_component
        recipe = _COMPONENT_RECIPES.get(
            component,
            {"sources": ["project-local", "native-web"], "required": ["keyboard", "focus", "error", "responsive"]},
        )
        canonical = str(recipe.get("aliasOf") or component)
        project_match = _project_component_match(component, project_items, framework_value)
        if project_match:
            project_match_count += 1
        candidates: list[dict[str, Any]] = []
        for rank, source_id in enumerate(recipe["sources"]):
            source = _source_by_id(source_id, sources)
            if source_id == "project-local" and not project_match and not legacy_project_local:
                continue
            if not source or not _framework_matches(source, framework_value):
                continue
            errors = validate_source(source)
            if errors:
                continue
            resolved_package = _resolve_package_for_project(source, framework_value, import_items, imports_text)
            if isinstance(source.get("packageByFramework"), Mapping) and source.get("mode") == "package" and not resolved_package:
                continue
            score, breakdown, architecture_fit, score_reasons, limitations, evidence_level = _score_candidate(
                source,
                component=component,
                rank=rank,
                resolved_package=resolved_package,
                import_items=import_items,
                imports_text=imports_text,
                prefer_headless=prefer_headless,
                page_type=page_value,
                task_type=task_value,
                density=density_value,
                risk=risk_value,
                project_match=project_match if source_id == "project-local" else None,
                legacy_project_local=legacy_project_local,
            )
            resolved_tier, resolved_license = _resolved_license(source, resolved_package)
            candidate = {
                **source,
                "declaredPackage": source.get("package"),
                "package": resolved_package,
                "resolvedPackage": resolved_package,
                "resolvedLicenseTier": resolved_tier,
                "resolvedLicense": resolved_license,
                "score": score,
                "scoreBreakdown": breakdown,
                "rankReason": score_reasons or ["与当前框架和组件合同匹配"],
                "architectureFit": architecture_fit,
                "limitations": limitations,
                "evidenceLevel": evidence_level,
                "implementationStatus": "CANDIDATE_ONLY",
                "legacyProjectLocal": bool(source_id == "project-local" and legacy_project_local and not project_match),
            }
            if source_id == "project-local" and project_match:
                candidate["projectComponent"] = deepcopy(project_match)
            candidate["fitAssessment"] = _fit_assessment(
                source,
                resolved_package=resolved_package,
                import_items=import_items,
                imports_text=imports_text,
                required_contract=recipe["required"],
                architecture_fit=architecture_fit,
                evidence_level=evidence_level,
            )
            candidates.append(candidate)
        candidates.sort(key=lambda item: (-int(item["score"]), str(item["id"])))
        selected = candidates[0] if candidates else None
        alternatives = candidates[1:4]
        recommendations.append({
            "component": component,
            "canonicalComponent": canonical,
            "requiredContract": list(recipe["required"]),
            "recommended": selected,
            "alternatives": alternatives,
            "architectureFit": deepcopy(selected.get("architectureFit")) if selected else None,
            "limitations": list(selected.get("limitations", [])) if selected else ["没有找到具有足够框架证据的候选实现。"],
            "whyNotAlternatives": _why_not_alternatives(selected, alternatives),
            "implementationStatus": "CANDIDATE_ONLY",
        })
    context["projectComponents"]["matchedRecommendations"] = project_match_count
    selected_architectures = sorted({
        str((item.get("recommended") or {}).get("architectureFit", {}).get("source"))
        for item in recommendations if item.get("recommended")
    })
    return {
        "schemaVersion": "2.2",
        "status": "READY",
        "implementationStatus": "CANDIDATE_ONLY",
        "claimBoundary": "推荐只确定候选与验证合同，不声明组件已在项目中实现。",
        "framework": framework_value,
        "policy": policy,
        "decisionContext": context,
        "architectureFit": {
            "selectedArchitectures": selected_architectures,
            "existingSystemFirstApplied": bool(existing_systems or project_match_count),
            "legacyCompatibilityApplied": legacy_project_local,
        },
        "limitations": base_limitations,
        "whyNotAlternatives": [
            {"component": item["component"], "alternatives": item["whyNotAlternatives"]}
            for item in recommendations
        ],
        "recommendations": recommendations,
    }


def build_install_plan(recommendation: Mapping[str, Any], package_manager: str | None = None) -> dict[str, Any]:
    packages: list[str] = []
    sources: list[dict[str, Any]] = []
    for item in recommendation.get("recommendations", []) if isinstance(recommendation.get("recommendations"), list) else []:
        selected = item.get("recommended")
        if not isinstance(selected, Mapping):
            continue
        package = selected.get("resolvedPackage", selected.get("package"))
        already_present = bool((selected.get("fitAssessment") or {}).get("existingInProject"))
        if package and not already_present and package not in packages and package != "registry-source":
            packages.append(str(package))
        if selected.get("id") not in {source.get("id") for source in sources}:
            sources.append(dict(selected))
    if recommendation.get("status") == "FRAMEWORK_NOT_SUPPORTED":
        return {
            "status": "NOT_APPLICABLE",
            "packageManager": None,
            "packages": [],
            "suggestedCommand": None,
            "sources": [],
            "reason": "FRAMEWORK_NOT_SUPPORTED",
            "notice": "No package-manager or installation command was inferred without Web framework evidence.",
        }
    command = None
    if packages and package_manager:
        prefix = {"npm": "npm install", "pnpm": "pnpm add", "yarn": "yarn add", "bun": "bun add"}.get(package_manager)
        if prefix:
            command = f"{prefix} {' '.join(packages)}"
    return {
        "status": "APPROVAL_REQUIRED" if packages and command else "NO_INSTALL_REQUIRED",
        "packageManager": package_manager,
        "packages": packages,
        "suggestedCommand": command,
        "sources": [
            {
                "id": item.get("id"),
                "license": item.get("license"),
                "homepage": item.get("homepage"),
                "resolvedPackage": item.get("resolvedPackage", item.get("package")),
                "resolvedLicenseTier": item.get("resolvedLicenseTier"),
                "resolvedLicense": item.get("resolvedLicense"),
                "licenseTiers": item.get("licenseTiers"),
            }
            for item in sources
        ],
        "notice": "The command is a suggestion only. Review versions, transitive dependencies, bundle impact, and license notices before execution.",
    }
