#!/usr/bin/env python3
"""Build a privacy-reduced external qualification collection pack.

The HMAC key is caller supplied and is never copied into the output. This tool
creates attestation/label *requests* only; it cannot manufacture HOST_ATTESTED
provenance or independent outcome labels.
"""
from __future__ import annotations
import argparse, json, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RUNTIME=ROOT/'runtime/python'
if str(RUNTIME) not in sys.path: sys.path.insert(0,str(RUNTIME))
from web_ui_quality.phase2_collection import sanitize_shadow_observation, build_host_attestation_request, build_label_request, build_collection_manifest
from web_ui_quality.schema_validation import validate_instance

SCHEMAS=ROOT/'schemas'

def _load_json(path:Path): return json.loads(path.read_text(encoding='utf-8'))
def _write_jsonl(path:Path, rows):
    path.write_text(''.join(json.dumps(x,ensure_ascii=False,sort_keys=True)+'\n' for x in rows),encoding='utf-8')

def main()->int:
    p=argparse.ArgumentParser(description='Build privacy-reduced external qualification collection pack')
    p.add_argument('shadow_dir',type=Path,help='Directory containing *-observation.json shadow artifacts')
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--key-file',type=Path,required=True,help='Local HMAC pseudonymization key; never copied into output')
    p.add_argument('--host-id',default='UNSPECIFIED_HOST')
    p.add_argument('--host-version',default='UNKNOWN')
    p.add_argument('--label-source',choices=['EXTERNAL_ORACLE','HOST_ACCEPTANCE','HUMAN_BLIND_REVIEW'],default='HUMAN_BLIND_REVIEW')
    p.add_argument('--split',choices=['DEVELOPMENT','HOLDOUT','EXTERNAL'],default='DEVELOPMENT')
    args=p.parse_args()
    key=args.key_file.read_bytes().strip()
    if len(key)<16: raise SystemExit('key file must contain at least 16 bytes')
    observations=[]
    for path in sorted(args.shadow_dir.glob('*-observation.json')):
        value=_load_json(path)
        if value.get('mode')!='SHADOW_ONLY' or value.get('authoritative') is not False:
            raise SystemExit(f'not a non-authoritative shadow observation: {path.name}')
        observations.append(value)
    if not observations: raise SystemExit('no shadow observations found')
    now=datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
    records=[sanitize_shadow_observation(x,key) for x in observations]
    if len({x['exportRecordDigest'] for x in records}) != len(records): raise SystemExit('duplicate exported record digest')
    attest=[build_host_attestation_request(x,host_id=args.host_id,host_version=args.host_version,created_at=now) for x in records]
    labels=[build_label_request(x,requested_source=args.label_source,split=args.split,created_at=now) for x in records]
    manifest=build_collection_manifest(records,created_at=now)
    schemas={
        'record':_load_json(SCHEMAS/'qualification-export-record-v1.schema.json'),
        'att':_load_json(SCHEMAS/'host-attestation-request-v1.schema.json'),
        'label':_load_json(SCHEMAS/'independent-label-request-v1.schema.json'),
        'manifest':_load_json(SCHEMAS/'qualification-collection-manifest-v1.schema.json'),
    }
    for row in records: validate_instance(row,schemas['record'],base_dir=SCHEMAS)
    for row in attest: validate_instance(row,schemas['att'],base_dir=SCHEMAS)
    for row in labels: validate_instance(row,schemas['label'],base_dir=SCHEMAS)
    validate_instance(manifest,schemas['manifest'],base_dir=SCHEMAS)
    args.output.mkdir(parents=True,exist_ok=True)
    _write_jsonl(args.output/'shadow-export.jsonl',records)
    _write_jsonl(args.output/'host-attestation-requests.jsonl',attest)
    _write_jsonl(args.output/'independent-label-requests.jsonl',labels)
    (args.output/'collection-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    (args.output/'README.txt').write_text(
        'WUQ external qualification collection pack\n\n'
        'This pack contains pseudonymized shadow research records plus host-attestation and independent-label REQUESTS.\n'
        'It contains no pseudonymization key and does not establish HOST_ATTESTED provenance, independent labels, real-world predictive validity, or adaptive permission.\n',encoding='utf-8')
    print(json.dumps({'status':'PASS','recordCount':len(records),'output':str(args.output),'keyIncludedInPack':False,'hostAttestation':'REQUESTED_NOT_VERIFIED','labels':'REQUESTED_NOT_LABELED','realWorldPredictiveValidity':'NOT_MEASURED','adaptiveGuidance':'NOT_ACTIVE'},indent=2,sort_keys=True))
    return 0
if __name__=='__main__': raise SystemExit(main())
