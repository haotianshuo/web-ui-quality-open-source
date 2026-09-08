"""Project-specific selector and design-token grounding for implementation candidates.

The implementation layer must not assume that every product calls its shell
``.app`` or its primary workspace ``.workspace``.  This module extracts bounded,
source-grounded class/id evidence and maps it to UI roles that the candidate
styles can consume.  The mapping is deliberately portable and never contains an
absolute project path.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import json
from pathlib import Path
import re
from typing import Any, Mapping

from .design_system_map import build_design_system_map
from .scope_policy import collect_project_sources


_SUFFIXES = {".html", ".htm", ".jsx", ".tsx", ".js", ".ts", ".vue", ".svelte", ".css", ".scss", ".less"}
_CLASS_VALUE = re.compile(r"(?:class|className)\s*=\s*[\"']([^\"']+)[\"']", re.I)
_ID_VALUE = re.compile(r"\bid\s*=\s*[\"']([A-Za-z_][\w-]*)[\"']", re.I)
_CSS_CLASS = re.compile(r"(?<![\w-])\.([A-Za-z_][\w-]*)")
_COMPONENT = re.compile(r"<([A-Z][A-Za-z0-9]*(?:[._-][A-Za-z0-9]+)*)\b")
_SAFE_TOKEN = re.compile(r"^[A-Za-z_][\w-]*$")


_ROLE_TERMS: dict[str, tuple[str, ...]] = {
    "shell": ("app", "app-shell", "application", "shell", "product-shell", "site-shell", "dashboard-shell", "layout"),
    "navigation": ("nav", "navbar", "navigation", "sidebar", "side-nav", "sidenav", "topbar", "top-bar", "menu", "rail"),
    "pageHeader": ("page-head", "page-header", "hero", "masthead", "intro", "titlebar", "title-bar", "heading"),
    "toolbar": ("toolbar", "tool-bar", "controls", "control-bar", "command-bar", "filters", "filter-bar", "searchbar", "search-bar"),
    "workspace": ("workspace", "canvas", "work-area", "content-grid", "dashboard", "dashboard-grid", "split-view", "main-content"),
    "collection": ("list-panel", "collection", "results", "result-list", "data-grid", "record-list", "account-list", "accounts", "records", "customers", "products", "catalog", "feed", "table-wrap"),
    "detail": ("detail", "inspector", "record-detail", "record-inspector", "preview", "drawer", "side-panel"),
    "item": ("account", "record", "result", "row", "list-item", "collection-item", "customer", "product-item"),
    "facts": ("facts", "stats", "metrics", "metadata", "summary-grid", "key-values", "attributes"),
    "fact": ("fact", "stat", "metric", "datum", "attribute"),
    "actions": ("actions", "action-bar", "button-row", "cta-row", "form-actions", "footer-actions"),
    "brand": ("logo", "brand", "wordmark"),
    "profile": ("profile", "user-profile", "profile-menu", "user-menu", "account-menu", "avatar-menu"),
    "status": ("status", "toast", "notice", "alert", "feedback", "empty-state", "error-state"),
}

_STRUCTURAL_FALLBACKS: dict[str, tuple[str, ...]] = {
    "shell": ("[data-app]", "#app", "#root", "body"),
    "navigation": ("[role=\"navigation\"]", "nav", "body > aside"),
    "pageHeader": ("main > header", "main > :first-child"),
    "toolbar": ("[role=\"search\"]", "main form"),
    "workspace": ("main",),
    "collection": ("main table", "main ul", "main ol"),
    "detail": ("[role=\"dialog\"]", "dialog", "main article"),
    "item": ("tbody > tr", "main li"),
    "facts": ("dl",),
    "fact": ("dl > div",),
    "actions": ("[role=\"toolbar\"]", "form > footer"),
    "brand": ("[aria-label*=\"home\" i]",),
    "profile": ("[aria-label*=\"account\" i]", "[aria-label*=\"profile\" i]"),
    "status": ("[role=\"status\"]", "[role=\"alert\"]"),
}


def _normalise_token(token: str) -> str:
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "-", token).casefold().replace("_", "-")


def _role_token_allowed(role: str, token: str) -> bool:
    """Reject common container/action collisions before compiling selectors."""
    lowered = _normalise_token(token)
    parts = [part for part in lowered.split("-") if part]
    if role == "item":
        if parts and parts[0] in {"add", "create", "new", "edit", "delete", "remove", "open", "close"}:
            return False
        if parts and parts[-1] in {"count", "total", "list", "grid", "panel", "table", "collection", "container"}:
            return False
        if lowered in {"accounts", "records", "results", "customers", "products", "items"}:
            return False
    if role == "fact" and lowered in {"facts", "stats", "metrics", "metadata", "attributes"}:
        return False
    if role == "detail" and parts and parts[-1] in {"top", "head", "header", "body", "content", "footer", "actions", "title"}:
        return False
    return True


def _score(token: str, terms: tuple[str, ...]) -> int:
    lowered = _normalise_token(token)
    parts = set(part for part in lowered.split("-") if part)
    best = 0
    for term in terms:
        normalized = term.casefold()
        if lowered == normalized:
            best = max(best, 12)
        elif normalized in parts:
            best = max(best, 8)
        elif len(normalized) >= 4 and normalized in lowered:
            best = max(best, 5)
    return best


def _sources(root: Path) -> tuple[list[dict[str, str]], dict[str, Any]]:
    paths, _skipped, hygiene = collect_project_sources(
        root,
        suffixes=_SUFFIXES,
        max_files=220,
        max_file_bytes=512_000,
        max_total_bytes=16 * 1024 * 1024,
    )
    result: list[dict[str, str]] = []
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        result.append({"path": path.relative_to(root).as_posix(), "text": text})
    return result, hygiene


def build_project_semantic_map(project_root: str | Path) -> dict[str, Any]:
    """Return source-grounded selectors, tokens, and a visible coverage boundary."""
    root = Path(project_root).expanduser().resolve(strict=True)
    sources, hygiene = _sources(root)
    tokens: Counter[str] = Counter()
    ids: Counter[str] = Counter()
    components: Counter[str] = Counter()
    token_files: dict[str, set[str]] = defaultdict(set)
    css_sources: list[dict[str, str]] = []
    for source in sources:
        path = source["path"]
        text = source["text"]
        suffix = Path(path).suffix.casefold()
        if suffix in {".css", ".scss", ".less"}:
            css_sources.append(source)
        for value in _CLASS_VALUE.findall(text):
            for token in value.split():
                if _SAFE_TOKEN.fullmatch(token):
                    tokens[token] += 3
                    token_files[token].add(path)
        for token in _CSS_CLASS.findall(text):
            if _SAFE_TOKEN.fullmatch(token):
                tokens[token] += 1
                token_files[token].add(path)
        for token in _ID_VALUE.findall(text):
            ids[token] += 2
            token_files[token].add(path)
        components.update(_COMPONENT.findall(text))

    role_candidates: dict[str, list[tuple[int, int, str, str]]] = defaultdict(list)
    for token, frequency in tokens.items():
        for role, terms in _ROLE_TERMS.items():
            if not _role_token_allowed(role, token):
                continue
            score = _score(token, terms)
            if score:
                role_candidates[role].append((score, frequency, f".{token}", token))
    for token, frequency in ids.items():
        for role, terms in _ROLE_TERMS.items():
            if not _role_token_allowed(role, token):
                continue
            score = _score(token, terms)
            if score:
                role_candidates[role].append((score + 1, frequency, f"#{token}", token))

    roles: dict[str, Any] = {}
    project_selector_count = 0
    for role in _ROLE_TERMS:
        ranked = sorted(role_candidates.get(role, []), key=lambda item: (-item[0], -item[1], item[2]))
        selectors: list[str] = []
        evidence: list[dict[str, Any]] = []
        for score, frequency, selector, token in ranked:
            if selector in selectors:
                continue
            selectors.append(selector)
            evidence.append({
                "selector": selector,
                "score": score,
                "occurrences": frequency,
                "sourceFiles": sorted(token_files[token])[:8],
            })
            if len(selectors) == 6:
                break
        project_selector_count += len(selectors)
        roles[role] = {
            "projectSelectors": selectors,
            "fallbackSelectors": list(_STRUCTURAL_FALLBACKS.get(role, ())),
            "evidence": evidence,
            "status": "PROJECT_GROUNDED" if selectors else "STRUCTURAL_FALLBACK",
        }

    grounded_roles = sum(1 for value in roles.values() if value["projectSelectors"])
    design_system = build_design_system_map(css_sources)
    return {
        "schemaVersion": "1",
        "status": "PROJECT_SEMANTICS_READY" if grounded_roles >= 3 else "PARTIAL_PROJECT_SEMANTICS",
        "projectRoot": ".",
        "sourceFileCount": len(sources),
        "roles": roles,
        "coverage": {
            "roleCount": len(roles),
            "groundedRoleCount": grounded_roles,
            "projectSelectorCount": project_selector_count,
            "ratio": round(grounded_roles / max(len(roles), 1), 3),
            "claimBoundary": "Selectors are source-grounded candidates; Browser rendering decides whether they own the intended region.",
        },
        "components": [{"name": name, "occurrences": count} for name, count in components.most_common(30)],
        "designSystem": design_system,
        "scopeHygiene": hygiene,
    }


def selectors_for_role(
    semantic_map: Mapping[str, Any] | None,
    role: str,
    legacy: tuple[str, ...] = (),
) -> str:
    """Compile a bounded selector group with project evidence first."""
    roles = semantic_map.get("roles") if isinstance(semantic_map, Mapping) and isinstance(semantic_map.get("roles"), Mapping) else {}
    record = roles.get(role) if isinstance(roles.get(role), Mapping) else {}
    values: list[str] = []
    for group in (record.get("projectSelectors", []), legacy, record.get("fallbackSelectors", [])):
        if not isinstance(group, (list, tuple)):
            continue
        for value in group:
            token = str(value)
            if token and token not in values:
                values.append(token)
    return ":where(" + ",".join(values[:12] or ["[data-wuq-unmatched]"]) + ")"


def write_project_design_context(context: Mapping[str, Any], output_dir: str | Path) -> dict[str, str]:
    """Persist portable main-path design evidence for review and packaging."""
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    artifacts: dict[str, str] = {}
    names = {
        "semanticMap": "project-semantic-map.json",
        "designIr": "project-design-ir.json",
        "designCandidates": "project-design-candidates.json",
        "designSystem": "project-design-system-map.json",
    }
    for key, name in names.items():
        value = context.get(key)
        if not isinstance(value, Mapping):
            continue
        (output / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        artifacts[key] = name
    return artifacts
