"""Read-only project start planning with recursive lifecycle expansion.

All command decisions come from :mod:`command_policy`; this module never keeps a
second, weaker classifier.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .command_policy import classify_command, classify_script_tree
from .contracts import ContractViolation

_LIFECYCLE = ("dev", "start", "serve", "preview")


def expand_lifecycle_scripts(scripts: Mapping[str, Any], script_name: str) -> list[dict[str, Any]]:
    tree = classify_script_tree(scripts, str(script_name))
    return list(tree.get("lifecycle") or [])


def inspect_project_start(project_root: str | Path, *, supplied_url: str | None = None) -> dict[str, Any]:
    root = Path(project_root).expanduser().resolve()
    if not root.is_dir():
        raise ContractViolation("PROJECT_ROOT_INVALID", ["$: project root missing"])
    if supplied_url:
        return {"status": "USE_SUPPLIED_URL", "url": supplied_url, "writes": 0, "installAttempts": 0}
    index = root / "index.html"
    if index.is_file():
        return {"status": "TRUSTED_STATIC_SERVER_AVAILABLE", "entry": str(index), "writes": 0, "installAttempts": 0}
    package = root / "package.json"
    if not package.is_file():
        return {"status": "UNABLE_TO_START", "reason": "No supplied URL, static index.html, or package.json script was found.", "writes": 0, "installAttempts": 0}
    try:
        value = json.loads(package.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        return {"status": "SCRIPT_BLOCKED", "reason": f"package.json could not be trusted: {type(error).__name__}", "writes": 0, "installAttempts": 0}
    scripts = value.get("scripts") if isinstance(value, dict) else None
    if not isinstance(scripts, dict):
        return {"status": "UNABLE_TO_START", "reason": "package.json contains no scripts.", "writes": 0, "installAttempts": 0}
    node_modules = root / "node_modules"
    candidates: list[dict[str, Any]] = []
    for name in _LIFECYCLE:
        if name not in scripts:
            continue
        tree = classify_script_tree(scripts, name)
        candidates.append({
            "name": name,
            "status": tree["status"],
            "classification": tree["classification"],
            "lifecycle": tree.get("lifecycle", []),
            "reasons": tree.get("reasons", []),
            "digest": tree.get("digest"),
        })
    if any(item["status"] == "SCRIPT_BLOCKED" for item in candidates):
        return {"status": "SCRIPT_BLOCKED", "candidates": candidates, "installAttempts": 0, "writes": 0}
    if not node_modules.exists() and candidates:
        return {"status": "DEPENDENCIES_NOT_READY", "candidates": candidates, "installAttempts": 0, "writes": 0}
    if candidates:
        return {
            "status": "HOST_REVIEW_REQUIRED",
            "candidates": candidates,
            "installAttempts": 0,
            "writes": 0,
            "execution": "Host may run one recursively expanded, reviewed command tree in an isolated environment.",
        }
    return {"status": "UNABLE_TO_START", "reason": "No supported start lifecycle exists.", "installAttempts": 0, "writes": 0}


__all__ = ["classify_command", "expand_lifecycle_scripts", "inspect_project_start"]
