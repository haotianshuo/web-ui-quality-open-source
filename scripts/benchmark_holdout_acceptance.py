#!/usr/bin/env python3
"""Beta.7 frozen holdout / browser-oracle acceptance.

The holdout corpus is frozen and excluded from development-corpus tuning gates.
It is hidden from prepared Host workspaces, not secret from package maintainers.
"""
from __future__ import annotations
import json, sys, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
RUNTIME=ROOT/'runtime'/'python'
if str(RUNTIME) not in sys.path: sys.path.insert(0,str(RUNTIME))
sys.path.insert(0,str(ROOT/'scripts'))
from web_ui_quality.release_info import PACKAGE_VERSION, KERNEL_VERSION, KERNEL_BASE_VERSION
from fault_injection_harness import load_cases, prepare_case, score_host_observation
from web_ui_quality.context_packet import build_relevant_context_packet, context_retrieval_metrics
from web_ui_quality.project_baseline import build_project_baseline

EXPECTED=PACKAGE_VERSION

def main()->int:
    cases=load_cases(corpus='holdout-v1')
    failures=[]
    if len(cases)!=8: failures.append('holdout-case-count')
    if len({c.get('archetype') for c in cases})!=len(cases): failures.append('holdout-archetype-diversity')
    kinds={str(o.get('type')) for c in cases for o in c.get('oracle',[])}
    if not {'BROWSER_ASSERT','NODE_SCRIPT','NO_MUTATION','FILE_CONTAINS'} <= kinds: failures.append('holdout-oracle-diversity')
    # Retrieval is intentionally measured, not a release gate: this corpus is meant to expose overfitting.
    retrieval=[]
    with tempfile.TemporaryDirectory(prefix='wuq-holdout-') as raw:
        base=Path(raw)
        for case in cases:
            project=base/case['id']; prep=prepare_case(case,project)
            expected=list(case.get('expectedRootSources') or [])
            if expected:
                packet=build_relevant_context_packet(project,request=case['request'],task_goal={'goal':case['request'],'nonGoals':case.get('protectedScope',[])},baseline=build_project_baseline(project),max_source_refs=8)
                retrieval.append({'caseId':case['id'],**context_retrieval_metrics(packet,expected,k=5)})
        # Exercise exactly one browser case to keep acceptance bounded.
        browser_case=next(c for c in cases if any(o.get('type')=='BROWSER_ASSERT' for o in c.get('oracle',[])))
        project=base/'browser-check'; prepared=prepare_case(browser_case,project)
        obs={'outcome':'VERIFIED','rootCauseFiles':browser_case['expectedRootSources'],'regressions':[]}
        broken=score_host_observation(prepared['evaluatorManifest'],project,obs)
        for rel,content in dict(browser_case.get('cleanFiles') or {}).items():
            p=project/rel; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(str(content),encoding='utf-8')
        repaired=score_host_observation(prepared['evaluatorManifest'],project,obs)
        brow=(repaired.get('oracleResults') or [{}])[0]
        browser_status=brow.get('status')
        if browser_status=='MEASURED':
            if broken.get('groundTruthSatisfied') is not False or repaired.get('groundTruthSatisfied') is not True:
                failures.append('browser-oracle-discrimination')
        elif browser_status not in {'NOT_MEASURED_ENVIRONMENT','EXECUTION_FAILED'}:
            failures.append('browser-oracle-status')
    measured=[r for r in retrieval if isinstance(r.get('recall'),(int,float))]
    mean_recall=sum(float(r['recall']) for r in measured)/len(measured) if measured else None
    payload={
        'schemaVersion':'1','status':'PASS' if not failures else 'FAIL','packageVersion':EXPECTED,'kernelVersion':KERNEL_VERSION,'kernelBaseVersion':KERNEL_BASE_VERSION,
        'holdoutCaseCount':len(cases),'oracleKinds':sorted(kinds),'retrievalAt5':{'measuredCases':len(measured),'meanRecall':mean_recall,'releaseGate':False},
        'browserOracleStatus':browser_status,'browserOracleMeasured':browser_status=='MEASURED',
        'holdoutPolicy':'FROZEN_VALIDATION_CORPUS_NOT_USED_AS_A_RECALL_RELEASE_GATE',
        'failures':failures,
        'claimBoundary':'Holdout cases are hidden from prepared Host workspaces but are shipped with the package and are therefore not secret from maintainers. Retrieval metrics are diagnostic, not a tuned release gate. Browser assertions are measured only when Playwright/Chromium is available.'
    }
    print(json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True))
    return 0 if not failures else 1
if __name__=='__main__': raise SystemExit(main())
