#!/usr/bin/env python3
"""Static network-egress policy acceptance for the deterministic Runtime."""
from __future__ import annotations

import ast
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime" / "python" / "web_ui_quality"
RUNTIME_PY = ROOT / "runtime" / "python"

import sys
if str(RUNTIME_PY) not in sys.path:
    sys.path.insert(0, str(RUNTIME_PY))

from web_ui_quality.context_packet import build_relevant_context_packet
from web_ui_quality.project_baseline import build_project_baseline
from web_ui_quality.task_result import build_task_result

# Explicit adapters/localhost infrastructure with a documented network need.
_ALLOWED = {
    "figma_input.py": {"urllib.request"},
    "report_server.py": {"socket", "socketserver"},
}
_DANGEROUS_ROOTS = {"requests", "httpx", "openai", "anthropic", "aiohttp", "socket", "socketserver"}


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    values: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            values.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            values.add(node.module)
    return values


def main() -> int:
    violations: list[str] = []
    observed_exceptions: dict[str, list[str]] = {}
    for path in sorted(RUNTIME.glob("*.py")):
        imports = _imports(path)
        risky = {
            name for name in imports
            if name.split(".")[0] in _DANGEROUS_ROOTS or name.startswith("urllib.request")
        }
        allowed = _ALLOWED.get(path.name, set())
        unapproved = {name for name in risky if not any(name == item or name.startswith(item + ".") for item in allowed)}
        if unapproved:
            violations.append(f"{path.name}: {sorted(unapproved)}")
        if risky:
            observed_exceptions[path.name] = sorted(risky)
    command_policy = (RUNTIME / "command_policy.py").read_text(encoding="utf-8")
    for command in ("curl", "wget", "ssh", "scp", "ftp", "nc", "netcat"):
        if f'"{command}"' not in command_policy:
            violations.append(f"command_policy.py missing network command block: {command}")
    smoke_calls: list[str] = []
    def _blocked(*args, **kwargs):
        smoke_calls.append("network")
        raise AssertionError("offline product-evidence smoke attempted network access")
    with tempfile.TemporaryDirectory(prefix="wuq-privacy-smoke-") as temp:
        project = Path(temp) / "project"
        project.mkdir()
        (project / "App.tsx").write_text("export const App = () => null\n", encoding="utf-8")
        with patch("socket.create_connection", _blocked), patch("urllib.request.urlopen", _blocked):
            baseline = build_project_baseline(project)
            build_relevant_context_packet(project, request="inspect App", task_goal={"goal": "inspect App", "nonGoals": []}, baseline=baseline)
            build_task_result({"status": "PASS", "runId": "smoke", "taskId": "smoke-task", "mode": "CHECK", "taskGoal": {"goal": "inspect App", "nonGoals": []}, "projectBaseline": {"completenessStatus": "COMPLETE"}})
    if smoke_calls:
        violations.append("offline product-evidence smoke attempted network access")

    result = {
        "schemaVersion": "1",
        "status": "PASS" if not violations else "FAIL",
        "unapprovedNetworkImports": violations,
        "explicitNetworkExceptions": observed_exceptions,
        "coreRuntimePolicy": "NO_UNAPPROVED_NETWORK_EGRESS_IMPORTS",
        "offlineProductEvidenceSmoke": "PASS" if not smoke_calls else "FAIL",
        "claimBoundary": "This gate enforces static Runtime import/command policy. Explicit Figma and local report-server adapters remain network-capable and require their own Host/user controls; this is not a proof about the external Host AI provider's data handling.",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
