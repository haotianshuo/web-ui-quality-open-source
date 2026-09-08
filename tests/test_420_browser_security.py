from pathlib import Path
from datetime import datetime, timedelta, timezone
import json, subprocess
import os
import pytest
try:
    from playwright.sync_api import sync_playwright
except (ModuleNotFoundError, ImportError):
    sync_playwright = None
from web_ui_quality.contracts import ContractViolation
from web_ui_quality.secure_browser_context import create_secure_context, sanitize_headers_for_origin
from web_ui_quality.browser_locator import resolve_browser_executable

ROOT=Path(__file__).resolve().parents[1]
BROWSER_REQUIRED = pytest.mark.skipif(sync_playwright is None, reason="browser extra not installed; Full release gate requires it")

def bound_request(origin, method, path):
    now=datetime.now(timezone.utc)
    return {
        'origin':origin,'method':method,'path':path,'purpose':'browser-security-regression',
        'taskId':'task-browser-security','runId':'run-browser-security','sessionId':'session-browser-security',
        'issuedAt':now.isoformat(),'expiresAt':(now+timedelta(minutes=5)).isoformat(),
    }

def chromium_executable(_playwright):
    # Resolve desktop/PATH executables without touching the live sync
    # Playwright driver. Passing a sync browser type into the resolver can
    # leave pending driver tasks on stderr when the test context exits.
    decision = resolve_browser_executable("chromium")
    if not decision.get("available"):
        pytest.skip('No local Chromium executable available')
    return decision["executable"]


