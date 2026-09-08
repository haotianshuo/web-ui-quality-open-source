"""Single deterministic command policy used by all project-facing workflows.

The policy is intentionally conservative.  It parses shell tokens, expands package
manager script references separately, and reports the highest risk in a command
or script tree.  It never executes a command.
"""
from __future__ import annotations

import re
import shlex
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .contracts import ContractViolation, digest_json

_BLOCKED_EXECUTABLES = {
    "rm", "rmdir", "del", "erase", "format", "mkfs", "truncate", "shutdown", "reboot",
    "curl", "wget", "powershell", "pwsh", "ssh", "scp", "ftp", "nc", "netcat",
    "kubectl", "terraform", "ansible", "helm",
}
_PACKAGE_MANAGERS = {"npm", "pnpm", "yarn", "bun"}
_INSTALL_WORDS = {"install", "add", "update", "upgrade", "ci", "link", "unlink", "publish", "deploy", "release"}
_WRITE_FLAGS = {
    "--write", "--fix", "--fix-dry-run", "--updateSnapshot", "--update-snapshot", "-u",
    "--outDir", "--out-dir", "--emitDeclarationOnly", "--generateTrace", "--coverage",
}
_READ_ONLY_EXECUTABLES = {"eslint", "mypy", "pyright", "stylelint", "htmlhint", "pytest", "unittest"}
_READ_ONLY_SUBCOMMANDS = {
    ("ruff", "check"), ("tsc", "--noEmit"), ("python", "-m", "compileall"),
}
_DESTRUCTIVE = re.compile(
    r"(?ix)(?:\brm\s+-rf\b|\bdel\s+/[sq]\b|\brmdir\s+/s\b|\bmkfs\b|"
    r"\btruncate\b|\bshutdown\b|\breboot\b|\b(?:drop|truncate)\s+(?:table|database)\b)"
)
_DOWNLOAD = re.compile(r"(?ix)(?:\bcurl\b|\bwget\b|invoke-webrequest|\bdownload\b|https?://[^\s]+\.(?:sh|ps1|exe|msi))")
_NETWORK = re.compile(r"(?ix)(?:https?://|\bssh\b|\bscp\b|\bnc\b|\bnetcat\b|\bwebsocket\b)")
_WRITE_REDIRECT = re.compile(r"(?:^|[^>])>{1,2}(?:[^>]|$)")
_SHELL_OPERATOR = re.compile(r"(?:&&|\|\||(?<!\|)\|(?!\|)|;|\n)")
_SCRIPT_REF = re.compile(r"(?<![A-Za-z0-9_.-])(?:npm|pnpm|yarn|bun)(?:\s+[^;&|\n]*)?\s+(?:run|run-script)\s+([A-Za-z0-9_.:-]+)")

_RANK = {"SAFE_BOUNDED": 0, "REQUIRES_APPROVAL": 1, "BLOCKED": 2}


def _tokenize(command: str) -> list[str]:
    try:
        return shlex.split(command, posix=True)
    except ValueError as error:
        raise ContractViolation("SCRIPT_BLOCKED", [f"$: shell tokenization failed: {error}"]) from error


def _highest(statuses: Iterable[str]) -> str:
    values = list(statuses)
    return max(values, key=lambda value: _RANK.get(value, 2)) if values else "REQUIRES_APPROVAL"


def _package_operation(tokens: Sequence[str]) -> str | None:
    """Find the effective package-manager operation even when flags precede it."""
    if not tokens:
        return None
    executable = Path(tokens[0]).name.casefold()
    if executable not in _PACKAGE_MANAGERS:
        return None
    lowered = [token.casefold() for token in tokens[1:]]
    for token in lowered:
        if token in _INSTALL_WORDS or token in {"run", "run-script", "exec", "dlx"}:
            return token
    # Yarn/Bun may invoke a script directly. Treat the first non-option token as a script operation.
    for token in lowered:
        if not token.startswith("-") and token not in {"silent", "."}:
            return token
    return None


