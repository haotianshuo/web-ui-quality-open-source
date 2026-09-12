#!/usr/bin/env python3
"""Bounded natural-language regression validation for the real-user fixes."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime" / "python"
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from web_ui_quality.task_intent_adapter import normalize_task_intent  # noqa: E402


def _scoped(result: dict[str, Any]) -> bool:
    return (
        result["taskIntent"] == "REPAIR"
        and result["writeRequested"] is True
        and result["readOnlyRequired"] is False
        and result["mutation"] == "HOST_GATED"
        and result["scopeIntent"] == "WRITE_ALLOWED_WITH_SCOPE"
        and result["conflictStatus"] == "NONE"
        and result["writeAuthorized"] is False
    )


def _verify(result: dict[str, Any]) -> bool:
    return (
        result["taskIntent"] == "VERIFY_ONLY"
        and result["writeRequested"] is False
        and result["readOnlyRequired"] is True
        and result["mutation"] == "FORBIDDEN"
        and result["writeAuthorized"] is False
    )


def _read_only(result: dict[str, Any]) -> bool:
    return (
        result["writeRequested"] is False
        and result["readOnlyRequired"] is True
        and result["mutation"] == "FORBIDDEN"
        and result["scopeIntent"] == "READ_ONLY"
        and result["writeAuthorized"] is False
    )


def _conflict(result: dict[str, Any]) -> bool:
    return (
        result["taskIntent"] == "REPAIR"
        and result["writeRequested"] is True
        and result["readOnlyRequired"] is True
        and result["mutation"] == "FORBIDDEN"
        and result["scopeIntent"] == "INTENT_CONFLICT"
        and result["conflictStatus"] == "INTENT_CONFLICT"
        and result["writeAuthorized"] is False
    )


def validation_cases() -> list[tuple[str, str, Callable[[dict[str, Any]], bool]]]:
    scoped = [
        "请只允许编辑 src/main.css，其余文件均不得修改",
        "你可以修复，但只能改 src/app.js",
        "请只准调整 components/Card.tsx",
        "只修改这个页面的 HTML，配置文件不要改",
        "Edit src/theme.css only; leave every other file alone",
        "Change src/index.html and leave the rest untouched",
        "Just change this file, and leave everything else alone",
        "Just modify assets/logo.svg, but do not edit anything else",
        "Update config/ui.json only",
        "app.css だけ変更してください",
        "Touch README.md only",
        "Only change src/a.css. Do not touch any other files.",
        "You may repair it, but modify src/b.css only.",
        "Modify src/c.css and leave everything else unchanged.",
        "仅允许修改 src/d.css，其他文件不要碰",
    ]
    verify = [
        "Please check whether the earlier patch introduced regressions.",
        "Verify if the previous repair broke anything.",
        "Confirm the last fix still works.",
        "See whether the prior change caused new errors.",
        "Test the earlier fix for regressions.",
        "Check the previous patch; do not change source.",
        "Verify that the prior repair did not break mobile layout.",
        "comprueba si el parche anterior provocó una regresión",
        "comprueba si el arreglo previo introdujo una regresión",
        "以前の修正で回帰がないか確認してください",
        "检查上次修复是否引入新问题",
        "验证之前的修复有没有回归",
        "确认上次改动是否有问题",
        "check the fix for new errors please",
        "test prior repair for a regression now",
    ]
    read_only = [
        "please make no changes to this repository",
        "change nothing in this repo",
        "touch nothing here",
        "leave everything unchanged for now",
        "without changing code",
        "do not change any files here",
        "don't alter any code",
        "no edits for this task",
        "sin cambiar ningún archivo",
        "ファイルを変更しないでください",
    ]
    polite_conflicts = [
        "Fix the card, but do not modify any files, please",
        "Fix the card, but do not modify any files, please.",
        "Fix the card, but do not modify any files now",
        "Fix the card, but do not modify any files, thanks",
        "Fix the card, but do not modify any files, thank you!",
        "Fix the card, but do not modify any files for me",
        "Fix the card, but do not modify any files if possible",
        "Fix the card, but do not modify any files;\nplease",
        "Fix the card, but do not modify any files… thanks",
        "Fix the card, but do not modify any files, if possible.",
    ]
    return (
        [("scoped_write", text, _scoped) for text in scoped]
        + [("verify_only", text, _verify) for text in verify]
        + [("read_only", text, _read_only) for text in read_only]
        + [("polite_conflict", text, _conflict) for text in polite_conflicts]
    )


def run_validation() -> dict[str, Any]:
    cases = validation_cases()
    timings: list[float] = []
    failures: list[dict[str, str]] = []
    counts: dict[str, int] = {}
    authorization_true = 0
    for category, text, predicate in cases:
        start = time.perf_counter()
        result = normalize_task_intent(text)
        timings.append((time.perf_counter() - start) * 1000)
        authorization_true += int(bool(result.get("writeAuthorized")))
        counts[category] = counts.get(category, 0) + 1
        if not predicate(result):
            failures.append({"category": category, "text": text, "actual": str({k: result.get(k) for k in ("taskIntent", "writeRequested", "readOnlyRequired", "mutation", "scopeIntent", "conflictStatus")})})
    sorted_timings = sorted(timings)
    p95_index = max(0, min(len(sorted_timings) - 1, int(len(sorted_timings) * 0.95) - 1))
    return {
        "status": "PASS" if len(cases) == 50 and not failures and sorted_timings and sorted_timings[p95_index] < 5.0 else "FAIL",
        "caseCount": len(cases),
        "categoryCounts": counts,
        "passed": len(cases) - len(failures),
        "failed": len(failures),
        "writeAuthorizedTrue": authorization_true,
        "p95NormalizationMs": sorted_timings[p95_index] if sorted_timings else None,
        "maxNormalizationMs": max(timings) if timings else None,
        "failures": failures,
        "claimBoundary": "This is a local deterministic intent-normalization regression check; writeAuthorized remains false and no external model or Host authority is used.",
    }


def main() -> int:
    result = run_validation()
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
