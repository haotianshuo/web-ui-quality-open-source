"""Host-gated execution plans for project-owned verification tools.

This module never executes project binaries.  Project-local tools are untrusted
input and their output remains conditional evidence unless a Host executes the
exact recorded plan and returns the result in the current workflow.
"""
from __future__ import annotations

import os
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from .contracts import ContractViolation, digest_json, hash_file, sha256_hex

_ALLOWED = {
    "tsc": ("--noEmit",),
    "vue-tsc": ("--noEmit",),
    "eslint": (),
    "vitest": ("run",),
    "jest": (),
    "stylelint": (),
}
_TRUSTED_HOST_TOOL_AUTHORITY = object()

_FORBIDDEN_ARGS = {"--fix", "--write", "-u", "--updateSnapshot", "--update-snapshot", "--outDir", "--emitDeclarationOnly"}


def _resolve_local_tool(root: Path, tool: str) -> Path:
    if tool not in _ALLOWED:
        raise ContractViolation("PROJECT_TOOL_NOT_ALLOWED", [f"$: unsupported project tool {tool!r}"])
    bin_dir = root / "node_modules" / ".bin"
    candidates = [bin_dir / tool]
    if os.name == "nt":
        candidates = [bin_dir / f"{tool}.cmd", bin_dir / f"{tool}.exe", bin_dir / tool]
    for path in candidates:
        if path.is_file():
            resolved = path.resolve()
            try:
                resolved.relative_to(root)
            except ValueError:
                continue
            if resolved.is_file():
                return resolved
    raise ContractViolation("PROJECT_TOOL_MISSING", [f"$: local tool {tool!r} was not found under node_modules/.bin"])


def plan_project_tool_execution(
    project_root: str | Path, tool: str, *, args: Iterable[str] = (), timeout_seconds: int = 120,
    run_id: str | None = None, task_id: str | None = None, session_id: str | None = None,
) -> dict[str, Any]:
    root = Path(project_root).expanduser().resolve()
    if not root.is_dir():
        raise ContractViolation("PROJECT_TOOL_SCOPE_INVALID", ["$: project directory required"])
    tool = str(tool)
    argv = [str(x) for x in args]
    lowered = {x.casefold() for x in argv}
    if lowered & {x.casefold() for x in _FORBIDDEN_ARGS}:
        raise ContractViolation("PROJECT_TOOL_WRITE_FORBIDDEN", ["$: write-producing tool arguments are forbidden"])
    if any(any(op in item for op in ("&&", "||", ";", "|", "\n")) for item in argv):
        raise ContractViolation("PROJECT_TOOL_SHELL_FORBIDDEN", ["$: shell composition is forbidden"])
    required = list(_ALLOWED[tool])
    for item in required:
        if item not in argv:
            argv.insert(0, item)
    executable = _resolve_local_tool(root, tool)
    executable_ref = executable.relative_to(root).as_posix()
    body = {
        "schemaVersion": "2",
        "projectRoot": ".",
        "tool": tool,
        "executable": executable_ref,
        "executableSha256": hash_file(executable),
        "argv": argv,
        "cwd": ".",
        "runBinding": {"runId": run_id, "taskId": task_id, "sessionId": session_id},
        "network": "DENY_BY_DEFAULT",
        "filesystemPolicy": "READ_ONLY_PROJECT",
        "allowedWriteRoots": [],
        "timeoutSeconds": max(1, min(int(timeout_seconds), 600)),
        "resourcePolicy": "HOST_ENFORCED",
        "execution": "HOST_GATED",
        "runtimeMayExecute": False,
        "evidenceAuthority": "CONDITIONAL_PROJECT_TOOL_EVIDENCE",
    }
    body["planDigest"] = digest_json(body)
    return body


@dataclass(frozen=True, slots=True)
class TrustedHostToolResult:
    payload: Mapping[str, Any]
    result_digest: str
    _authority: object

    def to_dict(self) -> dict[str, Any]:
        return {**dict(self.payload), "resultDigest": self.result_digest}


