#!/usr/bin/env python3
"""Independent public-mainline V3 closure acceptance."""
from __future__ import annotations
import json, os, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
RUNTIME=ROOT/'runtime'/'python'
def main()->int:
    env=dict(os.environ); env['PYTHONPATH']=str(RUNTIME)+(os.pathsep+env['PYTHONPATH'] if env.get('PYTHONPATH') else '')
    c=subprocess.run([sys.executable,'-B','-m','pytest','tests/test_421_trust_release_closure.py','-q'],cwd=ROOT,env=env,check=False)
    payload={'status':'PASS' if c.returncode==0 else 'FAIL','scope':'PUBLIC_RUN_V3_TRUST_CLOSURE','legacyReceiptMayVerify':False,'v3RequiredForVerified':True,'realCodexHostQualification':'NOT_MEASURED'}
    print(json.dumps(payload,ensure_ascii=False,indent=2))
    return c.returncode
if __name__=='__main__': raise SystemExit(main())
