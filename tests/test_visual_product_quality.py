"""Real rendered counterexamples plus the normal discovery-to-Host handoff.

These are isolated, network-free component fixtures, not product acceptance.
"""
from __future__ import annotations

import pytest

from web_ui_quality.acceptance_findings import normalize_findings
from web_ui_quality.browser_locator import resolve_browser_executable
from web_ui_quality.contracts import ContractViolation
from web_ui_quality.quick_ui import summarize_top_ui_issues
from web_ui_quality.rendered_quality import _ICON_GRAPHIC_ANALYSIS_JS, _RENDERED_QUALITY_JS, _composition_findings, _text_fragmentation_findings
from web_ui_quality.repair_recipe import build_repair_recipes
from web_ui_quality.smart_acceptance import _finding_candidates
from web_ui_quality.task_result import build_task_result
from web_ui_quality.visual_review import build_visual_review_work, normalize_visual_review, review_template


@pytest.fixture(scope="module")
def browser():
    pw_api = pytest.importorskip("playwright.sync_api")
    with pw_api.sync_playwright() as pw:
        decision = resolve_browser_executable("chromium", playwright_browser_type=pw.chromium)
        if not decision["available"]:
            pytest.skip("A real browser is required for rendered counterexamples")
        with pw.chromium.launch(executable_path=decision["executable"], headless=True) as instance:
            yield instance


@pytest.fixture
def page(browser):
    context = browser.new_context(viewport={"width": 390, "height": 844})
    context.route("**/*", lambda route: route.abort())
    page = context.new_page()
    yield page
    context.close()


def measure(page, markup: str, css: str = ""):
    page.set_content("<html lang='zh-CN'><head><meta charset='utf-8'><style>"
                     "*{box-sizing:border-box}body{margin:16px;font:16px/1.5 sans-serif;color:#17221c;background:#edf3ef}"
                     "strong{display:block}button{font:inherit}"
                     + css + "</style></head><body><main>" + markup + "</main></body></html>")
    return page.evaluate(_RENDERED_QUALITY_JS)


def measure_icon_graphics(page, markup: str, css: str = ""):
    page.set_content("<html lang='zh-CN'><head><meta charset='utf-8'><style>"
                     "*{box-sizing:border-box}body{margin:16px;font:16px/1.5 sans-serif;color:#17221c;background:#edf3ef}"
                     + css + "</style></head><body><main>" + markup + "</main></body></html>")
    return page.evaluate(_ICON_GRAPHIC_ANALYSIS_JS)


def png_data_uri(width: int, height: int, ink_rects: list[tuple[int, int, int, int]]) -> str:
    """Build a small RGBA PNG with standard-library code for crop fixtures."""
    import base64
    import struct
    import zlib

    pixels = bytearray(width * height * 4)
    for left, top, right, bottom in ink_rects:
        for y in range(max(0, top), min(height, bottom)):
            for x in range(max(0, left), min(width, right)):
                pixels[(y * width + x) * 4:(y * width + x) * 4 + 4] = b"\xff\xff\xff\xff"
    raw = b"".join(b"\x00" + pixels[y * width * 4:(y + 1) * width * 4] for y in range(height))

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    payload = b"\x89PNG\r\n\x1a\n"
    payload += chunk(b"IHDR", struct.pack(">2I5B", width, height, 8, 6, 0, 0, 0))
    payload += chunk(b"IDAT", zlib.compress(raw))
    payload += chunk(b"IEND", b"")
    return "data:image/png;base64," + base64.b64encode(payload).decode("ascii")


