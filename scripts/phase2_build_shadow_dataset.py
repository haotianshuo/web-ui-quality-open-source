#!/usr/bin/env python3
"""Build an offline alpha.5 signal dataset from production shadow artifacts."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
RUNTIME=ROOT/'runtime/python'
if str(RUNTIME) not in sys.path: sys.path.insert(0,str(RUNTIME))
from web_ui_quality.phase2_signal_dataset import build_dataset_record


def _binding(value):
    b=value.get('taskBinding') if isinstance(value,dict) else None
    if not isinstance(b,dict): return None
    result=tuple(str(b.get(k) or '') for k in ('runId','taskId','sessionId'))
    return result if all(result) else None


def main()->int:
    p=argparse.ArgumentParser(description='Build non-authoritative shadow signal dataset')
    p.add_argument('artifact_root',type=Path)
    p.add_argument('--labels',type=Path)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    labels={}
    if args.labels and args.labels.exists():
        for path in sorted(args.labels.rglob('*.json')):
            try: value=json.loads(path.read_text(encoding='utf-8'))
            except (OSError,json.JSONDecodeError): continue
            key=_binding(value)
            if key is None: continue
            if key in labels and labels[key] != value:
                raise SystemExit(f'conflicting outcome labels for {key}')
            labels[key]=value
    rows=[]
    for path in sorted(args.artifact_root.rglob('experimental/phase1-shadow/*-observation.json')):
        try: obs=json.loads(path.read_text(encoding='utf-8'))
        except (OSError,json.JSONDecodeError): continue
        key=_binding(obs)
        if key is None: continue
        rows.append(build_dataset_record(obs,outcome_label=labels.get(key)))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(''.join(json.dumps(row,ensure_ascii=False,sort_keys=True)+'\n' for row in rows),encoding='utf-8')
    summary={
        'status':'PASS','recordCount':len(rows),'labelCount':sum(1 for r in rows if r['label'] is not None),
        'unlabelledCount':sum(1 for r in rows if r['label'] is None),'authorityEffect':'NONE','adaptiveEffect':'NONE',
        'predictiveValidity':'NOT_EVALUATED_BY_DATASET_BUILDER',
    }
    print(json.dumps(summary,ensure_ascii=False,indent=2,sort_keys=True))
    return 0
if __name__=='__main__': raise SystemExit(main())
