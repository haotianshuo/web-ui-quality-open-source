from __future__ import annotations

from web_ui_quality.core import SourceFile, _collect_findings


RULE_ID = "A11Y-DND-KEYBOARD-SCOPE"


BEFORE = """
export function SessionRow() {
  return (
    <SidebarRowShell
      actions={<div data-row-actions />}
      onPointerDown={event => startSessionDrag(event)}
    >
      <SidebarRowBody />
    </SidebarRowShell>
  );
}
"""


AFTER = BEFORE.replace(
    "      onPointerDown={event => startSessionDrag(event)}",
    "      {...dragHandleProps}\n      onPointerDown={event => startSessionDrag(event)}",
)


def _findings(text: str, path: str = "apps/desktop/src/app/chat/sidebar/session-row.tsx") -> list[dict]:
    return [
        item
        for item in _collect_findings([SourceFile(path, text)], {}, "external_hermes_82373")
        if item["id"] == RULE_ID
    ]


def test_hermes_drag_title_change_before_has_no_row_shell_keyboard_spread() -> None:
    assert _findings(BEFORE) == []


def test_hermes_merged_drag_title_change_reports_full_listener_on_shell() -> None:
    findings = _findings(AFTER)

    assert len(findings) == 1
    assert findings[0]["severity"] == "P2"
    assert findings[0]["reasonCode"] == "DND_KEYBOARD_LISTENERS_SPREAD_TO_ROW_SHELL"
    assert findings[0]["location"]["selector"] == "SidebarRowShell > dragHandleProps"


def test_hermes_project_row_family_is_checked() -> None:
    findings = _findings(AFTER, "apps/desktop/src/app/chat/sidebar/projects/overview-row.tsx")

    assert len(findings) == 1
    assert findings[0]["id"] == RULE_ID


def test_pointer_only_shell_contract_is_not_reported() -> None:
    pointer_only = BEFORE.replace(
        "      onPointerDown={event => startSessionDrag(event)}",
        "      onPointerDown={event => startSessionDrag(event)}\n      // full keyboard props stay on SidebarRowGrab",
    )

    assert _findings(pointer_only) == []


def test_unrelated_row_shape_and_unsupported_suffix_are_not_inferred() -> None:
    unrelated = AFTER.replace("SidebarRowShell", "OtherRowShell")

    assert _findings(unrelated) == []
    assert _findings(AFTER, "fixtures/session-row.txt") == []