def test_short_labels_wrap_before_and_fit_after_without_shrinking_type(page, tmp_path):
    markup = "<div class='priority-grid'>" + "".join(
        f"<article class='priority-item'><span class='icon-wrap'><i data-icon></i></span><strong>{title}</strong><span>›</span></article>"
        for title in ("专项二审", "申诉复核", "财务批次")) + "</div>"
    css = ".priority-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}.priority-item{display:grid;grid-template-columns:36px minmax(0,1fr) 10px;padding:8px;background:white;border-radius:12px;gap:4px}.icon-wrap{width:36px;height:36px}strong{font-size:16px;line-height:24px;margin:0}"
    before = measure(page, markup, css)
    page.screenshot(path=str(tmp_path / "short-label-before.png"))
    assert before["visualReviewCandidates"]["shortLabelWrap"] or before["issues"]["textFragmentation"]
    after = measure(page, markup, css + ".priority-grid{grid-template-columns:1fr}.priority-item{align-items:center}")
    page.screenshot(path=str(tmp_path / "short-label-after.png"))
    assert after["visualReviewCandidates"]["shortLabelWrap"] == []
    assert after["issues"]["textFragmentation"] == []
    assert page.locator("strong").first.evaluate("el=>getComputedStyle(el).fontSize") == "16px"


def test_refresh_two_character_label_wrap_is_a_review_candidate(page):
    raw = measure(page, "<button><span>刷新</span></button>", "button{width:32px;padding:8px}button span{display:block}")
    assert [row["text"] for row in raw["visualReviewCandidates"]["shortLabelWrap"]] == ["刷新"]


def test_normal_wrapped_paragraph_and_intentional_vertical_writing_are_not_short_label_defects(page):
    raw = measure(page, "<p>专项二审</p><strong>专项二审</strong>", "p{width:32px}strong{writing-mode:vertical-rl;height:100px}")
    assert raw["visualReviewCandidates"]["shortLabelWrap"] == []
    assert raw["issues"]["textFragmentation"] == []


def test_historical_single_character_fragmentation_stays_measured(page):
    raw = measure(page, "<strong>专项二审</strong>", "strong{width:18px;font-size:18px;line-height:24px}")
    findings = _text_fragmentation_findings(raw["issues"])
    assert findings and findings[0]["evidenceClass"] == "BROWSER_MEASURED"


@pytest.mark.parametrize("gap,radius,expected", [(0, 14, True), (12, 14, False), (0, 0, False)])
def test_rounded_card_grouping_does_not_force_gaps_into_flat_lists(page, gap, radius, expected):
    raw = measure(page, "<div class='messages'><article class='message-card'>通知一</article><article class='message-card'>通知二</article></div>",
                  f".messages{{display:grid;gap:{gap}px}}.message-card{{height:110px;background:white;border-radius:{radius}px;padding:16px}}")
    assert bool(raw["visualReviewCandidates"]["adjoiningRoundedCards"]) is expected


@pytest.mark.parametrize("css,underfill,offcenter", [
    (".icon-wrap{display:flex;align-items:center;justify-content:center}i{width:30px;height:30px}", False, False),
    (".icon-wrap{display:flex;align-items:center;justify-content:center}i{width:16px;height:16px}", True, False),
    ("i{position:relative;left:1px;top:1px;width:30px;height:30px}", False, True),
])
def test_icon_surface_proportion_and_box_center_are_separate(page, css, underfill, offcenter):
    raw = measure(page, "<span class='icon-wrap'><i data-icon></i></span>",
                  ".icon-wrap{display:block;width:48px;height:48px;background:#d9eee1;border-radius:12px}i{display:block;background:#168045}" + css)
    assert bool(raw["issues"]["iconElementBoxUnderfill"]) is underfill
    assert bool(raw["visualReviewCandidates"]["iconBoxMisalignment"]) is offcenter
    assert not _composition_findings({"iconElementBoxUnderfill": raw["issues"]["iconElementBoxUnderfill"]})
    for row in raw["visualReviewCandidates"]["iconBoxMisalignment"]:
        assert row["metric"] == "BOX_CENTER_OFFSET_NOT_OPTICAL_INK"


def test_good_touch_target_does_not_count_as_oversized_icon_backplate(page):
    raw = measure(page, "<button aria-label='关闭'><i data-icon></i></button>",
                  "button{width:48px;height:48px;display:grid;place-items:center}i{display:block;width:20px;height:20px}")
    assert raw["issues"]["iconElementBoxUnderfill"] == []
    assert raw["visualReviewCandidates"]["iconBoxMisalignment"] == []


