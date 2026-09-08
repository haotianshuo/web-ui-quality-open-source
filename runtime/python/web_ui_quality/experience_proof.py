"""Traceable UI understanding, interaction intelligence, and experience proof.

Serialized mappings remain candidates. Browser authority is accepted only
through the process-local TrustedUIBrowserEvidence receipt.
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

from .contracts import digest_json
from .trusted_evidence import (
    TrustedUIBrowserEvidence,
    browser_payload,
    require_browser_evidence,
)

_REQUIRED_VIEWPORTS = {1440, 768, 390}
_PRIORITY = {"must-fix": 0, "should-fix": 1, "candidate": 2}
_SEVERITY = {"UX1": 0, "UX2": 1, "UX3": 2}


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _rows(value: Any) -> list[dict[str, Any]]:
    return [dict(item) for item in value if isinstance(item, Mapping)] if isinstance(value, (list, tuple)) else []


def _text(value: Any) -> str:
    return str(value or "").strip()


def _source_ref(prefix: str, *parts: Any) -> str:
    suffix = ":".join(_text(item).replace(":", "-") for item in parts if _text(item))
    return f"{prefix}:{suffix}" if suffix else prefix


def _fact(fact_id: str, authority: str, source_ref: str, value: Any) -> dict[str, Any]:
    return {"id": fact_id, "authority": authority, "sourceRef": source_ref, "value": value}


def _entry(
    field: str,
    facts: Sequence[Mapping[str, Any]],
    inference: str,
    confidence: str,
    verification: Sequence[str] = (),
) -> dict[str, Any]:
    return {
        "field": field,
        "observedFacts": [dict(item) for item in facts],
        "inference": inference,
        "confidence": confidence,
        "verificationNeeded": list(verification),
    }


def trusted_experience_geometry(
    value: TrustedUIBrowserEvidence | None,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Extract after-page geometry from a process-local trusted receipt."""

    trusted = require_browser_evidence(value)
    if trusted is None:
        return {}, None
    payload = browser_payload(trusted)
    viewports: list[dict[str, Any]] = []
    elements: list[dict[str, Any]] = []
    visual: dict[str, Any] = {}
    for record in _rows(payload.get("records")):
        if _text(record.get("label")).casefold() != "after":
            continue
        if _text(record.get("status")).upper() not in {"PASS", "PASS_WITH_WARNINGS"}:
            continue
        geometry = _mapping(record.get("experienceGeometry"))
        viewport = _mapping(record.get("viewport"))
        viewport_id = str(viewport.get("width") or "")
        for row in _rows(geometry.get("viewports")):
            row.setdefault("id", viewport_id)
            row["evidenceRef"] = trusted.evidence_ref
            row["recordRef"] = _source_ref(trusted.evidence_ref, "after", viewport_id)
            viewports.append(row)
        visual_items = _rows(geometry.get("visualElements")) or _rows(_mapping(geometry.get("visual")).get("elements"))
        for item in visual_items:
            item.setdefault("viewport", viewport_id)
            item["evidenceRef"] = trusted.evidence_ref
            elements.append(item)
        if not visual:
            visual = _mapping(geometry.get("visual"))
    if not viewports:
        return {}, payload
    return {
        "schemaVersion": "3.1",
        "status": "MEASURED",
        "viewports": viewports,
        "visual": visual,
        "visualElements": elements,
        "evidenceTier": "browser-measured",
        "evidenceRef": trusted.evidence_ref,
        "evidenceDigest": trusted.evidence_digest,
        "claimBoundary": "Only the bound Browser run, target, role, state, and viewports are observed.",
    }, payload


def _transition_candidates(page_type: str) -> list[dict[str, Any]]:
    catalogs = {
        "crm": [
            ("apply-filter", "list-ready", "filter-applied", "Activate the intended filter", ["filter state is exposed", "result feedback is visible", "query remains available"], False),
            ("open-detail", "filter-applied", "detail-open", "Activate one result", ["selected record is exposed", "detail content matches selection", "filter remains active"], False),
            ("return-list", "detail-open", "list-restored", "Close detail or press Escape when supported", ["focus returns", "filter and selection remain", "list position remains"], True),
        ],
        "erp": [
            ("select-records", "table-ready", "bulk-selection", "Select one or more rows", ["selection count is visible", "bulk actions appear only after selection"], False),
            ("open-dialog", "bulk-selection", "dialog-open", "Open a scoped edit dialog", ["dialog is named", "focus enters dialog", "selection remains"], False),
            ("cancel-recover", "dialog-open", "table-restored", "Cancel or press Escape", ["dialog closes", "focus returns to trigger", "selection remains"], True),
        ],
        "mobile-workflow": [
            ("edit-result", "draft-ready", "draft-edited", "Change the inspection result", ["new value is visible", "draft remains safe"], False),
            ("sync-draft", "draft-edited", "sync-complete", "Activate sync", ["sync feedback names the result", "draft continuity is visible"], True),
        ],
    }
    rows = catalogs.get(page_type) or [
        ("complete-primary-task", "ready", "result", "Complete the primary task", ["result feedback is visible", "a safe next step is available"], False)
    ]
    return [
        {
            "id": item[0],
            "fromState": item[1],
            "toState": item[2],
            "action": item[3],
            "modality": "keyboard" if "Escape" in item[3] else "mouse-or-keyboard",
            "assertions": item[4],
            "recovery": item[5],
        }
        for item in rows
    ]


