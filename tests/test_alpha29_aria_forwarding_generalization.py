from __future__ import annotations

from pathlib import Path

from web_ui_quality.aria_forwarding_rule import scan_aria_forwarding_gaps


REACT_BEFORE = """
const InputBase = React.forwardRef(function InputBase(inProps, ref) {
  const { 'aria-describedby': ariaDescribedby, ...other } = inProps;
  return <Root {...other}><Input aria-describedby={ariaDescribedby} /></Root>;
});
InputBase.propTypes = {};
"""
REACT_AFTER = REACT_BEFORE.replace(
    "'aria-describedby': ariaDescribedby,",
    "'aria-describedby': ariaDescribedby, 'aria-label': ariaLabel,",
).replace(
    "<Input aria-describedby={ariaDescribedby} />",
    "<Input aria-describedby={ariaDescribedby} aria-label={ariaLabel} />",
)


VUE_BEFORE = """
<template><label :for="labelFor">{{ currentLabel }}</label><slot /></template>
<script setup lang="ts">
const labelFor = computed(() => props.for || propString.value)
</script>
"""
VUE_AFTER = """
<template><component :is="labelFor ? 'label' : 'div'" :for="labelFor" /><slot /></template>
<script setup lang="ts">
const inputIds = ref<string[]>([])
const labelFor = computed(() => props.for || inputIds.value[0])
</script>
"""


WEB_COMPONENT_BEFORE = """
@Component({ tag: 'ion-button', shadow: true })
export class Button {
  private inheritedAttributes: Attributes = {};
  componentWillLoad() { this.inheritedAttributes = inheritAriaAttributes(this.el); }
  render() { return <button {...inheritedAttributes}><slot /></button>; }
}
"""
WEB_COMPONENT_AFTER = WEB_COMPONENT_BEFORE.replace(
    "componentWillLoad()",
    "startAriaWatcher() { watchForAriaAttributeChanges(this.el); }\n  componentWillLoad()",
)


def _ids(path: str, text: str) -> list[tuple[int, str, str]]:
    return list(scan_aria_forwarding_gaps(path, text))


def test_react_wrapper_forwarding_before_after() -> None:
    assert _ids("InputBase.jsx", REACT_BEFORE)[0][1:] == (
        "InputBase > Input",
        "TOP_LEVEL_ARIA_LABEL_NOT_FORWARDED_TO_CONTROL",
    )
    assert _ids("InputBase.jsx", REACT_AFTER) == []


def test_vue_form_label_binding_before_after() -> None:
    assert _ids("form-item.vue", VUE_BEFORE)[0][1:] == (
        "ElFormItem > control",
        "FORM_LABEL_NOT_BOUND_TO_CONTROL",
    )
    assert _ids("form-item.vue", VUE_AFTER) == []


def test_web_component_host_aria_sync_before_after() -> None:
    assert _ids("button.tsx", WEB_COMPONENT_BEFORE)[0][1:] == (
        "ion-button > native control",
        "HOST_ARIA_ATTRIBUTES_NOT_SYNCHRONIZED_TO_CONTROL",
    )
    assert _ids("button.tsx", WEB_COMPONENT_AFTER) == []


def test_registry_does_not_treat_unrelated_react_issue_controls_as_forwarding() -> None:
    mui_x = """
    export function ListViewMediaQuery() { return <DataGrid listView />; }
    """
    ant_design = """
    export function Descriptions() { return <Descriptions responsive={{ md: 2 }} />; }
    """
    assert _ids("ListViewMediaQuery.tsx", mui_x) == []
    assert _ids("index.tsx", ant_design) == []


def test_core_line_budget_remains_at_or_below_alpha28_baseline() -> None:
    core = Path(__file__).parents[1] / "runtime" / "python" / "web_ui_quality" / "core.py"
    assert len(core.read_text(encoding="utf-8").splitlines()) <= 2317
