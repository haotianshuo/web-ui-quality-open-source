"""Stable metadata for the install-free Lite rule set."""

from __future__ import annotations

from .coverage import CoverageLedger, RuleMetadata, RuleRegistry


_RULES = (
    ("SEC-PLAINTEXT-CREDENTIAL", "security", "P0"),
    ("SEC-PROMPT-INJECTION", "security", "P1"),
    ("CONTENT-PLACEHOLDER", "content", "P3"),
    ("SEC-DANGEROUS-DOM-WRITE", "security", "P1"),
    ("A11Y-FOCUS-OUTLINE-REMOVED", "accessibility", "P1"),
    ("A11Y-DUPLICATE-ID", "accessibility", "P1"),
    ("A11Y-FORM-CONTROL-NAME", "accessibility", "P1"),
    ("A11Y-IMAGE-ALT-MISSING", "accessibility", "P2"),
    ("SEC-UNSAFE-BLANK-TARGET", "security", "P2"),
    ("SEM-SCRIPT-MODULE-MISMATCH", "logic", "P1"),
    ("SEM-FILTER-CONTROL-MISSING", "logic", "P1"),
    ("SEM-MUTUALLY-EXCLUSIVE-STATES", "logic", "P1"),
)


def builtin_rule_registry() -> RuleRegistry:
    return RuleRegistry(tuple(
        RuleMetadata(
            rule_id, category, ("web-source",), ("S",), severity, True,
            "builtin-lite", False, "1.0.0",
        )
        for rule_id, category, severity in _RULES
    ))


def coverage_for_findings(run_id: str, findings: list[dict[str, object]]) -> dict[str, object]:
    ledger = CoverageLedger(builtin_rule_registry())
    finding_ids = [str(item.get("id", "")) for item in findings]
    for rule_id, _, _ in _RULES:
        matched = any(value == rule_id or value.startswith(rule_id + "-") for value in finding_ids)
        ledger.record(
            run_id, rule_id, "builtin-lite", "violation" if matched else "pass",
            f"finding:{rule_id}" if matched else f"coverage:{rule_id}",
        )
    return ledger.report()
