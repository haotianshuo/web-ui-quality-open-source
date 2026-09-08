#!/usr/bin/env python3
"""Independent alpha.6 qualification-harness acceptance.

All rows built here are test fixtures.  They validate qualification mechanics but
never constitute real-world predictive evidence.
"""
from __future__ import annotations
import json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; RUNTIME=ROOT/'runtime/python'
if str(RUNTIME) not in sys.path: sys.path.insert(0,str(RUNTIME))
from web_ui_quality.release_info import PACKAGE_VERSION, KERNEL_BASE_VERSION
from web_ui_quality.phase1_shadow import build_shadow_observation
from web_ui_quality.phase2_signal_dataset import build_dataset_record, build_outcome_label
from web_ui_quality.phase2_qualification import build_qualification_plan, build_qualification_case, qualification_case_eligibility, analyze_shadow_qualification
from web_ui_quality.schema_validation import validate_instance

def shadow(run,bad=False):
    fixed={'status':'VERIFIED' if bad else 'NOT_VERIFIED','taskResult':{'status':'VERIFIED' if bad else 'NOT_VERIFIED'},'projectToolEvidence':[{'tool':'tests','status':'FAIL'}] if bad else []}
    return build_shadow_observation(run_id=run,task_id=f't-{run}',session_id='s',request='private',selected_mode='FIX_AND_VERIFY',target_kind='url',intent_route={'intent':'REPAIR_SMALL','specialty':None,'writeRequested':True,'readOnlyRequired':False},control_intent={'action':'FIX','profile':'standard','protectedScope':[]},fixed_result=fixed)
def label(run,outcome,source='EXTERNAL_ORACLE',split='DEVELOPMENT'):
    return build_outcome_label(run_id=run,task_id=f't-{run}',session_id='s',source=source,outcome=outcome,independence='INDEPENDENT',split=split,evaluator_id='acceptance-only',evidence_digest='a'*64,created_at='2026-08-11T00:00:00Z')
def rec(run,bad=False,source='EXTERNAL_ORACLE',split='DEVELOPMENT'):
    return build_dataset_record(shadow(run,bad),outcome_label=label(run,'BAD' if bad else 'GOOD',source,split))
def qcase(run,bad=False,origin='CONTROLLED_BENCHMARK',prov='BENCHMARK_CONTROLLER_ATTESTED',source='EXTERNAL_ORACLE'):
    return build_qualification_case(rec(run,bad,source),data_origin=origin,provenance_integrity=prov,provenance_evidence_digest='b'*64,task_family='acceptance',host_id='test-host',model_id='test-model',reasoning_mode='test',repo_scale='SMALL',risk_tier='T1',captured_at='2026-08-11T00:00:00Z')
def ck(name,ok,detail=''): return {'name':name,'status':'PASS' if ok else 'FAIL','detail':detail}
def main():
    checks=[]
    plan=build_qualification_plan(plan_id='acceptance',created_at='2026-08-11T00:00:00Z',minimum_real_world_rows=4,minimum_task_families=1,minimum_hosts=1,minimum_models=1,minimum_signal_support=2,minimum_precision=.8,minimum_recall=.8,maximum_false_positive_rate=.2)
    controlled=[qcase(f'c{i}',bool(i%2)) for i in range(6)]
    cr=analyze_shadow_qualification(controlled,plan)
    checks.append(ck('controlled_never_becomes_real_world',cr['controlledEvidenceStatus']=='CONTROLLED_ORACLE_MEASURED' and cr['realWorldEvidenceStatus']=='NOT_MEASURED'))
    declared=qcase('declared',False,origin='PRODUCTION_SHADOW',prov='DECLARED_ONLY',source='HOST_ACCEPTANCE')
    checks.append(ck('declared_production_excluded',qualification_case_eligibility(declared)['reason']=='PRODUCTION_PROVENANCE_NOT_HOST_ATTESTED'))
    synth=qcase('synthetic',False,origin='SYNTHETIC_FIXTURE',prov='TEST_ONLY')
    checks.append(ck('synthetic_excluded',qualification_case_eligibility(synth)['reason']=='SYNTHETIC_NOT_QUALIFICATION_EVIDENCE'))
    real=[]
    for i in range(3): real.append(qcase(f'rb{i}',True,origin='PRODUCTION_SHADOW',prov='HOST_ATTESTED',source='HOST_ACCEPTANCE'))
    for i in range(3): real.append(qcase(f'rg{i}',False,origin='PRODUCTION_SHADOW',prov='HOST_ATTESTED',source='HOST_ACCEPTANCE'))
    rr=analyze_shadow_qualification(real,plan)
    checks.append(ck('test_fixture_can_exercise_real_world_branch_without_becoming_evidence',rr['qualificationDecision']=='READY_FOR_PHASE3_5_PREREGISTRATION'))
    checks.append(ck('no_adaptive_activation',rr['profileRecommendation']=='NOT_EVALUATED_UNTIL_PHASE3_5_GATE' and rr['adaptiveEffect']=='NONE'))
    hold=qcase('hold',True,origin='PRODUCTION_SHADOW',prov='HOST_ATTESTED',source='HOST_ACCEPTANCE'); hold['datasetRecord']['label']['split']='HOLDOUT'
    hr=analyze_shadow_qualification([hold],plan)
    checks.append(ck('holdout_default_excluded',hr['realWorldCoverage']['rowCount']==0))
    dup=[real[0],dict(real[0])]; dup[1]['caseId']='duplicate'; dup[1]['caseDigest']='duplicate-digest-123456'
    dr=analyze_shadow_qualification(dup,plan)
    checks.append(ck('duplicate_binding_not_double_counted',dr['duplicateTaskBindingCount']==1 and dr['realWorldCoverage']['rowCount']==1))
    base=ROOT/'schemas'
    for name,val in [('qualification-plan-v1.schema.json',plan),('qualification-case-v1.schema.json',real[0]),('qualification-report-v1.schema.json',rr)]:
        validate_instance(val,json.loads((base/name).read_text(encoding='utf-8')),base_dir=base); checks.append(ck(name,True))
    checks.append(ck('real_world_claim_remains_not_measured','NOT_MEASURED'=='NOT_MEASURED','Acceptance uses generated test fixtures, not collected production evidence.'))
    result={'status':'PASS' if all(x['status']=='PASS' for x in checks) else 'FAIL','scope':'PHASE2_INDEPENDENT_SHADOW_QUALIFICATION_HARNESS','packageVersion':PACKAGE_VERSION,'kernelBase':KERNEL_BASE_VERSION,'controlledQualification':'HARNESS_MEASURED_ONLY','realWorldPredictiveValidity':'NOT_MEASURED','adaptiveAutonomy':'NOT_ACTIVE','checks':checks}
    print(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)); return 0 if result['status']=='PASS' else 1
if __name__=='__main__': raise SystemExit(main())
