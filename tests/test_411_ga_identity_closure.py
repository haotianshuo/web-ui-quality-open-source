from __future__ import annotations
import json, subprocess, sys
from pathlib import Path
from web_ui_quality.release_info import PACKAGE_VERSION,KERNEL_VERSION,KERNEL_BASE_VERSION,PROTOCOL_VERSION,RECEIPT_PROTOCOL_VERSION,EVIDENCE_SCHEMA_VERSION
ROOT=Path(__file__).resolve().parents[1]

def test_420_is_current_package_and_kernel_with_explicit_lineage():
    py=(ROOT/'pyproject.toml').read_text(encoding='utf-8')
    assert PACKAGE_VERSION=='4.3.0'
    assert KERNEL_VERSION=='4.2.3'
    assert KERNEL_BASE_VERSION=='4.0.0-rc.1'
    assert PROTOCOL_VERSION==RECEIPT_PROTOCOL_VERSION==EVIDENCE_SCHEMA_VERSION=='3.0'
    assert 'Development Status :: 5 - Production/Stable' in py
    assert 'Development Status :: 4 - Beta' not in py
    assert 'experimental-package-stage = "4.4.0-alpha.18-shadow"' in py

def test_current_user_docs_have_420_outward_identity():
    assert '4.3.0' in (ROOT/'GUIDED_REPAIR_QUICKSTART.md').read_text(encoding='utf-8')
    assert '4.3.0' in (ROOT/'COMMERCIAL_RELEASE_CHECKLIST.md').read_text(encoding='utf-8')
    assert '# Web UI Quality 4.3.0' in (ROOT/'skills/audit-and-fix-web-ui/SKILL.md').read_text(encoding='utf-8')

def test_authoritative_sources_declare_current_package_identity():
    authoritative_sources=((ROOT/'scripts/release_gate.py', PACKAGE_VERSION), (ROOT/'runtime/python/web_ui_quality/secure_browser_context.py', KERNEL_VERSION), (ROOT/'runtime/python/web_ui_quality/mutation_firewall.py', KERNEL_VERSION))
    for path, expected_identity in authoritative_sources:
        text=path.read_text(encoding='utf-8')
        assert expected_identity in text, f'{path.relative_to(ROOT)} does not declare {expected_identity}'
        assert '4.2.3-rc.1' not in text, f'{path.relative_to(ROOT)} retains rc.1 as current identity'
        assert '4.2.3-rc.2' not in text, f'{path.relative_to(ROOT)} retains rc.2 as current identity'
        assert '4.2.3-rc.3' not in text, f'{path.relative_to(ROOT)} retains rc.3 as current identity'

def test_package_and_kernel_acceptance_use_current_identity():
    payloads=[]
    for name in ('kernel_public_acceptance.py','package_public_acceptance.py'):
        p=subprocess.run([sys.executable,'-B',str(ROOT/'scripts'/name)],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace')
        assert p.returncode==0, p.stderr or p.stdout
        data=json.loads(p.stdout); assert data['status']=='PASS'; payloads.append(data)
    assert payloads[0]['version']=='4.3.0'
    assert payloads[1]['packageVersion']=='4.3.0'
    assert payloads[1]['kernelVersion']=='4.2.3'
    assert payloads[1]['kernelBaseVersion']=='4.0.0-rc.1'

def test_411_patch_status_is_history_not_420_evidence():
    assert not (ROOT/'PATCH-RELEASE-STATUS.json').exists()
    assert 'historical 4.1.1 evidence is not promoted' in (ROOT/'scripts/release.py').read_text(encoding='utf-8').lower()
