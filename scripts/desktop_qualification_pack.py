#!/usr/bin/env python3
"""Prepare two fully scoreable 36-run Desktop Host qualification controllers."""
from __future__ import annotations
import argparse, json, shutil, sys, uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT/'runtime'/'python') not in sys.path: sys.path.insert(0,str(ROOT/'runtime'/'python'))
from fault_injection_harness import load_cases, prepare_all

CORE_FAMILIES=['responsive-layout','systemic-root-cause','multi-file','protected-scope','pre-existing-errors','patch-quality','executable-behavior','environment-honesty']

def selected_cases():
    cases=load_cases(corpus='v2'); selected=[]
    for family in CORE_FAMILIES: selected.append(next(c for c in cases if c.get('family')==family))
    for family in ['systemic-root-cause','multi-file','protected-scope','patch-quality']:
        selected.append([c for c in cases if c.get('family')==family][1])
    return selected

def prepare(destination: Path,repetitions:int=3)->dict:
    destination=destination.resolve()
    if destination.exists(): shutil.rmtree(destination)
    destination.mkdir(parents=True)
    cases=selected_cases(); queue=[]; controllers={}
    for host in ['codex-desktop','claude-desktop']:
        token=uuid.uuid4().hex[:8]
        controller=destination/f'{host}-controller'
        host_root=destination.parent/f'{destination.name}-{host}-host-{token}'
        evaluator_root=destination.parent/f'.{destination.name}-{host}-evaluator-{token}'
        planned_host={'name':host,'version':'DESKTOP-APP','model':'USER_SELECTED_MODEL'}
        planned_conditions={'reasoningMode':'USER_SELECTED','permissionProfile':'WORKSPACE_ONLY','toolPolicy':'HOST_APPROVAL_REQUIRED','browserCondition':'USER_ENVIRONMENT','authCondition':'TASK_DEPENDENT','os':sys.platform,'runtime':f'python-{sys.version_info.major}.{sys.version_info.minor}','contextPolicy':'wuq-relevant-context-v1','wuqVersion':'4.0.0-rc.1','fixtureVersion':'fault-injection-v2'}
        prepared=prepare_all(controller,repetitions=repetitions,corpus='v2',host_root=host_root,evaluator_root=evaluator_root,cases_override=cases,planned_host=planned_host,planned_conditions=planned_conditions)
        controllers[host]={'controllerDir':str(controller),'hostWorkspaceRoot':prepared['hostWorkspaceRoot'],'runCount':prepared['runCount']}
        plan=json.loads((controller/'benchmark-plan.json').read_text(encoding='utf-8'))
        for run in plan['runs']:
            project=Path(run['projectPath'])
            task_json=json.loads(Path(run['taskPath']).read_text(encoding='utf-8'))
            task_md=(f"# Web UI Quality Desktop Qualification\n\nHost: **{host}**\n\nRun ID: `{run['runId']}`\n\n## Task\n\n{task_json['request']}\n\nProtected scope: `{', '.join(task_json['protectedScope']) or 'none'}`\n\nWork only inside this project. Do not search outside this workspace. When finished, create `host-result.json` following `agent-benchmark-result.schema.json`. Do not claim VERIFIED without evidence.\n")
            (project/'TASK.md').write_text(task_md,encoding='utf-8')
            template={'schemaVersion':'4','kind':'HOST_RESULT','protocolVersion':'4','runId':run['runId'],'caseId':run['caseId'],'repetition':run['repetition'],'conditionDigest':run['conditionDigest'],'host':run['plannedHost'],'conditions':run['plannedConditions'],'observation':{'outcome':'NOT_VERIFIED','rootCauseFiles':[],'regressions':[]},'metrics':{'wallTimeSeconds':None,'inputTokens':None,'outputTokens':None,'costUsd':None,'hostInteractions':None},'claimBoundary':'Complete observation/metrics from this run only. Do not edit Controller-planned host/conditions/conditionDigest.'}
            (project/'HOST_RESULT_TEMPLATE.json').write_text(json.dumps(template,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            queue.append({'host':host,'runId':run['runId'],'caseId':run['caseId'],'repetition':run['repetition'],'conditionDigest':run['conditionDigest'],'controllerDir':str(controller),'projectPath':str(project),'taskPath':str(project/'TASK.md'),'resultTemplate':str(project/'HOST_RESULT_TEMPLATE.json'),'resultPath':str(project/'host-result.json'),'ingestCommand':f"python -B scripts/agent_benchmark_qualification.py ingest {controller} {project/'host-result.json'}",'status':'PENDING'})
    payload={'schemaVersion':'4','hosts':['codex-desktop','claude-desktop'],'caseCount':len(cases),'repetitionsPerHostCase':repetitions,'runCount':len(queue),'controllers':controllers,'runs':queue,'agentScores':'NOT_MEASURED','claimBoundary':'Controllers/evaluator roots exist for scoring but must not be opened in the Desktop Host. Only each Host workspace root should be selected in Codex/Claude.'}
    (destination/'qualification-queue.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    first=queue[0]; (destination/'NEXT_TASK.txt').write_text(f"Host: {first['host']}\nRun: 1/{len(queue)}\nProject: {first['projectPath']}\nTask: {first['taskPath']}\nAfter completion: {first['ingestCommand']}\n",encoding='utf-8')
    return {'status':'READY','hosts':payload['hosts'],'caseCount':len(cases),'repetitionsPerHostCase':repetitions,'runCount':len(queue),'qualificationDir':str(destination),'controllers':controllers,'agentScores':'NOT_MEASURED'}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('destination',type=Path); ap.add_argument('--repetitions',type=int,default=3); a=ap.parse_args(); v=prepare(a.destination,a.repetitions); print(json.dumps(v,ensure_ascii=False,indent=2)); return 0
if __name__=='__main__': raise SystemExit(main())
