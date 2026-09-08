"""Pure candidate-patch bridge; it never reads or writes a target project."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .contracts import ContractViolation, digest_json
from .provider_contracts import ProviderEnvelope, normalize_target
from .risk import escalate_risk, require_safe_edit_risk, risk_from_impacts


@dataclass(frozen=True)
class PatchCandidate:
    provider_id: str
    target: str
    start_byte: int
    end_byte: int
    replacement: str
    source_sha256: str
    risk_level: str
    evidence_digest: str
    candidate_digest: str
    language: str
    match_count: int


def build_patch_candidate(
    envelope: ProviderEnvelope,
    *,
    approved_scope: Iterable[str],
    start_byte: int,
    end_byte: int,
    replacement: str,
    source_sha256: str,
    risk_level: str,
    detected_impacts: Iterable[str] = (),
    language: str = "unknown",
    source_size: int | None = None,
    approved_ranges: Iterable[tuple[int, int]] = (),
    changed_ranges: Iterable[tuple[int, int]] = (),
    match_count: int = 1,
    parse_complete: bool = False,
    grammar_compatible: bool = False,
    query_overflow: bool = False,
    second_transform_empty: bool = False,
) -> PatchCandidate:
    if envelope.evidence_kind != "candidate_patch" or envelope.status != "violation":
        raise ContractViolation("PATCH_CANDIDATE_INVALID", ["$: envelope is not candidate-patch evidence"])
    target = normalize_target(envelope.target)
    scope = {normalize_target(item, "$.approvedScope") for item in approved_scope}
    if target not in scope:
        raise ContractViolation("PATCH_CANDIDATE_SCOPE_MISMATCH", ["$.target: outside approved scope"])
    if not isinstance(start_byte, int) or isinstance(start_byte, bool) or start_byte < 0:
        raise ContractViolation("PATCH_CANDIDATE_INVALID", ["$.startByte: invalid"])
    if not isinstance(end_byte, int) or isinstance(end_byte, bool) or end_byte < start_byte:
        raise ContractViolation("PATCH_CANDIDATE_INVALID", ["$.endByte: invalid"])
    if not isinstance(replacement, str):
        raise ContractViolation("PATCH_CANDIDATE_INVALID", ["$.replacement: expected string"])
    if len(source_sha256) != 64 or any(ch not in "0123456789abcdef" for ch in source_sha256):
        raise ContractViolation("PATCH_CANDIDATE_INVALID", ["$.sourceSha256: expected sha256"])
    if language not in {"html", "css", "javascript", "typescript", "jsx", "tsx", "vue", "svelte"}:
        raise ContractViolation("PATCH_CANDIDATE_LANGUAGE_UNSUPPORTED", ["$.language: unsupported"])
    if not isinstance(source_size, int) or isinstance(source_size, bool) or source_size < end_byte:
        raise ContractViolation("PATCH_CANDIDATE_RANGE_INVALID", ["$.sourceSize: byte range outside source"])
    approved = tuple(approved_ranges)
    changed = tuple(changed_ranges)

    def valid_range(item: object) -> bool:
        return (
            isinstance(item, tuple)
            and len(item) == 2
            and all(isinstance(v, int) and not isinstance(v, bool) for v in item)
            and 0 <= item[0] <= item[1] <= source_size
        )

    if not approved or any(not valid_range(item) for item in approved) or any(not valid_range(item) for item in changed):
        raise ContractViolation("PATCH_CANDIDATE_RANGE_INVALID", ["$: approved/changed ranges invalid"])
    if not any(left <= start_byte and end_byte <= right for left, right in approved):
        raise ContractViolation("PATCH_CANDIDATE_SCOPE_MISMATCH", ["$: replacement is outside approved node range"])
    if any(not any(left <= child_left and child_right <= right for left, right in approved) for child_left, child_right in changed):
        raise ContractViolation("PATCH_CANDIDATE_SCOPE_MISMATCH", ["$: changed range exceeds approved node"])
    if match_count != 1 or not parse_complete or not grammar_compatible or query_overflow or not second_transform_empty:
        raise ContractViolation("PATCH_CANDIDATE_SAFETY_UNVERIFIED", ["$: parse, grammar, match-count, query, or idempotency gate failed"])
    impacts = set(detected_impacts)
    risk = require_safe_edit_risk(escalate_risk(risk_level, risk_from_impacts(impacts)))
    payload = {"endByte": end_byte, "evidenceDigest": envelope.evidence_digest,
               "providerId": envelope.provider_id, "replacement": replacement,
               "riskLevel": risk, "sourceSha256": source_sha256,
               "startByte": start_byte, "target": target, "language": language,
               "sourceSize": source_size,
               "approvedRanges": [[left, right] for left, right in approved],
               "changedRanges": [[left, right] for left, right in changed],
               "matchCount": match_count, "parseComplete": parse_complete,
               "grammarCompatible": grammar_compatible, "queryOverflow": query_overflow,
               "secondTransformEmpty": second_transform_empty}
    return PatchCandidate(envelope.provider_id, target, start_byte, end_byte, replacement,
                          source_sha256, risk, envelope.evidence_digest, digest_json(payload), language, match_count)
