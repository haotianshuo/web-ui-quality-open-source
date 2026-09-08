#!/usr/bin/env python3
"""Independent acceptance for the 4.2.3 package Phase1 trust boundary.

The script uses a temporary simulated Host. It does not claim real Codex Host
enforcement; it proves package-local contract behavior only.
"""
from __future__ import annotations

import argparse, hashlib, hmac, json, os, sys, tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RUNTIME=ROOT/'runtime'/'python'
if str(RUNTIME) not in sys.path:
    sys.path.insert(0,str(RUNTIME))
from web_ui_quality.release_info import PACKAGE_VERSION, KERNEL_BASE_VERSION

from web_ui_quality.contracts import ContractViolation, digest_json, hash_file
from web_ui_quality.phase1_boundaries import authorize_read_path, authorize_write_target
from web_ui_quality.phase1_capabilities import verify_capability_snapshot
from web_ui_quality.phase1_claims import evaluate_claim
from web_ui_quality.phase1_evidence import bind_host_observation
from web_ui_quality.phase1_host_apply import build_target_digest, prepare_host_apply_request, verify_host_write_receipt_v2
from web_ui_quality.phase1_task_result import aggregate_task_result

SECRET=b'phase1-acceptance-host-secret-not-shipped'
NOW=datetime(2026,8,11,9,0,tzinfo=timezone.utc)

def ts(m=0): return (NOW+timedelta(minutes=m)).isoformat().replace('+00:00','Z')
def sign(d): return 'hmac:'+hmac.new(SECRET,d.encode(),hashlib.sha256).hexdigest()
def verify(p,k): return isinstance(p.get('integrityTag'),str) and hmac.compare_digest(p['integrityTag'],sign(str(p.get(k))))
def assess(row):
    r=dict(row); r['assessmentDigest']=digest_json(r); return r

def common(cid,kind,level='ENFORCED'):
    return {'channelId':cid,'kind':kind,'capabilityLevel':level,'limitationCodes':[],'assessedAt':ts(),'validUntil':ts(60),'assessorId':'acceptance-host'}

def snapshot():
    rows=[]
    for c in ('fileEditControl','fileCreateControl','fileDeleteControl','fileRenameControl'):
        rows.append(assess({**common(c,'MUTATION'),'canPrevent':True,'canDetect':True,'canAttribute':True,'canHashBefore':True,'canHashAfter':True,'canBindReceipt':True,'canBlockReplay':True,'atomicityLevel':'PER_FILE'}))
    rows += [
        assess({**common('fileReadControl','OBSERVATION'),'canObserve':True,'canAttribute':True,'observationIntegrity':'HOST_ATTESTED','freshnessBound':'operation','environmentBinding':True}),
        assess({**common('browserControl','OBSERVATION'),'canObserve':True,'canAttribute':True,'observationIntegrity':'HOST_ATTESTED','freshnessBound':'operation','environmentBinding':True}),
        assess({**common('taskIdentity','IDENTITY'),'authoritativeSource':'host-session','integrityLevel':'HOST_ATTESTED','versionBinding':True,'freshnessBound':'session','sessionBinding':True}),
    ]
    p={'schemaVersion':'1.1','snapshotId':'acceptance-snapshot','hostId':'acceptance-host','hostVersion':'1','adapterId':'acceptance-adapter','adapterVersion':'1','threatModelVersion':'phase1-core-v1','channelAssessments':rows,'issuedAt':ts(),'validUntil':ts(60),'previousSnapshotDigest':None,'integrityMechanism':'HMAC_SHA256','keyId':'acceptance-key'}
    p['snapshotDigest']=digest_json(p); p['integrityTag']=sign(p['snapshotDigest']); return p

def ceiling():
    p={'schemaVersion':'1','ceilingId':'c','taskId':'task-1','allowedWriteRoots':['src/components'],'allowedOperations':['EDIT'],'allowedIntent':['repair_ui'],'forbiddenWriteRoots':['src/auth','src/payment'],'expiresAt':ts(60)}
    p['ceilingDigest']=digest_json(p); return p

def read_boundary():
    p={'schemaVersion':'1','boundaryId':'r','taskId':'task-1','allowedRoots':['src'],'deniedRoots':['src/secrets'],'sensitiveRoots':['.env']}
    p['boundaryDigest']=digest_json(p); return p

