#!/usr/bin/env python3
"""Join alpha.5 dataset rows with an explicit alpha.6 qualification provenance manifest."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
RUNTIME=ROOT/'runtime/python'
if str(RUNTIME) not in sys.path: sys.path.insert(0,str(RUNTIME))
from web_ui_quality.phase2_qualification import build_qualification_case


def main()->int:
    p=argparse.ArgumentParser(description='Build qualification cases from dataset JSONL + provenance context JSONL')
    p.add_argument('dataset',type=Path)
    p.add_argument('--context',type=Path,required=True,help='JSONL keyed by datasetRecordDigest')
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    contexts={}
    for line in args.context.read_text(encoding='utf-8').splitlines():
        if not line.strip(): continue
        row=json.loads(line); key=str(row.get('datasetRecordDigest') or '')
        if not key: raise SystemExit('qualification context missing datasetRecordDigest')
        if key in contexts: raise SystemExit(f'duplicate qualification context for {key}')
        contexts[key]=row
    out=[]; missing=0
    for line in args.dataset.read_text(encoding='utf-8').splitlines():
        if not line.strip(): continue
        record=json.loads(line); key=str(record.get('datasetRecordDigest') or '')
        ctx=contexts.get(key)
        if ctx is None: missing+=1; continue
        out.append(build_qualification_case(
            record,data_origin=ctx['dataOrigin'],provenance_integrity=ctx['provenanceIntegrity'],
            provenance_evidence_digest=ctx['provenanceEvidenceDigest'],task_family=ctx['taskFamily'],host_id=ctx['hostId'],model_id=ctx['modelId'],reasoning_mode=ctx['reasoningMode'],repo_scale=ctx['repoScale'],risk_tier=ctx['riskTier'],captured_at=ctx['capturedAt']))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(''.join(json.dumps(x,ensure_ascii=False,sort_keys=True)+'\n' for x in out),encoding='utf-8')
    print(json.dumps({'status':'PASS','caseCount':len(out),'missingContextCount':missing,'realWorldPredictiveValidity':'NOT_EVALUATED_BY_CASE_BUILDER','authorityEffect':'NONE','adaptiveEffect':'NONE'},indent=2,sort_keys=True))
    return 0
if __name__=='__main__': raise SystemExit(main())
