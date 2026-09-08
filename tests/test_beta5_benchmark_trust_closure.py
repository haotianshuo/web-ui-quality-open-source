from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from fault_injection_harness import load_cases, prepare_all, prepare_case, score_host_observation
from agent_benchmark_qualification import ingest, _load, _save, _synthetic_host_result
from web_ui_quality.contracts import ContractViolation


def test_v2_repair_corpus_has_40_unique_archetypes_and_required_families():
    cases=load_cases(corpus='v2')
    assert len(cases)==40
    families={c['family'] for c in cases}
    assert {'systemic-root-cause','multi-file','protected-scope','pre-existing-errors','patch-quality','environment-honesty','executable-behavior'} <= families
    assert len({c['archetype'] for c in cases}) == 40


def test_host_controller_and_evaluator_are_separate_roots(tmp_path: Path):
    controller=tmp_path/'controller'
    value=prepare_all(controller,repetitions=1,corpus='v2')
    state=_load(controller/'benchmark-controller-state.json')
    host=Path(value['hostWorkspaceRoot']).resolve(); evaluator=Path(state['evaluatorRoot']).resolve(); control=controller.resolve()
    assert host != evaluator != control
    assert evaluator not in host.parents and host not in evaluator.parents
    assert control not in host.parents and host not in control.parents
    task=next(host.rglob('.wuq-benchmark-task.json')).read_text(encoding='utf-8')
    assert 'evaluatorRoot' not in task and 'expectedRootSources' not in task and 'allowedScope' not in task


def test_plan_tamper_is_rejected_before_ingest(tmp_path: Path):
    controller=tmp_path/'controller'; value=prepare_all(controller,repetitions=1)
    plan=_load(controller/'benchmark-plan.json'); plan['runCount']+=1
    (controller/'benchmark-plan.json').write_text(json.dumps(plan),encoding='utf-8')
    run=next(Path(value['hostWorkspaceRoot']).rglob('.wuq-benchmark-task.json'))
    task=json.loads(run.read_text(encoding='utf-8'))
    fake={'schemaVersion':'4','kind':'HOST_RESULT','protocolVersion':'4','conditionDigest':task['conditionDigest'],'runId':task['runId'],'caseId':task['caseId'],'repetition':task['repetition'],'host':task['plannedHost'],'conditions':task['plannedConditions'],'observation':{'outcome':'NOT_VERIFIED','rootCauseFiles':[],'regressions':[]},'metrics':{'wallTimeSeconds':None,'inputTokens':None,'outputTokens':None,'costUsd':None,'hostInteractions':None},'claimBoundary':'test'}
    incoming=tmp_path/'incoming.json'; incoming.write_text(json.dumps(fake),encoding='utf-8')
    with pytest.raises(ContractViolation) as caught: ingest(controller,incoming)
    assert caught.value.code=='BENCHMARK_PLAN_TAMPERED'


def test_ingest_is_immutable_and_controller_contained(tmp_path: Path):
    controller=tmp_path/'controller'; prepare_all(controller,repetitions=1)
    plan=_load(controller/'benchmark-plan.json'); state=_load(controller/'benchmark-controller-state.json'); run=plan['runs'][0]
    ev=_load(Path(state['evaluatorRoot'])/f"{run['runId']}.json")
    result=_synthetic_host_result(run,outcome='NOT_VERIFIED',roots=list(ev.get('expectedRootSources') or []))
    incoming=tmp_path/'incoming.json'; _save(incoming,result)
    recorded=ingest(controller,incoming); assert controller.resolve() in Path(recorded['resultPath']).resolve().parents
    with pytest.raises(ContractViolation) as caught: ingest(controller,incoming)
    assert caught.value.code=='BENCHMARK_RESULT_IMMUTABLE'


def test_root_precision_and_recall_are_real_set_metrics(tmp_path: Path):
    case=next(c for c in load_cases(corpus='v2') if c['family']=='responsive-layout')
    project=tmp_path/'project'; prepared=prepare_case(case,project)
    expected=case['expectedRootSources'][0]
    row=score_host_observation(prepared['evaluatorManifest'],project,{'outcome':'NOT_VERIFIED','rootCauseFiles':[expected,'wrong-a.ts','wrong-b.ts','wrong-c.ts'],'regressions':[]})
    assert row['rootCausePrecision']==pytest.approx(0.25)
    assert row['rootCauseRecall']==pytest.approx(1.0)


def test_noop_scope_precision_is_not_applicable(tmp_path: Path):
    case=next(c for c in load_cases(corpus='v2') if c['family']=='environment-honesty')
    project=tmp_path/'project'; prepared=prepare_case(case,project)
    row=score_host_observation(prepared['evaluatorManifest'],project,{'outcome':'NOT_VERIFIED','rootCauseFiles':[],'regressions':[]})
    assert row['repairSuccess'] is True
    assert row['scopePrecision'] is None
    assert row['repairAttempted'] is False


def test_behavioral_oracle_accepts_equivalent_not_exact_clean_content(tmp_path: Path):
    case=next(c for c in load_cases(corpus='v2') if c['family']=='responsive-layout')
    project=tmp_path/'project'; prepared=prepare_case(case,project)
    root=project/case['expectedRootSources'][0]
    root.write_text('.order-table { max-width:100%; overflow-x: auto; overscroll-behavior: contain; }\n',encoding='utf-8')
    row=score_host_observation(prepared['evaluatorManifest'],project,{'outcome':'VERIFIED','rootCauseFiles':case['expectedRootSources'],'regressions':[]})
    assert row['groundTruthSatisfied'] is True
    assert row['repairSuccess'] is True


def test_attack_suite_runs_1200_fake_agent_probes():
    completed=subprocess.run([sys.executable,'-B','scripts/benchmark_attack_suite.py'],cwd=ROOT,text=True,encoding='utf-8',errors='replace',capture_output=True,check=True)
    value=json.loads(completed.stdout)
    assert value['status']=='PASS' and value['probes']['fakeAgentRuns']==1200
    assert value['probes']['strategyFamilies'] >= 12


def test_desktop_qualification_pack_contains_72_pending_runs(tmp_path: Path):
    completed=subprocess.run([sys.executable,'-B','scripts/desktop_qualification_pack.py',str(tmp_path/'pack'),'--repetitions','3'],cwd=ROOT,text=True,encoding='utf-8',errors='replace',capture_output=True,check=True)
    value=json.loads(completed.stdout)
    assert value['runCount']==72 and value['agentScores']=='NOT_MEASURED'
    queue=json.loads((tmp_path/'pack'/'qualification-queue.json').read_text(encoding='utf-8'))
    assert len(queue['runs'])==72
    assert {r['host'] for r in queue['runs']}=={'codex-desktop','claude-desktop'}


def test_inspection_without_browser_evidence_asks_for_url():
    from web_ui_quality.task_result import build_task_result
    result={"status":"NOT_VERIFIED","runId":"r1","taskId":"t1","mode":"CHECK","before":{"topFindings":[]},"comparison":{},"projectBaseline":{},"taskGoal":{"goal":"移动端错位","nonGoals":[]}}
    value=build_task_result(result,request="移动端错位")
    assert "--url" in value["nextAction"]
    assert "不建议修改源码" in value["nextAction"]
