"""Browser-gate exactly three source-backed candidates and present them as design work."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from html import escape
import json
from pathlib import Path
import shutil
from typing import Any

from .production_validation import validate_transformation
from .release_info import PACKAGE_VERSION, release_identity
from .visual_diff import compare_images


VIEWPORT_IDS = ("desktop", "tablet", "mobile")


def _browser_score(report: Mapping[str, Any]) -> tuple[int, list[str]]:
    reasons: list[str] = []
    score = 0
    if report.get("status") == "PASS":
        score += 35; reasons.append("三视口 Browser 验收无警告")
    elif report.get("status") == "PASS_WITH_WARNINGS":
        score += 25; reasons.append("Browser 验收通过但仍有警告")
    journey = [item for item in report.get("journey", []) if isinstance(item, Mapping)]
    if journey and all(item.get("status") == "PASS" for item in journey):
        score += 20; reasons.append("关键任务旅程完整通过")
    records = [item for item in report.get("records", []) if isinstance(item, Mapping) and item.get("label") == "after"]
    if records and not any(item.get("horizontalOverflow") for item in records):
        score += 10; reasons.append("桌面、平板和手机均无页面级横向溢出")
    if records and not any(item.get("console") or item.get("pageErrors") for item in records):
        score += 10; reasons.append("无控制台或页面运行时错误")
    if records and all(item.get("metrics", {}).get("keyboard", {}).get("status") == "PASS" for item in records):
        reasons.append("桌面、平板和手机键盘焦点抽样均通过")
    if records and not any(int(item.get("metrics", {}).get("smallControlCount", 0)) for item in records):
        score += 10; reasons.append("可见操作目标满足最小尺寸要求")
    diffs = [item for item in report.get("visualDiff", []) if isinstance(item, Mapping)]
    if len(diffs) == 3 and all(item.get("status") == "COMPUTED" and float(item.get("changedPixelRatio", 0)) > .005 for item in diffs):
        score += 15; reasons.append("三个视口均检测到实质视觉变化")
    return min(score, 100), reasons


def _pairwise_distinctness(records: Sequence[Mapping[str, Any]], validation_root: Path) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    diff_root = validation_root / "candidate-diffs"
    for left_index, left in enumerate(records):
        for right in records[left_index + 1:]:
            pair_id = f"{left['pathId']}--{right['pathId']}"
            viewport_results = []
            for viewport in VIEWPORT_IDS:
                left_image = validation_root / "variants" / str(left["pathId"]) / "screenshots" / "after" / f"{viewport}.png"
                right_image = validation_root / "variants" / str(right["pathId"]) / "screenshots" / "after" / f"{viewport}.png"
                diff_path = diff_root / pair_id / f"{viewport}.png"
                diff_path.parent.mkdir(parents=True, exist_ok=True)
                result = compare_images(left_image, right_image, diff_path=diff_path)
                viewport_results.append({"viewport": viewport, **result, "diffRef": f"validation/candidate-diffs/{pair_id}/{viewport}.png"})
            computed = [item for item in viewport_results if item.get("status") == "COMPUTED"]
            minimum = min((float(item.get("changedPixelRatio", 0)) for item in computed), default=0)
            results.append({
                "left": left["id"], "right": right["id"], "viewports": viewport_results,
                "status": "MATERIALLY_DISTINCT" if len(computed) == 3 and minimum >= .01 else "TOO_SIMILAR",
                "minimumChangedPixelRatio": round(minimum, 6),
            })
    return results


def _gallery_html_legacy(report: Mapping[str, Any]) -> str:
    cards = []
    selected = report.get("selectedVariantId")
    for index, item in enumerate(report.get("variants", [])):
        if not isinstance(item, Mapping):
            continue
        path_id = escape(str(item.get("pathId")))
        variant_id = escape(str(item.get("id")))
        name = escape(str(item.get("name")))
        recipe = item.get("recipe") if isinstance(item.get("recipe"), Mapping) else {}
        concept = item.get("designConcept") if isinstance(item.get("designConcept"), Mapping) else {}
        badge = '<span class="badge selected">Browser 推荐</span>' if item.get("id") == selected else f'<span class="badge">方向 {index + 1}</span>'
        reasons = "".join(f"<li>{escape(str(value))}</li>" for value in item.get("reviewReasons", [])[:4])
        if item.get("screenshotsAvailable"):
            preview = f'<div class="frame"><img loading="lazy" src="../validation/variants/{path_id}/screenshots/after/desktop.png" data-base="../validation/variants/{path_id}/screenshots/after/" alt="{name} desktop preview"></div>'
        else:
            preview = f'<div class="frame missing" role="status"><div><strong>尚无 Browser 截图</strong><p>{escape(str(item.get("browserReason") or "浏览器运行环境尚未就绪"))}</p><code>web-ui-quality doctor</code></div></div>'
        entry = str(item.get("runnableEntry") or "")
        open_candidate = (
            f'<a href="../implementation/generated-preview/variants/{path_id}/{escape(entry)}">打开可运行版本 <span aria-hidden="true">↗</span></a>'
            if entry else '<span class="source-only">框架源码候选 · 请在项目构建环境运行</span>'
        )
        cards.append(f"""<article class="candidate" data-variant="{variant_id}">
          <div class="candidate-head"><div>{badge}<span class="concept">{escape(str(concept.get('name') or concept.get('archetype') or '项目语义方案'))}</span><h2>{name}</h2><p>{escape(str(recipe.get('promise', '')))}</p></div><strong>{escape(str(item.get('reviewScore')))}<small>/100</small></strong></div>
          {preview}
          <div class="candidate-foot"><ul>{reasons}</ul><div class="candidate-actions"><button class="choose" data-select="{variant_id}" type="button">选择这个方向</button>{open_candidate}</div></div>
          <label class="notes">给这个方向的备注<textarea data-note="{variant_id}" rows="2" placeholder="例如：保留导航，但降低卡片圆角"></textarea></label>
        </article>""")
    distinct = "".join(
        f"<li><b>{escape(str(item.get('left')))}</b> vs <b>{escape(str(item.get('right')))}</b><span>{escape(str(item.get('status')))} · {escape(str(item.get('minimumChangedPixelRatio')))}</span></li>"
        for item in report.get("pairwiseDistinctness", []) if isinstance(item, Mapping)
    )
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Web UI Quality {PACKAGE_VERSION} · Design Gallery</title><style>
:root{{--ink:#111a16;--muted:#66716b;--paper:#edf2ef;--surface:#fff;--line:#dbe3de;--brand:#176b52;--soft:#dff3e9;font-family:Inter,"Segoe UI","PingFang SC",sans-serif}}*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink)}}main{{max-width:1440px;margin:auto;padding:28px clamp(16px,4vw,58px) 90px}}header{{min-height:360px;padding:clamp(30px,6vw,76px);border-radius:32px;background:#10251d;color:#fff;display:grid;align-content:end;position:relative;overflow:hidden}}header::after{{content:"";position:absolute;width:420px;height:420px;border-radius:50%;background:#2c8a6a;filter:blur(110px);opacity:.45;right:-90px;top:-160px}}header>*{{position:relative;z-index:1}}.eyebrow{{font-size:12px;letter-spacing:.16em;text-transform:uppercase;color:#9bd4bd}}h1{{font-size:clamp(48px,8vw,104px);line-height:.9;letter-spacing:-.07em;margin:16px 0;max-width:900px}}header p{{max-width:720px;color:#c2d4cc;font-size:17px;line-height:1.7}}.controls{{display:flex;gap:8px;position:sticky;top:12px;z-index:10;margin:22px 0;padding:8px;width:max-content;background:#ffffffdd;border:1px solid var(--line);border-radius:14px;backdrop-filter:blur(16px)}}.controls button{{border:0;background:transparent;border-radius:9px;padding:10px 14px;color:var(--muted);font-weight:700}}.controls button[aria-pressed="true"]{{background:var(--ink);color:#fff}}.gallery{{display:grid;gap:28px}}.candidate{{background:var(--surface);border:1px solid var(--line);border-radius:28px;padding:clamp(16px,2.5vw,30px);box-shadow:0 24px 70px rgba(24,48,38,.08)}}.candidate-head{{display:flex;align-items:start;justify-content:space-between;gap:20px;margin-bottom:20px}}.candidate h2{{font-size:clamp(28px,3vw,42px);letter-spacing:-.04em;margin:10px 0 6px}}.candidate p{{color:var(--muted);margin:0;max-width:680px;line-height:1.6}}.candidate strong{{font-size:46px;letter-spacing:-.05em;color:var(--brand)}}.candidate strong small{{font-size:12px;color:var(--muted)}}.badge{{display:inline-block;background:#eef1ef;color:#53615a;padding:6px 9px;border-radius:99px;font-size:11px;font-weight:800}}.badge.selected{{background:var(--soft);color:var(--brand)}}.frame{{overflow:auto;border-radius:18px;background:#dfe6e2;padding:10px;text-align:center}}.frame img{{display:block;width:100%;height:auto;margin:auto;border-radius:10px;box-shadow:0 14px 34px #0002}}.frame[data-device="tablet"] img{{width:min(100%,768px)}}.frame[data-device="mobile"] img{{width:min(100%,390px)}}.candidate-foot{{display:grid;grid-template-columns:1fr auto;align-items:end;gap:20px;margin-top:16px}}ul{{padding-left:20px;color:var(--muted);line-height:1.7}}.candidate-foot a{{background:var(--ink);color:#fff;text-decoration:none;padding:13px 16px;border-radius:12px;font-weight:800;white-space:nowrap}}.proof{{margin-top:28px;background:#fff;border:1px solid var(--line);padding:26px;border-radius:24px}}.proof li{{display:flex;justify-content:space-between;gap:16px;border-bottom:1px solid var(--line);padding-block:10px}}.proof li span{{color:var(--muted)}}@media(max-width:720px){{header{{min-height:300px}}.candidate-foot{{grid-template-columns:1fr}}.candidate-foot a{{text-align:center}}.proof li{{display:block}}}}
</style></head><body><main><header><span class="eyebrow">Web UI Quality {PACKAGE_VERSION} · Design Work</span><h1>三个可以运行的升级作品</h1><p>不是三段建议，也不是几套换色主题。每个方向都拥有独立源码、布局、密度、导航策略、三视口截图和关键旅程验证。</p></header><div class="controls" role="group" aria-label="预览设备"><button data-device="desktop" aria-pressed="true">桌面</button><button data-device="tablet" aria-pressed="false">平板</button><button data-device="mobile" aria-pressed="false">手机</button></div><section class="gallery">{''.join(cards)}</section><section class="proof"><h2>方案差异证明</h2><ul>{distinct}</ul><p>自动选择采用“产品诊断优先、Browser 验收否决”的规则。像素差异用于证明方案不是同一主题换色，不被当作审美或业务提升结论。</p></section></main><script>
const buttons=[...document.querySelectorAll('[data-device]')];buttons.forEach(button=>button.addEventListener('click',()=>{{const device=button.dataset.device;buttons.forEach(item=>item.setAttribute('aria-pressed',String(item===button)));document.querySelectorAll('.frame').forEach(frame=>{{frame.dataset.device=device;const image=frame.querySelector('img');if(image){{image.src=image.dataset.base+device+'.png';image.alt=image.alt.replace(/ (desktop|tablet|mobile) preview$/,` ${{device}} preview`)}}}})}}));
</script></body></html>"""


