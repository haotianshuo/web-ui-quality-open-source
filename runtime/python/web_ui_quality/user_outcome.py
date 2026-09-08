"""Simple user-facing three-state rendering over exact internal machine status."""
from __future__ import annotations
from typing import Any, Mapping

def user_outcome(result: Mapping[str,Any]) -> dict[str,Any]:
    status=str(result.get("outcome") or result.get("status") or "NOT_VERIFIED").upper()
    blockers=list(result.get("blockers") or [])
    risks=list(result.get("uncertainties") or result.get("risks") or [])
    if status in {"VERIFIED","BROWSER_PASS"}: label="已完成并验证"
    elif blockers or status in {"BLOCKED","USER_ACTION_REQUIRED","AUTH_REQUIRED","SCOPE_NOT_CONFIRMED"}: label="需要你处理"
    else: label="已完成但部分未验证"
    return {"result":label,"changed":list(result.get("changes") or []),"verified":dict(result.get("verification") or {}),"risks":risks or blockers,"machineStatus":status,"auditDetailsAvailable":True}

__all__=["user_outcome"]
