#!/usr/bin/env python3
"""Build three production-like Experience Fusion examples.

These are representative fixtures, not customer evidence.  They exist to test
routing, project token mapping, UX repair detection, interaction contracts, and
Studio output across materially different enterprise tasks.
"""
from __future__ import annotations

import json
from pathlib import Path

from web_ui_quality.core import audit_project
from web_ui_quality.experience_preview import generate_experience_preview
from web_ui_quality.experience_studio import generate_experience_studio

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "examples" / "v2.1"

CASES = {
    "manufacturing-inventory": {
        "title": "制造业库存与批次工作台",
        "html": """<!doctype html><html lang='zh-CN'><body><div class='legacy'><h1>库存批次表</h1><div class='filters'><input placeholder='物料编码'><select><option>全部仓库</option></select><button>查询</button></div><table><tr><th>物料</th><th>批次</th><th>仓库</th><th>可用</th><th>冻结</th><th>质检</th><th>供应商</th><th>入库日期</th><th>操作</th></tr><tr><td>M-1024</td><td>B240716</td><td>华东一库</td><td>120</td><td>12</td><td>待复核</td><td>远航制造</td><td>2026-07-12</td><td><button>查看</button></td></tr></table></div></body></html>""",
        "css": """:root{--primary:#1769aa;--border:#ddd}.legacy{width:1320px;margin:0 auto}.filters{display:flex;gap:8px}.filters input{width:360px}table{width:1280px;border-collapse:collapse}th,td{padding:7px;border:1px solid #ddd;font-size:12px}.legacy button{transition:all .3s}@media(max-width:600px){.legacy{transform:scale(.72);transform-origin:top left}}""",
        "context": {"primaryRole":"仓库与质量管理员","primaryTask":"每天高频查找批次、比较可用量并处理质检异常","successMetric":"减少查找时间和批次处理错误","frequency":"每天高频","userExpertise":"专业用户","environment":"办公室桌面和仓库平板混合","risk":"高风险业务处理","informationDensity":"高","devicePriority":"桌面优先","painPoints":["列多且手机缩放","异常和下一步不突出","返回后筛选丢失"],"mustPreserve":["物料与批次字段语义","库存冻结规则"],"patternOverride":"data-workbench","skeletonOverride":"list-detail-inventory-batch","visualDirection":"dense-operations"},
    },
    "education-enrollment": {
        "title": "教育报名与资料审核表单",
        "html": """<!doctype html><html lang='zh-CN'><body><h1>新生报名</h1><form><label>学生姓名<input></label><label>证件号<input></label><label>年级<select><option>一年级</option></select></label><label>监护人<input></label><label>联系电话<input></label><label>住址<textarea></textarea></label><label>证明材料<input type='file'></label><button>提交报名</button></form></body></html>""",
        "css": """body{font-family:Arial;color:#333}form{width:920px;padding:20px}label{display:block;margin:10px 0}input,select,textarea{width:100%;height:32px;border:1px solid #bbb}button{background:#1677ff;color:white;transition:all .2s}textarea{height:100px}@media(max-width:600px){form{width:900px}}""",
        "context": {"primaryRole":"家长与招生审核员","primaryTask":"低频完成报名、保存资料并复核提交","successMetric":"提高首次提交成功率并减少资料补交","frequency":"每学期低频","userExpertise":"普通新手","environment":"家庭手机和学校桌面混合","risk":"中高风险提交","informationDensity":"中等","devicePriority":"移动优先","painPoints":["长表单不知道进度","错误只在提交后出现","材料上传失败会丢失"],"mustPreserve":["招生字段和审核流程"],"patternOverride":"guided-form","skeletonOverride":"form-application","visualDirection":"warm-professional"},
    },
    "logistics-dispatch": {
        "title": "物流调度与移动异常处理",
        "html": """<!doctype html><html lang='zh-CN'><body><header><h1>今日配送任务</h1></header><div class='cards'><article><b>沪A-102</b><p>南京东路 → 浦东仓</p><span>运输中</span><button>到达确认</button></article><article><b>沪B-226</b><p>昆山仓 → 苏州门店</p><span>延误</span><button>异常上报</button></article></div></body></html>""",
        "css": """body{margin:0;font-family:Arial}.cards{width:1100px;display:grid;grid-template-columns:repeat(3,1fr);gap:16px}.cards article{position:relative;height:180px;padding:14px;border:1px solid #ddd}.cards button{position:absolute;right:10px;bottom:10px;height:34px}.cards span{color:red}@media(max-width:600px){.cards{width:1000px}}""",
        "context": {"primaryRole":"司机与调度员","primaryTask":"在移动现场查看下一站、确认到达并上报异常","successMetric":"减少单次处理步骤并提升弱网成功率","frequency":"每天高频","userExpertise":"普通用户","environment":"移动现场单手和车载环境","risk":"高风险状态写入","informationDensity":"低到中等","devicePriority":"移动优先","painPoints":["按钮难以单手触达","弱网失败没有保留","状态只靠颜色"],"mustPreserve":["任务顺序","到达与异常状态机"],"patternOverride":"mobile-field","skeletonOverride":"field-delivery-mobile","visualDirection":"field-friendly"},
    },
}