def _gallery_html(report: Mapping[str, Any]) -> str:
    """Upgrade the gallery into a local decision surface without a server."""
    html = _gallery_html_legacy(report)
    verified = report.get("status") == "DESIGN_GALLERY_PASS"
    readiness = (
        "候选方案已完成无警告 Browser 验收，可以比较并导出选择。"
        if verified
        else "设计候选已经生成，但 Browser 证据尚未完成；这里不会伪造截图或显示破损图片。"
    )
    decision = """<section class="decision"><h2>形成设计决策</h2><p id="selection-copy">尚未选择方向。</p><div class="decision-grid">
      <label>目标密度<select id="density"><option value="preserve">沿用项目</option><option value="compact">更紧凑</option><option value="comfortable">更舒展</option></select></label>
      <label>品牌策略<select id="brand"><option value="preserve">保留现有品牌 Token</option><option value="refine">保留品牌、修正对比</option><option value="explore">允许探索新方向</option></select></label>
      <button class="download" id="download" type="button">下载 design-decision.json</button>
    </div><p>下载后运行：<code>web-ui-quality finalize-design &lt;upgrade-output&gt; design-decision.json</code></p></section>"""
    extra_css = """<style>
.readiness{margin:18px 0 0;padding:14px 16px;border:1px solid #ffffff24;border-radius:14px;background:#ffffff0d;color:#d9e9e2}.concept{display:block;margin-top:8px;color:var(--muted);font-size:11px;letter-spacing:.12em;text-transform:uppercase}.candidate{border:2px solid transparent}.candidate.is-chosen{border-color:var(--brand)}.frame{min-height:180px}.frame.missing{display:grid;place-items:center;padding:36px;background:repeating-linear-gradient(135deg,#edf1ef,#edf1ef 14px,#e4eae7 14px,#e4eae7 28px)}.frame.missing div{max-width:560px;padding:28px;border-radius:18px;background:#fff}.frame.missing strong{font-size:22px}.frame code,.decision code{display:inline-block;margin-top:10px;padding:7px 9px;border-radius:8px;background:#10251d;color:#fff}.candidate-actions{display:grid;gap:8px}.candidate-actions a,.choose,.download{border:0;background:var(--ink);color:#fff;text-decoration:none;padding:13px 16px;border-radius:12px;font-weight:800;text-align:center}.choose{background:var(--soft);color:var(--brand);cursor:pointer}.source-only{max-width:250px;color:var(--muted);font-size:12px}.notes{display:grid;gap:7px;margin-top:16px;color:var(--muted);font-size:12px}.notes textarea{resize:vertical;padding:12px;border:1px solid var(--line);border-radius:12px;font:inherit}.decision{margin-top:28px;background:#fff;border:1px solid var(--line);padding:26px;border-radius:24px}.decision-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:14px;align-items:end}.decision label{display:grid;gap:8px;color:var(--muted)}.decision select{padding:11px;border:1px solid var(--line);border-radius:10px;font:inherit}
</style>"""
    initial = json.dumps(report.get("selectedVariantId"), ensure_ascii=False)
    decision_script = f"""<script>
const initialSelection={initial};let chosen=initialSelection;const cards=[...document.querySelectorAll('.candidate')];const selectionCopy=document.getElementById('selection-copy');function choose(id){{chosen=id;cards.forEach(card=>card.classList.toggle('is-chosen',card.dataset.variant===id));selectionCopy.textContent=`已选择：${{id}}。下载决策文件后可重新生成对应补丁。`;localStorage.setItem('wuq-design-selection',id)}}document.querySelectorAll('[data-select]').forEach(button=>button.addEventListener('click',()=>choose(button.dataset.select)));const stored=localStorage.getItem('wuq-design-selection');if(stored&&cards.some(card=>card.dataset.variant===stored))choose(stored);else if(initialSelection)choose(initialSelection);document.querySelectorAll('[data-note]').forEach(field=>{{const key='wuq-note-'+field.dataset.note;field.value=localStorage.getItem(key)||'';field.addEventListener('input',()=>localStorage.setItem(key,field.value))}});document.getElementById('download').addEventListener('click',()=>{{if(!chosen){{selectionCopy.textContent='请先选择一个方向。';return}}const decision={{schemaVersion:'1',selectedVariantId:chosen,preferences:{{density:document.getElementById('density').value,brand:document.getElementById('brand').value}},notes:Object.fromEntries([...document.querySelectorAll('[data-note]')].map(field=>[field.dataset.note,field.value])),source:'web-ui-quality-design-gallery'}};const blob=new Blob([JSON.stringify(decision,null,2)+'\\n'],{{type:'application/json'}});const link=document.createElement('a');link.href=URL.createObjectURL(blob);link.download='design-decision.json';link.click();setTimeout(()=>URL.revokeObjectURL(link.href),1000)}});
</script>"""
    html = html.replace(f"<title>Web UI Quality {PACKAGE_VERSION} · Design Gallery</title>", f"<title>Web UI Quality {PACKAGE_VERSION} · Design Decision Workbench</title>")
    html = html.replace(f"Web UI Quality {PACKAGE_VERSION} · Design Work", f"Web UI Quality {PACKAGE_VERSION} · Design Decision")
    if not verified:
        html = html.replace(
            "每个方向都拥有独立源码、布局、密度、导航策略、三视口截图和关键旅程验证。",
            "每个方向都拥有独立源码、布局、密度和导航策略；三视口截图与关键旅程仍等待 Browser 环境验证。",
        )
    html = html.replace("</p></header>", f"</p><div class=\"readiness\">{escape(readiness)}</div></header>", 1)
    html = html.replace('<section class="proof">', decision + '<section class="proof">', 1)
    html = html.replace("</head>", extra_css + "</head>", 1)
    html = html.replace("</body>", decision_script + "</body>", 1)
    return html


