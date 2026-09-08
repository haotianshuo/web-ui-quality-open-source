from __future__ import annotations
import json, subprocess, sys
from pathlib import Path
from web_ui_quality.phase1_shadow import build_shadow_observation
from web_ui_quality.phase2_signal_dataset import build_dataset_record, build_outcome_label
from web_ui_quality.phase2_qualification import build_qualification_plan, build_qualification_case, qualification_case_eligibility, analyze_shadow_qualification
from web_ui_quality.schema_validation import validate_instance
ROOT=Path(__file__).resolve().parents[1]


def shadow(run,bad=False):
    fixed={'status':'VERIFIED' if bad else 'NOT_VERIFIED','taskResult':{'status':'VERIFIED' if bad else 'NOT_VERIFIED'},'projectToolEvidence':[{'tool':'tests','status':'FAIL'}] if bad else []}
    return build_shadow_observation(run_id=run,task_id=f't-{run}',session_id='s',request='private',selected_mode='FIX_AND_VERIFY',target_kind='url',intent_route={'intent':'REPAIR_SMALL','specialty':None,'writeRequested':True,'readOnlyRequired':False},control_intent={'action':'FIX','profile':'standard','protectedScope':[]},fixed_result=fixed)

def label(run,outcome,source='HOST_ACCEPTANCE',split='DEVELOPMENT',independence='INDEPENDENT'):
    return build_outcome_label(run_id=run,task_id=f't-{run}',session_id='s',source=source,outcome=outcome,independence=independence,split=split,evaluator_id='independent-evaluator',evidence_digest='b'*64,created_at='2026-08-11T00:00:00Z')

def record(run,bad=False,source='HOST_ACCEPTANCE',split='DEVELOPMENT'):
    return build_dataset_record(shadow(run,bad=bad),outcome_label=label(run,'BAD' if bad else 'GOOD',source=source,split=split))

def case(run,bad=False,origin='PRODUCTION_SHADOW',provenance='HOST_ATTESTED',source='HOST_ACCEPTANCE',split='DEVELOPMENT',family='layout',host='host-a',model='model-a'):
    return build_qualification_case(record(run,bad=bad,source=source,split=split),data_origin=origin,provenance_integrity=provenance,provenance_evidence_digest='c'*64,task_family=family,host_id=host,model_id=model,reasoning_mode='high',repo_scale='MEDIUM',risk_tier='T2',captured_at='2026-08-11T00:00:00Z')

def plan(**kw):
    return build_qualification_plan(plan_id='plan',created_at='2026-08-11T00:00:00Z',minimum_real_world_rows=kw.get('rows',4),minimum_task_families=kw.get('families',1),minimum_hosts=kw.get('hosts',1),minimum_models=kw.get('models',1),minimum_signal_support=kw.get('support',2),minimum_precision=.8,minimum_recall=.8,maximum_false_positive_rate=.2)


def test_declared_production_provenance_cannot_count_as_real_world():
    c=case('d',provenance='DECLARED_ONLY')
    e=qualification_case_eligibility(c)
    assert e == {'eligible':False,'class':'EXCLUDED','reason':'PRODUCTION_PROVENANCE_NOT_HOST_ATTESTED'}
    r=analyze_shadow_qualification([c],plan(rows=1,support=1))
    assert r['qualificationStatus']=='NOT_MEASURED_REAL_WORLD'


def test_controlled_benchmark_never_satisfies_real_world_gate():
    rows=[case(f'c{i}',bad=bool(i%2),origin='CONTROLLED_BENCHMARK',provenance='BENCHMARK_CONTROLLER_ATTESTED',source='EXTERNAL_ORACLE') for i in range(6)]
    r=analyze_shadow_qualification(rows,plan(rows=2,support=1))
    assert r['controlledEvidenceStatus']=='CONTROLLED_ORACLE_MEASURED'
    assert r['realWorldEvidenceStatus']=='NOT_MEASURED'
    assert r['qualificationDecision']=='NOT_READY_NO_REAL_WORLD_CASES'


def test_synthetic_fixture_is_excluded_even_with_independent_label():
    c=case('s',origin='SYNTHETIC_FIXTURE',provenance='TEST_ONLY')
    e=qualification_case_eligibility(c)
    assert e['eligible'] is False and e['reason']=='SYNTHETIC_NOT_QUALIFICATION_EVIDENCE'


def test_real_world_coverage_gate_blocks_undercoverage():
    rows=[case('r1',False),case('r2',True)]
    r=analyze_shadow_qualification(rows,plan(rows=4,support=1))
    assert r['qualificationStatus']=='REAL_WORLD_DATA_INSUFFICIENT'
    assert r['qualificationDecision']=='NOT_READY_COVERAGE_REQUIREMENTS'


def test_balanced_real_world_pre_gate_can_be_ready_only_for_preregistration():
    rows=[]
    for i in range(4): rows.append(case(f'bad{i}',True,family='layout' if i<2 else 'state'))
    for i in range(4): rows.append(case(f'good{i}',False,family='layout' if i<2 else 'state'))
    r=analyze_shadow_qualification(rows,plan(rows=8,families=2,support=3))
    assert r['qualificationStatus']=='REAL_WORLD_PRE_GATE_MEASURED'
    assert r['qualificationDecision']=='READY_FOR_PHASE3_5_PREREGISTRATION'
    assert any(x['code']=='TOOL_FAILURE_WITH_SUCCESS_CLAIM_CONFLICT' for x in r['candidateSignals'])
    assert r['profileRecommendation']=='NOT_EVALUATED_UNTIL_PHASE3_5_GATE'
    assert r['adaptiveEffect']=='NONE'