def test_repeated_sparse_cards_detected_but_single_hero_not_assumed_wrong(page):
    css = ".card{height:200px;background:white;border-radius:12px;padding:16px}"
    raw = measure(page, "<article class='card'>主要入口</article>" * 3, css)
    assert len(raw["issues"]["sparseRepeatedComponents"]) == 3
    raw = measure(page, "<article class='card'>主要入口</article>", css)
    assert raw["issues"]["sparseRepeatedComponents"] == []


def test_local_horizontal_tab_strip_is_not_page_overflow(page):
    raw = measure(page, "<div class='tabs'><button>全部</button><button>待办</button><button>审核</button><button>视频</button></div>",
                  ".tabs{display:flex;overflow-x:auto;width:330px}.tabs button{flex:0 0 120px;height:44px}")
    assert raw["issues"]["overflowViewport"] == []


def test_all_candidates_reach_normal_findings_recipes_and_host_work_without_auto_confirmation():
    findings = _composition_findings({key: [{"selector": ".icon", "styleSelector": ".icon", "container": ".card"}]
                                      for key in ("shortLabelWrap", "iconBoxMisalignment", "iconVisibleGraphicMisalignment", "iconVisibleGraphicUnderfill", "spriteEdgeResidue", "adjoiningRoundedCards", "sparseRepeatedComponents")})
    records = [{"status": "PASS", "pageHealth": {"pageStatus": "REAL_PAGE_READY"}, "viewport": {"width": 390, "height": 844},
                "screenshotRef": "screenshots/mobile.png", "renderedQuality": {"findings": findings}}]
    all_issues = summarize_top_ui_issues(records, limit=None)
    assert len(all_issues) == 7 and len(summarize_top_ui_issues(records)) == 3
    assert all(row["evidenceClass"] == "DIAGNOSTIC_CANDIDATE" and row["claimBoundary"] for row in all_issues)
    candidates = _finding_candidates(url="http://localhost/", quick_report={"records": records, "topIssues": all_issues[:3], "allIssues": all_issues}, journey_report={}, preflight={})
    normalized = normalize_findings(candidates, context_version="test")
    assert not normalized["normalizationErrors"]
    assert len(normalized["findings"]) == 7
    assert all(row["issueType"] == "VISUAL_FRICTION" and row["verificationState"] == "NOT_VERIFIED" for row in normalized["findings"])
    recipes = build_repair_recipes(normalized["findings"], confirmed_ids=[row["ruleId"] for row in normalized["findings"]])
    assert all(row["evidenceClass"] == "REPAIR_HINT" for row in recipes)
    raw_recipes = build_repair_recipes(all_issues, confirmed_ids=[row["id"] for row in all_issues])
    assert all(row["evidenceClass"] == "REPAIR_HINT" for row in raw_recipes)
    work = build_visual_review_work(records, all_issues)
    assert len(work["candidates"]) == 7 and work["screenshots"][0]["viewportRef"] == "screenshots/mobile.png"
    assert work["review"]["status"] == "NOT_REVIEWED" and work["assetGeneration"]["executed"] is False


@pytest.mark.parametrize("missing", ["evidence", "changes", "redlines"])
def test_visual_approval_rejects_missing_evidence_or_unresolved_work(missing):
    review = review_template()
    review.update(status="APPROVED", evidenceRefs=["after-mobile.png"])
    for value in review["dimensions"].values():
        value.update(score=85, reason="Observed in the cited screenshot")
    if missing == "evidence":
        review["evidenceRefs"] = []
    elif missing == "changes":
        review["changesRequired"] = ["Primary labels still wrap badly"]
    else:
        review["hardRedLines"] = ["Main action is hidden"]
    with pytest.raises(ContractViolation, match="VISUAL_REVIEW_INVALID"):
        normalize_visual_review(review)


