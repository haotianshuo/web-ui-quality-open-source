"""Outcome measurement from local GA4, Mixpanel, PostHog, or generic exports."""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from html import escape
import json
from pathlib import Path
from statistics import median
from typing import Any, Mapping, Sequence

from .release_info import release_identity


PROVIDERS = {"generic", "ga4", "mixpanel", "posthog"}
DEFAULT_CONFIG = {
    "startEvent": "task_started",
    "successEvent": "task_completed",
    "errorEvent": "task_error",
    "recoveryEvent": "task_recovered",
    "supportEvent": "support_opened",
    "minimumStartedSessions": 20,
    "minimumSuccessRateDelta": 0.03,
    "minimumDurationImprovement": 0.05,
    "maximumRegressionTolerance": 0.02,
}


def _read_rows(path: Path) -> list[Mapping[str, Any]]:
    if path.suffix.casefold() == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            return [dict(row) for row in csv.DictReader(stream)]
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, Mapping):
        payload = payload.get("events") or payload.get("results") or payload.get("data")
    if not isinstance(payload, list) or not all(isinstance(item, Mapping) for item in payload):
        raise ValueError(f"{path}: expected CSV rows or a JSON event array")
    return list(payload)


def _timestamp(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        text = str(value).strip().replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(text).replace(tzinfo=datetime.fromisoformat(text).tzinfo or timezone.utc).timestamp()
        except ValueError:
            return None
    if number > 10_000_000_000_000:
        return number / 1_000_000
    if number > 10_000_000_000:
        return number / 1_000
    return number


def _normalize(row: Mapping[str, Any], provider: str) -> dict[str, Any] | None:
    properties = row.get("properties") if isinstance(row.get("properties"), Mapping) else {}
    if provider == "mixpanel":
        event = row.get("event")
        session = properties.get("session_id") or properties.get("$session_id") or properties.get("distinct_id")
        timestamp = properties.get("time") or row.get("timestamp")
    elif provider == "posthog":
        event = row.get("event")
        session = properties.get("$session_id") or properties.get("session_id") or row.get("distinct_id")
        timestamp = row.get("timestamp") or properties.get("timestamp")
    elif provider == "ga4":
        event = row.get("event_name") or row.get("eventName")
        session = row.get("session_id") or row.get("ga_session_id") or row.get("user_pseudo_id")
        timestamp = row.get("event_timestamp") or row.get("timestamp")
    else:
        event = row.get("event") or row.get("event_name") or row.get("name")
        session = row.get("session_id") or row.get("sessionId") or row.get("user_id") or row.get("distinct_id")
        timestamp = row.get("timestamp") or row.get("time") or row.get("event_timestamp")
    if not event or not session:
        return None
    return {"event": str(event), "session": str(session), "timestamp": _timestamp(timestamp)}


def _summary(rows: Sequence[Mapping[str, Any]], provider: str, config: Mapping[str, Any]) -> dict[str, Any]:
    events = [item for row in rows if (item := _normalize(row, provider)) is not None]
    sessions: dict[str, list[dict[str, Any]]] = {}
    for item in events:
        sessions.setdefault(item["session"], []).append(item)
    start_name = str(config["startEvent"])
    success_name = str(config["successEvent"])
    error_name = str(config["errorEvent"])
    recovery_name = str(config["recoveryEvent"])
    support_name = str(config["supportEvent"])
    started = 0
    succeeded = 0
    errored = 0
    recovered = 0
    support = 0
    durations: list[float] = []
    for session_events in sessions.values():
        names = {item["event"] for item in session_events}
        starts = [item["timestamp"] for item in session_events if item["event"] == start_name and item["timestamp"] is not None]
        successes = [item["timestamp"] for item in session_events if item["event"] == success_name and item["timestamp"] is not None]
        if start_name not in names:
            continue
        started += 1
        if success_name in names:
            succeeded += 1
        if error_name in names:
            errored += 1
            if recovery_name in names or success_name in names:
                recovered += 1
        if support_name in names:
            support += 1
        if starts and successes:
            elapsed = min((finish - min(starts) for finish in successes if finish >= min(starts)), default=None)
            if elapsed is not None and elapsed <= 86_400:
                durations.append(elapsed)
    return {
        "rowCount": len(rows),
        "normalizedEventCount": len(events),
        "sessionCount": len(sessions),
        "startedSessions": started,
        "successfulSessions": succeeded,
        "taskSuccessRate": round(succeeded / started, 6) if started else None,
        "medianTaskDurationSeconds": round(median(durations), 3) if durations else None,
        "erroredSessions": errored,
        "recoveredSessions": recovered,
        "recoveryRate": round(recovered / errored, 6) if errored else None,
        "supportSignalRate": round(support / started, 6) if started else None,
    }


def _delta(before: float | None, after: float | None) -> float | None:
    return round(after - before, 6) if before is not None and after is not None else None


def _relative_improvement(before: float | None, after: float | None) -> float | None:
    return round((before - after) / before, 6) if before not in (None, 0) and after is not None else None


def build_measurement_template() -> dict[str, Any]:
    return {
        "schemaVersion": "1",
        "generator": release_identity(),
        "status": "BASELINE_REQUIRED",
        "supportedProviders": sorted(PROVIDERS),
        "requiredEvents": {key: DEFAULT_CONFIG[key] for key in ("startEvent", "successEvent", "errorEvent", "recoveryEvent", "supportEvent")},
        "minimumStartedSessions": DEFAULT_CONFIG["minimumStartedSessions"],
        "claimBoundary": "No outcome or causal claim is permitted until baseline and post-change exports are supplied with a consistent event definition.",
    }


def measure_outcome(
    baseline_path: str | Path,
    after_path: str | Path,
    *,
    provider: str = "generic",
    config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    provider = provider.casefold().strip()
    if provider not in PROVIDERS:
        raise ValueError(f"unsupported provider: {provider}")
    settings = {**DEFAULT_CONFIG, **dict(config or {})}
    baseline_file = Path(baseline_path).expanduser().resolve()
    after_file = Path(after_path).expanduser().resolve()
    baseline = _summary(_read_rows(baseline_file), provider, settings)
    after = _summary(_read_rows(after_file), provider, settings)
    success_delta = _delta(baseline["taskSuccessRate"], after["taskSuccessRate"])
    duration_improvement = _relative_improvement(baseline["medianTaskDurationSeconds"], after["medianTaskDurationSeconds"])
    recovery_delta = _delta(baseline["recoveryRate"], after["recoveryRate"])
    minimum = int(settings["minimumStartedSessions"])
    sample_ready = baseline["startedSessions"] >= minimum and after["startedSessions"] >= minimum
    tolerance = float(settings["maximumRegressionTolerance"])
    if not sample_ready:
        decision = "INSUFFICIENT_DATA"
    elif success_delta is not None and success_delta < -tolerance:
        decision = "REGRESSED"
    elif duration_improvement is not None and duration_improvement < -tolerance:
        decision = "REGRESSED"
    elif (
        success_delta is not None
        and success_delta >= float(settings["minimumSuccessRateDelta"])
        and (duration_improvement is None or duration_improvement >= -tolerance)
    ) or (
        duration_improvement is not None
        and duration_improvement >= float(settings["minimumDurationImprovement"])
        and (success_delta is None or success_delta >= -tolerance)
    ):
        decision = "IMPROVED"
    else:
        decision = "INCONCLUSIVE"
    return {
        "schemaVersion": "1",
        "generator": release_identity(),
        "status": "PASS" if sample_ready else "INSUFFICIENT_DATA",
        "provider": provider,
        "eventContract": {key: settings[key] for key in ("startEvent", "successEvent", "errorEvent", "recoveryEvent", "supportEvent")},
        "baseline": baseline,
        "after": after,
        "comparison": {
            "taskSuccessRateAbsoluteDelta": success_delta,
            "medianTaskDurationRelativeImprovement": duration_improvement,
            "recoveryRateAbsoluteDelta": recovery_delta,
        },
        "sampleReadiness": {"status": "PASS" if sample_ready else "FAIL", "minimumStartedSessionsPerPeriod": minimum},
        "decision": decision,
        "causalClaim": False,
        "claimBoundary": "A pre/post change is observational. Causality requires a controlled experiment or equivalent design that accounts for traffic, seasonality, audience, and concurrent changes.",
    }


def render_outcome_html(report: Mapping[str, Any]) -> str:
    baseline = report.get("baseline") if isinstance(report.get("baseline"), Mapping) else {}
    after = report.get("after") if isinstance(report.get("after"), Mapping) else {}
    rows = "".join(
        f"<tr><td>{escape(label)}</td><td>{escape(str(baseline.get(key)))}</td><td>{escape(str(after.get(key)))}</td></tr>"
        for key, label in (
            ("startedSessions", "Started sessions"),
            ("taskSuccessRate", "Task success rate"),
            ("medianTaskDurationSeconds", "Median duration (s)"),
            ("recoveryRate", "Recovery rate"),
            ("supportSignalRate", "Support signal rate"),
        )
    )
    decision = escape(str(report.get("decision", report.get("status"))))
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Outcome measurement · {decision}</title><style>
:root{{--ink:#17211d;--muted:#627068;--line:#d9e4de;--paper:#f3f7f5;font-family:Inter,"Segoe UI","PingFang SC",sans-serif}}*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink)}}main{{max-width:960px;margin:auto;padding:48px 20px 80px}}header{{padding:40px;border-radius:24px;background:var(--ink);color:white}}h1{{font-size:clamp(36px,6vw,62px);margin:8px 0}}header p{{color:#bed0c7;line-height:1.6}}.decision{{display:inline-block;padding:7px 10px;border-radius:99px;background:#cef1dc;color:#0e503a;font-size:12px;font-weight:800}}section{{background:white;border:1px solid var(--line);border-radius:18px;overflow:auto;margin-top:18px}}table{{width:100%;border-collapse:collapse}}th,td{{padding:14px;border-bottom:1px solid var(--line);text-align:left}}.boundary{{color:var(--muted);line-height:1.6}}
</style></head><body><main><header><span class="decision">{decision}</span><h1>业务结果测量</h1><p>使用同一事件口径比较改造前后任务成功、时长、恢复和支持信号。</p></header><section><table><thead><tr><th>Metric</th><th>Before</th><th>After</th></tr></thead><tbody>{rows}</tbody></table></section><p class="boundary">{escape(str(report.get('claimBoundary', '')))}</p></main></body></html>"""


def export_outcome_report(report: Mapping[str, Any], output_dir: str | Path) -> dict[str, str]:
    output = Path(output_dir).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    json_path = output / "outcome-measurement-report.json"
    html_path = output / "outcome-measurement-report.html"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    html_path.write_text(render_outcome_html(report), encoding="utf-8")
    return {"report": json_path.name, "html": html_path.name}
