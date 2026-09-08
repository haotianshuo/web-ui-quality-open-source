#!/usr/bin/env python3
"""Dependency-light v2.3 P0 acceptance shipped with the distribution."""
from __future__ import annotations
import json, sys, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'runtime/python'))
from web_ui_quality.acceptance_findings import normalize_findings
from web_ui_quality.business_context import build_context_v2, mark_stale
from web_ui_quality.journey import JourneyPolicy, execute_journey, validate_journey
from web_ui_quality.schema_validation import check_schema_bundle, validate_instance
from web_ui_quality.smart_acceptance import run_smart_acceptance
from web_ui_quality.source_assurance import command_safety_plan, run_source_assurance

class Locator:
    def __init__(self,p): self.p=p
    def nth(self,n): return self
    def click(self,timeout=0):
        if self.p.change_on_click:self.p.changed=True
    def get_attribute(self,n,timeout=0): return 'true' if self.p.changed else 'false'
    def is_visible(self,timeout=0): return True
    def inner_text(self,timeout=0): return 'changed' if self.p.changed else 'before'
    def input_value(self,timeout=0): return ''
    def is_checked(self,timeout=0): return False
    def count(self): return 1
    def dblclick(self,timeout=0): self.click(timeout)
    def fill(self,v,timeout=0): self.click(timeout)
    def press(self,k,timeout=0): self.click(timeout)
    def select_option(self,v,timeout=0): self.click(timeout)
    def check(self,timeout=0): self.click(timeout)
    def uncheck(self,timeout=0): self.click(timeout)
    def wait_for(self,state='visible',timeout=0): pass
    def scroll_into_view_if_needed(self,timeout=0): pass
    def hover(self,timeout=0): pass
    def focus(self,timeout=0): pass
class Page:
    def __init__(self,change=True): self.change_on_click=change;self.changed=False;self.url='https://example.test/';self.listeners={}
    def on(self,e,c): self.listeners.setdefault(e,[]).append(c)
    def remove_listener(self,e,c):
        if c in self.listeners.get(e,[]):self.listeners[e].remove(c)
    def evaluate(self,s,arg=None): return {'url':self.url,'title':'Fixture','text':'changed' if self.changed else 'before','controls':[{'selected':self.changed}],'active':''}
    def locator(self,x): return Locator(self)
    def get_by_role(self,*a,**k): return Locator(self)
    def get_by_label(self,*a,**k): return Locator(self)
    def get_by_placeholder(self,*a,**k): return Locator(self)
    def get_by_test_id(self,*a,**k): return Locator(self)
    def get_by_text(self,*a,**k): return Locator(self)
    def wait_for_timeout(self,x): pass
    def screenshot(self,path,**k): Path(path).write_bytes(b'png')
    def goto(self,url,**k): self.url=url
    def go_back(self,**k): pass
    def reload(self,**k): pass

def require(condition,message):
    if not condition: raise RuntimeError(message)

def main():
    from web_ui_quality.release_info import configure_stdout

    configure_stdout()
    checks=[]
    health=check_schema_bundle(ROOT/'schemas');require(health['status']=='PASS',str(health));checks.append('schema bundle')
    first=build_context_v2({'primaryRole':'运营','primaryTask':'筛选订单'});second=build_context_v2({'primaryRole':'运营','primaryTask':'审批订单'},parent_version=first['contextVersion'],reason='user_correction')
    require(mark_stale({'contextVersion':first['contextVersion'],'status':'PASS'},current_context_version=second['contextVersion'])['status']=='STALE','context invalidation');checks.append('context identity and invalidation')
    raw=[{'id':'toggle','action':'click','risk':'ui-state','role':'button','name':'展开','outcome':{'signals':[{'kind':'state_changed','evidenceRole':'user_visible'}]}}]
    steps=validate_journey(raw,JourneyPolicy(allowed_risks=frozenset({'read-only','ui-state'})))
    with tempfile.TemporaryDirectory() as d:
        require(execute_journey(Page(True),steps,output_dir=d)[0]['status']=='PASS','outcome pass')
        require(execute_journey(Page(False),steps,output_dir=d)[0]['status']=='FAIL','outcome fail')
    checks.append('Outcome Proof pass/fail')
    bad=normalize_findings([{'targetIdentity':'x','routeTemplate':'/','issueType':'NO_RESPONSE','semanticTarget':'b','state':'default','viewportClass':'mobile','expectedOutcomeKey':'changed','observedOutcomeKey':'unchanged','evidenceKinds':['interaction'],'evidenceRefs':[],'ruleId':'R','verificationState':'NOT_VERIFIED','resultLabel':'现在会出错','severity':'high','summary':'坏了','impact':'不能用','recommendation':'修复'}],context_version=first['contextVersion'])
    require(not bad['findings'] and bad['normalizationErrors'],'unverified bug label accepted');checks.append('finding evidence qualification')
    with tempfile.TemporaryDirectory() as d:
        project=Path(d)/'project';project.mkdir();(project/'a.py').write_text('x=1\n');(project/'package.json').write_text(json.dumps({'scripts':{'test':'pytest','deploy':'npm publish'}}))
        source=run_source_assurance(project,output_dir=Path(d)/'source',files=['a.py']);require(source['status']=='VERIFIED_WITH_WARNINGS','source assurance')
        classes={x['id']:x['classification'] for x in command_safety_plan(project)['commands']};require(classes['npm:test']=='SAFE_BOUNDED' and classes['npm:deploy']=='BLOCKED','command safety')
        acceptance=run_smart_acceptance(project,output_dir=Path(d)/'acceptance');require(acceptance['status']=='NOT_VERIFIED','project-only honesty')
        schema=json.loads((ROOT/'schemas/smart-acceptance-report.schema.json').read_text());validate_instance(acceptance,schema,base_dir=ROOT/'schemas')
    checks.append('source safety and project-only honesty')
    print(json.dumps({'status':'PASS','scope':'V2_3_P0_ACCEPTANCE','checks':checks},ensure_ascii=False,indent=2))
    return 0
if __name__=='__main__': raise SystemExit(main())
