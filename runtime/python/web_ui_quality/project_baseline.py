"""Sealed project baseline with target-aware and critical-context coverage.

Large repositories may remain globally partial, but every explicit repair target
and its nearby toolchain/config context is indexed independently of the global
scan limit. This keeps legacy/monorepo repairs bounded without pretending that a
partial repository snapshot is globally complete.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from .contracts import ContractViolation, digest_json, hash_file
from .experience_run import load_experience_run, write_phase_file

_EXCLUDED = {".git", "node_modules", "dist", "build", ".next", "coverage", "__pycache__", ".venv", "venv", ".wuq"}
_GENERATED_OUTPUT_DIRS = {"dist", "build", "out", "_site", ".next"}
_CONFIG_NAMES = {
    "package.json", "package-lock.json", "pnpm-lock.yaml", "pnpm-workspace.yaml", "yarn.lock", "bun.lockb",
    "tsconfig.json", "jsconfig.json", "turbo.json", "nx.json", "workspace.json",
    "vite.config.js", "vite.config.ts", "vite.config.mjs", "vite.config.cjs",
    "next.config.js", "next.config.mjs", "next.config.ts", "next.config.cjs",
}
_CONFIG_PREFIXES = (
    "tsconfig.", "jsconfig.", "eslint.config.", "vite.config.", "vitest.config.", "jest.config.",
    "webpack.config.", "rollup.config.", "tailwind.config.", "postcss.config.", "stylelint.config.",
)
_DOT_CONFIG_PREFIXES = (".eslintrc", ".stylelintrc", ".prettierrc")
_TEXT_SUFFIXES = {".js", ".jsx", ".ts", ".tsx", ".vue", ".svelte", ".css", ".scss", ".sass", ".less", ".html", ".htm", ".py"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_critical_config(rel: Path) -> bool:
    name = rel.name.casefold()
    if name in {item.casefold() for item in _CONFIG_NAMES}:
        return True
    if any(name.startswith(prefix) for prefix in _CONFIG_PREFIXES):
        return True
    if any(name.startswith(prefix) for prefix in _DOT_CONFIG_PREFIXES):
        return True
    return False


def _quality_signals(path: Path) -> dict[str, int]:
    if path.suffix.lower() not in _TEXT_SUFFIXES:
        return {"important": 0, "inlineStyle": 0, "magicPixel": 0}
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return {"important": 0, "inlineStyle": 0, "magicPixel": 0}
    return {
        "important": len(re.findall(r"!important\b", text, flags=re.I)),
        "inlineStyle": len(re.findall(r"\bstyle\s*=\s*\{\{", text)),
        "magicPixel": len(re.findall(r"(?<![\w-])(?:-?\d{2,4})px\b", text)),
    }


def _file_row(root: Path, path: Path, *, allow_generated_output: bool = False) -> dict[str, Any] | None:
    try:
        rel = path.relative_to(root)
    except ValueError:
        return None
    generated_output = any(part in _GENERATED_OUTPUT_DIRS for part in rel.parts)
    if not path.is_file() or path.is_symlink() or (any(part in _EXCLUDED for part in rel.parts) and not (allow_generated_output and generated_output)):
        return None
    try:
        return {
            "path": rel.as_posix(),
            "sha256": hash_file(path),
            "bytes": path.stat().st_size,
            "suffix": path.suffix.lower(),
            "configOrToolchain": _is_critical_config(rel),
            "qualitySignals": _quality_signals(path),
        }
    except OSError:
        return None


def _project_metadata(root: Path) -> dict[str, Any]:
    package = root / "package.json"
    package_data: dict[str, Any] = {}
    if package.is_file():
        try:
            raw = json.loads(package.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                package_data = raw
        except (OSError, UnicodeError, json.JSONDecodeError):
            package_data = {}
    deps: dict[str, Any] = {}
    for key in ("dependencies", "devDependencies", "peerDependencies"):
        value = package_data.get(key)
        if isinstance(value, Mapping):
            deps.update(value)
    frameworks = [name for name in ("next", "react", "vue", "nuxt", "svelte", "@sveltejs/kit", "vite") if name in deps]
    package_manager = None
    for name, manager in (("pnpm-lock.yaml", "pnpm"), ("yarn.lock", "yarn"), ("bun.lockb", "bun"), ("package-lock.json", "npm")):
        if (root / name).exists():
            package_manager = manager
            break
    scripts = package_data.get("scripts") if isinstance(package_data.get("scripts"), Mapping) else {}
    local_bins = root / "node_modules" / ".bin"
    tools = []
    for name in ("tsc", "vue-tsc", "eslint", "vitest", "jest", "stylelint"):
        candidates = [local_bins / name, local_bins / f"{name}.cmd", local_bins / f"{name}.ps1"]
        if any(item.is_file() for item in candidates):
            tools.append(name)
    return {
        "frameworks": frameworks,
        "packageManager": package_manager,
        "scripts": {str(k): str(v) for k, v in scripts.items()},
        "localTools": tools,
    }


def _normalise_targets(target_files: Iterable[str]) -> set[str]:
    return {str(item).replace("\\", "/").lstrip("./") for item in target_files if str(item).strip()}


def _target_dirs(root: Path, targets: set[str]) -> set[Path]:
    dirs = {root}
    for rel_text in targets:
        path = (root / rel_text).resolve()
        try:
            path.relative_to(root)
        except ValueError:
            continue
        current = path.parent
        while True:
            dirs.add(current)
            if current == root:
                break
            parent = current.parent
            if parent == current:
                break
            current = parent
    return dirs


def _critical_context_candidates(root: Path, targets: set[str]) -> set[str]:
    """Return existing critical config files on the root/target ancestor chain.

    This deliberately does not scan arbitrary dependency trees. It captures the
    configuration layers that can change how a target is parsed/built/tested,
    while project-tool binaries are separately hash-bound by the tool plan.
    """
    result: set[str] = set()
    for directory in sorted(_target_dirs(root, targets), key=lambda item: str(item)):
        try:
            children = list(directory.iterdir())
        except OSError:
            continue
        for child in children:
            if not child.is_file() or child.is_symlink():
                continue
            try:
                rel = child.relative_to(root)
            except ValueError:
                continue
            if any(part in _EXCLUDED for part in rel.parts):
                continue
            if _is_critical_config(rel):
                result.add(rel.as_posix())
    return result


def build_project_baseline(project_root: str | Path, *, max_files: int = 5000, target_files: Iterable[str] = ()) -> dict[str, Any]:
    root = Path(project_root).expanduser().resolve()
    if not root.is_dir():
        raise ContractViolation("PROJECT_BASELINE_INVALID", ["$: project directory required"])
    if max_files < 1:
        raise ContractViolation("PROJECT_BASELINE_INVALID", ["$: max_files must be positive"])

    files: list[dict[str, Any]] = []
    indexed: set[str] = set()
    targets = _normalise_targets(target_files)
    truncated = False

    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        rel = path.relative_to(root)
        if any(part in _EXCLUDED for part in rel.parts):
            continue
        if len(files) >= max_files:
            truncated = True
            break
        row = _file_row(root, path)
        if row is None:
            continue
        files.append(row)
        indexed.add(row["path"])

    # Explicit repair targets are indexed independently of the bounded global scan.
    for rel_text in sorted(targets - indexed):
        row = _file_row(root, (root / rel_text).resolve(), allow_generated_output=True)
        if row is not None:
            files.append(row)
            indexed.add(row["path"])

    # Critical config/toolchain context on the target ancestor chain is also
    # indexed independently. This closes the "target hash matches but tsconfig
    # changed outside the global scan" gap in large repositories.
    critical_requested = _critical_context_candidates(root, targets)
    for rel_text in sorted(critical_requested - indexed):
        row = _file_row(root, (root / rel_text).resolve())
        if row is not None:
            files.append(row)
            indexed.add(row["path"])

    files.sort(key=lambda row: row["path"])
    metadata = _project_metadata(root)
    critical_indexed = critical_requested & indexed
    critical_missing = critical_requested - indexed
    body = {
        "schemaVersion": "1",
        "projectRoot": ".",
        "createdAt": _now(),
        "files": files,
        "fileCount": len(files),
        "truncated": truncated,
        "completenessStatus": "INDETERMINATE" if truncated else "COMPLETE",
        "scanLimit": max_files,
        "targetCoverage": {
            "requested": sorted(targets),
            "indexed": sorted(targets & indexed),
            "missing": sorted(targets - indexed),
            "status": "COMPLETE" if targets <= indexed else "INDETERMINATE",
        },
        "criticalContextCoverage": {
            "requested": sorted(critical_requested),
            "indexed": sorted(critical_indexed),
            "missing": sorted(critical_missing),
            "status": "COMPLETE" if not critical_missing else "INDETERMINATE",
            "claimBoundary": "Covers existing root/ancestor Web toolchain configuration for explicit repair targets; does not claim a complete dependency graph.",
        },
        "metadata": metadata,
    }
    body["baselineDigest"] = digest_json({k: v for k, v in body.items() if k not in {"createdAt", "baselineDigest"}})
    return body


def build_scope_baseline(project_root: str | Path, project_baseline: Mapping[str, Any], *, source_scope: Iterable[str]) -> dict[str, Any]:
    """Build a complete exact patch-scope + critical-context baseline."""
    root = Path(project_root).expanduser().resolve()
    scope = _normalise_targets(source_scope)
    current = build_project_baseline(root, max_files=1, target_files=scope)
    rows = {str(row.get("path")): row for row in current.get("files", []) if isinstance(row, Mapping) and row.get("path")}
    target_rows: list[dict[str, Any]] = []
    for rel in sorted(scope):
        row = rows.get(rel)
        if row is None:
            raise ContractViolation("TARGET_BASELINE_INCOMPLETE", [f"$: target file {rel!r} could not be baselined before Host write"])
        target_rows.append({
            "path": rel,
            "sha256": row.get("sha256"),
            "bytes": row.get("bytes"),
            "suffix": row.get("suffix"),
            "configOrToolchain": bool(row.get("configOrToolchain")),
            "qualitySignals": dict(row.get("qualitySignals") or {}),
        })

    coverage = dict(current.get("criticalContextCoverage") or {})
    critical_rows: list[dict[str, Any]] = []
    for rel in coverage.get("indexed", []):
        if rel in scope:
            continue
        row = rows.get(str(rel))
        if row is not None:
            critical_rows.append({"path": str(rel), "sha256": row.get("sha256"), "bytes": row.get("bytes")})
    critical_rows.sort(key=lambda row: row["path"])
    body = {
        "schemaVersion": "2",
        "sourceProjectBaselineDigest": project_baseline.get("baselineDigest"),
        "files": target_rows,
        "criticalContextFiles": critical_rows,
        "criticalContextCoverage": coverage,
    }
    body["scopeBaselineDigest"] = digest_json(body)
    return body


def attach_project_baseline(run_dir: str | Path, project_root: str | Path, *, target_files: Iterable[str] = ()) -> dict[str, Any]:
    baseline = build_project_baseline(project_root, target_files=target_files)
    write_phase_file(run_dir, "before", "project-baseline.json", json.dumps(baseline, ensure_ascii=False, indent=2, sort_keys=True))
    return baseline


def load_project_baseline(run_dir: str | Path, *, require_sealed: bool = True) -> dict[str, Any]:
    run = load_experience_run(run_dir)
    if require_sealed and run.get("phases", {}).get("before", {}).get("status") != "SEALED":
        raise ContractViolation("PROJECT_BASELINE_NOT_SEALED", ["$: Before phase must be sealed before baseline is authoritative"])
    path = Path(run["runDir"]) / "before" / "project-baseline.json"
    if not path.is_file():
        raise ContractViolation("PROJECT_BASELINE_MISSING", ["$: project-baseline.json is missing"])
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ContractViolation("PROJECT_BASELINE_INVALID", ["$: baseline is unreadable"]) from error
    expected = digest_json({k: v for k, v in value.items() if k not in {"createdAt", "baselineDigest"}})
    if value.get("baselineDigest") != expected:
        raise ContractViolation("PROJECT_BASELINE_TAMPERED", ["$: baseline digest mismatch"])
    return value


def compare_project_baseline(
    baseline: Mapping[str, Any], project_root: str | Path, *, target_files: Iterable[str] = ()
) -> dict[str, Any]:
    current = build_project_baseline(project_root, max_files=int(baseline.get("scanLimit") or 5000), target_files=target_files)
    before = {str(row["path"]): row for row in baseline.get("files", []) if isinstance(row, Mapping) and row.get("path")}
    after = {str(row["path"]): row for row in current.get("files", []) if isinstance(row, Mapping) and row.get("path")}
    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    changed = sorted(path for path in set(before) & set(after) if before[path].get("sha256") != after[path].get("sha256"))
    targets = _normalise_targets(target_files)
    target_drift = sorted(path for path in changed + removed if path in targets)

    before_critical = set((baseline.get("criticalContextCoverage") or {}).get("indexed", []))
    current_critical = set((current.get("criticalContextCoverage") or {}).get("indexed", []))
    known_critical = before_critical | current_critical | {
        path for path in set(before) | set(after) if _is_critical_config(Path(path))
    }
    critical_context_drift = sorted(path for path in set(changed + added + removed) if path in known_critical)
    toolchain_drift = list(critical_context_drift)
    unindexed_targets = sorted(path for path in targets if path not in before or path not in after)
    critical_before_status = str((baseline.get("criticalContextCoverage") or {}).get("status") or "INDETERMINATE")
    critical_after_status = str((current.get("criticalContextCoverage") or {}).get("status") or "INDETERMINATE")
    critical_context_complete = critical_before_status == "COMPLETE" and critical_after_status == "COMPLETE"
    global_partial = bool(baseline.get("truncated") or current.get("truncated"))
    target_complete = not unindexed_targets

    if not target_complete:
        status = "INDETERMINATE"
    elif target_drift:
        status = "REBASE_REQUIRED"
    elif not critical_context_complete or critical_context_drift:
        status = "REVALIDATION_REQUIRED"
    elif global_partial and targets:
        status = "TARGET_MATCH_GLOBAL_PARTIAL"
    elif global_partial:
        status = "INDETERMINATE"
    elif changed or added or removed:
        status = "DRIFT_RECORDED"
    else:
        status = "MATCH"

    patch_scope_verified = bool(
        targets and target_complete and critical_context_complete and not target_drift and not critical_context_drift
    )
    reason_code = None
    detail_code = None
    if not target_complete:
        reason_code, detail_code = "BASELINE_INCOMPLETE", "TARGET_BASELINE_INCOMPLETE"
    elif not critical_context_complete:
        reason_code, detail_code = "CRITICAL_CONTEXT_INCOMPLETE", "CRITICAL_CONTEXT_COVERAGE_INCOMPLETE"
    elif critical_context_drift:
        reason_code, detail_code = "CRITICAL_CONTEXT_DRIFT", "TOOLCHAIN_OR_CONFIG_CHANGED"
    elif global_partial:
        reason_code = "GLOBAL_BASELINE_PARTIAL"

    return {
        "schemaVersion": "1",
        "status": status,
        "baselineDigest": baseline.get("baselineDigest"),
        "currentDigest": current.get("baselineDigest"),
        "added": added,
        "removed": removed,
        "changed": changed,
        "targetFileDrift": target_drift,
        "toolchainDrift": toolchain_drift,
        "criticalContextDrift": critical_context_drift,
        "unindexedTargets": unindexed_targets,
        "baselineComplete": not global_partial,
        "targetCoverageComplete": target_complete,
        "criticalContextCoverageComplete": critical_context_complete,
        "patchScopeAssurance": "VERIFIED" if patch_scope_verified else "NOT_VERIFIED",
        "requiresRebase": bool(target_drift or not target_complete),
        "requiresRevalidation": bool(target_drift or critical_context_drift or not critical_context_complete or not target_complete),
        "reasonCode": reason_code,
        "detailCode": detail_code,
    }


def classify_post_repair_drift(
    comparison: Mapping[str, Any] | None, *, expected_write_paths: Iterable[str] = ()
) -> dict[str, Any]:
    """Classify repository drift after an authorized repair.

    The project baseline is intentionally independent from the Host write receipt:
    expected receipt paths are allowed to change, while any other observed source/
    config change is treated as an unexpected mutation.  A partial global baseline
    remains a bounded claim and is never promoted to full-repository cleanliness.
    """
    if not isinstance(comparison, Mapping):
        return {
            "schemaVersion": "1", "status": "NOT_VERIFIED", "unexpected": [], "expected": [],
            "globalCoverage": "UNKNOWN", "claimBoundary": "No project-baseline comparison was available.",
        }
    expected = _normalise_targets(expected_write_paths)
    observed = {
        str(path).replace("\\", "/")
        for key in ("changed", "added", "removed")
        for path in (comparison.get(key) or [])
        if str(path).strip()
    }
    unexpected = sorted(observed - expected)
    expected_observed = sorted(observed & expected)
    coverage_ok = bool(comparison.get("targetCoverageComplete")) and bool(comparison.get("criticalContextCoverageComplete"))
    if unexpected:
        status = "UNEXPECTED_DRIFT"
    elif not coverage_ok:
        status = "NOT_VERIFIED"
    elif expected_observed:
        status = "EXPECTED_ONLY"
    else:
        status = "CLEAN"
    return {
        "schemaVersion": "1",
        "status": status,
        "expected": expected_observed,
        "unexpected": unexpected,
        "globalCoverage": "COMPLETE" if comparison.get("baselineComplete") else "PARTIAL",
        "targetCoverageComplete": bool(comparison.get("targetCoverageComplete")),
        "criticalContextCoverageComplete": bool(comparison.get("criticalContextCoverageComplete")),
        "claimBoundary": (
            "CLEAN/EXPECTED_ONLY means no unexpected mutation was observed in the sealed/indexed baseline coverage. "
            "A PARTIAL global baseline does not prove untouched files outside indexed coverage; filesystem policy and exact Host receipts remain authoritative boundaries."
        ),
    }


__all__ = [
    "build_project_baseline", "build_scope_baseline", "attach_project_baseline", "load_project_baseline", "compare_project_baseline",
    "classify_post_repair_drift"
]
