"""Best-effort evidence redaction for persisted Browser artifacts.

This is a persistence boundary, not a claim that arbitrary visual PII can be
recognized. Raw values may exist transiently inside the Browser/Host process;
WUQ removes common credentials and bounded PII patterns before textual evidence
is written and masks known sensitive DOM fields before screenshots.
"""
from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

_SECRET_KEY_RE = re.compile(r"(?:auth|token|secret|credential|cookie|session|csrf|password|passwd|api[_-]?key|signature|signed)", re.I)
_BEARER_RE = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{8,}", re.I)
_JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}\b")
_QUERY_SECRET_RE = re.compile(r"([?&](?:access[_-]?token|token|key|api[_-]?key|secret|session|code)=)[^&#\s]+", re.I)
_ASSIGN_SECRET_RE = re.compile(r"\b((?:access[_-]?token|token|api[_-]?key|secret|password|session|cookie|authorization)\s*[:=]\s*)([^\s,;]{4,})", re.I)
_EMAIL_RE = re.compile(r"(?<![\w.+-])([A-Z0-9._%+-]+)@([A-Z0-9.-]+\.[A-Z]{2,})(?![\w.-])", re.I)
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d[\d ()-]{7,}\d)(?!\d)")

REDACTED = "[REDACTED]"


def redact_text(value: Any, *, pii: bool = True) -> str:
    text = str(value or "")
    text = _BEARER_RE.sub("Bearer " + REDACTED, text)
    text = _JWT_RE.sub(REDACTED, text)
    text = _QUERY_SECRET_RE.sub(lambda m: m.group(1) + REDACTED, text)
    text = _ASSIGN_SECRET_RE.sub(lambda m: m.group(1) + REDACTED, text)
    if pii:
        text = _EMAIL_RE.sub(REDACTED, text)
        text = _PHONE_RE.sub(REDACTED, text)
    return text


def redact_structure(value: Any, *, pii: bool = True) -> Any:
    if isinstance(value, Mapping):
        out: dict[str, Any] = {}
        for raw_key, raw_value in value.items():
            key = str(raw_key)
            if _SECRET_KEY_RE.search(key):
                # Preserve only type/shape, never secret-like values.
                if isinstance(raw_value, (list, tuple, dict)):
                    out[key] = {"redacted": True, "kind": type(raw_value).__name__, "count": len(raw_value)}
                elif raw_value is None:
                    out[key] = None
                else:
                    out[key] = REDACTED
            else:
                out[key] = redact_structure(raw_value, pii=pii)
        return out
    if isinstance(value, (list, tuple)):
        return [redact_structure(item, pii=pii) for item in value]
    if isinstance(value, str):
        return redact_text(value, pii=pii)
    return value


_SCREENSHOT_MASK_JS = r"""
() => {
  const selectors = [
    'input[type="password"]',
    'input[autocomplete="one-time-code"]',
    'input[autocomplete^="cc-"]',
    '[data-wuq-sensitive]',
    '[data-private="true"]',
    '[data-sensitive="true"]'
  ];
  const nodes = Array.from(document.querySelectorAll(selectors.join(',')));
  for (const node of nodes) {
    node.setAttribute('data-wuq-redacted-for-evidence', 'true');
    node.style.setProperty('filter', 'blur(12px)', 'important');
    node.style.setProperty('color', 'transparent', 'important');
    node.style.setProperty('text-shadow', '0 0 12px rgba(0,0,0,.8)', 'important');
  }
  return nodes.length;
}
"""


def mask_sensitive_dom_for_screenshot(page: Any) -> int:
    """Mask known/annotated sensitive DOM nodes before a persisted screenshot.

    This does not claim automatic recognition of arbitrary PII rendered as text.
    Product owners can mark additional regions with ``data-wuq-sensitive``.
    """
    try:
        return int(page.evaluate(_SCREENSHOT_MASK_JS) or 0)
    except Exception:
        return 0


__all__ = ["REDACTED", "redact_text", "redact_structure", "mask_sensitive_dom_for_screenshot"]
