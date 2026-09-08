#!/usr/bin/env python3
"""External Host-Agent benchmark controller, immutable ingest and scorer."""
from __future__ import annotations

import argparse
import hmac
import json
import math
import statistics
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime" / "python"
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from web_ui_quality.benchmark_protocol import (  # noqa: E402
    condition_fingerprint, contained_path, immutable_write_json, integrity_mac, merkleish_root,
    verify_mac_sealed, verify_sealed,
)
from web_ui_quality.contracts import ContractViolation  # noqa: E402
from web_ui_quality.schema_validation import validate_instance  # noqa: E402
from fault_injection_harness import prepare_all, score_host_observation  # noqa: E402

HOST_SCHEMA = ROOT / "schemas" / "agent-benchmark-result.schema.json"
REPORT_SCHEMA = ROOT / "schemas" / "agent-benchmark-report.schema.json"


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _save(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _controller(controller: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    controller = controller.resolve()
    key_path = controller / ".benchmark-integrity.key"
    if not key_path.is_file() or key_path.is_symlink():
        raise ContractViolation("BENCHMARK_INTEGRITY_KEY_MISSING", ["controller integrity key is missing"])
    integrity_key = key_path.read_bytes()
    plan = _load(controller / "benchmark-plan.json")
    verify_mac_sealed(plan, key=integrity_key, digest_field="planDigest", mac_field="planMac", digest_code="BENCHMARK_PLAN_TAMPERED", mac_code="BENCHMARK_PLAN_AUTH_FAILED")
    state = _load(controller / "benchmark-controller-state.json")
    verify_mac_sealed(state, key=integrity_key, digest_field="stateDigest", mac_field="stateMac", digest_code="BENCHMARK_CONTROLLER_TAMPERED", mac_code="BENCHMARK_CONTROLLER_AUTH_FAILED")
    if Path(state["controllerRoot"]).resolve() != controller:
        raise ContractViolation("BENCHMARK_CONTROLLER_MISMATCH", ["controllerRoot does not match current controller"])
    manifests = {str(k): str(v) for k, v in dict(state.get("manifestDigests") or {}).items()}
    if merkleish_root(manifests) != state.get("groundTruthRootDigest"):
        raise ContractViolation("BENCHMARK_GROUND_TRUTH_ROOT_TAMPERED", ["ground truth digest root mismatch"])
    return plan, state


def validate_host_result(value: Mapping[str, Any]) -> None:
    schema = _load(HOST_SCHEMA)
    validate_instance(dict(value), schema, base_dir=HOST_SCHEMA.parent)


def ingest(controller_dir: Path, result_path: Path) -> dict[str, Any]:
    controller = controller_dir.resolve()
    plan, _ = _controller(controller)
    value = _load(result_path)
    validate_host_result(value)
    run_id = str(value["runId"])
    planned = next((row for row in plan["runs"] if row["runId"] == run_id), None)
    if planned is None:
        raise ContractViolation("BENCHMARK_RUN_UNKNOWN", [f"unknown runId: {run_id}"])
    for field in ("caseId", "repetition"):
        if value[field] != planned[field]:
            raise ContractViolation("BENCHMARK_RESULT_PLAN_MISMATCH", [f"{field} does not match sealed plan for {run_id}"])
    if str(value.get("conditionDigest") or "") != str(planned.get("conditionDigest") or ""):
        raise ContractViolation("BENCHMARK_CONDITION_MISMATCH", [f"conditionDigest does not match Controller plan for {run_id}"])
    if dict(value.get("host") or {}) != dict(planned.get("plannedHost") or {}):
        raise ContractViolation("BENCHMARK_CONDITION_MISMATCH", [f"host identity does not match Controller plan for {run_id}"])
    if dict(value.get("conditions") or {}) != dict(planned.get("plannedConditions") or {}):
        raise ContractViolation("BENCHMARK_CONDITION_MISMATCH", [f"conditions do not match Controller plan for {run_id}"])
    destination = contained_path(controller / "results", f"{run_id}.json", code="BENCHMARK_RESULT_PATH_ESCAPE")
    immutable_write_json(destination, value)
    return {"status": "RECORDED", "runId": run_id, "resultPath": str(destination), "immutable": True}


def _wilson_interval(successes: int, n: int, z: float = 1.959963984540054) -> dict[str, float] | None:
    if n <= 0:
        return None
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    radius = z * math.sqrt((p * (1 - p) / n) + (z * z / (4 * n * n))) / denom
    return {"lower": max(0.0, centre - radius), "upper": min(1.0, centre + radius)}


def _mean(values: list[float]) -> float | None:
    return statistics.fmean(values) if values else None


def _stdev(values: list[float]) -> float | None:
    return statistics.stdev(values) if len(values) >= 2 else None


def _metric(rows: list[Mapping[str, Any]], key: str) -> dict[str, Any]:
    values: list[float] = []
    for row in rows:
        value = dict(row.get("metrics") or {}).get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            values.append(float(value))
    return {"measuredRuns": len(values), "mean": _mean(values), "sampleStdDev": _stdev(values), "min": min(values) if values else None, "max": max(values) if values else None}


def _micro_root_metric(scored: list[Mapping[str, Any]]) -> dict[str, Any]:
    tp = sum(int(row.get("rootCauseTP") or 0) for row in scored)
    fp = sum(int(row.get("rootCauseFP") or 0) for row in scored)
    fn = sum(int(row.get("rootCauseFN") or 0) for row in scored)
    return {
        "truePositive": tp, "falsePositive": fp, "falseNegative": fn,
        "precision": tp / (tp + fp) if (tp + fp) else None,
        "recall": tp / (tp + fn) if (tp + fn) else None,
        "claimBoundary": "Precision penalizes extra claimed root files; Recall penalizes missed expected root files. Runs with no applicable root truth contribute no TP/FP/FN unless the Host claims a root.",
    }


def aggregate(controller_dir: Path) -> dict[str, Any]:
    controller = controller_dir.resolve()
    plan, state = _controller(controller)
    evaluator_root = Path(str(state["evaluatorRoot"])).resolve()
    scored: list[dict[str, Any]] = []
    host_results: list[dict[str, Any]] = []
    missing: list[str] = []
    condition_cohorts: dict[str, dict[str, Any]] = {}
    for run in plan["runs"]:
        run_id = str(run["runId"])
        result_path = contained_path(controller / "results", f"{run_id}.json", code="BENCHMARK_RESULT_PATH_ESCAPE")
        if not result_path.is_file():
            missing.append(run_id)
            continue
        host = _load(result_path)
        validate_host_result(host)
        if host["caseId"] != run["caseId"] or host["repetition"] != run["repetition"]:
            raise ContractViolation("BENCHMARK_RESULT_PLAN_MISMATCH", [f"stored result mismatches plan: {run_id}"])
        if str(host.get("conditionDigest") or "") != str(run.get("conditionDigest") or "") or dict(host.get("host") or {}) != dict(run.get("plannedHost") or {}) or dict(host.get("conditions") or {}) != dict(run.get("plannedConditions") or {}):
            raise ContractViolation("BENCHMARK_CONDITION_MISMATCH", [f"stored result conditions do not match Controller plan: {run_id}"])
        fp = condition_fingerprint(dict(run.get("plannedHost") or {}), dict(run.get("plannedConditions") or {}))
        if fp["digest"] != run.get("conditionDigest"):
            raise ContractViolation("BENCHMARK_PLAN_TAMPERED", [f"planned condition digest mismatch for {run_id}"])
        condition_cohorts.setdefault(fp["digest"], {"digest": fp["digest"], "host": fp["host"], "conditions": fp["conditions"], "runs": 0, "authority": "CONTROLLER_PLANNED"})["runs"] += 1
        host_results.append(host)
        evaluator_path = evaluator_root / f"{run_id}.json"
        evaluator = _load(evaluator_path)
        expected_digest = str(dict(state.get("manifestDigests") or {}).get(run_id) or "")
        actual_digest = verify_sealed(evaluator, field="manifestDigest", code="BENCHMARK_GROUND_TRUTH_TAMPERED")
        if expected_digest != actual_digest:
            raise ContractViolation("BENCHMARK_GROUND_TRUTH_TAMPERED", [f"manifest digest mismatch for {run_id}"])
        integrity_key = (controller / ".benchmark-integrity.key").read_bytes()
        expected_mac = str(dict(state.get("manifestMacs") or {}).get(run_id) or "")
        if not expected_mac or not hmac.compare_digest(expected_mac, integrity_mac(evaluator, integrity_key)):
            raise ContractViolation("BENCHMARK_GROUND_TRUTH_AUTH_FAILED", [f"manifest HMAC mismatch for {run_id}"])
        scored.append(score_host_observation(evaluator, Path(run["projectPath"]), host["observation"]))

    by_case: dict[str, list[dict[str, Any]]] = {}
    for row in scored:
        by_case.setdefault(str(row["caseId"]), []).append(row)
    for rows in by_case.values():
        rows.sort(key=lambda item: int(item["repetition"]))
    repetitions = int(plan.get("repetitionsPerCase") or 1)
    pass_at: dict[str, float | None] = {}
    for k in sorted({1, min(3, repetitions), repetitions}):
        eligible = [rows for rows in by_case.values() if len(rows) >= k]
        pass_at[f"pass@{k}"] = (sum(1 for rows in eligible if any(bool(item["repairSuccess"]) for item in rows[:k])) / len(eligible)) if eligible else None

    completed = len(scored)
    successes = sum(1 for row in scored if row["repairSuccess"])
    verified = sum(1 for row in scored if row["hostOutcome"] == "VERIFIED")
    attempted = sum(1 for row in scored if row["repairAttempted"])
    false_verified = sum(1 for row in scored if row["falseVerified"])
    regressions = sum(1 for row in scored if row["regressionEscape"])
    scope_values = [float(row["scopePrecision"]) for row in scored if isinstance(row.get("scopePrecision"), (int, float))]
    false_rate = false_verified / verified if verified else None
    rule_three = min(1.0, 3 / verified) if verified and false_verified == 0 else None

    if completed == 0:
        status = "NOT_VERIFIED_HOST_AUTOMATION"
    elif missing:
        status = "MEASURED_PARTIAL"
    elif len(condition_cohorts) != 1:
        status = "MEASURED_MIXED_CONDITIONS"
    else:
        status = "MEASURED_QUALIFICATION"

    difficulty: dict[str, dict[str, Any]] = {}
    for level in sorted({str(row["difficulty"]) for row in scored}):
        rows = [row for row in scored if row["difficulty"] == level]
        difficulty[level] = {"runs": len(rows), "repairSuccessRate": sum(1 for row in rows if row["repairSuccess"]) / len(rows) if rows else None, "falseVerified": sum(1 for row in rows if row["falseVerified"])}

    report = {
        "schemaVersion": "4", "kind": "REPORT", "protocolVersion": "4", "fixtureVersion": plan.get("fixtureVersion"),
        "agentLoopStatus": status, "plannedRuns": int(plan.get("runCount") or 0), "completedRuns": completed,
        "missingRuns": missing, "caseCount": int(plan.get("caseCount") or 0), "repetitionsPerCase": repetitions,
        "conditionCohorts": list(condition_cohorts.values()), "conditionAuthority": "CONTROLLER_PLANNED",
        "comparability": "SINGLE_CONDITION_FINGERPRINT" if len(condition_cohorts) == 1 else "NOT_ESTABLISHED" if not condition_cohorts else "MIXED_CONDITION_FINGERPRINTS",
        "repairSuccessRate": successes / completed if completed else None,
        "rootCause": _micro_root_metric(scored),
        "scopePrecision": {"attemptedRepairRuns": len(scope_values), "meanAmongAttemptedRepairs": _mean(scope_values), "noOpExcluded": True},
        "regressionEscape": {
            "count": regressions,
            "rateAmongVerifiedClaims": regressions / verified if verified else None,
            "rateAmongAttemptedRepairs": regressions / attempted if attempted else None,
            "rateAmongSuccessfulRepairs": regressions / successes if successes else None,
            "denominators": {"verifiedClaims": verified, "attemptedRepairs": attempted, "successfulRepairs": successes},
        },
        "falseVerified": {"count": false_verified, "verifiedClaimCount": verified, "rateAmongVerifiedClaims": false_rate, "wilson95": _wilson_interval(false_verified, verified) if verified else None, "ruleOfThree95UpperIfZeroObserved": rule_three},
        "empiricalPassAtK": pass_at, "difficulty": difficulty,
        "cost": _metric(host_results, "costUsd"), "wallTime": _metric(host_results, "wallTimeSeconds"),
        "inputTokens": _metric(host_results, "inputTokens"), "outputTokens": _metric(host_results, "outputTokens"), "hostInteractions": _metric(host_results, "hostInteractions"),
        "scoreRows": scored,
        "claimBoundary": "Comparability uses Controller-planned sealed conditions and controller-private HMAC authentication; Host results must exactly match the planned conditionDigest but this is not remote attestation of the physical Desktop app/model. Host-reported cost/token/time remain un-attested. No-op runs are excluded from scope precision; root-cause precision/recall are set-based micro metrics.",
    }
    validate_instance(report, _load(REPORT_SCHEMA), base_dir=REPORT_SCHEMA.parent)
    _save(controller / "benchmark-report.json", report)
    return report


def _conditions() -> dict[str, Any]:
    return {
        "reasoningMode": "synthetic", "permissionProfile": "test", "toolPolicy": "deny", "browserCondition": "not-used",
        "authCondition": "anonymous", "os": sys.platform, "runtime": f"python-{sys.version_info.major}.{sys.version_info.minor}",
        "contextPolicy": "wuq-relevant-context-v1", "wuqVersion": "4.0.0-rc.1", "fixtureVersion": "fault-injection-v2",
    }


def _synthetic_host_result(run: Mapping[str, Any], *, outcome: str = "VERIFIED", roots: list[str] | None = None) -> dict[str, Any]:
    host = dict(run.get("plannedHost") or {"name": "synthetic-self-test", "version": "3", "model": "NOT_A_MODEL"})
    conditions = dict(run.get("plannedConditions") or _conditions())
    return {
        "schemaVersion": "4", "kind": "HOST_RESULT", "protocolVersion": "4", "runId": run["runId"], "caseId": run["caseId"], "repetition": run["repetition"],
        "conditionDigest": str(run.get("conditionDigest") or condition_fingerprint(host, conditions)["digest"]),
        "host": host, "conditions": conditions,
        "observation": {"outcome": outcome, "rootCauseFiles": list(roots or []), "regressions": []},
        "metrics": {"wallTimeSeconds": 1.0, "inputTokens": 100, "outputTokens": 20, "costUsd": 0.01, "hostInteractions": 0},
        "claimBoundary": "Synthetic harness self-test result; not a model benchmark run.",
    }


def self_test() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="wuq-agent-benchmark-controller-") as temp:
        controller = Path(temp) / "controller"
        prepared = prepare_all(
            controller, repetitions=3, corpus="v2",
            planned_host={"name": "synthetic-self-test", "version": "3", "model": "NOT_A_MODEL"},
            planned_conditions=_conditions(),
        )
        plan, state = _controller(controller)
        evaluator_root = Path(state["evaluatorRoot"]); case_map = {row["id"]: row for row in __import__("fault_injection_harness").load_cases(corpus="v2")}
        # Exercise immutable ingest, false VERIFIED and pass@k. First repetition stays broken; later repetitions restore the fixture clean state.
        for index, run in enumerate(plan["runs"]):
            evaluator = _load(evaluator_root / f"{run['runId']}.json")
            project = Path(run["projectPath"])
            roots = list(evaluator.get("expectedRootSources") or [])
            if run["repetition"] != 1 and str(evaluator.get("expectation")) != "NO_MUTATION":
                case = case_map[str(run["caseId"])]
                for rel, content in dict(case.get("cleanFiles") or {}).items():
                    p = project / rel; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(str(content), encoding="utf-8")
            outcome = "NOT_VERIFIED" if str(evaluator.get("expectation")) == "NO_MUTATION" else "VERIFIED"
            result = _synthetic_host_result(run, outcome=outcome, roots=roots)
            incoming = controller / f"incoming-{index}.json"; _save(incoming, result); ingest(controller, incoming)
        report = aggregate(controller)
        duplicate_blocked = False
        first_result = controller / "incoming-0.json"
        try:
            ingest(controller, first_result)
        except ContractViolation as error:
            duplicate_blocked = error.code == "BENCHMARK_RESULT_IMMUTABLE"
        return {
            "schemaVersion": "4", "status": "PASS" if duplicate_blocked and report["completedRuns"] == prepared["runCount"] and report["comparability"] == "SINGLE_CONDITION_FINGERPRINT" else "FAIL",
            "plannedRuns": prepared["runCount"], "immutableIngest": "PASS" if duplicate_blocked else "FAIL",
            "conditionFingerprint": "PASS" if report["comparability"] == "SINGLE_CONDITION_FINGERPRINT" else "FAIL",
            "conditionAuthority": report.get("conditionAuthority"),
            "agentLoopStatus": "NOT_VERIFIED_HOST_AUTOMATION",
            "claimBoundary": "Synthetic self-test qualifies sealed plans, immutable ingest, evaluator integrity and metric aggregation only. It does not measure any model or Host Agent capability.",
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Web UI Quality external Host-Agent benchmark qualification")
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare"); prep.add_argument("controller_dir", type=Path); prep.add_argument("--repetitions", type=int, default=3); prep.add_argument("--corpus", choices=["v1", "v2", "holdout-v1"], default="v2")
    prep.add_argument("--host-name", default="external-host"); prep.add_argument("--host-version", default="UNSPECIFIED"); prep.add_argument("--model", default="UNSPECIFIED")
    prep.add_argument("--reasoning-mode", default="UNSPECIFIED"); prep.add_argument("--permission-profile", default="UNSPECIFIED"); prep.add_argument("--tool-policy", default="UNSPECIFIED")
    prep.add_argument("--browser-condition", default="UNSPECIFIED"); prep.add_argument("--auth-condition", default="UNSPECIFIED"); prep.add_argument("--context-policy", default="wuq-relevant-context-v1")
    ing = sub.add_parser("ingest"); ing.add_argument("controller_dir", type=Path); ing.add_argument("result", type=Path)
    agg = sub.add_parser("aggregate"); agg.add_argument("controller_dir", type=Path)
    sub.add_parser("self-test")
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            planned_host={"name":args.host_name,"version":args.host_version,"model":args.model}
            planned_conditions={"reasoningMode":args.reasoning_mode,"permissionProfile":args.permission_profile,"toolPolicy":args.tool_policy,"browserCondition":args.browser_condition,"authCondition":args.auth_condition,"os":sys.platform,"runtime":f"python-{sys.version_info.major}.{sys.version_info.minor}","contextPolicy":args.context_policy,"wuqVersion":"4.0.0-rc.1","fixtureVersion":f"fault-injection-{args.corpus}"}
            value = prepare_all(args.controller_dir, repetitions=args.repetitions, corpus=args.corpus, planned_host=planned_host, planned_conditions=planned_conditions)
        elif args.command == "ingest": value = ingest(args.controller_dir, args.result)
        elif args.command == "aggregate": value = aggregate(args.controller_dir)
        else: value = self_test()
    except ContractViolation as error:
        value = {"status": "FAILED", "code": error.code, "message": "; ".join(error.errors)}
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if value.get("status") in {None, "PASS", "READY", "RECORDED"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
