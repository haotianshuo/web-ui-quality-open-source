from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from real_user_findings_validation import run_validation  # noqa: E402


def test_fifty_new_real_user_sentences_meet_routing_and_latency_gates() -> None:
    result = run_validation()

    assert result["status"] == "PASS"
    assert result["caseCount"] == 50
    assert result["passed"] == 50
    assert result["failed"] == 0
    assert result["writeAuthorizedTrue"] == 0
    assert result["p95NormalizationMs"] < 5.0
