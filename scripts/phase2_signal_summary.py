#!/usr/bin/env python3
"""Summarize alpha.4 capability-shadow artifacts without scoring or adapting."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
RUNTIME=ROOT/'runtime/python'
if str(RUNTIME) not in sys.path: sys.path.insert(0,str(RUNTIME))
from web_ui_quality.phase2_signal_analysis import summarize_signal_observations


def main()->int:
    parser=argparse.ArgumentParser(description='Summarize non-authoritative capability shadow observations')
    parser.add_argument('artifact_root',type=Path)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    rows=[]
    for path in sorted(args.artifact_root.rglob('experimental/phase1-shadow/*-observation.json')):
        try:
            value=json.loads(path.read_text(encoding='utf-8'))
        except (OSError,json.JSONDecodeError):
            continue
        if isinstance(value,dict): rows.append(value)
    result=summarize_signal_observations(rows)
    result['observationFiles']=len(rows)
    raw=json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+'\n'
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(raw,encoding='utf-8')
    print(raw,end='')
    return 0
if __name__=='__main__': raise SystemExit(main())
