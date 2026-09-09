from __future__ import annotations

from web_ui_quality.core import EvidenceHtmlParser, SourceFile, _collect_findings


def _jsx_findings(text: str, path: str = "packages/trace-viewer/src/ui/networkFilters.tsx") -> list[dict]:
    return _collect_findings([SourceFile(path, text)], {}, "external_playwright_42463")


def test_placeholder_only_search_control_gets_issue_specific_reason_code() -> None:
    findings = _jsx_findings(
        """
        <input type="search" placeholder="Filter network" onChange={onChange} />
        """
    )

    matches = [item for item in findings if item["id"] == "A11Y-FORM-CONTROL-NAME"]
    assert len(matches) == 1
    assert matches[0]["severity"] == "P1"
    assert matches[0]["reasonCode"] == "PLACEHOLDER_ONLY_NOT_ACCESSIBLE_NAME"
    assert matches[0]["location"]["line"] == 2


def test_explicit_name_contract_is_clean_even_when_placeholder_is_present() -> None:
    text = """
    <input type="search" placeholder="Filter network" aria-label="Filter network" />
    <input type="search" placeholder="Filter errors" id="error-filter" />
    """

    assert not any(item["id"] == "A11Y-FORM-CONTROL-NAME" for item in _jsx_findings(text))


def test_placeholder_reason_code_is_available_for_canonical_html_facts() -> None:
    source = SourceFile(
        "fixtures/filter.html",
        '<label for="query">Query</label><input id="other" placeholder="Search" />',
    )
    parser = EvidenceHtmlParser()
    parser.feed(source.text)

    findings = _collect_findings([source], {source.path: parser.facts}, "external_playwright_42463")
    matches = [item for item in findings if item["id"] == "A11Y-FORM-CONTROL-NAME"]
    assert len(matches) == 1
    assert matches[0]["reasonCode"] == "PLACEHOLDER_ONLY_NOT_ACCESSIBLE_NAME"


def test_pointer_only_trace_viewer_error_row_remains_reported() -> None:
    findings = _jsx_findings(
        """
        <span onClick={openSourceLocation}>source location</span>
        """,
        "packages/trace-viewer/src/ui/errorsTab.tsx",
    )

    matches = [item for item in findings if item["id"] == "A11Y-POINTER-ONLY-INTERACTION"]
    assert len(matches) == 1
    assert matches[0]["reasonCode"] == "NON_NATIVE_CLICK_WITHOUT_KEYBOARD_SEMANTICS"


def test_unsupported_text_fixture_is_not_scanned_as_jsx() -> None:
    findings = _jsx_findings('<input placeholder="Filter network" />', "fixtures/notes.txt")

    assert findings == []
