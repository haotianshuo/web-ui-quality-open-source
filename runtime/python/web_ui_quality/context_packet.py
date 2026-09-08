"""Deterministic Relevant Context Packet v1.

The packet selects references and constraints for the Host model; it is not an
LLM, does not call a remote service, and does not grant authority.  Mandatory
safety context is never removed by the source-reference budget.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable, Mapping

_TOKEN = re.compile(r"[A-Za-z0-9_.$/@-]{2,}|[\u4e00-\u9fff]{2,}")
_EXCLUDED = {".git", "node_modules", "dist", "build", ".next", "coverage", "__pycache__", ".venv", "venv", ".wuq"}

# Small deterministic bilingual/domain expansion. This is retrieval plumbing, not
# model reasoning: the map only adds common Web repair concepts so a Chinese
# request can retrieve English source names in legacy repositories.
_SEMANTIC_EXPANSIONS = {
    "订单": {"order", "orders", "checkout"}, "表格": {"table", "grid"}, "手机": {"mobile", "responsive"},
    "裁掉": {"overflow", "clip", "clipped"}, "溢出": {"overflow"}, "按钮": {"button", "cta"},
    "禁用": {"disabled", "disable"}, "加载": {"loading", "loader", "pending"}, "登录": {"login", "auth"},
    "认证": {"auth", "authentication"}, "分页": {"pagination", "page"}, "侧边栏": {"sidebar", "drawer"},
    "弹窗": {"modal", "dialog"}, "下拉": {"dropdown", "select", "menu"}, "搜索": {"search", "query"},
    "筛选": {"filter"}, "选择": {"selection", "selected"}, "主题": {"theme", "token"}, "间距": {"spacing", "gap"},
    "颜色": {"color", "token"}, "圆角": {"radius"}, "遮挡": {"overlay", "z-index", "stacking"},
    "跳转": {"redirect", "route", "navigation"}, "状态": {"state"}, "共享": {"shared", "common"},
    "多个页面": {"shared", "component", "pages"}, "支付": {"payment", "checkout"}, "错误": {"error", "failure"},
    "空状态": {"empty", "state"}, "提示": {"toast", "tooltip", "message"}, "标签": {"tab", "tabs"},
}


def _tokens(text: str) -> set[str]:
    raw = {token.casefold() for token in _TOKEN.findall(text or "") if len(token.strip()) >= 2}
    expanded = set(raw)
    # Add lexical parts so `SharedButton.tsx`, `modal.css` and route-like paths
    # can match ordinary request concepts without requiring exact punctuation.
    for token in list(raw):
        expanded.update(part for part in re.split(r"[.$/@_\-]+", token) if len(part) >= 2)
        # Conservative CamelCase splitting helps legacy component names.
        expanded.update(part.casefold() for part in re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z]|$)|\d+", token) if len(part) >= 2)
    lowered = (text or "").casefold()
    for phrase, additions in _SEMANTIC_EXPANSIONS.items():
        if phrase.casefold() in lowered:
            expanded.update(additions)
    return expanded


def _safe_rel(root: Path, value: str) -> str | None:
    text = str(value).replace("\\", "/").lstrip("./")
    path = (root / text).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        return None
    if not path.is_file() or path.is_symlink():
        return None
    rel = path.relative_to(root)
    if any(part in _EXCLUDED for part in rel.parts):
        return None
    return rel.as_posix()


def _candidate_rows(project_root: Path, baseline: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    if isinstance(baseline, Mapping):
        rows = [row for row in baseline.get("files", []) if isinstance(row, Mapping) and row.get("path")]
        if rows:
            return rows
    rows: list[dict[str, Any]] = []
    for path in sorted(project_root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        rel = path.relative_to(project_root)
        if any(part in _EXCLUDED for part in rel.parts):
            continue
        rows.append({"path": rel.as_posix(), "sha256": None})
        if len(rows) >= 5000:
            break
    return rows


def _dependency_tokens(root: Path, rel: str) -> set[str]:
    path = root / rel
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")[:65536]
    except OSError:
        return set()
    values: set[str] = set()
    for match in re.finditer(r"(?:from\s+|import\s*\(|require\s*\()?[\"']([^\"']+)[\"']", text):
        values.update(_tokens(match.group(1).replace("/", " ")))
    return values


def _score_file(root: Path, rel: str, query_tokens: set[str], explicit: set[str]) -> tuple[int, list[str]]:
    score = 1000 if rel in explicit else 0
    reasons = ["explicit-source-scope"] if rel in explicit else []
    path_tokens = _tokens(rel.replace("/", " "))
    overlap = query_tokens & path_tokens
    if overlap:
        score += 55 * len(overlap)
        reasons.append("path-token-match")
    dep_overlap = query_tokens & _dependency_tokens(root, rel)
    if dep_overlap:
        score += 20 * len(dep_overlap)
        reasons.append("dependency-token-match")
    path = root / rel
    try:
        raw = path.read_bytes()[:32768]
        text = raw.decode("utf-8", errors="ignore")
    except OSError:
        text = ""
    if text and query_tokens:
        lower = text.casefold()
        hits = sum(1 for token in query_tokens if token in lower)
        if hits:
            score += min(100, hits * 10)
            reasons.append("content-token-match")
    return score, reasons


def build_relevant_context_packet(
    project_root: str | Path,
    *,
    request: str,
    task_goal: Mapping[str, Any] | None = None,
    baseline: Mapping[str, Any] | None = None,
    evidence: Mapping[str, Any] | None = None,
    explicit_source_scope: Iterable[str] = (),
    max_source_refs: int = 12,
) -> dict[str, Any]:
    root = Path(project_root).expanduser().resolve()
    goal = dict(task_goal or {})
    protected = [str(item) for item in goal.get("nonGoals", []) if str(item).strip()]
    explicit = {rel for value in explicit_source_scope if (rel := _safe_rel(root, str(value))) is not None}

    evidence_text: list[str] = []
    if isinstance(evidence, Mapping):
        for key in ("deliveryConclusion", "status"):
            if evidence.get(key):
                evidence_text.append(str(evidence.get(key)))
        for finding in list(evidence.get("topFindings") or [])[:10]:
            if isinstance(finding, Mapping):
                evidence_text.extend(str(finding.get(key) or "") for key in ("summary", "message", "title", "ruleId", "sourcePath"))
                source_path = finding.get("sourcePath") or finding.get("path")
                if source_path:
                    rel = _safe_rel(root, str(source_path))
                    if rel:
                        explicit.add(rel)
    query_tokens = _tokens(" ".join([request, str(goal.get("goal") or ""), *protected, *evidence_text]))

    ranked: list[dict[str, Any]] = []
    for row in _candidate_rows(root, baseline):
        rel = _safe_rel(root, str(row.get("path")))
        if rel is None:
            continue
        score, reasons = _score_file(root, rel, query_tokens, explicit)
        if score <= 0 and rel not in explicit:
            continue
        ranked.append({
            "path": rel,
            "score": score,
            "reasons": reasons or ["bounded-fallback"],
            "sha256": row.get("sha256"),
        })
    ranked.sort(key=lambda row: (-int(row["score"]), row["path"]))

    # Explicit source scope is mandatory even if it exceeds the normal relevance
    # ordering; max_source_refs is therefore a soft relevance budget, not a safety
    # budget.
    selected: list[dict[str, Any]] = []
    for row in ranked:
        if row["path"] in explicit and row not in selected:
            selected.append(row)
    for row in ranked:
        if row in selected:
            continue
        if len(selected) >= max_source_refs:
            break
        selected.append(row)

    baseline_summary = {
        "baselineDigest": (baseline or {}).get("baselineDigest") if isinstance(baseline, Mapping) else None,
        "globalCoverage": "COMPLETE" if (baseline or {}).get("completenessStatus") == "COMPLETE" else "PARTIAL" if (baseline or {}).get("completenessStatus") == "INDETERMINATE" else "UNKNOWN",
        "frameworks": list(((baseline or {}).get("metadata") or {}).get("frameworks", [])) if isinstance(baseline, Mapping) else [],
        "packageManager": ((baseline or {}).get("metadata") or {}).get("packageManager") if isinstance(baseline, Mapping) else None,
    }
    selected_bytes = 0
    for row in selected:
        try:
            selected_bytes += int((root / str(row["path"])).stat().st_size)
        except OSError:
            pass
    estimated_tokens = (selected_bytes + 3) // 4
    return {
        "schemaVersion": "1",
        "task": {
            "request": request,
            "goal": str(goal.get("goal") or request),
            "protectedScope": protected,
        },
        "mandatoryContext": {
            "protectedScope": protected,
            "writeAuthority": "HOST_ONLY",
            "projectToolAuthority": "HOST_ONLY",
            "claimBoundary": "No Evidence, No PASS; Runtime cannot self-authorize writes or project-tool execution.",
        },
        "project": baseline_summary,
        "sourceRefs": selected,
        "budget": {
            "maxSourceRefs": int(max_source_refs),
            "selectedSourceRefs": len(selected),
            "candidateSourceRefs": len(ranked),
            "explicitSourceRefs": len(explicit),
            "selectedSourceBytes": selected_bytes,
            "estimatedSourceTokens": estimated_tokens,
        },
        "claimBoundary": "This packet is a deterministic relevance/context plan. It does not prove that selected sources contain the root cause and it carries no write or execution authority.",
    }


def context_recall(packet: Mapping[str, Any], expected_paths: Iterable[str], *, k: int | None = None) -> dict[str, Any]:
    expected = {str(path).replace("\\", "/").lstrip("./") for path in expected_paths}
    rows = [row for row in packet.get("sourceRefs", []) if isinstance(row, Mapping)]
    if k is not None:
        rows = rows[: max(0, int(k))]
    observed = {str(row.get("path") or "") for row in rows}
    matched = sorted(expected & observed)
    recall = 1.0 if not expected else len(matched) / len(expected)
    return {
        "expected": sorted(expected), "matched": matched, "missing": sorted(expected - observed),
        "recall": recall, "k": k, "selected": len(rows),
    }


def context_retrieval_metrics(packet: Mapping[str, Any], expected_paths: Iterable[str], *, k: int | None = None) -> dict[str, Any]:
    expected = {str(path).replace("\\", "/").lstrip("./") for path in expected_paths}
    rows = [row for row in packet.get("sourceRefs", []) if isinstance(row, Mapping)]
    if k is not None:
        rows = rows[: max(0, int(k))]
    observed = [str(row.get("path") or "") for row in rows]
    matched = expected & set(observed)
    return {
        "k": k, "expectedCount": len(expected), "selectedCount": len(observed), "matchedCount": len(matched),
        "recall": (len(matched) / len(expected)) if expected else None,
        "precision": (len(matched) / len(observed)) if observed else None,
        "selectedSourceBytes": int(dict(packet.get("budget") or {}).get("selectedSourceBytes") or 0),
        "estimatedSourceTokens": int(dict(packet.get("budget") or {}).get("estimatedSourceTokens") or 0),
    }


__all__ = ["build_relevant_context_packet", "context_recall", "context_retrieval_metrics"]
