#!/usr/bin/env python3
"""Analyze alpha.5 labelled shadow rows without enabling adaptation."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
RUNTIME=ROOT/'runtime/python'
if str(RUNTIME) not in sys.path: sys.path.insert(0,str(RUNTIME))
from web_ui_quality.phase2_signal_validity import analyze_signal_validity


def main()->int:
    p=argparse.ArgumentParser(description='Compute development-only signal validity pre-gate metrics')
    p.add_argument('dataset',type=Path)
    p.add_argument('--output',type=Path)
    p.add_argument('--include-holdout',action='store_true',help='Explicitly analyze HOLDOUT labels; off by default')
    p.add_argument('--minimum-independent-rows',type=int,default=20)
    p.add_argument('--minimum-signal-support',type=int,default=5)
    args=p.parse_args()
    rows=[]
    for line in args.dataset.read_text(encoding='utf-8').splitlines():
        if not line.strip(): continue
        value=json.loads(line)
        if isinstance(value,dict): rows.append(value)
    result=analyze_signal_validity(rows,include_holdout=args.include_holdout,minimum_independent_rows=args.minimum_independent_rows,minimum_signal_support=args.minimum_signal_support)
    raw=json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+'\n'
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(raw,encoding='utf-8')
    print(raw,end='')
    return 0
if __name__=='__main__': raise SystemExit(main())
