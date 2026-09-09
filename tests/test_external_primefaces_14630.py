from __future__ import annotations

from web_ui_quality.core import SourceFile, _collect_findings


RULE_ID = "A11Y-COMPONENT-ARIA-DISABLED-PROPAGATION"


BEFORE = """
# Synthetic Java-like fixture authored for this detector contract; it is not
# copied from a PrimeFaces source file.
public class SelectOneMenuRenderer extends SelectOneRenderer<SelectOneMenu> {
    protected void encodeLabel(RenderContext context, SelectOneMenu component, List<Option> selectItems) throws IOException {
        ResponseWriter writer = context.getResponseWriter();
        if (component.isEditable()) {
            writer.startElement("input", null);
            if (component.isDisabled()) {
                writer.writeAttribute("disabled", "disabled", null);
            }
            renderAccessibilityAttributes(context, component);
            writer.endElement("input");
        }
        else {
            String clientId = component.getClientId(context);
            writer.startElement("span", null);
            writer.writeAttribute(HTML.ARIA_CONTROLS, clientId + "_panel", null);
            encodeAriaLabel(writer, component);
            renderARIACombobox(context, component);
            renderAccessibilityAttributes(context, component);
            renderPassThruAttributes(context, component, HTML.TAB_INDEX);
            renderDomEvents(context, component, HTML.BLUR_FOCUS_EVENTS);
            writer.endElement("span");
        }
    }

    protected void encodeMenuIcon(RenderContext context, SelectOneMenu component, boolean valid) throws IOException {
        writer.endElement("div");
    }
}
"""


AFTER = BEFORE.replace(
    "            renderARIACombobox(context, component);\n            renderAccessibilityAttributes(context, component);",
    "            if (component.isDisabled()) {\n                writer.writeAttribute(HTML.ARIA_DISABLED, \"true\", null);\n            }\n            encodeAriaLabel(writer, component);\n            renderARIACombobox(context, component);",
).replace(
    "            encodeAriaLabel(writer, component);\n            if (component.isDisabled()) {\n                writer.writeAttribute(HTML.ARIA_DISABLED, \"true\", null);\n            }\n            encodeAriaLabel(writer, component);\n            renderARIACombobox(context, component);",
    "            if (component.isDisabled()) {\n                writer.writeAttribute(HTML.ARIA_DISABLED, \"true\", null);\n            }\n            encodeAriaLabel(writer, component);\n            renderARIACombobox(context, component);",
)


def _findings(text: str, path: str = "primefaces/src/main/java/org/primefaces/component/selectonemenu/SelectOneMenuRenderer.java") -> list[dict]:
    return [
        item
        for item in _collect_findings([SourceFile(path, text)], {}, "external_primefaces_14630")
        if item["id"] == RULE_ID
    ]


def test_primefaces_select_one_menu_before_has_disabled_state_gap() -> None:
    findings = _findings(BEFORE)

    assert len(findings) == 1
    assert findings[0]["severity"] == "P2"
    assert findings[0]["reasonCode"] == "DISABLED_STATE_NOT_EXPOSED_TO_ASSISTIVE_TECHNOLOGY"
    assert findings[0]["location"]["selector"] == "SelectOneMenuRenderer > encodeLabel > non-editable combobox"


def test_primefaces_select_one_menu_merged_after_is_clean() -> None:
    assert _findings(AFTER) == []


def test_unrelated_java_renderer_is_not_inferred_as_primefaces_select_one_menu() -> None:
    assert _findings(BEFORE.replace("SelectOneMenuRenderer", "OtherRenderer")) == []


def test_explicit_aria_disabled_state_is_not_reported_even_with_generic_call() -> None:
    text = BEFORE.replace(
        "            renderAccessibilityAttributes(context, component);\n            renderPassThruAttributes",
        "            writer.writeAttribute(HTML.ARIA_DISABLED, \"true\", null);\n            renderAccessibilityAttributes(context, component);\n            renderPassThruAttributes",
    )

    assert _findings(text) == []


def test_unsupported_source_suffix_is_not_scanned() -> None:
    assert _findings(BEFORE, "fixtures/SelectOneMenuRenderer.txt") == []
