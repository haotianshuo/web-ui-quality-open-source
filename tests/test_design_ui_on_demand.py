import json
from pathlib import Path

from web_ui_quality.__main__ import main
from web_ui_quality.design_gallery import build_design_gallery


def _empty_design_review(tmp_path: Path) -> Path:
    before = tmp_path / "before"
    before.mkdir()
    report = build_design_gallery(
        before,
        {"variants": []},
        tmp_path / "validation",
        tmp_path / "design-gallery",
        render_ui=False,
    )
    assert report["ui"]["status"] == "ON_DEMAND"
    return tmp_path


def test_core_report_does_not_render_ui_by_default(tmp_path: Path):
    root = _empty_design_review(tmp_path)
    gallery = root / "design-gallery"
    assert (gallery / "design-review.json").is_file()
    assert not (gallery / "index.html").exists()
    assert not (gallery / "executive-decision-brief.md").exists()


def test_design_ui_renders_on_demand_and_keeps_local_dependency_boundary(tmp_path: Path, capsys):
    root = _empty_design_review(tmp_path)
    assert main(["design-ui", str(root), "--compact"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "DESIGN_UI_RENDERED"
    gallery = root / "design-gallery"
    assert (gallery / "index.html").is_file()
    assert (gallery / "executive-decision-brief.md").is_file()
    report = json.loads((gallery / "design-review.json").read_text(encoding="utf-8"))
    assert report["ui"]["status"] == "RENDERED"
    html = (gallery / "index.html").read_text(encoding="utf-8")
    assert "<script src=" not in html
    assert "<link rel=" not in html
