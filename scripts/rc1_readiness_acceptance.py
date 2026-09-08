#!/usr/bin/env python3
"""Verify the archived 4.1.0-rc.1 status record shipped inside later 4.1 packages.

This is not the current-package readiness gate after GA. Use ga_readiness_acceptance.py
for 4.1.0. The RC artifact is preserved rather than rewritten into GA evidence.
"""
from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def main()->int:
    path=ROOT/'RC1-RELEASE-CANDIDATE-STATUS.json'
    checks=[]
    def add(cid,ok,detail): checks.append({'id':cid,'status':'PASS' if ok else 'FAIL','detail':detail})
    try:
        status=json.loads(path.read_text(encoding='utf-8'))
    except Exception as exc:
        print(json.dumps({'status':'FAIL','scope':'WUQ_4_1_RC1_ARCHIVAL_RECORD','error':str(exc)},indent=2)); return 1
    add('RC-ARCH-001',status.get('packageVersion')=='4.1.0-rc.1',status.get('packageVersion'))
    add('RC-ARCH-002',status.get('kernelBaseVersion')=='4.0.0-rc.1',status.get('kernelBaseVersion'))
    add('RC-ARCH-003',status.get('featureFreeze')=='FEATURE_FROZEN',status.get('featureFreeze'))
    add('RC-ARCH-004',status.get('realWorldPredictiveValidity')=='NOT_MEASURED',status.get('realWorldPredictiveValidity'))
    add('RC-ARCH-005',status.get('realCodexHostEnforcement')=='NOT_MEASURED',status.get('realCodexHostEnforcement'))
    failed=[x for x in checks if x['status']!='PASS']
    print(json.dumps({'status':'FAIL' if failed else 'PASS','scope':'WUQ_4_1_RC1_ARCHIVAL_RECORD','checks':checks,'claimBoundary':'This verifies only the archived RC.1 status record; it does not re-run the RC.1 package after GA.'},ensure_ascii=False,indent=2))
    return 1 if failed else 0
if __name__=='__main__': raise SystemExit(main())
