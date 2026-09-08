"""Interactive Before / After experience preview driven by diagnosis evidence.

The preview is a candidate review surface, not a Figma replacement and not a
production write.  It demonstrates layout, token, component, theme, responsive,
and state changes while keeping the evidence/claim boundary visible.
"""
from __future__ import annotations

import html
import json
from pathlib import Path
import shutil
from typing import Any, Mapping


def _escape(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def _recommendation_cards(diagnosis: Mapping[str, Any]) -> str:
    items = diagnosis.get("recommendations")
    if not isinstance(items, list):
        return ""
    cards = []
    for item in items[:8]:
        if not isinstance(item, Mapping):
            continue
        title = item.get("title") or item.get("id") or "体验建议"
        problem = item.get("userProblem") or item.get("userExplanation") or ""
        change = item.get("recommendation") or item.get("change") or ""
        cards.append(
            '<article class="recommendation">'
            f'<div class="rec-meta">{_escape(item.get("priority") or item.get("severity") or "candidate")} · {_escape(item.get("id"))}</div>'
            f'<h3>{_escape(title)}</h3><p>{_escape(problem)}</p><p class="change"><b>改进：</b>{_escape(change)}</p>'
            "</article>"
        )
    return "".join(cards)


def _dashboard(after: bool) -> str:
    metrics = [
        ("待处理异常", "12", "较昨日 -3"),
        ("任务完成率", "92%", "本周 +4%"),
        ("活跃客户", "2,418", "近 30 天"),
        ("平均处理时长", "18m", "目标 < 20m"),
    ]
    metric_html = "".join(
        f'<article class="metric {"priority" if index == 0 and after else ""}"><span>{label}</span><b>{value}</b><small>{note}</small></article>'
        for index, (label, value, note) in enumerate(metrics)
    )
    action_queue = (
        '<section class="action-queue"><div class="section-head"><h3>需要处理</h3><span class="badge">12 项</span></div>'
        '<button><span class="status danger"></span><b>支付失败率升高</b><small>查看 5 个受影响账户 →</small></button>'
        '<button><span class="status warning"></span><b>3 个自动化流程延迟</b><small>检查运行记录 →</small></button></section>'
        if after else
        '<section class="card-wall"><div class="equal-card">更多指标</div><div class="equal-card">更多图表</div><div class="equal-card">更多通知</div></section>'
    )
    return (
        f'<div class="page-title"><div><small>运营总览</small><h2>今天需要关注什么？</h2></div><button class="primary">创建报告</button></div>'
        f'<section class="metrics">{metric_html}</section>'
        '<section class="dashboard-grid"><article class="chart"><div class="section-head"><h3>处理趋势</h3><button>近 30 天</button></div>'
        '<div class="bars" aria-label="趋势图"><i style="--h:45%"></i><i style="--h:68%"></i><i style="--h:56%"></i><i style="--h:78%"></i><i style="--h:64%"></i><i style="--h:88%"></i></div>'
        '<a href="#" class="drill">查看过滤后的明细 →</a></article>'
        f'{action_queue}</section>'
    )


def _crm(after: bool) -> str:
    rows = "".join(
        f'<button class="record {"selected" if index == 0 else ""}"><b>客户 {index + 1:02d}</b><span>{"待跟进" if index % 2 == 0 else "正常"}</span><small>负责人 · 陈晨</small></button>'
        for index in range(5)
    )
    if after:
        return (
            '<div class="page-title"><div><small>客户工作台</small><h2>查找并处理客户</h2></div><button class="primary">新建客户</button></div>'
            '<div class="filterbar"><input aria-label="搜索客户" placeholder="搜索名称、ID 或负责人"><button>状态：待跟进</button><button>更多筛选</button></div>'
            f'<div class="crm-split"><section class="record-list">{rows}</section><aside class="detail"><span class="badge">待跟进</span><h3>客户 01</h3>'
            '<dl><dt>最近活动</dt><dd>今天 10:24</dd><dt>负责人</dt><dd>陈晨</dd><dt>下一步</dt><dd>确认合同条款</dd></dl>'
            '<div class="detail-actions"><button>记录活动</button><button class="primary">标记已完成</button></div></aside></div>'
        )
    return (
        '<div class="page-title"><h2>客户列表</h2><div><button class="primary">新增</button><button class="primary">导出</button></div></div>'
        '<div class="filterbar crowded"><input placeholder="搜索"><button>筛选</button><button>排序</button><button>批量</button><button>更多</button></div>'
        f'<section class="wide-table"><div class="table-head">客户　状态　负责人　等级　地区　来源　更新时间　操作</div>{rows}</section>'
    )


def _erp(after: bool) -> str:
    header = '<div class="table-head">物料编码　名称　可用库存　占用　仓库　批次　状态　更新时间　操作</div>'
    rows = "".join(
        f'<div class="erp-row"><input type="checkbox" aria-label="选择物料 {index + 1}"><b>MAT-{1200 + index}</b><span>关键物料 {index + 1}</span><span>{45 + index * 7}</span><span>{index + 2}</span><span>华东仓</span><span>B-{index + 1}</span><span class="badge">正常</span><small>10:{20 + index}</small></div>'
        for index in range(5)
    )
    summary = '<div class="bulk-summary"><b>已选 3 项</b><span>仅当前页</span><button>调整仓位</button><button class="danger-button">批量冻结</button></div>' if after else '<div class="always-bulk"><button>批量修改</button><button>批量删除</button><button>批量导出</button></div>'
    return (
        '<div class="page-title"><div><small>库存运营</small><h2>物料与可用库存</h2></div><button class="primary">新建盘点</button></div>'
        f'{summary}<div class="filterbar"><input placeholder="搜索物料编码或名称"><button>仓库</button><button>状态</button><button>应用筛选</button></div>'
        f'<section class="erp-table">{header}{rows}</section>'
        + ('<div class="recovery-note">发生并发变化时保留选择，展示差异并允许重新核对。</div>' if after else '')
    )


def _landing(after: bool) -> str:
    if after:
        return (
            '<section class="hero focused"><div class="hero-copy"><span class="eyebrow">让团队更快完成关键工作</span><h2>把复杂流程变成清晰的下一步</h2>'
            '<p>统一查找、处理与状态反馈，让每个角色都能在桌面和移动端保持上下文。</p><div class="hero-actions"><button class="primary">免费体验</button><a href="#">查看真实案例</a></div>'
            '<small>无需信用卡 · 可随时导出数据</small></div><div class="product-visual"><div class="mini-kpi">任务时间 <b>待真实测量</b></div><div class="mini-list">异常处理队列<br>清晰状态 · 明确下一步</div></div></section>'
            '<section class="trust-row"><span>清晰层级</span><span>可靠状态</span><span>跨端连续</span></section>'
            '<section class="feature-story"><article><small>01</small><h3>先看见最重要的事</h3><p>摘要与待处理事项共享同一阅读路径。</p></article>'
            '<article><small>02</small><h3>处理时保持上下文</h3><p>列表、详情和返回路径不再相互打断。</p></article></section>'
        )
    return (
        '<section class="hero unfocused"><div class="hero-copy"><span class="eyebrow">AI POWERED ENTERPRISE PLATFORM</span><h2>面向未来的一站式智能数字化解决方案</h2>'
        '<p>赋能组织、连接生态、重塑体验、释放增长潜力。</p><div class="hero-actions"><button class="primary">立即开始</button><button class="primary">预约演示</button><button>了解更多</button></div></div>'
        '<div class="product-visual noisy"><div>图表</div><div>数据</div><div>AI</div><div>增长</div></div></section>'
        '<section class="card-wall"><div class="equal-card">能力一</div><div class="equal-card">能力二</div><div class="equal-card">能力三</div><div class="equal-card">能力四</div></section>'
    )


def _mobile(after: bool) -> str:
    content = (
        '<header><small>现场任务 · 3/8</small><h2>核对设备 SN-2048</h2></header>'
        '<div class="mobile-status"><span class="badge">离线草稿已保存</span><span>上次同步 10:24</span></div>'
        '<section class="scan-area"><b>扫码或输入编号</b><input placeholder="设备编号"><button>打开扫描</button></section>'
        '<section class="mobile-fields"><label>检查结果<select><option>正常</option></select></label><label>备注<textarea></textarea></label></section>'
        '<footer class="mobile-actions"><button>保存草稿</button><button class="primary">完成并继续</button></footer>'
        if after else
        '<header><h2>现场检查表</h2></header><div class="mobile-toolbar"><button>返回</button><button>上传</button><button>删除</button><button>更多</button></div>'
        '<section class="mobile-fields cramped"><label>设备编号<input></label><label>位置<input></label><label>状态<select><option>请选择</option></select></label><label>备注<textarea></textarea></label></section>'
        '<footer class="mobile-actions unsafe"><button class="primary">提交</button></footer>'
    )
    return f'<div class="phone">{content}</div>'


def _surface(page_type: str, after: bool) -> str:
    if page_type == "saas-dashboard":
        return _dashboard(after)
    if page_type == "crm":
        return _crm(after)
    if page_type == "erp":
        return _erp(after)
    if page_type == "landing-page":
        return _landing(after)
    if page_type == "mobile-workflow":
        return _mobile(after)
    return _crm(after)


def generate_modernization_preview(
    diagnosis: Mapping[str, Any],
    output_dir: str | Path,
    *,
    title: str | None = None,
    source_screenshot: str | Path | None = None,
) -> Path:
    """Write an isolated, interactive comparison preview and return index.html."""

    out = Path(output_dir).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    (out / "experience-diagnosis.json").write_text(
        json.dumps(diagnosis, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    screenshot_name = None
    if source_screenshot:
        source = Path(source_screenshot).expanduser().resolve(strict=True)
        screenshot_name = "before" + source.suffix.casefold()
        shutil.copyfile(source, out / screenshot_name)

    understanding = diagnosis.get("pageUnderstanding") if isinstance(diagnosis.get("pageUnderstanding"), Mapping) else {}
    page_type_obj = understanding.get("pageType") if isinstance(understanding.get("pageType"), Mapping) else {}
    page_type = str(page_type_obj.get("id") or "unclassified")
    primary_task_obj = understanding.get("primaryTask") if isinstance(understanding.get("primaryTask"), Mapping) else {}
    primary_task = str(primary_task_obj.get("value") or "体验现代化预览")
    title = title or primary_task
    before_surface = (
        f'<figure class="source-shot"><img src="{_escape(screenshot_name)}" alt="用户提供的页面参考截图"><figcaption>参考截图（未验证为 Before 状态）</figcaption></figure>'
        if screenshot_name else _surface(page_type, False)
    )
    before_label = "参考截图" if screenshot_name else "当前结构示意"
    before_meta = "未验证 Before 状态" if screenshot_name else "概念结构，不是实测截图"
    after_surface = _surface(page_type, True)
    recommendations = _recommendation_cards(diagnosis)
    boundary = str(diagnosis.get("claimBoundary") or "这是体验候选预览；真实改善仍需 Browser、专家和用户结果验证。")
    payload = json.dumps(diagnosis, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    page = f'''<!doctype html>
<html lang="zh-CN" data-theme="light" data-density="comfortable">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_escape(title)} · Before / After</title>
<style>
:root{{--bg:#eef1f5;--surface:#fff;--text:#17212b;--muted:#637083;--line:#d9e0e8;--brand:#315efb;--brand-soft:#e9efff;--danger:#c83434;--warning:#a66000;--radius:16px;--space:8px;--shadow:0 18px 50px rgba(30,45,70,.12)}}*{{box-sizing:border-box}}html{{font-family:Inter,"Segoe UI","PingFang SC",system-ui,sans-serif;background:var(--bg);color:var(--text)}}body{{margin:0}}button,input,select,textarea{{font:inherit}}button{{min-height:40px;border:1px solid var(--line);border-radius:9px;background:var(--surface);padding:0 12px;color:inherit}}button:focus-visible,a:focus-visible,input:focus-visible,select:focus-visible,textarea:focus-visible{{outline:3px solid color-mix(in srgb,var(--brand) 32%,transparent);outline-offset:2px}}.primary{{background:var(--brand);border-color:var(--brand);color:#fff}}.shell{{min-height:100vh;display:grid;grid-template-rows:auto 1fr}}.topbar{{position:sticky;top:0;z-index:30;display:flex;align-items:center;justify-content:space-between;gap:16px;padding:12px 18px;background:color-mix(in srgb,var(--surface) 92%,transparent);backdrop-filter:blur(16px);border-bottom:1px solid var(--line)}}.title small{{display:block;color:var(--muted)}}h1{{font-size:18px;margin:2px 0}}.controls{{display:flex;gap:7px;align-items:center;flex-wrap:wrap}}.controls button[aria-pressed="true"]{{background:var(--brand-soft);border-color:var(--brand);color:#173fbf}}.main{{padding:18px;display:grid;gap:18px}}.boundary{{padding:10px 12px;border:1px solid #e5c06a;background:#fff8df;border-radius:10px;color:#604400}}.compare{{display:grid;grid-template-columns:1fr 1fr;gap:14px;align-items:start}}.pane{{min-width:0}}.pane-head{{display:flex;align-items:center;justify-content:space-between;margin-bottom:8px}}.pane-head span{{font-size:12px;color:var(--muted)}}.viewport-shell{{margin:auto;width:min(100%,var(--preview-width,1440px));transition:width .2s ease}}.viewport{{container-type:inline-size;background:#f7f9fc;border:1px solid var(--line);border-radius:18px;min-height:620px;overflow:auto;box-shadow:var(--shadow)}}.product{{min-width:0;padding:20px;color:var(--text)}}.before .product{{--brand:#56606b;--radius:6px;filter:saturate(.72)}}.page-title,.section-head,.hero,.filterbar,.detail-actions,.bulk-summary{{display:flex;gap:12px;align-items:center;justify-content:space-between}}.page-title h2,.hero h2{{margin:3px 0;font-size:clamp(22px,3cqi,32px)}}.page-title small,.metric span,.metric small,.rec-meta,.mobile-status{{color:var(--muted)}}.metrics{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:18px 0}}.metric,.chart,.action-queue,.detail,.wide-table,.erp-table,.scan-area,.recommendation,.equal-card{{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);padding:14px}}.metric b{{display:block;font-size:26px;margin:9px 0 2px}}.metric.priority{{border-color:#f0a650;background:#fffaf1}}.dashboard-grid{{display:grid;grid-template-columns:1.25fr .9fr;gap:12px}}.bars{{height:220px;display:flex;align-items:flex-end;gap:10px;padding:18px}}.bars i{{flex:1;height:var(--h);background:linear-gradient(var(--brand),#8a9cff);border-radius:7px 7px 2px 2px}}.drill{{display:block;padding:0 18px 16px;color:var(--brand)}}.action-queue button{{display:grid;grid-template-columns:auto 1fr;gap:4px 8px;width:100%;text-align:left;border:0;border-top:1px solid var(--line);border-radius:0;padding:12px 4px}}.action-queue small{{grid-column:2;color:var(--muted)}}.status{{width:8px;height:8px;border-radius:50%;margin-top:5px;background:var(--brand)}}.status.danger{{background:var(--danger)}}.status.warning{{background:#d98a11}}.card-wall{{display:grid;grid-template-columns:repeat(3,1fr);gap:9px}}.equal-card{{min-height:90px;display:grid;place-items:center}}.filterbar{{justify-content:flex-start;margin:14px 0}}.filterbar input{{min-height:40px;min-width:220px;border:1px solid var(--line);border-radius:9px;padding:8px 10px;background:var(--surface)}}.filterbar.crowded{{gap:3px}}.crm-split{{display:grid;grid-template-columns:minmax(280px,.9fr) minmax(320px,1.1fr);gap:12px}}.record-list{{display:grid;background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);overflow:hidden}}.record{{display:grid;grid-template-columns:1.2fr .7fr .9fr;gap:10px;text-align:left;border:0;border-bottom:1px solid var(--line);border-radius:0;padding:13px}}.record.selected{{background:var(--brand-soft);box-shadow:inset 3px 0 var(--brand)}}.record small{{color:var(--muted)}}.detail dl{{display:grid;grid-template-columns:100px 1fr;gap:10px;margin:18px 0}}.detail dt{{color:var(--muted)}}.detail dd{{margin:0;font-weight:600}}.badge{{display:inline-flex;padding:4px 8px;border-radius:999px;background:var(--brand-soft);color:#2447ad;font-size:12px}}.table-head,.erp-row{{min-width:860px;white-space:nowrap}}.table-head{{font-weight:700;padding:10px;background:#f1f4f8}}.wide-table .record{{min-width:860px}}.erp-table{{overflow:auto;padding:0}}.erp-row{{display:grid;grid-template-columns:26px 90px 1.2fr 70px 60px 90px 65px 70px 65px;gap:8px;align-items:center;padding:10px;border-top:1px solid var(--line)}}.erp-row input{{width:18px;height:18px}}.danger-button{{color:var(--danger)}}.recovery-note{{margin-top:10px;padding:10px;border-radius:9px;background:#eef8f2;color:#22603d}}.hero{{min-height:390px;padding:36px;border-radius:24px;background:linear-gradient(145deg,#fff 45%,#eef3ff)}}.hero-copy{{max-width:620px}}.hero h2{{font-size:clamp(34px,6cqi,64px);line-height:1.06}}.hero p{{font-size:18px;color:var(--muted)}}.hero-actions{{display:flex;align-items:center;gap:14px;margin:22px 0}}.hero-actions a{{color:var(--brand)}}.unfocused h2{{font-size:44px}}.noisy,.product-visual{{min-width:260px;display:grid;grid-template-columns:1fr 1fr;gap:8px}}.noisy div,.mini-kpi,.mini-list{{padding:22px;background:#fff;border:1px solid var(--line);border-radius:16px}}.mini-list{{grid-column:1/-1}}.trust-row{{display:flex;justify-content:space-around;padding:18px;color:var(--muted)}}.feature-story{{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:34px 0}}.feature-story article{{padding:28px;border-top:1px solid var(--line)}}.phone{{max-width:390px;min-height:690px;margin:auto;background:var(--surface);border:10px solid #1d2430;border-radius:34px;padding:18px;position:relative;overflow:hidden}}.mobile-toolbar{{display:flex;gap:3px}}.mobile-fields{{display:grid;gap:12px;margin:18px 0 90px}}.mobile-fields label{{display:grid;gap:5px}}.mobile-fields input,.mobile-fields select,.mobile-fields textarea,.scan-area input{{min-height:44px;border:1px solid var(--line);border-radius:9px;padding:8px;width:100%}}.mobile-fields.cramped{{gap:4px}}.mobile-status{{display:flex;justify-content:space-between;font-size:12px}}.mobile-actions{{position:absolute;left:12px;right:12px;bottom:12px;display:flex;gap:8px;padding:10px;background:color-mix(in srgb,var(--surface) 94%,transparent);border:1px solid var(--line);border-radius:14px}}.mobile-actions button{{flex:1;min-height:48px}}.mobile-actions.unsafe{{bottom:-5px;padding-bottom:0}}.source-shot{{margin:0;padding:12px}}.source-shot img{{display:block;max-width:100%;height:auto;margin:auto}}.source-shot figcaption{{text-align:center;color:var(--muted);padding:8px}}.recommendations h2{{margin-bottom:10px}}.recommendation-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}}.recommendation h3{{margin:5px 0}}.recommendation p{{color:var(--muted)}}.recommendation .change{{color:var(--text)}}[data-density="dense"]{{--space:6px;--radius:11px}}[data-density="dense"] .product{{padding:12px}}[data-density="dense"] .metric,[data-density="dense"] .chart,[data-density="dense"] .detail{{padding:10px}}[data-components="headless"] .after .metric,[data-components="headless"] .after .chart,[data-components="headless"] .after .detail{{box-shadow:none;border-radius:8px}}[data-layout="off"] .after .crm-split,[data-layout="off"] .after .dashboard-grid{{display:block}}[data-tokens="off"] .after{{filter:saturate(.2)}}html[data-theme="dark"]{{--bg:#10141b;--surface:#19202a;--text:#f3f6fb;--muted:#aab5c4;--line:#35404e;--brand-soft:#26365e;--shadow:none}}html[data-theme="dark"] .hero{{background:linear-gradient(145deg,#19202a,#182744)}}@container (max-width:760px){{.metrics{{grid-template-columns:1fr 1fr}}.dashboard-grid,.crm-split,.feature-story{{grid-template-columns:1fr}}.detail{{display:none}}.filterbar{{flex-wrap:wrap}}.filterbar input{{min-width:100%}}.hero{{display:grid;padding:22px}}.product-visual,.noisy{{min-width:0}}}}@container (max-width:460px){{.product{{padding:12px}}.metrics{{grid-template-columns:1fr 1fr}}.page-title{{align-items:flex-start;flex-direction:column}}.page-title>div:last-child{{display:flex;flex-wrap:wrap}}.metric b{{font-size:21px}}.card-wall{{grid-template-columns:1fr}}}}@media(max-width:980px){{.compare{{grid-template-columns:1fr}}.recommendation-grid{{grid-template-columns:1fr 1fr}}}}@media(max-width:600px){{.topbar{{align-items:flex-start;flex-direction:column}}.recommendation-grid{{grid-template-columns:1fr}}}}@media(prefers-reduced-motion:reduce){{*{{animation:none!important;transition:none!important;scroll-behavior:auto!important}}}}
</style>
<style id="viewport-accuracy">
.compare{{grid-template-columns:repeat(2,max-content);overflow:auto;padding-bottom:8px}}.pane,.viewport-shell{{width:var(--preview-width,1440px);max-width:none}}
@media(max-width:980px){{.compare{{grid-template-columns:max-content}}}}
</style>

</head>
<body>
<div class="shell">
<header class="topbar"><div class="title"><small>WUQ Experience Preview · {_escape(page_type)}</small><h1>{_escape(title)}</h1></div>
<div class="controls" aria-label="预览控制">
<button data-width="1440" aria-pressed="true">桌面</button><button data-width="768" aria-pressed="false">平板</button><button data-width="390" aria-pressed="false">移动</button>
<button id="theme">深色</button><button id="density">密度</button>
<label><input id="layoutToggle" type="checkbox" checked> 布局</label><label><input id="tokenToggle" type="checkbox" checked> Token</label>
<select id="components" aria-label="组件策略"><option value="suite">成熟组件</option><option value="headless">Headless</option></select>
<select id="state" aria-label="页面状态"><option value="ready">正常</option><option value="loading">加载</option><option value="empty">空态</option><option value="error">错误</option><option value="success">成功</option></select>
</div></header>
<main class="main">
<div class="boundary"><b>证据边界：</b>{_escape(boundary)}</div>
<section class="compare" aria-label="改造前后对比">
<article class="pane before"><div class="pane-head"><b>{_escape(before_label)}</b><span>{_escape(before_meta)}</span></div><div class="viewport-shell"><div class="viewport"><div class="product">{before_surface}</div></div></div></article>
<article class="pane after"><div class="pane-head"><b>After</b><span>体验现代化候选</span></div><div class="viewport-shell"><div class="viewport"><div class="product" id="afterProduct">{after_surface}</div></div></div></article>
</section>
<section class="recommendations"><h2>为什么这样改</h2><div class="recommendation-grid">{recommendations}</div></section>
</main></div>
<script>
const DIAGNOSIS={payload};
const root=document.documentElement;
const widthButtons=[...document.querySelectorAll('[data-width]')];
widthButtons.forEach(button=>button.onclick=()=>{{widthButtons.forEach(item=>item.setAttribute('aria-pressed','false'));button.setAttribute('aria-pressed','true');root.style.setProperty('--preview-width',button.dataset.width+'px');}});
document.getElementById('theme').onclick=()=>{{const dark=root.dataset.theme==='dark';root.dataset.theme=dark?'light':'dark';document.getElementById('theme').textContent=dark?'深色':'浅色';}};
document.getElementById('density').onclick=()=>{{root.dataset.density=root.dataset.density==='dense'?'comfortable':'dense';}};
document.getElementById('layoutToggle').onchange=e=>root.dataset.layout=e.target.checked?'on':'off';
document.getElementById('tokenToggle').onchange=e=>root.dataset.tokens=e.target.checked?'on':'off';
document.getElementById('components').onchange=e=>root.dataset.components=e.target.value;
document.getElementById('state').onchange=e=>{{const host=document.getElementById('afterProduct');const original=host.dataset.original||(host.dataset.original=host.innerHTML);const states={{loading:'<div class="metric"><b>正在加载</b><p>保留页面骨架，避免内容跳动。</p></div>',empty:'<div class="metric"><b>当前没有匹配结果</b><p>清除筛选或创建第一条记录。</p><button>清除筛选</button></div>',error:'<div class="metric"><b>这一部分暂时不可用</b><p>已保留筛选和输入，可安全重试。</p><button>重试</button></div>',success:'<div class="metric"><b>任务已完成</b><p>结果已保存，可以继续下一项。</p><button>继续</button></div>'}};host.innerHTML=e.target.value==='ready'?original:states[e.target.value];}};
</script>
</body></html>'''
    path = out / "index.html"
    path.write_text(page, encoding="utf-8")
    return path


__all__ = ["generate_modernization_preview"]
