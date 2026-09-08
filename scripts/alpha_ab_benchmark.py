#!/usr/bin/env python3
"""Controlled A/B measurement for the 4.4 Shadow runtime wiring.

This is deliberately a synthetic contract benchmark.  It compares the
observable Fixed Workflow bridge from the frozen Phase-0 copy with the alpha
copy, checks that the fixed result and authority boundary are preserved, and
reports agent-quality metrics as ``NOT_MEASURED`` until a real Host study is
provided.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime" / "python"))
from web_ui_quality.release_info import EXPERIMENTAL_VERSION  # noqa: E402
DEFAULT_BASELINE = ROOT.parents[2] / "wuq-20260827-phase0" / "package" / "web-ui-quality"
DEFAULT_REPETITIONS = 3

_CASES: tuple[dict[str, Any], ...] = (
    {"id": "check-completed", "mode": "CHECK", "status": "PASS", "outcome": "COMPLETED"},
    {"id": "check-not-verified", "mode": "CHECK", "status": "NOT_VERIFIED", "outcome": "NOT_VERIFIED"},
    {"id": "fix-verified", "mode": "FIX_AND_VERIFY", "status": "VERIFIED", "outcome": "VERIFIED"},
    {"id": "fix-awaiting-host", "mode": "FIX_AND_VERIFY", "status": "AWAITING_HOST_WRITE", "outcome": "REVIEW_REQUIRED"},
    {"id": "specialized-failed", "mode": "SPECIALIZED_AUDIT", "status": "FAIL", "outcome": "COMPLETED"},
    {"id": "redesign-review", "mode": "DEEP_REDESIGN", "status": "PRODUCT_UNDERSTANDING_REVIEW_REQUIRED", "outcome": "REVIEW_REQUIRED"},
)


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def _percentile_nearest_rank(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    rank = max(1, int((percentile * len(ordered)) + 0.999999))
    return ordered[min(rank, len(ordered)) - 1]


def _summary(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    def metric(name: str) -> dict[str, float]:
        values = [float(row[name]) for row in rows]
        return {
            "median": round(_median(values), 6),
            "p95": round(_percentile_nearest_rank(values, 0.95), 6),
        }

    def sampled_metric(name: str, samples_name: str) -> dict[str, float]:
        values = [float(sample) for row in rows for sample in (row.get(samples_name) or [row[name]])]
        return {
            "median": round(_median(values), 6),
            "p95": round(_percentile_nearest_rank(values, 0.95), 6),
        }

    overhead = metric("bOverheadBytes")
    a_bytes = metric("aBytes")
    b_bytes = metric("bBytes")
    a_wall = sampled_metric("aWallTimeSeconds", "aWallTimeSamplesSeconds")
    b_wall = sampled_metric("bWallTimeSeconds", "bWallTimeSamplesSeconds")
    return {
        "sampleCount": len(rows),
        "timingSampleCount": sum(len(row.get("aWallTimeSamplesSeconds") or [row["aWallTimeSeconds"]]) for row in rows),
        "aggregation": {
            "median": "middle value (mean of two middle values for an even sample)",
            "p95": "nearest-rank percentile",
        },
        "serializedBytes": {"A": a_bytes, "B": b_bytes, "BMinusA": overhead},
        "wallTimeSeconds": {"A": a_wall, "B": b_wall},
        "protocol": {
            "caseSet": "fixed six-case synthetic scenario",
            "repetitionsPerCase": max((int(row.get("repetitions", 1)) for row in rows), default=1),
            "timingScope": "subprocess import + observation serialization",
            "agentMetrics": "NOT_MEASURED",
        },
    }


def _display_path(path: Path) -> str:
    """Keep the operator-facing path stable and readable when it is in-package."""
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def _invoke(root: Path, case: Mapping[str, Any], *, alpha: bool) -> tuple[dict[str, Any], int, float]:
    code = r'''
import json, sys
from pathlib import Path
root = Path(sys.argv[1])
case = json.loads(sys.argv[2])
sys.path.insert(0, str(root / "runtime" / "python"))
from web_ui_quality.phase1_shadow import build_shadow_observation
fixed = {"status": case["status"], "taskResult": {"status": case["status"], "subjectStatus": case["status"], "outcome": case["outcome"]}}
kwargs = {
    "run_id": "benchmark-run",
    "task_id": "benchmark-" + case["id"],
    "session_id": "benchmark-session",
    "request": "synthetic-secret-" + case["id"],
    "selected_mode": case["mode"],
    "target_kind": "project",
    "intent_route": {"intent": "inspect", "specialty": None, "writeRequested": False, "readOnlyRequired": True},
    "control_intent": {"action": "CHECK", "profile": "standard", "protectedScope": []},
    "fixed_result": fixed,
}
if sys.argv[3] == "alpha":
    kwargs["task_goal"] = {"goal": "Measure bounded workflow preservation", "successCriteria": ["fixed result remains authoritative"]}
print(json.dumps(build_shadow_observation(**kwargs), ensure_ascii=False, sort_keys=True, separators=(",", ":")))
'''
    started = time.perf_counter()
    completed = subprocess.run(
        [sys.executable, "-B", "-c", code, str(root), json.dumps(dict(case), ensure_ascii=False), "alpha" if alpha else "baseline"],
        cwd=root,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8"},
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    elapsed = time.perf_counter() - started
    if completed.returncode != 0:
        raise RuntimeError(f"{'alpha' if alpha else 'baseline'} observation failed: {completed.stderr.strip()}")
    value = json.loads(completed.stdout)
    if not isinstance(value, dict):
        raise RuntimeError("observation did not emit an object")
    return value, len(completed.stdout.encode("utf-8")), elapsed


def _authority_clean(value: Mapping[str, Any]) -> bool:
    adaptive = value.get("adaptiveControlPlane") if isinstance(value.get("adaptiveControlPlane"), Mapping) else {}
    authority = adaptive.get("authority") if isinstance(adaptive.get("authority"), Mapping) else {}
    invariants = value.get("invariants") if isinstance(value.get("invariants"), Mapping) else {}
    return (
        value.get("authoritative") is False
        and authority.get("writeAuthority") is False
        and authority.get("claimAuthority") is False
        and authority.get("mayChangeTaskResult") is False
        and invariants.get("fixedWorkflowAuthoritative") is True
        and invariants.get("mayAuthorizeWrite") is False
        and invariants.get("maySetClaimStatus") is False
        and invariants.get("mayChangeTaskResult") is False
    )


def measure(*, baseline_root: Path, output: Path | None = None, repetitions: int = DEFAULT_REPETITIONS) -> dict[str, Any]:
    baseline_root = baseline_root.expanduser().resolve()
    if not baseline_root.is_dir():
        raise RuntimeError(f"baseline package not found: {baseline_root}")
    if repetitions < 1:
        raise ValueError("repetitions must be at least 1")
    rows: list[dict[str, Any]] = []
    for case in _CASES:
        samples: list[tuple[dict[str, Any], int, float, dict[str, Any], int, float]] = []
        for _ in range(repetitions):
            baseline, a_bytes, a_seconds = _invoke(baseline_root, case, alpha=False)
            alpha, b_bytes, b_seconds = _invoke(ROOT, case, alpha=True)
            samples.append((baseline, a_bytes, a_seconds, alpha, b_bytes, b_seconds))
        baseline, a_bytes, _, alpha, b_bytes, _ = samples[0]
        token = "synthetic-secret-" + case["id"]
        baseline_observations = [sample[0] for sample in samples]
        alpha_observations = [sample[3] for sample in samples]
        rows.append({
            "caseId": case["id"],
            "fixedStatusA": baseline.get("fixedWorkflowObservation", {}).get("status"),
            "fixedStatusB": alpha.get("fixedWorkflowObservation", {}).get("status"),
            "fixedResultPreserved": all(a.get("fixedWorkflowObservation") == b.get("fixedWorkflowObservation") for a, b in zip(baseline_observations, alpha_observations)),
            "adaptiveFieldsWired": all("adaptiveControlPlane" not in a and "adaptiveControlPlane" in b for a, b in zip(baseline_observations, alpha_observations)),
            "authorityBoundaryPreserved": all(_authority_clean(value) for value in alpha_observations),
            "requestRedacted": all(token not in json.dumps(value, ensure_ascii=False) for value in alpha_observations),
            "deterministicDigest": all(value.get("observationDigest") == _invoke(ROOT, case, alpha=True)[0].get("observationDigest") for value in alpha_observations),
            "aBytes": a_bytes,
            "bBytes": b_bytes,
            "bOverheadBytes": b_bytes - a_bytes,
            "aWallTimeSamplesSeconds": [round(sample[2], 6) for sample in samples],
            "bWallTimeSamplesSeconds": [round(sample[5], 6) for sample in samples],
            "aWallTimeSeconds": round(_median([sample[2] for sample in samples]), 6),
            "bWallTimeSeconds": round(_median([sample[5] for sample in samples]), 6),
            "repetitions": repetitions,
        })
    checks = {
        "caseCount": len(rows),
        "fixedResultPreserved": all(row["fixedResultPreserved"] for row in rows),
        "adaptiveFieldsWired": all(row["adaptiveFieldsWired"] for row in rows),
        "authorityBoundaryPreserved": all(row["authorityBoundaryPreserved"] for row in rows),
        "requestRedacted": all(row["requestRedacted"] for row in rows),
        "deterministicReplay": all(row["deterministicDigest"] for row in rows),
    }
    payload: dict[str, Any] = {
        "schemaVersion": "1",
        "kind": "CONTROLLED_SHADOW_AB_BENCHMARK",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "evidenceType": "SYNTHETIC_SCENARIO",
        "baseline": {"label": "A", "packageVersion": "4.2.3"},
        "candidate": {"label": "B", "experimentalVersion": EXPERIMENTAL_VERSION},
        "checks": checks,
        "cases": rows,
        "measurementSummary": _summary(rows),
        "agentMetrics": {
            "taskCompletion": "NOT_MEASURED",
            "falseVerified": "NOT_MEASURED",
            "falseFinished": "NOT_MEASURED",
            "scopeViolation": "NOT_MEASURED",
            "unexpectedDrift": "NOT_MEASURED",
            "regressionEscape": "NOT_MEASURED",
            "wrongFix": "NOT_MEASURED",
            "humanInterventionTime": "NOT_MEASURED",
        },
        "claimBoundary": "This controlled synthetic measurement proves only that the 4.3 Shadow observer is wired, deterministic, redacts the request, preserves Fixed Workflow results, and has no write/claim authority. It does not measure model accuracy, user outcomes, or real Host performance.",
    }
    if output is not None:
        output = output.expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure 4.4 Shadow runtime wiring against the frozen package")
    parser.add_argument("--baseline-root", type=Path, default=Path(os.environ.get("WUQ_ALPHA_BASELINE_ROOT", DEFAULT_BASELINE)))
    parser.add_argument("--output", type=Path, default=ROOT / "qualification" / "phase1-ab-benchmark.json")
    parser.add_argument("--repetitions", type=int, default=DEFAULT_REPETITIONS, help=f"repeat each synthetic case (default: {DEFAULT_REPETITIONS})")
    parser.add_argument("--compact", action="store_true", help="emit a one-line operator summary while keeping the full JSON artifact")
    args = parser.parse_args()
    result = measure(baseline_root=args.baseline_root, output=args.output, repetitions=args.repetitions)
    if args.compact:
        summary = result.get("measurementSummary", {})
        overhead = (summary.get("serializedBytes") or {}).get("BMinusA") or {}
        print(json.dumps({
            "status": result.get("status"),
            "caseCount": (result.get("checks") or {}).get("caseCount"),
            "fixedResultPreserved": (result.get("checks") or {}).get("fixedResultPreserved"),
            "authorityBoundaryPreserved": (result.get("checks") or {}).get("authorityBoundaryPreserved"),
            "deterministicReplay": (result.get("checks") or {}).get("deterministicReplay"),
            "serializedBytesOverhead": overhead,
            "agentMetrics": "NOT_MEASURED",
            "artifact": _display_path(args.output),
        }, ensure_ascii=False, sort_keys=True))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
