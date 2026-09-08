from __future__ import annotations
import json, subprocess, sys
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))

from agent_benchmark_qualification import _controller
from fault_injection_harness import load_cases, prepare_all, prepare_case, score_host_observation
from web_ui_quality.benchmark_protocol import canonical_digest
from web_ui_quality.contracts import ContractViolation
from web_ui_quality.intent_router import route_user_intent
from web_ui_quality.risk_tier import classify_risk_tier
from web_ui_quality.change_budget import build_change_budget
from web_ui_quality.evidence_graph import build_evidence_graph


def test_runtime_convergence_keeps_architecture_controls():
    assert route_user_intent('检查刚才改的有没有回归')['taskIntent']=='VERIFY_ONLY'
    assert classify_risk_tier('修复登录权限判断',source_scope=['src/auth/guard.ts'])['tier']=='T4'
    assert build_change_budget('只修这个按钮',risk_tier='T1',explicit_files=['src/Button.tsx'])['maxFiles']==1
    graph=build_evidence_graph({'mode':'FIX_AND_VERIFY','status':'NOT_VERIFIED','taskGoal':{'goal':'x'}})
    assert 'graphDigest' in graph


def test_benchmark_protocol_v4_uses_controller_hmac(tmp_path: Path):
    controller=tmp_path/'controller'
    prepared=prepare_all(controller,repetitions=1,corpus='v2')
    assert prepared['integrityMode']=='CONTROLLER_HMAC_SHA256'
    assert (controller/'.benchmark-integrity.key').is_file()
    plan=json.loads((controller/'benchmark-plan.json').read_text(encoding='utf-8'))
    state=json.loads((controller/'benchmark-controller-state.json').read_text(encoding='utf-8'))
    assert plan['protocolVersion']=='4'
    assert len(plan['planMac'])==64 and len(state['stateMac'])==64
    assert state['integrityMode']=='CONTROLLER_HMAC_SHA256'


def test_rehashed_plan_without_hmac_key_is_rejected(tmp_path: Path):
    controller=tmp_path/'controller'; prepare_all(controller,repetitions=1,corpus='v2')
    plan_path=controller/'benchmark-plan.json'; plan=json.loads(plan_path.read_text(encoding='utf-8'))
    plan['runCount']=int(plan['runCount'])+1
    body={k:v for k,v in plan.items() if k not in {'planDigest','planMac'}}
    plan['planDigest']=canonical_digest(body)  # attacker can recompute SHA but not Controller HMAC
    plan_path.write_text(json.dumps(plan,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    with pytest.raises(ContractViolation) as caught:
        _controller(controller)
    assert caught.value.code=='BENCHMARK_PLAN_AUTH_FAILED'


def test_frozen_holdout_has_obfuscated_roots_and_oracle_diversity():
    cases=load_cases(corpus='holdout-v1')
    assert len(cases)==8
    assert len({c['archetype'] for c in cases})==8
    kinds={o['type'] for c in cases for o in c['oracle']}
    assert {'BROWSER_ASSERT','NODE_SCRIPT','NO_MUTATION','FILE_CONTAINS'} <= kinds
    assert any(c['expectedRootSources'] and any(part in c['expectedRootSources'][0] for part in ('a17','z9','m4','b2','q7','u2','k3')) for c in cases)


def test_browser_oracle_discriminates_broken_and_repaired_when_available(tmp_path: Path):
    case=next(c for c in load_cases(corpus='holdout-v1') if c['id']=='holdout-mobile-cta')
    project=tmp_path/'project'; prepared=prepare_case(case,project)
    obs={'outcome':'VERIFIED','rootCauseFiles':case['expectedRootSources'],'regressions':[]}
    broken=score_host_observation(prepared['evaluatorManifest'],project,obs)
    status=(broken.get('oracleResults') or [{}])[0].get('status')
    if status=='NOT_MEASURED_ENVIRONMENT': pytest.skip('Playwright/Chromium unavailable')
    assert status=='MEASURED'
    assert broken['groundTruthSatisfied'] is False
    for rel,content in case['cleanFiles'].items(): (project/rel).write_text(content,encoding='utf-8')
    repaired=score_host_observation(prepared['evaluatorManifest'],project,obs)
    assert repaired['groundTruthSatisfied'] is True
    assert repaired['oracleResults'][0]['oracleLevel']=='BROWSER_BEHAVIOR'
    assert repaired['oracleResults'][0]['networkPolicy']=='HTTP_HTTPS_ABORTED'
    assert repaired['oracleResults'][0]['fixtureMode']=='SECURE_CONTEXT_LOCAL_SYNTHETIC_ONLY'


def test_node_oracle_discloses_non_os_sandbox_boundary(tmp_path: Path):
    case=next(c for c in load_cases(corpus='holdout-v1') if c['id']=='holdout-latest-query')
    project=tmp_path/'project'; prepared=prepare_case(case,project)
    for rel,content in case['cleanFiles'].items(): (project/rel).write_text(content,encoding='utf-8')
    row=score_host_observation(prepared['evaluatorManifest'],project,{'outcome':'VERIFIED','rootCauseFiles':case['expectedRootSources'],'regressions':[]})
    oracle=row['oracleResults'][0]
    assert oracle['pass'] is True
    assert oracle['sandboxMode']=='PROCESS_LIMITED_NOT_OS_ISOLATED'
    assert 'no network/filesystem namespace isolation' in oracle['securityBoundary']


def test_holdout_acceptance_is_diagnostic_not_tuned_recall_gate():
    cp=subprocess.run([sys.executable,'-B','scripts/benchmark_holdout_acceptance.py'],cwd=ROOT,text=True,encoding='utf-8',errors='replace',capture_output=True,check=True,timeout=80)
    value=json.loads(cp.stdout)
    assert value['status']=='PASS'
    assert value['holdoutCaseCount']==8
    assert value['retrievalAt5']['releaseGate'] is False
    assert value['holdoutPolicy']=='FROZEN_VALIDATION_CORPUS_NOT_USED_AS_A_RECALL_RELEASE_GATE'