def node_network_decision(url, method="GET", approved=()):
    runner = ROOT / "runtime" / "python" / "web_ui_quality" / "browser_runner.cjs"
    payload = json.dumps({"url": url, "method": method, "approved": list(approved)}, ensure_ascii=False)
    script = (
        f"const r=require({json.dumps(str(runner))});"
        f"const p={payload};"
        "process.stdout.write(JSON.stringify(r.networkDecision(p.url,p.method,new Set(['https://app.test']),p.approved)));"
    )
    completed = subprocess.run(
        ["node", "-e", script], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


def test_browser_execution_sentinel_requires_a_live_browser():
    """A Full Gate Browser run must execute at least one non-skippable test."""
    if sync_playwright is None:
        pytest.fail("PLAYWRIGHT_SYNC_API_REQUIRED_FOR_FULL_BROWSER_GATE")
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, executable_path=chromium_executable(pw))
        try:
            page = browser.new_page()
            page.set_content("<button type='button'>Browser execution sentinel</button>")
            assert page.locator("button").count() == 1
            assert page.locator("button").first.is_visible()
            receipt_path = os.environ.get("WUQ_BROWSER_RECEIPT_PATH")
            if receipt_path:
                Path(receipt_path).write_text(json.dumps({
                    "schemaVersion": "1",
                    "status": "PASS",
                    "test": "tests/test_420_browser_security.py",
                    "releaseRunId": os.environ.get("WUQ_RELEASE_RUN_ID"),
                    "browser": "chromium",
                    "executable": str(chromium_executable(pw)),
                    "executed": True,
                }, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        finally:
            browser.close()

def test_node_runner_safe_default_has_no_no_sandbox_flags():
    runner=ROOT/'runtime/python/web_ui_quality/browser_runner.cjs'
    c=subprocess.run(['node','-e',f"const r=require({json.dumps(str(runner))}); process.stdout.write(JSON.stringify(r.launchSecurity({{}})))"],capture_output=True,text=True,encoding='utf-8',errors='replace')
    assert c.returncode==0,c.stderr
    payload=json.loads(c.stdout)
    assert payload['degraded'] is False
    assert not {'--no-sandbox','--disable-setuid-sandbox','--no-zygote','--single-process'} & set(payload['args'])

def test_node_runner_unsafe_launch_requires_outer_isolation():
    runner=ROOT/'runtime/python/web_ui_quality/browser_runner.cjs'
    c=subprocess.run(['node','-e',f"const r=require({json.dumps(str(runner))}); r.launchSecurity({{allowNoSandbox:true}})"],capture_output=True,text=True,encoding='utf-8',errors='replace')
    assert c.returncode!=0
    assert 'BROWSER_OS_ISOLATION_REQUIRED' in c.stderr


def test_node_query_digest_matches_python_fixed_vectors():
    runner = ROOT / "runtime" / "python" / "web_ui_quality" / "browser_runner.cjs"
    script = f"const r=require({json.dumps(str(runner))}); process.stdout.write(JSON.stringify([r.queryDigest('q=1'),r.queryDigest('q=2'),r.queryDigest('b=2&a=1')]));"
    completed = subprocess.run(
        ["node", "-e", script], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30
    )
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == [
        "02f5e6e36c0369d5dbc9195fb0cf6d5eb415a620d0b80b8bc080039186e26925",
        "cc5e3ae088faa7bf48de14a36d8914fec78d0e5cc1209b4914a99fb49b7f9e6b",
        "a746b90cddac3e075db2f0c7b65aa5d09a354bef1562352d9dab3156d1142834",
    ]


def test_node_network_policy_blocks_dangerous_gets_and_binds_query_approvals_exactly():
    assert node_network_decision("https://app.test/delete")["code"] == "SIDE_EFFECT_ROUTE_BLOCKED"
    assert node_network_decision("https://app.test/confirm")["code"] == "SIDE_EFFECT_ROUTE_BLOCKED"
    assert node_network_decision("https://evil.test/delete")["code"] == "ORIGIN_NOT_APPROVED"
    assert node_network_decision("ws://app.test/socket")["code"] == "WEBSOCKET_BLOCKED"

    q1 = "02f5e6e36c0369d5dbc9195fb0cf6d5eb415a620d0b80b8bc080039186e26925"
    q2 = "cc5e3ae088faa7bf48de14a36d8914fec78d0e5cc1209b4914a99fb49b7f9e6b"
    approved = [{"origin": "https://app.test", "method": "POST", "path": "/transfer", "queryDigest": q1}]
    assert node_network_decision("https://app.test/transfer?q=1", "POST", approved)["code"] == "EXPLICIT_SIDE_EFFECT_POLICY"
    assert node_network_decision("https://app.test/transfer?q=2", "POST", approved)["code"] == "SIDE_EFFECT_BLOCKED"
    assert node_network_decision("https://app.test/transfer?q=1", "POST", [{"origin": "https://app.test", "method": "POST", "path": "/transfer"}])["code"] == "SIDE_EFFECT_BLOCKED"
    assert node_network_decision("https://app.test/transfer?q=1", "POST", [{"origin": "https://app.test", "method": "POST", "path": "/transfer?q=1"}])["code"] == "EXPLICIT_SIDE_EFFECT_POLICY"
    assert q1 != q2

@BROWSER_REQUIRED
def test_context_wide_sensitive_headers_are_rejected():
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,executable_path=chromium_executable(pw))
        try:
            with pytest.raises(ContractViolation):
                create_secure_context(browser,context_options={'extra_http_headers':{'Authorization':'Bearer SECRET'}},allowed_origins={'http://app.test'})
        finally: browser.close()

def test_origin_credentials_are_stripped_or_injected_by_exact_origin():
    credentials={'http://app.test':{'Authorization':'Bearer SECRET','Cookie':'session=secret'}}
    out,stripped,injected=sanitize_headers_for_origin({'Authorization':'Bearer LEAK','Cookie':'bad=1','Accept':'*/*'},'http://cdn.test',credentials)
    assert 'Authorization' not in out and 'Cookie' not in out and out['Accept']=='*/*'
    assert stripped==2 and injected==0
    out,stripped,injected=sanitize_headers_for_origin({'Accept':'*/*'},'http://app.test',credentials)
    assert out['Authorization']=='Bearer SECRET' and out['Cookie']=='session=secret'
    assert injected==2

@BROWSER_REQUIRED
def test_real_chromium_secure_context_blocks_egress_side_effect_and_websocket():
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,executable_path=chromium_executable(pw))
        try:
            audit=create_secure_context(browser,context_options={'viewport':{'width':390,'height':844}},allowed_origins={'http://app.test'})
            page=audit.context.new_page()
            page.set_content("""<script>
                fetch('http://evil.test/private').catch(()=>{});
                fetch('http://app.test/mutate',{method:'POST',body:'x'}).catch(()=>{});
                try { new WebSocket('ws://app.test/socket'); } catch(e) {}
            </script>""")
            page.wait_for_timeout(350)
            report=audit.report(); decisions=report['firewallDecisions']
            assert any(x.get('code')=='ORIGIN_NOT_APPROVED' for x in decisions)
            assert any(x.get('code')=='SIDE_EFFECT_BLOCKED' for x in decisions)
            assert report['blockedWebSocketCount']>=1
            audit.context.close()
        finally: browser.close()