def main() -> int:
    from web_ui_quality.release_info import configure_stdout

    configure_stdout()
    OUT.mkdir(parents=True, exist_ok=True)
    links = []
    for case_id, case in CASES.items():
        case_dir = OUT / case_id
        source = case_dir / "before"
        source.mkdir(parents=True, exist_ok=True)
        (source / "index.html").write_text(case["html"], encoding="utf-8")
        (source / "styles.css").write_text(case["css"], encoding="utf-8")
        (case_dir / "business-context.json").write_text(json.dumps(case["context"], ensure_ascii=False, indent=2), encoding="utf-8")
        report = audit_project(source, business_context=case["context"])
        generated = case_dir / "generated"
        generated.mkdir(exist_ok=True)
        (generated / "experience-core.json").write_text(json.dumps(report["experienceCore"], ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        generate_experience_preview(report["experienceCore"], generated / "preview", title=case["title"])
        generate_experience_studio(report["experienceCore"], generated / "studio", title=case["title"])
        (case_dir / "measurement-plan.json").write_text(json.dumps({
            "status":"PLANNED_NOT_MEASURED",
            "primaryTask":case["context"]["primaryTask"],
            "metrics":["任务完成时间","操作步骤","首次完成率","移动端通过率","用户偏好","业务回归"],
            "note":"代表性 Fixture 仅验证产品流程；真实效果必须在 v2.3 经真实用户与真实项目测量。",
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        links.append((case_id, case["title"], report["experienceCore"]["qualityReadiness"]["score"]))
    cards = "".join(f"<a class='card' href='{cid}/generated/studio/index.html'><b>{title}</b><span>实施准备度 {score}</span><small>打开交互 Studio →</small></a>" for cid,title,score in links)
    (OUT / "index.html").write_text(f"""<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Experience Fusion 代表场景</title><style>body{{margin:0;padding:40px;background:#f4f6f8;font-family:Inter,'PingFang SC',sans-serif;color:#182230}}h1{{margin-bottom:8px}}p{{color:#667085}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px;margin-top:28px}}.card{{display:grid;gap:10px;padding:20px;border:1px solid #dfe5ec;border-radius:16px;background:white;color:inherit;text-decoration:none;box-shadow:0 12px 36px rgba(31,41,55,.07)}}.card span,.card small{{color:#667085}}</style></head><body><h1>v2.1 Experience Fusion 代表场景</h1><p>这些是生产化特征较强的测试 Fixture，不是客户案例，也不作为业务效果证明。</p><div class='grid'>{cards}</div></body></html>""", encoding="utf-8")
    (OUT / "README.md").write_text("# v2.1 representative fixtures\n\n制造库存、教育报名、物流移动调度三类场景用于验证路由、修复、Token 映射、交互合同和 Studio 输出。它们不是客户证据，效果指标保持 `PLANNED_NOT_MEASURED`。\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
