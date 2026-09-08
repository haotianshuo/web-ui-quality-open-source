"""Deterministic Phase-1 no-progress and resource stop controller."""
from __future__ import annotations

from dataclasses import dataclass
from typing import FrozenSet


@dataclass(frozen=True, slots=True)
class DeadlockState:
    no_progress_rounds: int = 0
    same_blocked_action_count: int = 0
    tool_failure_count: int = 0
    repeated_invalid_operation_count: int = 0
    last_blocked_action: str | None = None
    deadlock_detected: bool = False


def observe_round(
    state: DeadlockState,
    *,
    obligations_before: FrozenSet[str],
    obligations_after: FrozenSet[str],
    authoritative_progress_event: bool = False,
    blocked_action: str | None = None,
    tool_failed: bool = False,
    invalid_operation: bool = False,
    max_no_progress_rounds: int = 2,
    max_same_blocked_action: int = 3,
) -> DeadlockState:
    obligation_reduction = obligations_after < obligations_before
    progressed = obligation_reduction or authoritative_progress_event
    no_progress = 0 if progressed else state.no_progress_rounds + 1
    same_blocked = (
        state.same_blocked_action_count + 1
        if blocked_action and blocked_action == state.last_blocked_action
        else 1 if blocked_action else 0
    )
    detected = no_progress >= max_no_progress_rounds or same_blocked >= max_same_blocked_action
    return DeadlockState(
        no_progress_rounds=no_progress,
        same_blocked_action_count=same_blocked,
        tool_failure_count=state.tool_failure_count + int(tool_failed),
        repeated_invalid_operation_count=state.repeated_invalid_operation_count + int(invalid_operation),
        last_blocked_action=blocked_action,
        deadlock_detected=detected,
    )


def resource_stop(
    *,
    accepted_progress: bool,
    hard_token_limit_reached: bool = False,
    hard_cost_limit_reached: bool = False,
    hard_timeout_reached: bool = False,
    tool_unavailable: bool = False,
    telemetry_authoritative: bool = True,
) -> tuple[str, str]:
    if tool_unavailable:
        return "TOOL_UNAVAILABLE", "SUFFICIENT"
    if not telemetry_authoritative and (hard_token_limit_reached or hard_cost_limit_reached or hard_timeout_reached):
        return "NONE", "UNKNOWN"
    if hard_timeout_reached:
        return "TIMEOUT", "SUFFICIENT"
    if hard_cost_limit_reached:
        return "COST_LIMIT_REACHED", "MORE_RESOURCE_REQUIRED" if accepted_progress else "EXHAUSTED"
    if hard_token_limit_reached:
        return "TOKEN_LIMIT_REACHED", "MORE_RESOURCE_REQUIRED" if accepted_progress else "EXHAUSTED"
    return "NONE", "SUFFICIENT"


__all__ = ["DeadlockState", "observe_round", "resource_stop"]