def test_scoped_technical_verification_does_not_claim_visual_acceptance():
    result = build_task_result({"mode": "FIX_AND_VERIFY", "status": "VERIFIED", "visualReviewWork": build_visual_review_work([], [])})
    assert result["outcome"] == "VERIFIED"
    assert "visual finish has not been accepted" in result["claims"][0]["claim"]
    assert any("页面视觉完成度尚未确认" in value for value in result["uncertainties"])
    assert "visualReviewWork" in result["nextAction"]


def test_box_center_does_not_pass_a_visible_graphic_that_is_off_center(page):
    icon_svg = "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'><rect x='2' y='8' width='7' height='8'/></svg>"
    import urllib.parse
    source = "data:image/svg+xml," + urllib.parse.quote(icon_svg, safe="")
    css = f".icon-wrap{{display:flex;align-items:center;justify-content:center;width:48px;height:48px;background:#d9eee1}}.icon{{display:block;width:24px;height:24px;background:#168045;mask-image:url('{source}');mask-size:contain;mask-position:center;mask-repeat:no-repeat}}"
    raw = measure(page, "<span class='icon-wrap'><span class='icon'></span></span>", css)
    graphic = measure_icon_graphics(page, "<span class='icon-wrap'><span class='icon'></span></span>", css)
    assert raw["visualReviewCandidates"]["iconBoxMisalignment"] == []
    assert len(graphic["candidates"]["visibleGraphicMisalignment"]) == 1
    sample = graphic["samples"][0]
    assert sample["centers"]["surface"] and sample["centers"]["elementBox"] and sample["centers"]["visibleGraphicBounds"]
    assert sample["visualCenterStatus"] == "NOT_AUTO_PASSED"
    assert sample["sourceOwner"]["status"] == "NOT_CONFIRMED"


def test_selected_sprite_cell_reports_exact_css_crop_and_edge_ink(page):
    source = png_data_uri(96, 96, [(28, 28, 42, 42), (46, 34, 48, 36), (62, 29, 82, 47)])
    css = f".icon-wrap{{display:flex;width:48px;height:48px;background:#d9eee1}}.icon{{display:block;width:24px;height:24px;background:#168045;mask-image:url('{source}');mask-size:400% 400%;mask-position:33.333333% 33.333333%;mask-repeat:no-repeat}}"
    report = measure_icon_graphics(page, "<span class='icon-wrap'><span class='icon icon-raster'></span></span>", css)
    assert len(report["candidates"]["spriteEdgeResidue"]) == 1
    item = report["candidates"]["spriteEdgeResidue"][0]
    assert item["resource"]["path"].startswith("data:image/png;base64,")
    assert item["crop"]["kind"] == "CSS_MASK_IMAGE"
    assert item["crop"]["grid"] == {"columns": 4, "rows": 4, "column": 1, "row": 1}
    assert item["crop"]["edgeInkPixels"] >= 2
    assert item["assetUse"]["selector"] == "span.icon.icon-raster"
    assert item["sourceOwner"]["status"] == "NOT_CONFIRMED"


def test_asymmetric_but_centered_glyph_and_independent_png_are_not_sprite_defects(page):
    import urllib.parse
    arrow = "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'><path d='M4 12h16M14 6l6 6-6 6' fill='none' stroke='black' stroke-width='2'/></svg>"
    svg_url = "data:image/svg+xml," + urllib.parse.quote(arrow, safe="")
    independent_png = png_data_uri(24, 24, [(6, 6, 18, 18)])
    css = f".icon-wrap{{display:flex;align-items:center;justify-content:center;width:48px;height:48px;background:#d9eee1}}.icon{{display:block;width:24px;height:24px;background:#168045;mask-size:contain;mask-position:center;mask-repeat:no-repeat}}.arrow{{mask-image:url('{svg_url}')}}.map-pin{{mask-image:url('{independent_png}')}}"
    report = measure_icon_graphics(page, "<span class='icon-wrap'><span class='icon arrow'></span></span><span class='icon-wrap'><span class='icon map-pin'></span></span>", css)
    assert report["candidates"]["visibleGraphicMisalignment"] == []
    assert report["candidates"]["visibleGraphicUnderfill"] == []
    assert report["candidates"]["spriteEdgeResidue"] == []
    png_item = next(item for item in report["samples"] if "map-pin" in item["selector"])
    assert png_item["resource"]["path"].startswith("data:image/png;base64,")
    assert png_item["crop"]["gridLike"] is False