def _tool_boundaries(payload: Mapping[str, Any] | None) -> dict[str, str]:
    supplied = _mapping(payload.get("toolBoundaries")) if payload else {}
    return {
        "nativeTabEnterSpace": _text(supplied.get("nativeTabEnterSpace")) or "UNVERIFIED_AUTOMATION_SURFACE",
        "escapeAndFocusReturn": _text(supplied.get("escapeAndFocusReturn")) or "VERIFICATION_NEEDED",
        "screenReader": _text(supplied.get("screenReader")) or "UNVERIFIED",
    }


def _interaction_intelligence(page: Mapping[str, Any], payload: Mapping[str, Any] | None) -> dict[str, Any]:
    page_type = _text(_mapping(page.get("pageType")).get("id")) or "unclassified"
    task = _text(_mapping(page.get("primaryTask")).get("value"))
    trusted_steps = [
        item for item in _rows(payload.get("journey") if payload else None)
        if _text(item.get("fromState")) and _text(item.get("toState")) and _text(item.get("action"))
    ]
    boundaries = _tool_boundaries(payload)
    if trusted_steps:
        transitions: list[dict[str, Any]] = []
        state_ids: list[str] = []
        for index, item in enumerate(trusted_steps):
            before, after = _text(item.get("fromState")), _text(item.get("toState"))
            for state_id in (before, after):
                if state_id not in state_ids:
                    state_ids.append(state_id)
            context = [_text(value) for value in item.get("contextPreserved", []) if _text(value)] if isinstance(item.get("contextPreserved"), list) else []
            transitions.append({
                "id": _text(item.get("id")) or f"transition-{index + 1}",
                "from": before,
                "to": after,
                "event": {"action": _text(item.get("action")), "modality": _text(item.get("modality")) or "unknown"},
                "status": _text(item.get("status")).upper() or "NOT_VERIFIED",
                "feedback": _mapping(item.get("feedback")),
                "contextPreserved": context,
                "contextSwitch": bool(item.get("contextSwitch")),
                "recovery": bool(item.get("recovery")),
                "focusReturn": _text(item.get("focusReturn")) or None,
                "evidence": {
                    "authority": "browser-measured",
                    "sourceRef": _source_ref("trusted-browser", "journey", item.get("id") or index + 1),
                    "reason": _text(item.get("reason")),
                },
            })
        feedback_pass = all(
            row["feedback"].get("visible") is True and _text(row["feedback"].get("text"))
            for row in transitions
        )
        continuity_pass = all(bool(row["contextPreserved"]) for row in transitions)
        recoveries = [row for row in transitions if row["recovery"]]
        recovery_pass = bool(recoveries) and all(
            row["status"] == "PASS" and row["contextPreserved"] and row["focusReturn"]
            for row in recoveries
        )
        durations = [item.get("durationMs") for item in trusted_steps if isinstance(item.get("durationMs"), (int, float))]
        acceptance = []
        for row in transitions:
            assertions = [f"state becomes {row['to']}"]
            if _text(row["feedback"].get("text")):
                assertions.append("feedback: " + _text(row["feedback"].get("text")))
            if row["contextPreserved"]:
                assertions.append("preserve: " + ", ".join(row["contextPreserved"]))
            if row["focusReturn"]:
                assertions.append("focus returns to " + str(row["focusReturn"]))
            acceptance.append({
                "id": row["id"],
                "setup": f"reach {row['from']}",
                "action": row["event"]["action"],
                "assertions": assertions,
                "authority": "browser-measured",
            })
        flow = {
            "id": "trusted-critical-journey",
            "primaryTask": task,
            "states": [{"id": value, "authority": "browser-measured"} for value in state_ids],
            "transitions": transitions,
            "metrics": {
                "interactionCost": {
                    "status": "MEASURED",
                    "actionCount": len(transitions),
                    "weightedActions": len(transitions),
                    "taskTimeMs": sum(durations) if len(durations) == len(transitions) else None,
                    "taskTimeStatus": "MEASURED" if len(durations) == len(transitions) else "NOT_MEASURED",
                },
                "contextSwitches": {"status": "MEASURED", "count": sum(bool(row["contextSwitch"]) for row in transitions)},
                "stateContinuity": {"status": "PASS" if continuity_pass else "FAIL", "preservedTransitions": sum(bool(row["contextPreserved"]) for row in transitions), "totalTransitions": len(transitions)},
                "feedbackQuality": {"status": "PASS" if feedback_pass else "FAIL", "clearFeedbackTransitions": sum(row["feedback"].get("visible") is True and bool(_text(row["feedback"].get("text"))) for row in transitions), "totalTransitions": len(transitions)},
                "recoveryPath": {"status": "PASS" if recovery_pass else "NOT_VERIFIED", "verifiedTransitions": len(recoveries) if recovery_pass else 0},
            },
            "acceptanceSteps": acceptance,
        }
        return {
            "schemaVersion": "3.1",
            "status": "MEASURED",
            "taskFlows": [flow],
            "keyStates": state_ids,
            "toolBoundaries": boundaries,
            "claimBoundary": "Structural cost and continuity are measured; user task time stays unmeasured unless the trusted run supplies it.",
        }

    candidates = _transition_candidates(page_type)
    states: list[str] = []
    transitions = []
    for item in candidates:
        for state_id in (item["fromState"], item["toState"]):
            if state_id not in states:
                states.append(state_id)
        transitions.append({
            "id": item["id"],
            "from": item["fromState"],
            "to": item["toState"],
            "event": {"action": item["action"], "modality": item["modality"]},
            "status": "VERIFICATION_NEEDED",
            "feedback": {},
            "contextPreserved": [],
            "contextSwitch": None,
            "recovery": bool(item.get("recovery")),
            "focusReturn": None,
            "evidence": {"authority": "source-inferred", "sourceRef": _source_ref("page-pattern", page_type, item["id"])},
        })
    flow = {
        "id": f"{page_type}-candidate-flow",
        "primaryTask": task,
        "states": [{"id": value, "authority": "source-inferred"} for value in states],
        "transitions": transitions,
        "metrics": {
            "interactionCost": {"status": "NOT_MEASURED", "actionCount": len(transitions), "taskTimeMs": None},
            "contextSwitches": {"status": "NOT_MEASURED", "count": None},
            "stateContinuity": {"status": "NOT_VERIFIED"},
            "feedbackQuality": {"status": "NOT_VERIFIED"},
            "recoveryPath": {"status": "NOT_VERIFIED"},
        },
        "acceptanceSteps": [
            {"id": item["id"], "setup": f"reach {item['fromState']}", "action": item["action"], "assertions": list(item["assertions"]), "authority": "verification-plan"}
            for item in candidates
        ],
    }
    return {
        "schemaVersion": "3.1",
        "status": "CANDIDATE_ONLY",
        "taskFlows": [flow],
        "keyStates": states,
        "toolBoundaries": boundaries,
        "claimBoundary": "Source patterns define executable checks; no interaction passes without trusted Browser evidence.",
    }


