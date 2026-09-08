"""Shared fixtures for the trust-boundary regression suite."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime" / "python"))

TARGET = {"kind": "url", "url": "https://example.test/app", "route": "/app"}
CONDITIONS = {
    "url": "https://example.test/app",
    "scheme": "https",
    "host": "example.test",
    "port": 443,
    "route": "/app",
    "query_policy": "exact",
    "query": "",
    "target_kind": "url",
    "project_root": None,
    "locale": "zh-CN",
    "viewports": [{"width": 390, "height": 844}],
}


@pytest.fixture
def sealed_run(tmp_path):
    """Create a run with one sealed Before phase and return its directory."""
    from web_ui_quality.experience_run import create_experience_run, seal_before, write_phase_file

    run = create_experience_run(
        tmp_path / "runs",
        task_id="t1",
        session_id="s1",
        mode="CHECK",
        target=TARGET,
        conditions=CONDITIONS,
        run_id="wuq-" + "a" * 16,
    )
    run_dir = Path(run["runDir"])
    write_phase_file(run_dir, "before", "page.json", '{"ok":true}')
    seal_before(run_dir)
    return run_dir
