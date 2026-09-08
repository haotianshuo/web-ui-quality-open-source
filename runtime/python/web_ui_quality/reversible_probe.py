"""Deterministic, reversible A1 task probe protected by the Mutation Firewall."""
from __future__ import annotations

from typing import Any


def _snapshot(page: Any) -> dict[str, Any]:
    return page.evaluate("""() => ({
      url: location.href,
      openDetails: Array.from(document.querySelectorAll('details')).map((el,i)=>[i,el.open]),
      expanded: Array.from(document.querySelectorAll('[aria-expanded]')).map((el,i)=>[i,el.getAttribute('aria-expanded')]),
      selectedTabs: Array.from(document.querySelectorAll('[role=tab]')).map((el,i)=>[i,el.getAttribute('aria-selected')]),
      bodyText: (document.body?.innerText || '').slice(0,4000)
    })""")


def select_probe(page: Any) -> dict[str, Any] | None:
    return page.evaluate("""() => {
      const visible = el => { const r=el.getBoundingClientRect(); const s=getComputedStyle(el); return r.width>0&&r.height>0&&s.visibility!=='hidden'&&s.display!=='none'; };
      const summary = Array.from(document.querySelectorAll('details:not([open]) > summary')).find(visible);
      if (summary) return {kind:'details', selector:'details:not([open]) > summary'};
      const expandable = Array.from(document.querySelectorAll('[aria-expanded="false"]')).find(el=>visible(el)&&['BUTTON','A'].includes(el.tagName));
      if (expandable) { expandable.setAttribute('data-wuq-safe-probe','1'); return {kind:'aria-expanded', selector:'[data-wuq-safe-probe="1"]'}; }
      const tab = Array.from(document.querySelectorAll('[role="tab"][aria-selected="false"]')).find(visible);
      if (tab) { tab.setAttribute('data-wuq-safe-probe','1'); return {kind:'tab', selector:'[data-wuq-safe-probe="1"]'}; }
      return null;
    }""")


def run_reversible_probe(page: Any, firewall: Any, *, timeout_ms: int = 5000) -> dict[str, Any]:
    candidate = select_probe(page)
    if not candidate:
        return {"status": "NOT_VERIFIED_NO_SAFE_TARGET", "candidate": None, "restored": None}
    before = _snapshot(page)
    locator = page.locator(candidate["selector"]).first
    try:
        locator.click(timeout=timeout_ms)
        page.wait_for_timeout(200)
        after = _snapshot(page)
        if firewall.mutation_attempted:
            return {"status": "BLOCKED_MUTATION_ATTEMPT", "candidate": candidate, "restored": False, "before": before, "after": after}
        changed = before != after
        if not changed:
            return {"status": "FAIL_NO_STATE_CHANGE", "candidate": candidate, "restored": False, "before": before, "after": after}
        locator.click(timeout=timeout_ms)
        page.wait_for_timeout(200)
        restored = _snapshot(page)
        if restored == before:
            status = "PASS_RESTORED"
        else:
            status = "FAIL_NOT_RESTORED"
        return {"status": status, "candidate": candidate, "restored": status == "PASS_RESTORED", "before": before, "after": after, "restoredState": restored}
    except Exception as error:
        return {"status": "NOT_VERIFIED_NO_SAFE_TARGET", "candidate": candidate, "restored": False, "error": f"{type(error).__name__}: {error}"}
    finally:
        try:
            page.evaluate("document.querySelectorAll('[data-wuq-safe-probe]').forEach(el=>el.removeAttribute('data-wuq-safe-probe'))")
        except Exception:
            pass


__all__ = ["run_reversible_probe", "select_probe"]
