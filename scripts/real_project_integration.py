#!/usr/bin/env python3
from __future__ import annotations
import json, tempfile, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"runtime"/"python"))
from web_ui_quality.experience_fix import run_experience_fix
from web_ui_quality.project_launcher import inspect_project_start


def main()->int:
    from web_ui_quality.release_info import configure_stdout

    configure_stdout()
    checks=[]
    with tempfile.TemporaryDirectory() as tmp:
        base=Path(tmp); project=base/"demo"; project.mkdir()
        (project/"index.html").write_text("""<!doctype html><html lang=zh-CN><body><main><h1>订单工作台</h1><details><summary>展开详情</summary><p>内容</p></details></main></body></html>""",encoding="utf-8")
        launch=inspect_project_start(project)
        checks.append(("static-launch-plan",launch["status"]=="TRUSTED_STATIC_SERVER_AVAILABLE"))
        artifacts=base/"artifacts"
        result=run_experience_fix(project,artifacts,request="看看这个页面",task_id="integration-task",session_id="integration-session",environment="local")
        run_dirs=sorted(path for path in artifacts.glob("wuq-*") if path.is_dir())
        run_dir=run_dirs[-1] if run_dirs else artifacts/"missing"
        checks.append(("experience-run-created",(run_dir/"run.json").is_file()))
        checks.append(("before-sealed",(run_dir/"before"/".sealed").is_file() and (run_dir/"before"/"manifest.json").is_file()))
        checks.append(("main-report",(run_dir/"before"/"index.html").is_file()))
        checks.append(("page-health-present",isinstance(result.get("pageHealth"),dict)))
        redesign=run_experience_fix(project,base/"redesign",request="重新设计这个后台",task_id="redesign-task",session_id="integration-session")
        checks.append(("redesign-hard-stop",redesign.get("hardStop") is True and redesign.get("hostBridge",{}).get("action")=="submitProductConfirmation"))
    failed=[n for n,o in checks if not o]
    result={"status":"PASS" if not failed else "FAIL","scope":"REAL_PROJECT_INTEGRATION","checks":[{"id":n,"status":"PASS" if o else "FAIL"} for n,o in checks]}
    print(json.dumps(result,ensure_ascii=False,indent=2)); return 1 if failed else 0
if __name__=="__main__": raise SystemExit(main())