def test_small_visible_mark_is_measured_separately_from_centered_icon_box(page):
    import urllib.parse
    tiny = "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'><circle cx='12' cy='12' r='2'/></svg>"
    source = "data:image/svg+xml," + urllib.parse.quote(tiny, safe="")
    css = f".mini-icon{{display:flex;align-items:center;justify-content:center;width:48px;height:48px;background:#d9eee1}}.icon{{display:block;width:24px;height:24px;background:#168045;mask-image:url('{source}');mask-size:contain;mask-position:center;mask-repeat:no-repeat}}"
    report = measure_icon_graphics(page, "<span class='mini-icon'><span class='icon'></span></span>", css)
    assert len(report["candidates"]["visibleGraphicUnderfill"]) == 1
    sample = report["candidates"]["visibleGraphicUnderfill"][0]
    assert sample["offsets"]["visibleBoundsVsElementBox"] == {"x": 0, "y": 0}
    assert sample["graphicBoundsFill"]["linearRatio"] < .20


def test_icon_aligned_within_a_data_tile_is_not_compared_to_the_whole_tile_center(page):
    source = png_data_uri(24, 24, [(3, 3, 21, 21)])
    css = f".data-tile{{display:flex;flex-direction:column;align-items:center;width:72px;height:92px;background:#eef7f1}}.icon{{display:block;width:24px;height:24px;background:#168045;mask-image:url('{source}');mask-size:contain;mask-position:center;mask-repeat:no-repeat}}"
    report = measure_icon_graphics(page, "<div class='data-tile'><span class='icon'></span><strong>0</strong><small>今日上传</small></div>", css)
    sample = report["samples"][0]
    assert sample["surfaceSelector"] is None
    assert report["candidates"]["visibleGraphicMisalignment"] == []
    assert report["candidates"]["visibleGraphicUnderfill"] == []


def test_repeated_list_rows_measure_same_role_text_ranges_even_when_row_boxes_align(page):
    markup = """<ul>
      <li><span aria-hidden="true"><svg viewBox="0 0 16 16"><circle cx="8" cy="8" r="6"/></svg></span><section><h3>短标题</h3><p>一段用途说明</p></section><span aria-hidden="true"><svg viewBox="0 0 16 16"><path d="m5 3 5 5-5 5"/></svg></span></li>
      <li><span aria-hidden="true"><svg viewBox="0 0 16 16"><circle cx="8" cy="8" r="6"/></svg></span><section><h3>长度明显不同的标题</h3><p>另一段用途说明文字</p></section><span aria-hidden="true"><svg viewBox="0 0 16 16"><path d="m5 3 5 5-5 5"/></svg></span></li>
      <li><span aria-hidden="true"><svg viewBox="0 0 16 16"><circle cx="8" cy="8" r="6"/></svg></span><section><h3>中等长度标题</h3><p>第三项说明</p></section><span aria-hidden="true"><svg viewBox="0 0 16 16"><path d="m5 3 5 5-5 5"/></svg></span></li>
    </ul>"""
    css = "ul{display:grid;gap:6px;padding:0;list-style:none;width:100%}li{display:grid;grid-template-columns:24px minmax(0,1fr) 24px;gap:8px;width:100%;padding:8px}section{min-width:0;text-align:center}h3,p{display:block;margin:0}h3{font-size:16px;font-weight:700}p{font-size:12px}svg{display:block;width:16px;height:16px}"
    raw = measure(page, markup, css)
    candidates = raw["visualReviewCandidates"]["repeatedRowTextAlignment"]
    assert len(candidates) == 1
    item = candidates[0]
    assert item["rowCount"] == 3
    assert item["evidence"]["rowWidthSpreadPx"] == 0
    assert item["evidence"]["textRangeStartSpreadPx"]["emphasized_text"] > 0
    assert item["evidence"]["textRangeStartSpreadPx"]["supporting_text"] > 0
    assert len(item["evidence"]["rows"]) == 3
    first_title = item["evidence"]["rows"][0]["textRoles"]["emphasized_text"]
    assert first_title["measurement"] == "DOM_RANGE_CLIENT_RECT_NOT_GLYPH_BOUNDS"
    assert first_title["textBlockSelector"].endswith("h3")
    assert "text range starts vary" in item["evidence"]["summary"]


