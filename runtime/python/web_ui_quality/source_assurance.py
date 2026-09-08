"""Local-only P0-B-S source assurance foundation.

This is intentionally read-only.  It locks an explicit change scope, detects
workspace conflicts, performs deterministic syntax checks, and produces a
command-safety plan.  It never applies a patch, installs dependencies, sends
source externally, commits, pushes, creates a PR, or runs an unapproved command.
"""
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .contracts import ContractViolation, digest_json
from .release_info import PACKAGE_VERSION
from .source_parsers import parse_source
from .command_policy import classify_script_tree

_EXCLUDED_PARTS = {".git", "node_modules", "dist", "build", ".next", "coverage", "__pycache__", ".venv", "venv"}
_BLOCKED_TOKENS = {"publish", "deploy", "release", "migrate", "migration", "seed", "prisma", "terraform", "kubectl", "docker push", "npm install", "pnpm install", "yarn install", "pip install", "--updateSnapshot", "-u"}
_BOUNDED_TOKENS = {"lint", "typecheck", "check", "test", "pytest", "unittest", "tsc", "eslint", "ruff", "mypy"}


def _git_config_args() -> list[str]:
    """Config overrides that neutralise repository-controlled program execution.

    A repository under review is untrusted input. Git otherwise honours
    ``core.fsmonitor``, ``core.hooksPath`` and ``diff.external`` from the
    inspected repository's own config, which turns inspection into execution.
    """
    return [
        "-c", "core.fsmonitor=false",
        "-c", "core.hooksPath=" + os.devnull,
        "-c", "diff.external=",
        "-c", "core.pager=cat",
        "-c", "core.askPass=",
        "-c", "credential.helper=",
        "-c", "protocol.ext.allow=never",
        "-c", "uploadpack.packObjectsHook=",
    ]


def _git_env() -> dict[str, str]:
    """Minimal environment for git that ignores system and user configuration.

    PATH is inherited because git and its helper shell must stay resolvable;
    the previous hard-coded POSIX PATH silently disabled isolation on Windows.
    """
    env = {
        "PATH": os.environ.get("PATH", ""),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_EXTERNAL_DIFF": "",
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_ALLOW_PROTOCOL": "",
        "HOME": os.devnull,
    }
    for name in ("SYSTEMROOT", "SystemRoot", "COMSPEC", "LOCALAPPDATA"):
        value = os.environ.get(name)
        if value:
            env[name] = value
    return env


def _run_git(project: Path, args: Sequence[str]) -> tuple[int, str]:
    try:
        result = subprocess.run(
            ["git", *_git_config_args(), "-C", str(project), *args],
            capture_output=True, text=True,
            timeout=10, check=False, env=_git_env(),
        )
        return result.returncode, result.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return 127, ""


def _safe_relative(project: Path, value: str | Path) -> Path:
    raw = Path(value)
    path = (project / raw).resolve() if not raw.is_absolute() else raw.resolve()
    try:
        rel = path.relative_to(project)
    except ValueError as error:
        raise ContractViolation("SOURCE_SCOPE_INVALID", [f"$: path escapes project: {value}"]) from error
    if any(part in _EXCLUDED_PARTS for part in rel.parts):
        raise ContractViolation("SOURCE_SCOPE_INVALID", [f"$: excluded path: {rel.as_posix()}"])
    if not path.is_file():
        raise ContractViolation("SOURCE_SCOPE_INVALID", [f"$: file does not exist: {rel.as_posix()}"])
    return rel


def resolve_change_scope(
    project_root: str | Path,
    *,
    files: Iterable[str | Path] = (),
    base_ref: str | None = None,
    intent: str = "review current change",
) -> dict[str, Any]:
    project = Path(project_root).expanduser().resolve()
    if not project.is_dir():
        raise ContractViolation("SOURCE_SCOPE_INVALID", ["$: project directory required"])
    explicit = list(files)
    source = "explicit"
    if explicit:
        rels = [_safe_relative(project, item) for item in explicit]
    else:
        code, output = _run_git(project, ["diff", "--name-only", "--diff-filter=ACMRTUXB", *( [base_ref] if base_ref else [] ), "--"])
        if code != 0 or not output:
            return {
                "schemaVersion": "2.3-p0bs", "scopeState": "NO_REVIEWABLE_CHANGE",
                "projectRoot": ".", "files": [], "intent": intent,
                "reason": "No explicit files and no reliable Git diff were available.",
            }
        source = "git-diff"
        rels = []
        for line in output.splitlines():
            candidate = Path(line.strip())
            if not line.strip() or any(part in _EXCLUDED_PARTS for part in candidate.parts):
                continue
            try:
                rels.append(_safe_relative(project, candidate))
            except ContractViolation:
                continue
    unique = sorted({rel.as_posix() for rel in rels})
    if not unique:
        return {
            "schemaVersion": "2.3-p0bs", "scopeState": "NO_REVIEWABLE_CHANGE",
            "projectRoot": ".", "files": [], "intent": intent,
            "reason": "The resolved change set contained no reviewable source files.",
        }
    dirty_rows: list[str] = []
    workspace_state_source = "NOT_CONSULTED"
    if source != "explicit":
        # Explicit scopes are user-selected, so git adds no authority here. Skipping
        # it keeps an untrusted repository's config off the execution path entirely.
        dirty_code, dirty = _run_git(project, ["status", "--porcelain=v1", "--untracked-files=all"])
        if dirty_code == 0 and dirty:
            dirty_rows = dirty.splitlines()
            workspace_state_source = "GIT_STATUS"
        elif dirty_code == 0:
            workspace_state_source = "GIT_STATUS"
        else:
            workspace_state_source = "GIT_UNAVAILABLE"
    dirty_files = {row[3:].strip() for row in dirty_rows if len(row) >= 4}
    explicit_set = set(unique)
    unknown_overlap: list[str] = []  # explicit files are user-selected; dirty state is disclosed, not treated as unknown overlap
    scope_payload = {
        "plane": "target_runtime", "baseRef": base_ref, "intent": intent,
        "files": unique, "source": source,
    }
    scope_hash = digest_json(scope_payload)
    return {
        "schemaVersion": "2.3-p0bs",
        "changeSetId": f"chg-{scope_hash[:16]}",
        "plane": "target_runtime",
        "baseRef": base_ref,
        "intent": intent,
        "files": unique,
        "scopeHash": scope_hash,
        "source": source,
        "excludedPaths": sorted(_EXCLUDED_PARTS),
        "dirtyWorkspace": dirty_rows,
        "workspaceStateSource": workspace_state_source,
        "scopeState": "SCOPE_CONFLICT" if unknown_overlap else "SOURCE_SCOPE_READY",
        "conflictingFiles": unknown_overlap,
        "writeAuthority": False,
    }


