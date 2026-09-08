"""Shared, bounded source-scope policy for Codex Desktop Web UI analysis.

The policy prunes dependency, virtual-environment, cache, generated-output and
benchmark directories before walking their contents.  It keeps project-relative
evidence only and applies deterministic file/byte budgets to Lite/R0 analysis.
"""
from __future__ import annotations

from collections import Counter
import os
from pathlib import Path
from typing import Any, Iterable

WEB_SOURCE_SUFFIXES = frozenset({
    ".html", ".htm", ".css", ".scss", ".less", ".js", ".jsx", ".ts", ".tsx", ".vue", ".svelte"
})

EXCLUDED_DIR_NAMES = frozenset({
    ".git", ".hg", ".svn", ".idea", ".vscode",
    ".venv", "venv", "env", ".tox", ".nox",
    "node_modules", "vendor", "bower_components",
    "dist", "build", "out", "target", ".output", ".next", ".nuxt", ".svelte-kit",
    "coverage", "htmlcov", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    ".cache", ".parcel-cache", ".turbo", ".vite", ".eslintcache",
    ".npm", ".yarn", ".pnpm-store", ".gradle", ".angular", ".astro",
    "storybook-static", ".vitepress", ".docusaurus",
    "tmp", "temp", "logs", ".wuq", "wuq-output", "reference-output", "one-hour-test",
    "design-intelligence", "visual-builder", "production-scaffold", "preview", "studio",
    "benchmark-results", "benchmarks-output", "install", "runtime-venv", ".ssh",
})

EXCLUDED_FILE_NAMES = frozenset({
    ".env", ".env.local", ".env.production", ".npmrc", ".pypirc", "id_rsa", "id_ed25519",
})


def is_excluded_parts(parts: Iterable[str]) -> bool:
    return any(str(part).casefold() in EXCLUDED_DIR_NAMES for part in parts)


def exclusion_reason_for_file(path: Path) -> str | None:
    name = path.name.casefold()
    if name in EXCLUDED_FILE_NAMES:
        return "SENSITIVE_OR_CONFIG_FILE"
    if name.endswith((".min.js", ".min.css")):
        return "MINIFIED_GENERATED_ASSET"
    if name.endswith((".map", ".pyc", ".pyo")):
        return "GENERATED_ARTIFACT"
    return None


def collect_project_sources(
    root: Path,
    *,
    suffixes: Iterable[str] = WEB_SOURCE_SUFFIXES,
    max_files: int = 600,
    max_file_bytes: int = 1_048_576,
    max_total_bytes: int = 24 * 1024 * 1024,
) -> tuple[list[Path], list[dict[str, Any]], dict[str, Any]]:
    """Return deterministic source files, explicit skips and a hygiene summary.

    Excluded directories are pruned rather than recursively counted, so a large
    virtual environment cannot dominate either runtime or result size.
    """
    root = root.resolve(strict=True)
    allowed = {str(item).casefold() for item in suffixes}
    files: list[Path] = []
    skipped: list[dict[str, Any]] = []
    excluded_dirs: Counter[str] = Counter()
    excluded_files: Counter[str] = Counter()
    candidate_files = 0
    included_bytes = 0
    budget_reason: str | None = None

    for current, dirs, names in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        kept_dirs: list[str] = []
        for dirname in sorted(dirs, key=str.casefold):
            if dirname.casefold() in EXCLUDED_DIR_NAMES:
                excluded_dirs[dirname.casefold()] += 1
            else:
                kept_dirs.append(dirname)
        dirs[:] = kept_dirs

        for filename in sorted(names, key=str.casefold):
            path = current_path / filename
            relative = path.relative_to(root)
            if is_excluded_parts(relative.parts[:-1]):
                continue
            if path.suffix.casefold() not in allowed:
                continue
            candidate_files += 1
            reason = exclusion_reason_for_file(path)
            if reason:
                excluded_files[reason] += 1
                continue
            if path.is_symlink():
                excluded_files["SYMLINK_SKIPPED"] += 1
                continue
            try:
                size = path.stat().st_size
            except OSError:
                excluded_files["STAT_FAILED"] += 1
                continue
            if size > max_file_bytes:
                skipped.append({"path": relative.as_posix(), "reason": "SOURCE_TOO_LARGE", "size": size, "limit": max_file_bytes})
                continue
            if len(files) >= max_files:
                budget_reason = "SOURCE_FILE_BUDGET_EXCEEDED"
                break
            if included_bytes + size > max_total_bytes:
                budget_reason = "SOURCE_BYTE_BUDGET_EXCEEDED"
                break
            resolved = path.resolve(strict=True)
            try:
                resolved.relative_to(root)
            except ValueError:
                skipped.append({"path": relative.as_posix(), "reason": "SOURCE_SCOPE_ESCAPE", "size": size})
                continue
            files.append(path)
            included_bytes += size
        if budget_reason:
            break

    if budget_reason:
        skipped.append({
            "path": ".",
            "reason": budget_reason,
            "includedFiles": len(files),
            "includedBytes": included_bytes,
            "fileLimit": max_files,
            "byteLimit": max_total_bytes,
        })

    files.sort(key=lambda item: item.relative_to(root).as_posix())
    skipped.sort(key=lambda item: (str(item.get("path", "")), str(item.get("reason", ""))))
    summary = {
        "policyVersion": "scope-hygiene-v1",
        "candidateFiles": candidate_files,
        "includedFiles": len(files),
        "includedBytes": included_bytes,
        "excludedDirectoryRoots": sum(excluded_dirs.values()),
        "excludedDirectoriesByName": dict(sorted(excluded_dirs.items())),
        "excludedFilesByReason": dict(sorted(excluded_files.items())),
        "explicitSkippedFiles": len(skipped),
        "budgetExceeded": budget_reason is not None,
        "budgetReason": budget_reason,
        "limits": {
            "maxFiles": max_files,
            "maxFileBytes": max_file_bytes,
            "maxTotalBytes": max_total_bytes,
        },
    }
    return files, skipped, summary
