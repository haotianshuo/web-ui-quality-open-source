from __future__ import annotations

from web_ui_quality.core import SourceFile, _collect_findings


RULE_ID = "LAYOUT-FLEX-ITEM-MIN-WIDTH"


def _findings(text: str, path: str = "src/Chat.svelte") -> list[dict]:
    return [
        item
        for item in _collect_findings([SourceFile(path, text)], {}, "external_openwebui_28500")
        if item["id"] == RULE_ID
    ]


def test_full_width_flex_column_without_min_width_guard_is_reported() -> None:
    findings = _findings(
        """
        <div class=\"w-full max-w-full flex flex-col\" id={chatContainerId}>
          chat
        </div>
        """
    )

    assert len(findings) == 1
    assert findings[0]["severity"] == "P2"
    assert findings[0]["reasonCode"] == "FLEX_ITEM_MIN_WIDTH_AUTO_CAN_PUSH_SIBLING"
    assert findings[0]["location"]["line"] == 2


def test_openwebui_after_fix_with_min_w_0_is_clean() -> None:
    findings = _findings(
        """
        <div class=\"w-full max-w-full min-w-0 flex flex-col\" id={chatContainerId}>
          chat
        </div>
        """
    )

    assert findings == []


def test_jsx_class_name_is_supported() -> None:
    findings = _findings(
        """
        <section id="chat-container" className='w-full max-w-full flex flex-col' />
        """,
        "src/Chat.tsx",
    )

    assert len(findings) == 1
    assert findings[0]["location"]["file"] == "src/Chat.tsx"


def test_non_flex_or_non_full_width_layout_is_not_reported() -> None:
    text = """
    <div id=\"chat-container\" class=\"w-full max-w-full block flex-col\">not a flex item</div>
    <div id=\"chat-container\" class=\"w-full max-w-md flex flex-col\">bounded layout</div>
    <div id=\"chat-container\" class=\"w-full max-w-full flex flex-row\">row layout</div>
    """

    assert _findings(text) == []


def test_similar_utility_names_do_not_trigger_the_candidate() -> None:
    text = """
    <div id=\"chat-container\" class=\"w-full max-w-full flex-colors flex-col\">not the flex utility</div>
    <div id=\"chat-container\" class=\"w-full max-w-full flex flex-column\">not the flex-col utility</div>
    """

    assert _findings(text) == []


def test_min_w_full_is_not_a_min_w_0_guard() -> None:
    findings = _findings(
        """
        <div id=\"chat-container\" class=\"w-full max-w-full min-w-full flex flex-col\">content</div>
        """
    )

    assert len(findings) == 1


def test_non_supported_path_is_left_for_runtime_review() -> None:
    text = '<div class="w-full max-w-full flex flex-col">content</div>'

    assert _findings(text, "fixtures/notes.txt") == []


def test_dynamic_class_expression_without_static_contract_is_not_inferred() -> None:
    text = """
    <div class={layoutClasses}>content</div>
    """

    assert _findings(text) == []
