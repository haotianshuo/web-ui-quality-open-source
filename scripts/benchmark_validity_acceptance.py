#!/usr/bin/env python3
"""Independent Beta.6 Benchmark Validity Closure acceptance."""
from __future__ import annotations
import json, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
RUNTIME=ROOT/'runtime'/'python'
if str(RUNTIME) not in sys.path: sys.path.insert(0,str(RUNTIME))
sys.path.insert(0,str(ROOT/'scripts'))
from web_ui_quality.release_info import PACKAGE_VERSION, KERNEL_VERSION, KERNEL_BASE_VERSION
from fault_injection_harness import load_cases, self_test as harness_self_test
from agent_benchmark_qualification import self_test as benchmark_self_test

EXPECTED=PACKAGE_VERSION

def main()->int:
    failures=[]
    cases=load_cases(corpus='v2')
    harness=harness_self_test()
    bench=benchmark_self_test()
    attack=json.loads(subprocess.run([sys.executable,'-B','scripts/benchmark_attack_suite.py'],cwd=ROOT,text=True,encoding='utf-8',errors='replace',capture_output=True,check=True).stdout)
    if len(cases)!=40: failures.append('case-count')
    if len({c.get('archetype') for c in cases})!=40: failures.append('archetype-diversity')
    if len({c.get('request') for c in cases})!=40: failures.append('request-diversity')
    kinds={str(o.get('type')) for c in cases for o in c.get('oracle',[])}
    if not {'FILE_CONTAINS','NODE_SCRIPT','NO_MUTATION'} <= kinds: failures.append('oracle-diversity')
    if harness.get('contextRetrieval',{}).get('measurementScope')!='ALL_APPLICABLE_CASES': failures.append('context-scope')
    if harness.get('contextRetrieval',{}).get('measuredRuns')!=36: failures.append('context-applicable-count')
    if harness.get('protectedScopeRecall')!=1.0: failures.append('protected-scope-recall')
    if bench.get('conditionAuthority')!='CONTROLLER_PLANNED': failures.append('condition-authority')
    if attack.get('probes',{}).get('strategyFamilies',0)<12: failures.append('attack-diversity')
    if attack.get('probes',{}).get('totalDeterministicProbes')!=1200: failures.append('attack-volume')
    payload={
      'schemaVersion':'1','status':'PASS' if not failures else 'FAIL','packageVersion':EXPECTED,'kernelVersion':KERNEL_VERSION,'kernelBaseVersion':KERNEL_BASE_VERSION,
      'caseCount':len(cases),'archetypeCount':len({c.get('archetype') for c in cases}),'familyCount':len({c.get('family') for c in cases}),
      'oracleKinds':sorted(kinds),'contextRetrieval':harness.get('contextRetrieval'),'protectedScopeRecall':harness.get('protectedScopeRecall'),
      'conditionAuthority':bench.get('conditionAuthority'),'attackStrategyFamilies':attack.get('probes',{}).get('strategyFamilies'),
      'deterministicProbeCount':attack.get('probes',{}).get('totalDeterministicProbes'),'failures':failures,
      'agentScores':'NOT_MEASURED','claimBoundary':'This acceptance qualifies benchmark validity mechanics and deterministic corpus behavior. It does not measure Claude/Codex accuracy or prove OS-level sandbox isolation.'
    }
    print(json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True))
    return 0 if not failures else 1
if __name__=='__main__': raise SystemExit(main())
