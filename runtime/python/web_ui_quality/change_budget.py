"""Change-budget policy for preventing silent repair scope expansion."""
from __future__ import annotations

import re
from typing import Any, Iterable, Mapping

_NARROW_REQUEST = re.compile(r"(?:只|仅|最小|不要动|别动|不要改|只修|only|minimal|smallest|do not touch|don't touch)", re.I)
_DEPENDENCY_NAMES = {"package.json", "package-lock.json", "pnpm-lock.yaml", "yarn.lock", "bun.lockb"}
_CONFIG_HINTS = ("config.", "tsconfig", "eslint", "prettier", "vite.config", "next.config", "webpack.config")

_DEFAULTS = {
    "T0": {"maxFiles": 3, "maxChangedLines": 120},
    "T1": {"maxFiles": 5, "maxChangedLines": 260},
    "T2": {"maxFiles": 8, "maxChangedLines": 520},
    "T3": {"maxFiles": 12, "maxChangedLines": 900},
    "T4": {"maxFiles": 4, "maxChangedLines": 320},
}


def build_change_budget(
    request: str | None,
    *,
    risk_tier: str,
    explicit_files: Iterable[str] = (),
    systemic: bool = False,
) -> dict[str, Any]:
    tier = str(risk_tier or "T1").upper()
    base = dict(_DEFAULTS.get(tier, _DEFAULTS["T1"]))
    explicit = sorted({str(item).replace("\\", "/").lstrip("./") for item in explicit_files if str(item).strip()})
    narrow = bool(_NARROW_REQUEST.search(str(request or "")))
    if explicit:
        # Explicit source scope is a ceiling, not permission to add neighboring files.
        base["maxFiles"] = min(base["maxFiles"], len(explicit))
    elif narrow:
        base["maxFiles"] = min(base["maxFiles"], 3)
        base["maxChangedLines"] = min(base["maxChangedLines"], 180)
    if systemic:
        # A systemic diagnosis may need a wider candidate set, but still remains bounded.
        base["maxFiles"] = max(base["maxFiles"], 6)
    return {
        "schemaVersion": "1",
        "riskTier": tier,
        **base,
        "allowNewFiles": False,
        "allowDependencyChanges": False,
        "allowConfigChanges": False,
        "explicitSourceCeiling": explicit,
        "narrowRequest": narrow,
        "requiresHostReceipt": True,
        "claimBoundary": "Change budget limits scope expansion; widening it requires a new explicit Host/user decision and a new bound plan digest.",
    }


def evaluate_change_budget(
    budget: Mapping[str, Any],
    *,
    changed_files: Iterable[str],
    changed_lines: int | None = None,
    new_files: Iterable[str] = (),
) -> dict[str, Any]:
    files = sorted({str(item).replace("\\", "/").lstrip("./") for item in changed_files if str(item).strip()})
    new = sorted({str(item).replace("\\", "/").lstrip("./") for item in new_files if str(item).strip()})
    blockers: list[str] = []
    warnings: list[str] = []
    max_files = int(budget.get("maxFiles") or 0)
    max_lines = int(budget.get("maxChangedLines") or 0)
    if len(files) > max_files:
        blockers.append(f"CHANGE_BUDGET_FILES_EXCEEDED:{len(files)}>{max_files}")
    explicit = set(str(item) for item in budget.get("explicitSourceCeiling", []) if str(item))
    outside = sorted(set(files) - explicit) if explicit else []
    if outside:
        blockers.append("CHANGE_BUDGET_EXPLICIT_SCOPE_EXCEEDED:" + ",".join(outside))
    if new and not bool(budget.get("allowNewFiles")):
        blockers.append("CHANGE_BUDGET_NEW_FILES_BLOCKED:" + ",".join(new))
    dep = [path for path in files if path.rsplit("/", 1)[-1].casefold() in _DEPENDENCY_NAMES]
    if dep and not bool(budget.get("allowDependencyChanges")):
        blockers.append("CHANGE_BUDGET_DEPENDENCY_CHANGE_BLOCKED:" + ",".join(dep))
    config = [path for path in files if any(hint in path.rsplit("/", 1)[-1].casefold() for hint in _CONFIG_HINTS)]
    if config and not bool(budget.get("allowConfigChanges")):
        blockers.append("CHANGE_BUDGET_CONFIG_CHANGE_BLOCKED:" + ",".join(config))
    if changed_lines is None:
        warnings.append("CHANGED_LINES_NOT_MEASURED")
        line_status = "NOT_MEASURED"
    else:
        line_status = "PASS" if int(changed_lines) <= max_lines else "BLOCKED"
        if line_status == "BLOCKED":
            blockers.append(f"CHANGE_BUDGET_LINES_EXCEEDED:{int(changed_lines)}>{max_lines}")
    return {
        "schemaVersion": "1",
        "status": "BLOCKED" if blockers else "PASS",
        "fileStatus": "BLOCKED" if any("FILES_EXCEEDED" in item or "SCOPE_EXCEEDED" in item for item in blockers) else "PASS",
        "lineStatus": line_status,
        "changedFiles": files,
        "changedFileCount": len(files),
        "changedLines": changed_lines,
        "newFiles": new,
        "blockers": blockers,
        "warnings": warnings,
        "claimBoundary": "PASS proves only that the observed patch stayed inside the declared budget; it does not prove behavioral correctness.",
    }


__all__ = ["build_change_budget", "evaluate_change_budget"]
