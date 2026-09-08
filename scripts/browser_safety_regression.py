#!/usr/bin/env python3
from __future__ import annotations
import json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"runtime"/"python"))

from web_ui_quality.attempts import AttemptLimiter, issue_fingerprint
from web_ui_quality.condition_registry import STANDARD_VIEWPORTS
from web_ui_quality.comparison_gate import evaluate_improvement_claim
from web_ui_quality.contracts import ContractViolation, digest_json
from web_ui_quality.mutation_firewall import BrowserMutationFirewall
from web_ui_quality.page_health import evaluate_page_health
from web_ui_quality.quick_ui import summarize_top_ui_issues
from web_ui_quality.readiness import assess_readiness
from web_ui_quality.reversible_probe import run_reversible_probe
from web_ui_quality.resource_integrity import classify_resource_events


def main()->int:
    from web_ui_quality.release_info import configure_stdout

    configure_stdout()
    checks=[]
    fw=BrowserMutationFirewall({"https://app.example"})
    checks.append(("same-origin-get",fw.evaluate(url="https://app.example/data",method="GET",resource_type="fetch").allow))
    checks.append(("same-origin-post-blocked",not fw.evaluate(url="https://app.example/save",method="POST",resource_type="fetch").allow and fw.mutation_attempted))
    checks.append(("external-get-blocked",not fw.evaluate(url="https://cdn.example/app.js",method="GET",resource_type="script").allow))

    telemetry=classify_resource_events([{"url":"https://www.google-analytics.com/g/collect","resourceType":"fetch"}],page_origin="https://app.example")
    core=classify_resource_events([{"url":"https://app.example/app.js","resourceType":"script"}],page_origin="https://app.example")
    checks.append(("telemetry-warning",telemetry["status"]=="PASS_WITH_WARNINGS"))
    checks.append(("core-resource-blocker",core["status"]=="BLOCKED"))

    health=evaluate_page_health(readiness={"status":"READY"},resource_integrity={"status":"PASS"},runtime_errors=["TypeError"],visual_findings=10,browser_executed=True)
    checks.append(("runtime-over-visual",health["pageStatus"]=="RUNTIME_BROKEN"))
    auth=evaluate_page_health(readiness={"status":"AUTH_REQUIRED"},resource_integrity={"status":"PASS"},auth_required=True,visual_findings=5,browser_executed=True)
    checks.append(("auth-over-visual",auth["pageStatus"]=="AUTH_REQUIRED"))
    data=assess_readiness({"readyState":"complete","textLength":200,"mainPresent":True,"skeletonCount":2},http_status=200)
    checks.append(("skeleton-data-not-ready",data["status"]=="DATA_NOT_READY"))


    partial=evaluate_page_health(readiness={"status":"PARTIAL"},resource_integrity={"status":"PASS"},task_status="PASS_RESTORED",visual_findings=0,browser_executed=True)
    timeout=evaluate_page_health(readiness={"status":"TIMEOUT"},resource_integrity={"status":"PASS"},task_status="PASS_RESTORED",visual_findings=0,browser_executed=True)
    checks.append(("partial-not-pass",partial["pageStatus"]=="NOT_VERIFIED"))
    checks.append(("timeout-not-pass",timeout["pageStatus"]=="NOT_VERIFIED"))

    base_report={"pageHealth":{"pageStatus":"TASK_FAILED"},"journey":{"journeyId":"primary-journey","status":"FAIL","journey":[{"id":"submit"}],"runs":[{"status":"FAIL"}]},"findings":[{"id":"F1","severity":"P1"}]}
    improved_report={"pageHealth":{"pageStatus":"REAL_PAGE_READY"},"journey":{"journeyId":"primary-journey","status":"PASS","journey":[{"id":"submit"}],"runs":[{"status":"PASS"}]},"findings":[]}
    same_report={"pageHealth":{"pageStatus":"REAL_PAGE_READY"},"journey":{"journeyId":"primary-journey","status":"PASS","journey":[{"id":"submit"}],"runs":[{"status":"PASS"}]},"findings":[]}
    improved=evaluate_improvement_claim(base_report,improved_report,condition_match=True,target_match=True,safe_task_match=True)
    unchanged=evaluate_improvement_claim(same_report,same_report,condition_match=True,target_match=True,safe_task_match=True)
    mismatched=evaluate_improvement_claim(base_report,improved_report,condition_match=False,target_match=True,safe_task_match=True)
    regressed=evaluate_improvement_claim(improved_report,base_report,condition_match=True,target_match=True,safe_task_match=True)
    checks.append(("improvement-gate-requires-better-outcome",improved["status"]=="IMPROVEMENT_CLAIM_ALLOWED" and improved["improvementClaimAllowed"] is True))
    checks.append(("unchanged-not-improvement",unchanged["status"]=="COMPARABLE_NO_PROVEN_IMPROVEMENT" and unchanged["improvementClaimAllowed"] is False))
    checks.append(("condition-mismatch-inconclusive",mismatched["status"]=="INCONCLUSIVE"))
    checks.append(("regression-detected",regressed["status"]=="REGRESSED"))

    records=[
      {"status":"PASS_WITH_WARNINGS","viewport":{"width":390,"height":844},"pageHealth":{"pageStatus":"RUNTIME_BROKEN"},"renderedQuality":{"findings":[{"id":"COLOR","severity":"P3","title":"颜色不一致","samples":[{}]}]}},
      {"status":"PASS_WITH_WARNINGS","viewport":{"width":768,"height":1024},"pageHealth":{"pageStatus":"AUTH_REQUIRED"},"renderedQuality":{"findings":[{"id":"FONT","severity":"P3","title":"小字号","samples":[{}]}]}},
    ]
    top=summarize_top_ui_issues(records,limit=3)
    checks.append(("top3-health-first",[x["id"] for x in top[:2]]==["PAGE-RUNTIME-BROKEN","PAGE-AUTH-REQUIRED"]))
    checks.append(("authoritative-viewports",STANDARD_VIEWPORTS==((390,844),(768,1024),(1440,900))))

    limiter=AttemptLimiter(); key=issue_fingerprint("browser","playwright","target","provider_call","blocked")
    for kind in ("root_cause_minimal_fix","alternative_path","fallback"):
        permit=limiter.begin(key,kind,kind)
        limiter.record_failure(permit,feature_id="browser",provider_id="playwright",target="target",root_cause="blocked",evidence_digest="a"*64,result="NOT_VERIFIED",remaining_risk="R2")
    try:
        limiter.begin(key,"fallback","fourth")
        fourth=False
    except ContractViolation as e:
        fourth=e.code=="ATTEMPT_LIMIT_REACHED"
    checks.append(("three-attempt-hard-stop",fourth and len(limiter.records(key))==3))


    class _Locator:
        def __init__(self, page): self.page=page
        @property
        def first(self): return self
        def click(self, timeout=0): self.page.opened=not self.page.opened
    class _Page:
        def __init__(self): self.opened=False; self.locator_obj=_Locator(self); self.selecting=True
        def evaluate(self, script):
            if "const summary" in script:
                return {"kind":"details","selector":"details:not([open]) > summary"}
            if "openDetails" in script:
                return {"url":"https://app.example","openDetails":[[0,self.opened]],"expanded":[],"selectedTabs":[],"bodyText":"demo"}
            return None
        def locator(self, selector): return self.locator_obj
        def wait_for_timeout(self, ms): return None
    reversible=run_reversible_probe(_Page(), BrowserMutationFirewall({"https://app.example"}))
    checks.append(("reversible-probe-restored",reversible["status"]=="PASS_RESTORED" and reversible["restored"] is True))

    success_limiter=AttemptLimiter(); success_key=issue_fingerprint("browser","playwright","target-ok","provider_call","temporary")
    success_limiter.invoke(feature_id="browser",provider_id="playwright",target="target-ok",root_cause="temporary",strategy_kind="root_cause_minimal_fix",strategy_detail="retry after readiness fix",provider_call=lambda: "ok",evidence_digest="b"*64,remaining_risk="R0")
    checks.append(("successful-attempt-recorded",success_limiter.records(success_key)[0]["result"]=="PASS"))

    failed=[n for n,o in checks if not o]
    result={"status":"PASS" if not failed else "FAIL","scope":"BROWSER_SAFETY_REGRESSION","checks":[{"id":n,"status":"PASS" if o else "FAIL"} for n,o in checks]}
    print(json.dumps(result,ensure_ascii=False,indent=2)); return 1 if failed else 0
if __name__=="__main__": raise SystemExit(main())