def ticket(baseline,target,ceil,snap):
    p={'schemaVersion':'2','ticketId':'t','issuer':'acceptance-host','authoritySource':'HOST_AUTHORITY','taskId':'task-1','baselineDigest':baseline,'targetDigest':target,'changeSetDigest':None,'writeDelegatedCeilingDigest':ceil,'capabilitySnapshotDigest':snap,'nonce':'0123456789abcdef','issuedAt':ts(-1),'expiresAt':ts(30),'singleUse':True,'concurrencySemantics':'SINGLE_WRITER_SERIALIZED','integrityMechanism':'HMAC_SHA256','keyId':'acceptance-key'}
    p['ticketDigest']=digest_json(p); p['integrityTag']=sign(p['ticketDigest']); return p

def receipt(td,path,before,after):
    p={'schemaVersion':'2','receiptId':'r','taskId':'task-1','authorizationTicketDigest':td,'changeSetDigest':None,'actualOperation':'EDIT','applyResult':'APPLIED','hostActor':'acceptance-host','observedAt':ts(1),'concurrencySemantics':'SINGLE_WRITER_SERIALIZED','entries':[{'entryId':'e','canonicalPath':path,'actualOperation':'EDIT','entryResult':'APPLIED','actualBeforeHash':before,'actualAfterHash':after,'reasonCode':None}],'integrityMechanism':'HMAC_SHA256','keyId':'acceptance-key'}
    p['receiptDigest']=digest_json(p); p['integrityTag']=sign(p['receiptDigest']); return p

class TicketState:
    def __init__(self): self.ref=None; self.used=False
    def reserve(self,d,n):
        if self.ref or self.used: return ''
        self.ref='reservation:'+n; return self.ref
    def consume(self,d,r):
        if self.used or r!=self.ref: return False
        self.used=True; self.ref=None; return True