def _decision_brief_markdown(report: Mapping[str, Any]) -> str:
    variants = [item for item in report.get("variants", []) if isinstance(item, Mapping)]
    selected = next((item for item in variants if item.get("id") == report.get("selectedVariantId")), None)
    discovery = report.get("productDiscovery") if isinstance(report.get("productDiscovery"), Mapping) else {}
    readiness = "候选方案已通过 Browser 验证，等待负责人确认。" if report.get("status") == "DESIGN_GALLERY_PASS" else "源码候选方案已生成，Browser 证据尚未完成。"
    lines = [
        "# 设计决策简报",
        "",
        f"- 当前状态：{readiness}",
        "- 原项目：未修改",
        "- 当前动作：比较候选作品并确认一个方向",
        "",
    ]
    if discovery:
        role_labels = "、".join(str(value) for value in discovery.get("roles", [])) or "尚未确认具体角色"
        lines.extend([
            "## 系统理解",
            "",
            str(discovery.get("productJob") or "已从项目证据重建产品任务。"),
            "",
            f"- 已识别角色：{role_labels}",
            f"- 识别置信度：{discovery.get('confidencePercent', 0)}%",
            "- 证据详情：`../system-understanding/index.html`",
            "",
        ])
    lines.extend(["## 系统推荐", ""])
    if selected:
        recipe = selected.get("recipe") if isinstance(selected.get("recipe"), Mapping) else {}
        lines.extend([
            f"**{selected.get('name')}**",
            "",
            str(recipe.get("promise") or "该方向最符合当前产品诊断。"),
            "",
            f"- 适合：{selected.get('outcome') or '希望优先改善核心任务的团队'}",
            f"- 需要接受：{selected.get('tradeoff') or '仍需负责人确认设计偏好'}",
        ])
    else:
        lines.append("Browser 证据尚未形成推荐，请由负责人先完成视觉评审。")
    lines.extend(["", "## 候选方案", "", "| 方向 | 适合 | 主要代价 | 验证 |", "| --- | --- | --- | --- |"]) 
    for item in variants:
        lines.append(
            f"| {item.get('name')} | {item.get('outcome') or '待确认'} | {item.get('tradeoff') or '待确认'} | "
            f"{'已通过' if item.get('browserStatus') == 'PASS' else '待验证'} |"
        )
    lines.extend([
        "",
        "## 决策边界",
        "",
        "作品可运行且视觉差异已验证，不代表用户偏好或业务指标已经提升。确认方向后，应在隔离输出中生成最终补丁并复验。",
        "",
        "## 下一步",
        "",
        "打开 `design-gallery/index.html`，选择角色视图，统一切换 Before / After 和设备，确认方向后下载决策文件并交给 Codex 完成。",
        "",
    ])
    return "\n".join(lines)


