from __future__ import annotations

from web_ui_quality.core import SourceFile, _collect_findings


RULE_ID = "A11Y-COMPONENT-ARIA-LABEL-FORWARDING"


BEFORE = """
const InputBase = React.forwardRef(function InputBase(inProps, ref) {
  const props = useDefaultProps({ props: inProps, name: 'MuiInputBase' });
  const {
    'aria-describedby': ariaDescribedby,
    ...other
  } = props;
  return (
    <Root {...other}>
      <Input aria-describedby={ariaDescribedby} />
    </Root>
  );
});
InputBase.propTypes = {};
"""


AFTER = BEFORE.replace(
    "    'aria-describedby': ariaDescribedby,\n",
    "    'aria-describedby': ariaDescribedby,\n    'aria-label': ariaLabel,\n",
).replace(
    "<Input aria-describedby={ariaDescribedby} />",
    "<Input aria-describedby={ariaDescribedby} aria-label={ariaLabel} />",
)


def _findings(text: str, path: str = "packages/mui-material/src/InputBase/InputBase.js") -> list[dict]:
    return [
        item
        for item in _collect_findings([SourceFile(path, text)], {}, "external_mui_48283")
        if item["id"] == RULE_ID
    ]


def test_mui_input_base_before_has_top_level_aria_label_forwarding_gap() -> None:
    findings = _findings(BEFORE)

    assert len(findings) == 1
    assert findings[0]["severity"] == "P2"
    assert findings[0]["reasonCode"] == "TOP_LEVEL_ARIA_LABEL_NOT_FORWARDED_TO_CONTROL"
    assert findings[0]["location"]["line"] == 10
    assert findings[0]["location"]["selector"] == "InputBase > Input"


def test_mui_input_base_merged_after_forwards_aria_label_cleanly() -> None:
    assert _findings(AFTER) == []


def test_unrelated_wrapper_is_not_inferred_as_mui_input_base() -> None:
    text = BEFORE.replace("InputBase", "OtherInput", 2)

    assert _findings(text) == []


def test_unsupported_file_is_not_scanned_as_component_source() -> None:
    assert _findings(BEFORE, "fixtures/InputBase.txt") == []
