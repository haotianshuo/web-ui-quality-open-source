#!/usr/bin/env python3
"""Package-self-reproducible acceptance for alpha.4 capability shadow observation."""
from __future__ import annotations
import json, sys, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
RUNTIME=ROOT/'runtime/python'
if str(RUNTIME) not in sys.path: sys.path.insert(0,str(RUNTIME))
import web_ui_quality.experience_fix as ef
from web_ui_quality.phase1_shadow import build_shadow_observation
from web_ui_quality.phase2_signal_analysis import summarize_signal_observations


def make(fixed, *, read_only=False, write=False, mode='CHECK'):
    return build_shadow_observation(
        run_id='r',task_id='t',session_id='s',request='not persisted',selected_mode=mode,target_kind='url',
        intent_route={'intent':mode,'specialty':None,'writeRequested':write,'readOnlyRequired':read_only},
        control_intent={'action':'CHECK' if read_only else 'FIX','profile':'standard','protectedScope':[]},
        fixed_result=fixed,
    )


def fake_acceptance(*args, **kwargs):
    output=Path(kwargs['output_dir']); output.mkdir(parents=True,exist_ok=True)
    report={'status':'PASS','pageHealth':{'pageStatus':'PASS'},'journey':{'journeyId':'primary','status':'PASS','journey':[],'runs':[{'status':'PASS'}]},'findings':[],'topFindings':[],'deliveryConclusion':'alpha4 capability shadow acceptance','open':'index.html'}
    (output/'smart-acceptance-report.json').write_text(json.dumps(report),encoding='utf-8')
    return report


def main():
    checks=[]
    def ok(cid, cond, detail): checks.append({'id':cid,'status':'PASS' if cond else 'FAIL','detail':detail})
    honest=make({'status':'NOT_VERIFIED','taskResult':{'status':'NOT_VERIFIED'}},write=True,mode='FIX_AND_VERIFY')
    conflict=make({'status':'VERIFIED','taskResult':{'status':'VERIFIED'},'hostWriteReceipt':{'receiptId':'r'},'projectToolEvidence':[{'status':'FAIL'}]},write=True,mode='FIX_AND_VERIFY')
    ro=make({'status':'PASS','taskResult':{'status':'PASS'},'hostWriteReceipt':{'receiptId':'r'}},read_only=True)
    c1=honest['capabilitySignalObservation']; c2=conflict['capabilitySignalObservation']; c3=ro['capabilitySignalObservation']
    ok('CSO-001', c1['authoritative'] is False and c1['adaptiveEffect']=='NONE', 'signals are non-authoritative')
    ok('CSO-002', c1['semanticSignalsUsed'] is False, 'no semantic signal participates')
    ok('CSO-003', 'UNCERTAINTY_PRESERVED_BY_FIXED_WORKFLOW' in {r['code'] for r in c1['derivedDeterministicSignals']}, 'honest uncertainty is observed')
    ok('CSO-004', 'TOOL_FAILURE_WITH_SUCCESS_CLAIM_CONFLICT' in {r['code'] for r in c2['derivedDeterministicSignals']}, 'tool/success contradiction is detected mechanically')
    ok('CSO-005', 'READ_ONLY_WITH_WRITE_RECEIPT_CONFLICT' in {r['code'] for r in c3['derivedDeterministicSignals']}, 'read-only/write evidence contradiction is detected mechanically')
    summary=summarize_signal_observations([honest, conflict, ro])
    ok('CSO-006', summary['predictiveValidity']=='NOT_MEASURED' and summary['profileRecommendation'].startswith('NOT_EVALUATED'), 'frequency summary does not claim predictive validity or autonomy recommendation')
    original=ef.run_smart_acceptance
    try:
        ef.run_smart_acceptance=fake_acceptance
        with tempfile.TemporaryDirectory() as td:
            artifacts=Path(td)/'artifacts'
            result=ef.run_experience_fix('https://example.test/',artifacts,request='只检查响应式，不要改代码',mode='CHECK',task_id='cso-real',session_id='cso-real-s')
            run_dir=next(artifacts.glob('wuq-*'))
            obs_path=next((run_dir/'experimental'/'phase1-shadow').glob('*-observation.json'))
            persisted=json.loads(obs_path.read_text(encoding='utf-8'))
            signal=persisted.get('capabilitySignalObservation',{})
            ok('CSO-007', result.get('status')=='PASS' and signal.get('mode')=='SHADOW_ONLY' and signal.get('adaptiveEffect')=='NONE', 'real run persists capability signals without changing fixed result')
            ok('CSO-008', '只检查响应式' not in obs_path.read_text(encoding='utf-8'), 'raw request is not persisted in capability shadow artifact')
    finally:
        ef.run_smart_acceptance=original
    result={'status':'PASS' if all(r['status']=='PASS' for r in checks) else 'FAIL','passed':sum(r['status']=='PASS' for r in checks),'failed':sum(r['status']!='PASS' for r in checks),'checks':checks,'predictiveValidity':'NOT_MEASURED','adaptiveRuntime':'SHADOW_ONLY','realCodexHostEnforcement':'NOT_MEASURED'}
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result['status']=='PASS' else 1
if __name__=='__main__': raise SystemExit(main())