def verify_host_tool_result(project_root: str | Path, plan: Mapping[str, Any], receipt: Mapping[str, Any]) -> TrustedHostToolResult:
    root = Path(project_root).expanduser().resolve()
    plan_body = {k: v for k, v in dict(plan).items() if k != "planDigest"}
    plan_digest = digest_json(plan_body)
    if plan.get("planDigest") != plan_digest or receipt.get("planDigest") != plan_digest:
        raise ContractViolation("PROJECT_TOOL_RESULT_MISMATCH", ["$.planDigest: result is not bound to the exact execution plan"])
    executable = (root / str(plan.get("executable") or "")).resolve()
    try:
        executable.relative_to(root)
    except ValueError as error:
        raise ContractViolation("PROJECT_TOOL_SCOPE_INVALID", ["$.executable: escapes project root"]) from error
    if not executable.is_file() or hash_file(executable) != plan.get("executableSha256"):
        raise ContractViolation("PROJECT_TOOL_BINARY_DRIFT", ["$.executableSha256: project tool changed after the plan was created"])
    expected = {
        "tool": plan.get("tool"), "executableSha256": plan.get("executableSha256"),
        "argv": list(plan.get("argv") or []), "cwd": plan.get("cwd"),
    }
    mismatches = [key for key, value in expected.items() if receipt.get(key) != value]
    if mismatches:
        raise ContractViolation("PROJECT_TOOL_RESULT_MISMATCH", [f"$.{key}: Host result does not match the execution plan" for key in mismatches])
    run_binding = dict(plan.get("runBinding") or {})
    binding_required = any(run_binding.get(key) for key in ("runId", "taskId", "sessionId"))
    if binding_required and receipt.get("runBinding") != run_binding:
        raise ContractViolation("PROJECT_TOOL_RESULT_MISMATCH", ["$.runBinding: Host result is not bound to the exact repair run/task/session"])
    receipt_filesystem_policy = receipt.get("filesystemPolicy")
    if receipt_filesystem_policy is not None and receipt_filesystem_policy != plan.get("filesystemPolicy"):
        raise ContractViolation("PROJECT_TOOL_RESULT_MISMATCH", ["$.filesystemPolicy: Host result does not match the execution plan"])
    stdout = str(receipt.get("stdout") or "")
    stderr = str(receipt.get("stderr") or "")
    if len(stdout.encode("utf-8")) > 1_000_000 or len(stderr.encode("utf-8")) > 1_000_000:
        raise ContractViolation("PROJECT_TOOL_RESULT_TOO_LARGE", ["$: stdout/stderr must each be <= 1MB"])
    timed_out = bool(receipt.get("timedOut", False))
    network_ok = receipt.get("networkPolicyEnforced") is True
    resource_ok = receipt.get("resourcePolicyEnforced") is True
    filesystem_ok = receipt_filesystem_policy == plan.get("filesystemPolicy") and receipt.get("filesystemPolicyEnforced") is True
    unexpected_writes_raw = receipt.get("unexpectedWrites", [])
    if not isinstance(unexpected_writes_raw, list) or any(not isinstance(item, str) for item in unexpected_writes_raw):
        raise ContractViolation("PROJECT_TOOL_RESULT_INVALID", ["$.unexpectedWrites: array of project-relative strings required"])
    unexpected_writes = sorted({item.replace("\\", "/").lstrip("./") for item in unexpected_writes_raw if item.strip()})
    if any(item.startswith("../") or item.startswith("/") for item in unexpected_writes):
        raise ContractViolation("PROJECT_TOOL_RESULT_INVALID", ["$.unexpectedWrites: project-relative paths required"])
    policy_ok = network_ok and resource_ok and filesystem_ok
    exit_code = int(receipt.get("exitCode", -1))
    if unexpected_writes:
        status = "FAIL"
    elif timed_out or not policy_ok:
        status = "NOT_VERIFIED"
    else:
        status = "PASS" if exit_code == 0 else "FAIL"
    payload = {
        "schemaVersion": "2", "planDigest": plan_digest, "tool": plan.get("tool"),
        "executableSha256": plan.get("executableSha256"), "argv": list(plan.get("argv") or []), "cwd": plan.get("cwd"),
        "runBinding": run_binding,
        "status": status, "exitCode": exit_code, "timedOut": timed_out,
        "networkPolicyEnforced": network_ok,
        "resourcePolicyEnforced": resource_ok,
        "filesystemPolicy": plan.get("filesystemPolicy"),
        "filesystemPolicyEnforced": filesystem_ok,
        "unexpectedWrites": unexpected_writes,
        "stdoutSha256": sha256_hex(stdout.encode("utf-8")), "stderrSha256": sha256_hex(stderr.encode("utf-8")),
        "evidenceAuthority": "CONDITIONAL_PROJECT_TOOL_EVIDENCE",
        "claimBoundary": "Host-executed project tool result bound to an exact plan and local binary hash. PASS additionally requires network/resource/filesystem policy enforcement and no unexpected project writes; it is not independent parser evidence or remote attestation.",
    }
    return TrustedHostToolResult(payload, digest_json(payload), _TRUSTED_HOST_TOOL_AUTHORITY)