def _gallery_html_v372(report: Mapping[str, Any]) -> str:
    """Render a role-aware decision workbench for non-technical reviewers."""
    verified = report.get("status") == "DESIGN_GALLERY_PASS"
    has_previews = any(isinstance(item, Mapping) and item.get("screenshotsAvailable") for item in report.get("variants", []))
    selected = report.get("selectedVariantId")
    cards: list[str] = []
    names: dict[str, str] = {}
    for index, item in enumerate(report.get("variants", [])):
        if not isinstance(item, Mapping):
            continue
        path_id = escape(str(item.get("pathId")))
        variant_id = escape(str(item.get("id")))
        raw_id = str(item.get("id"))
        name = escape(str(item.get("name") or f"方向 {index + 1}"))
        names[raw_id] = str(item.get("name") or f"方向 {index + 1}")
        recipe = item.get("recipe") if isinstance(item.get("recipe"), Mapping) else {}
        concept = item.get("designConcept") if isinstance(item.get("designConcept"), Mapping) else {}
        dna = concept.get("designDNA") if isinstance(concept.get("designDNA"), Mapping) else {}
        tone_value = dna.get("tone") if isinstance(dna.get("tone"), list) else []
        tone = "、".join(str(value) for value in tone_value[:3]) or "项目一致、任务清楚"
        badge = "系统推荐 · 仍需你确认" if item.get("id") == selected else f"备选方向 {index + 1}"
        proof = "三端已验证" if item.get("browserStatus") == "PASS" else "作品已生成 · 截图待验证"
        fit = escape(str(item.get("outcome") or "希望改善核心任务的团队"))
        tradeoff = escape(str(item.get("tradeoff") or "需要负责人确认视觉偏好和真实内容"))
        promise = escape(str(recipe.get("promise") or "围绕核心任务重新组织界面。"))
        concept_name = escape(str(concept.get("name") or concept.get("archetype") or "项目语义方案"))
        reasons = "".join(f"<li>{escape(str(value))}</li>" for value in item.get("reviewReasons", [])[:5])
        if item.get("screenshotsAvailable"):
            before_base = f"../validation/variants/{path_id}/screenshots/before/"
            after_base = f"../validation/variants/{path_id}/screenshots/after/"
            preview = (
                f'<button class="preview" type="button" data-preview="{variant_id}" aria-label="放大查看{name}">'
                f'<img loading="lazy" src="{after_base}desktop.png" data-before-base="{before_base}" '
                f'data-after-base="{after_base}" alt="{name} After 桌面预览"><span>点击放大审阅</span></button>'
            )
        else:
            preview = (
                '<div class="preview missing" role="status"><div><b>源码作品已经生成 · 尚无 Browser 截图</b>'
                f'<p>{escape(str(item.get("browserReason") or "当前环境没有完成 Browser 截图"))}</p>'
                '<span>可先评审方向；运行 <code>web-ui-quality doctor</code> 后补齐视觉证据。</span></div></div>'
            )
        entry = str(item.get("runnableEntry") or "")
        open_candidate = (
            f'<a class="text-link" href="../implementation/generated-preview/variants/{path_id}/{escape(entry)}">打开完整作品 ↗</a>'
            if entry else '<span class="source-only">框架源码候选需在项目构建环境打开</span>'
        )
        cards.append(f"""<article class="candidate" data-variant="{variant_id}" data-name="{name}">
          <div class="candidate-top"><span class="badge">{escape(badge)}</span><span class="proof-status">{escape(proof)}</span></div>
          <p class="concept">{concept_name}</p><h2>{name}</h2><p class="promise">{promise}</p>
          {preview}
          <div class="lens lens-general"><dl><div><dt>适合谁</dt><dd>{fit}</dd></div><div><dt>主要改变</dt><dd>{promise}</dd></div><div><dt>需要接受</dt><dd>{tradeoff}</dd></div></dl></div>
          <div class="lens lens-designer"><dl><div><dt>视觉气质</dt><dd>{escape(tone)}</dd></div><div><dt>信息密度</dt><dd>{escape(str(dna.get('density') or '依据项目内容'))}</dd></div><div><dt>导航策略</dt><dd>{escape(str(dna.get('navigation') or recipe.get('signature') or '依据主任务'))}</dd></div></dl><p class="score-note">诊断与验证综合参考：{escape(str(item.get('reviewScore')))} / 100。分数只辅助排序，不替代审美判断。</p></div>
          <div class="lens lens-executive"><dl><div><dt>决策价值</dt><dd>{fit}</dd></div><div><dt>组织代价</dt><dd>{tradeoff}</dd></div><div><dt>证据结论</dt><dd>{escape(proof)}；未声明业务指标因果提升。</dd></div></dl></div>
          <details class="evidence"><summary>查看验证依据</summary><ul>{reasons}</ul></details>
          <label class="notes">评审备注<textarea data-note="{variant_id}" rows="2" placeholder="记录要保留、调整或验证的地方"></textarea></label>
          <div class="candidate-actions"><button class="choose" data-select="{variant_id}" type="button">选择{name}</button>{open_candidate}</div>
        </article>""")
    distinct = "".join(
        f"<li><span>{escape(str(item.get('left')))} 与 {escape(str(item.get('right')))}</span><b>{'差异明确' if item.get('status') == 'MATERIALLY_DISTINCT' else '需要复核'}</b></li>"
        for item in report.get("pairwiseDistinctness", []) if isinstance(item, Mapping)
    ) or "<li><span>视觉差异证据</span><b>等待 Browser</b></li>"
    candidate_count = len([item for item in report.get("variants", []) if isinstance(item, Mapping)])
    readiness = (
        f"{candidate_count} 套候选作品均已通过桌面、平板和手机验证。系统推荐只是起点，最终偏好由你决定。"
        if verified else
        f"{candidate_count} 套源码候选已经生成。当前没有完整 Browser 证据，但仍可评审方向；界面不会用破损截图冒充结果。"
    )
    discovery = report.get("productDiscovery") if isinstance(report.get("productDiscovery"), Mapping) else {}
    understanding = ""
    understanding_css = ""
    if discovery:
        roles = "".join(f"<span>{escape(str(value))}</span>" for value in discovery.get("roles", []))
        understanding = (
            '<section class="understanding" aria-label="系统理解摘要"><div><p>系统理解已完成</p>'
            f'<h2>{escape(str(discovery.get("productJob") or "已重建产品任务与关键流程"))}</h2>'
            f'<div class="understanding-roles">{roles or "<span>角色仍待确认</span>"}</div></div>'
            f'<aside><b>{escape(str(discovery.get("confidencePercent") or 0))}%</b><span>识别置信度</span>'
            '<a href="../system-understanding/index.html">查看证据与执行简报 →</a></aside></section>'
        )
        understanding_css = """<style>
.understanding{display:grid;grid-template-columns:1fr auto;gap:22px;align-items:center;margin:16px 0;padding:22px clamp(18px,3vw,34px);border:1px solid var(--line);border-radius:22px;background:#fff}.understanding p{margin:0 0 7px;color:var(--brand);font-size:11px;font-weight:850;letter-spacing:.12em;text-transform:uppercase}.understanding h2{max-width:900px;margin:0;font-size:clamp(20px,2.6vw,34px);letter-spacing:-.035em}.understanding-roles{display:flex;flex-wrap:wrap;gap:7px;margin-top:14px}.understanding-roles span{padding:6px 9px;border-radius:99px;background:var(--brand2);color:var(--brand);font-size:11px;font-weight:750}.understanding aside{display:grid;min-width:155px;padding-left:20px;border-left:1px solid var(--line)}.understanding aside b{font-size:32px;letter-spacing:-.05em}.understanding aside span{color:var(--muted);font-size:10px}.understanding aside a{margin-top:9px;color:var(--brand);font-size:11px;font-weight:800;text-decoration:none}@media(max-width:720px){.understanding{grid-template-columns:1fr}.understanding aside{padding:14px 0 0;border-top:1px solid var(--line);border-left:0}}
</style>"""
    html = """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Web UI Quality __VERSION__ · 设计决策工作台</title><style>
:root{--ink:#142019;--muted:#637168;--paper:#eef3f0;--surface:#fff;--line:#d8e2dc;--brand:#116b4d;--brand2:#d9f1e5;--dark:#0d281e;--warn:#f6e8bd;font-family:Inter,"Segoe UI","PingFang SC",sans-serif;color-scheme:light}*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink)}button,select,textarea{font:inherit}button,a,select,textarea{outline-offset:3px}button:focus-visible,a:focus-visible,select:focus-visible,textarea:focus-visible{outline:3px solid #2778ff}main{max-width:1540px;margin:auto;padding:22px clamp(14px,3vw,44px) 150px}.hero{padding:clamp(28px,5vw,62px);border-radius:30px;background:radial-gradient(circle at 88% 0,#2b806260 0,transparent 32%),var(--dark);color:#fff}.eyebrow{color:#9ed5bf;font-size:12px;letter-spacing:.14em;text-transform:uppercase}.hero h1{font-size:clamp(40px,6.5vw,82px);line-height:.96;letter-spacing:-.065em;margin:14px 0}.hero>p{max-width:780px;color:#c5d7cf;font-size:17px;line-height:1.65}.readiness{margin-top:20px;max-width:900px;padding:14px 16px;border:1px solid #ffffff25;border-radius:14px;background:#ffffff0d}.steps{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-top:26px}.step{padding:12px;border-radius:12px;background:#ffffff0c;color:#bad0c7;font-size:12px}.step b{display:block;color:#fff;margin-bottom:3px}.workbar{position:sticky;top:10px;z-index:20;display:flex;flex-wrap:wrap;justify-content:space-between;gap:12px;margin:16px 0;padding:10px;border:1px solid var(--line);border-radius:16px;background:#ffffffec;box-shadow:0 10px 34px #173c2d14;backdrop-filter:blur(16px)}.control-group{display:flex;align-items:center;gap:5px}.control-label{padding:0 7px;color:var(--muted);font-size:11px;font-weight:800}.segmented{display:flex;padding:3px;border-radius:11px;background:#edf1ef}.segmented button{min-height:40px;border:0;border-radius:8px;padding:8px 11px;background:transparent;color:var(--muted);font-weight:750;cursor:pointer}.segmented button[aria-pressed="true"]{background:var(--ink);color:#fff;box-shadow:0 2px 8px #0002}.gallery{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,320px),1fr));gap:16px}.candidate{min-width:0;padding:18px;border:2px solid transparent;border-radius:24px;background:var(--surface);box-shadow:0 18px 52px #1f463617;transition:.2s}.candidate.is-chosen{border-color:var(--brand);box-shadow:0 22px 62px #126b4d24}.candidate-top{display:flex;justify-content:space-between;gap:8px;align-items:center}.badge,.proof-status{padding:6px 8px;border-radius:99px;background:#edf1ef;color:#536159;font-size:10px;font-weight:850}.candidate.is-chosen .badge{background:var(--brand2);color:var(--brand)}.proof-status{background:#e5f3eb;color:#155f46}.concept{margin:18px 0 6px;color:var(--brand);font-size:10px;font-weight:850;letter-spacing:.12em;text-transform:uppercase}.candidate h2{margin:0;font-size:clamp(26px,2.4vw,38px);letter-spacing:-.045em}.promise{min-height:64px;color:var(--muted);line-height:1.55}.preview{position:relative;display:grid;width:100%;aspect-ratio:16/10;overflow:hidden;padding:8px;border:0;border-radius:16px;background:#dfe6e2;cursor:zoom-in}.preview img{width:100%;height:100%;object-fit:contain;border-radius:9px;background:#fff;box-shadow:0 10px 24px #0002}.preview>span{position:absolute;right:14px;bottom:14px;padding:6px 8px;border-radius:8px;background:#10251de6;color:#fff;font-size:10px}.preview.missing{place-items:center;cursor:default;background:repeating-linear-gradient(135deg,#edf1ef,#edf1ef 14px,#e4eae7 14px,#e4eae7 28px)}.preview.missing div{padding:20px;border-radius:14px;background:#fff;text-align:left}.preview.missing b{font-size:16px}.preview.missing p,.preview.missing span{color:var(--muted);font-size:12px;line-height:1.5}.lens{margin-top:14px}.lens dl{display:grid;gap:8px;margin:0}.lens dl>div{padding:11px;border-radius:12px;background:#f5f7f6}.lens dt{color:var(--muted);font-size:10px;font-weight:800}.lens dd{margin:5px 0 0;font-size:13px;line-height:1.45}.lens-designer,.lens-executive{display:none}body[data-audience="designer"] .lens-general,body[data-audience="designer"] .lens-designer{display:block}body[data-audience="executive"] .lens-general,body[data-audience="executive"] .lens-designer{display:none}body[data-audience="executive"] .lens-executive{display:block}.score-note{color:var(--muted);font-size:11px;line-height:1.5}.evidence{margin-top:12px;border-top:1px solid var(--line);padding-top:12px}.evidence summary{cursor:pointer;color:var(--muted);font-size:12px;font-weight:750}.evidence ul{padding-left:18px;color:var(--muted);font-size:11px;line-height:1.5}.notes{display:grid;gap:6px;margin-top:12px;color:var(--muted);font-size:11px}.notes textarea{resize:vertical;width:100%;padding:10px;border:1px solid var(--line);border-radius:10px}.candidate-actions{display:grid;grid-template-columns:1fr;gap:8px;margin-top:12px}.choose,.primary-action,.secondary-action{min-height:44px;border:0;border-radius:11px;padding:11px 13px;font-weight:850;cursor:pointer}.choose{background:var(--brand2);color:var(--brand)}.candidate.is-chosen .choose{background:var(--brand);color:#fff}.text-link{color:var(--brand);font-size:12px;font-weight:750;text-align:center;text-decoration:none}.source-only{color:var(--muted);font-size:11px;text-align:center}.executive{display:grid;grid-template-columns:1.3fr .7fr;gap:16px;margin-top:18px}.panel{padding:22px;border:1px solid var(--line);border-radius:20px;background:#fff}.panel h2{margin:0 0 9px;font-size:24px}.panel p,.panel li{color:var(--muted);line-height:1.6}.proof-list{list-style:none;padding:0}.proof-list li{display:flex;justify-content:space-between;gap:10px;padding:9px 0;border-bottom:1px solid var(--line)}.decision-dock{position:fixed;z-index:40;left:50%;bottom:14px;translate:-50% 0;width:min(1180px,calc(100% - 24px));display:grid;grid-template-columns:1fr auto;gap:18px;align-items:center;padding:14px 16px;border:1px solid #ffffff24;border-radius:20px;background:#10251df2;color:#fff;box-shadow:0 24px 70px #0004;backdrop-filter:blur(20px)}.decision-copy b{display:block;font-size:15px}.decision-copy span{display:block;margin-top:3px;color:#bcd1c8;font-size:12px}.dock-actions{display:flex;flex-wrap:wrap;justify-content:end;gap:8px}.dock-actions label{display:grid;gap:3px;color:#bcd1c8;font-size:9px}.dock-actions select{min-height:38px;border:1px solid #ffffff28;border-radius:9px;padding:6px 28px 6px 8px;background:#ffffff12;color:#fff}.dock-actions option{color:#111}.primary-action{background:#d3f3e2;color:#0e583f}.secondary-action{border:1px solid #ffffff30;background:transparent;color:#fff}.brief-link{color:#d3f3e2;font-size:11px;font-weight:750;text-decoration:none;align-self:center}.toast{position:fixed;z-index:70;left:50%;bottom:112px;translate:-50% 14px;padding:11px 14px;border-radius:11px;background:#111;color:#fff;opacity:0;pointer-events:none;transition:.2s}.toast.show{opacity:1;translate:-50% 0}.lightbox{width:min(95vw,1420px);max-height:94vh;padding:12px;border:0;border-radius:18px;background:#dfe6e2}.lightbox::backdrop{background:#07110ddd}.lightbox img{display:block;max-width:100%;max-height:86vh;margin:auto;border-radius:10px}.lightbox button{position:absolute;right:18px;top:18px;width:44px;height:44px;border:0;border-radius:99px;background:#10251d;color:#fff;font-size:22px}.lightbox p{margin:8px;text-align:center;color:var(--muted)}@media(max-width:1100px){.gallery{grid-template-columns:1fr}.promise{min-height:0}.candidate{display:grid;grid-template-columns:minmax(280px,.9fr) minmax(0,1.1fr);gap:0 18px}.candidate-top,.concept,.candidate h2,.promise{grid-column:1/-1}.candidate .preview{grid-row:5/span 6}.candidate .lens,.candidate .evidence,.candidate .notes,.candidate .candidate-actions{grid-column:2}.executive{grid-template-columns:1fr}}@media(max-width:720px){main{padding-inline:10px}.steps{grid-template-columns:1fr 1fr}.workbar{position:static}.control-group{width:100%;overflow:auto}.gallery{grid-template-columns:1fr}.candidate{display:block;padding:15px}.executive{display:block}.panel{margin-top:12px}.decision-dock{grid-template-columns:1fr;padding:12px}.dock-actions{justify-content:start}.dock-actions label{display:none}.brief-link{display:none}.secondary-action{flex:1}.primary-action{flex:1}.toast{bottom:170px}.hero{border-radius:22px}.hero h1{font-size:42px}}@media(prefers-reduced-motion:reduce){*,*::before,*::after{scroll-behavior:auto!important;transition:none!important}}
</style></head><body data-audience="general"><main><header class="hero"><span class="eyebrow">Web UI Quality __VERSION__ · Design Decision</span><h1>不用懂设计术语，也能选对方向</h1><p>先用同一设备、同一状态比较 3 套真实作品，再切换到适合你的评审视角。系统给出推荐，但不会替你做审美和业务决定。</p><div class="readiness">__READINESS__</div><div class="steps"><div class="step"><b>1 · 已理解</b>产品任务与关键问题</div><div class="step"><b>2 · 正在比较</b>3 套可运行作品</div><div class="step"><b>3 · 需要你决定</b>方向与偏好</div><div class="step"><b>4 · 尚未执行</b>生成补丁并复验</div></div></header><div class="workbar" aria-label="评审控制"><div class="control-group"><span class="control-label">我的视角</span><div class="segmented" data-control="audience"><button data-audience="general" aria-pressed="true">普通评审</button><button data-audience="designer" aria-pressed="false">设计师</button><button data-audience="executive" aria-pressed="false">高管</button></div></div><div class="control-group"><span class="control-label">统一画面</span><div class="segmented" data-control="stage"><button data-stage="before" aria-pressed="false">改造前</button><button data-stage="after" aria-pressed="true">改造后</button></div><div class="segmented" data-control="device"><button data-device="desktop" aria-pressed="true">桌面</button><button data-device="tablet" aria-pressed="false">平板</button><button data-device="mobile" aria-pressed="false">手机</button></div></div></div><section class="gallery" aria-label="设计方向">__CARDS__</section><section class="executive"><div class="panel"><h2>高管一分钟结论</h2><p><b>现在需要决定的只有一件事：</b>哪一种体验方向最符合产品接下来的业务阶段。技术集成、上线和业务增益都还没有被擅自承诺。</p><ul><li>所有候选方向都保留原有业务含义，原项目没有被修改。</li><li>推荐方向来自产品诊断；负责人可以因品牌、组织成本或战略选择其他方向。</li><li>选择后仍在隔离副本中生成补丁，偏好变化必须重新验证。</li></ul><a class="text-link" href="executive-decision-brief.md">打开可分享的一页决策简报 →</a></div><div class="panel"><h2>证据状态</h2><ul class="proof-list">__PROOF__</ul><p>视觉差异只能证明不是几套换色主题，不能证明用户更喜欢或业务指标已提升。</p></div></section></main><aside class="decision-dock" aria-live="polite" data-finalize-command="finalize-design"><div class="decision-copy"><b id="selection-title">尚未确认方向</b><span id="selection-copy">先比较作品，再选择最适合当前业务阶段的一套。</span></div><div class="dock-actions"><label>密度<select id="density"><option value="preserve">沿用项目</option><option value="compact">更紧凑</option><option value="comfortable">更舒展</option></select></label><label>品牌<select id="brand"><option value="preserve">保留品牌</option><option value="refine">优化对比</option><option value="explore">探索新方向</option></select></label><button class="secondary-action" id="copy-handoff" type="button">复制给 Codex</button><button class="primary-action" id="download" type="button">确认并下载决策</button><a class="brief-link" href="executive-decision-brief.md">分享简报</a></div></aside><dialog class="lightbox" id="lightbox"><button type="button" aria-label="关闭放大预览">×</button><img alt=""><p></p></dialog><div class="toast" id="toast" role="status"></div><script>
const state={audience:'general',stage:'after',device:'desktop',selected:__INITIAL__};const names=__NAMES__;const cards=[...document.querySelectorAll('.candidate')];const title=document.getElementById('selection-title');const copy=document.getElementById('selection-copy');const toast=document.getElementById('toast');function notify(message){toast.textContent=message;toast.classList.add('show');setTimeout(()=>toast.classList.remove('show'),1800)}function press(group,key,value){document.querySelectorAll(`[data-control="${group}"] [data-${key}]`).forEach(button=>button.setAttribute('aria-pressed',String(button.dataset[key]===value)))}function updateImages(){document.querySelectorAll('.preview img').forEach(image=>{const base=state.stage==='before'?image.dataset.beforeBase:image.dataset.afterBase;image.src=base+state.device+'.png';image.alt=`${image.closest('.candidate').dataset.name} ${state.stage==='before'?'改造前':'改造后'} ${state.device}`})}function choose(id,userInitiated=true){state.selected=id;cards.forEach(card=>card.classList.toggle('is-chosen',card.dataset.variant===id));title.textContent=`已选择：${names[id]||id}`;copy.textContent=userInitiated?'这个选择只更新隔离输出，不会直接修改原项目。':'这是系统推荐；请按你的业务与审美判断确认或改选。';localStorage.setItem('wuq-design-selection',id)}document.querySelectorAll('[data-audience]').forEach(button=>button.addEventListener('click',()=>{state.audience=button.dataset.audience;document.body.dataset.audience=state.audience;press('audience','audience',state.audience)}));document.querySelectorAll('[data-stage]').forEach(button=>button.addEventListener('click',()=>{state.stage=button.dataset.stage;press('stage','stage',state.stage);updateImages()}));document.querySelectorAll('[data-device]').forEach(button=>button.addEventListener('click',()=>{state.device=button.dataset.device;press('device','device',state.device);updateImages()}));document.querySelectorAll('[data-select]').forEach(button=>button.addEventListener('click',()=>{choose(button.dataset.select);document.querySelector('.decision-dock').scrollIntoView({behavior:'smooth',block:'nearest'})}));document.querySelectorAll('[data-note]').forEach(field=>{const key='wuq-note-'+field.dataset.note;field.value=localStorage.getItem(key)||'';field.addEventListener('input',()=>localStorage.setItem(key,field.value))});const stored=localStorage.getItem('wuq-design-selection');if(stored&&cards.some(card=>card.dataset.variant===stored))choose(stored);else if(state.selected)choose(state.selected,false);const decision=()=>({schemaVersion:'1',selectedVariantId:state.selected,preferences:{density:document.getElementById('density').value,brand:document.getElementById('brand').value},notes:Object.fromEntries([...document.querySelectorAll('[data-note]')].map(field=>[field.dataset.note,field.value])),reviewAudience:state.audience,source:'web-ui-quality-design-gallery'});function requireChoice(){if(state.selected)return true;notify('请先选择一个方向');return false}document.getElementById('download').addEventListener('click',()=>{if(!requireChoice())return;const blob=new Blob([JSON.stringify(decision(),null,2)+'\n'],{type:'application/json'});const link=document.createElement('a');link.href=URL.createObjectURL(blob);link.download='design-decision.json';link.click();setTimeout(()=>URL.revokeObjectURL(link.href),1000);notify('决策文件已生成，交给 Codex 即可继续')});document.getElementById('copy-handoff').addEventListener('click',async()=>{if(!requireChoice())return;const prompt=`请按 design-decision.json 完成 Web UI Quality 设计定稿：采用 ${names[state.selected]||state.selected}，保持原项目不变，在隔离输出中生成最终补丁；若偏好改变画面，请重新执行 Browser 验证。`;try{await navigator.clipboard.writeText(prompt)}catch(_error){const area=document.createElement('textarea');area.value=prompt;document.body.append(area);area.select();document.execCommand('copy');area.remove()}notify('已复制下一步，直接粘贴给 Codex')});const lightbox=document.getElementById('lightbox');document.querySelectorAll('[data-preview]').forEach(button=>button.addEventListener('click',()=>{const image=button.querySelector('img');lightbox.querySelector('img').src=image.src;lightbox.querySelector('img').alt=image.alt;lightbox.querySelector('p').textContent=image.alt;lightbox.showModal()}));lightbox.querySelector('button').addEventListener('click',()=>lightbox.close());lightbox.addEventListener('click',event=>{if(event.target===lightbox)lightbox.close()});updateImages();
</script></body></html>"""
    if understanding:
        html = html.replace('</header><div class="workbar"', f'</header>{understanding}<div class="workbar"', 1)
        html = html.replace("</head>", understanding_css + "</head>", 1)
    lightbox = '<dialog class="lightbox" id="lightbox"><button type="button" aria-label="关闭放大预览">×</button>'
    if has_previews:
        lightbox += '<img alt=""><p></p>'
    else:
        lightbox += '<p>Browser 截图完成后，可在这里放大审阅作品。</p>'
    lightbox += '</dialog>'
    return (
        html.replace("__VERSION__", escape(PACKAGE_VERSION))
        .replace("__READINESS__", escape(readiness))
        .replace("__CARDS__", "".join(cards))
        .replace("__PROOF__", distinct)
        .replace("__INITIAL__", json.dumps(selected, ensure_ascii=False))
        .replace("__NAMES__", json.dumps(names, ensure_ascii=False))
        .replace('<dialog class="lightbox" id="lightbox"><button type="button" aria-label="关闭放大预览">×</button><img alt=""><p></p></dialog>', lightbox)
    )


