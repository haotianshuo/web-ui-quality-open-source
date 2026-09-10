from __future__ import annotations

from web_ui_quality.core import SourceFile, _collect_findings, _css_has_focus_replacement


def _finding_ids(css: str) -> list[str]:
    return [
        str(item.get("id"))
        for item in _collect_findings([SourceFile("sample.css", css)], {}, "stage01-focus")
    ]


def test_focus_outline_removal_is_whitespace_invariant() -> None:
    removed = (
        "outline:none",
        "outline: none",
        "outline:\tnone",
        "outline : none",
        "outline:0",
        "outline: 0",
        "outline:\t0",
    )
    for declaration in removed:
        css = "button:focus{" + declaration + ";}"
        assert _css_has_focus_replacement(css) is False
        assert "A11Y-FOCUS-OUTLINE-REMOVED" in _finding_ids(css)


def test_focus_replacement_matrix_and_selector_scope() -> None:
    replacements = (
        "outline:2px solid blue",
        "outline: 2px solid blue",
        "box-shadow:0 0 0 2px blue",
        "box-shadow: 0 0 0 2px blue",
        "border-color: blue",
    )
    for declaration in replacements:
        css = "button:focus{outline: none;" + declaration + ";}"
        assert _css_has_focus_replacement(css) is True
        assert "A11Y-FOCUS-OUTLINE-REMOVED" not in _finding_ids(css)

    assert _css_has_focus_replacement("button:hover{outline:2px solid blue;}") is False
    assert _css_has_focus_replacement("button:focus{outline: none; box-shadow: none;}") is False
    assert "A11Y-FOCUS-OUTLINE-REMOVED" in _finding_ids(
        "button:focus{outline: none; box-shadow: none;}"
    )
