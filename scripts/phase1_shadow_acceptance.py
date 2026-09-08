#!/usr/bin/env python3
"""Package-self-reproducible acceptance for the alpha.5 production shadow path."""
from __future__ import annotations
import json, sys, tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RUNTIME=ROOT/'runtime'/'python'
if str(RUNTIME) not in sys.path: sys.path.insert(0,str(RUNTIME))
from web_ui_quality.release_info import PACKAGE_VERSION, KERNEL_BASE_VERSION

import web_ui_quality.experience_fix as ef
from web_ui_quality.phase1_shadow import adaptive_runtime_status


def fake_acceptance(*args, **kwargs):
    output=Path(kwargs['output_dir']); output.mkdir(parents=True,exist_ok=True)
    report={
        'status':'PASS','pageHealth':{'pageStatus':'PASS'},
        'journey':{'journeyId':'primary','status':'PASS','journey':[],'runs':[{'status':'PASS'}]},
        'findings':[],'topFindings':[],'deliveryConclusion':'alpha5 shadow acceptance','open':'index.html',
    }
    (output/'smart-acceptance-report.json').write_text(json.dumps(report),encoding='utf-8')
    return report


def main()->int:
    checks=[]
    status=adaptive_runtime_status()
    checks.append({'id':'S-001','status':'PASS' if status.get('productionWired') and status.get('mode')=='SHADOW_ONLY' and not status.get('authoritative') else 'FAIL','detail':status})
    original_acceptance=ef.run_smart_acceptance
    original_shadow=ef.build_shadow_observation
    try:
        ef.run_smart_acceptance=fake_acceptance
        with tempfile.TemporaryDirectory() as td:
            artifacts=Path(td)/'artifacts'
            result=ef.run_experience_fix('https://example.test/',artifacts,request='只检查响应式，不要改代码',mode='CHECK',task_id='shadow-a',session_id='shadow-s')
            run_dir=next(artifacts.glob('wuq-*'))
            files=sorted((run_dir/'experimental'/'phase1-shadow').glob('*-observation.json'))
            ok=result.get('status')=='PASS' and len(files)==1 and 'experimentalShadow' not in result
            checks.append({'id':'S-002','status':'PASS' if ok else 'FAIL','detail':f'fixed={result.get("status")} observations={len(files)}'})
            if files:
                obs=json.loads(files[0].read_text(encoding='utf-8'))
                inv=obs.get('invariants',{})
                safe=(obs.get('authoritative') is False and inv.get('fixedWorkflowAuthoritative') is True and inv.get('mayAuthorizeWrite') is False and inv.get('maySetClaimStatus') is False and inv.get('mayChangeTaskResult') is False and obs.get('hostBoundary',{}).get('realCodexHostEnforcement')=='NOT_MEASURED')
                checks.append({'id':'S-003','status':'PASS' if safe else 'FAIL','detail':'shadow authority isolation'})
                checks.append({'id':'S-004','status':'PASS' if '只检查响应式' not in files[0].read_text(encoding='utf-8') else 'FAIL','detail':'raw request not persisted'})
            else:
                checks += [{'id':'S-003','status':'FAIL','detail':'missing observation'},{'id':'S-004','status':'FAIL','detail':'missing observation'}]
        def broken(**kwargs): raise RuntimeError('shadow fault')
        ef.build_shadow_observation=broken
        with tempfile.TemporaryDirectory() as td:
            result=ef.run_experience_fix('https://example.test/',Path(td)/'artifacts',request='检查页面',mode='CHECK',task_id='shadow-f',session_id='shadow-fs')
            checks.append({'id':'S-005','status':'PASS' if result.get('status')=='PASS' else 'FAIL','detail':'shadow failure cannot alter fixed result'})
    finally:
        ef.run_smart_acceptance=original_acceptance
        ef.build_shadow_observation=original_shadow
    outcome={'status':'PASS' if all(c['status']=='PASS' for c in checks) else 'FAIL','scope':'PHASE1_RUNTIME_SHADOW_WIRING','packageVersion':PACKAGE_VERSION,'kernelBase':KERNEL_BASE_VERSION,'realCodexHostEnforcement':'NOT_MEASURED','adaptiveAutonomy':'NOT_ACTIVE','checks':checks}
    print(json.dumps(outcome,ensure_ascii=False,indent=2))
    return 0 if outcome['status']=='PASS' else 1
if __name__=='__main__': raise SystemExit(main())
