"""Read-only Core MVP for evidence-backed Web UI audits."""

from __future__ import annotations

import html as html_lib
import re
from collections import Counter
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from time import perf_counter
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import urlsplit, urlunsplit

from .contracts import (
    ContractViolation,
    build_source_scope_manifest,
    plan_digest,
    redact_text,
    sha256_hex,
    source_scope_fingerprint,
    validate_finding,
    validate_productization_plan,
)
from .builtin_rules import coverage_for_findings
from .design_context import build_project_reference
from .provider_registry import default_provider_registry
from .product_decision import PageProfile, profile_from_facts, rank_directions
from .business_context import normalize as normalize_business_context
from .scope_policy import EXCLUDED_DIR_NAMES, EXCLUDED_FILE_NAMES, WEB_SOURCE_SUFFIXES, collect_project_sources, is_excluded_parts
from .experience_core import build_experience_core
from .trusted_evidence import (
    TrustedRealTargetContext,
    TrustedUIBrowserEvidence,
    browser_payload,
    require_browser_evidence,
    require_real_target,
)


SUPPORTED_SUFFIXES = set(WEB_SOURCE_SUFFIXES)
EXCLUDED_DIRS = set(EXCLUDED_DIR_NAMES)
EXCLUDED_NAMES = set(EXCLUDED_FILE_NAMES)
MAX_SOURCE_BYTES = 1024 * 1024
MAX_SOURCE_FILES = 600
MAX_TOTAL_SOURCE_BYTES = 24 * 1024 * 1024
SECRET_ASSIGN_RE = re.compile(
    r"(?i)\b(api[_-]?key|access[_-]?token|auth[_-]?token|password|passwd|client[_-]?secret)\b"
    r"\s*(?:=|:)\s*['\"]([^'\"]{8,})['\"]"
)
PROMPT_INJECTION_RE = re.compile(
    r"(?i)(ignore\s+(?:all\s+)?previous\s+instructions|"
    r"reveal\s+(?:the\s+)?system\s+prompt|"
    r"read\s+(?:credentials|cookies|tokens)|"
    r"write\s+outside\s+(?:the\s+)?project)"
)
PLACEHOLDER_RE = re.compile(r"(?i)\b(TODO|FIXME|lorem\s+ipsum)\b|占位内容|演示数据")
DANGEROUS_DOM_PATTERNS = (
    (re.compile(r"\.innerHTML\s*="), "DIRECT_INNER_HTML"),
    (re.compile(r"\.outerHTML\s*="), "DIRECT_OUTER_HTML"),
    (re.compile(r"\binsertAdjacentHTML\s*\("), "INSERT_ADJACENT_HTML"),
    (re.compile(r"\bdocument\.write(?:ln)?\s*\("), "DOCUMENT_WRITE"),
    (re.compile(r"\bdangerouslySetInnerHTML\s*="), "REACT_DANGEROUS_HTML"),
    (re.compile(r"\bsrcdoc\s*="), "IFRAME_SRCDOC"),
    (re.compile(r"\.html\s*\("), "JQUERY_HTML_WRITE"),
)
OUTLINE_NONE_RE = re.compile(r"(?i)\boutline\s*:\s*(?:none|0)\b")
TOKEN_RE = re.compile(r"(--[A-Za-z0-9_-]+)\s*:")
SCRIPT_BLOCK_RE = re.compile(r"(?is)<script\b(?P<attrs>[^>]*)>(?P<body>.*?)</script\s*>")
HTML_ATTR_RE = re.compile(
    r'''(?ix)(?P<name>[A-Za-z_:][-A-Za-z0-9_:.]*)\s*=\s*(?:"(?P<double>[^"]*)"|'(?P<single>[^']*)'|(?P<bare>[^\s>]+))'''
)
ESM_SYNTAX_RE = re.compile(
    r"(?m)^[ \t]*(?:import\s+(?:(?:[\w*$]+|\{[^\n}]*\}|\*\s+as\s+\w+)\s+from\s+)?['\"]|export\s+(?:default\b|\{[^\n}]*\}|(?:const|let|var|function|class)\b|\*\s+from\s+['\"]))"
)
FILTER_ACTION_RE = re.compile(r"(?i)^(?:筛选|过滤|filter)$")
FILTER_CONTROL_RE = re.compile(r"(?i)(?:筛选|过滤|搜索|查询|filter|search|query)")
STATE_GROUPS = {
    "loading": re.compile(r"(?i)(?:加载中|正在加载|loading|processing)"),
    "empty": re.compile(r"(?i)(?:暂无(?:数据|内容|结果)|空数据|empty|no\s+(?:data|results?))"),
    "failure": re.compile(r"(?i)(?:加载失败|请求失败|出错|error|failed|failure)"),
    "success": re.compile(r"(?i)(?:加载成功|操作成功|已完成|success|succeeded|completed?)"),
}
JSX_POINTER_ONLY_TAG_RE = re.compile(
    r"(?is)<(?P<tag>div|span|li|p|td|tr|section|article|header|footer|nav|aside)\b(?P<attrs>[^>]*?)>"
)
JSX_POINTER_HANDLER_RE = re.compile(r"(?i)(?:^|\s)on(?:click|doubleclick)(?:capture)?\s*=")
JSX_KEYBOARD_HANDLER_RE = re.compile(r"(?i)(?:^|\s)onkey(?:down|up|press)(?:capture)?\s*=")
JSX_ROLE_RE = re.compile(r"(?i)(?:^|\s)role\s*=")
JSX_TAB_INDEX_RE = re.compile(r"(?i)(?:^|\s)tabindex\s*=")
NESTED_KEYBOARD_VISIBLE_ITEMS_RE = re.compile(
    r"(?ims)^\s*(?:get\s+)?visibleItems\s*(?:\([^)]*\))?\s*\{(?P<body>.*?)(?=^\s*(?:get\s+)?processedItems\b)"
)
NESTED_KEYBOARD_PARENT_GUARD_RE = re.compile(
    r"(?i)\bprocessedItem\s*&&\s*processedItem\.key\s*===\s*this\.focusedItemInfo\(\)\.parentKey\b"
)


def _split_values(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in re.split(r"[|,]", value) if part.strip()]


@dataclass
class HtmlFacts:
    ids: list[tuple[str, int]] = field(default_factory=list)
    label_for: set[str] = field(default_factory=set)
    controls: list[tuple[str, dict[str, str], int]] = field(default_factory=list)
    images: list[tuple[dict[str, str], int]] = field(default_factory=list)
    anchors: list[tuple[dict[str, str], int]] = field(default_factory=list)
    buttons: list[tuple[dict[str, str], int, str]] = field(default_factory=list)
    headings: list[tuple[str, int, str]] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)
    table_headers: list[str] = field(default_factory=list)
    metrics: list[str] = field(default_factory=list)
    tags: Counter[str] = field(default_factory=Counter)
    text: list[str] = field(default_factory=list)
    work_modes: set[str] = field(default_factory=set)
    prototypes: set[str] = field(default_factory=set)
    entities: set[str] = field(default_factory=set)
    roles: set[str] = field(default_factory=set)
    operations: set[str] = field(default_factory=set)
    states: set[str] = field(default_factory=set)
    constraints: set[str] = field(default_factory=set)
    table_rows: int = 0
    max_table_columns: int = 0


class EvidenceHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.facts = HtmlFacts()
        self._capture: list[tuple[str, int, dict[str, str], list[str]]] = []
        self._row_columns = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        line, _ = self.getpos()
        normalized = {key.casefold(): value or "" for key, value in attrs}
        tag = tag.casefold()
        self.facts.tags[tag] += 1
        if normalized.get("id"):
            self.facts.ids.append((normalized["id"], line))
        if tag == "label" and normalized.get("for"):
            self.facts.label_for.add(normalized["for"])
        if tag in {"input", "select", "textarea"}:
            self.facts.controls.append((tag, normalized, line))
        elif tag == "img":
            self.facts.images.append((normalized, line))
        elif tag == "a":
            self.facts.anchors.append((normalized, line))
        if tag in {"button", "label", "th", "h1", "h2", "h3", "title"}:
            self._capture.append((tag, line, normalized, []))
        if tag == "tr":
            self._row_columns = 0
            self.facts.table_rows += 1
        elif tag in {"th", "td"}:
            self._row_columns += 1
            self.facts.max_table_columns = max(self.facts.max_table_columns, self._row_columns)
        for key, target in (
            ("data-work-mode", self.facts.work_modes),
            ("data-product-archetype", self.facts.prototypes),
            ("data-entity", self.facts.entities),
            ("data-role", self.facts.roles),
            ("data-action", self.facts.operations),
            ("data-state", self.facts.states),
            ("data-constraint", self.facts.constraints),
        ):
            target.update(_split_values(normalized.get(key)))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.casefold()
        if not self._capture:
            return
        capture_tag, line, attrs, chunks = self._capture[-1]
        if capture_tag != tag:
            return
        self._capture.pop()
        text = re.sub(r"\s+", " ", " ".join(chunks)).strip()
        if tag == "button":
            self.facts.buttons.append((attrs, line, text))
        elif tag == "label" and text:
            self.facts.labels.append(text)
        elif tag == "th" and text:
            self.facts.table_headers.append(text)
        elif tag in {"h1", "h2", "h3", "title"} and text:
            self.facts.headings.append((tag, line, text))
        if tag == "tr":
            self._row_columns = 0

    def handle_data(self, data: str) -> None:
        value = re.sub(r"\s+", " ", data).strip()
        if value:
            self.facts.text.append(value)
            for index in range(len(self._capture)):
                self._capture[index][3].append(value)
            if re.fullmatch(r"(?:[$¥€£]?\s*)?\d[\d,.%+\-]*", value) and len(value) <= 24:
                self.facts.metrics.append(value)