def test_redirect_destination_policy_fails_closed():
    from web_ui_quality.mutation_firewall import BrowserMutationFirewall
    fw=BrowserMutationFirewall({'http://app.test'})
    first=fw.evaluate(url='http://app.test/redirect',method='GET',resource_type='document')
    escaped=fw.evaluate(url='http://evil.test/landing',method='GET',resource_type='document')
    assert first.allow is True
    assert escaped.allow is False and escaped.code=='ORIGIN_NOT_APPROVED'

def test_storage_state_is_filtered_to_explicit_credential_origin():
    from web_ui_quality.secure_browser_context import sanitize_storage_state
    state={
        'cookies':[
            {'name':'session','value':'secret','domain':'app.test','path':'/','expires':-1,'httpOnly':True,'secure':False,'sameSite':'Lax'},
            {'name':'other','value':'secret2','domain':'evil.test','path':'/','expires':-1,'httpOnly':True,'secure':False,'sameSite':'Lax'},
        ],
        'origins':[
            {'origin':'http://app.test','localStorage':[{'name':'token','value':'secret'}]},
            {'origin':'http://evil.test','localStorage':[{'name':'token','value':'leak'}]},
        ],
    }
    out=sanitize_storage_state(state,credential_origins={'http://app.test'})
    assert [x['name'] for x in out['cookies']]==['session']
    assert [x['origin'] for x in out['origins']]==['http://app.test']


@BROWSER_REQUIRED
def test_real_chromium_origin_firewall_redirect_side_effect_and_credentials():
    credentials={'http://app.test':{'Authorization':'Bearer TEST_SECRET'}}
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,executable_path=chromium_executable(pw))
        try:
            audit=create_secure_context(
                browser,
                context_options={'viewport':{'width':390,'height':844}},
                allowed_origins={'http://app.test'},
                credential_headers_by_origin=credentials,
                credential_origins={'http://app.test'},
            )
            page=audit.context.new_page()
            page.set_content("""<script>
              fetch('http://app.test/echo').catch(()=>{});
              fetch('http://app.test/mutate',{method:'POST',body:'x'}).catch(()=>{});
              fetch('http://127.0.0.1:9222/leak').catch(()=>{});
              setTimeout(()=>{ location.href='http://evil.test/redirect-target'; },20);
              try { new WebSocket('ws://app.test/socket'); } catch(e) {}
            </script>""")
            page.wait_for_timeout(600)
            report=audit.report(); codes={x.get('code') for x in report['firewallDecisions']}
            assert 'SIDE_EFFECT_BLOCKED' in codes
            assert 'ORIGIN_NOT_APPROVED' in codes
            assert report['blockedWebSocketCount'] >= 1
            assert report['credentials']['injectedHeaderCount'] >= 1
            assert report['credentials']['valuesRecorded'] is False
            serialized=json.dumps(report)
            assert 'TEST_SECRET' not in serialized
            audit.context.close()
        finally: browser.close()