def test_repeated_rows_find_variable_width_and_tail_drift_across_changed_tags(page):
    markup = """<div>
      <button><span><svg viewBox="0 0 16 16"><circle cx="8" cy="8" r="6"/></svg></span><div><b>Open item</b><small>Waiting</small></div><span><svg viewBox="0 0 16 16"><path d="m5 3 5 5-5 5"/></svg></span></button>
      <button><span><svg viewBox="0 0 16 16"><circle cx="8" cy="8" r="6"/></svg></span><div><h4>A much longer title</h4><p>Waiting for one more review</p></div><span><svg viewBox="0 0 16 16"><path d="m5 3 5 5-5 5"/></svg></span></button>
      <button><span><svg viewBox="0 0 16 16"><circle cx="8" cy="8" r="6"/></svg></span><div><label>Mid length</label><small>Review in progress</small></div><span><svg viewBox="0 0 16 16"><path d="m5 3 5 5-5 5"/></svg></span></button>
    </div>"""
    css = "body>main>div{display:flex;flex-direction:column;align-items:flex-start;gap:6px}button{display:grid;grid-template-columns:24px max-content 16px;gap:6px;width:max-content;padding:8px;text-align:center}button>div{display:block}b,h4,label,small,p{display:block;margin:0}h4{font-weight:700}small,p{font-size:12px}svg{display:block;width:16px;height:16px}"
    raw = measure(page, markup, css)
    candidates = raw["visualReviewCandidates"]["repeatedRowTextAlignment"]
    assert len(candidates) == 1
    item = candidates[0]
    assert item["rowCount"] == 3
    assert "REPEATED_ROW_WIDTH_SPREAD" in item["evidence"]["causes"]
    assert "TRAILING_VISUAL_INLINE_END_SPREAD" in item["evidence"]["causes"]
    assert "SAME_ROLE_TEXT_RANGE_INLINE_START_SPREAD" in item["evidence"]["causes"]
    assert len(set(item["evidence"]["rowSelectors"])) == 3
    assert all(row["trailingVisual"] for row in item["evidence"]["rows"])
    assert all(row["textRoles"] for row in item["evidence"]["rows"])


def test_repeated_row_group_recognizes_nested_css_painted_leading_marks(page):
    markup = "<div><button><span><i></i></span><div><b>First</b><small>One</small></div><span>›</span></button><button><span><i></i></span><div><b>Another longer title</b><small>Two</small></div><span>›</span></button><button><span><i></i></span><div><b>Third</b><small>Three</small></div><span>›</span></button></div>"
    css = "body>main>div{display:flex;flex-direction:column;align-items:flex-start}button{display:grid;grid-template-columns:24px max-content 16px;gap:6px;width:max-content;padding:8px;text-align:center}button>span:first-child i{display:block;width:16px;height:16px;background-image:linear-gradient(#000,#000)}b,small{display:block;margin:0}small{font-size:12px}"
    raw = measure(page, markup, css)
    candidates = raw["visualReviewCandidates"]["repeatedRowTextAlignment"]
    assert len(candidates) == 1
    assert candidates[0]["rowCount"] == 3
    assert "REPEATED_ROW_WIDTH_SPREAD" in candidates[0]["evidence"]["causes"]


