from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping

from web_ui_quality.design_intelligence import generate_design_candidates
from web_ui_quality.design_ir import summarise_design_ir, validate_design_ir
from web_ui_quality.design_pipeline import run_design_pipeline
from web_ui_quality.project_source_ir import build_project_design_ir
from web_ui_quality.schema_validation import validate_instance


ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "schemas"
LAYERS = ("Product", "Route", "Journey", "Region", "Component", "Interaction State")


def _schema(name: str) -> dict[str, Any]:
    return json.loads((SCHEMAS / name).read_text(encoding="utf-8"))


def _write_project(root: Path, *, framework: str = "react") -> None:
    root.mkdir()
    dependency = "react" if framework == "react" else "@angular/core"
    (root / "package.json").write_text(
        json.dumps({"dependencies": {dependency: "1.0.0"}}), encoding="utf-8"
    )
    (root / "App.tsx").write_text(
        """
        export function App() {
          return <Route path="/orders"><nav>Orders</nav><main>
            <form><input aria-label="Search"/><button>Apply</button></form>
            <table><tbody><tr><td>Order</td></tr></tbody></table><Chart />
          </main></Route>;
        }
        """,
        encoding="utf-8",
    )
    (root / "tokens.css").write_text(
        ":root{--color-brand:#166b4f;--space-3:12px}", encoding="utf-8"
    )


def _walk_product(node: Mapping[str, Any], depth: int = 1):
    yield node, depth
    for child in node.get("children", []):
        if isinstance(child, Mapping):
            yield from _walk_product(child, depth + 1)


def _assert_no_absolute_path(root: Path) -> None:
    pattern = re.compile(r"(?i)(?:^|[\"'\s])[a-z]:[\\/]")
    leaks: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.casefold() not in {".json", ".html", ".md", ".css", ".js"}:
            continue
        if pattern.search(path.read_text(encoding="utf-8", errors="replace")):
            leaks.append(path.relative_to(root).as_posix())
    assert leaks == []


def test_project_design_ir_has_six_layers_and_honest_source_evidence(tmp_path: Path):
    project = tmp_path / "react-project"
    _write_project(project)

    document = build_project_design_ir(project)
    summary = summarise_design_ir(document)
    product_nodes = list(_walk_product(document["productModel"]))
    layers = {str(node["layer"]) for node, _depth in product_nodes}
    component_roles = {
        str(node.get("semantics", {}).get("role"))
        for node, _depth in product_nodes
        if node.get("layer") == "Component"
    }

    assert validate_design_ir(document) == []
    validate_instance(document, _schema("design-ir.schema.json"), base_dir=SCHEMAS)
    assert document["productModelVersion"] == "2.0"
    assert layers == set(LAYERS)
    assert summary["productModelMaxDepth"] == 6
    assert summary["productModelNodeCount"] == len(product_nodes)
    assert {"navigation", "table", "form", "chart"}.issubset(component_roles)
    assert any(node["layer"] == "Route" and node["name"] == "/orders" for node, _depth in product_nodes)
    for node, _depth in product_nodes:
        assert node["evidenceClass"] in {"observed", "inferred", "declared", "unknown"}
        assert node["sourceOwnership"]["authority"] == "read-only-reference"
        assert set(node["evidence"]["channels"]) == {"source", "dom", "visual", "runtime"}
        assert node["evidence"]["channels"]["dom"] == []
        assert node["evidence"]["channels"]["visual"] == []
        assert node["evidence"]["channels"]["runtime"] == []
        if node["layer"] == "Interaction State":
            assert node["evidenceClass"] == "unknown"
            assert node["evidence"]["unknown"]


def test_candidates_honor_one_to_three_product_directions_with_pairwise_gate():
    result = generate_design_candidates(
        {"experienceModel": {"primaryTask": "Review orders", "userExpertise": "novice"}},
        count=2,
    )

    assert [item["name"] for item in result["candidates"]] == [
        "Conservative Repair", "Journey Focused"
    ]
    assert result["selectionPolicy"]["candidateCount"] == 2
    assert result["differenceGate"]["status"] == "PASS"
    assert len(result["differenceGate"]["pairwise"]) == 1
    assert all(item["distinctDimensionCount"] >= 3 for item in result["differenceGate"]["pairwise"])
    validate_instance(result, _schema("design-candidates.schema.json"), base_dir=SCHEMAS)


def test_pipeline_persists_requested_candidate_gate_and_visual_builder(tmp_path: Path):
    project = tmp_path / "react-project"
    output = tmp_path / "output"
    _write_project(project)

    result = run_design_pipeline(
        project,
        output,
        experience_plan={"experienceModel": {"primaryTask": "Review orders"}},
        candidate_count=2,
    )
    persisted_candidates = json.loads((output / result["designCandidates"]).read_text(encoding="utf-8"))
    persisted_ir = json.loads((output / "design-input" / "design-ir.json").read_text(encoding="utf-8"))

    assert result["status"] == "DESIGN_PIPELINE_READY"
    assert result["gates"]["candidateCount"] == {
        "requested": 2, "actual": 2, "required": 2, "status": "PASS"
    }
    assert result["gates"]["candidateStructuralDifference"] == "PASS"
    assert len(persisted_candidates["candidates"]) == 2
    assert persisted_ir["productModelVersion"] == "2.0"
    assert (output / result["visualBuilder"]).is_file()
    validate_instance(result, _schema("design-pipeline.schema.json"), base_dir=SCHEMAS)
    _assert_no_absolute_path(output)


def test_unsupported_framework_stays_fail_closed_without_html_scaffold(tmp_path: Path):
    project = tmp_path / "angular-project"
    output = tmp_path / "output"
    _write_project(project, framework="angular")

    result = run_design_pipeline(
        project,
        output,
        experience_plan={"experienceModel": {"primaryTask": "Review orders"}},
    )

    assert result["status"] == "FRAMEWORK_NOT_SUPPORTED"
    assert result["reason"] == "FRAMEWORK_NOT_SUPPORTED"
    assert result["productionScaffold"]["status"] == "NOT_SUPPORTED"
    assert result["productionScaffold"]["reason"] == "FRAMEWORK_NOT_SUPPORTED"
    assert list((output / "production-scaffold").glob("*.html")) == []
    validate_instance(result, _schema("design-pipeline.schema.json"), base_dir=SCHEMAS)