def test_duplicate_task_binding_does_not_inflate_sample_size():
    a=case('dup',False); b=dict(a); b['caseId']='other'; b['caseDigest']='otherdigest123456'
    r=analyze_shadow_qualification([a,b],plan(rows=2,support=1))
    assert r['duplicateTaskBindingCount']==1
    assert r['realWorldCoverage']['rowCount']==1
    assert r['excludedReasonCounts']['DUPLICATE_TASK_BINDING']==1


def test_holdout_is_excluded_by_default_and_explicit_only_when_requested():
    c=case('h',True,split='HOLDOUT')
    r=analyze_shadow_qualification([c],plan(rows=1,support=1))
    assert r['realWorldCoverage']['rowCount']==0
    assert r['excludedReasonCounts']['HOLDOUT_EXCLUDED_BY_DEFAULT']==1
    e=analyze_shadow_qualification([c],plan(rows=1,support=1),include_holdout=True)
    assert e['realWorldCoverage']['rowCount']==1 and e['analysisMode']=='EXPLICIT_HOLDOUT_ANALYSIS'


def test_proxy_label_never_counts_as_real_world_qualification():
    c=build_qualification_case(record('proxy',source='FIXED_WORKFLOW_PROXY'),data_origin='PRODUCTION_SHADOW',provenance_integrity='HOST_ATTESTED',provenance_evidence_digest='c'*64,task_family='layout',host_id='h',model_id='m',reasoning_mode='high',repo_scale='SMALL',risk_tier='T1',captured_at='2026-08-11T00:00:00Z')
    r=analyze_shadow_qualification([c],plan(rows=1,support=1))
    assert r['realWorldCoverage']['rowCount']==0
    assert r['excludedReasonCounts']['LABEL_SOURCE_NOT_CONFIRMATORY']==1


def test_qualification_schemas_validate():
    p=plan(rows=1,support=1); c=case('schema'); r=analyze_shadow_qualification([c],p)
    base=ROOT/'schemas'
    for name,value in [('qualification-plan-v1.schema.json',p),('qualification-case-v1.schema.json',c),('qualification-report-v1.schema.json',r)]:
        validate_instance(value,json.loads((base/name).read_text(encoding='utf-8')),base_dir=base)


def test_cli_emits_valid_non_authoritative_report(tmp_path: Path):
    p=plan(rows=1,support=1); c=case('cli')
    pf=tmp_path/'plan.json'; cf=tmp_path/'cases.jsonl'
    pf.write_text(json.dumps(p),encoding='utf-8'); cf.write_text(json.dumps(c)+'\n',encoding='utf-8')
    done=subprocess.run([sys.executable,str(ROOT/'scripts/phase2_shadow_qualification.py'),str(cf),'--plan',str(pf)],cwd=ROOT,text=True,encoding='utf-8',errors='replace',capture_output=True)
    assert done.returncode==0, done.stderr
    r=json.loads(done.stdout); assert r['authoritative'] is False and r['authorityEffect']=='NONE' and r['adaptiveEffect']=='NONE'


def test_case_builder_requires_explicit_provenance_manifest(tmp_path: Path):
    rec=record('builder')
    ds=tmp_path/'dataset.jsonl'; ctx=tmp_path/'context.jsonl'; out=tmp_path/'cases.jsonl'
    ds.write_text(json.dumps(rec)+'\n',encoding='utf-8')
    context={'datasetRecordDigest':rec['datasetRecordDigest'],'dataOrigin':'CONTROLLED_BENCHMARK','provenanceIntegrity':'BENCHMARK_CONTROLLER_ATTESTED','provenanceEvidenceDigest':'d'*64,'taskFamily':'layout','hostId':'benchmark-controller','modelId':'model','reasoningMode':'high','repoScale':'SMALL','riskTier':'T1','capturedAt':'2026-08-11T00:00:00Z'}
    ctx.write_text(json.dumps(context)+'\n',encoding='utf-8')
    done=subprocess.run([sys.executable,str(ROOT/'scripts/phase2_build_qualification_cases.py'),str(ds),'--context',str(ctx),'--output',str(out)],cwd=ROOT,text=True,encoding='utf-8',errors='replace',capture_output=True)
    assert done.returncode==0, done.stderr
    built=json.loads(out.read_text(encoding='utf-8').strip())
    assert built['dataOrigin']=='CONTROLLED_BENCHMARK' and built['provenanceIntegrity']=='BENCHMARK_CONTROLLER_ATTESTED'


def test_qualification_acceptance_runner_passes():
    done=subprocess.run([sys.executable,str(ROOT/'scripts/phase2_qualification_acceptance.py')],cwd=ROOT,text=True,encoding='utf-8',errors='replace',capture_output=True)
    assert done.returncode==0, done.stderr+done.stdout
    result=json.loads(done.stdout); assert result['status']=='PASS' and result['realWorldPredictiveValidity']=='NOT_MEASURED'