def test_repeated_row_text_start_uses_group_position_when_content_tracks_shift(page):
    markup = "<ul><li style='--lead:24px'><span>◉</span><div><b>First</b><small>One</small></div><span>›</span></li><li style='--lead:40px'><span>◉</span><div><b>Second</b><small>Two</small></div><span>›</span></li><li style='--lead:32px'><span>◉</span><div><b>Third</b><small>Three</small></div><span>›</span></li></ul>"
    css = "ul{padding:0;list-style:none;width:100%}li{display:grid;grid-template-columns:var(--lead) minmax(0,1fr) 20px;gap:8px;width:100%;text-align:start}b,small{display:block;margin:0}small{font-size:12px}"
    raw = measure(page, markup, css)
    candidates = raw["visualReviewCandidates"]["repeatedRowTextAlignment"]
    assert len(candidates) == 1
    evidence = candidates[0]["evidence"]
    assert evidence["rowWidthSpreadPx"] == 0
    assert "SAME_ROLE_TEXT_RANGE_INLINE_START_SPREAD" in evidence["causes"]
    assert evidence["textRangeStartSpreadPx"]["emphasized_text"] == 16
    assert evidence["textOffsetWithinContentSpreadPx"]["emphasized_text"] == 0


def test_correct_left_lists_centered_controls_stats_rtl_and_tree_indentation_are_not_flagged(page):
    aligned_list = "<ul><li><span>◉</span><div><b>First</b><small>One</small></div><span>›</span></li><li><span>◉</span><div><b>Second, longer</b><small>Two</small></div><span>›</span></li><li><span>◉</span><div><b>Third</b><small>Three</small></div><span>›</span></li></ul>"
    css = "ul{padding:0;list-style:none;width:100%}li{display:grid;grid-template-columns:24px minmax(0,1fr) 20px;gap:8px;width:100%;text-align:start}b,small{display:block;margin:0}small{font-size:12px}"
    assert measure(page, aligned_list, css)["visualReviewCandidates"]["repeatedRowTextAlignment"] == []

    centered = "<div class='stats'><article><span>New</span><strong>12</strong></article><article><span>Open</span><strong>3</strong></article><article><span>Done</span><strong>8</strong></article></div><div class='actions'><button>Save</button><button>Cancel</button><button>More options</button></div>"
    centered_css = ".stats{display:grid;grid-template-columns:repeat(3,1fr)}.stats article{text-align:center}.actions{display:flex;gap:8px}.actions button{min-height:44px}"
    assert measure(page, centered, centered_css)["visualReviewCandidates"]["repeatedRowTextAlignment"] == []

    horizontal = "<ul aria-orientation='horizontal'><li><span>◉</span><div><b>Overview</b><small>First</small></div><span>›</span></li><li><span>◉</span><div><b>Activity</b><small>Second</small></div><span>›</span></li><li><span>◉</span><div><b>Settings</b><small>Third</small></div><span>›</span></li></ul>"
    horizontal_css = "ul{display:flex;justify-content:center;gap:8px;padding:0;list-style:none}li{display:grid;grid-template-columns:24px max-content 16px;gap:4px;text-align:center}b,small{display:block;margin:0}small{font-size:12px}"
    assert measure(page, horizontal, horizontal_css)["visualReviewCandidates"]["repeatedRowTextAlignment"] == []

    rtl = "<ul dir='rtl'><li><span>◉</span><div><b>العنصر الأول</b><small>وصف قصير</small></div><span>‹</span></li><li><span>◉</span><div><b>العنصر الثاني الأطول</b><small>وصف آخر</small></div><span>‹</span></li></ul>"
    rtl_css = "ul{padding:0;list-style:none;width:100%}li{display:grid;grid-template-columns:24px minmax(0,1fr) 20px;gap:8px;width:100%;text-align:start}b,small{display:block;margin:0}small{font-size:12px}"
    assert measure(page, rtl, rtl_css)["visualReviewCandidates"]["repeatedRowTextAlignment"] == []

    tree = "<div role='tree'><div role='treeitem' aria-level='1' style='margin-inline-start:0'><span>◉</span><b>Parent</b><span>›</span></div><div role='treeitem' aria-level='2' style='margin-inline-start:20px'><span>◉</span><b>Child</b><span>›</span></div><div role='treeitem' aria-level='3' style='margin-inline-start:40px'><span>◉</span><b>Nested child</b><span>›</span></div></div>"
    tree_css = "[role=treeitem]{display:grid;grid-template-columns:24px 1fr 20px;gap:8px;width:100%}"
    assert measure(page, tree, tree_css)["visualReviewCandidates"]["repeatedRowTextAlignment"] == []


