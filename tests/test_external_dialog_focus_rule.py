from __future__ import annotations

from web_ui_quality.core import SourceFile, _collect_findings


def _findings(text: str, path: str = "src/BaseDialog.tsx") -> list[dict]:
    return _collect_findings([SourceFile(path, text)], {}, "external_jitsi_dialog_focus")


def _dialog_findings(text: str) -> list[dict]:
    return [item for item in _findings(text) if item["id"] == "A11Y-DIALOG-FOCUS-RESTORE"]


def test_dialog_focus_lock_without_return_focus_is_reported() -> None:
    findings = _dialog_findings(
        """
        <FocusLock className = { classes.focusLock }>
            <div aria-modal = { true } role = 'dialog'>content</div>
        </FocusLock>
        """
    )

    assert len(findings) == 1
    assert findings[0]["severity"] == "P2"
    assert findings[0]["reasonCode"] == "DIALOG_FOCUS_RETURN_CONTRACT_MISSING"
    assert findings[0]["location"]["line"] == 2


def test_dialog_focus_lock_with_explicit_return_focus_is_clean() -> None:
    findings = _dialog_findings(
        """
        <FocusLock
            className = { classes.focusLock }
            returnFocus = { true }>
            <div aria-modal = { true } role = 'dialog'>content</div>
        </FocusLock>
        """
    )

    assert findings == []


def test_non_dialog_focus_lock_is_not_reported() -> None:
    findings = _dialog_findings(
        """
        <FocusLock className = { classes.focusLock }>
            <div role = 'menu'>content</div>
        </FocusLock>
        """
    )

    assert findings == []


def test_dynamic_return_focus_contract_is_left_for_runtime_review() -> None:
    findings = _dialog_findings(
        """
        <FocusLock
            returnFocus = { shouldReturnFocus }>
            <div role = 'dialog' aria-modal = { true }>content</div>
        </FocusLock>
        """
    )

    assert findings == []


def test_dialog_focus_rule_is_scoped_to_jsx_like_sources() -> None:
    text = """
    <FocusLock>
        <div role = 'dialog' aria-modal = { true }>content</div>
    </FocusLock>
    """

    assert len(_dialog_findings(text)) == 1
    assert [
        item for item in _findings(text, "src/notes.txt")
        if item["id"] == "A11Y-DIALOG-FOCUS-RESTORE"
    ] == []
