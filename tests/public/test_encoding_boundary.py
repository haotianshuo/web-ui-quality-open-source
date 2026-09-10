from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
REQUEST = "检查中文结账页移动端布局，不要修改登录逻辑"


def _run(*flags: str, io_encoding: str) -> subprocess.CompletedProcess[bytes]:
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(ROOT / "runtime" / "python")
    environment["PYTHONIOENCODING"] = io_encoding
    return subprocess.run(
        [
            sys.executable,
            "-B",
            "scripts/run_runtime.py",
            "run",
            *flags,
            "examples/scope-drift-demo",
            REQUEST,
        ],
        cwd=ROOT,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=30,
    )


def test_plain_and_json_output_survive_utf8_and_cp936_process_settings() -> None:
    for io_encoding in ("utf-8", "cp936"):
        plain = _run(io_encoding=io_encoding)
        assert plain.returncode == 0
        plain_text = plain.stdout.decode("utf-8")
        assert "结果：" in plain_text
        assert "下一步：" in plain_text
        assert "�" not in plain_text

        structured = _run("--json", io_encoding=io_encoding)
        assert structured.returncode == 0
        payload = json.loads(structured.stdout.decode("utf-8"))
        task = payload.get("taskResult", payload)
        assert isinstance(task.get("nextAction"), str)
        assert isinstance(task.get("observations"), list)
        assert "�" not in structured.stdout.decode("utf-8")


def test_ci_keeps_exit_contract_while_preserving_utf8_json() -> None:
    for io_encoding in ("utf-8", "cp936"):
        completed = _run("--ci", "--require", "VERIFIED", io_encoding=io_encoding)
        assert completed.returncode == 3
        payload = json.loads(completed.stdout.decode("utf-8"))
        task = payload.get("taskResult", payload)
        assert task.get("outcome") in {"NOT_VERIFIED", "SCOPE_NOT_CONFIRMED", "PARTIAL"}
        assert "�" not in completed.stdout.decode("utf-8")
