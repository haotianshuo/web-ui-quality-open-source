from __future__ import annotations

from web_ui_quality.core import SourceFile, _collect_findings


RULE_ID = "A11Y-MENU-DELAYED-ITEM-FOCUS"


BEFORE = """
export class MenuTriggerPattern<V> {
  readonly pendingFocus = signal<'first' | 'last' | undefined>(undefined);

  pendingFocusEffect(): void {
    const menu = this.inputs.menu();
    const intent = this.pendingFocus();
    if (menu && intent) {
      if (intent === 'first') {
        menu.first();
      } else if (intent === 'last') {
        menu.last();
      }
      this.pendingFocus.set(undefined);
    }
  }

  /** Handles keyboard events for the menu trigger. */
  onKeydown(event: KeyboardEvent) {
    this.keydownManager().handle(event);
  }
}
"""


AFTER = BEFORE.replace(
    "    const intent = this.pendingFocus();\n    if (menu && intent) {",
    "    const intent = this.pendingFocus();\n    const items = menu?.items();\n    if (menu && intent && items?.length) {",
).replace(
    "export class MenuTriggerPattern<V> {",
    "export class MenuPattern<V> {\n  readonly items = () => this.inputs.items();\n}\n\nexport class MenuTriggerPattern<V> {",
)


def _findings(text: str, path: str = "src/aria/private/menu/menu.ts") -> list[dict]:
    return [
        item
        for item in _collect_findings([SourceFile(path, text)], {}, "external_angular_33743")
        if item["id"] == RULE_ID
    ]


def test_angular_menu_before_has_delayed_item_focus_gap() -> None:
    findings = _findings(BEFORE)

    assert len(findings) == 1
    assert findings[0]["severity"] == "P2"
    assert findings[0]["reasonCode"] == "DELAYED_MENU_ITEMS_PREVENT_INITIAL_FOCUS"
    assert findings[0]["location"]["selector"] == "MenuTriggerPattern > pendingFocusEffect"


def test_angular_menu_merged_after_waits_for_items() -> None:
    assert _findings(AFTER) == []


def test_unrelated_trigger_class_is_not_inferred_as_angular_aria_menu() -> None:
    assert _findings(BEFORE.replace("MenuTriggerPattern", "OtherTriggerPattern")) == []


def test_existing_item_availability_guard_is_not_reported() -> None:
    text = BEFORE.replace(
        "    const intent = this.pendingFocus();\n    if (menu && intent) {",
        "    const intent = this.pendingFocus();\n    const items = menu?.items();\n    if (menu && intent && items?.length) {",
    )

    assert _findings(text) == []


def test_unsupported_source_suffix_is_not_scanned() -> None:
    assert _findings(BEFORE, "fixtures/menu.txt") == []