def test_private_loopback_unknown_protocol_and_download_service_worker_defaults_fail_closed():
    from web_ui_quality.mutation_firewall import BrowserMutationFirewall
    fw=BrowserMutationFirewall({'http://app.test'})
    private=fw.evaluate(url='http://127.0.0.1:9222/json',method='GET',resource_type='fetch')
    unknown=fw.evaluate(url='file:///etc/passwd',method='GET',resource_type='document')
    assert private.allow is False and private.code=='ORIGIN_NOT_APPROVED'
    assert unknown.allow is False and unknown.code=='UNKNOWN_PROTOCOL_BLOCKED'

    captured={}
    class FakeContext:
        def route(self,*a,**k): pass
        def route_web_socket(self,*a,**k): pass
    class FakeBrowser:
        def new_context(self,**options): captured.update(options); return FakeContext()
    audit=create_secure_context(FakeBrowser(),context_options={},allowed_origins={'http://app.test'})
    assert captured['service_workers']=='block'
    assert captured['accept_downloads'] is False
    assert audit.report()['processNetworkIsolation']=='NOT_MEASURED'

def test_custom_session_and_credential_headers_fail_closed_when_context_wide():
    class FakeContext:
        def route(self,*a,**k): pass
        def route_web_socket(self,*a,**k): pass
    class FakeBrowser:
        def new_context(self,**options): return FakeContext()
    for header in ('X-Session-Token','X-CSRF-Token','X-Company-Credential','X-Internal-Auth'):
        with pytest.raises(ContractViolation):
            create_secure_context(FakeBrowser(),context_options={'extra_http_headers':{header:'SECRET'}},allowed_origins={'http://app.test'})


def test_dangerous_get_requires_exact_machine_authorization():
    from web_ui_quality.mutation_firewall import BrowserMutationFirewall
    fw=BrowserMutationFirewall({'https://app.test'})
    blocked=fw.evaluate(url='https://app.test/confirm',method='GET',resource_type='document')
    assert blocked.allow is False and blocked.code=='SIDE_EFFECT_ROUTE_BLOCKED'
    approved=BrowserMutationFirewall(
        {'https://app.test'},
        approved_requests=(bound_request('https://app.test','GET','/confirm'),),
    ).evaluate(url='https://app.test/confirm',method='GET',resource_type='document')
    assert approved.allow is True
    other=BrowserMutationFirewall(
        {'https://app.test'},
        approved_requests=(bound_request('https://app.test','GET','/confirm'),),
    ).evaluate(url='https://app.test/buy',method='GET',resource_type='document')
    assert other.allow is False


def test_websocket_authorization_is_exact_origin_and_path():
    from web_ui_quality.mutation_firewall import BrowserMutationFirewall
    fw=BrowserMutationFirewall(
        {'wss://app.test'},
        allow_websocket=True,
        approved_requests=(bound_request('wss://app.test','WEBSOCKET','/events'),),
    )
    ok=fw.evaluate(url='wss://app.test/events',method='GET',resource_type='websocket')
    bad=fw.evaluate(url='wss://app.test/admin-events',method='GET',resource_type='websocket')
    assert ok.allow is True and ok.code=='WEBSOCKET_ALLOWED'
    assert bad.allow is False and bad.code=='WEBSOCKET_BLOCKED'


def test_unbound_or_expired_browser_request_approval_never_authorizes():
    from web_ui_quality.mutation_firewall import BrowserMutationFirewall
    unbound={'origin':'https://app.test','method':'POST','path':'/mutate'}
    expired=bound_request('https://app.test','POST','/mutate')
    expired['expiresAt']=(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()
    for row in (unbound, expired):
        fw=BrowserMutationFirewall({'https://app.test'},approved_requests=(row,))
        result=fw.evaluate(url='https://app.test/mutate',method='POST',resource_type='fetch')
        assert result.allow is False and result.code=='SIDE_EFFECT_BLOCKED'
        assert fw.rejected_approvals


def test_lighthouse_no_sandbox_requires_outer_isolation_attestation(tmp_path):
    from web_ui_quality.external_providers import run_lighthouse
    fake=tmp_path/'lighthouse'
    fake.write_text('#!/bin/sh\nexit 99\n',encoding='utf-8')
    fake.chmod(0o755)
    result=run_lighthouse('https://app.test',output_dir=tmp_path/'out',executable=fake,allow_no_sandbox=True,outer_isolation_attested=False)
    assert result['status']=='NOT_RUN'
    assert result['reason']=='BROWSER_OS_ISOLATION_REQUIRED'
    assert result['browserSecurity']=='BLOCKED'
