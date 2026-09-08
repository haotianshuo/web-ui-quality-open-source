#!/usr/bin/env python3
from __future__ import annotations
import json, subprocess, sys, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; RUNTIME=ROOT/'runtime/python'
if str(RUNTIME) not in sys.path: sys.path.insert(0,str(RUNTIME))
from web_ui_quality.release_info import PACKAGE_VERSION, KERNEL_BASE_VERSION
from web_ui_quality.phase1_shadow import build_shadow_observation
from web_ui_quality.phase2_collection import sanitize_shadow_observation, build_host_attestation_request, build_label_request, build_collection_manifest
from web_ui_quality.schema_validation import validate_instance

def fixed(): return {'status':'NOT_VERIFIED','taskResult':{'status':'NOT_VERIFIED'},'projectToolEvidence':[{'tool':'tests','status':'PASS'}]}
def obs(run='secret-run',task='secret-task',session='secret-session'):
    return build_shadow_observation(run_id=run,task_id=task,session_id=session,request='super secret user request',selected_mode='FIX_AND_VERIFY',target_kind='url',intent_route={'intent':'REPAIR_SMALL','specialty':'RESPONSIVE','writeRequested':True,'readOnlyRequired':False},control_intent={'action':'FIX','profile':'standard','protectedScope':['auth secret path']},fixed_result=fixed())
def ck(name,ok,detail=''): return {'name':name,'status':'PASS' if ok else 'FAIL','detail':detail}
def main():
    checks=[]; key=b'acceptance-key-material-32-bytes!!'; o=obs(); r=sanitize_shadow_observation(o,key)
    serialized=json.dumps(r,sort_keys=True)
    checks.append(ck('raw_binding_absent',all(x not in serialized for x in ['secret-run','secret-task','secret-session'])))
    checks.append(ck('raw_request_absent','super secret user request' not in serialized and str(o['requestDigest']) not in serialized))
    checks.append(ck('stable_pseudonymization',sanitize_shadow_observation(o,key)['taskBinding']==r['taskBinding']))
    checks.append(ck('different_key_changes_binding',sanitize_shadow_observation(o,b'another-acceptance-key-material')['taskBinding']!=r['taskBinding']))
    att=build_host_attestation_request(r,host_id='host',host_version='1',created_at='2026-08-11T00:00:00Z')
    checks.append(ck('attestation_request_not_verified',att['verificationStatus']=='REQUESTED_NOT_VERIFIED' and att['attestationEvidenceDigest'] is None))
    lab=build_label_request(r,requested_source='HUMAN_BLIND_REVIEW',split='DEVELOPMENT',created_at='2026-08-11T00:00:00Z')
    checks.append(ck('label_request_not_label',lab['outcome'] is None and lab['independence']=='UNASSESSED'))
    man=build_collection_manifest([r],created_at='2026-08-11T00:00:00Z')
    checks.append(ck('manifest_honesty',man['realWorldPredictiveValidity']=='NOT_MEASURED' and man['adaptiveGuidance']=='NOT_ACTIVE' and man['keyIncludedInPack'] is False))
    base=ROOT/'schemas'
    pairs=[('qualification-export-record-v1.schema.json',r),('host-attestation-request-v1.schema.json',att),('independent-label-request-v1.schema.json',lab),('qualification-collection-manifest-v1.schema.json',man)]
    for name,val in pairs:
        validate_instance(val,json.loads((base/name).read_text(encoding='utf-8')),base_dir=base); checks.append(ck(name,True))
    with tempfile.TemporaryDirectory(prefix='wuq-alpha7-') as td:
        td=Path(td); shadow=td/'shadow'; out=td/'pack'; shadow.mkdir(); (shadow/'one-observation.json').write_text(json.dumps(o),encoding='utf-8'); keyfile=td/'key'; keyfile.write_bytes(key)
        cp=subprocess.run([sys.executable,str(ROOT/'scripts/phase2_build_external_collection_pack.py'),str(shadow),'--output',str(out),'--key-file',str(keyfile),'--host-id','host','--host-version','1'],cwd=ROOT,text=True,encoding='utf-8',errors='replace',capture_output=True)
        checks.append(ck('cli_builds_pack',cp.returncode==0,cp.stderr[-300:]))
        contents=''.join(p.read_text(encoding='utf-8',errors='ignore') for p in out.glob('*') if p.is_file())
        checks.append(ck('pack_has_no_key_or_raw_ids',key.decode('utf-8') not in contents and 'secret-run' not in contents and 'super secret user request' not in contents))
    result={'status':'PASS' if all(x['status']=='PASS' for x in checks) else 'FAIL','scope':'PHASE2_EXTERNAL_QUALIFICATION_COLLECTION_PACK','packageVersion':PACKAGE_VERSION,'realWorldPredictiveValidity':'NOT_MEASURED','adaptiveGuidance':'NOT_ACTIVE','checks':checks}
    print(json.dumps(result,indent=2,sort_keys=True)); return 0 if result['status']=='PASS' else 1
if __name__=='__main__': raise SystemExit(main())