def require_verified_host_tool_result(value: TrustedHostToolResult | None) -> TrustedHostToolResult:
    if not isinstance(value, TrustedHostToolResult) or value._authority is not _TRUSTED_HOST_TOOL_AUTHORITY:
        raise ContractViolation("TRUSTED_HOST_TOOL_RESULT_REQUIRED", ["$: process-local verified Host tool result required"])
    return value


def verify_host_tool_results(project_root: str | Path, plans: Sequence[Mapping[str, Any]], receipts: Sequence[Mapping[str, Any]]) -> list[TrustedHostToolResult]:
    by_digest = {str(item.get("planDigest") or ""): item for item in receipts}
    verified: list[TrustedHostToolResult] = []
    for plan in plans:
        digest = str(plan.get("planDigest") or "")
        if digest not in by_digest:
            raise ContractViolation("PROJECT_TOOL_RESULT_REQUIRED", [f"$: Host result required for project tool plan {digest}"])
        verified.append(verify_host_tool_result(project_root, plan, by_digest[digest]))
    return verified



def summarise_host_tool_results(results: Sequence[TrustedHostToolResult]) -> dict[str, Any]:
    """Collapse authenticated Host tool evidence without promoting its authority.

    Authenticity and semantic success are separate: a correctly bound compiler
    result may still be FAIL, and a timed-out/non-policy-enforced result remains
    NOT_VERIFIED.  Only all-PASS results can clear the project-tool gate.
    """
    rows = [item.to_dict() for item in results]
    statuses = [str(row.get("status") or "NOT_VERIFIED") for row in rows]
    if not rows:
        status = "NOT_APPLICABLE"
    elif any(value == "FAIL" for value in statuses):
        status = "FAIL"
    elif any(value != "PASS" for value in statuses):
        status = "NOT_VERIFIED"
    else:
        status = "PASS"
    return {
        "schemaVersion": "1",
        "status": status,
        "results": rows,
        "passCount": sum(value == "PASS" for value in statuses),
        "failCount": sum(value == "FAIL" for value in statuses),
        "notVerifiedCount": sum(value not in {"PASS", "FAIL"} for value in statuses),
        "claimBoundary": "PASS means every Host-approved project-tool result passed under its exact recorded plan; it is still conditional project-tool evidence, not independent parser evidence.",
    }


def require_passing_host_tool_results(results: Sequence[TrustedHostToolResult]) -> dict[str, Any]:
    """Require semantic PASS after authenticity has already been verified."""
    for item in results:
        require_verified_host_tool_result(item)
    summary = summarise_host_tool_results(results)
    if summary["status"] == "FAIL":
        failed = [str(row.get("tool")) for row in summary["results"] if row.get("status") == "FAIL"]
        raise ContractViolation("PROJECT_TOOL_VERIFICATION_FAILED", [f"$: Host project-tool verification failed: {', '.join(failed)}"])
    if summary["status"] == "NOT_VERIFIED":
        pending = [str(row.get("tool")) for row in summary["results"] if row.get("status") != "PASS"]
        raise ContractViolation("PROJECT_TOOL_VERIFICATION_NOT_VERIFIED", [f"$: Host project-tool verification is incomplete: {', '.join(pending)}"])
    return summary

def classify_host_tool_result(plan: dict[str, Any], *, exit_code: int, stdout_digest: str | None = None) -> dict[str, Any]:
    # Compatibility helper only. New repair flows must use verify_host_tool_result().
    return {
        "schemaVersion": "1", "planDigest": plan.get("planDigest"),
        "status": "PASS" if exit_code == 0 else "FAIL", "exitCode": int(exit_code),
        "stdoutDigest": stdout_digest, "evidenceAuthority": "UNVERIFIED_HOST_REPORT",
        "claimBoundary": "Compatibility-only Host report; not accepted as verified project-tool evidence.",
    }


__all__ = ["plan_project_tool_execution", "classify_host_tool_result", "TrustedHostToolResult", "verify_host_tool_result", "verify_host_tool_results", "require_verified_host_tool_result", "summarise_host_tool_results", "require_passing_host_tool_results"]
