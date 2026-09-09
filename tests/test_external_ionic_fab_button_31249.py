from __future__ import annotations

from web_ui_quality.core import SourceFile, _collect_findings


RULE_ID = "A11Y-COMPONENT-FORM-PARTICIPATION"


BEFORE = """
@Component({
  tag: 'ion-fab-button',
  shadow: true,
})
export class FabButton {
  @Prop() disabled = false;
  @Prop() type: 'submit' | 'reset' | 'button' = 'button';

  private onClick = () => {};

  render() {
    const TagType = href === undefined ? 'button' : ('a' as any);
    const attrs = TagType === 'button' ? { type: this.type } : { href };
    return (
      <Host onClick={this.onClick}>
        <TagType {...attrs} disabled={disabled} onClick={(ev: Event) => openURL(href, ev)}></TagType>
      </Host>
    );
  }
}
"""


AFTER = BEFORE.replace(
    "  private onClick = () => {};\n",
    "  private formButtonEl: HTMLButtonElement | null = null;\n"
    "  @Prop() form?: string | HTMLFormElement;\n"
    "  private onClick = (ev: Event) => {\n"
    "    if (this.type !== 'button' && hasShadowDom(this.el)) this.submitForm(ev);\n"
    "  };\n"
    "  private renderHiddenButton() {}\n"
    "  private submitForm(ev: Event) { this.formButtonEl?.click(); }\n",
)


def _findings(text: str, path: str = "core/src/components/fab-button/fab-button.tsx") -> list[dict]:
    return [
        item
        for item in _collect_findings([SourceFile(path, text)], {}, "external_ionic_31249")
        if item["id"].startswith(RULE_ID)
    ]


def test_ionic_fab_button_before_has_shadow_dom_form_gap() -> None:
    findings = _findings(BEFORE)

    assert len(findings) == 1
    assert findings[0]["severity"] == "P1"
    assert findings[0]["reasonCode"] == "SHADOW_DOM_BUTTON_NOT_FORM_ASSOCIATED"
    assert findings[0]["location"]["line"] == 8
    assert findings[0]["location"]["selector"] == "ion-fab-button[type=submit|reset][shadow]"


def test_ionic_fab_button_merged_after_has_form_bridge() -> None:
    assert _findings(AFTER) == []


def test_non_shadow_component_is_not_inferred_as_ionic_form_gap() -> None:
    assert _findings(BEFORE.replace("shadow: true", "shadow: false")) == []


def test_unrelated_component_is_not_inferred_as_ionic_form_gap() -> None:
    assert _findings(BEFORE.replace("ion-fab-button", "other-button")) == []


def test_unsupported_file_is_not_scanned_as_component_source() -> None:
    assert _findings(BEFORE, "fixtures/fab-button.txt") == []
