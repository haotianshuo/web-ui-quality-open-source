from __future__ import annotations

from web_ui_quality.core import SourceFile, _collect_findings


def _findings(text: str, path: str = "src/context-explorer.tsx") -> list[dict]:
    return _collect_findings([SourceFile(path, text)], {}, "external_issue_4288")


def test_pointer_only_non_native_row_is_reported() -> None:
    findings = _findings(
        """
        <div className=\"tree-row cursor-pointer\" onClick={select}>
          <span>context</span>
        </div>
        """
    )

    assert [item["id"] for item in findings] == ["A11Y-POINTER-ONLY-INTERACTION"]
    assert findings[0]["severity"] == "P2"
    assert findings[0]["reasonCode"] == "NON_NATIVE_CLICK_WITHOUT_KEYBOARD_SEMANTICS"


def test_native_or_explicit_keyboard_contract_is_not_reported() -> None:
    text = """
    <button type=\"button\" onClick={select}>context</button>
    <div role=\"button\" tabIndex={0} onClick={select} onKeyDown={onKeyDown}>context</div>
    <li><button aria-label={name} onClick={select}>context</button></li>
    """

    assert not any(item["id"] == "A11Y-POINTER-ONLY-INTERACTION" for item in _findings(text))


def test_rule_is_scoped_to_jsx_like_sources() -> None:
    text = '<div onClick={select}>context</div>'

    assert not any(
        item["id"] == "A11Y-POINTER-ONLY-INTERACTION"
        for item in _findings(text, "src/notes.txt")
    )


def test_nested_keyboard_parent_guard_is_reported_in_arrowdown_context() -> None:
    findings = _findings(
        """
        class MegaMenu {
          get visibleItems() {
            const processedItem = this.activeItem();
            return processedItem && processedItem.key === this.focusedItemInfo().parentKey
              ? processedItem.items.reduce((items, col) => items.concat(col), [])
              : this.processedItems;
          }
          get processedItems() { return this._processedItems; }
          onArrowDownKey(event) { return this.visibleItems[event.key]; }
        }
        """,
        "src/app/components/megamenu/megamenu.ts",
    )

    nested = [item for item in findings if item["id"] == "A11Y-NESTED-KEYBOARD-TRAVERSAL-GUARD"]
    assert len(nested) == 1
    assert nested[0]["severity"] == "P2"
    assert nested[0]["reasonCode"] == "NESTED_MENU_PARENT_KEY_GUARD_CAN_FALL_BACK_TO_ROOT"


def test_nested_keyboard_parent_guard_after_fix_is_not_reported() -> None:
    text = """
    class MegaMenu {
      get visibleItems() {
        const processedItem = this.activeItem();
        return processedItem
          ? processedItem.items.reduce((items, col) => items.concat(col), [])
          : this.processedItems;
      }
      get processedItems() { return this._processedItems; }
      onArrowDownKey(event) { return this.visibleItems[event.key]; }
    }
    """

    assert not any(item["id"] == "A11Y-NESTED-KEYBOARD-TRAVERSAL-GUARD" for item in _findings(text, "src/app/components/megamenu/megamenu.ts"))


def test_similar_key_guard_without_arrowdown_context_is_not_reported() -> None:
    text = """
    class MenuState {
      get visibleItems() {
        const processedItem = this.activeItem();
        return processedItem && processedItem.key === this.focusedItemInfo().parentKey
          ? processedItem.items
          : this.processedItems;
      }
      get processedItems() { return this._processedItems; }
    }
    """

    assert not any(item["id"] == "A11Y-NESTED-KEYBOARD-TRAVERSAL-GUARD" for item in _findings(text, "src/menu-state.ts"))