def _focus_facts(
    visual: Mapping[str, Any],
    screenshot: Mapping[str, Any],
    position: str,
    trusted_ref: str | None,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    hierarchy = _mapping(_mapping(visual.get("model")).get("visualHierarchy"))
    rendered = _mapping(hierarchy.get("firstFocus" if position == "first" else "secondFocus"))
    screenshot_hierarchy = _mapping(screenshot.get("visualHierarchy"))
    screenshot_value = screenshot_hierarchy.get("firstGlance" if position == "first" else "secondGlance")
    facts: list[dict[str, Any]] = []
    selected: dict[str, Any] | None = None
    if rendered and trusted_ref:
        selected = {
            "selector": rendered.get("selector"),
            "text": rendered.get("text"),
            "role": rendered.get("role"),
            "score": rendered.get("score"),
        }
        facts.append(_fact(
            f"visual-focus-{position}-browser",
            "browser-measured",
            _source_ref(trusted_ref, "visual-focus", position, rendered.get("selector")),
            selected,
        ))
    if screenshot_value not in (None, ""):
        value = dict(screenshot_value) if isinstance(screenshot_value, Mapping) else {"text": screenshot_value}
        selected = selected or value
        facts.append(_fact(
            f"visual-focus-{position}-screenshot",
            "screenshot-overlay",
            _source_ref("screenshot-overlay", "visual-focus", position),
            value,
        ))
    return selected, facts


def _maturity_signals(diagnosis: Mapping[str, Any], interaction: Mapping[str, Any]) -> list[dict[str, Any]]:
    mappings = {
        "LAYOUT-FIXED-WIDTH": ("fixed-width-layout", "Large fixed width can make the product feel legacy and brittle."),
        "LAYOUT-ABSOLUTE-OVERUSE": ("coordinate-layout-debt", "Coordinate-heavy layout is fragile across content and zoom."),
        "VISUAL-COLOR-SYSTEM-FRAGMENTED": ("fragmented-color-system", "Color literals without semantic tokens weaken consistency."),
        "VISUAL-CTA-COMPETITION": ("competing-primary-actions", "Multiple primary actions weaken product hierarchy."),
        "VISUAL-TYPOGRAPHY-TOO-MANY-STYLES": ("fragmented-type-system", "Excess type roles weaken visual maturity."),
    }
    result: list[dict[str, Any]] = []
    for module_name in ("layoutIntelligence", "responsiveExperience", "visualIntelligence"):
        for item in _rows(_mapping(diagnosis.get(module_name)).get("findings")):
            code = _text(item.get("id"))
            if code not in mappings:
                continue
            signal, inference = mappings[code]
            result.append({
                "id": signal,
                "findingId": code,
                "observedFact": item.get("evidence"),
                "inference": inference,
                "confidence": item.get("confidence"),
                "authority": item.get("evidenceMode"),
                "verificationNeeded": list(item.get("verification") or []),
            })
    if interaction.get("status") != "MEASURED":
        result.append({
            "id": "interaction-proof-missing",
            "findingId": None,
            "observedFact": "No trusted critical journey was supplied.",
            "inference": "Interaction maturity cannot be confirmed from control presence.",
            "confidence": "high",
            "authority": "contract-boundary",
            "verificationNeeded": ["Run the executable critical journey and recovery path."],
        })
    return result


def _experience_model(
    diagnosis: Mapping[str, Any],
    *,
    context: Mapping[str, Any],
    screenshot: Mapping[str, Any],
    interaction: Mapping[str, Any],
    trusted_receipt: TrustedUIBrowserEvidence | None,
) -> dict[str, Any]:
    page = _mapping(diagnosis.get("pageUnderstanding"))
    visual = _mapping(diagnosis.get("visualIntelligence"))
    layout = _mapping(diagnosis.get("layoutIntelligence"))
    component = _mapping(diagnosis.get("componentIntelligence"))
    page_type = _mapping(page.get("pageType"))
    primary_task = _mapping(page.get("primaryTask"))
    trusted = require_browser_evidence(trusted_receipt)
    trusted_ref = trusted.evidence_ref if trusted else None
    ledger: list[dict[str, Any]] = []

    page_facts: list[dict[str, Any]] = []
    evidence = page_type.get("evidence") if isinstance(page_type.get("evidence"), list) else []
    for index, item in enumerate(evidence):
        if isinstance(item, Mapping):
            page_facts.append(_fact(
                f"page-type-source-{index + 1}",
                _text(item.get("tier")) or "source-inferred",
                _source_ref("page-understanding", "page-type", index + 1),
                item.get("fact"),
            ))
    screenshot_page = _mapping(screenshot.get("pageType"))
    if _text(screenshot_page.get("id")):
        authority = "screenshot-overlay" if screenshot.get("evidenceMode") == "screenshot-plus-host-overlay" else "screenshot-inferred"
        page_facts.append(_fact(
            "page-type-screenshot",
            authority,
            _source_ref("screenshot", "page-type"),
            {"id": screenshot_page.get("id"), "confidence": screenshot_page.get("confidence")},
        ))
    ledger.append(_entry(
        "pageType",
        page_facts,
        _text(page_type.get("id")) or "unclassified",
        _text(page.get("confidence")) or "low",
        [] if trusted else ["Confirm the visible page and role in Browser."],
    ))

    task_facts = []
    if primary_task.get("value"):
        task_facts.append(_fact(
            "primary-task",
            _text(primary_task.get("provenance")) or "unknown",
            _source_ref("experience-context", "primary-task"),
            primary_task.get("value"),
        ))
    ledger.append(_entry(
        "primaryTask",
        task_facts,
        _text(primary_task.get("value")) or "unknown",
        "high" if primary_task.get("confirmed") else "medium" if primary_task.get("value") else "low",
        [] if primary_task.get("confirmed") else ["Confirm the task with business/user evidence."],
    ))

    first_focus, first_facts = _focus_facts(visual, screenshot, "first", trusted_ref)
    second_focus, second_facts = _focus_facts(visual, screenshot, "second", trusted_ref)
    ledger.append(_entry(
        "visualFocus.first",
        first_facts,
        _text((first_focus or {}).get("text")) or "unknown",
        "high" if trusted_ref and len(first_facts) >= 2 else "medium" if first_facts else "low",
        [] if trusted_ref else ["Capture the same state and viewport in Browser."],
    ))
    ledger.append(_entry(
        "visualFocus.second",
        second_facts,
        _text((second_focus or {}).get("text")) or "unknown",
        "high" if trusted_ref and len(second_facts) >= 2 else "medium" if second_facts else "low",
        [] if trusted_ref else ["Capture the same state and viewport in Browser."],
    ))

    layout_rows = [
        {
            "viewport": row.get("id"),
            "width": row.get("width"),
            "status": row.get("status"),
            "issues": list(row.get("issues") or []),
        }
        for row in _rows(layout.get("viewports"))
    ]
    if trusted_ref:
        layout_facts = [
            _fact(
                f"layout-{row.get('viewport')}",
                "browser-measured",
                _source_ref(trusted_ref, "layout", row.get("viewport")),
                row,
            )
            for row in layout_rows
        ]
    else:
        layout_facts = [_fact(
            "layout-source-model",
            "source-static",
            _source_ref("layout-intelligence", "model"),
            layout.get("model"),
        )]
    ledger.append(_entry(
        "layoutHierarchy",
        layout_facts,
        "responsive rendered hierarchy" if trusted_ref else "source layout candidate",
        "high" if trusted_ref else "medium",
        [] if trusted_ref else ["Measure DOM geometry at 1440, 768, and 390."],
    ))

    density = _text(context.get("informationDensity"))
    if not density:
        count = sum(int(item.get("count") or 0) for item in _rows(page.get("componentInventory")))
        density = "high" if count >= 12 or _text(page_type.get("id")) in {"crm", "erp"} else "medium" if count >= 5 else "low"
    ledger.append(_entry(
        "density",
        [_fact(
            "density-context",
            "explicit-business-context" if context.get("informationDensity") else "source-inferred",
            _source_ref("experience-context", "information-density"),
            density,
        )],
        density,
        "high" if context.get("informationDensity") else "medium",
        ["Confirm density with representative data volume."] if not context.get("informationDensity") else [],
    ))

    framework = _text(component.get("framework")) or "unknown"
    ledger.append(_entry(
        "componentSystem",
        [_fact(
            "component-inventory",
            "source-static",
            _source_ref("page-understanding", "component-inventory"),
            page.get("componentInventory"),
        )],
        framework,
        "high" if framework != "unknown" else "low",
        [] if framework != "unknown" else ["Resolve framework/component-system ambiguity."],
    ))

    patterns = _rows(page.get("interactionPatterns"))
    ledger.append(_entry(
        "interactionPatterns",
        [
            _fact(
                f"interaction-pattern-{index + 1}",
                _text(item.get("evidenceTier")) or "source-inferred",
                _source_ref("page-understanding", "interaction-pattern", item.get("id") or index + 1),
                item,
            )
            for index, item in enumerate(patterns)
        ],
        ", ".join(_text(item.get("id")) for item in patterns) or "unknown",
        "medium" if patterns else "low",
        ["Execute the task flow; control presence does not prove behavior."] if interaction.get("status") != "MEASURED" else [],
    ))

    states = list(interaction.get("keyStates") or [])
    state_authority = "browser-measured" if interaction.get("status") == "MEASURED" else "source-inferred"
    ledger.append(_entry(
        "keyStates",
        [_fact(f"state-{state}", state_authority, _source_ref("interaction-intelligence", state), state) for state in states],
        ", ".join(states) or "unknown",
        "high" if interaction.get("status") == "MEASURED" else "medium",
        [] if interaction.get("status") == "MEASURED" else ["Verify first-time, repeat, and recovery states."],
    ))

    maturity = _maturity_signals(diagnosis, interaction)
    ledger.append(_entry(
        "maturitySignals",
        [
            _fact(
                f"maturity-{index + 1}",
                _text(item.get("authority")) or "source-risk",
                _source_ref("diagnosis", item.get("findingId") or item.get("id")),
                {"observedFact": item.get("observedFact"), "signal": item.get("id")},
            )
            for index, item in enumerate(maturity)
        ],
        "; ".join(_text(item.get("inference")) for item in maturity) or "no material signal detected",
        "high" if any(item.get("authority") == "rendered-observation" for item in maturity) else "medium",
        [step for item in maturity for step in item.get("verificationNeeded", [])][:12],
    ))

    model = {
        "schemaVersion": "3.1",
        "status": "OBSERVED_WITH_INFERENCES" if trusted_ref and page.get("status") == "CLASSIFIED" else "CANDIDATE_MODEL" if page.get("status") == "CLASSIFIED" else "DISCOVERY_REQUIRED",
        "authority": "TRUSTED_BROWSER_PLUS_CANDIDATES" if trusted_ref else "CANDIDATE_ONLY",
        "pageType": {"value": _text(page_type.get("id")) or "unclassified", "confidence": page.get("confidence")},
        "primaryTask": {"value": primary_task.get("value"), "confirmed": bool(primary_task.get("confirmed"))},
        "visualFocus": {"first": first_focus, "second": second_focus},
        "layoutHierarchy": {"structure": page.get("structure"), "viewports": layout_rows},
        "density": {"value": density},
        "componentSystem": {
            "framework": framework,
            "inventory": page.get("componentInventory"),
            "status": component.get("status"),
        },
        "interactionPatterns": patterns,
        "keyStates": states,
        "maturitySignals": maturity,
        "evidenceLedger": ledger,
        "claimBoundary": "Observed facts are source-specific. Inferences remain labeled; screenshots and serialized fields cannot grant Browser authority.",
    }
    model["digest"] = digest_json(model)
    return model


def _group_for(category: str) -> str:
    value = category.casefold()
    if value in {"layout", "responsive"}:
        return "responsive-layout"
    if value in {"hierarchy", "typography", "color", "spacing", "visual-system", "visual"}:
        return "visual-hierarchy"
    if value in {"interaction", "accessibility", "layering"}:
        return "interaction-recovery"
    if value == "component":
        return "component-system"
    return "task-clarity"


def _code_locations(sources: Sequence[Mapping[str, Any]], group: str) -> list[dict[str, str]]:
    preferences = {
        "responsive-layout": (".css", ".scss", ".less", ".html", ".vue", ".svelte", ".jsx", ".tsx"),
        "visual-hierarchy": (".css", ".scss", ".less", ".html", ".vue", ".svelte", ".jsx", ".tsx"),
        "interaction-recovery": (".js", ".ts", ".jsx", ".tsx", ".vue", ".svelte", ".html"),
        "component-system": (".json", ".toml", ".vue", ".jsx", ".tsx", ".svelte", ".html"),
        "task-clarity": (".html", ".vue", ".svelte", ".jsx", ".tsx", ".js", ".ts"),
    }
    rows = [
        {
            "path": _text(item.get("path")),
            "reason": f"owns {group} source or behavior",
            "authority": "source-location-candidate",
        }
        for item in sources
        if _text(item.get("path")) and Path(_text(item.get("path"))).suffix.casefold() in preferences[group]
    ]
    if not rows:
        rows = [
            {
                "path": _text(item.get("path")),
                "reason": "nearest bounded source",
                "authority": "source-location-candidate",
            }
            for item in sources
            if _text(item.get("path"))
        ]
    return rows[:4]


def _recommendation_compilation(
    diagnosis: Mapping[str, Any],
    sources: Sequence[Mapping[str, Any]],
    interaction: Mapping[str, Any],
) -> dict[str, Any]:
    recommendations = _rows(diagnosis.get("recommendations"))
    recommendations.sort(key=lambda item: (
        _PRIORITY.get(_text(item.get("priority")), 9),
        _SEVERITY.get(_text(item.get("severity")), 9),
        _text(item.get("id")),
    ))
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    order: list[str] = []
    for item in recommendations:
        group = _group_for(_text(item.get("category")))
        if group not in grouped:
            order.append(group)
        if len(grouped[group]) < 4:
            grouped[group].append(item)
    if not order:
        order = ["task-clarity"]
        grouped["task-clarity"] = [{
            "id": "EXPERIENCE-PROOF-DISCOVERY",
            "priority": "candidate",
            "category": "interaction",
            "title": "Ground and verify the primary task",
            "recommendation": "Confirm the primary task and execute one critical journey.",
            "verificationNeeded": ["Business task is confirmed", "Critical journey is executed"],
        }]

    page = _mapping(diagnosis.get("pageUnderstanding"))
    components = [
        _text(item.get("type"))
        for item in _rows(page.get("componentInventory"))
        if _text(item.get("type"))
    ][:6]
    key_states = list(interaction.get("keyStates") or [])
    titles = {
        "responsive-layout": "Recompose the task across responsive layouts",
        "visual-hierarchy": "Clarify visual focus and token hierarchy",
        "interaction-recovery": "Make the critical journey continuous and recoverable",
        "component-system": "Map the repair to compatible project components",
        "task-clarity": "Ground the primary task and next action",
    }
    options = []
    for index, group in enumerate(order[:3]):
        items = grouped[group]
        addresses = [_text(item.get("id")) for item in items if _text(item.get("id"))]
        gates: list[str] = []
        for item in items:
            values = item.get("verificationNeeded") if isinstance(item.get("verificationNeeded"), list) else []
            for gate in values:
                if _text(gate) and _text(gate) not in gates:
                    gates.append(_text(gate))
        for gate in ("1440 layout/state verified", "768 layout/state verified", "390 layout/state verified"):
            if gate not in gates:
                gates.append(gate)
        if interaction.get("taskFlows"):
            gates.append("Critical journey acceptance steps pass with stated keyboard boundaries.")
        priorities = {_text(item.get("priority")) for item in items}
        risk = "high" if "must-fix" in priorities and len(items) >= 3 else "medium" if "must-fix" in priorities or len(items) >= 2 else "low"
        recommendation_text = [_text(item.get("recommendation")) for item in items if _text(item.get("recommendation"))]
        options.append({
            "id": f"EXP-PROOF-OPTION-{index + 1}",
            "title": titles[group],
            "whyNow": _text(items[0].get("userProblem")) or _text(items[0].get("title")),
            "addresses": addresses,
            "authority": "IMPLEMENTATION_CANDIDATE",
            "evidenceRefs": [_source_ref("recommendation", item_id) for item_id in addresses],
            "changes": {
                "components": components if group in {"component-system", "interaction-recovery"} else components[:3],
                "tokens": ["spacing", "type", "color", "focus"] if group in {"visual-hierarchy", "responsive-layout"} else ["state", "focus"],
                "layout": recommendation_text if group in {"responsive-layout", "visual-hierarchy", "task-clarity"} else [],
                "interactionStates": key_states if group in {"interaction-recovery", "component-system", "task-clarity"} else key_states[:4],
            },
            "codeLocations": _code_locations(sources, group),
            "migrationRisk": {
                "level": risk,
                "risks": [
                    "Confirm CSS/component ownership before editing.",
                    "Do not change business rules, permissions, data contracts, or framework implicitly.",
                ],
                "rollback": "Keep the current route and behavior; revert only the scoped owning component.",
                "automaticWriteAuthorized": False,
            },
            "acceptanceGates": gates[:16],
        })
    result = {
        "schemaVersion": "3.1",
        "status": "OPTIONS_READY" if options else "DISCOVERY_REQUIRED",
        "options": options,
        "selectionRule": "Compile only the highest-impact evidence into at most three coherent implementation candidates.",
        "claimBoundary": "Options identify candidate code locations and gates; they authorize no installation, migration, project write, or release.",
    }
    result["digest"] = digest_json(result)
    return result


def _visual_proof(trusted_receipt: TrustedUIBrowserEvidence | None) -> dict[str, Any]:
    trusted = require_browser_evidence(trusted_receipt)
    if trusted is None:
        result = {
            "schemaVersion": "3.1",
            "status": "PLANNED_NOT_CAPTURED",
            "authority": "CANDIDATE_ONLY",
            "coverage": {"viewports": [], "threeViewportPairs": False, "equalConditionPairs": False},
            "artifacts": [],
            "afterQuality": {
                "consoleErrors": None,
                "pageErrors": None,
                "requestFailures": None,
                "horizontalOverflowViewports": None,
            },
            "expertReview": [],
            "toolBoundaries": _tool_boundaries(None),
            "requiredEvidence": [
                "fresh Before/After screenshots at 1440, 768, and 390",
                "DOM snapshot and computed geometry for each run",
                "console, page error, request failure, and overflow evidence",
                "critical interaction states and expert review",
            ],
            "claimBoundary": "A proof plan is not Browser proof.",
        }
        result["digest"] = digest_json(result)
        return result

    payload = browser_payload(trusted)
    usable = [
        item for item in _rows(payload.get("records"))
        if _text(item.get("label")).casefold() in {"before", "after"}
        and isinstance(item.get("viewport"), Mapping)
    ]
    widths = sorted({
        int(_mapping(item.get("viewport")).get("width"))
        for item in usable
        if isinstance(_mapping(item.get("viewport")).get("width"), (int, float))
    })
    pairs = {
        width: {
            _text(item.get("label")).casefold()
            for item in usable
            if int(_mapping(item.get("viewport")).get("width") or 0) == width
        }
        for width in widths
    }
    three_pairs = _REQUIRED_VIEWPORTS.issubset(widths) and all(
        {"before", "after"}.issubset(pairs.get(width, set()))
        for width in _REQUIRED_VIEWPORTS
    )
    equal_pairs = three_pairs and all(
        len({
            (
                int(_mapping(item.get("viewport")).get("width") or 0),
                int(_mapping(item.get("viewport")).get("height") or 0),
            )
            for item in usable
            if int(_mapping(item.get("viewport")).get("width") or 0) == width
        }) == 1
        for width in _REQUIRED_VIEWPORTS
    )
    artifacts = []
    artifact_complete = True
    for item in usable:
        viewport = _mapping(item.get("viewport"))
        geometry = _mapping(item.get("experienceGeometry"))
        row = {
            "variant": _text(item.get("label")).casefold(),
            "viewport": {"width": viewport.get("width"), "height": viewport.get("height")},
            "screenshotRef": item.get("screenshotRef"),
            "screenshotSha256": item.get("screenshotSha256"),
            "domRef": item.get("domRef"),
            "geometryRef": item.get("geometryRef"),
            "console": list(item.get("console") or []),
            "pageErrors": list(item.get("pageErrors") or []),
            "requestFailures": list(item.get("requestFailures") or []),
            "horizontalOverflow": bool(item.get("horizontalOverflow")),
            "geometryStatus": geometry.get("status"),
            "authority": "browser-measured",
            "sourceRef": _source_ref(trusted.evidence_ref, item.get("label"), viewport.get("width")),
        }
        artifacts.append(row)
        if not row["screenshotRef"] or not row["domRef"] or not row["geometryRef"] or not geometry:
            artifact_complete = False

    after = [item for item in artifacts if item["variant"] == "after"]
    console_errors = sum(len(item["console"]) for item in after)
    page_errors = sum(len(item["pageErrors"]) for item in after)
    request_failures = sum(len(item["requestFailures"]) for item in after)
    overflow = sorted(
        int(_mapping(item.get("viewport")).get("width") or 0)
        for item in usable
        if _text(item.get("label")).casefold() == "after" and item.get("horizontalOverflow")
    )
    boundaries = _tool_boundaries(payload)
    boundary_open = any(
        value.startswith("UNVERIFIED") or value == "VERIFICATION_NEEDED"
        for value in boundaries.values()
    )
    runtime_fail = (
        _text(payload.get("status")).upper() == "FAIL"
        or console_errors > 0
        or page_errors > 0
        or request_failures > 0
        or bool(overflow)
    )
    if not three_pairs or not equal_pairs or not artifact_complete:
        status = "INCOMPLETE"
    elif runtime_fail:
        status = "FAIL"
    elif boundary_open:
        status = "PASS_WITH_TOOL_BOUNDARIES"
    else:
        status = "PASS"
    result = {
        "schemaVersion": "3.1",
        "status": status,
        "authority": "TRUSTED_BROWSER_EVIDENCE",
        "evidenceRef": trusted.evidence_ref,
        "evidenceDigest": trusted.evidence_digest,
        "coverage": {
            "viewports": widths,
            "threeViewportPairs": three_pairs,
            "equalConditionPairs": equal_pairs,
        },
        "artifacts": artifacts,
        "afterQuality": {
            "consoleErrors": console_errors,
            "pageErrors": page_errors,
            "requestFailures": request_failures,
            "horizontalOverflowViewports": overflow,
        },
        "expertReview": _rows(payload.get("step10")),
        "toolBoundaries": boundaries,
        "requiredEvidence": [],
        "claimBoundary": "Browser proof covers only the bound URLs, states, data, role, environment, and run; it proves no conversion or preference outcome.",
    }
    result["digest"] = digest_json(result)
    return result


def build_experience_proof(
    diagnosis: Mapping[str, Any],
    sources: Sequence[Mapping[str, Any]],
    *,
    experience_context: Mapping[str, Any] | None = None,
    screenshot_model: Mapping[str, Any] | None = None,
    trusted_browser_evidence: TrustedUIBrowserEvidence | None = None,
    untrusted_observed_supplied: bool = False,
) -> dict[str, Any]:
    """Build the UI-understanding → interaction → recommendation → proof loop."""

    context = _mapping(experience_context)
    screenshot = _mapping(screenshot_model)
    trusted = require_browser_evidence(trusted_browser_evidence)
    payload = browser_payload(trusted) if trusted else None
    interaction = _interaction_intelligence(
        _mapping(diagnosis.get("pageUnderstanding")),
        payload,
    )
    model = _experience_model(
        diagnosis,
        context=context,
        screenshot=screenshot,
        interaction=interaction,
        trusted_receipt=trusted_browser_evidence,
    )
    compilation = _recommendation_compilation(diagnosis, sources, interaction)
    visual_proof = _visual_proof(trusted_browser_evidence)
    result = {
        "schemaVersion": "3.1",
        "status": (
            "PROOF_READY"
            if visual_proof["status"] in {"PASS", "PASS_WITH_TOOL_BOUNDARIES"}
            else "IMPLEMENTATION_CANDIDATE"
            if model["status"] != "DISCOVERY_REQUIRED"
            else "DISCOVERY_REQUIRED"
        ),
        "experienceModel": model,
        "interactionIntelligence": interaction,
        "recommendationCompilation": compilation,
        "visualProof": visual_proof,
        "evidenceBoundary": {
            "untrustedObservedInputDiscarded": bool(untrusted_observed_supplied),
            "browserAuthorityRequiresProcessLocalReceipt": True,
            "screenshotIsNotOcr": True,
            "userOutcomeMetricsMeasured": False,
        },
        "claimBoundary": "This sidecar never turns serialized fields, screenshots, or source heuristics into Browser authority or user-outcome claims.",
    }
    result["experienceProofDigest"] = digest_json(result)
    return result


__all__ = ["build_experience_proof", "trusted_experience_geometry"]
