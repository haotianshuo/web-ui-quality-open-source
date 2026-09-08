"""Safe declarative browser journeys with Outcome Proof.

The P0-A contract distinguishes "Playwright clicked the control" from "the
user-visible task produced the promised result".  Existing 3.x journey files
remain valid; an optional ``outcome`` object adds one to three independent
signals and explicit PASS/FAIL/NOT_VERIFIED evidence.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from .contracts import ContractViolation

_ALLOWED = {
    "goto", "click", "dblclick", "fill", "press", "select", "check", "uncheck",
    "wait_for", "assert_visible", "assert_hidden", "assert_text", "assert_value",
    "assert_checked", "assert_count", "assert_url", "screenshot", "back", "reload",
    "scroll", "hover", "focus",
}
_MUTATING_TOKENS = (
    "delete", "remove", "destroy", "purchase", "pay", "submit", "approve", "reject",
    "publish", "upload", "save", "create", "删除", "支付", "提交", "审批", "驳回",
    "作废", "发布", "上传", "保存", "新建", "确认发放",
)
_ALLOWED_RISKS = {"read-only", "ui-state", "submit", "destructive"}
_OUTCOME_KINDS = {
    "state_changed", "url_contains", "visible", "hidden", "text_contains",
    "value_equals", "checked_equals", "count_equals", "attribute_equals",
    "request_observed", "no_page_error", "no_console_error",
}
_OUTCOME_ROLES = {"user_visible", "independent", "persistence", "recovery", "supporting"}


@dataclass(frozen=True, slots=True)
class JourneyPolicy:
    allow_submit: bool = False
    approved_action_ids: frozenset[str] = field(default_factory=frozenset)
    max_steps: int = 60
    timeout_ms: int = 10_000
    allowed_risks: frozenset[str] = field(default_factory=lambda: frozenset(_ALLOWED_RISKS))


def _locator_description(raw: Mapping[str, Any]) -> str:
    for key in ("selector", "role", "label", "placeholder", "testId", "text"):
        if raw.get(key):
            return f"{key}={raw.get(key)}"
    return "none"


def _infer_risk(raw: Mapping[str, Any]) -> str:
    explicit = str(raw.get("risk", "")).strip().casefold()
    if explicit:
        if explicit not in _ALLOWED_RISKS:
            raise ContractViolation("JOURNEY_RISK_INVALID", [f"risk={explicit!r}"])
        return explicit
    action = str(raw.get("action", "")).strip()
    if action in {"goto", "wait_for", "assert_visible", "assert_hidden", "assert_text", "assert_value", "assert_checked", "assert_count", "assert_url", "screenshot", "back", "reload", "scroll", "hover", "focus"}:
        return "read-only"
    text = " ".join(str(raw.get(k, "")) for k in ("name", "value", "text", "selector", "label", "role", "description")).casefold()
    if any(token in text for token in _MUTATING_TOKENS):
        return "destructive" if any(token in text for token in ("delete", "remove", "destroy", "删除", "作废")) else "submit"
    return "ui-state"


def _validate_signal(signal: Any, path: str) -> dict[str, Any]:
    if not isinstance(signal, Mapping):
        raise ContractViolation("JOURNEY_OUTCOME_INVALID", [f"{path}: expected object"])
    item = dict(signal)
    kind = str(item.get("kind", "")).strip()
    if kind not in _OUTCOME_KINDS:
        raise ContractViolation("JOURNEY_OUTCOME_INVALID", [f"{path}.kind: unsupported {kind!r}"])
    item["kind"] = kind
    evidence_role = str(item.get("evidenceRole") or "supporting")
    if evidence_role not in _OUTCOME_ROLES:
        raise ContractViolation("JOURNEY_OUTCOME_INVALID", [f"{path}.evidenceRole: unsupported {evidence_role!r}"])
    item["evidenceRole"] = evidence_role
    if kind in {"visible", "hidden", "text_contains", "value_equals", "checked_equals", "count_equals", "attribute_equals"}:
        locator_fields = [key for key in ("selector", "role", "label", "placeholder", "testId", "text") if str(item.get(key, "")).strip()]
        if not locator_fields:
            raise ContractViolation("JOURNEY_OUTCOME_INVALID", [f"{path}: locator required"])
    if kind == "attribute_equals" and not str(item.get("attribute", "")).strip():
        raise ContractViolation("JOURNEY_OUTCOME_INVALID", [f"{path}.attribute: required"])
    if kind == "request_observed" and not str(item.get("urlContains", "")).strip():
        raise ContractViolation("JOURNEY_OUTCOME_INVALID", [f"{path}.urlContains: required"])
    return item


def _validate_outcome(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ContractViolation("JOURNEY_OUTCOME_INVALID", [f"{path}: expected object"])
    signals_raw = value.get("signals")
    if not isinstance(signals_raw, list) or not 1 <= len(signals_raw) <= 3:
        raise ContractViolation("JOURNEY_OUTCOME_INVALID", [f"{path}.signals: expected 1-3 signals"])
    signals = [_validate_signal(item, f"{path}.signals[{index}]") for index, item in enumerate(signals_raw)]
    minimum = int(value.get("minimumSatisfied", len(signals)))
    if minimum < 1 or minimum > len(signals):
        raise ContractViolation("JOURNEY_OUTCOME_INVALID", [f"{path}.minimumSatisfied: outside signal count"])
    return {
        "description": str(value.get("description") or "操作后应产生可观察结果"),
        "required": bool(value.get("required", True)),
        "settleMs": max(0, min(int(value.get("settleMs", 350)), 5_000)),
        "minimumSatisfied": minimum,
        "signals": signals,
    }


def validate_journey(value: Any, policy: JourneyPolicy | None = None) -> list[dict[str, Any]]:
    policy = policy or JourneyPolicy()
    if not isinstance(value, list) or not value:
        raise ContractViolation("JOURNEY_INVALID", ["$: expected non-empty array"])
    if len(value) > policy.max_steps:
        raise ContractViolation("JOURNEY_INVALID", [f"$: exceeds maxSteps={policy.max_steps}"])
    result: list[dict[str, Any]] = []
    ids: set[str] = set()
    for index, raw in enumerate(value):
        if not isinstance(raw, Mapping):
            raise ContractViolation("JOURNEY_INVALID", [f"$[{index}]: expected object"])
        action = str(raw.get("action", "")).strip()
        if action not in _ALLOWED:
            raise ContractViolation("JOURNEY_ACTION_FORBIDDEN", [f"$[{index}].action: {action!r}"])
        item = dict(raw)
        item["action"] = action
        action_id = str(raw.get("id") or f"step-{index + 1}").strip()
        if not action_id or action_id in ids:
            raise ContractViolation("JOURNEY_INVALID", [f"$[{index}].id: empty or duplicate"])
        ids.add(action_id)
        item["id"] = action_id
        risk = _infer_risk(raw)
        if risk not in policy.allowed_risks:
            raise ContractViolation("JOURNEY_RISK_NOT_ALLOWED", [f"$[{index}] {action_id}: {risk} not allowed in this run"])
        item["risk"] = risk
        approved = action_id in policy.approved_action_ids or (risk == "submit" and policy.allow_submit)
        if risk in {"submit", "destructive"} and not approved:
            raise ContractViolation(
                "JOURNEY_MUTATION_APPROVAL_REQUIRED",
                [f"$[{index}] {action_id}: {risk} action requires step-scoped host approval"],
            )
        needs_locator = action in {
            "click", "dblclick", "fill", "press", "select", "check", "uncheck", "wait_for",
            "assert_visible", "assert_hidden", "assert_text", "assert_value", "assert_checked",
            "assert_count", "hover", "focus",
        }
        locator_fields = [key for key in ("selector", "role", "label", "placeholder", "testId", "text") if str(raw.get(key, "")).strip()]
        if needs_locator and not locator_fields:
            raise ContractViolation("JOURNEY_INVALID", [f"$[{index}]: one locator field is required"])
        if len(locator_fields) > 1 and "selector" in locator_fields:
            raise ContractViolation("JOURNEY_INVALID", [f"$[{index}]: selector cannot be mixed with semantic locators"])
        item["locatorStrategy"] = _locator_description(raw)
        if raw.get("outcome") is not None:
            item["outcome"] = _validate_outcome(raw.get("outcome"), f"$[{index}].outcome")
        result.append(item)
    return result


def _locator(page: Any, step: Mapping[str, Any]) -> Any:
    exact = bool(step.get("exact", False))
    if step.get("selector"):
        locator = page.locator(str(step["selector"]))
    elif step.get("role"):
        kwargs: dict[str, Any] = {"exact": exact}
        if step.get("name") is not None:
            kwargs["name"] = str(step.get("name"))
        locator = page.get_by_role(str(step["role"]), **kwargs)
    elif step.get("label"):
        locator = page.get_by_label(str(step["label"]), exact=exact)
    elif step.get("placeholder"):
        locator = page.get_by_placeholder(str(step["placeholder"]), exact=exact)
    elif step.get("testId"):
        locator = page.get_by_test_id(str(step["testId"]))
    elif step.get("text"):
        locator = page.get_by_text(str(step["text"]), exact=exact)
    else:
        raise AssertionError("locator missing")
    nth = step.get("nth")
    return locator.nth(int(nth)) if nth is not None else locator


def _state_snapshot(page: Any) -> dict[str, Any]:
    value = page.evaluate(
        r"""
        () => {
          const visible = (el) => {
            const r = el.getBoundingClientRect();
            const s = getComputedStyle(el);
            return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
          };
          const active = document.activeElement;
          const text = (document.body?.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 12000);
          const controls = Array.from(document.querySelectorAll('button,[role=button],[role=tab],input,select,textarea,details'))
            .filter(visible).slice(0, 120).map((el) => ({
              tag: el.tagName, id: el.id || '', role: el.getAttribute('role') || '',
              selected: el.getAttribute('aria-selected'), expanded: el.getAttribute('aria-expanded'),
              checked: 'checked' in el ? Boolean(el.checked) : null,
              value: 'value' in el ? String(el.value).slice(0, 120) : null,
              open: 'open' in el ? Boolean(el.open) : null,
              disabled: 'disabled' in el ? Boolean(el.disabled) : null,
            }));
          return {url: location.href, title: document.title || '', text, controls,
            active: active ? `${active.tagName}#${active.id || ''}` : ''};
        }
        """
    )
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    value["digest"] = hashlib.sha256(encoded).hexdigest()
    return value


def _signal_locator(page: Any, signal: Mapping[str, Any]) -> Any:
    return _locator(page, signal)


def _evaluate_signal(
    page: Any,
    signal: Mapping[str, Any],
    *,
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    responses: Sequence[Mapping[str, Any]],
    page_errors: Sequence[str],
    console_errors: Sequence[str],
    timeout_ms: int,
) -> dict[str, Any]:
    kind = str(signal["kind"])
    passed = False
    observed: Any = None
    expected: Any = signal.get("value")
    try:
        if kind == "state_changed":
            observed = before.get("digest") != after.get("digest")
            expected = True
            passed = bool(observed)
        elif kind == "url_contains":
            expected = str(signal.get("value", ""))
            observed = str(after.get("url", ""))
            passed = expected in observed
        elif kind in {"visible", "hidden"}:
            locator = _signal_locator(page, signal)
            observed = locator.is_visible(timeout=timeout_ms)
            expected = kind == "visible"
            passed = observed is expected
        elif kind == "text_contains":
            locator = _signal_locator(page, signal)
            observed = locator.inner_text(timeout=timeout_ms)
            expected = str(signal.get("value", ""))
            passed = expected in observed
        elif kind == "value_equals":
            locator = _signal_locator(page, signal)
            observed = locator.input_value(timeout=timeout_ms)
            expected = str(signal.get("value", ""))
            passed = observed == expected
        elif kind == "checked_equals":
            locator = _signal_locator(page, signal)
            observed = locator.is_checked(timeout=timeout_ms)
            expected = bool(signal.get("value", True))
            passed = observed == expected
        elif kind == "count_equals":
            locator = _signal_locator(page, signal)
            observed = locator.count()
            expected = int(signal.get("value", 1))
            passed = observed == expected
        elif kind == "attribute_equals":
            locator = _signal_locator(page, signal)
            attribute = str(signal.get("attribute"))
            observed = locator.get_attribute(attribute, timeout=timeout_ms)
            expected = str(signal.get("value", ""))
            passed = str(observed) == expected
        elif kind == "request_observed":
            url_contains = str(signal.get("urlContains", ""))
            method = str(signal.get("method", "")).upper()
            minimum = int(signal.get("statusMin", 200))
            maximum = int(signal.get("statusMax", 399))
            matches = [row for row in responses if url_contains in str(row.get("url", "")) and (not method or method == str(row.get("method", "")).upper())]
            observed = matches[-5:]
            expected = {"urlContains": url_contains, "method": method or "ANY", "status": [minimum, maximum]}
            passed = any(isinstance(row.get("status"), int) and minimum <= int(row["status"]) <= maximum for row in matches)
        elif kind == "no_page_error":
            observed = list(page_errors)
            expected = []
            passed = not page_errors
        elif kind == "no_console_error":
            observed = list(console_errors)
            expected = []
            passed = not console_errors
    except Exception as error:
        observed = f"{type(error).__name__}: {str(error)[:300]}"
        passed = False
    return {
        "kind": kind,
        "evidenceRole": signal.get("evidenceRole", "supporting"),
        "passed": passed,
        "expected": expected,
        "observed": observed,
    }


def _evaluate_outcome(
    page: Any,
    outcome: Mapping[str, Any],
    *,
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    responses: Sequence[Mapping[str, Any]],
    page_errors: Sequence[str],
    console_errors: Sequence[str],
    timeout_ms: int,
) -> dict[str, Any]:
    signals = [
        _evaluate_signal(
            page, signal, before=before, after=after, responses=responses,
            page_errors=page_errors, console_errors=console_errors, timeout_ms=timeout_ms,
        )
        for signal in outcome.get("signals", [])
    ]
    satisfied = sum(1 for item in signals if item["passed"])
    minimum = int(outcome.get("minimumSatisfied", len(signals)))
    result = "PASS" if satisfied >= minimum else "FAIL" if outcome.get("required", True) else "NOT_VERIFIED"
    return {
        "description": outcome.get("description"),
        "result": result,
        "required": bool(outcome.get("required", True)),
        "minimumSatisfied": minimum,
        "satisfied": satisfied,
        "signals": signals,
        "beforeDigest": before.get("digest"),
        "afterDigest": after.get("digest"),
        "userVisibleChanged": before.get("text") != after.get("text") or before.get("url") != after.get("url"),
    }


def execute_journey(
    page: Any,
    steps: Sequence[Mapping[str, Any]],
    *,
    output_dir: Any,
    timeout_ms: int = 10_000,
    screenshot_on_failure: bool = True,
) -> list[dict[str, Any]]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    for index, step in enumerate(steps):
        action = str(step["action"])
        action_id = str(step.get("id") or f"step-{index + 1}")
        label = str(step.get("name") or f"{action_id}-{action}")
        started = time.perf_counter()
        responses: list[dict[str, Any]] = []
        step_page_errors: list[str] = []
        step_console_errors: list[str] = []

        def on_response(response: Any) -> None:
            responses.append({"url": response.url.split("?", 1)[0], "method": response.request.method, "status": response.status})

        def on_page_error(error: Any) -> None:
            step_page_errors.append(str(error)[:500])

        def on_console(message: Any) -> None:
            if message.type == "error":
                step_console_errors.append(message.text[:500])

        page.on("response", on_response)
        page.on("pageerror", on_page_error)
        page.on("console", on_console)
        try:
            before = _state_snapshot(page)
            locator = _locator(page, step) if action not in {"goto", "assert_url", "screenshot", "back", "reload", "scroll"} else None
            if action == "goto":
                page.goto(str(step["url"]), wait_until=str(step.get("waitUntil", "domcontentloaded")), timeout=timeout_ms)
            elif action == "click": locator.click(timeout=timeout_ms)
            elif action == "dblclick": locator.dblclick(timeout=timeout_ms)
            elif action == "fill": locator.fill(str(step.get("value", "")), timeout=timeout_ms)
            elif action == "press": locator.press(str(step.get("key", "Enter")), timeout=timeout_ms)
            elif action == "select": locator.select_option(str(step.get("value", "")), timeout=timeout_ms)
            elif action == "check": locator.check(timeout=timeout_ms)
            elif action == "uncheck": locator.uncheck(timeout=timeout_ms)
            elif action == "wait_for": locator.wait_for(state=str(step.get("state", "visible")), timeout=timeout_ms)
            elif action == "assert_visible":
                if not locator.is_visible(timeout=timeout_ms): raise AssertionError("element is not visible")
            elif action == "assert_hidden":
                if locator.is_visible(timeout=timeout_ms): raise AssertionError("element is still visible")
            elif action == "assert_text":
                actual = locator.inner_text(timeout=timeout_ms)
                expected = str(step.get("contains", step.get("textValue", "")))
                if expected not in actual: raise AssertionError(f"text mismatch: expected substring {expected!r}, actual {actual[:160]!r}")
            elif action == "assert_value":
                actual = locator.input_value(timeout=timeout_ms)
                expected = str(step.get("expected", ""))
                if actual != expected: raise AssertionError(f"value mismatch: expected {expected!r}, actual {actual!r}")
            elif action == "assert_checked":
                expected = bool(step.get("expected", True)); actual = locator.is_checked(timeout=timeout_ms)
                if actual != expected: raise AssertionError(f"checked mismatch: expected {expected}, actual {actual}")
            elif action == "assert_count":
                expected = int(step.get("expected", 1)); actual = locator.count()
                if actual != expected: raise AssertionError(f"count mismatch: expected {expected}, actual {actual}")
            elif action == "assert_url":
                expected = str(step.get("contains", step.get("expected", "")))
                if expected not in page.url: raise AssertionError(f"url mismatch: {page.url!r}")
            elif action == "screenshot":
                path = output / str(step.get("filename") or f"journey-{index + 1}.png")
                page.screenshot(path=str(path), full_page=bool(step.get("fullPage", False)), animations="disabled")
            elif action == "back": page.go_back(wait_until="domcontentloaded", timeout=timeout_ms)
            elif action == "reload": page.reload(wait_until="domcontentloaded", timeout=timeout_ms)
            elif action == "scroll":
                if step.get("selector") or step.get("role") or step.get("label") or step.get("text"):
                    _locator(page, step).scroll_into_view_if_needed(timeout=timeout_ms)
                else:
                    page.evaluate("([x,y]) => window.scrollTo(x,y)", [int(step.get("x", 0)), int(step.get("y", 0))])
            elif action == "hover": locator.hover(timeout=timeout_ms)
            elif action == "focus": locator.focus(timeout=timeout_ms)

            outcome_proof = None
            if step.get("outcome"):
                page.wait_for_timeout(int(step["outcome"].get("settleMs", 350)))
                after = _state_snapshot(page)
                outcome_proof = _evaluate_outcome(
                    page, step["outcome"], before=before, after=after, responses=responses,
                    page_errors=step_page_errors, console_errors=step_console_errors, timeout_ms=timeout_ms,
                )
            elapsed = round((time.perf_counter() - started) * 1000)
            status = outcome_proof["result"] if outcome_proof else "PASS"
            results.append({
                "id": action_id, "step": label, "action": action, "risk": step.get("risk", "read-only"),
                "locator": step.get("locatorStrategy", "none"), "status": status,
                "durationMs": elapsed, "url": page.url.split("?", 1)[0],
                "reason": "outcome verified" if status == "PASS" and outcome_proof else f"{action} completed" if status == "PASS" else "expected outcome was not proved",
                "outcomeProof": outcome_proof,
                "runtimeEvidence": {"responses": responses[-20:], "pageErrors": step_page_errors, "consoleErrors": step_console_errors},
            })
            if status == "FAIL":
                if screenshot_on_failure:
                    failure_path = output / f"journey-failure-{index + 1}.png"
                    page.screenshot(path=str(failure_path), full_page=False, animations="disabled")
                    results[-1]["failureScreenshotRef"] = failure_path.name
                break
        except Exception as error:
            elapsed = round((time.perf_counter() - started) * 1000)
            failure_ref = None
            if screenshot_on_failure:
                failure_path = output / f"journey-failure-{index + 1}.png"
                try:
                    page.screenshot(path=str(failure_path), full_page=False, animations="disabled")
                    failure_ref = failure_path.name
                except Exception:
                    pass
            results.append({
                "id": action_id, "step": label, "action": action, "risk": step.get("risk", "read-only"),
                "locator": step.get("locatorStrategy", "none"), "status": "FAIL",
                "durationMs": elapsed, "url": page.url.split("?", 1)[0],
                "reason": f"{type(error).__name__}: {str(error)[:500]}", "failureScreenshotRef": failure_ref,
                "outcomeProof": None,
                "runtimeEvidence": {"responses": responses[-20:], "pageErrors": step_page_errors, "consoleErrors": step_console_errors},
            })
            break
        finally:
            try: page.remove_listener("response", on_response)
            except Exception: pass
            try: page.remove_listener("pageerror", on_page_error)
            except Exception: pass
            try: page.remove_listener("console", on_console)
            except Exception: pass
    return results


__all__ = ["JourneyPolicy", "validate_journey", "execute_journey"]