class CanonicalEvidenceParser(HTMLParser):
    """Drop executable/dynamic markup while preserving auditable HTML semantics."""

    SKIPPED = {"script", "style", "noscript", "template"}
    STABLE_ATTRIBUTES = {"id", "name", "type", "role", "target", "rel", "alt", "for", "lang", "title"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.output: list[str] = []
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.casefold()
        if tag in self.SKIPPED:
            self.skip_depth += 1
            return
        if self.skip_depth:
            return
        stable: list[tuple[str, str]] = []
        for key, raw_value in attrs:
            key = key.casefold()
            value = re.sub(r"\s+", " ", (raw_value or "").strip())
            if key in self.STABLE_ATTRIBUTES or key.startswith("aria-") or key.startswith("data-ui-audit-"):
                stable.append((key, value))
            elif key == "href":
                parts = urlsplit(value)
                stable.append((key, urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))))
        stable.sort()
        rendered = "".join(
            f' {key}="{html_lib.escape(value, quote=True)}"' for key, value in stable
        )
        self.output.append(f"<{tag}{rendered}>")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.casefold()
        if tag in self.SKIPPED:
            if self.skip_depth:
                self.skip_depth -= 1
            return
        if not self.skip_depth:
            self.output.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        if self.skip_depth:
            return
        value = re.sub(r"\s+", " ", data).strip()
        if value:
            self.output.append(html_lib.escape(value))


def canonicalize_external_html(content: str) -> str:
    parser = CanonicalEvidenceParser()
    parser.feed(content)
    parser.close()
    return "".join(parser.output)


@dataclass(frozen=True)
class SourceFile:
    path: str
    text: str


def _source_inventory(root: Path) -> tuple[list[Path], list[dict[str, Any]], dict[str, Any]]:
    files, skipped, hygiene = collect_project_sources(
        root,
        suffixes=SUPPORTED_SUFFIXES,
        max_files=MAX_SOURCE_FILES,
        max_file_bytes=MAX_SOURCE_BYTES,
        max_total_bytes=MAX_TOTAL_SOURCE_BYTES,
    )
    escaped = [item for item in skipped if item.get("reason") == "SOURCE_SCOPE_ESCAPE"]
    if escaped:
        raise ContractViolation("SOURCE_SCOPE_ESCAPE", [f"$.path: source resolves outside project root: {escaped[0].get('path')}"])
    return files, skipped, hygiene


def _project_rules(root: Path) -> tuple[list[str], list[str]]:
    paths: list[str] = []
    constraints: set[str] = set()
    directive_re = re.compile(
        r"(?i)(?:^|[。；;])\s*((?:不得|禁止|不要|必须保留|必须|never|do not|must preserve|must)\b[^\n。；;]{2,240})"
    )
    for name in ("AGENTS.override.md", "AGENTS.md"):
        for candidate in root.rglob(name):
            relative = candidate.relative_to(root)
            if is_excluded_parts(relative.parts):
                continue
            resolved = candidate.resolve(strict=True)
            try:
                resolved.relative_to(root)
            except ValueError:
                continue
            paths.append(relative.as_posix())
            if candidate.stat().st_size <= 256 * 1024:
                try:
                    text = candidate.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    text = candidate.read_text(encoding="utf-8", errors="replace")
                for match in directive_re.finditer(text):
                    value = re.sub(r"\s+", " ", match.group(1)).strip(" -*#")
                    if value and PROMPT_INJECTION_RE.search(value) is None:
                        constraints.add(value)
    return sorted(set(paths)), sorted(constraints)


def _read_sources(root: Path) -> tuple[list[SourceFile], list[dict[str, Any]], dict[str, Any]]:
    files, skipped, hygiene = _source_inventory(root)
    sources: list[SourceFile] = []
    for path in files:
        relative = path.relative_to(root).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = path.read_text(encoding="utf-8", errors="replace")
        sources.append(SourceFile(relative, text))
    return sources, skipped, hygiene


