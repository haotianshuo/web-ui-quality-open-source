#!/usr/bin/env python3
"""Package-level public acceptance for Web UI Quality 4.3.0 with Trust Kernel 4.2.3."""
from __future__ import annotations
import json,re,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; RUNTIME=ROOT/'runtime'/'python'
if str(RUNTIME) not in sys.path: sys.path.insert(0,str(RUNTIME))
from web_ui_quality.release_info import PACKAGE_VERSION,KERNEL_VERSION,KERNEL_BASE_VERSION,PROTOCOL_VERSION,RECEIPT_PROTOCOL_VERSION,EVIDENCE_SCHEMA_VERSION
EXPECTED='4.3.0'
def row(cid,ok,detail): return {'id':cid,'status':'PASS' if ok else 'FAIL','detail':detail}
def main():
 plugin=json.loads((ROOT/'.codex-plugin/plugin.json').read_text(encoding='utf-8')); py=(ROOT/'pyproject.toml').read_text(encoding='utf-8'); quick=(ROOT/'GUIDED_REPAIR_QUICKSTART.md').read_text(encoding='utf-8'); skill=(ROOT/'skills/audit-and-fix-web-ui/SKILL.md').read_text(encoding='utf-8'); checks=[]; declared=re.search(r'(?m)^version\s*=\s*"([^"]+)"',py)
 checks.append(row('PKG-PUB-001',PACKAGE_VERSION==EXPECTED and plugin.get('version')==EXPECTED and declared and declared.group(1)==EXPECTED,{'runtime':PACKAGE_VERSION,'plugin':plugin.get('version'),'pyproject':declared.group(1) if declared else None}))
 checks.append(row('PKG-PUB-002',KERNEL_VERSION=='4.2.3' and KERNEL_BASE_VERSION=='4.0.0-rc.1',{'kernelVersion':KERNEL_VERSION,'kernelBaseVersion':KERNEL_BASE_VERSION}))
 checks.append(row('PKG-PUB-003',PROTOCOL_VERSION=='3.0' and RECEIPT_PROTOCOL_VERSION=='3.0' and EVIDENCE_SCHEMA_VERSION=='3.0',{'protocol':PROTOCOL_VERSION,'receipt':RECEIPT_PROTOCOL_VERSION,'evidence':EVIDENCE_SCHEMA_VERSION}))
 checks.append(row('PKG-PUB-004',EXPECTED in quick and EXPECTED in skill,'public docs current identity'))
 completed=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/run_runtime.py'),'--help'],cwd=ROOT,text=True,encoding='utf-8',errors='replace',capture_output=True)
 checks.append(row('PKG-PUB-005',completed.returncode==0 and '4.3.0' in completed.stdout,{'returncode':completed.returncode}))
 completed=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/public_acceptance.py')],cwd=ROOT,text=True,encoding='utf-8',errors='replace',capture_output=True)
 try: kernel=json.loads(completed.stdout)
 except Exception: kernel={}
 checks.append(row('PKG-PUB-006',completed.returncode==0 and kernel.get('status')=='PASS',{'returncode':completed.returncode,'status':kernel.get('status')}))
 outcome={'status':'PASS' if all(x['status']=='PASS' for x in checks) else 'FAIL','scope':'PACKAGE_PUBLIC_ACCEPTANCE','packageVersion':PACKAGE_VERSION,'kernelVersion':KERNEL_VERSION,'kernelBaseVersion':KERNEL_BASE_VERSION,'checks':checks,'claimBoundary':'Local package identity and public entry only; Real Codex Host qualification is NOT_MEASURED.'}; print(json.dumps(outcome,ensure_ascii=False,indent=2)); return 0 if outcome['status']=='PASS' else 1
if __name__=='__main__': raise SystemExit(main())