def check(name,fn,checks):
    try:
        detail=fn() or 'PASS'
        checks.append({'id':name,'status':'PASS','detail':str(detail)})
    except Exception as e:
        checks.append({'id':name,'status':'FAIL','detail':f'{type(e).__name__}: {e}'})

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--compact',action='store_true'); args=ap.parse_args()
    checks=[]
    trusted=verify_capability_snapshot(snapshot(),verifier=lambda p:verify(p,'snapshotDigest'),now=NOW)

    def symlink_read():
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); (root/'src/safe').mkdir(parents=True); (root/'src/secrets').mkdir(parents=True); (root/'src/secrets/token').write_text('SECRET')
            try: (root/'src/safe/alias').symlink_to(root/'src/secrets',target_is_directory=True)
            except OSError: return 'SKIPPED_SYMLINK_UNAVAILABLE'
            try: authorize_read_path(root,read_boundary(),'src/safe/alias/token')
            except ContractViolation as e:
                if e.code=='READ_RESOLVED_TARGET_DENIED': return e.code
                raise
            raise RuntimeError('symlink sensitive-root read was authorized')
    check('P1A-001',symlink_read,checks)

    def symlink_write():
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); (root/'src/components').mkdir(parents=True); (root/'src/auth').mkdir(parents=True); (root/'src/auth/x.ts').write_text('x')
            try: (root/'src/components/alias').symlink_to(root/'src/auth',target_is_directory=True)
            except OSError: return 'SKIPPED_SYMLINK_UNAVAILABLE'
            try: authorize_write_target(root,ceiling(),relative_path='src/components/alias/x.ts',operation='EDIT',intent='repair_ui',now=NOW)
            except ContractViolation as e:
                if e.code=='WRITE_ALIAS_NOT_ALLOWED': return e.code
                raise
            raise RuntimeError('symlink write alias was authorized')
    check('P1A-002',symlink_write,checks)

    def end_to_end():
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); target=root/'src/components/Button.tsx'; target.parent.mkdir(parents=True); target.write_text('old')
            before=hash_file(target); intended='new'; after=hashlib.sha256(intended.encode()).hexdigest(); baseline=digest_json({'src/components/Button.tsx':before})
            entries=[{'canonicalPath':'src/components/Button.tsx','operation':'EDIT','expectedBeforeHash':before,'intendedAfterHash':after}]
            c=ceiling(); t=ticket(baseline,build_target_digest(entries),c['ceilingDigest'],trusted.snapshot_digest); state=TicketState()
            req=prepare_host_apply_request(root,task_id='task-1',baseline_digest=baseline,entries=entries,intent='repair_ui',write_ceiling=c,capability_snapshot=trusted,ticket_payload=t,ticket_verifier=lambda p:verify(p,'ticketDigest'),reserve_ticket=state.reserve,now=NOW)
            target.write_text(intended) # simulated external Host only
            rec=verify_host_write_receipt_v2(root,receipt(t['ticketDigest'],'src/components/Button.tsx',before,after),apply_request=req,receipt_verifier=lambda p:verify(p,'receiptDigest'),consume_ticket=state.consume)
            env='e'*64
            obs=bind_host_observation(evidence_id='ev',task_id='task-1',subtype='FILE_STATE',source_ref='host:file',observation_payload={'sha256':after},baseline_digest=baseline,environment_fingerprint=env,verifier=lambda e:True,state_epoch=1,observed_at=ts(2))
            cc={'claimId':'claim','taskId':'task-1','claimRole':'REQUIRED','statement':'approved file state','verificationContractId':'vc','baselineId':'base','environmentFingerprint':env,'requiredEvidenceTypes':['FILE_STATE'],'requiredChannels':[{'channelId':'fileEditControl','minimumLevel':'ENFORCED','purpose':'WRITE_SAFETY'}]}
            claim=evaluate_claim(cc,capability_snapshot=trusted,evidence=[obs],predicates=[True],receipts=[rec],requires_write_receipt=True,baseline_digest=baseline,minimum_state_epoch=1,evaluated_at=ts(3))
            if claim['status']!='BLOCKED' or 'LEGACY_RECEIPT_NOT_SUFFICIENT_FOR_VERIFIED' not in claim['reasonCodes']:
                raise RuntimeError(claim)
            return 'Legacy V2 receipt remains readable but cannot support a current VERIFIED claim'
    check('P1A-003',end_to_end,checks)

    def precedence():
        claims=[{'claimId':'a','taskId':'task-1','status':'VERIFIED','claimDigest':'a'*64},{'claimId':'b','taskId':'task-1','status':'NOT_VERIFIED','claimDigest':'b'*64}]
        r=aggregate_task_result(task_id='task-1',task_contract_digest='f'*64,required_claim_ids=['a','b'],optional_claim_ids=[],claims=claims,capability_snapshot_digest='c'*64,environment_fingerprint='e'*64)
        if r['status']!='NOT_VERIFIED': raise RuntimeError(r)
        return 'NOT_VERIFIED precedes PARTIAL'
    check('P1A-004',precedence,checks)

    def epoch():
        env='e'*64; baseline='b'*64
        obs=bind_host_observation(evidence_id='old',task_id='task-1',subtype='BROWSER',source_ref='host:browser',observation_payload={'ok':True},baseline_digest=baseline,environment_fingerprint=env,verifier=lambda e:True,state_epoch=4,observed_at='2099-01-01T00:00:00Z')
        cc={'claimId':'c','taskId':'task-1','claimRole':'REQUIRED','statement':'x','verificationContractId':'v','baselineId':'base','environmentFingerprint':env,'requiredEvidenceTypes':['BROWSER'],'requiredChannels':[{'channelId':'browserControl','minimumLevel':'DETECT_ONLY','purpose':'MEASUREMENT'}]}
        claim=evaluate_claim(cc,capability_snapshot=trusted,evidence=[obs],predicates=[True],baseline_digest=baseline,minimum_state_epoch=5,evaluated_at=ts())
        if claim['status']!='INVALIDATED': raise RuntimeError(claim)
        return 'stateEpoch 4 < required 5 → INVALIDATED'
    check('P1A-005',epoch,checks)

    result={'status':'PASS' if all(c['status']=='PASS' for c in checks) else 'FAIL','scope':'PHASE1_BOUNDARY_CLOSURE','packageVersion':PACKAGE_VERSION,'kernelBase':KERNEL_BASE_VERSION,'realCodexHostEnforcement':'NOT_MEASURED','checks':checks}
    print(json.dumps(result,ensure_ascii=False,separators=(',',':')) if args.compact else json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result['status']=='PASS' else 1

if __name__=='__main__': raise SystemExit(main())
