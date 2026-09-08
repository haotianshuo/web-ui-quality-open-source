"""WUQ 4.2.3 non-skippable public execution state contract."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

STAGES=("DISCOVER","PREFLIGHT","PLAN","HOST_APPLY","VERIFY","REPORT")
FAILURE_CLASSES=frozenset({"AUTO_RETRY","DEGRADED_CONTINUE","USER_ACTION_REQUIRED","SAFE_TERMINATION"})

@dataclass(slots=True)
class ExecutionState:
    stage: str="DISCOVER"
    history: list[dict[str,Any]]|None=None
    def __post_init__(self):
        if self.stage not in STAGES: raise ValueError("unknown stage")
        if self.history is None: self.history=[]
    def advance(self, target: str, *, status: str="PASS", input_ref: str|None=None, output_ref: str|None=None, evidence_refs: list[str]|None=None, failure_class: str|None=None) -> dict[str,Any]:
        if target not in STAGES: raise ValueError("unknown target stage")
        current=STAGES.index(self.stage); wanted=STAGES.index(target)
        if wanted != current+1: raise ValueError(f"illegal transition {self.stage}->{target}")
        if failure_class is not None and failure_class not in FAILURE_CLASSES: raise ValueError("unknown failure class")
        row={"from":self.stage,"to":target,"status":str(status),"inputRef":input_ref,"outputRef":output_ref,"evidenceRefs":list(evidence_refs or []),"failureClass":failure_class}
        self.history.append(row); self.stage=target; return row

def evidence_state(*, requested: bool, attempted: bool, executed: bool, measured: bool, verified: bool) -> dict[str,bool]:
    values=[requested,attempted,executed,measured,verified]
    if any(values[i] and not values[i-1] for i in range(1,len(values))): raise ValueError("evidence lifecycle cannot skip prerequisites")
    return dict(zip(("requested","attempted","executed","measured","verified"),values))

def browser_result_status(*, browser_executed: bool, browser_measured: bool, browser_verified: bool) -> str:
    if browser_verified and not (browser_executed and browser_measured): raise ValueError("BROWSER_PASS requires executed and measured browser evidence")
    if browser_verified: return "BROWSER_PASS"
    if browser_executed and browser_measured: return "BROWSER_NOT_VERIFIED"
    return "NOT_MEASURED"

__all__=["ExecutionState","STAGES","FAILURE_CLASSES","browser_result_status","evidence_state"]