def classify_command(command: str) -> dict[str, Any]:
    """Classify one complete shell command without executing it."""
    text = str(command or "").strip()
    tokens = _tokenize(text) if text else []
    executable = Path(tokens[0]).name.casefold() if tokens else ""
    lowered = [token.casefold() for token in tokens]
    operation = _package_operation(tokens)
    reasons: list[str] = []
    write_reasons: list[str] = []
    network_reasons: list[str] = []

    if not tokens:
        reasons.append("empty command")
    if executable in _BLOCKED_EXECUTABLES or _DESTRUCTIVE.search(text):
        reasons.append("destructive or remote-capable executable")
    if executable in _PACKAGE_MANAGERS and operation in _INSTALL_WORDS:
        reasons.append(f"package-manager operation {operation!r} can change dependencies or publish")
    if executable in _PACKAGE_MANAGERS and operation in {"exec", "dlx"}:
        reasons.append("package-manager remote execution is not trusted")
    if _DOWNLOAD.search(text):
        reasons.append("download or remote script operation")
        network_reasons.append("download")
    if _WRITE_REDIRECT.search(text):
        write_reasons.append("shell write redirection")
    if any(flag in tokens for flag in _WRITE_FLAGS):
        write_reasons.append("write-producing flag")
    if executable == "ruff" and len(lowered) > 1 and lowered[1] == "format":
        write_reasons.append("ruff format rewrites source")
    if executable in {"prettier", "biome"} and any(flag in lowered for flag in {"--write", "format"}):
        write_reasons.append("formatter rewrites source")
    if executable == "tsc" and any(flag.casefold() in {"--outdir", "--emitdeclarationonly", "--generatetrace"} for flag in tokens):
        write_reasons.append("TypeScript compiler emits files")
    if executable in {"jest", "vitest"} and any(flag in tokens for flag in {"-u", "--updateSnapshot", "--update-snapshot"}):
        write_reasons.append("snapshot update writes project files")
    if _NETWORK.search(text):
        network_reasons.append("network-capable command")

    compound = bool(_SHELL_OPERATOR.search(text))
    segment_results: list[dict[str, Any]] = []
    if compound:
        # Classify every lexical segment so a later destructive command cannot hide behind a benign first command.
        for segment in [part.strip() for part in _SHELL_OPERATOR.split(text) if part.strip()]:
            if segment == text:
                continue
            segment_result = classify_command(segment)
            segment_results.append(segment_result)
            if segment_result["classification"] == "BLOCKED":
                reasons.append("compound command contains a blocked segment")
        if not reasons:
            write_reasons.append("compound shell command requires Host review")

    if reasons:
        classification = "BLOCKED"
    else:
        pair = tuple(lowered[:2])
        explicitly_read_only = executable in _READ_ONLY_EXECUTABLES or pair in _READ_ONLY_SUBCOMMANDS
        if executable == "tsc" and "--noemit" in lowered:
            explicitly_read_only = True
        if executable == "ruff" and len(lowered) > 1 and lowered[1] == "check" and "--fix" not in lowered:
            explicitly_read_only = True
        classification = "REQUIRES_APPROVAL" if write_reasons or network_reasons or compound or not explicitly_read_only else "SAFE_BOUNDED"

    return {
        "command": text,
        "tokens": tokens,
        "executable": executable,
        "operation": operation,
        "classification": classification,
        "status": "SCRIPT_BLOCKED" if classification == "BLOCKED" else classification,
        "reasons": sorted(dict.fromkeys(reasons + write_reasons + network_reasons)),
        "writeHint": bool(write_reasons),
        "networkHint": bool(network_reasons),
        "downloadHint": bool(_DOWNLOAD.search(text)),
        "compound": compound,
        "segments": segment_results,
        "sandboxRequired": True,
        "digest": digest_json({"tokens": tokens, "classification": classification, "reasons": sorted(dict.fromkeys(reasons + write_reasons + network_reasons))}),
    }


def _nested_script_names(command: str) -> list[str]:
    return list(dict.fromkeys(match.group(1) for match in _SCRIPT_REF.finditer(command)))


def classify_script_tree(
    scripts: Mapping[str, Any],
    script_name: str,
    *,
    max_depth: int = 8,
    _stack: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Recursively expand lifecycle and nested package scripts.

    The result takes the highest risk across pre/main/post and every nested script.
    Cycles and depth exhaustion are blocked rather than silently truncated.
    """
    name = str(script_name)
    if name in _stack:
        return {"name": name, "classification": "BLOCKED", "status": "SCRIPT_BLOCKED", "reasons": ["recursive package script cycle"], "children": []}
    if len(_stack) >= max_depth:
        return {"name": name, "classification": "BLOCKED", "status": "SCRIPT_BLOCKED", "reasons": ["package script expansion depth exceeded"], "children": []}

    nodes: list[dict[str, Any]] = []
    for stage in (f"pre{name}", name, f"post{name}"):
        if stage not in scripts:
            continue
        command = str(scripts[stage])
        decision = classify_command(command)
        children = [classify_script_tree(scripts, child, max_depth=max_depth, _stack=(*_stack, name)) for child in _nested_script_names(command)]
        classification = _highest([decision["classification"], *(child["classification"] for child in children)])
        reasons = list(decision["reasons"])
        for child in children:
            if child["classification"] == "BLOCKED":
                reasons.append(f"nested script {child['name']!r} is blocked")
            elif child["classification"] == "REQUIRES_APPROVAL":
                reasons.append(f"nested script {child['name']!r} requires approval")
        nodes.append({
            "stage": stage,
            "command": command,
            "decision": decision,
            "children": children,
            "classification": classification,
            "status": "SCRIPT_BLOCKED" if classification == "BLOCKED" else classification,
            "reasons": sorted(dict.fromkeys(reasons)),
        })
    classification = _highest(node["classification"] for node in nodes) if nodes else "REQUIRES_APPROVAL"
    return {
        "name": name,
        "classification": classification,
        "status": "SCRIPT_BLOCKED" if classification == "BLOCKED" else classification,
        "lifecycle": nodes,
        "reasons": sorted(dict.fromkeys(reason for node in nodes for reason in node["reasons"])),
        "digest": digest_json({"name": name, "nodes": nodes}),
    }


__all__ = ["classify_command", "classify_script_tree"]
