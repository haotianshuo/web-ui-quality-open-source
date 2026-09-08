"""Rule metadata and honest Coverage Ledger statuses."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from .contracts import ContractViolation, digest_json


COVERAGE_STATUSES = {"executed", "violation", "pass", "incomplete", "inapplicable", "error", "unavailable"}


@dataclass(frozen=True)
class RuleMetadata:
    rule_id: str
    category: str
    applicability: tuple[str, ...]
    evidence_method: tuple[str, ...]
    severity: str
    gate_applicable: bool
    provider_id: str
    fixable: bool
    version: str
    deprecated: bool = False
    source: str = "project-internal"
    license: str = "project-internal"


class RuleRegistry:
    def __init__(self, rules: tuple[RuleMetadata, ...]) -> None:
        ids = [item.rule_id for item in rules]
        if len(ids) != len(set(ids)):
            raise ContractViolation("RULE_DUPLICATE", ["$.ruleId: duplicate rule"])
        for item in rules:
            if item.severity not in {"P0", "P1", "P2", "P3"} or not item.version or not item.provider_id or not item.source or not item.license:
                raise ContractViolation("RULE_METADATA_INVALID", [f"$.rules.{item.rule_id}: incomplete metadata"])
        self._rules = {item.rule_id: item for item in rules}

    def require(self, rule_id: str) -> RuleMetadata:
        if rule_id not in self._rules:
            raise ContractViolation("RULE_UNKNOWN", ["$.ruleId: unknown rule"])
        return self._rules[rule_id]

    def digest(self) -> str:
        return digest_json([asdict(self._rules[key]) for key in sorted(self._rules)])


class CoverageLedger:
    def __init__(self, registry: RuleRegistry) -> None:
        self._registry = registry
        self._entries: list[dict[str, object]] = []

    def record(self, run_id: str, rule_id: str, provider_id: str, status: str, evidence_ref: str | None = None) -> None:
        rule = self._registry.require(rule_id)
        if status not in COVERAGE_STATUSES:
            raise ContractViolation("COVERAGE_STATUS_INVALID", ["$.status: unknown coverage status"])
        if provider_id != rule.provider_id:
            raise ContractViolation("COVERAGE_PROVIDER_MISMATCH", ["$.providerId: rule provider mismatch"])
        if status in {"violation", "pass"} and not evidence_ref:
            raise ContractViolation("COVERAGE_EVIDENCE_REQUIRED", ["$.evidenceRef: required"])
        self._entries.append({
            "runId": run_id, "ruleId": rule_id, "providerId": provider_id,
            "status": status, "evidenceRef": evidence_ref,
        })

    def report(self) -> dict[str, object]:
        entries = sorted(self._entries, key=lambda item: (str(item["ruleId"]), str(item["providerId"]), str(item["status"])))
        non_pass = [item for item in entries if item["status"] in {"executed", "incomplete", "error", "unavailable"}]
        result = "NOT_VERIFIED" if not entries or non_pass else ("FAIL" if any(item["status"] == "violation" for item in entries) else "PASS")
        payload: dict[str, object] = {"entries": entries, "result": result}
        payload["digest"] = digest_json(payload)
        return payload