def build_design_gallery(
    before_dir: str | Path,
    implementation: Mapping[str, Any],
    validation_dir: str | Path,
    gallery_dir: str | Path,
    *,
    browser_executable: str | Path | None = None,
    journey: Sequence[Mapping[str, Any]] = (),
    single_process: bool = False,
    product_discovery: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    before = Path(before_dir).resolve()
    validation_root = Path(validation_dir).resolve()
    gallery_root = Path(gallery_dir).resolve()
    validation_root.mkdir(parents=True, exist_ok=True)
    gallery_root.mkdir(parents=True, exist_ok=True)
    variants: list[dict[str, Any]] = []
    for candidate in implementation.get("variants", []):
        if not isinstance(candidate, Mapping) or candidate.get("status") != "IMPLEMENTED":
            continue
        item = dict(candidate)
        path_id = str(item["pathId"])
        candidate_root = before.parent / "variants" / path_id
        report = validate_transformation(
            before, candidate_root, validation_root / "variants" / path_id,
            browser_executable=browser_executable, journey=journey, single_process=single_process,
        )
        browser_score, reasons = _browser_score(report)
        diagnostic_fit = int(item.get("diagnosticFit") or (100 if item.get("recommendedByDiagnosis") else 78))
        screenshots_root = validation_root / "variants" / path_id / "screenshots" / "after"
        screenshots_available = all((screenshots_root / f"{viewport}.png").is_file() for viewport in VIEWPORT_IDS)
        entries = [path for path in sorted(candidate_root.rglob("index.html")) if path.is_file()]
        runnable_entry = entries[0].relative_to(candidate_root).as_posix() if entries else None
        item.update({
            "browserStatus": report.get("status"), "browserReport": f"validation/variants/{path_id}/production-validation-report.json",
            "browserScore": browser_score, "diagnosticFit": diagnostic_fit,
            "reviewScore": round(browser_score * .68 + diagnostic_fit * .32), "reviewReasons": reasons,
            "browserReason": report.get("reason"), "screenshotsAvailable": screenshots_available,
            "runnableEntry": runnable_entry,
        })
        variants.append(item)
    passing = [item for item in variants if item.get("browserStatus") == "PASS"]
    preferred_id = implementation.get("selectedVariantId")
    selected = next((item for item in passing if item.get("id") == preferred_id), max(passing, key=lambda item: item["reviewScore"], default=None))
    distinctness = _pairwise_distinctness(variants, validation_root) if len(variants) >= 2 else []
    distinct_pass = bool(distinctness) and all(item.get("status") == "MATERIALLY_DISTINCT" for item in distinctness)
    status = "DESIGN_GALLERY_PASS" if 2 <= len(variants) <= 3 and len(passing) == len(variants) and distinct_pass and selected else "DESIGN_GALLERY_NOT_VERIFIED"
    discovery_product = product_discovery.get("product") if isinstance(product_discovery, Mapping) and isinstance(product_discovery.get("product"), Mapping) else {}
    discovery_confidence = product_discovery.get("confidence") if isinstance(product_discovery, Mapping) and isinstance(product_discovery.get("confidence"), Mapping) else {}
    discovery_roles = product_discovery.get("rolePermissionMap", []) if isinstance(product_discovery, Mapping) else []
    discovery_summary = {
        "status": product_discovery.get("status"),
        "productName": discovery_product.get("name"),
        "productJob": discovery_product.get("job"),
        "confidencePercent": discovery_confidence.get("percent"),
        "roles": [str(item.get("label")) for item in discovery_roles if isinstance(item, Mapping) and item.get("label")][:6],
        "artifact": "../system-understanding/index.html",
    } if isinstance(product_discovery, Mapping) else None
    report = {
        "schemaVersion": "1", "generator": release_identity(), "status": status,
        "selectionMode": "DIAGNOSIS_PREFERRED_BROWSER_GATED", "selectedVariantId": selected.get("id") if selected else None,
        "diagnosticPreferredVariantId": preferred_id,
        "decisionExport": {"schemaVersion": "1", "command": "finalize-design", "filename": "design-decision.json"},
        "decisionExperience": {
            "status": "READY_FOR_HUMAN_DECISION" if status == "DESIGN_GALLERY_PASS" else "SOURCE_REVIEW_READY_BROWSER_EVIDENCE_REQUIRED",
            "recommendedVariantId": selected.get("id") if selected else None,
            "finalDecisionOwner": "human-reviewer",
            "audiences": ["general", "designer", "executive"],
            "beforeAfterSynchronized": True,
            "handoff": "design-decision.json",
        },
        "productDiscovery": discovery_summary,
        "variants": variants, "pairwiseDistinctness": distinctness,
        "claimBoundary": "Browser gates and pairwise screenshot differences prove runnable, materially different candidates. They do not establish user preference or business improvement.",
    }
    (gallery_root / "design-review.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (gallery_root / "index.html").write_text(_gallery_html_v372(report), encoding="utf-8")
    (gallery_root / "executive-decision-brief.md").write_text(_decision_brief_markdown(report), encoding="utf-8")
    if selected:
        selected_validation = validation_root / "variants" / str(selected["pathId"])
        for name in ("production-validation-report.json", "production-validation-report.html", "node-browser-report.json", "journey-complete.png"):
            source = selected_validation / name
            if source.is_file():
                shutil.copy2(source, validation_root / name)
        source_screens = selected_validation / "screenshots"
        target_screens = validation_root / "screenshots"
        if source_screens.is_dir() and not target_screens.exists():
            shutil.copytree(source_screens, target_screens)
    return report
