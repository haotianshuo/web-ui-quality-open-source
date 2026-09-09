from __future__ import annotations

from web_ui_quality.core import SourceFile, _collect_findings


RULE_ID = "A11Y-DIALOG-ARIA-REFERENCE-INTEGRITY"


BEFORE = """
type DialogContextValue = {
  contentId: string;
  titleId: string;
  descriptionId: string;
};
const DialogContentImpl = React.forwardRef((props, forwardedRef) => {
  const context = useDialogContext('DialogContent', undefined);
  return (
    <DismissableLayer
      role="dialog"
      id={context.contentId}
      aria-describedby={context.descriptionId}
      aria-labelledby={context.titleId}
      {...props}
      ref={forwardedRef}
    />
  );
});
const DialogTitle = React.forwardRef((props, forwardedRef) => {
  const context = useDialogContext('DialogTitle', undefined);
  return <Primitive.h2 id={context.titleId} {...props} ref={forwardedRef} />;
});
const DialogDescription = React.forwardRef((props, forwardedRef) => {
  const context = useDialogContext('DialogDescription', undefined);
  return <Primitive.p id={context.descriptionId} {...props} ref={forwardedRef} />;
});
"""


AFTER = BEFORE.replace(
    "      aria-describedby={context.descriptionId}\n      aria-labelledby={context.titleId}",
    "      aria-describedby={context.descriptionPresent ? context.descriptionId : undefined}\n      aria-labelledby={context.titlePresent ? context.titleId : undefined}",
).replace(
    "  descriptionId: string;\n};",
    "  descriptionId: string;\n  titlePresent: boolean;\n  descriptionPresent: boolean;\n};",
)


def _findings(text: str, path: str = "packages/react/dialog/src/dialog.tsx") -> list[dict]:
    return [
        item
        for item in _collect_findings([SourceFile(path, text)], {}, "external_radix_dialog_4031")
        if item["id"] == RULE_ID
    ]


def test_radix_dialog_before_has_unconditional_generated_aria_references() -> None:
    findings = _findings(BEFORE)

    assert len(findings) == 1
    assert findings[0]["severity"] == "P2"
    assert findings[0]["reasonCode"] == "DIALOG_ARIA_REFERENCE_MAY_BE_DANGLING"
    assert findings[0]["location"]["line"] == 13
    assert findings[0]["location"]["selector"] == "DialogContentImpl > DismissableLayer[aria-labelledby/aria-describedby]"


def test_radix_dialog_merged_after_conditionally_emits_references() -> None:
    assert _findings(AFTER) == []


def test_unrelated_dialog_component_is_not_inferred_as_radix_dialog() -> None:
    text = BEFORE.replace("DialogContentImpl", "OtherContentImpl", 2)

    assert _findings(text) == []


def test_unconditional_references_in_a_non_dialog_layer_are_not_reported() -> None:
    text = BEFORE.replace('role="dialog"', 'role="region"')

    assert _findings(text) == []


def test_unsupported_text_path_is_not_scanned_as_tsx_source() -> None:
    assert _findings(BEFORE, "fixtures/dialog.txt") == []