def _line_for(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _html_attrs(raw: str) -> dict[str, str]:
    attrs: dict[str, str] = {}
    for match in HTML_ATTR_RE.finditer(raw):
        attrs[match.group("name").casefold()] = (
            match.group("double") or match.group("single") or match.group("bare") or ""
        )
    return attrs


def _local_script_source(source: SourceFile, src: str, sources: dict[str, SourceFile]) -> SourceFile | None:
    clean = src.split("#", 1)[0].split("?", 1)[0].replace("\\", "/")
    if not clean or clean.startswith(("/", "//")) or ":" in clean or "{{" in clean or "<%" in clean:
        return None
    candidate = (Path(source.path).parent / clean).as_posix()
    parts: list[str] = []
    for part in candidate.split("/"):
        if part in {"", "."}:
            continue
        if part == "..":
            if not parts:
                return None
            parts.pop()
        else:
            parts.append(part)
    return sources.get("/".join(parts))


def _semantic_findings(
    sources: list[SourceFile],
    html: dict[str, HtmlFacts],
    factory: "FindingFactory",
) -> None:
    by_path = {source.path: source for source in sources}
    for source in sources:
        if source.path not in html:
            continue

        for script in SCRIPT_BLOCK_RE.finditer(source.text):
            attrs = _html_attrs(script.group("attrs"))
            script_type = attrs.get("type", "").strip().casefold()
            if script_type == "module" or (script_type and script_type not in {
                "text/javascript", "application/javascript", "text/ecmascript", "application/ecmascript"
            }):
                continue
            script_source = _local_script_source(source, attrs["src"], by_path) if attrs.get("src") else None
            inspected = script_source.text if script_source else script.group("body")
            if not inspected or ESM_SYNTAX_RE.search(inspected) is None:
                continue
            factory.add(
                "SEM-SCRIPT-MODULE-MISMATCH",
                category="logic",
                severity="P1",
                file=source.path,
                line=_line_for(source.text, script.start()),
                selector="script",
                summary="经典 script 加载路径包含可确定识别的 ESM import/export 语法。",
                impact="浏览器会按经典脚本解析，模块语法可能导致页面脚本无法执行。",
                recommendation="将该 script 明确标记为 type=\"module\"，或改为加载不含 ESM 语法的经典构建产物。",
                reason_code="CLASSIC_SCRIPT_WITH_ESM_SYNTAX",
            )

        facts = html[source.path]
        declares_filter = any(FILTER_ACTION_RE.fullmatch(item.strip()) for item in facts.operations)
        if declares_filter:
            has_control = False
            for tag_match in re.finditer(
                r"(?is)<(?P<tag>input|select|button|form)\b(?P<attrs>[^>]*)>(?P<body>.*?</(?P=tag)\s*>)?",
                source.text,
            ):
                attrs = _html_attrs(tag_match.group("attrs"))
                searchable = " ".join(
                    attrs.get(key, "") for key in ("id", "name", "class", "role", "aria-label", "title", "placeholder")
                ) + " " + re.sub(r"<[^>]+>", " ", tag_match.group("body") or "")
                if attrs.get("type", "").casefold() == "search" or FILTER_CONTROL_RE.search(searchable):
                    has_control = True
                    break
            if not has_control:
                declaration = re.search(r"(?is)data-action\s*=\s*(['\"])[^'\"]*(?:筛选|过滤|filter)[^'\"]*\1", source.text)
                factory.add(
                    "SEM-FILTER-CONTROL-MISSING",
                    category="logic",
                    severity="P1",
                    file=source.path,
                    line=_line_for(source.text, declaration.start() if declaration else 0),
                    summary="页面显式声明筛选操作，但未找到可识别的筛选、搜索或查询控件。",
                    impact="已声明的核心业务操作可能无法由用户触达。",
                    recommendation="补充带稳定语义名称的筛选控件，或移除不准确的操作声明。",
                    reason_code="DECLARED_FILTER_WITHOUT_CONTROL",
                )

        state_hits: dict[str, int] = {}
        for element in re.finditer(
            r"(?is)<(?P<tag>[a-z][\w:-]*)\b(?P<attrs>[^>]*(?:data-state|aria-live|role\s*=)[^>]*)>(?P<body>.*?)</(?P=tag)\s*>",
            source.text,
        ):
            attrs = _html_attrs(element.group("attrs"))
            if (
                re.search(r"(?i)(?:^|\s)hidden(?:\s|=|$)", element.group("attrs")) is not None
                or attrs.get("aria-hidden", "").casefold() == "true"
                or re.search(r"(?i)(?:display\s*:\s*none|visibility\s*:\s*hidden)", attrs.get("style", ""))
            ):
                continue
            evidence = " ".join((attrs.get("data-state", ""), attrs.get("class", ""), attrs.get("id", ""), re.sub(r"<[^>]+>", " ", element.group("body"))))
            for name, pattern in STATE_GROUPS.items():
                if name not in state_hits and pattern.search(evidence):
                    state_hits[name] = element.start()
        if set(state_hits) == set(STATE_GROUPS):
            factory.add(
                "SEM-MUTUALLY-EXCLUSIVE-STATES",
                category="logic",
                severity="P1",
                file=source.path,
                line=_line_for(source.text, min(state_hits.values())),
                summary="加载、空、失败和成功四类互斥状态占位同时存在于静态展示中。",
                impact="用户可能同时看到冲突的页面状态，无法判断真实结果。",
                recommendation="默认只展示当前状态，其余状态通过确定的状态切换逻辑隐藏。",
                reason_code="SIMULTANEOUS_EXCLUSIVE_STATE_PLACEHOLDERS",
            )


class FindingFactory:
    def __init__(self, instruction_source: str) -> None:
        self.instruction_source = instruction_source
        self.counts: Counter[str] = Counter()
        self.items: list[dict[str, Any]] = []

    def add(
        self,
        code: str,
        *,
        category: str,
        severity: str,
        file: str,
        line: int,
        summary: str,
        impact: str,
        recommendation: str,
        redaction_applied: bool = False,
        reason_code: str | None = None,
        selector: str | None = None,
    ) -> None:
        self.counts[code] += 1
        suffix = "" if self.counts[code] == 1 else f"-{self.counts[code]}"
        safe_summary, changed = redact_text(summary)
        finding: dict[str, Any] = {
            "id": f"{code}{suffix}",
            "category": category,
            "severity": severity,
            "method": ["S"],
            "applicability": "applicable",
            "requiredForCurrentGate": True,
            "location": {
                "route": None,
                "viewport": None,
                "selector": selector,
                "file": file,
                "line": line,
            },
            "instructionSource": self.instruction_source,
            "evidenceSource": "static_source",
            "trustLevel": "untrusted_evidence",
            "evidenceSummary": safe_summary,
            "impact": impact,
            "recommendation": recommendation,
            "state": "verified",
            "redactionApplied": redaction_applied or changed,
            "acceptedDifference": False,
        }
        if reason_code:
            finding["reasonCode"] = reason_code
        validate_finding(finding)
        self.items.append(finding)


def _html_like_text(source: SourceFile) -> str | None:
    suffix = Path(source.path).suffix.casefold()
    if suffix in {".html", ".htm"}:
        return source.text
    if suffix == ".vue":
        match = re.search(r"(?is)<template\b[^>]*>(.*?)</template\s*>", source.text)
        return match.group(1) if match else None
    if suffix == ".svelte":
        return re.sub(r"(?is)<(?:script|style)\b[^>]*>.*?</(?:script|style)\s*>", "", source.text)
    return None


def _parse_html(source: SourceFile) -> HtmlFacts:
    parser = EvidenceHtmlParser()
    parser.feed(_html_like_text(source) or "")
    parser.close()
    return parser.facts


def _css_has_focus_replacement(text: str) -> bool:
    for block in re.finditer(r"(?is)([^{}]+)\{([^{}]*)\}", text):
        selector, body = block.group(1), block.group(2)
        if ":focus" not in selector.casefold():
            continue
        if re.search(r"(?i)(?:outline\s*:\s*(?!none|0)[^;]+|box-shadow\s*:\s*(?!none)[^;]+|border(?:-color)?\s*:\s*[^;]+)", body):
            return True
    return False


def _visible_code_for_placeholder(source: SourceFile) -> str:
    html_like = _html_like_text(source)
    if html_like is None:
        return source.text
    without_tags = re.sub(r"(?is)<[^>]+>", " ", html_like)
    comments = " ".join(re.findall(r"(?is)<!--(.*?)-->", html_like))
    return without_tags + " " + comments


def _jsx_pointer_only_interactions(source: SourceFile) -> Iterable[tuple[str, int]]:
    """Yield non-native JSX elements with a pointer handler but no keyboard contract.

    This is deliberately a narrow heuristic.  It does not attempt to infer whether
    every click handler is a user-facing action, and it leaves elements that already
    declare a role, tabIndex, or keyboard handler for a deeper/browser check.
    """
    for match in JSX_POINTER_ONLY_TAG_RE.finditer(source.text):
        attrs = match.group("attrs")
        if not JSX_POINTER_HANDLER_RE.search(attrs):
            continue
        if JSX_KEYBOARD_HANDLER_RE.search(attrs) or JSX_ROLE_RE.search(attrs) or JSX_TAB_INDEX_RE.search(attrs):
            continue
        yield match.group("tag").casefold(), _line_for(source.text, match.start())


def _nested_keyboard_traversal_guards(source: SourceFile) -> Iterable[int]:
    """Yield a narrow nested-menu focus guard that can fall back to root items.

    This is a candidate diagnostic derived from PrimeNG #15110.  It intentionally
    requires the visible-items getter, the exact parent-key guard, a root-list
    fallback, and an ArrowDown traversal method in the same source file.  It is
    not a generic proof that every key comparison is defective.
    """
    if "onArrowDownKey" not in source.text:
        return
    for match in NESTED_KEYBOARD_VISIBLE_ITEMS_RE.finditer(source.text):
        body = match.group("body")
        guard = NESTED_KEYBOARD_PARENT_GUARD_RE.search(body)
        if guard is None or re.search(r"\bthis\.processedItems\b", body) is None:
            continue
        yield _line_for(source.text, match.start("body") + guard.start())


def _collect_findings(
    sources: list[SourceFile],
    html: dict[str, HtmlFacts],
    instruction_source: str,
    *,
    skipped_sources: Sequence[Mapping[str, Any]] = (),
    include_security: bool = False,
) -> list[dict[str, Any]]:
    factory = FindingFactory(instruction_source)
    _semantic_findings(sources, html, factory)
    for skipped in skipped_sources:
        factory.add(
            "COVERAGE-SOURCE-SKIPPED",
            category="coverage",
            severity="P2",
            file=str(skipped.get("path", "unknown")),
            line=1,
            summary="受支持的 Web 源文件超过单文件审查上限，已明确标记为未覆盖。",
            impact="该文件中的安全、可访问性或产品问题可能未进入当前结论。",
            recommendation="将文件拆分、提供构建后可审查片段，或在受控环境中提高显式读取上限后重新审查。",
            reason_code=str(skipped.get("reason", "SOURCE_SKIPPED")),
        )
    for source in sources:
        for match in (SECRET_ASSIGN_RE.finditer(source.text) if include_security else ()):
            factory.add(
                "SEC-PLAINTEXT-CREDENTIAL",
                category="security",
                severity="P0",
                file=source.path,
                line=_line_for(source.text, match.start()),
                summary="疑似前端明文凭据赋值；原始值已脱敏。",
                impact="客户端源码可能向未授权人员暴露可复用凭据。",
                recommendation="移除客户端凭据，改用受控服务端配置，并轮换任何真实暴露值。",
                redaction_applied=True,
                reason_code="CLIENT_CREDENTIAL_ASSIGNMENT",
            )
        for match in (PROMPT_INJECTION_RE.finditer(source.text) if include_security else ()):
            factory.add(
                "SEC-PROMPT-INJECTION",
                category="security",
                severity="P1",
                file=source.path,
                line=_line_for(source.text, match.start()),
                summary="检测到试图改变 Agent 权限或指令边界的项目内容；诱导文本未执行且未复述。",
                impact="若把不可信项目内容当成授权，可能导致越权读取、写入或外部操作。",
                recommendation="仅记录来源、位置、类别和影响，继续按平台与用户授权边界执行。",
                redaction_applied=True,
                reason_code="UNTRUSTED_INSTRUCTION_ATTEMPT",
            )
        visible_placeholder_text = _visible_code_for_placeholder(source)
        for match in PLACEHOLDER_RE.finditer(visible_placeholder_text):
            factory.add(
                "CONTENT-PLACEHOLDER",
                category="content",
                severity="P3",
                file=source.path,
                line=1,
                summary="页面可见文本或注释仍包含占位或待办内容。",
                impact="用户可能看到未完成内容，降低产品可信度。",
                recommendation="用正式业务内容替换，并检查同一页面的演示数据。",
            )
        for pattern, reason_code in (DANGEROUS_DOM_PATTERNS if include_security else ()):
            for match in pattern.finditer(source.text):
                factory.add(
                    "SEC-DANGEROUS-DOM-WRITE",
                    category="security",
                    severity="P1",
                    file=source.path,
                    line=_line_for(source.text, match.start()),
                    summary="检测到直接 HTML 注入或动态 DOM 写入路径。",
                    impact="不可信输入进入该路径时可能造成 DOM 注入。",
                    recommendation="使用文本节点、框架安全绑定或经过验证的清洗器，并追踪输入来源。",
                    reason_code=reason_code,
                )
        if source.path.casefold().endswith(".css"):
            if OUTLINE_NONE_RE.search(source.text) and not _css_has_focus_replacement(source.text):
                match = OUTLINE_NONE_RE.search(source.text)
                assert match is not None
                factory.add(
                    "A11Y-FOCUS-OUTLINE-REMOVED",
                    category="accessibility",
                    severity="P1",
                    file=source.path,
                    line=_line_for(source.text, match.start()),
                    summary="CSS 移除了默认焦点轮廓，且未检测到等价的可见焦点样式。",
                    impact="键盘用户可能无法定位当前焦点。",
                    recommendation="提供始终可见且对比充分的 :focus-visible 样式。",
                )

        suffix = Path(source.path).suffix.casefold()
        if suffix in {".jsx", ".tsx", ".js", ".ts"}:
            for tag, line in _jsx_pointer_only_interactions(source):
                factory.add(
                    "A11Y-POINTER-ONLY-INTERACTION",
                    category="accessibility",
                    severity="P2",
                    file=source.path,
                    line=line,
                    selector=f"{tag}[onClick]",
                    summary="非原生 JSX 元素绑定点击事件，但未检测到键盘、角色或焦点语义。",
                    impact="键盘用户可能无法到达或触发与鼠标相同的操作。",
                    recommendation="优先改用原生 button/a；若必须自定义，补齐 role、tabIndex、键盘处理和可见焦点，并在 Browser 中复验。",
                    reason_code="NON_NATIVE_CLICK_WITHOUT_KEYBOARD_SEMANTICS",
                )
            for line in _nested_keyboard_traversal_guards(source):
                factory.add(
                    "A11Y-NESTED-KEYBOARD-TRAVERSAL-GUARD",
                    category="accessibility",
                    severity="P2",
                    file=source.path,
                    line=line,
                    selector="visibleItems",
                    summary="嵌套菜单可见项遍历把活动项 key 与当前焦点 parentKey 绑定，并回退到根级列表。",
                    impact="当焦点已进入子菜单但活动项上下文尚未同步时，ArrowDown 等键盘路径可能跳回根项或无法继续遍历。",
                    recommendation="不要把活动项 parent-key 相等作为继续嵌套键盘遍历的必要条件；用 issue-specific 键盘回归覆盖根项、子项和同级/下一级移动，并在 Browser 中复验。",
                    reason_code="NESTED_MENU_PARENT_KEY_GUARD_CAN_FALL_BACK_TO_ROOT",
                )
            for match in re.finditer(r"(?is)<(?P<tag>input|select|textarea)\b(?P<attrs>[^>]*)>", source.text):
                attrs = match.group("attrs")
                if re.search(r"(?i)\b(?:aria-label|aria-labelledby|id|title)\s*=", attrs) is None:
                    factory.add(
                        "A11Y-FORM-CONTROL-NAME",
                        category="accessibility",
                        severity="P1",
                        file=source.path,
                        line=_line_for(source.text, match.start()),
                        selector=match.group("tag"),
                        summary="JSX/TSX 表单控件缺少可识别的可访问名称。",
                        impact="辅助技术用户可能无法理解输入目的。",
                        recommendation="使用可关联 label、aria-label 或 aria-labelledby。",
                    )
            for match in re.finditer(r"(?is)<button\b(?P<attrs>[^>]*)>(?P<body>.*?)</button\s*>", source.text):
                attrs = match.group("attrs")
                body = re.sub(r"(?is)<[^>]+>|\{[^{}]*\}", " ", match.group("body"))
                if not body.strip() and re.search(r"(?i)\b(?:aria-label|aria-labelledby|title)\s*=", attrs) is None:
                    factory.add(
                        "A11Y-CONTROL-NAME-MISSING",
                        category="accessibility",
                        severity="P1",
                        file=source.path,
                        line=_line_for(source.text, match.start()),
                        selector="button",
                        summary="图标或空按钮缺少可访问名称。",
                        impact="用户无法可靠理解按钮用途。",
                        recommendation="提供可见文字或准确的 aria-label/aria-labelledby。",
                    )

    for path, facts in html.items():
        id_counts = Counter(value for value, _ in facts.ids)
        for value, count in sorted(id_counts.items()):
            if count > 1:
                line = next(line for item, line in facts.ids if item == value)
                factory.add(
                    "A11Y-DUPLICATE-ID",
                    category="accessibility",
                    severity="P1",
                    file=path,
                    line=line,
                    selector=f"#{value}",
                    summary="同一文档存在重复 ID。",
                    impact="标签、ARIA 关系和脚本目标可能指向错误元素。",
                    recommendation="为每个元素分配稳定且唯一的 ID，并更新关联引用。",
                )
        for tag, attrs, line in facts.controls:
            input_type = attrs.get("type", "text").casefold()
            if tag == "input" and input_type in {"hidden", "submit", "button", "reset", "image"}:
                continue
            control_id = attrs.get("id", "")
            has_name = bool(
                attrs.get("aria-label")
                or attrs.get("aria-labelledby")
                or attrs.get("title")
                or (control_id and control_id in facts.label_for)
            )
            if not has_name:
                factory.add(
                    "A11Y-FORM-CONTROL-NAME",
                    category="accessibility",
                    severity="P1",
                    file=path,
                    line=line,
                    selector=f"#{control_id}" if control_id else tag,
                    summary="表单控件缺少可关联标签或可访问名称。",
                    impact="用户无法可靠理解核心输入字段，屏幕阅读器用户尤其受影响。",
                    recommendation="使用显式 label/for 或准确的 aria-labelledby 建立名称关系。",
                )
        for attrs, line, text in facts.buttons:
            if not text and not (attrs.get("aria-label") or attrs.get("aria-labelledby") or attrs.get("title")):
                factory.add(
                    "A11Y-CONTROL-NAME-MISSING",
                    category="accessibility",
                    severity="P1",
                    file=path,
                    line=line,
                    selector=f"#{attrs['id']}" if attrs.get("id") else "button",
                    summary="按钮缺少可见文字或可访问名称。",
                    impact="键盘和辅助技术用户无法判断操作用途。",
                    recommendation="提供可见文字，或为纯图标按钮提供准确名称。",
                )
        for attrs, line in facts.images:
            if "alt" not in attrs:
                factory.add(
                    "A11Y-IMAGE-ALT-MISSING",
                    category="accessibility",
                    severity="P2",
                    file=path,
                    line=line,
                    selector=f"#{attrs['id']}" if attrs.get("id") else "img",
                    summary="图片缺少 alt 属性。",
                    impact="辅助技术无法判断图片是信息内容还是装饰。",
                    recommendation="为信息图片提供等价文本；装饰图片使用空 alt。",
                )
        if include_security:
            for attrs, line in facts.anchors:
                rel = {part.casefold() for part in attrs.get("rel", "").split()}
                if attrs.get("target", "").casefold() == "_blank" and "noopener" not in rel:
                    factory.add(
                        "SEC-UNSAFE-BLANK-TARGET",
                        category="security",
                        severity="P2",
                        file=path,
                        line=line,
                        selector=f"#{attrs['id']}" if attrs.get("id") else "a[target=_blank]",
                        summary="新窗口链接缺少 noopener。",
                        impact="目标页面可能获得来源窗口引用。",
                        recommendation="添加 rel=\"noopener noreferrer\" 并确认外部跳转边界。",
                        reason_code="TARGET_BLANK_WITHOUT_NOOPENER",
                    )
    return factory.items


def _business_model(
    html: dict[str, HtmlFacts],
    *,
    project_constraints: Sequence[str] = (),
) -> dict[str, list[str]]:
    entities: set[str] = set()
    roles: set[str] = set()
    operations: set[str] = set()
    states: set[str] = set()
    constraints: set[str] = set(project_constraints)
    for facts in html.values():
        entities.update(facts.entities)
        roles.update(facts.roles)
        operations.update(facts.operations)
        states.update(facts.states)
        constraints.update(facts.constraints)
        text = " ".join(facts.text)
        heading_candidates = [value for tag, _, value in facts.headings if tag in {"h1", "title"}]
        if not facts.entities and heading_candidates:
            candidate = heading_candidates[0].strip()
            if 1 < len(candidate) <= 80:
                entities.add(candidate)
        if not facts.entities and not heading_candidates and (facts.tags["table"] or "记录" in text):
            entities.add("记录")
        if not facts.entities and facts.tags["form"]:
            entities.add("表单")
        role_patterns = (
            ("管理员", r"管理员|admin(?:istrator)?"),
            ("审核员", r"审核员|reviewer|moderator"),
            ("普通用户", r"普通用户|end user|customer|用户"),
        )
        for role, pattern in role_patterns:
            if re.search(pattern, text, re.I):
                roles.add(role)
        for attrs, _, button_text in facts.buttons:
            if button_text:
                operations.add(button_text[:40])
            elif attrs.get("aria-label"):
                operations.add(attrs["aria-label"][:40])
        for action in (
            "查看", "搜索", "筛选", "填写", "提交", "审核", "重试", "取消", "返回", "保存", "导入", "导出",
            "view", "search", "filter", "submit", "review", "retry", "cancel", "save", "import", "export",
        ):
            if re.search(rf"(?i)(?<![A-Za-z]){re.escape(action)}(?![A-Za-z])", text):
                operations.add(action)
        for state in (
            "加载中", "空数据", "草稿", "处理中", "已完成", "失败", "权限不足", "loading", "empty", "draft",
            "processing", "completed", "failed", "permission denied",
        ):
            if state.casefold() in text.casefold():
                states.add(state)
    if not constraints:
        constraints.update({"不改变接口、权限或字段语义", "不执行外部副作用"})
    return {
        "entities": sorted(entities),
        "roles": sorted(roles),
        "operations": sorted(operations),
        "states": sorted(states),
        "constraints": sorted(constraints),
    }


def _classify(html: dict[str, HtmlFacts], tokens: list[str]) -> tuple[str, str, list[str]]:
    modes = sorted({mode for facts in html.values() for mode in facts.work_modes})
    prototypes = sorted({item for facts in html.values() for item in facts.prototypes})
    tags = Counter()
    combined_text = ""
    metric_count = 0
    for facts in html.values():
        tags.update(facts.tags)
        combined_text += " " + " ".join(facts.text)
        metric_count += len(facts.metrics)
    if modes:
        mode = modes[0]
    elif tags["form"] and re.search(r"下一步|上一步|step|步骤", combined_text, re.I):
        mode = "流程优化"
    elif len(tokens) >= 3:
        mode = "风格统一"
    else:
        mode = "页面审查"
    dashboard_signal = bool(
        tags["canvas"]
        or re.search(r"(?i)dashboard|仪表盘|趋势|同比|环比|kpi|待处理|异常", combined_text)
        or (metric_count >= 4 and (tags["nav"] or tags["aside"]))
    )
    if prototypes:
        archetype = prototypes[0]
    elif dashboard_signal:
        archetype = "Dashboard 与应用工作台"
    elif tags["form"]:
        archetype = "创作与编辑"
    elif tags["table"] or tags["dl"]:
        archetype = "实体资料管理"
    else:
        archetype = "内容与信息流"
    page_modes: list[str] = []
    if tags["nav"] or tags["aside"]:
        page_modes.append("应用外壳")
    if dashboard_signal:
        page_modes.append("Dashboard")
    has_record_structure = bool(tags["table"] or tags["dl"] or (tags["ul"] and re.search(r"列表|list", combined_text, re.I)))
    if has_record_structure:
        page_modes.append("列表和详情")
    if tags["form"]:
        page_modes.append("表单和向导")
    if not page_modes:
        page_modes.append("页面内容")
    return mode, archetype, page_modes


def _unverified_items() -> list[dict[str, Any]]:
    return [
        {
            "item": "真实布局、遮挡与 DOM 几何",
            "applicability": "deferred",
            "requiredForCurrentGate": False,
            "state": "unverified",
            "reason": "Core Lite 未执行 Browser。",
            "currentRisk": "静态风险可能与真实渲染不同。",
            "validationMethod": "在隔离 Browser Context 中执行 V1–V2。",
            "passCriteria": "批准视口无关键溢出、遮挡或不可达控件。",
        },
        {
            "item": "真实角色权限与关键闭环",
            "applicability": "deferred",
            "requiredForCurrentGate": False,
            "state": "unverified",
            "reason": "未提供隔离角色会话且静态源码不能证明授权。",
            "currentRisk": "入口可见性不等于服务端权限正确。",
            "validationMethod": "使用批准角色和只读/可逆测试数据执行旅程。",
            "passCriteria": "每个角色只访问授权功能且关键恢复路径通过。",
        },
        {
            "item": "渲染对比度、键盘与屏幕阅读器行为",
            "applicability": "deferred",
            "requiredForCurrentGate": False,
            "state": "unverified",
            "reason": "静态源码不能证明最终颜色合成、焦点顺序或播报。",
            "currentRisk": "可能仍存在运行时无障碍缺陷。",
            "validationMethod": "Browser 键盘/缩放检查并在可用时使用屏幕阅读器。",
            "passCriteria": "适用控件可达、有可见焦点、名称与状态播报正确。",
        },
    ]


def _recommendation(
    findings: list[dict[str, Any]],
    model: dict[str, list[str]],
    mode: str,
    page_modes: Sequence[str],
) -> tuple[str, str, list[str], str]:
    ids = {finding["id"] for finding in findings}
    if any(item.startswith("SEC-PLAINTEXT-CREDENTIAL") for item in ids):
        return (
            "优先移除前端明文凭据；在保留列表—详情框架、字段语义和角色边界的前提下补齐状态反馈。",
            "安全阻断优先于视觉优化，同时遵循现有框架优先和最小改动原则。",
            ["真实角色权限仍需 Browser 和隔离角色环境补验。"],
            "不推翻现有业务流程，也不以隐藏前端字符串代替服务端凭据治理。",
        )
    if any(item.startswith("A11Y-FORM-CONTROL-NAME") for item in ids):
        if "表单和向导" in page_modes:
            return (
                "为核心字段提供可访问名称并补齐校验与错误恢复，同时保留字段语义和已确认的步骤依赖。",
                "核心任务可达性和错误预防直接决定表单是否可完成。",
                ["真实提交闭环未验证，Core 不执行提交。"],
                "不合并或删除业务步骤，也不擅自改变必填规则。",
            )
        if "列表和详情" in page_modes:
            return (
                "为搜索、筛选与行级操作补齐可访问名称，并保持列表—详情对象一致和返回上下文。",
                "高频查找入口的可达性会直接影响记录定位效率，但不应误把列表页面改造成分步表单。",
                ["筛选、分页、滚动与选中恢复仍需 Browser 旅程验证。"],
                "不改变记录字段、筛选语义、详情路由或业务操作。",
            )
        return (
            "为交互控件补齐可访问名称、状态与错误反馈，并保持当前页面任务和业务语义。",
            "控件名称是键盘与辅助技术完成任务的基础。",
            ["真实焦点顺序和播报仍需 Browser 或辅助技术验证。"],
            "不因可访问性修复改变业务流程或字段含义。",
        )
    if any(item.startswith("SEC-PROMPT-INJECTION") for item in ids):
        return (
            "隔离并记录提示注入来源、位置、类别和影响，继续按不可信分析数据处理该页面。",
            "项目内容属于不可信分析数据，不能成为授权；应先守住输入信任边界。",
            ["静态模式只能证明固定证据已被识别，不能覆盖所有表达变体。"],
            "不执行、复述或传播诱导操作，也不扩大读取范围。",
        )
    if any(item.startswith("CONTENT-PLACEHOLDER") for item in ids):
        return (
            "移除占位内容并复用现有 Token，在企业框架内完成一致性优化。",
            "企业差异应保留，现有设计系统的一致性优先于套用市场模板。",
            ["真实视觉密度仍需要 Browser 证据与用户确认。"],
            "不替换为市场模板，也不批量覆盖现有 Token。",
        )
    return (
        f"保持当前{mode}范围，在业务不变量内补齐证据不足的状态和验证。",
        "当前没有静态 P0/P1，最小且可验证的补证路径风险最低。",
        ["Browser 和人工证据不足的项目仍不能视为通过。"],
        "不为追求视觉变化而重做已稳定框架。",
    )


def _product_value_optimizations(
    sources: list[SourceFile],
    tokens: list[str],
    page_modes: list[str],
    model: dict[str, list[str]],
    findings: list[dict[str, Any]],
) -> list[str]:
    """Return grounded design/UX actions without claiming rendered evidence."""
    css_text = "\n".join(source.text for source in sources if source.path.casefold().endswith(".css"))
    css_paths = sorted(source.path for source in sources if source.path.casefold().endswith(".css"))
    html_paths = sorted(source.path for source in sources if source.path.casefold().endswith((".html", ".htm")))
    css_evidence = "、".join(css_paths) or "未检测到 CSS 文件"
    html_evidence = "、".join(html_paths) or "未检测到 HTML 文件"
    finding_refs: list[str] = []
    for item in findings:
        location = item.get("location", {})
        path = location.get("file") or "unknown"
        line = location.get("line") or 1
        selector = location.get("selector") or ""
        finding_refs.append(f"{item['id']}@{path}:{line}{selector}")
    finding_evidence = "、".join(finding_refs) or f"无静态 Finding@{html_evidence}"
    color_tokens = [
        token for token in tokens
        if any(part in token.casefold() for part in ("color", "text", "surface", "background", "border", "focus", "primary", "error", "success"))
    ]
    if color_tokens:
        color_basis = "、".join(color_tokens[:4])
        color_action = (
            f"颜色：证据：{css_evidence} 的 {color_basis}；目标：默认、焦点、错误与成功状态均有稳定语义；"
            "最小动作：优先复用这些 Token 并逐一映射状态；验证：在相同 Browser 视口读取 computed style 并核对各状态；"
            "边界：静态源码不证明实际渲染对比度，保持未验证。"
        )
    else:
        color_action = (
            f"颜色：证据：{css_evidence} 未检出颜色语义 Token；目标：文本、表面、边框、焦点、错误与成功具备明确角色；"
            "最小动作：就近映射现有颜色且不批量替换品牌色；验证：在相同 Browser 视口读取 computed style 并核对状态；"
            "边界：渲染对比度保持未验证。"
        )

    typography_missing = []
    for label, pattern in (
        ("font-family/fallback", r"(?i)\bfont-family\s*:"),
        ("字号层级", r"(?i)\bfont-size\s*:"),
        ("行高", r"(?i)\bline-height\s*:"),
    ):
        if not re.search(pattern, css_text):
            typography_missing.append(label)
    if typography_missing:
        font_action = (
            f"字体：证据：{css_evidence} 缺少" + "、".join(typography_missing)
            + "；目标：正文、标题和数据拥有明确字体契约；最小动作：只补齐缺失声明并保留现有字体栈；"
            "验证：在相同 Browser 视口检查 computed font、长内容、中英文与数字；边界：字体加载和最终计算样式保持未验证。"
        )
    else:
        font_action = (
            f"字体：证据：{css_evidence} 已声明字体、字号与行高；目标：层级和 fallback 在业务内容下稳定；"
            "最小动作：保留现有契约，只修正被实际内容击穿的层级；验证：在相同 Browser 视口检查 computed font、长内容、中英文与数字；"
            "边界：字体加载和最终计算样式保持未验证。"
        )

    responsive_evidence = bool(re.search(r"(?i)@media\b|@container\b", css_text))
    mode_basis = "、".join(page_modes)
    if responsive_evidence:
        layout_action = (
            f"布局：证据：{css_evidence} 含响应式规则，页面模式为{mode_basis}；目标：批准视口的信息层级、对齐和关键操作可达；"
            "最小动作：只调整造成溢出、遮挡或主次错位的容器规则；验证：在相同 Browser 视口核对几何、横向溢出与 200% 缩放；"
            "边界：Browser 几何在正式运行前保持未验证。"
        )
    else:
        layout_action = (
            f"布局：证据：{css_evidence} 未检出明确响应式规则，页面模式为{mode_basis}；目标：移动、中间与桌面视口均保持主任务可达；"
            "最小动作：为层级、间距、溢出和固定区域补一个最小断点；验证：在相同 Browser 视口核对几何、横向溢出与 200% 缩放；"
            "边界：Browser 几何在正式运行前保持未验证。"
        )

    must_fix = [item["id"] for item in findings if item["severity"] in {"P0", "P1"}]
    states = "、".join(model["states"]) or "加载、空、失败、成功与权限不足"
    if must_fix:
        interaction_action = (
            f"交互与恢复：证据：{finding_evidence}，HTML={html_evidence}；目标：先关闭 " + "、".join(must_fix)
            + f" 并使关键旅程覆盖 {states}；最小动作：只修复 Finding 所在控件与对应恢复状态；"
            "验证：在相同 Browser 条件下执行键盘、失败恢复、重复提交和完成状态；边界：不执行真实提交或状态写入。"
        )
    else:
        interaction_action = (
            f"交互与恢复：证据：{finding_evidence}，HTML={html_evidence}；目标：关键旅程覆盖 {states}；"
            "最小动作：只补齐缺失的状态、焦点返回和重复提交保护；验证：在相同 Browser 条件下执行键盘、失败恢复、重复提交和完成状态；"
            "边界：不执行真实提交或状态写入。"
        )
    return [color_action, font_action, layout_action, interaction_action]


REVIEW_DIMENSIONS = ("任务", "层级", "构图", "节奏", "视觉", "交互", "响应式", "项目感")


def _page_task(page_modes: Sequence[str], model: Mapping[str, list[str]]) -> tuple[str, list[str], str, str]:
    is_list_detail = "列表和详情" in page_modes
    is_form = "表单和向导" in page_modes
    operations = set(model.get("operations", []))
    states = model.get("states", [])
    if is_list_detail:
        return (
            "筛选目标记录、识别状态、查看详情并返回继续工作",
            ["进入列表", "搜索或筛选", "识别目标记录", "打开详情", "核对信息", "返回并恢复上下文"],
            "桌面列表与详情分栏；移动列表与详情视图切换",
            "列表承担查找与比较，详情承担核对与下一步。",
        )
    if is_form:
        primary = "按步骤填写" + ("、".join(model.get("entities", [])[:2]) or "表单") + "，处理校验并完成提交或失败恢复"
        journey = ["进入表单", "填写必填信息", "检查校验反馈"]
        if "下一步" in operations:
            journey.append("按步骤前进")
        if "提交" in operations:
            journey.append("提交并确认结果")
        if any(state in states for state in ("失败", "提交失败", "校验失败")):
            journey.append("保留输入并从失败恢复")
        return primary, journey, "分步表单；移动端保持当前步骤、错误和下一步可见", "表单按步骤承载填写、校验与结果反馈。"
    primary_entity = "、".join(model.get("entities", [])[:2]) or "页面内容"
    primary_operation = "、".join(model.get("operations", [])[:2]) or "阅读"
    return (
        f"围绕{primary_entity}完成{primary_operation}并确认反馈",
        ["进入页面", "定位主要信息", "执行首要操作", "确认反馈", "从错误或空状态恢复"],
        "保持当前页面模式，按首要任务重组移动与桌面信息层级",
        "首要信息靠近主操作，异常和恢复状态贴近当前任务。",
    )


def _candidate_directions(page_modes: Sequence[str], profile: PageProfile, business_context: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
    return rank_directions(page_modes, profile, business_context)


def _normalise_status(value: Any, default: str = "NOT_VERIFIED") -> str:
    value = str(value or default).upper()
    return value if value in {"PASS", "PASS_WITH_WARNINGS", "FAIL", "NOT_VERIFIED", "NOT_RUN"} else default


def _evidence_and_delivery(
    *,
    evidence: Mapping[str, Any] | None,
    trusted_browser_evidence: TrustedUIBrowserEvidence | None,
    trusted_target_context: TrustedRealTargetContext | None,
    journey: list[str],
    findings: list[dict[str, Any]],
    page_goal: str,
    recommendation: str,
    implementation_scope: list[str],
    reference_limitations: list[str],
) -> dict[str, object]:
    candidate_raw = evidence.get("browser", evidence) if isinstance(evidence, Mapping) else {}
    candidate_raw = candidate_raw if isinstance(candidate_raw, Mapping) else {}
    trusted_receipt = require_browser_evidence(trusted_browser_evidence)
    target_context = require_real_target(trusted_target_context)
    trusted_raw = browser_payload(trusted_receipt) if trusted_receipt is not None else None
    raw = trusted_raw if trusted_raw is not None else candidate_raw

    conditions = raw.get("conditions") if isinstance(raw, Mapping) else None
    if not isinstance(conditions, list) or not all(isinstance(item, str) for item in conditions):
        conditions = [
            "相同页面、角色、数据和状态",
            "相同 CSS viewport、DPR、zoom、主题、语言和字体",
            "同一隔离 Browser run 与无副作用边界",
        ]
    before = raw.get("beforeRef") or raw.get("before") or "NOT_VERIFIED"
    after = raw.get("afterRef") or raw.get("after") or "NOT_VERIFIED"
    before = str(before) if isinstance(before, str) and before.strip() else "NOT_VERIFIED"
    after = str(after) if isinstance(after, str) and after.strip() else "NOT_VERIFIED"
    candidate_browser = _normalise_status(candidate_raw.get("status"), "NOT_RUN" if not evidence else "NOT_VERIFIED")
    formal_browser_status = _normalise_status(trusted_raw.get("status"), "NOT_VERIFIED") if trusted_raw else "NOT_VERIFIED"
    has_before_after = trusted_raw is not None and before != "NOT_VERIFIED" and after != "NOT_VERIFIED" and bool(conditions)
    before_after_status = formal_browser_status if has_before_after else "NOT_VERIFIED"

    journey_source = raw.get("journey") or raw.get("criticalJourney") if isinstance(raw, Mapping) else None
    journey_results: list[dict[str, str]] = []
    if isinstance(journey_source, list):
        for index, item in enumerate(journey_source):
            if isinstance(item, Mapping):
                journey_results.append({
                    "step": str(item.get("step", journey[index] if index < len(journey) else "关键步骤")),
                    "status": _normalise_status(item.get("status"), "NOT_VERIFIED"),
                    "reason": str(item.get("reason", "未提供步骤理由。")),
                })
    if not journey_results:
        journey_results = [
            {"step": step, "status": "NOT_VERIFIED", "reason": "未提供该步骤的可信 Browser 结果。"}
            for step in journey
        ]
    if trusted_raw is None:
        journey_status = "NOT_VERIFIED"
    else:
        statuses = {item["status"] for item in journey_results}
        if "FAIL" in statuses:
            journey_status = "FAIL"
        elif statuses and statuses <= {"PASS"}:
            journey_status = "PASS"
        elif statuses and statuses <= {"PASS", "PASS_WITH_WARNINGS"}:
            journey_status = "PASS_WITH_WARNINGS"
        else:
            journey_status = "NOT_VERIFIED"

    step10_input = raw.get("step10") if isinstance(raw, Mapping) else None
    if isinstance(step10_input, list):
        step10_input = {str(item.get("dimension")): item for item in step10_input if isinstance(item, Mapping)}
    allowed_levels = {"强", "可接受", "需改进"}
    step10: dict[str, dict[str, str]] = {}
    candidate_step10: dict[str, dict[str, str]] = {}
    for dimension in REVIEW_DIMENSIONS:
        item = step10_input.get(dimension) if isinstance(step10_input, Mapping) else None
        level = str(item.get("level", "")) if isinstance(item, Mapping) else ""
        reason = str(item.get("reason", "")).strip() if isinstance(item, Mapping) else ""
        if level in allowed_levels and reason:
            candidate_step10[dimension] = {"level": level, "reason": reason}
            if trusted_raw is not None:
                step10[dimension] = {"level": level, "reason": reason}
                continue
        step10[dimension] = {"level": "未验证", "reason": "缺少可信的同条件 before/after 与人工 Step 10 理由。"}
    step10_complete = all(item["level"] in allowed_levels for item in step10.values())

    blocking = any(item.get("severity") in {"P0", "P1"} for item in findings)
    advisory = any(item.get("severity") in {"P2", "P3"} for item in findings)
    key_evidence_missing = not (
        has_before_after
        and before_after_status in {"PASS", "PASS_WITH_WARNINGS"}
        and journey_status in {"PASS", "PASS_WITH_WARNINGS"}
        and step10_complete
    )
    if blocking or formal_browser_status == "FAIL" or journey_status == "FAIL":
        delivery_result = "FAIL"
    elif key_evidence_missing:
        delivery_result = "NOT_VERIFIED"
    elif advisory or formal_browser_status == "PASS_WITH_WARNINGS" or journey_status == "PASS_WITH_WARNINGS":
        delivery_result = "PASS_WITH_WARNINGS"
    else:
        delivery_result = "PASS"

    target_matches = bool(
        trusted_receipt is not None
        and target_context is not None
        and trusted_receipt.target_url == target_context.target_url
    )
    if target_matches:
        maturity = "real_page_proven"
    elif trusted_receipt is not None:
        maturity = "browser_proven"
    elif evidence:
        maturity = "candidate_evidence_only"
    else:
        maturity = "contract_only"

    unverified_text = list(reference_limitations)
    if trusted_receipt is None:
        unverified_text.append("未提供由运行时生成的可信 Browser receipt。")
    if target_context is None:
        unverified_text.append("目标是否为经批准的真实产品页面尚未由 Host 证明。")
    if not step10_complete:
        unverified_text.append("Step 10 八维人工理由未完成可信绑定。")
    summary = [
        {"section": "页面目标与核心问题", "content": f"目标：{page_goal}；静态 Finding：{len(findings)} 项。"},
        {"section": "推荐方案", "content": recommendation},
        {"section": "实际修改", "content": "当前审查未自动写入目标项目；候选文件：" + ("、".join(implementation_scope) or "未确认") + "。"},
        {"section": "验证结果", "content": f"Browser 正式状态：{formal_browser_status}；序列化候选：{candidate_browser}；关键旅程：{journey_status}；交付结果：{delivery_result}。"},
        {"section": "未验证/遗留风险", "content": "；".join(dict.fromkeys(unverified_text)) or "无。"},
    ]
    return {
        "beforeAfterConditions": conditions,
        "beforeAfter": {
            "status": before_after_status,
            "before": before,
            "after": after,
            "pixelScale": "trusted_equal_conditions" if has_before_after else "NOT_VERIFIED",
        },
        "criticalJourney": journey,
        "criticalJourneyResult": {"status": journey_status, "steps": journey_results},
        "step10": step10,
        "candidateStep10": candidate_step10,
        "step10Conclusion": delivery_result,
        "reviewDimensions": list(REVIEW_DIMENSIONS),
        "deliveryMode": "单页优化",
        "browserStatus": formal_browser_status,
        "browserCandidateResult": candidate_browser,
        "authorityVerified": trusted_receipt is not None,
        "realTargetVerified": target_matches,
        "maturity": maturity,
        "userSummary": summary,
        "result": delivery_result,
    }


def _ui_product_capability(
    sources: list[SourceFile],
    tokens: list[str],
    page_modes: list[str],
    model: dict[str, list[str]],
    findings: list[dict[str, Any]],
    *,
    mode: str,
    archetype: str,
    profile: PageProfile,
    project_reference: Mapping[str, Any] | None = None,
    evidence: Mapping[str, Any] | None = None,
    trusted_browser_evidence: TrustedUIBrowserEvidence | None = None,
    trusted_target_context: TrustedRealTargetContext | None = None,
    business_context: Mapping[str, Any] | None = None,
) -> dict[str, object]:
    """Build the eight outputs from observed page/model/context evidence."""

    source_files = [source.path for source in sources]
    primary_users = model["roles"] or ["未从静态证据确认"]
    entities = model["entities"] or ["记录"]
    states = model["states"] or ["默认", "加载", "空数据", "失败", "成功"]
    finding_ids = [item["id"] for item in findings]
    primary_task, journey, component_mode, composition_reason = _page_task(page_modes, model)
    normalized_business_context = normalize_business_context(business_context)
    candidates = _candidate_directions(page_modes, profile, normalized_business_context)
    selected_name = candidates[0]["name"]
    token_basis = tokens[:12]
    reference_context = project_reference.get("designContext") if isinstance(project_reference, Mapping) else None
    references = build_project_reference(
        source_files=source_files,
        tokens=tokens,
        roles=model["roles"],
        entities=model["entities"],
        operations=model["operations"],
        states=model["states"],
        page_modes=page_modes,
        archetype=archetype,
        constraints=model["constraints"],
        design_context=reference_context if isinstance(reference_context, Mapping) else None,
    )
    references["priority"] = ["用户当前要求", "项目设计上下文", "当前页面与本地 Token/组件", "行业模式 fallback（仅在参照不足时说明）"]
    references["preservedLanguage"] = [archetype, *page_modes]
    evidence_delivery = _evidence_and_delivery(
        evidence=evidence,
        trusted_browser_evidence=trusted_browser_evidence,
        trusted_target_context=trusted_target_context,
        journey=journey,
        findings=findings,
        page_goal=f"帮助{'、'.join(primary_users)}清楚完成{'、'.join(entities)}相关任务。",
        recommendation=candidates[0]["reason"],
        implementation_scope=source_files,
        reference_limitations=list(references.get("limitations", [])),
    )
    if "列表和详情" in page_modes:
        skeleton = ["页面身份与任务摘要", "高频搜索与筛选", "记录列表", "对象详情", "反馈与恢复"]
        supporting = ["对象身份", "重要状态", "判断依据", "下一步"]
        empty_states = ["初始无数据", "筛选无结果", "加载失败"]
        recovery = ["清除筛选", "保留输入", "恢复滚动、选中和焦点"]
    elif "表单和向导" in page_modes:
        skeleton = ["页面身份与步骤摘要", "当前步骤字段", "校验与帮助", "步骤导航", "提交结果与恢复"]
        supporting = ["当前步骤", "字段说明", "校验反馈", "提交结果"]
        empty_states = ["初始空表单", "校验失败", "提交失败"]
        recovery = ["保留已填输入", "就地显示错误", "重试不重复提交"]
    else:
        skeleton = ["页面身份与任务摘要", "首要内容", "主操作", "状态反馈", "错误与恢复"]
        supporting = ["对象身份", "判断依据", "状态", "下一步"]
        empty_states = ["初始空内容", "加载失败", "操作失败"]
        recovery = ["保留上下文", "说明失败原因", "提供下一步"]
    return {
        "pageBrief": {
            "goal": f"帮助{'、'.join(primary_users)}清楚完成{'、'.join(entities)}相关任务。",
            "primaryUsers": primary_users,
            "usageContext": f"{mode}中的页面；由页面角色、操作和状态字段观察得出",
            "primaryTask": primary_task,
            "supportingInformation": supporting,
            "secondaryActions": sorted(set(model["operations"]) - set(primary_task.split("、"))) or ["错误恢复"],
            "majorStates": states,
            "mustPreserve": model["constraints"],
            "currentProblems": finding_ids,
            "desiredExperience": "清楚、专业、高效且可信",
        },
        "businessContext": normalized_business_context,
        "projectReferences": references,
        "informationArchitecture": {
            "contentPriority": ["首要任务", "支持判断的信息", "次要操作", "例外与恢复", "低频信息"],
            "pageSkeleton": skeleton,
            "componentMode": component_mode,
            "responsiveComposition": {
                "mobile": composition_reason + " 移动端优先保留当前任务、状态和恢复入口。",
                "intermediate": "保留主任务和状态边界，压缩非关键辅助信息。",
                "desktop": composition_reason,
            },
        },
        "selectedDirection": {
            "recommendation": selected_name,
            "reason": candidates[0]["reason"],
            "internalCandidates": candidates,
            "decisionConfidence": candidates[0].get("confidence", "low"),
            "decisionScore": candidates[0].get("score", 0),
            "observedProfile": {
                "tables": profile.tables,
                "rows": profile.rows,
                "columns": profile.columns,
                "forms": profile.forms,
                "controls": profile.controls,
                "metrics": profile.metrics,
                "operations": profile.operations,
                "states": profile.states,
            },
            "explicitNonGoals": ["不切换框架", "不改变业务语义", "不使用隐藏或裁切制造整齐"],
        },
        "visualSystem": {
            "layout": component_mode,
            "typography": "复用项目字体栈，按页面实体、状态、步骤和数据证据建立层级。",
            "color": "复用观测到的语义 Token；状态使用文字或图标与颜色共同表达。",
            "components": "优先复用项目已有组件；未检出组件目录时保持参照不足。",
            "responsive": component_mode,
            "tokenBasis": token_basis,
        },
        "interactionAndStates": {
            "primaryAction": primary_task,
            "feedback": "关键动作需说明系统已收到、结果、失败原因和下一步。",
            "states": states,
            "emptyStates": empty_states,
            "recovery": recovery,
            "navigation": ["保留当前输入", "恢复滚动", "恢复选中", "恢复焦点"],
            "keyboard": ["Tab", "Shift+Tab", "Enter", "Space", "Escape"],
            "mobile": component_mode,
        },
        "implementationScope": {
            "ownerLevel": "页面构图、局部状态与响应式",
            "riskLevel": "R0",
            "candidateFiles": source_files,
            "protectedInvariants": model["constraints"],
            "writes": [],
        },
        "evidenceAndDelivery": evidence_delivery,
    }


def _audit_sources(
    sources: list[SourceFile],
    rules: list[str],
    manifest: dict[str, Any],
    *,
    instruction_source: str,
    scope_metadata: dict[str, str] | None = None,
    role: str | None = None,
    state: str | Sequence[str] | None = None,
    project_reference: Mapping[str, Any] | None = None,
    evidence: Mapping[str, Any] | None = None,
    trusted_browser_evidence: TrustedUIBrowserEvidence | None = None,
    trusted_target_context: TrustedRealTargetContext | None = None,
    project_constraints: Sequence[str] = (),
    skipped_sources: Sequence[Mapping[str, Any]] = (),
    scope_hygiene: Mapping[str, Any] | None = None,
    business_context: Mapping[str, Any] | None = None,
    include_security: bool = False,
) -> dict[str, Any]:
    html = {
        source.path: _parse_html(source)
        for source in sources
        if _html_like_text(source) is not None
    }
    tokens = sorted(
        {match.group(1) for source in sources if source.path.endswith(".css") for match in TOKEN_RE.finditer(source.text)}
    )
    findings = _collect_findings(
        sources, html, instruction_source,
        skipped_sources=skipped_sources,
        include_security=include_security,
    )
    model = _business_model(html, project_constraints=project_constraints)
    if role is not None and str(role).strip():
        model["roles"] = [str(role).strip()]
    if state is not None:
        values = [state] if isinstance(state, str) else list(state)
        normalized_states = sorted({str(item).strip() for item in values if str(item).strip()})
        if normalized_states:
            model["states"] = normalized_states
    mode, archetype, page_modes = _classify(html, tokens)
    css_text = "\n".join(source.text for source in sources if source.path.casefold().endswith(".css"))
    profile = profile_from_facts(list(html.values()), model, css_text)
    unverified = _unverified_items()
    recommendation, reason, tradeoffs, rejected = _recommendation(findings, model, mode, page_modes)
    must_fix = [item["id"] for item in findings if item["severity"] in {"P0", "P1"}]
    advisory_findings = [item["id"] for item in findings if item["severity"] in {"P2", "P3"}]
    optimizations = _product_value_optimizations(sources, tokens, page_modes, model, findings)
    ui_product_capability = _ui_product_capability(
        sources,
        tokens,
        page_modes,
        model,
        findings,
        mode=mode,
        archetype=archetype,
        profile=profile,
        project_reference=project_reference,
        evidence=evidence,
        trusted_browser_evidence=trusted_browser_evidence,
        trusted_target_context=trusted_target_context,
        business_context=business_context,
    )
    observed_profile = {
        "tables": profile.tables, "rows": profile.rows, "columns": profile.columns,
        "forms": profile.forms, "controls": profile.controls, "metrics": profile.metrics,
        "operations": profile.operations, "states": profile.states,
        "mobileEvidence": profile.mobile_evidence, "hasSearch": profile.has_search,
        "hasFilter": profile.has_filter, "hasPagination": profile.has_pagination,
        "hasSteps": profile.has_steps, "hasDestructiveAction": profile.has_destructive_action,
    }
    experience_core = build_experience_core(
        business_context, model, page_modes, observed_profile,
        style_override=str((business_context or {}).get("visualDirection") or "").strip() or None,
        pattern_override=str((business_context or {}).get("patternOverride") or "").strip() or None,
        skeleton_override=str((business_context or {}).get("skeletonOverride") or "").strip() or None,
        sources=[{"path": source.path, "text": source.text} for source in sources],
    )
    invariants = sorted(
        set(model["constraints"])
        | {"不改变路由、接口、字段语义、权限、状态机或数据持久化", "不执行支付、发布、删除、提交、上传或状态写入"}
    )
    intervention_level = 2 if any(item in page_modes for item in ("列表和详情", "表单和向导", "Dashboard")) else 1
    plan = {
        "schemaVersion": "1",
        "businessUnderstanding": (
            "实体：" + ("、".join(model["entities"]) or "未从静态证据确认")
            + "；角色：" + ("、".join(model["roles"]) or str((business_context or {}).get("primaryRole") or "未从静态证据确认"))
            + "；操作：" + ("、".join(model["operations"]) or "未从静态证据确认")
            + "；首要任务：" + str((business_context or {}).get("primaryTask") or "未提供")
            + "；成功指标：" + str((business_context or {}).get("successMetric") or "未提供")
        ),
        "currentFramework": f"检测到 {len(sources)} 个 Web 源文件、{len(tokens)} 个 CSS 自定义属性和 {len(rules)} 份项目规则。",
        "productArchetype": archetype,
        "pageModes": page_modes,
        "mainProblems": [item["id"] for item in findings],
        "mustFix": must_fix,
        "recommendedOptimizations": optimizations,
        "enterpriseDifferences": [],
        "unverifiedItems": [item["item"] for item in unverified],
        "recommendation": experience_core["selectedPattern"]["name"],
        "selectionReason": "；".join(experience_core["selectedPattern"].get("reasons", [])) or reason,
        "keyTradeoffs": list(experience_core["selectedPattern"].get("risks", [])) + tradeoffs[:2],
        "rejectedAlternative": "；".join(item["name"] for item in experience_core.get("patternAlternatives", [])[:2]) or rejected,
        "designInterventionLevel": intervention_level,
        "riskLevel": "R0",
        "approvedScope": [],
        "businessInvariants": invariants,
        "exclusions": ["目标项目写入", "依赖变更", "Browser 副作用", "业务不变量变更"],
        "verificationPlan": ["结构化 Finding 与失败路径校验", "R0 前后源码范围指纹一致", "后续阶段补齐 Browser 与真实角色证据"],
        "rollbackPlan": "R0 未写入目标项目，无需回退。",
    }
    validate_productization_plan(plan)
    delivery_result = ui_product_capability["evidenceAndDelivery"]["result"]
    if must_fix or delivery_result == "FAIL":
        result = "FAIL"
    elif delivery_result == "NOT_VERIFIED":
        result = "NOT_VERIFIED"
    elif advisory_findings or delivery_result == "PASS_WITH_WARNINGS":
        result = "PASS_WITH_WARNINGS"
    else:
        result = "PASS"
    execution = {
        "plane": "runtime",
        "executionLayer": "Lite",
        "riskLevel": "R0",
        "workMode": mode,
        "designInterventionLevel": intervention_level,
        "writes": [],
        "securityAudit": "RUN" if include_security else "OPT_IN_ONLY",
    }
    execution_status = "PASS"
    schema_status = "PASS"
    quality_status = result
    overall_status = "PASS" if quality_status == "PASS" else "PARTIAL"
    verification = {
        "schemaVersion": "1",
        "result": quality_status,
        "execution": execution,
        "verifiedItems": ["显式源码范围", "静态五维核心子集", "Finding 结构", "敏感摘要脱敏", "确定性摘要"],
        "unverifiedItems": unverified,
        "hardMetrics": {
            "unauthorizedWrites": 0,
            "scopeEscapes": 0,
            "userChangesOverwritten": 0,
            "sensitiveInformationLeaks": 0,
        },
        "redactionStatus": "PASS",
    }
    finding_files: dict[str, dict[str, Any]] = {}
    for finding in findings:
        file_name = str(finding.get("file") or "unknown")
        entry = finding_files.setdefault(file_name, {"count": 0, "severities": Counter(), "categories": Counter()})
        entry["count"] += 1
        entry["severities"][str(finding.get("severity") or "unknown")] += 1
        entry["categories"][str(finding.get("category") or "unknown")] += 1
    finding_source_summary = {
        "totalFindings": len(findings),
        "sourceFilesWithFindings": len(finding_files),
        "bySeverity": dict(sorted(Counter(str(item.get("severity") or "unknown") for item in findings).items())),
        "byCategory": dict(sorted(Counter(str(item.get("category") or "unknown") for item in findings).items())),
        "byFile": [
            {
                "file": name,
                "count": data["count"],
                "severities": dict(sorted(data["severities"].items())),
                "categories": dict(sorted(data["categories"].items())),
            }
            for name, data in sorted(finding_files.items(), key=lambda item: (-item[1]["count"], item[0]))[:100]
        ],
    }
    scope: dict[str, Any] = {
        "projectRoot": ".",
        "files": [source.path for source in sources],
        "projectRules": rules,
        "projectRuleConstraints": list(project_constraints),
        "skippedSources": [dict(item) for item in skipped_sources],
        "hygiene": dict(scope_hygiene or {}),
        "components": sorted(
            {
                part
                for source in sources
                for part in Path(source.path).parts
                if part.casefold() in {"component", "components"}
            }
        ),
        "tokens": tokens,
    }
    if scope_metadata:
        scope["source"] = dict(scope_metadata)
    provider_routing = default_provider_registry().route(
        ("static-audit", "rule-coverage", "evidence-normalization"),
        available={"builtin-lite": True},
    )
    return {
        "schemaVersion": "1",
        "schemaId": "audit-result",
        "status": overall_status,
        "executionStatus": execution_status,
        "schemaStatus": schema_status,
        "qualityStatus": quality_status,
        "overallStatus": overall_status,
        "execution": execution,
        "scope": scope,
        "businessModel": model,
        "businessContext": normalize_business_context(business_context),
        "findings": findings,
        "findingSourceSummary": finding_source_summary,
        "productizationPlan": plan,
        "uiProductCapability": ui_product_capability,
        "experienceCore": experience_core,
        "verificationReport": verification,
        "sourceScopeManifest": manifest,
        "sourceScopeFingerprint": source_scope_fingerprint(manifest),
        "planDigest": plan_digest(plan),
        "coverageLedger": coverage_for_findings(source_scope_fingerprint(manifest), findings),
        "providerRouting": provider_routing,
        "securityAudit": "RUN" if include_security else "OPT_IN_ONLY",
        "securityFindingsIncluded": include_security,
    }


def _empty_scope_audit_result(
    root: Path,
    *,
    skipped_sources: Sequence[Mapping[str, Any]] = (),
    business_context: Mapping[str, Any] | None = None,
    include_security: bool = False,
) -> dict[str, Any]:
    """Return a schema-valid, non-misleading result for a non-Web project."""
    manifest = {"schemaVersion": "1", "projectRoot": ".", "entries": []}
    empty_plan = {"schemaVersion": "1", "status": "NOT_APPLICABLE", "reason": "AUDIT_SCOPE_EMPTY"}
    error = {"code": "AUDIT_SCOPE_EMPTY", "errors": ["$: no supported Web source files found"]}
    return {
        "schemaVersion": "1",
        "schemaId": "audit-result",
        "status": "NOT_APPLICABLE",
        "executionStatus": "PASS",
        "schemaStatus": "PASS",
        "qualityStatus": "NOT_APPLICABLE",
        "overallStatus": "NOT_APPLICABLE",
        "execution": {
            "result": "NOT_APPLICABLE",
            "readOnly": True,
            "errorCode": "AUDIT_SCOPE_EMPTY",
        },
        "scope": {
            "projectRoot": ".",
            "files": [],
            "projectRules": [],
            "projectRuleConstraints": [],
            "skippedSources": [dict(item) for item in skipped_sources],
            "components": [],
            "tokens": [],
        },
        "businessModel": {"entities": [], "roles": [], "operations": [], "states": [], "constraints": []},
        "businessContext": normalize_business_context(business_context),
        "findings": [],
        "findingSourceSummary": {"totalFindings": 0, "sourceFilesWithFindings": 0, "bySeverity": {}, "byCategory": {}, "byFile": []},
        "productizationPlan": empty_plan,
        "uiProductCapability": {
            "status": "NOT_APPLICABLE",
            "evidenceAndDelivery": {
                "userSummary": {
                    "status": "NOT_APPLICABLE",
                    "reason": "AUDIT_SCOPE_EMPTY",
                    "message": "当前目录未发现受支持的 Web UI 源文件；未生成设计候选或生产映射。",
                }
            },
        },
        "experienceCore": {"schemaVersion": "2.1", "status": "NOT_APPLICABLE", "reason": "AUDIT_SCOPE_EMPTY"},
        "verificationReport": {"result": "NOT_VERIFIED", "reason": "AUDIT_SCOPE_EMPTY"},
        "sourceScopeManifest": manifest,
        "sourceScopeFingerprint": source_scope_fingerprint(manifest),
        "planDigest": sha256_hex(b"AUDIT_SCOPE_EMPTY"),
        "coverageLedger": {},
        "providerRouting": {},
        "securityAudit": "RUN" if include_security else "OPT_IN_ONLY",
        "securityFindingsIncluded": include_security,
        "error": error,
    }


def audit_project(
    project_root: str | Path,
    *,
    instruction_source: str = "user_current_conversation",
    role: str | None = None,
    state: str | Sequence[str] | None = None,
    project_reference: Mapping[str, Any] | None = None,
    evidence: Mapping[str, Any] | None = None,
    trusted_browser_evidence: TrustedUIBrowserEvidence | None = None,
    trusted_target_context: TrustedRealTargetContext | None = None,
    business_context: Mapping[str, Any] | None = None,
    include_security: bool = False,
) -> dict[str, Any]:
    """Audit a Web source tree without writing to it or following out-of-root links."""

    started = perf_counter()
    try:
        root = Path(project_root).expanduser().resolve(strict=True)
    except FileNotFoundError as error:
        raise ContractViolation("PROJECT_ROOT_INVALID", ["$: project root not found"]) from error
    if not root.is_dir():
        raise ContractViolation("PROJECT_ROOT_INVALID", ["$: project root must be a directory"])
    sources, skipped_sources, scope_hygiene = _read_sources(root)
    if not sources:
        result = _empty_scope_audit_result(
            root,
            skipped_sources=skipped_sources,
            business_context=business_context,
            include_security=include_security,
        )
        result["scope"]["hygiene"] = dict(scope_hygiene)
        elapsed = round(perf_counter() - started, 4)
        result["timing"] = {"totalSeconds": elapsed, "sourceFiles": 0}
        result["runtimeBudget"] = {"targetSeconds": 120, "status": "PASS" if elapsed <= 120 else "EXCEEDED", "boundedSourceScanning": True}
        return result
    rules, project_constraints = _project_rules(root)
    manifest_paths = sorted({source.path for source in sources} | set(rules))
    manifest = build_source_scope_manifest(root, manifest_paths)
    result = _audit_sources(
        sources,
        rules,
        manifest,
        instruction_source=instruction_source,
        scope_metadata={"type": "project-directory"},
        role=role,
        state=state,
        project_reference=project_reference,
        evidence=evidence,
        trusted_browser_evidence=trusted_browser_evidence,
        trusted_target_context=trusted_target_context,
        project_constraints=project_constraints,
        skipped_sources=skipped_sources,
        scope_hygiene=scope_hygiene,
        business_context=business_context,
        include_security=include_security,
    )
    elapsed = round(perf_counter() - started, 4)
    result["timing"] = {"totalSeconds": elapsed, "sourceFiles": len(sources)}
    result["runtimeBudget"] = {"targetSeconds": 120, "status": "PASS" if elapsed <= 120 else "EXCEEDED", "boundedSourceScanning": True}
    return result


def _safe_source_url(value: str | None) -> str | None:
    if value is None:
        return None
    parts = urlsplit(value)
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        raise ContractViolation("SOURCE_URL_INVALID", ["$: expected http(s) source URL"])
    host = parts.hostname
    if parts.port:
        host = f"{host}:{parts.port}"
    return urlunsplit((parts.scheme, host, parts.path or "/", "", ""))


def audit_html_document(
    content: str,
    *,
    source_name: str = "remote-page.html",
    source_url: str | None = None,
    instruction_source: str = "user_current_conversation",
    canonicalize_external: bool = False,
    role: str | None = None,
    state: str | Sequence[str] | None = None,
    project_reference: Mapping[str, Any] | None = None,
    evidence: Mapping[str, Any] | None = None,
    trusted_browser_evidence: TrustedUIBrowserEvidence | None = None,
    trusted_target_context: TrustedRealTargetContext | None = None,
    business_context: Mapping[str, Any] | None = None,
    include_security: bool = False,
) -> dict[str, Any]:
    """Audit one supplied real HTML document entirely in memory."""

    if not isinstance(content, str) or not content.strip():
        raise ContractViolation("HTML_INPUT_INVALID", ["$: expected non-empty HTML text"])
    if canonicalize_external:
        content = canonicalize_external_html(content)
        if not content:
            raise ContractViolation("HTML_INPUT_INVALID", ["$: canonical HTML evidence is empty"])
    normalized = source_name.replace("\\", "/")
    if (
        not normalized.endswith((".html", ".htm"))
        or normalized.startswith("/")
        or ".." in Path(normalized).parts
        or re.fullmatch(r"[A-Za-z0-9._/-]+", normalized) is None
    ):
        raise ContractViolation("HTML_INPUT_INVALID", ["$.sourceName: unsafe HTML source name"])
    raw = content.encode("utf-8")
    manifest = {
        "schemaVersion": "1",
        "projectRoot": ".",
        "entries": [
            {"path": normalized, "kind": "in-memory", "size": len(raw), "sha256": sha256_hex(raw)}
        ],
    }
    metadata = {
        "type": "in-memory-html",
        "canonicalization": "stable-semantic-v1" if canonicalize_external else "none",
    }
    safe_url = _safe_source_url(source_url)
    if safe_url:
        metadata["url"] = safe_url
    return _audit_sources(
        [SourceFile(normalized, content)],
        [],
        manifest,
        instruction_source=instruction_source,
        scope_metadata=metadata,
        role=role,
        state=state,
        project_reference=project_reference,
        evidence=evidence,
        trusted_browser_evidence=trusted_browser_evidence,
        trusted_target_context=trusted_target_context,
        business_context=business_context,
        include_security=include_security,
    )