def _syntax_check(project: Path, rel: str) -> dict[str, Any]:
    return parse_source(project / rel, rel)


def command_safety_plan(project_root: str | Path) -> dict[str, Any]:
    project = Path(project_root).expanduser().resolve()
    rows: list[dict[str, Any]] = []
    package = project / "package.json"
    if package.is_file():
        try:
            payload = json.loads(package.read_text(encoding="utf-8"))
            scripts = payload.get("scripts") if isinstance(payload, Mapping) else {}
            if isinstance(scripts, Mapping):
                for name in sorted(scripts):
                    tree = classify_script_tree(scripts, str(name))
                    classification = tree["classification"]
                    rows.append({
                        "id": f"npm:{name}",
                        "command": ["npm", "run", str(name), "--"],
                        "source": "package.json",
                        "exactScript": str(scripts[name]),
                        "expandedScriptTree": tree,
                        "classification": classification,
                        "required": False,
                        "network": "DENY_BY_DEFAULT",
                        "timeoutSeconds": 120,
                        "allowedWritePaths": [] if classification != "SAFE_BOUNDED" else ["coverage/", ".cache/", "*.tsbuildinfo"],
                    })
        except (OSError, UnicodeError, json.JSONDecodeError):
            rows.append({"id": "package-json", "classification": "NOT_VERIFIED", "reason": "package.json could not be parsed"})
    return {
        "schemaVersion": "2.3-p0bs",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "commands": rows,
        "executionPolicy": "PLAN_ONLY_NO_COMMAND_EXECUTED",
        "classifier": "web_ui_quality.command_policy",
        "externalReviewGate": "LOCAL_ONLY",
    }

def run_source_assurance(
    project_root: str | Path,
    *,
    output_dir: str | Path,
    files: Iterable[str | Path] = (),
    base_ref: str | None = None,
    intent: str = "review current change",
) -> dict[str, Any]:
    project = Path(project_root).expanduser().resolve()
    output = Path(output_dir).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    scope = resolve_change_scope(project, files=files, base_ref=base_ref, intent=intent)
    checks = [_syntax_check(project, rel) for rel in scope.get("files", [])]
    plan = command_safety_plan(project)
    if scope.get("scopeState") == "SCOPE_CONFLICT":
        status = "BLOCKED"
    elif scope.get("scopeState") != "SOURCE_SCOPE_READY":
        status = "NOT_APPLICABLE"
    elif any(row.get("status") == "FAIL" for row in checks):
        status = "FAIL"
    elif any(row.get("status") in {"NOT_VERIFIED", "TEXT_READABLE_ONLY"} for row in checks):
        status = "NOT_VERIFIED"
    else:
        status = "VERIFIED_WITH_WARNINGS"
    report = {
        "schemaVersion": "2.3-p0bs", "producer": "web-ui-quality-source-assurance",
        "packageVersion": PACKAGE_VERSION, "generatedAt": datetime.now(timezone.utc).isoformat(),
        "status": status, "scope": scope, "deterministicChecks": checks,
        "verificationPlan": plan,
        "sourceReview": {"status": "NOT_EXECUTED", "reason": "P0-B-S foundation runs deterministic correctness only; multi-view review is P1-S."},
        "externalReview": {"status": "LOCAL_ONLY"},
        "writeActions": {"applied": False, "commit": False, "push": False, "pullRequest": False},
        "claimBoundary": "Only registered trusted parsers may produce syntax PASS. Readable but unsupported text remains NOT_VERIFIED. This receipt does not prove runtime behavior or authorize a source write.",
    }
    report["reportDigest"] = digest_json(report)
    (output / "source-assurance-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return report


__all__ = ["resolve_change_scope", "command_safety_plan", "run_source_assurance"]
