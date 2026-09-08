#!/usr/bin/env python3
"""Independent acceptance for alpha.5 shadow dataset / signal-validity pre-gate."""
from __future__ import annotations
import json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
RUNTIME=ROOT/'runtime/python'
if str(RUNTIME) not in sys.path: sys.path.insert(0,str(RUNTIME))
from web_ui_quality.release_info import PACKAGE_VERSION, KERNEL_BASE_VERSION
from web_ui_quality.phase1_shadow import build_shadow_observation
from web_ui_quality.phase2_signal_dataset import build_dataset_record, build_outcome_label, label_validity_eligibility
from web_ui_quality.phase2_signal_validity import analyze_signal_validity
from web_ui_quality.schema_validation import validate_instance


def shadow(run,*,bad=False):
    fixed={
        'status':'VERIFIED' if bad else 'NOT_VERIFIED',
        'taskResult':{'status':'VERIFIED' if bad else 'NOT_VERIFIED'},
        'projectToolEvidence':[{'tool':'tests','status':'FAIL'}] if bad else [],
    }
    return build_shadow_observation(
        run_id=run,task_id=f't-{run}',session_id='s',request='private',selected_mode='FIX_AND_VERIFY',target_kind='url',
        intent_route={'intent':'REPAIR_SMALL','specialty':None,'writeRequested':True,'readOnlyRequired':False},
        control_intent={'action':'FIX','profile':'standard','protectedScope':[]},fixed_result=fixed)


def label(run,outcome,source='EXTERNAL_ORACLE',independence='INDEPENDENT',split='DEVELOPMENT'):
    return build_outcome_label(run_id=run,task_id=f't-{run}',session_id='s',source=source,outcome=outcome,independence=independence,split=split,evaluator_id='acceptance-oracle',evidence_digest='a'*64,created_at='2026-08-11T00:00:00Z')


def check(name,ok,detail=''):
    return {'name':name,'status':'PASS' if ok else 'FAIL','detail':detail}


def main()->int:
    checks=[]
    unlabeled=build_dataset_record(shadow('u'))
    r0=analyze_signal_validity([unlabeled],minimum_independent_rows=1,minimum_signal_support=1)
    checks.append(check('unlabelled_not_measured',r0['predictiveValidity']=='NOT_MEASURED'))
    proxy=build_dataset_record(shadow('p'),outcome_label=label('p','BAD','FIXED_WORKFLOW_PROXY','POTENTIALLY_DEPENDENT'))
    rp=analyze_signal_validity([proxy],minimum_independent_rows=1,minimum_signal_support=1)
    checks.append(check('proxy_label_excluded',rp['independentlyLabelledRowCount']==0 and rp['excludedReasonCounts'].get('LABEL_SOURCE_NOT_CONFIRMATORY')==1))
    hold=build_dataset_record(shadow('h',bad=True),outcome_label=label('h','BAD',split='HOLDOUT'))
    rh=analyze_signal_validity([hold],minimum_independent_rows=1,minimum_signal_support=1)
    checks.append(check('holdout_excluded_by_default',rh['independentlyLabelledRowCount']==0 and rh['holdoutUsed'] is False))
    rows=[]
    for i in range(6):
        run=f'b{i}'; rows.append(build_dataset_record(shadow(run,bad=True),outcome_label=label(run,'BAD')))
    for i in range(6):
        run=f'g{i}'; rows.append(build_dataset_record(shadow(run,bad=False),outcome_label=label(run,'GOOD')))
    report=analyze_signal_validity(rows,minimum_independent_rows=10,minimum_signal_support=3)
    metric={m['code']:m for m in report['signalMetrics']}.get('TOOL_FAILURE_WITH_SUCCESS_CLAIM_CONFLICT')
    checks.append(check('negative_signal_measured',bool(metric) and metric['polarity']=='NEGATIVE' and metric['tp']==6 and metric['fp']==0))
    checks.append(check('development_pre_gate_only',report['predictiveValidity']=='PRE_GATE_MEASURED_DEVELOPMENT_ONLY'))
    checks.append(check('no_adaptive_recommendation',report['profileRecommendation']=='NOT_EVALUATED_UNTIL_SIGNAL_VALIDITY_GATE' and report['adaptiveEffect']=='NONE'))
    schemas=ROOT/'schemas'
    for file,value,name in [
        ('outcome-label-v1.schema.json',label('schema','GOOD'),'outcome_label_schema'),
        ('shadow-signal-dataset-record-v1.schema.json',build_dataset_record(shadow('schema2'),outcome_label=label('schema2','GOOD')),'dataset_record_schema'),
        ('signal-validity-report-v1.schema.json',report,'validity_report_schema')]:
        schema=json.loads((schemas/file).read_text(encoding='utf-8')); validate_instance(value,schema,base_dir=schemas); checks.append(check(name,True))
    try:
        build_dataset_record(shadow('mismatch'),outcome_label=label('other','GOOD'))
        mismatch=False
    except ValueError:
        mismatch=True
    checks.append(check('task_binding_mismatch_rejected',mismatch))
    eligible=label_validity_eligibility(label('e','GOOD'))
    checks.append(check('independent_external_label_eligible',eligible['eligible'] is True))
    outcome={'status':'PASS' if all(c['status']=='PASS' for c in checks) else 'FAIL','scope':'PHASE2_SIGNAL_VALIDITY_PRE_GATE','packageVersion':PACKAGE_VERSION,'kernelBase':KERNEL_BASE_VERSION,'predictiveValidity':'NOT_MEASURED_REAL_WORLD','adaptiveAutonomy':'NOT_ACTIVE','checks':checks}
    print(json.dumps(outcome,ensure_ascii=False,indent=2,sort_keys=True))
    return 0 if outcome['status']=='PASS' else 1
if __name__=='__main__': raise SystemExit(main())
