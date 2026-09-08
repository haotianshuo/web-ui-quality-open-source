#!/usr/bin/env python3
"""Run the alpha.6 independent shadow qualification harness offline."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
RUNTIME=ROOT/'runtime/python'
if str(RUNTIME) not in sys.path: sys.path.insert(0,str(RUNTIME))
from web_ui_quality.phase2_qualification import analyze_shadow_qualification
from web_ui_quality.schema_validation import validate_instance


def main()->int:
    p=argparse.ArgumentParser(description='Analyze independent shadow qualification cases without activating adaptation')
    p.add_argument('cases',type=Path,help='JSONL qualification cases')
    p.add_argument('--plan',type=Path,required=True)
    p.add_argument('--include-holdout',action='store_true')
    p.add_argument('--output',type=Path)
    args=p.parse_args()
    plan=json.loads(args.plan.read_text(encoding='utf-8'))
    rows=[]
    for line in args.cases.read_text(encoding='utf-8').splitlines():
        if line.strip(): rows.append(json.loads(line))
    report=analyze_shadow_qualification(rows,plan,include_holdout=args.include_holdout)
    schema=json.loads((ROOT/'schemas/qualification-report-v1.schema.json').read_text(encoding='utf-8'))
    validate_instance(report,schema,base_dir=ROOT/'schemas')
    text=json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+'\n'
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(text,encoding='utf-8')
    print(text,end='')
    return 0
if __name__=='__main__': raise SystemExit(main())
