"""Deterministic, read-only contracts shared by Web UI Quality stages."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import stat
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping, Sequence


RESULTS = {"PASS", "PASS_WITH_WARNINGS", "FAIL", "NOT_VERIFIED"}
SEVERITIES = {"P0", "P1", "P2", "P3"}
FINDING_STATES = {"verified", "unverified"}
FINDING_REQUIRED = {
    "id",
    "category",
    "severity",
    "method",
    "applicability",
    "requiredForCurrentGate",
    "location",
    "instructionSource",
    "evidenceSource",
    "trustLevel",
    "evidenceSummary",
    "impact",
    "recommendation",
    "state",
    "redactionApplied",
    "acceptedDifference",
}
SENSITIVE_MARKER = "RAW_SENSITIVE_FIXTURE_VALUE_DO_NOT_LOG"
SENSITIVE_VALUE_RE = re.compile(
    r"(?ix)"
    r"(?:api[_-]?key|access[_-]?token|auth(?:orization)?|password|passwd|secret|cookie)"
    r"\s*(?:=|:)\s*['\"]?[^\s'\";,]{8,}"
)


class ContractViolation(ValueError):
    """A deterministic contract failure that is safe to serialize."""

    def __init__(self, code: str, errors: Sequence[str]) -> None:
        self.code = code
        self.errors = tuple(sorted(dict.fromkeys(errors)))
        super().__init__(f"{code}: {'; '.join(self.errors)}")

    def as_dict(self) -> dict[str, Any]:
        """Machine-facing representation; JSON Pointer locations are preserved."""
        return {"code": self.code, "errors": list(self.errors)}

    def as_user_dict(self) -> dict[str, Any]:
        """CLI-facing representation without leaking root JSON Pointer syntax."""
        def clean(value: str) -> str:
            return value[3:] if value.startswith("$: ") else value
        errors = [clean(value) for value in self.errors]
        return {"code": self.code, "message": errors[0] if errors else self.code, "errors": errors}


def _validate_json_value(value: Any, path: str = "$") -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ContractViolation("CANONICAL_JSON_INVALID", [f"{path}: non-finite number"])
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            _validate_json_value(child, f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, str):
                raise ContractViolation("CANONICAL_JSON_INVALID", [f"{path}: object key must be string"])
            _validate_json_value(child, f"{path}.{key}")
        return
    raise ContractViolation(
        "CANONICAL_JSON_INVALID",
        [f"{path}: unsupported type {type(value).__name__}"],
    )


def canonical_json(value: Any) -> str:
    """Return UTF-8-compatible canonical JSON with Unicode code-point key order."""

    _validate_json_value(value)
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest_json(value: Any) -> str:
    return sha256_hex(canonical_json(value).encode("utf-8"))


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def redact_text(value: str) -> tuple[str, bool]:
    """Remove credential-like values without returning the captured secret."""

    redacted = value.replace(SENSITIVE_MARKER, "[REDACTED_FIXTURE_VALUE]")
    redacted = SENSITIVE_VALUE_RE.sub("[REDACTED_CREDENTIAL_ASSIGNMENT]", redacted)
    return redacted, redacted != value


def finding_errors(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return ["$: expected object"]
    errors: list[str] = []
    summary = value.get("evidenceSummary")
    if isinstance(summary, str) and (
        SENSITIVE_MARKER in summary or SENSITIVE_VALUE_RE.search(summary) is not None
    ):
        errors.append("$.evidenceSummary: contains unredacted fixture-sensitive marker")
    if "id" not in value:
        errors.append("$.id: required")
    elif not isinstance(value["id"], str) or re.fullmatch(r"[A-Z0-9]+(?:-[A-Z0-9]+)+", value["id"]) is None:
        errors.append("$.id: expected uppercase hyphenated identifier")
    if value.get("severity") not in SEVERITIES:
        errors.append("$.severity: expected one of P0, P1, P2, P3")
    if value.get("state") not in FINDING_STATES:
        errors.append("$.state: expected one of verified, unverified")
    for key in sorted(FINDING_REQUIRED - {"id", "severity", "state"}):
        if key not in value:
            errors.append(f"$.{key}: required")
    method = value.get("method")
    if method is not None and (
        not isinstance(method, list)
        or not method
        or any(item not in {"S", "B", "M"} for item in method)
    ):
        errors.append("$.method: expected non-empty array containing S, B, or M")
    if "requiredForCurrentGate" in value and not isinstance(value["requiredForCurrentGate"], bool):
        errors.append("$.requiredForCurrentGate: expected boolean")
    if "redactionApplied" in value and not isinstance(value["redactionApplied"], bool):
        errors.append("$.redactionApplied: expected boolean")
    if "acceptedDifference" in value and not isinstance(value["acceptedDifference"], bool):
        errors.append("$.acceptedDifference: expected boolean")
    return sorted(dict.fromkeys(errors))


def validate_finding(value: Any) -> dict[str, Any]:
    errors = finding_errors(value)
    if errors:
        raise ContractViolation("FINDING_SCHEMA_INVALID", errors)
    return value


PLAN_REQUIRED = {
    "schemaVersion",
    "businessUnderstanding",
    "currentFramework",
    "productArchetype",
    "pageModes",
    "mainProblems",
    "mustFix",
    "recommendedOptimizations",
    "enterpriseDifferences",
    "unverifiedItems",
    "recommendation",
    "selectionReason",
    "keyTradeoffs",
    "rejectedAlternative",
    "designInterventionLevel",
    "riskLevel",
    "approvedScope",
    "businessInvariants",
    "exclusions",
    "verificationPlan",
    "rollbackPlan",
}


def plan_errors(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return ["$: expected object"]
    errors = [f"$.{key}: required" for key in sorted(PLAN_REQUIRED - set(value))]
    if value.get("schemaVersion") != "1":
        errors.append("$.schemaVersion: expected string '1'")
    if value.get("riskLevel") not in {"R0", "R1", "R2", "R3"}:
        errors.append("$.riskLevel: expected R0, R1, R2, or R3")
    if value.get("designInterventionLevel") not in {1, 2, 3}:
        errors.append("$.designInterventionLevel: expected 1, 2, or 3")
    if not isinstance(value.get("recommendation"), str) or not value.get("recommendation", "").strip():
        errors.append("$.recommendation: expected non-empty string")
    for key in ("approvedScope", "businessInvariants", "exclusions", "verificationPlan", "keyTradeoffs"):
        if key in value and not isinstance(value[key], list):
            errors.append(f"$.{key}: expected array")
    return sorted(dict.fromkeys(errors))


def validate_productization_plan(value: Any) -> dict[str, Any]:
    errors = plan_errors(value)
    if errors:
        raise ContractViolation("PRODUCTIZATION_PLAN_INVALID", errors)
    return value


def canonical_plan_payload(plan: Mapping[str, Any]) -> dict[str, Any]:
    """Return the complete user-visible plan payload for approval binding.

    v0.3 bound only a subset of the plan, allowing material design rationale and
    scope semantics to change without changing the approval digest.  Commercial
    releases bind the full validated plan.
    """

    validated = validate_productization_plan(dict(plan))
    return json.loads(canonical_json(validated))


def plan_digest(plan: Mapping[str, Any]) -> str:
    return digest_json(canonical_plan_payload(plan))


def _normalize_relative_path(raw: str) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise ContractViolation("SOURCE_SCOPE_INVALID", ["$.path: expected non-empty string"])
    normalized = raw.replace("\\", "/")
    pure = PurePosixPath(normalized)
    if pure.is_absolute() or ".." in pure.parts or "." == normalized or "" in pure.parts:
        raise ContractViolation("SOURCE_SCOPE_ESCAPE", [f"$.path: unsafe relative path {raw!r}"])
    if re.match(r"^[A-Za-z]:", normalized):
        raise ContractViolation("SOURCE_SCOPE_ESCAPE", [f"$.path: absolute drive path {raw!r}"])
    return pure.as_posix()


def _ensure_inside(root: Path, resolved: Path, raw: str) -> None:
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise ContractViolation(
            "SOURCE_SCOPE_ESCAPE",
            [f"$.path: resolved target leaves project root for {raw!r}"],
        ) from error


def _link_type(root: Path, candidate: Path) -> str:
    """Classify links in the logical path without exposing absolute paths."""

    relative = candidate.relative_to(root)
    current = root
    found: list[str] = []
    for part in relative.parts:
        current = current / part
        try:
            if current.is_symlink():
                found.append("symbolic-link")
                continue
            is_junction = getattr(current, "is_junction", None)
            if callable(is_junction) and is_junction():
                found.append("junction")
                continue
            attributes = getattr(os.lstat(current), "st_file_attributes", 0)
            if attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0):
                found.append("reparse-point")
        except FileNotFoundError:
            break
    if not found:
        return "regular"
    unique = list(dict.fromkeys(found))
    return unique[0] if len(unique) == 1 else "mixed-reparse"


def build_source_scope_manifest(
    project_root: str | Path,
    paths: Iterable[str],
    *,
    planned_new: Iterable[str] = (),
    missing: Iterable[str] = (),
) -> dict[str, Any]:
    """Build a deterministic explicit manifest without writing to the project."""

    root = Path(project_root).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise ContractViolation("PROJECT_ROOT_INVALID", ["$: project root must be a directory"])
    kinds: list[tuple[str, str]] = []
    kinds.extend((raw, "file") for raw in paths)
    kinds.extend((raw, "planned-new") for raw in planned_new)
    kinds.extend((raw, "missing") for raw in missing)
    normalized: dict[str, tuple[str, str]] = {}
    casefolded: dict[str, str] = {}
    for raw, kind in kinds:
        path = _normalize_relative_path(raw)
        folded = path.casefold()
        if folded in casefolded and casefolded[folded] != path:
            raise ContractViolation(
                "SOURCE_SCOPE_CASE_COLLISION",
                [f"$.entries: case-fold collision between {casefolded[folded]!r} and {path!r}"],
            )
        casefolded[folded] = path
        if path in normalized and normalized[path][1] != kind:
            raise ContractViolation("SOURCE_SCOPE_INVALID", [f"$.entries: conflicting kinds for {path!r}"])
        normalized[path] = (raw, kind)

    entries: list[dict[str, Any]] = []
    for path in sorted(normalized):
        raw, kind = normalized[path]
        candidate = root.joinpath(*PurePosixPath(path).parts)
        if kind == "file":
            try:
                resolved = candidate.resolve(strict=True)
            except FileNotFoundError as error:
                raise ContractViolation("SOURCE_SCOPE_MISSING", [f"$.entries: file missing {path!r}"]) from error
            _ensure_inside(root, resolved, raw)
            if not resolved.is_file():
                raise ContractViolation("SOURCE_SCOPE_INVALID", [f"$.entries: expected file {path!r}"])
            entries.append(
                {
                    "path": path,
                    "kind": "file",
                    "resolvedPath": resolved.relative_to(root).as_posix(),
                    "linkType": _link_type(root, candidate),
                    "size": resolved.stat().st_size,
                    "sha256": hash_file(resolved),
                }
            )
        else:
            resolved_parent = candidate.parent.resolve(strict=True)
            _ensure_inside(root, resolved_parent, raw)
            exists = candidate.exists()
            if exists:
                raise ContractViolation(
                    "SOURCE_SCOPE_INVALID",
                    [f"$.entries: {kind} target already exists {path!r}"],
                )
            entries.append({"path": path, "kind": kind})
    return {"schemaVersion": "1", "projectRoot": ".", "entries": entries}


def source_scope_fingerprint(manifest: Mapping[str, Any]) -> str:
    if manifest.get("schemaVersion") != "1" or manifest.get("projectRoot") != ".":
        raise ContractViolation("SOURCE_SCOPE_INVALID", ["$: unsupported manifest header"])
    entries = manifest.get("entries")
    if not isinstance(entries, list):
        raise ContractViolation("SOURCE_SCOPE_INVALID", ["$.entries: expected array"])
    paths = [entry.get("path") for entry in entries if isinstance(entry, dict)]
    if len(paths) != len(entries) or paths != sorted(paths):
        raise ContractViolation("SOURCE_SCOPE_INVALID", ["$.entries: expected path-sorted objects"])
    return digest_json(dict(manifest))


def load_json(path: str | Path) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ContractViolation("JSON_INPUT_INVALID", ["$: input is not readable UTF-8 JSON"]) from error
