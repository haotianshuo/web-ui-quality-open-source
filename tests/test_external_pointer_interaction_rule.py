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


def test_focusable_descendant_menu_key_interceptor_is_reported_before_fix() -> None:
    text = """
    const SELECTION_KEYS = ['Enter', ' '];
    const MenuItem = () => (
      <MenuItemImpl onKeyDown={composeEventHandlers(props.onKeyDown, (event) => {
        if (SELECTION_KEYS.includes(event.key)) {
          event.currentTarget.click();
          event.preventDefault();
        }
      })} />
    );
    """

    findings = _findings(text, "packages/react/menu/src/menu.tsx")
    matches = [item for item in findings if item["id"] == "A11Y-FOCUSABLE-DESCENDANT-KEY-INTERCEPTION"]
    assert len(matches) == 1
    assert matches[0]["severity"] == "P2"
    assert matches[0]["reasonCode"] == "MENU_KEY_HANDLER_LACKS_EVENT_ORIGIN_GUARD"


def test_focusable_descendant_menu_key_origin_guard_after_fix_is_not_reported() -> None:
    text = """
    const SELECTION_KEYS = ['Enter', ' '];
    const MenuItem = () => (
      <MenuItemImpl onKeyDown={composeEventHandlers(props.onKeyDown, (event) => {
        if (disabled || event.target !== event.currentTarget) {
          return;
        }
        if (SELECTION_KEYS.includes(event.key)) {
          event.currentTarget.click();
          event.preventDefault();
        }
      })} />
    );
    """

    assert not any(
        item["id"] == "A11Y-FOCUSABLE-DESCENDANT-KEY-INTERCEPTION"
        for item in _findings(text, "packages/react/menu/src/menu.tsx")
    )


def test_focusable_descendant_submenu_trigger_interceptor_is_reported_and_guarded() -> None:
    before = """
    const SUB_OPEN_KEYS = { ltr: ['Enter', 'ArrowRight'] };
    <MenuItemImpl onKeyDown={composeEventHandlers(props.onKeyDown, (event) => {
      if (SUB_OPEN_KEYS[rootContext.dir].includes(event.key)) {
        context.onOpenChange(true);
      }
    })} />
    """
    after = before.replace(
        "if (SUB_OPEN_KEYS",
        "if (event.target !== event.currentTarget) return;\n      if (SUB_OPEN_KEYS",
    )

    before_matches = [
        item
        for item in _findings(before, "packages/react/menu/src/menu.tsx")
        if item["id"] == "A11Y-FOCUSABLE-DESCENDANT-KEY-INTERCEPTION"
    ]
    assert len(before_matches) == 1
    assert not any(
        item["id"] == "A11Y-FOCUSABLE-DESCENDANT-KEY-INTERCEPTION"
        for item in _findings(after, "packages/react/menu/src/menu.tsx")
    )


def test_unrelated_keydown_handler_is_not_reported_as_menu_interceptor() -> None:
    text = """
    <div onKeyDown={composeEventHandlers(props.onKeyDown, (event) => {
      if (event.key === 'Enter') console.log(event.currentTarget);
    })} />
    """

    assert not any(
        item["id"] == "A11Y-FOCUSABLE-DESCENDANT-KEY-INTERCEPTION"
        for item in _findings(text, "src/unrelated.tsx")
    )