def test_repeated_row_candidate_survives_public_report_top_three_and_host_repair_handoff():
    measured = {"selector": "ul", "styleSelector": "ul", "rowCount": 3,
                "evidence": {"metric": "REPEATED_ROW_TEXT_AND_TRAILING_ALIGNMENT",
                             "summary": "emphasized text range starts vary by 12px; trailing visual end gaps vary by 9px",
                             "rows": [{"rowSelector": "ul > li:nth-of-type(1)", "rowWidthPx": 320,
                                       "textRoles": {"emphasized_text": {"selector": "ul > li:nth-of-type(1) > section > h3",
                                                                            "measurement": "DOM_RANGE_CLIENT_RECT_NOT_GLYPH_BOUNDS"}},
                                       "trailingVisual": {"selector": "ul > li:nth-of-type(1) > span:nth-of-type(2)"}}]},
                "claimBoundary": "Text Range boxes are not painted glyph bounds; screenshot review required."}
    findings = _composition_findings({"repeatedRowTextAlignment": [measured]})
    findings.extend({"id": f"BLOCKER-{index}", "severity": "P1", "title": "higher priority issue",
                     "samples": [{}], "evidenceClass": "FORMAL_FINDING"} for index in range(3))
    records = [{"status": "PASS", "pageHealth": {"pageStatus": "REAL_PAGE_READY"},
                "viewport": {"width": 390, "height": 844},
                "screenshotRef": "screenshots/mobile.png",
                "renderedQuality": {"findings": findings}}]
    all_issues = summarize_top_ui_issues(records, limit=None)
    top_issues = summarize_top_ui_issues(records)
    row_issue = next(issue for issue in all_issues if issue["id"] == "RENDER-REPEATED-ROW-ALIGNMENT")
    assert row_issue not in top_issues
    assert row_issue["samples"][0]["evidence"]["evidence"]["rows"][0]["textRoles"]["emphasized_text"]["measurement"] == "DOM_RANGE_CLIENT_RECT_NOT_GLYPH_BOUNDS"
    candidates = _finding_candidates(url="http://localhost/", quick_report={"records": records,
                                                                           "topIssues": top_issues,
                                                                           "allIssues": all_issues},
                                    journey_report={}, preflight={})
    locator = next(item for item in candidates if item.get("ruleId") == "RENDER-REPEATED-ROW-ALIGNMENT")
    assert locator["semanticTarget"] == "ul"
    assert locator["evidenceRefs"] == ["screenshots/mobile.png"]
    recipes = build_repair_recipes(all_issues)
    recipe = next(item for item in recipes if "RENDER-REPEATED-ROW-ALIGNMENT" in item["findingIds"])
    assert recipe["recommendedRepair"] == row_issue["recommendation"] and recipe["recommendedRepair"]
    work = build_visual_review_work(records, all_issues)
    host_item = next(item for item in work["candidates"] if item["ruleId"] == "RENDER-REPEATED-ROW-ALIGNMENT")
    assert host_item["samples"][0]["evidence"]["evidence"]["rows"][0]["rowSelector"] == "ul > li:nth-of-type(1)"
    assert host_item["repairDirection"] == recipe["recommendedRepair"]
