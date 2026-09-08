#!/usr/bin/env python3
"""Environment-tolerant performance gate with p50/p95 history-compatible output."""
from __future__ import annotations
import argparse, json, os, statistics, subprocess, sys, tempfile, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; RUNTIME=ROOT/'runtime'/'python'; ENV=dict(os.environ,PYTHONPATH=str(RUNTIME),PYTHONDONTWRITEBYTECODE='1')

def samples(command:list[str], repeats:int=3)->list[float]:
    rows=[]
    for _ in range(repeats):
        start=time.perf_counter(); completed=subprocess.run(command,cwd=ROOT,env=ENV,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=15); rows.append(time.perf_counter()-start)
        if completed.returncode: raise RuntimeError(f'benchmark command failed: {command}')
    return rows

def pct(values:list[float], p:float)->float:
    rows=sorted(values); idx=(len(rows)-1)*p; lo=int(idx); hi=min(lo+1,len(rows)-1); frac=idx-lo; return rows[lo]*(1-frac)+rows[hi]*frac

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('--compare',type=Path); args=ap.parse_args()
    import_rows=samples([sys.executable,'-B','-c','import web_ui_quality']); help_rows=samples([sys.executable,'-B','-m','web_ui_quality','--help'])
    sys.path.insert(0,str(RUNTIME)); from web_ui_quality.project_baseline import build_project_baseline
    baseline_rows=[]
    with tempfile.TemporaryDirectory(prefix='wuq-perf-') as raw:
        project=Path(raw)
        for i in range(120): (project/f'file-{i:03d}.ts').write_text(f'export const v{i}={i};\n',encoding='utf-8')
        for _ in range(3):
            start=time.perf_counter(); baseline=build_project_baseline(project); baseline_rows.append(time.perf_counter()-start)
    metrics={
      'importSeconds':{'p50':round(pct(import_rows,.5),4),'p95':round(pct(import_rows,.95),4)},
      'helpSeconds':{'p50':round(pct(help_rows,.5),4),'p95':round(pct(help_rows,.95),4)},
      'baseline120FilesSeconds':{'p50':round(pct(baseline_rows,.5),4),'p95':round(pct(baseline_rows,.95),4)},
    }
    budgets={'importSeconds':3.5,'helpSeconds':4.0,'baseline120FilesSeconds':2.5}; failures=[]
    for name,limit in budgets.items():
        if metrics[name]['p95']>limit: failures.append(name+':absolute-p95')
    comparison=None
    if args.compare and args.compare.is_file():
        old=json.loads(args.compare.read_text(encoding='utf-8')); old_metrics=old.get('metrics',{}); deltas={};
        for name in metrics:
            if name in old_metrics:
                deltas[name]={}
                for q in ('p50','p95'):
                    prev=float(old_metrics[name][q]); cur=float(metrics[name][q]); delta=(cur-prev)/prev if prev>0 else None; deltas[name][q]=delta
                    if delta is not None and delta>0.10: failures.append(name+':'+q+':relative>10%')
        comparison={'reference':str(args.compare),'relativeDeltas':deltas,'threshold':0.10}
    if baseline.get('fileCount')!=120: failures.append('baselineFileCount')
    payload={'status':'PASS' if not failures else 'FAIL','metrics':metrics,'budgetsP95':budgets,'comparison':comparison,'samplesPerMetric':3,'failures':failures,'claimBoundary':'p50/p95 are meaningful only within the same environment. --compare enables same-environment relative regression gating at 10%; absolute budgets remain coarse disaster guards.'}
    print(json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True)); return 0 if not failures else 1
if __name__=='__main__': raise SystemExit(main())
