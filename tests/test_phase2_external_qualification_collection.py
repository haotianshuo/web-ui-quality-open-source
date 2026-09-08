from pathlib import Path
import json
import pytest
ROOT=Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0,str(ROOT/'runtime/python'))
from web_ui_quality.phase1_shadow import build_shadow_observation
from web_ui_quality.phase2_collection import *
from web_ui_quality.schema_validation import validate_instance

def _obs():
    return build_shadow_observation(run_id='r-private',task_id='t-private',session_id='s-private',request='raw private prompt',selected_mode='FIX_AND_VERIFY',target_kind='url',intent_route={'intent':'REPAIR_SMALL','specialty':None,'writeRequested':True,'readOnlyRequired':False},control_intent={'action':'FIX','profile':'standard','protectedScope':[]},fixed_result={'status':'NOT_VERIFIED','taskResult':{'status':'NOT_VERIFIED'}})

def test_pseudonymized_export_removes_raw_binding_and_request_digest():
    o=_obs(); r=sanitize_shadow_observation(o,b'x'*32); blob=json.dumps(r)
    assert 'r-private' not in blob and 't-private' not in blob and 's-private' not in blob
    assert 'raw private prompt' not in blob and o['requestDigest'] not in blob
    assert r['requestToken'].startswith('r_')

def test_pseudonymization_is_stable_and_key_scoped():
    o=_obs(); a=sanitize_shadow_observation(o,b'a'*32); b=sanitize_shadow_observation(o,b'a'*32); c=sanitize_shadow_observation(o,b'b'*32)
    assert a['taskBinding']==b['taskBinding']
    assert a['taskBinding']!=c['taskBinding']

def test_empty_key_rejected():
    with pytest.raises(ValueError): sanitize_shadow_observation(_obs(),b'')

def test_attestation_request_cannot_claim_verified():
    r=sanitize_shadow_observation(_obs(),b'x'*32); a=build_host_attestation_request(r,host_id='h',host_version='1',created_at='now')
    assert a['verificationStatus']=='REQUESTED_NOT_VERIFIED' and a['attestationEvidenceDigest'] is None

def test_label_request_cannot_claim_outcome():
    r=sanitize_shadow_observation(_obs(),b'x'*32); l=build_label_request(r,requested_source='HUMAN_BLIND_REVIEW',split='DEVELOPMENT',created_at='now')
    assert l['outcome'] is None and l['independence']=='UNASSESSED'

def test_unknown_label_source_rejected():
    r=sanitize_shadow_observation(_obs(),b'x'*32)
    with pytest.raises(ValueError): build_label_request(r,requested_source='FIXED_WORKFLOW_PROXY',split='DEVELOPMENT',created_at='now')

def test_collection_manifest_never_promotes_validity_or_adaptive():
    r=sanitize_shadow_observation(_obs(),b'x'*32); m=build_collection_manifest([r],created_at='now')
    assert m['realWorldPredictiveValidity']=='NOT_MEASURED'; assert m['adaptiveGuidance']=='NOT_ACTIVE'; assert m['keyIncludedInPack'] is False

def test_duplicate_export_digest_rejected():
    r=sanitize_shadow_observation(_obs(),b'x'*32)
    with pytest.raises(ValueError): build_collection_manifest([r,r],created_at='now')

def test_collection_schemas_validate():
    base=ROOT/'schemas'; r=sanitize_shadow_observation(_obs(),b'x'*32); a=build_host_attestation_request(r,host_id='h',host_version='1',created_at='now'); l=build_label_request(r,requested_source='EXTERNAL_ORACLE',split='EXTERNAL',created_at='now'); m=build_collection_manifest([r],created_at='now')
    for name,val in [('qualification-export-record-v1.schema.json',r),('host-attestation-request-v1.schema.json',a),('independent-label-request-v1.schema.json',l),('qualification-collection-manifest-v1.schema.json',m)]:
        validate_instance(val,json.loads((base/name).read_text()),base_dir=base)
