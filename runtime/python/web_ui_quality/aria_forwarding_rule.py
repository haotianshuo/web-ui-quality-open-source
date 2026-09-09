"""Registered cross-framework probes for accessible-name/property forwarding."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, NamedTuple


class _RuleSpec(NamedTuple):
    suffixes: frozenset[str]
    gap: re.Pattern[str]
    selector: str
    reason_code: str


_RULE_REGISTRY = (
    _RuleSpec(frozenset({".js", ".jsx", ".ts", ".tsx"}), re.compile(r"(?is)\bInputBase\s*=\s*React\.forwardRef\s*\(\s*function\s+InputBase\b(?:(?!InputBase\.propTypes).)*?['\"]aria-describedby['\"]\s*:\s*(?P<alias>[A-Za-z_$][\w$]*)\s*,?.*?(?P<location><Input\b(?=[^>]*\baria-describedby\s*=\s*\{\s*(?P=alias)\s*\})(?![^>]*\baria-label\s*=)[^>]*>)"), "InputBase > Input", "TOP_LEVEL_ARIA_LABEL_NOT_FORWARDED_TO_CONTROL"),
    _RuleSpec(frozenset({".vue"}), re.compile(r"(?is)\A(?:(?!\binputIds\b).)*?(?P<location>const\s+labelFor\s*=\s*computed\s*\(\s*\(\)\s*=>\s*props\.for\s*\|\|\s*propString\.value\s*\))"), "ElFormItem > control", "FORM_LABEL_NOT_BOUND_TO_CONTROL"),
    _RuleSpec(frozenset({".tsx"}), re.compile(r"(?is)\A(?![\s\S]*watchForAriaAttributeChanges)(?=[\s\S]*\btag\s*:\s*['\"]ion-button['\"])(?=[\s\S]*\bshadow\s*:\s*true\b)(?=[\s\S]*inheritAriaAttributes)(?=[\s\S]*\{\.\.\.inheritedAttributes\})[\s\S]*?(?P<location>@Component)"), "ion-button > native control", "HOST_ARIA_ATTRIBUTES_NOT_SYNCHRONIZED_TO_CONTROL"),
)


def _line(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def scan_aria_forwarding_gaps(path: str, text: str) -> Iterable[tuple[int, str, str]]:
    suffix = Path(path).suffix.casefold()
    for spec in _RULE_REGISTRY:
        if suffix not in spec.suffixes:
            continue
        for match in spec.gap.finditer(text):
            yield _line(text, match.start("location")), spec.selector, spec.reason_code
