from __future__ import annotations

from web_ui_quality.core import audit_html_document, audit_project


def test_classic_html_script_with_esm_is_still_reported() -> None:
    result = audit_html_document("<html><body><script>import { value } from './module.js';</script></body></html>")

    assert any(item["id"] == "SEM-SCRIPT-MODULE-MISMATCH" for item in result["findings"])


def test_compiled_component_script_is_not_treated_as_classic_html(tmp_path) -> None:
    component = tmp_path / "Example.svelte"
    component.write_text('<script lang="ts">\n  import { value } from "./module";\n</script>\n<div>{value}</div>\n', encoding="utf-8")

    result = audit_project(tmp_path)

    assert not any(item["id"] == "SEM-SCRIPT-MODULE-MISMATCH" for item in result["findings"])
